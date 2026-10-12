#!/usr/bin/env python3
"""Estimate product energy from ingredient percentages inferred from the
descending-order ingredient list (GB 7718), then compare against the labeled
energy using the GB 28050 tolerance (measured/estimated <= 120% of label).

Input JSON (stdin or file arg):
{
  "labeled_energy_kj": 1800,
  "ingredients": [
    {"name": "小麦粉", "pct_min": 45, "pct_max": 55, "kj_per_100g": 1500},
    {"name": "植物油", "pct_min": 15, "pct_max": 20, "kj_per_100g": 3700},
    {"name": "白砂糖", "pct_min": 10, "pct_max": 15, "kj_per_100g": 1670},
    {"name": "水",     "pct_min": 5,  "pct_max": 10, "kj_per_100g": 0}
  ]
}

Percentages are agent-estimated from descending order (must satisfy
sum(pct_min) <= 100 <= sum(pct_max)). kj_per_100g values come from
references/ingredient-calories.md.

Output: estimated energy range, overlap analysis with the GB 28050 compliant
band [0, labeled*1.2], and a verdict flag.
"""

import json
import sys

GB_TOLERANCE = 1.20  # measured energy must be <= 120% of labeled value


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    d = json.load(src)
    ings = d.get("ingredients") or []
    labeled = d.get("labeled_energy_kj")

    warnings = []
    if not ings:
        print(json.dumps({"status": "insufficient_data",
                          "detail": "no ingredients provided"}, ensure_ascii=False))
        return

    sum_min = sum(i.get("pct_min", 0) for i in ings)
    sum_max = sum(i.get("pct_max", 0) for i in ings)
    if sum_min > 100.5 or sum_max < 99.5:
        warnings.append(
            f"percentage ranges inconsistent: sum_min={sum_min:.0f}%, sum_max={sum_max:.0f}% "
            f"(need sum_min <= 100 <= sum_max)")

    est_min = sum(i.get("pct_min", 0) * i.get("kj_per_100g", 0) / 100 for i in ings)
    est_max = sum(i.get("pct_max", 0) * i.get("kj_per_100g", 0) / 100 for i in ings)

    result = {
        "status": "ok",
        "estimated_energy_kj": {"min": round(est_min), "max": round(est_max)},
        "labeled_energy_kj": labeled,
        "warnings": warnings,
        "top_contributors": sorted(
            ({"name": i["name"],
              "kj_mid": round((i.get("pct_min", 0) + i.get("pct_max", 0)) / 2
                              * i.get("kj_per_100g", 0) / 100)} for i in ings),
            key=lambda x: -x["kj_mid"])[:3],
    }

    if isinstance(labeled, (int, float)):
        compliant_ceiling = labeled * GB_TOLERANCE
        overlaps = est_min <= compliant_ceiling  # any plausible value within limit
        result["gb28050_check"] = {
            "compliant_ceiling_kj": round(compliant_ceiling),
            "estimate_overlaps_compliant_band": overlaps,
            "verdict": "consistent" if overlaps else "suspect",
            "detail": (f"estimated {round(est_min)}-{round(est_max)} kJ vs "
                       f"labeled {labeled} kJ; GB 28050 allows up to "
                       f"{round(compliant_ceiling)} kJ (120%)"),
        }
    else:
        result["gb28050_check"] = {"verdict": "insufficient_data",
                                   "detail": "labeled energy missing"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
