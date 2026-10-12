#!/usr/bin/env python3
"""Normalize OCR'd nutrition-table rows into structured JSON.

Takes raw text lines (stdin or file) from an OCR read of a nutrition facts table
and realigns them into the canonical pattern: nutrient | value | unit | NRV%.
Handles common OCR issues: split columns, missing NRV, mg/g confusion flags.

Usage: python extract_tables.py raw_ocr.txt  > structured.json
"""

import json
import re
import sys

NUTRIENTS = {
    "能量": "energy_kj", "蛋白质": "protein_g", "脂肪": "fat_g",
    "反式脂肪酸": "trans_fat_g", "碳水化合物": "carb_g", "糖": "sugar_g",
    "膳食纤维": "fiber_g", "钠": "sodium_mg", "钙": "calcium_mg",
}

VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kJ|kj|千焦|kcal|g|mg|微克|μg)?")
NRV_RE = re.compile(r"(\d{1,3})\s*%")


def parse_line(line):
    for zh, key in NUTRIENTS.items():
        if zh in line:
            val = VALUE_RE.search(line)
            nrv = NRV_RE.search(line)
            entry = {"nutrient": zh, "field": key,
                     "value": float(val.group(1)) if val else None,
                     "unit_raw": val.group(2) if val else None,
                     "nrv_percent": int(nrv.group(1)) if nrv else None,
                     "raw": line.strip()}
            # unit sanity flags (never rewrite values)
            flags = []
            if key == "energy_kj" and entry["value"] is not None:
                if entry["unit_raw"] in ("kcal",):
                    flags.append("energy in kcal, convert to kJ (x4.184)")
                elif entry["value"] > 4000:
                    flags.append("suspicious magnitude for energy per 100 g")
            if key == "sodium_mg" and entry["unit_raw"] == "g":
                flags.append("sodium unit read as g, likely mg - verify")
            if key != "sodium_mg" and entry["unit_raw"] == "mg" and \
               key in ("protein_g", "fat_g", "carb_g"):
                flags.append("macro nutrient in mg, likely g - verify")
            entry["flags"] = flags
            return entry
    return None


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    lines = src.read().splitlines()
    entries, unmatched = [], []
    for line in lines:
        if not line.strip():
            continue
        e = parse_line(line)
        (entries if e else unmatched).append(e or line.strip())
    print(json.dumps({
        "status": "ok" if entries else "unrecognized",
        "nutrition": entries,
        "unmatched_lines": unmatched,
        "needs_manual_review": [e["field"] for e in entries
                                if e["value"] is None or e["flags"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
