import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def load_points(filename):
    points = []
    with open(filename, "r") as f:
        lines = f.readlines()
    start_idx = next(i for i, line in enumerate(lines) if line.strip() == "end_header") + 1
    for line in lines[start_idx:]:
        parts = line.strip().split()
        if len(parts) != 3:
            continue
        x, y, z = map(float, parts)
        points.append((x, y, z))
    return points

def draw_plot():
    filename = "bunny.ply"
    points = load_points(filename)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]

    fig = plt.Figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(xs, ys, zs, s=1, c="black")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("Stanford Bunny (point cloud)")

    canvas = FigureCanvasTkAgg(fig, master=window)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

window = tk.Tk()
window.title("Bunny Viewer (Matplotlib in Tkinter)")
window.geometry("800x800")

button = tk.Button(window, text="Load and Show Bunny", command=draw_plot)
button.pack(pady=10)

window.mainloop()
