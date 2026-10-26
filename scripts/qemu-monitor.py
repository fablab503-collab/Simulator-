"""Sends commands to a QEMU human monitor socket, one per argument."""
import socket
import sys
import time

sock_path, *commands = sys.argv[1:]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(sock_path)
s.settimeout(2)
for cmd in commands:
    s.sendall(cmd.encode() + b"\n")
    time.sleep(0.5)
try:
    while s.recv(4096):
        pass
except socket.timeout:
    pass
s.close()
