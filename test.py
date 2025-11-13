import open3d as o3d
import numpy as np
import time

bunny_points = np.loadtxt("bunny.ply", skiprows=next(i for i, line in enumerate(open("bunny.ply")) if line.strip() == "end_header") + 1)
bunny_points *= 1000

app = o3d.visualization.gui.Application.instance
app.initialize()

window = app.create_window("Bunny Viewer", 1000, 800)
scene = o3d.visualization.gui.SceneWidget()
scene.scene = o3d.visualization.rendering.Open3DScene(window.renderer)
window.add_child(scene)

pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(bunny_points)
scene.scene.add_geometry("bunny", pcd, o3d.visualization.rendering.MaterialRecord())

def update_geometry():
    for i in range(1, len(bunny_points), 500):
        subset = bunny_points[:i]
        pcd.points = o3d.utility.Vector3dVector(subset)
        scene.scene.remove_geometry("bunny")
        scene.scene.add_geometry("bunny", pcd, o3d.visualization.rendering.MaterialRecord())
        time.sleep(0.01)

app.post_to_main_thread(window, update_geometry)
app.run()
