#!/usr/bin/env python3
"""Corrige encoding de requirements.txt se estiver em UTF-16 (Windows)."""
import os
path = "requirements.txt"
if not os.path.exists(path):
    exit(0)
with open(path, "rb") as f:
    d = f.read()
if len(d) > 1 and d[1:2] == b"\x00":
    with open(path, "wb") as f:
        f.write(d.decode("utf-16-le").encode("utf-8"))
