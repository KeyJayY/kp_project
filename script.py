#!/usr/bin/env python3
import os
import time
import random

device = "/dev/pts/5"
print(f"Opening {device} for read/write...")

with open(device, "r+b", buffering=0) as port:
    print("Listening... (send '?' from the other end)")

    while True:
        data = port.read(1)
        if not data:
            time.sleep(0.01)
            continue
        if data == b'?':
            num = random.randint(0, 999)
            msg = f"{num}\n".encode()
            port.write(msg)
            port.flush()
            print(f"Received '?', sent: {num}")
        elif data in (b'q', b'Q'):
            print("Received 'q' -> exiting.")
            break
        else:
            continue
