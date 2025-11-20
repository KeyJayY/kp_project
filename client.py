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
import open3d as o3d
import numpy as np

REVOLUTION_STEPS = 4096
BAUDRATE = 9600
TIMEOUT = 1

class MathUtils:
    @staticmethod
    def clamp(val, min_val, max_val):
        return min(max(val, min_val), max_val)

    @staticmethod
    def int_to_angle(val, steps=REVOLUTION_STEPS, min_angle=-math.pi, max_angle=math.pi):
        val = max(0, min(steps - 1, val))
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
        time.sleep(1)

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
                line = self.ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                self.put("log", line)

                parts = line.split()
                if len(parts) == 4 and parts[0] == "R":
                    try:
                        phi_int = int(parts[1])
                        theta_int = int(parts[2])
                        r = float(parts[3])

                        phi = MathUtils.int_to_angle(phi_int)
                        theta = MathUtils.int_to_angle(theta_int)
                        x, y, z = MathUtils.spherical_to_cartesian(r, theta, phi)

                        self.put("point", (x, y, z))
                    except ValueError:
                        pass

            except serial.SerialException:
                self.put("log", "Serial connection lost.")
                break

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
        self.root.geometry("1200x850")

        frame_plot = ttk.Frame(self.root)
        frame_plot.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.frame_controls = ttk.Frame(self.root)
        self.frame_controls.pack(side=tk.TOP, fill=tk.X, pady=5)

        frame_logs = ttk.Frame(self.root)
        frame_logs.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(6, 6))
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.set_title("LIDAR Sweep Data")
        self.ax.set_xlim(-1000, 1000)
        self.ax.set_ylim(-1000, 1000)
        self.ax.set_zlim(-1000, 1000)
        self.ax.view_init(elev=30, azim=-60)

        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")

        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_plot)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(frame_logs, height=10, state=tk.DISABLED)
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
        ttk.Button(self.frame_controls, text="Show Open3D", command=self.show_open3d).pack(side=tk.LEFT, padx=10)

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
        entry = ttk.Entry(self.frame_controls, width=6)
        entry.insert(0, default)
        entry.pack(side=tk.LEFT, padx=2)
        return entry

    def update_plot(self):
        self.ax.cla()
        self.ax.scatter(self.x_data, self.y_data, self.z_data, s=5)
        self.ax.scatter([0], [0], [0], s=80, color="red")
        self.ax.set_title("LIDAR Sweep Data")
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
            self._real_log("No data to display.")
            return

        filename = "scan_output.ply"
        self.save_ply()

        points = np.loadtxt(
            filename,
            skiprows=next(i for i, line in enumerate(open(filename)) if line.strip() == "end_header") + 1
        )

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)

        o3d.visualization.draw_geometries([pcd])

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
