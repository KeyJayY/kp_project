import open3d as o3d
import numpy as np
import time

def load_ply_points(filename):
    with open(filename, "r") as f:
        lines = f.readlines()
    start_idx = next(i for i, line in enumerate(lines) if line.strip() == "end_header") + 1
    points = []
    for line in lines[start_idx:]:
        parts = line.strip().split()
        if len(parts) != 3:
            continue
        x, y, z = map(float, parts)
        points.append([x, y, z])
    return np.array(points)

bunny_points = load_ply_points("bunny.ply")
bunny_points *= 1000 

pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(bunny_points)

vis = o3d.visualization.Visualizer()
vis.create_window(window_name="Bunny Point Cloud", width=800, height=600)
vis.add_geometry(pcd)
vis.reset_view_point(True) 


for i in range(1, len(bunny_points), 500): 
    subset = bunny_points[:i]
    pcd.points = o3d.utility.Vector3dVector(subset)
    vis.update_geometry(pcd)
    vis.poll_events()
    vis.update_renderer()
    time.sleep(0.01)

vis.run()
vis.destroy_window()
