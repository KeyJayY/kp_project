import serial
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
import math

def spherical_to_cartesian(r, theta, phi):
    x = r * math.sin(theta) * math.cos(phi)
    y = r * math.sin(theta) * math.sin(phi)
    z = r * math.cos(theta)
    return x, y, z


PORT = "/dev/pts/6"
BAUDRATE = 9600
TIMEOUT = 1.0

ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)

x_data, y_data, z_data = [], [], []

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

scat = ax.scatter([], [], [], c='b', marker='o')

ax.set_title("Live 3D serial data")
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")
ax.set_xlim(0, 1000)
ax.set_ylim(0, 1000)
ax.set_zlim(0, 1000)
ax.grid(True)

def update(frame):
    ser.write(b"b")
    time.sleep(0.005)
    response = ser.readline().decode().strip()

    if response:
        print(response)
        try:
            parts = response.replace(',', ' ').split()
            if len(parts) >= 3:
                r = float(parts[0])
                theta = float(parts[1])
                phi = float(parts[2])
                x, y, z = spherical_to_cartesian(r, theta, phi)
                x_data.append(x)
                y_data.append(y)
                z_data.append(z)

                # if len(x_data) > 100:
                #     x_data.pop(0)
                #     y_data.pop(0)
                #     z_data.pop(0)

                ax.clear()
                ax.scatter(x_data, y_data, z_data, c='b', marker='o')
                ax.set_xlabel("X")
                ax.set_ylabel("Y")
                ax.set_zlabel("Z")
                ax.set_title("Live 3D serial data")
                ax.set_xlim(min(x_data), max(x_data))
                ax.set_ylim(min(y_data), max(y_data))
                ax.set_zlim(min(z_data), max(z_data))
        except ValueError:
            pass

ani = FuncAnimation(fig, update, interval=200)
plt.show()
