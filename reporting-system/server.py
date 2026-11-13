#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钣金工序流转卡 - 扫码报工服务
仅使用 Python 标准库，无需安装依赖。

启动:
    python3 server.py [port]
默认端口 8010，监听 0.0.0.0，手机与电脑需在同一局域网。
"""
import csv
import io
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(DATA_DIR, "reports.db")
PARTS_PATH = os.path.join(DATA_DIR, "parts.json")

TZ = timezone(timedelta(hours=8))
MAX_BODY = 64 * 1024


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def load_parts():
    with open(PARTS_PATH, encoding="utf-8") as f:
        return json.load(f)


PARTS_DB = load_parts()
PARTS = PARTS_DB["parts"]


def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wo TEXT NOT NULL,
                pn TEXT NOT NULL,
                process TEXT NOT NULL,
                qty_ok REAL NOT NULL DEFAULT 0,
                qty_ng REAL NOT NULL DEFAULT 0,
                worker TEXT NOT NULL,
                machine TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_pn ON reports(wo, pn)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_time ON reports(created_at)")


def part_summary(wo, pn):
    part = PARTS.get(pn)
    if not part:
        return None
    rows = {}
    with db() as conn:
        cur = conn.execute(
            """SELECT process, SUM(qty_ok) ok, SUM(qty_ng) ng, COUNT(*) cnt, MAX(created_at) last
               FROM reports WHERE wo=? AND pn=? GROUP BY process""",
            (wo, pn),
        )
        for r in cur:
            rows[r["process"]] = dict(ok=r["ok"] or 0, ng=r["ng"] or 0, cnt=r["cnt"], last=r["last"])
    for p in part["processes"]:
        s = rows.get(p["name"], dict(ok=0, ng=0, cnt=0, last=None))
        p["reportedOk"] = s["ok"]
        p["reportedNg"] = s["ng"]
        p["reportedCnt"] = s["cnt"]
        p["reportedLast"] = s["last"]
    part["planQty"] = part.get("orderQty") or part.get("semiQty") or 0
    return part


def recent_reports(wo, pn, limit=20):
    sql = "SELECT * FROM reports"
    args = []
    where = []
    if wo:
        where.append("wo=?")
        args.append(wo)
    if pn:
        where.append("pn=?")
        args.append(pn)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


class Handler(SimpleHTTPRequestHandler):
    server_version = "JRReport/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---------- helpers ----------
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/r", "/index.html"):
            return self.send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        if path in ("/admin", "/admin.html"):
            return self.send_file(os.path.join(STATIC_DIR, "admin.html"), "text/html; charset=utf-8")
        if path == "/static/app.css":
            return self.send_file(os.path.join(STATIC_DIR, "app.css"), "text/css; charset=utf-8")
        if path == "/static/app.js":
            return self.send_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")
        if path == "/static/admin.js":
            return self.send_file(os.path.join(STATIC_DIR, "admin.js"), "application/javascript; charset=utf-8")
        if path == "/api/meta":
            return self.send_json({"meta": PARTS_DB.get("meta"), "count": len(PARTS)})
        if path == "/api/parts":
            items = sorted(
                (
                    {
                        "pn": p["pn"],
                        "project": p.get("project", ""),
                        "orderQty": p.get("orderQty"),
                        "perSet": p.get("perSet"),
                        "processCount": len(p["processes"]),
                    }
                    for p in PARTS.values()
                ),
                key=lambda x: x["pn"],
            )
            return self.send_json({"items": items})
        if path == "/api/processes":
            names = set()
            for p in PARTS.values():
                for proc in p["processes"]:
                    names.add(proc["name"])
            return self.send_json({"items": sorted(names)})
        if path == "/api/part":
            wo = (qs.get("wo") or [""])[0]
            pn = (qs.get("pn") or [""])[0]
            part = part_summary(wo, pn)
            if not part:
                return self.send_json({"error": "零件不存在"}, 404)
            return self.send_json({"part": part, "reports": recent_reports(wo, pn, 10)})
        if path == "/api/reports":
            wo = (qs.get("wo") or [""])[0]
            pn = (qs.get("pn") or [""])[0]
            try:
                limit = min(int((qs.get("limit") or ["200"])[0]), 1000)
            except ValueError:
                limit = 200
            return self.send_json({"items": recent_reports(wo, pn, limit)})
        if path == "/api/summary":
            with db() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) cnt, COALESCE(SUM(qty_ok),0) ok, COALESCE(SUM(qty_ng),0) ng, COUNT(DISTINCT pn) parts FROM reports"
                ).fetchone()
                by_proc = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT process, SUM(qty_ok) ok, SUM(qty_ng) ng, COUNT(*) cnt FROM reports GROUP BY process ORDER BY ok DESC"
                    )
                ]
            return self.send_json({"total": dict(row), "byProcess": by_proc, "serverTime": now_str()})
        if path == "/api/export.csv":
            return self.export_csv()
        if path == "/healthz":
            return self.send_json({"ok": True, "time": now_str(), "parts": len(PARTS)})
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/reports":
            return self.send_json({"error": "接口不存在"}, 404)
        data = self.read_json()
        if not isinstance(data, dict):
            return self.send_json({"error": "请求格式错误"}, 400)

        wo = str(data.get("wo") or "").strip()
        pn = str(data.get("pn") or "").strip()
        process = str(data.get("process") or "").strip()
        worker = str(data.get("worker") or "").strip()
        machine = str(data.get("machine") or "").strip()[:60]
        note = str(data.get("note") or "").strip()[:200]
        try:
            qty_ok = float(data.get("qty_ok") or 0)
            qty_ng = float(data.get("qty_ng") or 0)
        except (TypeError, ValueError):
            return self.send_json({"error": "数量必须是数字"}, 400)

        part = PARTS.get(pn)
        if not part:
            return self.send_json({"error": "零件号不存在"}, 404)
        if process not in [p["name"] for p in part["processes"]]:
            return self.send_json({"error": "工序不在该流程卡内"}, 400)
        if not wo:
            return self.send_json({"error": "缺少工单号"}, 400)
        if not worker:
            return self.send_json({"error": "请填写报工人"}, 400)
        if qty_ok < 0 or qty_ng < 0 or qty_ok + qty_ng <= 0:
            return self.send_json({"error": "报工数量必须大于 0"}, 400)
        if qty_ok > 100000 or qty_ng > 100000:
            return self.send_json({"error": "数量超出合理范围"}, 400)

        with db() as conn:
            dup = conn.execute(
                """SELECT id FROM reports WHERE wo=? AND pn=? AND process=? AND worker=?
                   AND qty_ok=? AND qty_ng=? AND created_at > ?""",
                (wo, pn, process, worker, qty_ok, qty_ng,
                 (datetime.now(TZ) - timedelta(seconds=8)).strftime("%Y-%m-%d %H:%M:%S")),
            ).fetchone()
            if dup:
                return self.send_json({"error": "8 秒内重复提交，请勿重复扫码"}, 409)
            cur = conn.execute(
                """INSERT INTO reports(wo,pn,process,qty_ok,qty_ng,worker,machine,note,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (wo, pn, process, qty_ok, qty_ng, worker, machine, note, now_str()),
            )
            rid = cur.lastrowid

        part = part_summary(wo, pn)
        proc = next(p for p in part["processes"] if p["name"] == process)
        return self.send_json({
            "ok": True,
            "id": rid,
            "planQty": part["planQty"],
            "process": proc,
            "reports": recent_reports(wo, pn, 10),
        })

    def export_csv(self):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["记录ID", "工单号", "物料号", "工序", "合格数", "不良数", "报工人", "设备", "备注", "报工时间"])
        with db() as conn:
            for r in conn.execute("SELECT * FROM reports ORDER BY id"):
                writer.writerow([r["id"], r["wo"], r["pn"], r["process"], r["qty_ok"], r["qty_ng"],
                                 r["worker"], r["machine"], r["note"], r["created_at"]])
        body = ("\ufeff" + buf.getvalue()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="baogong-reports.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    init_db()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"报工服务已启动: http://0.0.0.0:{port}")
    print(f"报工页示例: http://127.0.0.1:{port}/r?wo={quote(PARTS_DB['meta']['order'])}&pn={quote(next(iter(PARTS)))}")
    print(f"管理页: http://127.0.0.1:{port}/admin")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
