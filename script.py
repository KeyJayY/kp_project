#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import threading
import time
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from pytransform3d.plot_utils import make_3d_axis, plot_vector
from pytransform3d.rotations import matrix_from_axis_angle

if TYPE_CHECKING:
    from collections.abc import Generator
    from mpl_toolkits.mplot3d.axes3d import Axes3D

REVOLUTION_STEPS = 4096


def rot(v: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    return matrix_from_axis_angle(np.hstack((axis, angle))) @ v


def get_arm_positions(
    phi: float, theta: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    A = np.array([0, 4, 0])
    B = np.array([0, -4, 1])
    C = np.array([0, 0, 0.5])
    Cd = np.array([0, 1, 0])
    Cr = rot(C, Cd, phi)
    D = np.array([0, 1, 0])
    Dr = rot(D, Cr, theta)
    pA = A
    pB = pA + B
    pC = pB + Cr
    return A, pA, B, pB, Cr, pC, Dr


def int_to_angle(val: int, min_angle: float = -np.pi, max_angle: float = np.pi) -> float:
    val = max(0, min(REVOLUTION_STEPS - 1, val))
    return min_angle + (max_angle - min_angle) * (val / REVOLUTION_STEPS)


def draw_arm(ax: Axes3D, phi: float, theta: float) -> None:
    A, pA, B, pB, Cr, pC, Dr = get_arm_positions(phi, theta)
    ax.cla()
    ax.set_xlim((-2, 2))
    ax.set_ylim((-2, 2))
    ax.set_zlim((-2, 2))
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    origin = np.zeros(3)
    plot_vector(ax, origin, A, color="r", label="A")
    plot_vector(ax, pA, B, color="g", label="B")
    plot_vector(ax, pB, Cr, color="b", label="C_rotated")
    plot_vector(ax, pC, Dr, color="y", label="D_rotated")
    ax.legend()


def sweep_pairs(a: int, b: int, c: int, d: int, e: int, f: int) -> Generator[tuple[int, int]]:
    i = 0
    pos = c > 0
    while True:
        x = a + i * c
        if x > b if pos else x < b:
            break
        if i % 2 == 0:
            yield from ((x, y) for y in range(d, e + 1, f))
        else:
            yield from ((x, y) for y in range(e, d - 1, -f))
        i += 1


def ray_intersect_cube(ray_origin: np.ndarray, ray_dir: np.ndarray, cube_min: np.ndarray, cube_max: np.ndarray) -> np.ndarray | None:
    dir_fraction = np.empty(3)
    dir_fraction[ray_dir != 0] = 1.0 / ray_dir[ray_dir != 0]
    dir_fraction[ray_dir == 0] = np.inf  # direction parallel to an axis

    t1 = (cube_min[0] - ray_origin[0]) * dir_fraction[0]
    t2 = (cube_max[0] - ray_origin[0]) * dir_fraction[0]
    t3 = (cube_min[1] - ray_origin[1]) * dir_fraction[1]
    t4 = (cube_max[1] - ray_origin[1]) * dir_fraction[1]
    t5 = (cube_min[2] - ray_origin[2]) * dir_fraction[2]
    t6 = (cube_max[2] - ray_origin[2]) * dir_fraction[2]

    tmin = max(min(t1, t2), min(t3, t4), min(t5, t6))
    tmax = min(max(t1, t2), max(t3, t4), max(t5, t6))

    if tmax < 0:
        return None
    if tmin > tmax:
        return None

    t_hit = tmin if tmin >= 0 else tmax
    intersection = ray_origin + t_hit * ray_dir
    return intersection


def raycast(v: np.ndarray, dir_: np.ndarray) -> int:
    room_min = np.array([-100, -200, -50])
    room_max = np.array([+200, +300, +150])
    table_min = np.array([-50, -50, -50])
    table_max = np.array([+50, +50, +0])
    room_intersection = ray_intersect_cube(v, dir_, room_min, room_max)
    table_intersection = ray_intersect_cube(v, dir_, table_min, table_max)
    room_distance = np.linalg.norm(room_intersection - v) if room_intersection is not None else np.inf
    table_distance = np.linalg.norm(table_intersection - v) if table_intersection is not None else np.inf
    return int(min(room_distance, table_distance, 1023.0))


class WorkerThread(threading.Thread):
    def __init__(self, data_ready: threading.Event, data_ack: threading.Event, port: str) -> None:
        super().__init__()
        self.daemon = True
        self.latest = (0.0, 0.0)
        self.running = True
        self.data_ready = data_ready
        self.data_ack = data_ack
        self.port = port

    def run(self) -> None:
        with Path(self.port).open("r+b", buffering=0) as port:
            while self.running:
                try:
                    line = port.readline()
                    port.write(b"\nL\n")
                    if not line:
                        break
                    parts = line.decode("852").strip().split()
                    if len(parts) != 7 or parts[0] != "SWEEP":
                        continue
                    parts = parts[1:]
                    try:
                        a, b, c, d, e, f = map(int, parts)
                        if (
                            not all(0 <= v <= REVOLUTION_STEPS - 1 for v in (a, b, d, e, f))
                            or not -REVOLUTION_STEPS + 1 <= c <= REVOLUTION_STEPS
                        ):
                            raise ValueError
                    except ValueError:
                        port.write(b"\nI\n")
                        continue
                    data = Path("skan.txt").open().readlines()
                    for line in data:
                        time.sleep(0.05)
                        port.write(line.encode())
                        port.flush()
                    port.flush()
                    continue
                    for phi_int, theta_int in sweep_pairs(a, b, c, d, e, f):
                        phi = int_to_angle(phi_int)
                        theta = int_to_angle(theta_int)
                        _, _, _, _, _, pC, Dr = get_arm_positions(phi, theta)
                        length = raycast(pC, Dr)
                        port.write(f"\nR {phi_int} {theta_int} {length}\n".encode())
                        # port.write(f"y+")
                        self.latest = (phi, theta)
                        self.data_ready.set()
                        self.data_ack.wait()
                        self.data_ack.clear()
                except KeyboardInterrupt:
                    self.running = False
                    break


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} /dev/...")
        sys.exit(1)
    port = sys.argv[1]
    ax = make_3d_axis(ax_s=2, unit="m")
    data_ready = threading.Event()
    data_ack = threading.Event()

    worker_thread = WorkerThread(data_ready, data_ack, port)
    worker_thread.start()
    draw_arm(ax, 0.0, 0.0)
    plt.ion()
    plt.show()
    try:
        while worker_thread.running:
            plt.pause(0.01)
            if data_ready.is_set():
                phi, theta = worker_thread.latest
                draw_arm(ax, phi, theta)
                data_ready.clear()
                data_ack.set()
    except KeyboardInterrupt:
        worker_thread.running = False


if __name__ == "__main__":
    main()
