# -*- coding: utf-8 -*-
"""cadapi.py — lop ket noi AutoCAD dang chay tren may nay (Windows).

RealCAD: noi qua COM bang pyautocad (da kiem chung tu source pyautocad 0.2.0):
  - Autocad(create_if_not_exists=False).app = GetActiveObject('AutoCAD.Application')
  - .doc = ActiveDocument, .model = ModelSpace
  - iter_objects(name, limit) duyet doc.ActiveLayout.Block, loc theo chuoi con
    cua ObjectName (vd 'AcDbLine', 'AcDbPolyline', 'AcDbCircle')
  - model.AddLine(APoint, APoint) / AddCircle(APoint, r) / AddText(str, APoint, h)
  - model.AddPolyline(aDouble(x1,y1,z1, x2,y2,z2, ...)) — aDouble nhan doi so
    phang hoac 1 list; Polyline.Closed = True de dong kin
  - doc.SendCommand("... ") gui lenh (khong dong bo)
  - Danh gia LISP: COM chuan KHONG co Application.EvalLisp. Dung VisualLISP
    ActiveX: app.GetInterfaceObject("VL.Application") -> ActiveDocument.Functions,
    .Item("read").funcall(expr) roi .Item("eval").funcall(sym). Neu khong co,
    du phong bang SendCommand + file tam.

FakeCAD: ban gia lap trong bo nho, dung de kiem thu may chu HTTP tren may
khong co AutoCAD (Linux). Cung giao dien nhu RealCAD.
"""
import math
import os
import time


class CadError(Exception):
    pass


def _pts2d(points):
    out = []
    for p in points:
        out.extend((float(p[0]), float(p[1]), 0.0))
    return out


def _com_to_py(v):
    if isinstance(v, (list, tuple)):
        return [_com_to_py(x) for x in v]
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    try:
        return float(v)
    except Exception:
        pass
    try:
        return str(v)
    except Exception:
        return repr(v)


# ---------------------------------------------------------------- RealCAD
class RealCAD(object):
    def __init__(self):
        try:
            from pyautocad import Autocad, APoint, aDouble
        except Exception as e:
            raise CadError("Khong nap duoc pyautocad: %s (chay: pip install pyautocad)" % e)
        self._APoint = APoint
        self._aDouble = aDouble
        try:
            self.acad = Autocad(create_if_not_exists=False)
            self._doc = self.acad.doc  # gay loi neu AutoCAD chua mo
        except Exception as e:
            raise CadError("Khong ket noi duoc AutoCAD dang chay: %s" % e)
        self._vl_funcs = None
        self._vl_tried = False

    # -- thong tin chung -------------------------------------------------
    def status(self):
        try:
            ver = str(self.acad.app.Version)
        except Exception:
            ver = ""
        try:
            name = str(self._doc.Name)
        except Exception:
            name = ""
        try:
            path = str(self._doc.FullName)
        except Exception:
            path = ""
        return {"connected": True, "version": ver, "doc_name": name, "doc_path": path}

    def layers(self):
        try:
            return [str(layer.Name) for layer in self._doc.Layers]
        except Exception as e:
            raise CadError("Khong doc duoc layers: %s" % e)

    # -- doc doi tuong ---------------------------------------------------
    def _summary(self, ent):
        d = {"handle": str(getattr(ent, "Handle", "")),
             "type": str(getattr(ent, "ObjectName", "")),
             "layer": str(getattr(ent, "Layer", ""))}
        return d

    def list_entities(self, type_filter=None, limit=200):
        out = []
        try:
            it = self.acad.iter_objects(type_filter, limit=limit)
        except Exception as e:
            raise CadError("Khong liet ke duoc doi tuong: %s" % e)
        for ent in it:
            d = self._summary(ent)
            name = d["type"].lower()
            try:
                if "polyline" in name:
                    d["closed"] = bool(ent.Closed)
                    try:
                        d["area"] = float(ent.Area)
                    except Exception:
                        d["area"] = None
                    try:
                        d["length"] = float(ent.Length)
                    except Exception:
                        d["length"] = None
                elif "line" in name:
                    d["start"] = [float(v) for v in ent.StartPoint][:2]
                    d["end"] = [float(v) for v in ent.EndPoint][:2]
                    d["length"] = float(ent.Length)
                elif "circle" in name:
                    d["center"] = [float(v) for v in ent.Center][:2]
                    d["radius"] = float(ent.Radius)
                    d["area"] = float(ent.Area)
                    d["circumference"] = float(ent.Circumference)
                elif "ellipse" in name:
                    d["center"] = [float(v) for v in ent.Center][:2]
                    d["area"] = float(ent.Area)
                elif "text" in name:
                    d["text"] = str(ent.TextString)
                    d["insertion"] = [float(v) for v in ent.InsertionPoint][:2]
            except Exception:
                pass
            out.append(d)
        return out

    def areas(self):
        """Duong bao kin (nhu lenh DIENTICH): polyline kin, circle, ellipse, region."""
        rows = []
        total_area = 0.0
        total_perim = 0.0
        for ent in self.acad.iter_objects(limit=10000):
            name = str(getattr(ent, "ObjectName", "")).lower()
            try:
                if "polyline" in name:
                    if not bool(ent.Closed):
                        continue
                    area = float(ent.Area)
                    perim = float(ent.Length)
                    typ = "Polyline"
                elif "circle" in name:
                    area = float(ent.Area)
                    perim = float(ent.Circumference)
                    typ = "Circle"
                elif "ellipse" in name:
                    area = float(ent.Area)
                    perim = None  # ActiveX khong co chu vi ellipse truc tiep
                    typ = "Ellipse"
                elif "region" in name:
                    area = float(ent.Area)
                    perim = float(ent.Perimeter)
                    typ = "Region"
                else:
                    continue
            except Exception:
                continue
            rows.append({"layer": str(getattr(ent, "Layer", "")),
                         "type": typ, "area": area, "perimeter": perim})
            total_area += area
            if perim:
                total_perim += perim
        return {"rows": rows, "total_area": total_area, "total_perimeter": total_perim}

    # -- ve ----------------------------------------------------------------
    def _ensure_layer(self, name):
        if not name:
            return
        try:
            self._doc.Layers.Add(name)
        except Exception:
            pass  # layer da co

    def draw(self, items):
        model = self.acad.model
        APoint = self._APoint
        aDouble = self._aDouble
        made = []
        for it in items:
            kind = str(it.get("kind", "")).lower()
            layer = it.get("layer") or None
            self._ensure_layer(layer)
            if kind == "line":
                ent = model.AddLine(APoint(*it["p1"]), APoint(*it["p2"]))
            elif kind == "polyline":
                ent = model.AddPolyline(aDouble(*_pts2d(it["points"])))
                if it.get("closed"):
                    ent.Closed = True
            elif kind == "circle":
                ent = model.AddCircle(APoint(*it["center"]), float(it["radius"]))
            elif kind == "text":
                ent = model.AddText(str(it["text"]), APoint(*it["pos"]),
                                    float(it.get("height", 2.5)))
            else:
                raise CadError("kind khong ho tro: %s" % kind)
            if layer:
                try:
                    ent.Layer = layer
                except Exception:
                    pass
            made.append({"handle": str(ent.Handle), "type": str(ent.ObjectName)})
        return made

    # -- lenh / LISP -------------------------------------------------------
    def send_command(self, cmd):
        try:
            self._doc.SendCommand(str(cmd) + " ")
            return {"sent": True}
        except Exception as e:
            raise CadError("SendCommand loi: %s" % e)

    def _get_vl_funcs(self):
        if self._vl_tried:
            return self._vl_funcs
        self._vl_tried = True
        app = self.acad.app
        for prog in ("VL.Application", "VL.Application.24", "VL.Application.23",
                     "VL.Application.22", "VL.Application.21", "VL.Application.20"):
            try:
                vl = app.GetInterfaceObject(prog)
                self._vl_funcs = vl.ActiveDocument.Functions
                return self._vl_funcs
            except Exception:
                continue
        return None

    def eval_lisp(self, expr):
        funcs = self._get_vl_funcs()
        if funcs is not None:
            try:
                sym = funcs.Item("read").funcall(expr)
                ret = funcs.Item("eval").funcall(sym)
                return {"result": _com_to_py(ret), "via": "VL.Application"}
            except Exception as e:
                raise CadError("Eval LISP loi: %s" % e)
        # Du phong: ghi bieu thuc ra file .lsp, (load ...) qua SendCommand,
        # LISP tu ghi ket qua ra file tam, Python doc lai (cho toi da 5 giay).
        tmpdir = os.environ.get("TEMP", r"C:\Temp")
        lsp_path = os.path.join(tmpdir, "cad_bridge_expr.lsp")
        out_path = os.path.join(tmpdir, "cad_bridge_lisp.txt")
        esc_out = out_path.replace("\\", "\\\\")
        esc_lsp = lsp_path.replace("\\", "\\\\")
        with open(lsp_path, "w", encoding="utf-8") as f:
            f.write('(progn (setq _brf (open "%s" "w")) '
                    '(write-line (vl-princ-to-string (progn %s)) _brf) '
                    '(close _brf) (setq _brf nil))\n' % (esc_out, expr))
        try:
            os.remove(out_path)
        except OSError:
            pass
        self.send_command('(load "%s")' % esc_lsp)
        for _ in range(25):
            time.sleep(0.2)
            if os.path.exists(out_path):
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        return {"result": f.read().strip(), "via": "SendCommand+file"}
                except OSError:
                    pass
        raise CadError("Het thoi gian cho ket qua LISP (5 giay) — kiem tra AutoCAD co dang mo hop thoai nao khong")


# ---------------------------------------------------------------- FakeCAD
def _shoelace(points):
    s = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _poly_length(points, closed):
    pts = list(points) + ([points[0]] if closed else [])
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


class FakeCAD(object):
    """Ban gia lap trong bo nho — dung de kiem thu may chu HTTP."""

    def __init__(self):
        self.version = "FakeCAD 1.0 (kiem thu)"
        self.doc_name = "TEST.dwg"
        self.doc_path = r"C:\Test\TEST.dwg"
        self.entities = [
            {"kind": "polyline", "layer": "0", "points": [[0, 0], [10, 0], [10, 5], [0, 5]],
             "closed": True},
            {"kind": "circle", "layer": "0", "center": [20, 20], "radius": 2.0},
            {"kind": "polyline", "layer": "0", "points": [[0, 0], [3, 4]], "closed": False},
            {"kind": "line", "layer": "S1", "p1": [0, 0], "p2": [3, 4]},
            {"kind": "text", "layer": "0", "pos": [1, 1], "text": "HELLO", "height": 2.5},
        ]
        self._next_handle = 100

    def status(self):
        return {"connected": True, "version": self.version,
                "doc_name": self.doc_name, "doc_path": self.doc_path}

    def layers(self):
        return sorted({e.get("layer", "0") for e in self.entities})

    def _summary(self, e):
        type_map = {"polyline": "AcDbPolyline", "circle": "AcDbCircle",
                    "line": "AcDbLine", "text": "AcDbText"}
        d = {"handle": str(e.get("handle", "")),
             "type": type_map.get(e["kind"], e["kind"]),
             "layer": e.get("layer", "0")}
        if e["kind"] == "polyline":
            d["closed"] = bool(e.get("closed"))
            if d["closed"]:
                d["area"] = _shoelace(e["points"])
                d["length"] = _poly_length(e["points"], True)
        elif e["kind"] == "circle":
            d["center"] = e["center"]
            d["radius"] = e["radius"]
            d["area"] = math.pi * e["radius"] ** 2
            d["circumference"] = 2 * math.pi * e["radius"]
        elif e["kind"] == "line":
            d["start"] = e["p1"]
            d["end"] = e["p2"]
            d["length"] = math.hypot(e["p2"][0] - e["p1"][0], e["p2"][1] - e["p1"][1])
        elif e["kind"] == "text":
            d["text"] = e["text"]
            d["insertion"] = e["pos"]
        return d

    def list_entities(self, type_filter=None, limit=200):
        out = []
        for e in self.entities:
            s = self._summary(e)
            if type_filter and type_filter.lower() not in s["type"].lower():
                continue
            out.append(s)
            if len(out) >= limit:
                break
        return out

    def areas(self):
        rows = []
        total_area = 0.0
        total_perim = 0.0
        for e in self.entities:
            if e["kind"] == "polyline" and e.get("closed"):
                area = _shoelace(e["points"])
                perim = _poly_length(e["points"], True)
                typ = "Polyline"
            elif e["kind"] == "circle":
                area = math.pi * e["radius"] ** 2
                perim = 2 * math.pi * e["radius"]
                typ = "Circle"
            else:
                continue
            rows.append({"layer": e.get("layer", "0"), "type": typ,
                         "area": area, "perimeter": perim})
            total_area += area
            total_perim += perim
        return {"rows": rows, "total_area": total_area, "total_perimeter": total_perim}

    def draw(self, items):
        made = []
        for it in items:
            kind = str(it.get("kind", "")).lower()
            if kind not in ("line", "polyline", "circle", "text"):
                raise CadError("kind khong ho tro: %s" % kind)
            e = dict(it)
            e["kind"] = kind
            e["layer"] = it.get("layer") or "0"
            self._next_handle += 1
            e["handle"] = "FAKE%d" % self._next_handle
            self.entities.append(e)
            made.append({"handle": e["handle"],
                         "type": self._summary(e)["type"]})
        return made

    def send_command(self, cmd):
        return {"sent": True}

    def eval_lisp(self, expr):
        expr = expr.strip()
        if expr == '(getvar "ACADVER")':
            return {"result": "24.0", "via": "FakeCAD"}
        return {"result": "FAKE:" + expr, "via": "FakeCAD"}
