# food-label-validator

一个开源的 WorkBuddy / Agent Skill：通过**配料表与营养成分表的交叉验证**，评估预包装食品标签的可信度。支持直接上传配料表 / 营养成分表照片，自动识别文字与表格，依据中国 GB 7718（标签通则）与 GB 28050（营养标签通则）给出分级结论。

An open-source agent skill that cross-validates food label credibility by checking the ingredient list against the nutrition facts table, based on China GB 7718 & GB 28050.

## 核心功能

1. **图像识别**：接收配料表 / 营养成分表照片，多模态直接读取文字与表格；`scripts/extract_tables.py` 负责把 OCR 结果规整为 `营养素 | 数值 | 单位 | NRV%` 结构。
2. **交叉验证**（四级证据）：
   - **L1 硬约束**（脚本确定性计算）：能量守恒（蛋白×17 + 脂肪×37 + 碳水×17 ±20%）、宏量营养素质量 ≤ 100 g/100 g、"0"界限值（脂肪 0 ≤ 0.5 g、糖 0 ≤ 0.5 g、反式脂肪酸 0 ≤ 0.3 g）。
   - **配料反推能量**：按 GB 7718 降序规则推测各配料百分比（排名衰减权重归一化至 100%），逐项乘以单位热量累加，与标示能量对照 GB 28050 的 120% 容差判定是否虚标。
   - **L2 配料-营养一致性**：降序规则 vs 宏量谱、氢化植物油 vs 反式脂肪酸标示、"无糖"宣称 vs 糖类排位等 12 条冲突模式。
   - **L3/L4 合理性与声称合规**：品类先验范围、高蛋白 ≥ 12 g/100 g 等 GB 28050 附录 C 条件。
3. **分级报告**：`pass` / `pass_with_warnings` / `suspect` / `inconsistent` / `insufficient_data`，每条结论附证据链与引用规则。

## 识别失败 / 数据缺失处理

- 低置信字段标记 `confidence: low`，不参与 L1 计算，进入人工确认清单
- 仅有单表时进入单源验证模式，明确标注"证据有限"
- 单位疑似误读（mg/g）只标记不改写
- 完全无法识别时返回 `status: unrecognized` 并给出重拍指引
- 原则：宁可输出"数据不足"，绝不编造数值

## 目录结构

```
food-label-validator/
├── SKILL.md                         # 触发条件 + 工作流 + 判定合成逻辑
├── references/
│   ├── gb28050-rules.md             # 界限值、NRV、声称条件、换算系数
│   ├── gb7718-rules.md              # 配料降序与标示要求
│   ├── conflict-patterns.md         # 配料↔营养冲突模式库 (L2/L3)
│   └── ingredient-calories.md       # 配料热量密度表
└── scripts/
    ├── extract_tables.py            # OCR 表格结构化与错列重对齐
    ├── cross_validate.py            # L1 能量守恒/质量边界/零声称阈值
    ├── estimate_energy.py           # 配料配比区间 → 能量区间估算
    └── food_energy_check.py         # 食品热量核验主程序（推测配比→累加→GB 判定）
```

## 使用方式

### 作为 WorkBuddy Skill

```bash
# 复制到用户级 skills 目录
cp -r food-label-validator ~/.workbuddy/skills/
```

然后直接对 WorkBuddy 说："帮我验证这个食品标签"，并上传配料表和营养成分表照片。

### 脚本独立使用

```bash
# 配料反推能量 + GB 28050 判定
echo '{"labeled_energy_kj": 2100, "ingredients": [{"name": "小麦粉"}, {"name": "植物油"}, {"name": "白砂糖"}]}' \
  | python scripts/food_energy_check.py

# L1 硬约束检查
echo '{"energy_kj": 2100, "protein_g": 6, "fat_g": 24, "carb_g": 60, "zero_claims": {"fat": true}}' \
  | python scripts/cross_validate.py
```

## 免责声明

本工具输出为参考性启发分析，不构成食品安全或合规的法律结论；配料百分比为基于降序规则的推测值。

## License

MIT
