#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为每张流程卡生成报工二维码 PNG。

用法:
    python3 tools/generate_qr.py http://192.168.1.20:8010
不传参数时自动使用本机局域网 IP + 8010 端口。
生成的二维码指向 <base>/r?wo=<工单号>&pn=<物料号>。
"""
import csv
import json
import os
import socket
import sys
from urllib.parse import quote

import qrcode
from qrcode.constants import ERROR_CORRECT_H

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QR_DIR = os.path.join(BASE, "qr")
PARTS_JSON = os.path.join(BASE, "data", "parts.json")


def lan_ip():
    """探测本机局域网 IP，让手机扫码后能访问报工页。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://%s:8010" % lan_ip()).rstrip("/")
    with open(PARTS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(QR_DIR, exist_ok=True)

    manifest = []
    for pn, part in sorted(data["parts"].items()):
        wo = part.get("order") or (data.get("meta") or {}).get("order", "")
        url = "%s/r?wo=%s&pn=%s" % (base, quote(wo), quote(pn))
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        out = os.path.join(QR_DIR, pn + ".png")
        img.save(out, dpi=(300, 300))
        manifest.append({"pn": pn, "url": url, "file": "qr/" + pn + ".png"})
        print("  " + pn + " -> " + url)

    with open(os.path.join(QR_DIR, "manifest.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["pn", "url", "file"])
        w.writeheader()
        w.writerows(manifest)
    print("\n共生成 %d 张二维码，目录: %s" % (len(manifest), QR_DIR))


if __name__ == "__main__":
    main()
