# -*- coding: utf-8 -*-
"""bridge.py — may chu HTTP nho noi Muse voi AutoCAD dang chay tren may nay.

Chay tren Windows:  py bridge.py   (hoac chay run.bat)
  - Lang nghe 0.0.0.0:8765 (can de Tailscale goi toi duoc)
  - Moi yeu cau (tru /ping) can header:  X-Bridge-Token: <token trong token.txt>
  - Token sinh ngau nhien lan dau chay, luu vao token.txt cung thu muc.
  - Bien moi truong CAD_BRIDGE_FAKE=1: dung FakeCAD thay cho AutoCAD that
    (chi de kiem thu tren may khong co AutoCAD).

Endpoints (JSON):
  GET  /ping                          -> {"ok": true, "service": "cad-bridge"}
  GET  /status                        -> version AutoCAD, ten ban ve dang mo
  GET  /layers                        -> danh sach layer
  GET  /entities?type=line&limit=200  -> doi tuong trong ModelSpace
  GET  /areas                         -> duong bao kin: dien tich + chu vi + tong
  POST /lisp    {"expr": "(+ 1 2)"}   -> ket qua LISP
  POST /draw    {"items": [{kind, ...}]} -> ve line/polyline/circle/text
  POST /command {"cmd": "ZOOM E"}     -> gui lenh cho AutoCAD
"""
import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = int(os.environ.get("CAD_BRIDGE_PORT", "8765"))
if getattr(sys, "frozen", False):
    # Chay dang file .exe (PyInstaller onefile): token.txt dat canh file .exe,
    # khong phai trong thu muc tam giai nen cua PyInstaller.
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            t = f.read().strip()
            if t:
                return t
    t = secrets.token_urlsafe(24)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(t)
    return t


TOKEN = load_token()
_CAD = None


def get_cad():
    global _CAD
    if _CAD is not None:
        return _CAD
    from cadapi import RealCAD, FakeCAD
    if os.environ.get("CAD_BRIDGE_FAKE") == "1":
        _CAD = FakeCAD()
    else:
        _CAD = RealCAD()  # gay CadError neu AutoCAD chua mo
    return _CAD


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[bridge] %s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        return self.headers.get("X-Bridge-Token") == TOKEN

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def _q(self, name, default=None):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        vals = qs.get(name)
        return vals[0] if vals else default

    def do_GET(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        if path == "/ping":
            return self._send(200, {"ok": True, "service": "cad-bridge", "version": "1.0"})
        if not self._auth():
            return self._send(401, {"ok": False, "error": "Sai hoac thieu X-Bridge-Token"})
        try:
            cad = get_cad()
            if path == "/status":
                self._send(200, {"ok": True, **cad.status()})
            elif path == "/layers":
                self._send(200, {"ok": True, "layers": cad.layers()})
            elif path == "/entities":
                typ = self._q("type")
                try:
                    limit = int(self._q("limit") or 200)
                except ValueError:
                    limit = 200
                self._send(200, {"ok": True, "entities": cad.list_entities(typ, limit)})
            elif path == "/areas":
                self._send(200, {"ok": True, **cad.areas()})
            else:
                self._send(404, {"ok": False, "error": "Khong co endpoint: %s" % path})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})

    def do_POST(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        if not self._auth():
            return self._send(401, {"ok": False, "error": "Sai hoac thieu X-Bridge-Token"})
        try:
            cad = get_cad()
            data = self._body()
            if path == "/lisp":
                self._send(200, {"ok": True, **cad.eval_lisp(str(data.get("expr", "")))})
            elif path == "/draw":
                items = data.get("items", [])
                if not isinstance(items, list):
                    raise ValueError("items phai la list")
                self._send(200, {"ok": True, "created": cad.draw(items)})
            elif path == "/command":
                self._send(200, {"ok": True, **cad.send_command(str(data.get("cmd", "")))})
            else:
                self._send(404, {"ok": False, "error": "Khong co endpoint: %s" % path})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})


def main():
    print("=" * 60)
    print("CAD Bridge v1.0 — noi Muse voi AutoCAD tren may nay")
    print("Cong: %d  (goi: http://<ten-may-tailscale>:%d/ping)" % (PORT, PORT))
    print("Token (giu kin, chi gui cho Muse): %s" % TOKEN)
    print("Token cung luu trong file token.txt cung thu muc.")
    print("Mo AutoCAD truoc, roi mo ban ve — cau noi se tu noi vao.")
    print("Dong cua so nay de dung cau noi.")
    print("=" * 60, flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDa dung cau noi.")


if __name__ == "__main__":
    main()
