#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从《副本工序流转卡》工作簿提取 77 张流程卡数据到 data/parts.json"""
import json
import os
import sys
import datetime

import openpyxl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_XLSX = "/workspace/.uploads/051d57e9-ff79-4e53-98a9-d9f9ab508719_副本工序流转卡(1).xlsx"
OUT = os.path.join(BASE, "data", "parts.json")
MASTER_SHEETS = 15  # 前 15 个为汇总/订单/问题表，之后为各零件流程卡


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
    wb = openpyxl.load_workbook(path, data_only=True)
    parts = {}
    meta = None
    for s in wb.sheetnames[MASTER_SHEETS:]:
        ws = wb[s]
        pn = str(ws["C4"].value or s).strip()
        due = ws["N4"].value
        due = due.strftime("%Y-%m-%d") if hasattr(due, "strftime") else (str(due)[:10] if due else "")
        procs = []
        for i in range(8, 17):
            name = ws.cell(i, 1).value
            if not name:
                continue
            procs.append({
                "seq": len(procs) + 1,
                "name": str(name).strip(),
                "content": str(ws.cell(i, 3).value or "").strip(),
                "machine": str(ws.cell(i, 12).value or "").strip(),
            })
        part = {
            "pn": pn,
            "project": str(ws["A5"].value or "").strip(),
            "order": str(ws["J4"].value or "").strip(),
            "due": due,
            "version": str(ws["H4"].value or "").strip(),
            "perSet": num(ws["N5"].value),
            "orderQty": num(ws["H5"].value),
            "semiQty": num(ws["J5"].value),
            "nestQty": num(ws["L5"].value),
            "material": str(ws["C19"].value or "").strip(),
            "spec": str(ws["G19"].value or "").strip(),
            "processes": procs,
        }
        parts[pn] = part
        if meta is None:
            meta = {"order": part["order"], "project": part["project"], "due": part["due"]}

    data = {
        "meta": meta,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "parts": parts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("已生成 %s，共 %d 个零件" % (OUT, len(parts)))


if __name__ == "__main__":
    main()
