#!/usr/bin/env python3
import os
import time
import math
import random

device = "/dev/pts/5"
ply_file = "bunny.ply"

def load_points(filename, step=10):
    points = []
    with open(filename, "r") as f:
        lines = f.readlines()
    start_idx = next(i for i, line in enumerate(lines) if line.strip() == "end_header") + 1
    for i, line in enumerate(lines[start_idx:]):
        if i % step != 0:
            continue
        parts = line.strip().split()
        if len(parts) != 3:
            continue
        x, y, z = map(float, parts)
        r = math.sqrt(x*x + y*y + z*z) * 1000.0
        if r == 0:
            theta = 0.0
        else:
            theta = math.acos(z / (r / 1000.0))
        phi = math.atan2(y, x)
        points.append((r, theta, phi))
    return points

points = load_points(ply_file)
print(f"Loaded {len(points)} points from {ply_file}")

print(f"Opening {device} for read/write...")

with open(device, "r+b", buffering=0) as port:
    print("Listening... ('?' = random point, 'b'/'B' = bunny point, 'q'/'Q' = quit)")
    index = 0

    while True:
        data = port.read(1)
        if not data:
            time.sleep(0.001)
            continue

        if data == b'?':
            r = random.uniform(0, 1000)
            theta = random.uniform(0, math.pi)
            phi = random.uniform(0, 2 * math.pi)
            msg = f"{r:.2f},{theta:.6f},{phi:.6f}\n".encode()
            port.write(msg)
            port.flush()
            print(f"Sent random point: r={r:.2f}, theta={theta:.6f}, phi={phi:.6f}")

        elif data in (b'b', b'B'):
            if index >= len(points):
                index = 0
            r, theta, phi = points[index]
            msg = f"{r:.2f},{theta:.6f},{phi:.6f}\n".encode()
            port.write(msg)
            port.flush()
            print(f"Sent bunny point {index}: r={r:.2f}, theta={theta:.6f}, phi={phi:.6f}")
            index += 1

        elif data in (b'q', b'Q'):
            print("Received 'q' -> exiting.")
            break
