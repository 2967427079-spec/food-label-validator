---
name: food-label-validator
description: Cross-validate food label credibility by checking the ingredients list against the nutrition facts table. This skill should be used when a user uploads photos of a food ingredient list (配料表) and/or nutrition facts table (营养成分表) and asks to verify, check, or validate whether the label is trustworthy, consistent, or compliant (e.g. "验证这个食品标签", "配料表和营养表对得上吗", "这个无糖宣称可信吗"). Based on China GB 7718 and GB 28050 standards.
agent_created: true
---

# Food Label Validator

Cross-validate a prepackaged food's ingredient list against its nutrition facts to assess label credibility, per China GB 7718 (labeling) and GB 28050 (nutrition labeling).

## Workflow

1. **Ingest images.** Accept photos of the ingredient list and/or nutrition facts table. Read text and tables directly from the images with vision capability. Optionally accept text supplements: product name, net weight, claims (e.g. "无糖", "高蛋白").
2. **Structure the data.** Normalize the nutrition table with `scripts/extract_tables.py`, which realigns misread rows/columns into the pattern `nutrient | value | unit | NRV%`. If it fails, keep raw rows and mark them for manual review.
3. **Run deterministic checks (L1).** Execute `scripts/cross_validate.py` on the structured nutrition JSON. It computes energy balance, mass bounds, and zero-claim thresholds. These are math-based and must NOT be done mentally. Then run `scripts/food_energy_check.py`: it infers each ingredient's percentage from the descending-order list (rank-decay weights normalized to 100%), accumulates each ingredient's energy contribution using `references/ingredient-calories.md`, and compares the estimated total against the labeled energy under the GB 28050 tolerance (estimated ≤ labeled × 120%).
4. **Run semantic checks (L2–L4).** Apply the rules in the references files:
   - `references/gb28050-rules.md` — nutrient thresholds, NRV, claim conditions, energy conversion factors (L1/L4).
   - `references/gb7718-rules.md` — descending-order ingredient rule and labeling requirements (L2 foundation).
   - `references/conflict-patterns.md` — known ingredient↔nutrition conflict patterns (L2/L3).
5. **Synthesize verdict.** Compose the final credibility report per the Verdict rules below.

## Check levels

- **L1 Hard constraints (deterministic, script-computed):** energy conservation, macro mass ≤ 100 g/100 g, zero-claim threshold violations. Any L1 failure → verdict `inconsistent`. The ingredient-derived energy estimate (`food_energy_check.py`) is a bottom-up cross-check of the same labeled energy: because percentages are inferred from order (not measured), treat its `fail` as strong evidence → verdict `suspect`; escalate to `inconsistent` only when the deviation is extreme (>100%) or corroborated by an L1 energy-balance failure.
- **L2 Ingredient–nutrition consistency (semantic):** descending-order rule vs macro profile; hydrogenated oils vs trans-fat labeling; sweetener position vs sugar claims. Conflict → `suspect` or `inconsistent`.
- **L3 Plausibility heuristics:** sodium vs salt/soy-sauce ingredients; category-typical nutrient ranges. Hit → warning only.
- **L4 Claim compliance:** "high protein" ≥ 12 g/100 g (solid), "low fat" ≤ 3 g/100 g, etc. (GB 28050 Appendix C).

## Verdict synthesis

- Any L1 failure → `inconsistent` (不一致)
- L2 conflict, no L1 failure → `suspect` (存疑); severe L2 conflict (e.g. first ingredient is oil but fat ≈ 0) → `inconsistent`
- Only L3/L4 hits → `pass_with_warnings` (通过，有提示)
- All pass → `pass` (通过)
- Missing one table → state "单源验证，证据有限" and only run applicable checks

## Failure and missing-data handling

Never invent values. Prefer `insufficient_data` over guessing.

- Low-confidence field → mark `confidence: low`, exclude from L1 math, add to manual-review list.
- Only one table available → single-source mode, note limited evidence.
- Table misalignment → `extract_tables.py` realigns; on failure keep raw rows + prompt.
- Unit anomalies (mg misread as g, etc.) → run order-of-magnitude sanity check, flag suspected unit error, do NOT rewrite the original value.
- Unrecognizable image → return `status: unrecognized` with retake guidance (lighting, angle, flatness).

## Output

Produce both:

1. **Structured JSON**: `{ingredients, nutrition_facts, checks[], verdict, confidence, missing_fields}`
2. **Markdown report**: each check with ✅/⚠️/❌, reasoning, and the rule cited; plus a manual-review field list when confidence is low.
