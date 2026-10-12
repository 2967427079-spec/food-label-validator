#!/usr/bin/env python3
"""L1 deterministic checks for food nutrition labels (GB 28050).

Input: JSON on stdin or as file arg:
{
  "energy_kj": 1800, "protein_g": 8.0, "fat_g": 20.0, "carb_g": 55.0,
  "sodium_mg": 400, "trans_fat_g": 0, "sugar_g": 10.0,
  "fiber_g": null,
  "zero_claims": {"fat": false, "sugar": true, "trans_fat": false},
  "low_confidence_fields": ["sugar_g"]
}
Output: JSON report with checks and l1_passed flag.

Rules:
- Energy conservation: energy ~ protein*17 + fat*37 + carb*17 (+ fiber*8), tolerance +/-20%.
- Macro mass bound: protein + fat + carb <= 100 g (+ small tolerance for rounding).
- Zero-claim thresholds (per 100 g/mL): fat <= 0.5, sugar <= 0.5, trans fat <= 0.3,
  energy <= 17 kJ, sodium <= 5 mg.
Fields listed in low_confidence_fields are excluded from energy math.
"""

import json
import sys

TOLERANCE = 0.20
ZERO_LIMITS = {
    "fat": ("fat_g", 0.5),
    "sugar": ("sugar_g", 0.5),
    "trans_fat": ("trans_fat_g", 0.3),
    "energy": ("energy_kj", 17.0),
    "sodium": ("sodium_mg", 5.0),
}


def num(d, key):
    v = d.get(key)
    return v if isinstance(v, (int, float)) else None


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    d = json.load(src)
    low_conf = set(d.get("low_confidence_fields") or [])
    checks = []

    energy = num(d, "energy_kj")
    prot = num(d, "protein_g")
    fat = num(d, "fat_g")
    carb = num(d, "carb_g")
    fiber = num(d, "fiber_g")

    # Check 1: energy conservation
    if energy is not None and not {"protein_g", "fat_g", "carb_g"} & low_conf \
            and None not in (prot, fat, carb):
        calc = prot * 17 + fat * 37 + carb * 17 + (fiber or 0) * 8
        if calc > 0:
            dev = abs(energy - calc) / calc
            checks.append({
                "id": "L1-energy-balance",
                "passed": dev <= TOLERANCE,
                "detail": f"label={energy} kJ vs calculated={calc:.0f} kJ, deviation={dev:.1%} (tolerance {TOLERANCE:.0%})",
            })
        else:
            checks.append({"id": "L1-energy-balance", "passed": None,
                           "detail": "calculated energy is 0, cannot compare"})
    else:
        checks.append({"id": "L1-energy-balance", "passed": None,
                       "detail": "skipped: missing or low-confidence macro fields"})

    # Check 2: macro mass bound
    if None not in (prot, fat, carb):
        total = prot + fat + carb
        checks.append({
            "id": "L1-mass-bound",
            "passed": total <= 102.0,  # rounding slack
            "detail": f"protein+fat+carb = {total:.1f} g per 100 g",
        })
    else:
        checks.append({"id": "L1-mass-bound", "passed": None,
                       "detail": "skipped: missing macro fields"})

    # Check 3: zero-claim thresholds
    for claim, (field, limit) in ZERO_LIMITS.items():
        if (d.get("zero_claims") or {}).get(claim):
            v = num(d, field)
            if v is None:
                checks.append({"id": f"L1-zero-{claim}", "passed": None,
                               "detail": f"'{claim}' claimed as 0 but value missing"})
            else:
                checks.append({
                    "id": f"L1-zero-{claim}",
                    "passed": v <= limit,
                    "detail": f"'{claim}' claimed as 0, actual {v} (limit {limit})",
                })

    failed = [c for c in checks if c["passed"] is False]
    print(json.dumps({
        "l1_passed": not failed,
        "checks": checks,
        "failed_ids": [c["id"] for c in failed],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
