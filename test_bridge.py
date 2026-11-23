# -*- coding: utf-8 -*-
"""test_bridge.py — kiem thu tang HTTP cua cau noi bang FakeCAD.

Chay:  python3 test_bridge.py
  - Khoi dong server that (bridge.py) voi CAD_BRIDGE_FAKE=1 tren cong 18765
  - Goi cac endpoint bang urllib, doi chieu ket qua voi so lieu tu tinh.
Khang dinh (anchors):
  - HCN 10x5 kin -> dien tich 50, chu vi 30
  - Tron r=2 -> dien tich 4*pi = 12.566370614359172, chu vi 2*pi*r cung so
  - Polyline MO (khong kin) khong vao bang dien tich
  - Thieu token -> 401; /ping khong can token
  - Ve them HCN 4x4 kin -> tong dien tich tang them 16
  - LISP (getvar "ACADVER") -> "24.0" (ban gia lap tra dung version AutoCAD 2022)
"""
import json
import math
import os
import sys
import threading
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["CAD_BRIDGE_FAKE"] = "1"
os.environ["CAD_BRIDGE_PORT"] = "18765"

import bridge  # noqa: E402

PORT = 18765
TOKEN = bridge.TOKEN
BASE = "http://127.0.0.1:%d" % PORT

passed = 0
failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("PASS %s" % name)
    else:
        failed += 1
        print("FAIL %s %s" % (name, extra))


def req(method, path, token=True, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if token:
        r.add_header("X-Bridge-Token", TOKEN)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def main():
    server = bridge.ThreadingHTTPServer(("127.0.0.1", PORT), bridge.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    s, b = req("GET", "/ping", token=False)
    check("ping khong can token", s == 200 and b.get("ok") is True, str(b))

    s, b = req("GET", "/status", token=False)
    check("thieu token -> 401", s == 401, str(b))

    s, b = req("GET", "/status")
    check("status ok + FakeCAD", s == 200 and b.get("connected") is True
          and "FakeCAD" in b.get("version", ""), str(b))

    s, b = req("GET", "/layers")
    check("layers co 0 va S1", s == 200 and set(b.get("layers", [])) == {"0", "S1"}, str(b))

    s, b = req("GET", "/areas")
    rows = b.get("rows", [])
    check("areas: 2 hang kin (HCN + tron)", s == 200 and len(rows) == 2, str(b))
    check("areas: HCN 10x5 = 50 / 30",
          any(abs(r["area"] - 50.0) < 1e-9 and abs(r["perimeter"] - 30.0) < 1e-9
              for r in rows), str(rows))
    check("areas: tron r=2 = 4pi",
          any(abs(r["area"] - 4 * math.pi) < 1e-9
              and abs(r["perimeter"] - 4 * math.pi) < 1e-9 for r in rows), str(rows))
    check("areas: tong = 50 + 4pi",
          abs(b.get("total_area", 0) - (50.0 + 4 * math.pi)) < 1e-9, str(b))

    s, b = req("GET", "/entities?type=circle")
    check("entities loc circle = 1", s == 200 and len(b.get("entities", [])) == 1, str(b))

    s, b = req("POST", "/lisp", body={"expr": '(getvar "ACADVER")'})
    check("lisp ACADVER = 24.0", s == 200 and b.get("result") == "24.0", str(b))

    s, b = req("POST", "/draw", body={"items": [
        {"kind": "polyline", "points": [[0, 0], [4, 0], [4, 4], [0, 4]],
         "closed": True, "layer": "TEST"},
        {"kind": "line", "p1": [0, 0], "p2": [1, 1]},
        {"kind": "circle", "center": [5, 5], "radius": 1},
        {"kind": "text", "pos": [2, 2], "text": "A1", "height": 2.5},
    ]})
    check("draw 4 doi tuong", s == 200 and len(b.get("created", [])) == 4, str(b))

    s, b = req("GET", "/areas")
    check("areas sau khi ve: tong tang 16 (HCN 4x4) + pi (tron r=1)",
          abs(b.get("total_area", 0) - (50.0 + 4 * math.pi + 16.0 + math.pi)) < 1e-9,
          str(b))
    check("areas sau khi ve: 4 hang", len(b.get("rows", [])) == 4, str(b))

    s, b = req("POST", "/command", body={"cmd": "ZOOM E"})
    check("command gui di", s == 200 and b.get("sent") is True, str(b))

    s, b = req("GET", "/khong-co")
    check("endpoint la -> 404", s == 404, str(b))

    server.shutdown()
    print("\n%d PASS, %d FAIL" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
