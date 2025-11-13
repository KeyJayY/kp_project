import serial
import time
import math
import threading
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

REVOLUTION_STEPS = 4096
PORT = "/dev/pts/6"
BAUDRATE = 9600
TIMEOUT = 1

x_data, y_data, z_data = [], [], []

root = tk.Tk()
root.title("3D LIDAR Simulation Viewer")
root.geometry("1000x850")

frame_plot = ttk.Frame(root)
frame_plot.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

frame_controls = ttk.Frame(root)
frame_controls.pack(side=tk.TOP, fill=tk.X, pady=5)

frame_logs = ttk.Frame(root)
frame_logs.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

fig = Figure(figsize=(6, 6))
ax = fig.add_subplot(111, projection='3d')
ax.set_title("LIDAR Sweep Data")
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")
ax.set_xlim(-1000, 1000)
ax.set_ylim(-1000, 1000)
ax.set_zlim(-1000, 1000)

canvas = FigureCanvasTkAgg(fig, master=frame_plot)
canvas.draw()
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

log_text = tk.Text(frame_logs, height=10, state=tk.DISABLED)
log_text.pack(fill=tk.BOTH, expand=True)
scrollbar = ttk.Scrollbar(frame_logs, command=log_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
log_text["yscrollcommand"] = scrollbar.set

stop_flag = False
ser = None

def clamp(val, min_val, max_val):
    return min(max(val, min_val), max_val)

def log(msg):
    log_text.configure(state=tk.NORMAL)
    log_text.insert(tk.END, msg + "\n")
    log_text.configure(state=tk.DISABLED)
    log_text.see(tk.END)

def int_to_angle(val, min_angle=-math.pi, max_angle=math.pi):
    val = max(0, min(REVOLUTION_STEPS - 1, val))
    return min_angle + (max_angle - min_angle) * (val / REVOLUTION_STEPS)

def spherical_to_cartesian(r, theta, phi):
    x = r * math.sin(theta) * math.cos(phi)
    y = r * math.sin(theta) * math.sin(phi)
    z = r * math.cos(theta)
    return x, y, z

def update_plot():
    ax.clear()
    ax.scatter(x_data, y_data, z_data, c='b', marker='o', s=5)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("LIDAR Sweep Data")
    canvas.draw_idle()

def read_serial(a, b, c, d, e, f):
    global stop_flag, ser
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    except serial.SerialException as err:
        log(f"Error opening serial port: {err}")
        return

    log(f"Connected to {PORT} at {BAUDRATE} baud.")
    time.sleep(1)

    sweep_cmd = f"SWEEP {a} {b} {c} {d} {e} {f}\n"
    ser.write(sweep_cmd.encode())
    log(f"> {sweep_cmd.strip()}")

    while not stop_flag:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            log(line)
            parts = line.split()
            if len(parts) == 4 and parts[0] == "R":
                try:
                    phi_int = int(parts[1])
                    theta_int = int(parts[2])
                    r = float(parts[3])

                    phi = int_to_angle(phi_int)
                    theta = int_to_angle(theta_int)
                    x, y, z = spherical_to_cartesian(r, theta, phi)

                    x_data.append(x)
                    y_data.append(y)
                    z_data.append(z)

                    root.after(0, update_plot)
                except ValueError:
                    pass
        except serial.SerialException:
            log("Serial connection lost.")
            break

    ser.close()
    log("Serial thread stopped.")

def start_reading():
    global stop_flag
    stop_flag = False
    try:
        a = int(clamp(float(entry_a.get())/360*REVOLUTION_STEPS, 0, 4095))
        b = int(clamp(float(entry_b.get())/360*REVOLUTION_STEPS, 0, 4095))
        c = int(clamp(float(entry_c.get())/360*REVOLUTION_STEPS, 0, 4095))
        d = int(clamp(float(entry_d.get())/360*REVOLUTION_STEPS, 0, 4095))
        e = int(clamp(float(entry_e.get())/360*REVOLUTION_STEPS, 0, 4095))
        f = int(clamp(float(entry_f.get())/360*REVOLUTION_STEPS, 0, 4095))
    except ValueError:
        log("Invalid sweep parameters.")
        return

    threading.Thread(target=read_serial, args=(a, b, c, d, e, f), daemon=True).start()
    log("Started reading from simulated device.")

def stop_reading():
    global stop_flag, ser
    stop_flag = True
    if ser and ser.is_open:
        ser.close()
    log("Stopping serial thread...")

ttk.Label("con")
ttk.Label(frame_controls, text="phi start:").pack(side=tk.LEFT)
entry_a = ttk.Entry(frame_controls, width=6)
entry_a.insert(0, "0")
entry_a.pack(side=tk.LEFT, padx=2)

ttk.Label(frame_controls, text="phi end:").pack(side=tk.LEFT)
entry_b = ttk.Entry(frame_controls, width=6)
entry_b.insert(0, "360")
entry_b.pack(side=tk.LEFT, padx=2)

ttk.Label(frame_controls, text="phi step:").pack(side=tk.LEFT)
entry_c = ttk.Entry(frame_controls, width=6)
entry_c.insert(0, "10")
entry_c.pack(side=tk.LEFT, padx=2)

ttk.Label(frame_controls, text="theta start:").pack(side=tk.LEFT)
entry_d = ttk.Entry(frame_controls, width=6)
entry_d.insert(0, "0")
entry_d.pack(side=tk.LEFT, padx=2)

ttk.Label(frame_controls, text="theta end:").pack(side=tk.LEFT)
entry_e = ttk.Entry(frame_controls, width=6)
entry_e.insert(0, "360")
entry_e.pack(side=tk.LEFT, padx=2)

ttk.Label(frame_controls, text="theta start:").pack(side=tk.LEFT)
entry_f = ttk.Entry(frame_controls, width=6)
entry_f.insert(0, "10")
entry_f.pack(side=tk.LEFT, padx=2)

start_button = ttk.Button(frame_controls, text="Start", command=start_reading)
stop_button = ttk.Button(frame_controls, text="Stop", command=stop_reading)
start_button.pack(side=tk.LEFT, padx=10)
stop_button.pack(side=tk.LEFT, padx=10)

root.protocol("WM_DELETE_WINDOW", lambda: (stop_reading(), root.destroy()))
root.mainloop()
