import tkinter as tk
from tkinter import ttk
import numpy as np
import open3d as o3d
from PIL import Image, ImageTk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class EmbeddedOpen3D:
    def __init__(self, parent, width=500, height=400):
        self.parent = parent
        self.width = width
        self.height = height
        
        self.panel = tk.Label(parent)
        self.panel.pack(fill=tk.BOTH, expand=True)

        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(width=self.width, height=self.height, visible=False)
        
        self.panel.bind("<Button-1>", self.on_mouse_press)
        self.panel.bind("<B1-Motion>", self.on_mouse_drag)
        self.panel.bind("<MouseWheel>", self.on_mouse_wheel) 
        self.panel.bind("<Button-4>", self.on_mouse_wheel)
        self.panel.bind("<Button-5>", self.on_mouse_wheel)

        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        self.pcd = None

    def update_geometry(self, points):
        if self.pcd is None:
            self.pcd = o3d.geometry.PointCloud()
            self.pcd.points = o3d.utility.Vector3dVector(points)
            self.vis.add_geometry(self.pcd)
        else:
            self.pcd.points = o3d.utility.Vector3dVector(points)
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

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dual Visualization App")
        self.root.geometry("1200x600")

        self.main_container = tk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_container, bg="white", width=600)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(self.main_container, bg="black", width=600)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.controls_frame = tk.Frame(root, height=50)
        self.controls_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.init_matplotlib()
        self.init_open3d()
        self.init_controls()

    def init_matplotlib(self):
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.plot(np.random.rand(10))
        self.ax.set_title("Matplotlib Data")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.left_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def init_open3d(self):
        self.o3d_app = EmbeddedOpen3D(self.right_frame, width=600, height=500)
        
        try:
            self.load_bunny()
        except Exception as e:
            print(f"Waiting for data... ({e})")

    def init_controls(self):
        btn_update = tk.Button(self.controls_frame, text="Update Open3D (Add Points)", command=self.update_visualization)
        btn_update.pack(side=tk.LEFT, padx=10)

        btn_clear = tk.Button(self.controls_frame, text="Update Chart", command=self.update_chart)
        btn_clear.pack(side=tk.LEFT, padx=10)

        btn_exit = tk.Button(self.controls_frame, text="Exit", command=self.root.quit)
        btn_exit.pack(side=tk.RIGHT, padx=10)

    def load_bunny(self):
        filename = "bunny.ply"
        with open(filename) as f:
            end_header_idx = next(i for i, line in enumerate(f) if line.strip() == "end_header")
        
        points = np.loadtxt(filename, skiprows=end_header_idx + 1)
        points *= 1000
        return points

    def update_visualization(self):
        try:
            base_points = self.load_bunny()
            
            noise = np.random.uniform(-5, 5, base_points.shape)
            new_points = base_points + noise
            
            self.o3d_app.update_geometry(new_points)
            print("Open3D geometry updated.")
        except Exception as e:
            print(f"Error updating geometry: {e}")

    def update_chart(self):
        self.ax.clear()
        self.ax.plot(np.random.rand(10) * 10)
        self.ax.set_title("Updated Matplotlib Data")
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()