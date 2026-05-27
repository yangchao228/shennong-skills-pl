# Hatch Pet 治理样本

## 样本目标

用真实安装的 `hatch-pet` skill 验证 Skills Manager 的治理价值。

本轮不直接修改 `/Users/yangchao/.codex/skills/hatch-pet`，先验证管理台的诊断质量，并沉淀一份可复用的测试协议草案。

## 样本来源

- skill 目录：`/Users/yangchao/.codex/skills/hatch-pet`
- 核心文件：`SKILL.md`
- 参考文件：
  - `references/codex-pet-contract.md`
  - `references/qa-rubric.md`
  - `references/animation-rows.md`
- 候选测试用例：`docs/samples/hatch-pet-test-cases.json`

## 初始诊断

修复前，管理台对 `hatch-pet` 的健康检查结果是：

| 指标 | 结果 |
|---|---:|
| 健康分 | 0 |
| 等级 | D |
| 阻断项 | 29 |
| 风险项 | 1 |
| 优化项 | 2 |

主要阻断项集中在“引用文件不存在”，例如：

- `imagegen-jobs.json`
- `record_imagegen_result.py`
- `generate_pet_images.py`
- `prepare_pet_run.py`
- `qa/review.json`
- `final/validation.json`
- `${CODEX_HOME:-$HOME/.codex}/pets/<pet-name>/pet.json`

## 判断

这不是 `hatch-pet` 真的有 29 个阻断问题。

根因是 Skills Manager 的依赖检查规则太粗：

- 把运行时生成的 `imagegen-jobs.json`、`qa/review.json`、`final/validation.json` 当成静态依赖。
- 只在 skill 根目录找脚本，漏掉了真实存在的 `scripts/record_imagegen_result.py` 这类文件。
- 把带 `${CODEX_HOME}` 和 `<pet-name>` 的占位路径当成真实文件路径。
- 工作流检测只识别 `Step 1`、`阶段 1` 这类格式，漏掉 `Default Workflow`。

这个样本说明，复杂 skill 的治理优先要保证诊断可信。误报太多会让健康分失去决策价值。

## 本轮修复

已调整 `app.py` 的结构检查逻辑：

- 裸脚本名会额外到 `scripts/` 下查找。
- 带 `$`、`{}`、`<>` 的占位路径不再作为缺失文件。
- `run/`、`qa/`、`final/`、`frames/`、`decoded/`、`prompts/`、`references/` 下的运行产物不再作为静态缺失依赖。
- `imagegen-jobs.json`、`pet_request.json`、`pet.json` 这类生成产物不再误判为静态依赖。
- 工作流检测增加 `Default Workflow`、`Visible Progress Plan` 等真实标题识别。

修复后，`hatch-pet` 的健康检查结果变为：

| 指标 | 结果 |
|---|---:|
| 健康分 | 87 |
| 等级 | B |
| 阻断项 | 0 |
| 风险项 | 1 |
| 优化项 | 1 |

剩余问题：

- `description` 缺少中文触发词。
- 缺少 `README.md`。

这两个问题更符合真实治理优先级：不阻断运行，但影响中文触发稳定性和交接成本。

## 候选测试协议

`docs/samples/hatch-pet-test-cases.json` 提供 4 个初始测试：

| 用例 | 验证目标 |
|---|---|
| `hp_text_only_run_start` | 文本描述场景下能启动正确工作流，并调用 `prepare_pet_run.py` 与 `$imagegen` |
| `hp_no_local_art_fallback` | 当 imagegen 不可用时，不用 Python/Pillow 伪造视觉资产 |
| `hp_subagent_row_generation` | base 记录后，行生成阶段使用 subagent 分工，并由父 agent 记录结果 |
| `hp_qa_acceptance` | 最终交付前检查 contact sheet、review、validation 和身份一致性 |

这些用例暂不写入真实 skill 目录。原因：

- 当前测试会真实调用模型，成本和稳定性受 AI provider 影响。
- validators 还需要经过一轮真实模型输出校准，避免把合理回答误判失败。
- `hatch-pet` 是已安装 skill，直接写入运行目录会改变管理台状态。

## 建议下一步

1. 在 Web 上把 `hatch-pet` 类型标为 `可验证型`。
2. 将 `docs/samples/hatch-pet-test-cases.json` 复制为真实 `test-cases.json` 后，先只运行 1-2 个用例。
3. 根据真实输出校准 validators，优先减少脆弱的 `contains`，增加语义更稳的 `regex`。
4. 确认测试稳定后，再保存基线。
5. 最后再考虑补 `hatch-pet/README.md` 和中文触发词。

## 对产品的启发

这个样本带来的产品结论：

- 结构检查要区分静态依赖、运行时产物、示例输出和占位路径。
- 健康分必须能解释“为什么扣分”，并且扣分要可行动。
- 对复杂 skill，先修误报，再谈自动进化。
- 测试用例应该先作为草案沉淀，校准后再进入运行目录。
