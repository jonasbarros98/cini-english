#!/usr/bin/env python3
import sys
path = "requirements.txt"
try:
    with open(path, "rb") as f:
        d = f.read()
    if b"\x00" in d[:min(100, len(d))]:
        with open(path, "wb") as f:
            f.write(d.decode("utf-16-le").encode("utf-8"))
        print("Converted requirements.txt from UTF-16 to UTF-8")
except Exception as e:
    print("fix_requirements_encoding:", e, file=sys.stderr)
    sys.exit(0)
