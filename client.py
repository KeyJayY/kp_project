import sys
import serial
import time
import math
import threading
import tkinter as tk
from tkinter import ttk
from queue import Queue

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.cm as cm
import matplotlib

import open3d as o3d
import numpy as np
from PIL import Image, ImageTk

REVOLUTION_STEPS = 200
BAUDRATE = 115200
TIMEOUT = 1


class MathUtils:
    @staticmethod
    def clamp(val, min_val, max_val):
        return min(max(val, min_val), max_val)

    @staticmethod
    def int_to_angle(val, steps=REVOLUTION_STEPS, min_angle=-math.pi, max_angle=math.pi):
        val = ((val % REVOLUTION_STEPS) + REVOLUTION_STEPS) % REVOLUTION_STEPS
        return min_angle + (max_angle - min_angle) * (val / steps)

    @staticmethod
    def spherical_to_cartesian(r, theta, phi):
        x = r * math.sin(theta) * math.cos(phi)
        y = r * math.sin(theta) * math.sin(phi)
        z = r * math.cos(theta)
        return x, y, z

class SerialReader(threading.Thread):
    def __init__(self, port, parameters, queue):
        super().__init__(daemon=True)
        self.port = port
        self.parameters = parameters
        self.queue = queue
        self.stop_flag = False
        self.ser = None

    def put(self, type_, payload=None):
        self.queue.put((type_, payload))

    def run(self):
        try:
            self.ser = serial.Serial(self.port, BAUDRATE, timeout=TIMEOUT)
        except serial.SerialException as err:
            self.put("log", f"Error opening serial port: {err}")
            self.put("stopped")
            return

        self.put("log", f"Connected to {self.port} at {BAUDRATE} baud.")
        time.sleep(2)

        sweep_cmd = f"SWEEP {' '.join(str(p) for p in self.parameters)}\n"
        try:
            self.ser.write(sweep_cmd.encode())
        except:
            self.put("log", "Failed to send sweep command.")
            self.put("stopped")
            return

        self.put("log", f"> {sweep_cmd.strip()}")

        while not self.stop_flag:
            try:
                if not self.ser or not self.ser.is_open:
                    break

                line = self.ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                parts = line.split()
                self.put("log", line)
                
                if len(parts) == 4 and parts[0] == "R":
                    try:
                        phi_int = int(parts[1])
                        theta_int = int(parts[2])
                        r = float(parts[3])

                        phi = MathUtils.int_to_angle(phi_int)
                        theta = MathUtils.int_to_angle(theta_int)
                        x, y, z = MathUtils.spherical_to_cartesian(r, theta, phi)
                        print(f"{phi:.2f}, {theta:.2f}, {r:.2f}, x,y,z")

                        self.put("point", (x, y, z))
                    except ValueError:
                        self.put("log", f"Corrupted packet data: {line}")
                else:
                    self.put("log", f"Garbage ignored: {line}")

            except (serial.SerialException, TypeError, OSError) as e:
                if self.stop_flag:
                    break
                else:
                    self.put("log", f"Serial connection lost: {e}")
                    break
            except Exception as e:
                self.put("log", f"Unexpected error: {e}")

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass

        self.put("log", "Serial thread stopped.")
        self.put("stopped")

    def stop(self):
        self.stop_flag = True
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass


class EmbeddedOpen3D:
    def __init__(self, parent, width=700, height=600):
        self.parent = parent
        self.width = width
        self.height = height
        
        self.panel = tk.Label(parent)
        self.panel.pack(fill=tk.BOTH, expand=True)

        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(width=self.width, height=self.height, visible=False)

        opt = self.vis.get_render_option()
        opt.background_color = np.asarray([1.0, 1.0, 1.0])
        opt.point_size = 5.0

        self.panel.bind("<Button-1>", self.on_mouse_press)
        self.panel.bind("<B1-Motion>", self.on_mouse_drag)
        self.panel.bind("<MouseWheel>", self.on_mouse_wheel) 
        self.panel.bind("<Button-4>", self.on_mouse_wheel)
        self.panel.bind("<Button-5>", self.on_mouse_wheel)

        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        self.pcd = None

        self.render_image()

    def update_geometry(self, points):
        if points.shape[0] == 0:
            return
            
        z_vals = points[:, 2]
        min_z = np.min(z_vals)
        max_z = np.max(z_vals)
        z_range = max_z - min_z
        
        if z_range == 0:
            z_range = 1.0
            
        norm_z = (z_vals - min_z) / z_range
        
        try:
            colormap = matplotlib.colormaps['jet']
        except AttributeError:
            colormap = cm.get_cmap("jet")

        colors = colormap(norm_z)[:, :3]

        if self.pcd is None:
            self.pcd = o3d.geometry.PointCloud()
            self.pcd.points = o3d.utility.Vector3dVector(points)
            self.pcd.colors = o3d.utility.Vector3dVector(colors)
            self.vis.add_geometry(self.pcd)
            self.vis.reset_view_point(True)
        else:
            self.pcd.points = o3d.utility.Vector3dVector(points)
            self.pcd.colors = o3d.utility.Vector3dVector(colors)
            self.vis.update_geometry(self.pcd)

        self.render_image()

    def render_image(self):
        self.vis.poll_events()
        self.vis.update_renderer()
        
        img_data = self.vis.capture_screen_float_buffer(do_render=True)
        img_data = (np.asarray(img_data) * 255).astype(np.uint8)
        
        img_pil = Image.fromarray(img_data)
        img_tk = ImageTk.PhotoImage(image=img_pil)
        
        self.panel.configure(image=img_tk)
        self.panel.image = img_tk

    def on_mouse_press(self, event):
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def on_mouse_drag(self, event):
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        
        ctr = self.vis.get_view_control()
        ctr.rotate(dx * 5.0, dy * 5.0)
        
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.render_image()

    def on_mouse_wheel(self, event):
        ctr = self.vis.get_view_control()
        if event.num == 5 or event.delta < 0:
            ctr.scale(-1.0)
        elif event.num == 4 or event.delta > 0:
            ctr.scale(1.0)
            
        self.render_image()


class LidarApp:
    def __init__(self, port):
        self.port = port
        self.serial_thread = None
        self.x_data = []
        self.y_data = []
        self.z_data = []
        self.queue = Queue()

        self.root = tk.Tk()
        self.root.title("3D LIDAR Simulation Viewer")
        self.root.geometry("1400x900")

        self.main_viz_frame = tk.Frame(self.root)
        self.main_viz_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.main_viz_frame.columnconfigure(0, weight=1, uniform="equal_split")
        self.main_viz_frame.columnconfigure(1, weight=1, uniform="equal_split")
        self.main_viz_frame.rowconfigure(0, weight=1)

        self.frame_mpl = tk.Frame(self.main_viz_frame, bg="white")
        self.frame_mpl.grid(row=0, column=0, sticky="nsew")

        self.frame_o3d = tk.Frame(self.main_viz_frame, bg="black")
        self.frame_o3d.grid(row=0, column=1, sticky="nsew")

        self.frame_controls = ttk.Frame(self.root)
        self.frame_controls.pack(side=tk.TOP, fill=tk.X, pady=5)

        frame_logs = ttk.Frame(self.root)
        frame_logs.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(5, 5))
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.set_title("Live LIDAR Data (Matplotlib)")
        self.ax.set_xlim(-1000, 1000)
        self.ax.set_ylim(-1000, 1000)
        self.ax.set_zlim(-1000, 1000)
        self.ax.view_init(elev=30, azim=-60)

        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_mpl)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.o3d_viewer = EmbeddedOpen3D(self.frame_o3d, width=700, height=650)

        self.log_text = tk.Text(frame_logs, height=8, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(frame_logs, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text["yscrollcommand"] = scrollbar.set

        self.entry_a = self._add_control("phi start:", "0")
        self.entry_b = self._add_control("phi end:", "360")
        self.entry_c = self._add_control("phi step:", "10")
        self.entry_d = self._add_control("theta start:", "0")
        self.entry_e = self._add_control("theta end:", "360")
        self.entry_f = self._add_control("theta step:", "10")

        ttk.Button(self.frame_controls, text="Start", command=self.start).pack(side=tk.LEFT, padx=10)
        ttk.Button(self.frame_controls, text="Stop", command=self.stop).pack(side=tk.LEFT, padx=10)
        ttk.Button(self.frame_controls, text="Save PLY", command=self.save_ply).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(self.frame_controls, text="Show/Update Open3D", command=self.show_open3d).pack(side=tk.LEFT, padx=10)

        self.root.after(10, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    def _real_log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.configure(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def _real_add_point(self, x, y, z):
        self.x_data.append(x)
        self.y_data.append(y)
        self.z_data.append(z)
        self.update_plot()

    def _add_control(self, label, default):
        ttk.Label(self.frame_controls, text=label).pack(side=tk.LEFT)
        entry = ttk.Entry(self.frame_controls, width=5)
        entry.insert(0, default)
        entry.pack(side=tk.LEFT, padx=2)
        return entry

    def update_plot(self):
        self.ax.cla()
        self.ax.scatter(self.x_data, self.y_data, self.z_data, s=5)
        self.ax.scatter([0], [0], [0], s=80, color="red")
        self.ax.set_title("Live LIDAR Data (Matplotlib)")
        self.canvas.draw_idle()

    def process_queue(self):
        try:
            while True:
                msg_type, payload = self.queue.get_nowait()

                if msg_type == "log":
                    self._real_log(payload)

                elif msg_type == "point":
                    x, y, z = payload
                    self._real_add_point(x, y, z)

                elif msg_type == "stopped":
                    self.serial_thread = None

        except:
            pass

        self.root.after(10, self.process_queue)

    def start(self):
        if self.serial_thread:
            self._real_log("Already running.")
            return

        try:
            params = [
                int(MathUtils.clamp(float(self.entry_a.get()) / 360 * REVOLUTION_STEPS, 0, 4095)),
                int(MathUtils.clamp(float(self.entry_b.get()) / 360 * REVOLUTION_STEPS, 0, 4095)),
                int(MathUtils.clamp(float(self.entry_c.get()) / 360 * REVOLUTION_STEPS, 0, 4095)),
                int(MathUtils.clamp(float(self.entry_d.get()) / 360 * REVOLUTION_STEPS, 0, 4095)),
                int(MathUtils.clamp(float(self.entry_e.get()) / 360 * REVOLUTION_STEPS, 0, 4095)),
                int(MathUtils.clamp(float(self.entry_f.get()) / 360 * REVOLUTION_STEPS, 0, 4095)),
            ]
        except ValueError:
            self._real_log("Invalid sweep parameters.")
            return

        self.x_data.clear()
        self.y_data.clear()
        self.z_data.clear()
        
        self.serial_thread = SerialReader(self.port, params, self.queue)
        self.serial_thread.start()

        self._real_log("Started reading from simulated device.")

    def stop(self):
        if self.serial_thread:
            self.serial_thread.stop()
            self._real_log("Stopping serial thread...")

    def save_ply(self):
        if not self.x_data:
            self._real_log("No data to save.")
            return

        filename = "scan_output.ply"
        n = len(self.x_data)

        with open(filename, "w") as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {n}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("end_header\n")

            for x, y, z in zip(self.x_data, self.y_data, self.z_data):
                f.write(f"{x} {y} {z}\n")

        self._real_log(f"Saved point cloud to {filename}")

    def show_open3d(self):
        if not self.x_data:
            self._real_log("No data to display in Open3D.")
            return

        points = np.vstack((self.x_data, self.y_data, self.z_data)).T

        self.o3d_viewer.update_geometry(points)
        self._real_log(f"Updated Open3D view with {len(points)} points.")

    def exit_app(self):
        self.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lidar.py <serialport>")
        sys.exit(1)

    PORT = sys.argv[1]
    app = LidarApp(PORT)
    app.run()