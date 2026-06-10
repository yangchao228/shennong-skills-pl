# Skillfully 产品调研与本项目功能借鉴

调研日期：2026-05-28

调研对象：[Skillfully](https://www.skillfully.sh/)

## 1. 结论摘要

Skillfully 的核心定位不是“帮用户写 agent skill”，而是“给已经发布或准备发布的 agent skill 建立 QA 与反馈闭环”。

它的产品主线可以概括为：

1. 创建或导入 skill
2. 发布并接入运行追踪
3. 收集真实运行反馈
4. 看使用量、成功率、失败原因
5. 基于真实反馈改进 skill

这和我们当前项目的定位有明显区别。

我们项目定位是：

> 管理好本机 skills，并方便用户迭代自己的专属技能。

所以不应该照搬 Skillfully 的“发布、云端工作区、目录分发、团队协作”路线。真正值得引入的是它的“反馈闭环”和“基于证据迭代”的产品思想。

最值得优先引入的能力是：

1. 本地运行反馈记录
2. Skill contract 检查清单
3. 运行历史与成功率
4. 反馈聚类后的改进队列
5. 改进建议生成 Diff，并由用户确认后应用

## 2. Skillfully 产品定位

官网首页直接把 Skillfully 定义为：

> Agent skill QA and analytics.

公开页面强调它用于创建、发布、监控和改进 agent skills，让 skill 作者知道哪些 skill 被使用、哪里失败、下一步该改什么。

它面向两类人：

- 开发者型 skill 作者：代码审查、SQL 辅助、API debug、单测生成等。
- 领域专家型 skill 作者：onboarding、分析流程、合规检查、报告生成等。

这说明 Skillfully 把 skill 看成一种可发布、可运营、可持续优化的知识产品，而不是一次性 prompt。

## 3. Skillfully 解决的核心问题

Skillfully 抓住的问题很明确：

> Agent skills 很容易发布，但很难知道它是否真的好用。

公开页面里反复强调几个痛点：

- skill 作者通常只能“发布后祈祷 agent 能理解”
- 失败反馈散落在 chat、issue、用户抱怨里
- 只看 markdown 文件本身，不知道真实运行效果
- 没有持续反馈层，就很难判断下一版该改什么

这和我们项目当前的“结构健康检查 + 测试 + 基线 + 回退”有互补关系。

我们的项目更擅长管理本地文件状态。Skillfully 更擅长把真实使用反馈变成迭代依据。

## 4. Skillfully 的主要产品模块

### 4.1 Overview 看板

首页展示的关键指标包括：

- Total skills
- Skill runs
- Success rate
- Waiting for feedback
- Recent feedback

这个看板的价值不在视觉，而在问题排序：用户打开后能知道哪些 skill 有真实使用、哪些没有反馈、哪些表现差。

### 4.2 Skill usage 使用分析

Skillfully 展示每个 skill 的运行次数、成功率和趋势。

这个能力解决的是：

- 哪些 skill 真正在被用
- 哪些 skill 放着没人用
- 哪些 skill 经常失败
- 哪些 skill 值得优先迭代

对我们项目来说，这比单纯展示“健康分”更接近真实使用价值。

### 4.3 Feedback detail 结构化反馈

Skillfully 的反馈详情包括：

- Skill
- Agent
- Run ID
- Time
- What worked
- What failed
- Suggested fix

这套结构很值得借鉴。它把一次失败从“用户感觉不好用”变成了可检索、可归因、可修复的数据。

### 4.4 Current / Draft 改进视图

官网展示了 Current 与 Draft 的对照。这背后的产品逻辑是：改进不应该直接覆盖当前版本，而应该先生成草稿，让用户判断。

这和我们项目已经引入的候选版本、候选 Diff、显式应用候选高度一致。

下一步可以继续往“反馈 -> 草稿 -> Diff -> 应用 -> 测试 -> 基线”闭环推进。

### 4.5 Skill status 发布状态

Skillfully 有类似状态流：

- Created skill
- Published version
- Connected feedback
- Directory submission

这个模块服务于“发布到外部”的产品目标。

我们当前定位是本机管理台，因此不建议照搬 Directory submission 或发布目录。但可以借鉴状态化表达，把本地 skill 分成：

- 未治理
- 已结构检查
- 已有测试
- 已保存基线
- 已有真实反馈
- 有候选改进待应用

## 5. Skillfully 的方法论

### 5.1 Skill 是可复用操作流程

Skillfully Guide 里把 agent skill 定义为 reusable operating procedure。它强调 skill 应该帮助 agent 更稳定地完成一个具体任务，而不是提供灵感。

可借鉴点：

- skill 应该描述一个可重复任务
- 需要明确输入、步骤、边界和可见结果
- 不适合一开始就写宽泛战略型 skill

### 5.2 先写可观察结果

Skillfully 强调 outcome 要能被证明，例如文件修改、命令执行、链接打开、结果提交。避免只写“优化、改进、润色”这类模糊结果。

这对我们的健康检查很有价值。当前项目已经能检查 frontmatter、description、工作流、异常路径、引用文件等。下一步可以增加“完成证据”维度。

### 5.3 Skill contract

Skillfully 的 contract 视角包括：

- 可信输入：哪些路径、URL、ID、账号上下文是必需的
- 工具和文件：agent 开始前应先看哪些文件或路由
- 完成证据：用什么命令、截图、diff 或 route check 证明完成
- 停止规则：遇到什么情况必须交给人判断
- 反馈提示：运行后如何收集反馈

这几项可以直接转化成本项目的结构检查项。

### 5.4 反馈应该发生在任务之后

Skillfully 不建议 feedback prompt 打断核心任务，而是放在完成标准附近。agent 先完成任务，再记录这次运行是否有效。

这对我们很重要。我们不应该让用户在使用 skill 前填写复杂表单，而应该在运行后提供一个轻量反馈入口。

### 5.5 负反馈和中性反馈更有价值

Skillfully 的质量文章强调，正反馈只能说明 skill 至少成功过一次；中性和负反馈更能暴露上下文丢失、卡住、错误下一步等问题。

本项目如果引入反馈模块，应优先展示：

- 失败最多的 skill
- 中性/负反馈最多的 skill
- 重复出现的失败原因
- 最近一次修改后是否减少了同类失败

## 6. 与本项目的定位差异

| 维度 | Skillfully | 本项目 |
|---|---|---|
| 核心定位 | 发布后 QA 与 analytics | 本机 skills 管理与个人迭代 |
| 使用场景 | 多 agent、多用户、发布后的真实使用 | 本机目录、个人专属 skill、局部治理 |
| 数据来源 | 运行追踪、用户/agent 反馈 | 本地文件、结构检查、测试用例、基线 |
| 主要价值 | 证明 skill 是否真的好用 | 管理、测试、回退、持续改进本地 skill |
| 风险 | 需要接入运行追踪，偏云端 | 容易停留在文件健康分，缺少真实反馈 |
| 值得借鉴 | 反馈闭环、使用分析、失败聚类 | 不应照搬发布目录和云端协作 |

判断：

Skillfully 更像“skill 发布后的产品运营系统”。本项目更应该成为“本地 skill 资产工作台”。

## 7. 值得引入的功能

### 7.1 本地运行反馈记录

优先级：P0

建议新增本地反馈数据结构，例如：

```json
{
  "run_id": "20260528-153000-hatch-pet",
  "skill_id": "hatch-pet",
  "agent": "codex",
  "task": "生成 Codex pet",
  "rating": "neutral",
  "what_worked": "能按流程调用 imagegen",
  "what_failed": "没有明确说明 QA 验收路径",
  "suggested_fix": "在最终交付步骤补充 qa/contact-sheet.png 和 final/validation.json 检查",
  "evidence": ["qa/contact-sheet.png", "final/validation.json"],
  "created_at": "2026-05-28T15:30:00+08:00"
}
```

理由：

当前项目有测试分数，但测试分数偏规则化，不能完全代表真实使用效果。引入运行反馈后，用户能从真实任务里知道 skill 哪里不清楚。

### 7.2 Skill contract 检查清单

优先级：P0

建议在结构健康检查里新增维度：

- 是否写清必需输入
- 是否写清可选输入
- 是否指定优先查看的文件、目录、命令或工具
- 是否写清完成证据
- 是否写清停止规则
- 是否写清失败或阻塞时的处理方式
- 是否有运行后反馈提示

理由：

这比单纯检查 description 长度更接近 skill 的真实质量。Skillfully 的 Guide 强调 contract，本项目可以把它产品化成结构检查。

### 7.3 使用与反馈看板

优先级：P0

建议首页增加本地治理看板：

- 总 skill 数
- 有测试的 skill 数
- 有基线的 skill 数
- 近期运行次数
- 成功/中性/失败反馈占比
- 待处理反馈数
- 有候选版本待应用的 skill 数

理由：

现在用户能看单个 skill，但缺少“今天该先处理什么”的总览。Skillfully 的 overview 看板值得借鉴，但我们要做成本地版。

### 7.4 反馈聚类与改进队列

优先级：P0

建议增加“待改进”视图：

| Skill | 反馈类型 | 重复次数 | 主要问题 | 建议动作 |
|---|---:|---:|---|---|
| hatch-pet | negative | 3 | QA 验收路径不清 | 生成候选改进 |
| report-generator | neutral | 2 | 完成证据模糊 | 补充 final answer 证据要求 |

理由：

Skillfully 的关键价值是让用户“基于证据改 skill”。本项目目前已经有候选版本机制，下一步应该让候选版本来自反馈聚类，而不是只来自测试失败。

### 7.5 AI 改进草稿必须走 Diff 审批

优先级：P0

建议标准流程变成：

1. 选择一组反馈
2. AI 生成改进草稿
3. 展示 Current / Draft Diff
4. 用户确认应用
5. 自动运行测试
6. 用户决定是否保存新基线

理由：

这同时吸收 Skillfully 的 Current / Draft 思路，也符合本项目“人的判断权保留给用户”的定位。

### 7.6 运行后轻量反馈入口

优先级：P1

建议在每次运行测试或用户手动记录运行后，提供三段式反馈：

- 这次完成了吗：positive / neutral / negative
- 卡在哪里
- 哪条 skill 指令应该修改

理由：

Skillfully 强调反馈在任务后发生，且要足够短。这个设计不会打断用户工作流。

### 7.7 Skill 迭代 changelog

优先级：P1

建议每次应用候选版本或保存基线时，要求选择或填写“本次修复哪类反馈”。

示例：

```markdown
## 2026-05-28

- 修复反馈簇：QA 验收路径不清
- 改动：补充 contact sheet、review、validation 的检查要求
- 验证：hp_qa_acceptance 通过
```

理由：

Skillfully 建议把 changelog 放在 skill 附近，记录每次编辑是为了解决哪类反馈。本项目已有版本历史，可以进一步增加“为什么改”的语义。

### 7.8 本地 readiness 状态

优先级：P1

建议给每个 skill 一个本地状态：

- Raw：仅有 SKILL.md
- Structured：结构检查无阻断
- Tested：已有测试用例
- Baselined：已保存基线
- Feedback-ready：已有反馈入口
- Improving：有待处理反馈或候选版本
- Stable：最近 N 次运行无负反馈

理由：

Skillfully 的发布状态不适合照搬，但状态化表达值得保留。它能让用户知道每个 skill 当前处在什么治理阶段。

## 8. 暂不建议引入的功能

### 8.1 公开发布目录

不建议现在做。

理由：

本项目定位是本机 skills 管理。公开发布会引入账号、审核、分发、版本兼容、隐私和维护成本，容易偏离当前目标。

### 8.2 云端 workspace

不建议现在做。

理由：

用户当前价值来自本地目录和个人资产治理。云端协作不是当前核心瓶颈。

### 8.3 多作者协作

不建议现在做。

理由：

当前用户场景是“自己的专属技能”。多人协作会提前引入权限、审计、评论、冲突解决。

### 8.4 外部运行追踪 SDK

短期不建议做成强依赖。

理由：

Skillfully 需要接入 runtime tracking，是因为它服务发布后的真实使用。本项目可以先做手动/本地反馈，再考虑接入 Codex、Claude Code 或其他 agent runtime。

## 9. 建议实施路线

### Phase 1：本地反馈闭环

目标：让用户能从真实运行里沉淀反馈。

功能：

- 新增本地 feedback JSONL 存储
- 单个 skill 页面展示反馈列表
- 支持 positive / neutral / negative
- 支持 what worked / what failed / suggested fix
- 首页展示待处理反馈数

### Phase 2：Skill contract 健康检查

目标：把 Skillfully 的 contract 方法论变成可执行检查。

功能：

- 新增 contract 维度检查
- 结构检查区拆成：基础结构、执行流程、完成证据、边界与停止规则、反馈闭环
- 支持忽略单项检查

### Phase 3：反馈驱动候选改进

目标：把反馈转成候选版本，而不是直接让 AI 自动改。

功能：

- 选择一条或一组反馈
- AI 生成候选改进
- 展示 Current / Draft Diff
- 用户应用候选
- 自动运行测试
- 保存新基线时记录 changelog

### Phase 4：本地运行分析

目标：让用户知道哪些 skill 值得优先改。

功能：

- 运行次数
- 成功率
- 中性/负反馈比例
- 最近一次运行时间
- 最近一次修改后反馈是否改善
- 负反馈重复原因 Top 5

## 10. 对当前产品定位的影响

引入这些功能后，产品定位可以从：

> 本地 skills 管理与进化平台

收敛为更清晰的：

> 本机 skills 资产工作台：管理、测试、反馈、改进自己的专属技能。

这个定位比“自动进化平台”更稳。

原因是：

- 用户不会把判断权交给自动化
- 改进来自真实反馈和测试证据
- 所有数据默认保存在本机
- skill 仍然是用户自己的数字资产
- 产品服务的是长期迭代，而不是一次性生成

## 11. 参考资料

- [Skillfully 官网](https://www.skillfully.sh/)
- [Start with agent skills](https://www.skillfully.sh/guide/start-with-agent-skills)
- [Design the skill contract](https://www.skillfully.sh/guide/design-the-skill-contract)
- [Install feedback collection](https://www.skillfully.sh/guide/install-feedback-collection)
- [How to write better agent skills](https://www.skillfully.sh/blog/how-to-write-better-agent-skills)
- [Measuring agent skill quality](https://www.skillfully.sh/blog/measuring-agent-skill-quality)
