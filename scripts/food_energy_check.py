#!/usr/bin/env python3
"""食品热量核验程序 (food energy verification)

逻辑:
1. 配料百分比推测: 按 GB 7718 降序规则，用排名衰减权重推测各配料百分比，
   归一化使总和 = 100%。支持手动传入百分比覆盖推测值。
2. 热量累加: 每种配料的推测含量 x 单位热量 (kJ/100g, 内置密度表可匹配中文名)，
   逐项累加得到估算总热量。
3. 合规判断: 与营养成分表标示热量对比，依据 GB 28050 能量允许误差
   (实测/估算值 <= 标示值 x 120%) 判定是否合格。

输入 JSON (stdin 或文件参数):
{
  "labeled_energy_kj": 1800,               // 营养成分表标示能量, 可选
  "decay": 0.8,                            // 排名衰减系数, 可选 (0.7-0.85 合理)
  "ingredients": [
    {"name": "小麦粉"},                     // 仅需名称, 按降序排列
    {"name": "植物油", "pct": 18},          // 可选手动百分比覆盖
    {"name": "白砂糖", "kj_per_100g": 1670} // 可选手动热量密度覆盖
  ]
}

输出: JSON 报告 (每项配料推测百分比/热量贡献/估算总热量/偏差/结论/计算过程)。
"""

import json
import sys

# 内置配料热量密度表 (kJ/100g), 源自 references/ingredient-calories.md
INGREDIENT_KJ_DB = [
    (["起酥油", "人造奶油", "黄油", "植物油", "棕榈油", "食用油脂", "可可脂"], 3700),
    (["果葡糖浆", "麦芽糖浆"], 1300),
    (["白砂糖", "冰糖", "红糖", "蔗糖", "糖粉"], 1670),
    (["蜂蜜"], 1350),
    (["小麦粉", "全麦粉", "面粉", "米粉", "糯米粉"], 1500),
    (["淀粉"], 1550),
    (["全脂乳粉", "全脂奶粉"], 2070),
    (["脱脂乳粉", "脱脂奶粉"], 1500),
    (["大豆蛋白", "乳清蛋白", "蛋白粉"], 1620),
    (["鸡蛋", "全蛋"], 600),
    (["花生", "核桃", "芝麻", "坚果", "杏仁"], 2500),
    (["可可粉"], 1450),
    (["脱水蔬菜", "蔬菜干"], 1100),
    (["燕麦"], 1550),
    (["饮用水", "水"], 0),
    (["食盐", "食用盐", "酵母", "香辛料", "添加剂", "香精", "色素",
      "碳酸氢钠", "泡打粉", "柠檬酸"], 0),
]

DEFAULT_KJ = 900  # 未匹配配料的保守默认值, 会在结果中标记
GB_TOLERANCE = 1.20


def lookup_kj(name):
    for keywords, kj in INGREDIENT_KJ_DB:
        if any(k in name for k in keywords):
            return kj, False
    return DEFAULT_KJ, True


def infer_percentages(n, decay):
    """排名衰减权重推测百分比并归一化到 100%。"""
    weights = [decay ** i for i in range(n)]
    total = sum(weights)
    return [w / total * 100 for w in weights]


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    d = json.load(src)
    ings = d.get("ingredients") or []
    labeled = d.get("labeled_energy_kj")
    decay = d.get("decay", 0.8)

    if not ings:
        print(json.dumps({"status": "insufficient_data",
                          "detail": "未提供配料"}, ensure_ascii=False))
        return

    inferred = infer_percentages(len(ings), decay)
    items, total_kj, steps = [], 0.0, []
    unestimated = [i for i, x in enumerate(ings) if x.get("pct") is None]
    manual_sum = sum(x["pct"] for x in ings if x.get("pct") is not None)
    scale = (100 - manual_sum) / sum(inferred[i] for i in unestimated) \
        if unestimated and manual_sum < 100 else 1.0

    for idx, ing in enumerate(ings):
        name = ing["name"]
        pct = ing.get("pct") if ing.get("pct") is not None else inferred[idx] * scale
        kj_density = ing.get("kj_per_100g")
        if kj_density is None:
            kj_density, used_default = lookup_kj(name)
        else:
            used_default = False
        contrib = pct * kj_density / 100
        total_kj += contrib
        items.append({
            "rank": idx + 1, "name": name,
            "pct_estimated": round(pct, 1),
            "pct_source": "manual" if ing.get("pct") is not None else "inferred",
            "kj_per_100g": kj_density,
            "density_default_fallback": used_default,
            "energy_contribution_kj": round(contrib, 1),
        })
        steps.append(f"第{idx+1}位 {name}: {pct:.1f}% x {kj_density} kJ/100g "
                     f"= {contrib:.1f} kJ")

    report = {
        "status": "ok",
        "method": {
            "percentage_inference": f"排名衰减权重 w=r^(i-1), r={decay}, "
                                    f"归一化至 100% (GB 7718 降序规则)",
            "energy_accumulation": "Σ(配料百分比 x 单位热量 / 100)",
            "compliance_rule": "GB 28050: 能量实测/估算值 <= 标示值 x 120%",
        },
        "ingredients": items,
        "estimated_total_energy": {
            "kj": round(total_kj, 1),
            "kcal": round(total_kj / 4.184, 1),
        },
        "calculation_steps": steps + [f"合计: {total_kj:.1f} kJ "
                                      f"(≈{total_kj/4.184:.0f} kcal)"],
        "caveats": ([f"以下配料未匹配密度表, 使用默认值 {DEFAULT_KJ} kJ/100g: "
                     + ", ".join(i["name"] for i in items
                                 if i["density_default_fallback"])]
                    if any(i["density_default_fallback"] for i in items) else []),
    }

    if isinstance(labeled, (int, float)) and labeled > 0:
        deviation = (total_kj - labeled) / labeled
        ceiling = labeled * GB_TOLERANCE
        report["comparison"] = {
            "labeled_energy_kj": labeled,
            "deviation_percent": round(deviation * 100, 1),
            "compliant_ceiling_kj": round(ceiling, 1),
            "estimated_within_limit": total_kj <= ceiling,
            "verdict": "pass" if total_kj <= ceiling else "fail",
            "conclusion": (
                f"估算总热量 {total_kj:.0f} kJ, 标示值 {labeled:.0f} kJ, "
                f"偏差 {deviation:+.1%}; GB 28050 上限 {ceiling:.0f} kJ (120%), "
                f"结论: {'合格' if total_kj <= ceiling else '不合格, 标示值涉嫌虚标'}"),
        }
    else:
        report["comparison"] = {"verdict": "insufficient_data",
                                "detail": "未提供标示能量, 仅输出估算值"}

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
