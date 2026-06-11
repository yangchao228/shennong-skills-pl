# 用户使用指南

本文面向这个项目的实际使用者，重点回答三件事：

1. 这个系统能做什么
2. 怎么启动并开始用
3. 日常如何管理和进化 skill

## 1. 产品定位

`Skills Manager` 是一个本地 Web 管理台，用来集中管理你的 skill 目录，并围绕每个 `SKILL.md` 做这些事：

- 浏览 skill 列表与基本信息
- 检查结构健康度
- 监听本地编辑器里的 `SKILL.md` 修改
- 给 skill 标记进化类型
- 用 AI 做诊断
- 为 skill 生成测试用例
- 运行测试并计算分数
- 保存基线、查看 Diff、恢复历史版本
- 自动进化并保留历史版本

适合的场景：

- 你已经有一批 skills，需要统一治理
- 你想知道哪些 skill 结构有问题
- 你希望把 skill 从“能用”推进到“可测试、可进化、可维护”

## 2. 运行前准备

### 环境要求

- Python 3.10+
- 一个可用的 skills 目录
- 如需 AI 分析 / 生成测试 / 自动进化，需要至少一种模型能力：
  - 本地 Ollama
  - 或 Anthropic API Key
  - 或 OpenAI API Key
  - 或已经登录的本地 Codex CLI

### skills 目录默认规则

程序会按下面顺序寻找 skills 目录：

1. 环境变量 `SKILLS_PATH`
2. 当前项目下 `.claude/skills`
3. `~/.claude/skills`

每个 skill 至少需要：

- 一个单独目录
- 目录内存在 `SKILL.md`

示例：

```text
skills/
  writing-helper/
    SKILL.md
  meeting-summarizer/
    SKILL.md
```

## 3. 启动方式

### 方式一：直接启动

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
python app.py
```

默认访问地址：

```text
http://localhost:7890
```

也可以指定技能目录或端口：

```bash
SKILLS_PATH=/path/to/skills python app.py
python app.py 8080
```

### 方式二：使用部署脚本

适合长期在本机或轻量服务器上跑。

```bash
cp .env.example .env
chmod +x scripts/deploy.sh
./scripts/deploy.sh start
```

常用命令：

```bash
./scripts/deploy.sh init
./scripts/deploy.sh start
./scripts/deploy.sh status
./scripts/deploy.sh logs
./scripts/deploy.sh stop
./scripts/deploy.sh restart
```

## 4. 配置说明

常用环境变量如下：

| 变量 | 作用 | 默认值 |
|---|---|---|
| `APP_HOST` | 服务监听地址 | `127.0.0.1` |
| `APP_PORT` | 服务端口 | `7890` |
| `SKILLS_PATH` | skills 根目录 | 自动检测 |
| `SKILLS_MANAGER_META_DIR` | 管理台元数据目录 | `runtime/meta` |
| `SKILLS_MANAGER_PROTECTED_ROOTS` | 写保护 skill 根目录，多个路径用系统 path separator 分隔 | `~/.codex/skills` |
| `SKILLS_MANAGER_PUBLIC_URL` | 生成反馈回传 endpoint 时使用的访问地址，留空则用当前浏览器访问地址 | 空 |
| `AI_PROVIDER` | AI 提供方选择策略 | `auto` |
| `OLLAMA_BASE_URL` | Ollama 地址 | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | 默认 Ollama 模型 | `glm4:latest` |
| `ANTHROPIC_API_KEY` | Anthropic 密钥 | 空 |
| `ANTHROPIC_MODEL` | Anthropic 模型 | `claude-sonnet-4-6` |
| `OPENAI_API_KEY` | OpenAI API 密钥，用于 SDK 调用 Codex 模型 | 空 |
| `OPENAI_CODEX_MODEL` | OpenAI Codex API 模型 | `gpt-5.2-codex` |
| `CODEX_COMMAND` | 本地 Codex CLI 命令 | `codex` |
| `CODEX_MODEL` | Codex 使用的模型，留空则用 Codex 默认配置 | 空 |
| `CODEX_PROFILE` | Codex 配置 profile，留空则不用 | 空 |
| `CODEX_TIMEOUT_SECONDS` | Codex 单次调用超时时间 | `180` |
| `HTTP_PROXY` | HTTP 代理，Codex CLI 可继承 | 空 |
| `HTTPS_PROXY` | HTTPS 代理，Codex CLI 可继承 | 空 |
| `ALL_PROXY` | SOCKS/全局代理，Codex CLI 可继承 | 空 |
| `NO_PROXY` | 不走代理的地址 | `127.0.0.1,localhost` |

### 元数据存储规则

管理台默认不往被管理的 skill 目录写缓存文件。

这些数据会写到 `SKILLS_MANAGER_META_DIR`：

- skill 类型标记
- 总览摘要缓存
- 测试用例
- 最近测试结果
- 基线信息
- 版本快照
- 进化日志
- 反馈采集配置
- agent 回传的运行反馈

只有恢复版本、恢复基线、自动进化保留改进版、安装反馈采集片段这类明确改变 skill 内容的操作，才会写回真实 `SKILL.md`。

### 写回保护规则

`~/.codex/skills` 下的外部安装 skill 默认启用写保护。

写保护不会影响：

- 扫描列表
- 结构检查
- AI 分析
- 测试用例保存
- 测试运行
- 基线快照保存
- Diff 查看
- 反馈配置保存
- 反馈事件读取

写保护会拦住静默覆盖 `SKILL.md` 的操作：

- 恢复历史版本
- 恢复到基线
- 自动进化直接保留改进版
- 安装反馈采集片段

对写保护 skill，自动进化默认只保存候选版本，不覆盖真实 `SKILL.md`。如果确实要写回，需要在操作时显式确认。

候选版本会出现在历史记录里，来源标记为 `候选`。建议先查看候选 Diff，再决定是否应用。应用候选前系统会保存一个 `pre-apply-candidate` 快照，方便回退。

### AI provider 规则

默认是：

```bash
AI_PROVIDER=auto
```

当前逻辑：

1. 优先检查本地 Ollama 是否可用，且模型是否存在
2. 如果可用，走 Ollama
3. 否则如果设置了 `ANTHROPIC_API_KEY`，走 Anthropic
4. 否则如果设置了 `OPENAI_API_KEY`，走 OpenAI Python SDK 调用 Codex 模型
5. 否则如果本机存在 Codex CLI，走本地 Codex
6. 都不可用，则 AI 相关功能会失败

如果你想强制指定：

```bash
AI_PROVIDER=ollama
```

或：

```bash
AI_PROVIDER=anthropic
```

或：

```bash
AI_PROVIDER=openai_codex
OPENAI_API_KEY=sk-...
OPENAI_CODEX_MODEL=gpt-5.2-codex
```

或：

```bash
AI_PROVIDER=codex
CODEX_COMMAND=codex
CODEX_MODEL=gpt-5
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
ALL_PROXY=socks5://127.0.0.1:7891
```

`openai_codex` provider 使用 OpenAI Python SDK 直连 Codex 模型，需要 `OPENAI_API_KEY`。`codex` provider 会通过本机 `codex exec` 非交互调用，并固定使用只读沙箱、永不请求审批和临时 session；它依赖你本机已经完成 `codex login`，适合复用本地 Codex 配置。如果目标是本机开源模型，优先使用 Ollama。

## 5. 界面说明

页面主要分成两部分：

- 左侧：skill 列表
- 右侧：当前 skill 的详细操作区

### 左侧列表能看什么

每个 skill 会显示：

- skill 名称
- 健康分与等级
- skill 类型
- 是否已有测试用例
- 阻断项 / 风险项 / 优化项提示
- 最近修改日期

默认会优先把结构健康度较差的 skill 排到前面，方便先处理问题。

### 右侧详情分两个标签页

1. `总览`
2. `版本与测试`

## 6. 总览页怎么用

### 6.1 结构检查

系统会自动检查 `SKILL.md` 的基础结构，并分成三层：

- `阻断项`：会直接影响可用性，优先修
- `风险项`：现在不一定坏，但会影响稳定性或维护
- `优化项`：不影响当前使用，但会影响长期复用和治理

典型检查包括：

- frontmatter 是否缺 `name`
- 是否缺 `description`
- `description` 是否过短
- 是否缺中文触发词
- 是否缺 `README.md`
- 是否缺工作流结构
- 是否缺异常处理路径
- 内容是否过短
- 引用的依赖文件是否实际存在

建议处理顺序：

1. 先清掉阻断项
2. 再处理风险项
3. 最后按价值决定是否做优化项

### 6.2 反馈采集

`反馈采集`用于把真实使用结果带回管理台。它不是一个让用户事后填写的表单，而是把一段回传指令安装到 `SKILL.md` 的任务收尾规则里。

推荐流程：

1. 在 skill 详情页点击 `启用反馈采集`
2. 查看系统生成的 snippet 和安装 Diff
3. 确认后写入 `SKILL.md`
4. 在 Codex、Claude Code 等本地 agent 中正常使用这个 skill
5. agent 在完成任务或遇到阻塞后，向本地 `POST /api/feedback/runs` 提交结构化反馈
6. 如果本地 endpoint 不可达，agent 追加一条 JSONL 到 snippet 中给出的 fallback file
7. 回到详情页查看最近反馈

反馈字段包括：

- `rating`：`positive`、`neutral`、`negative`
- `task_summary`
- `what_worked`
- `what_failed`
- `suggested_fix`
- `evidence`

注意：

- 反馈配置和 `feedback.jsonl` 保存在 `SKILLS_MANAGER_META_DIR`
- 安装 snippet 会修改真实 `SKILL.md`，写保护 skill 需要显式确认
- snippet 会要求 agent 不提交聊天全文、密钥、token 或无关用户数据
- 如果本地 endpoint 不可用，agent 只尝试一次，然后写 fallback file，不反复重试
- 纯网页聊天如果既不能访问你的本机 `localhost`，也不能写本地 fallback file，暂时不能自动回传

### 6.3 进化类型

每个 skill 可以手动标记为一种类型：

- `可验证型`
  - 输出有客观标准
  - 最适合自动测试和自动进化
- `锚点型`
  - 需要人工审批样本作为参照
  - 更适合半自动治理
- `判断型`
  - 强依赖主观判断
  - 适合维护，不适合全自动进化

如果你不确定，先选 `可验证型` 只在输出确实能被规则判断时使用；否则宁愿保守。

### 6.4 AI 分析

点击 `运行分析` 后，系统会对当前 `SKILL.md` 做一次智能诊断，并返回：

- 建议的 skill 分类
- 分类理由
- 主要问题
- 改进建议
- 总体评价

适合在这些场景使用：

- 新接手一个 skill，不清楚问题在哪
- 准备开始补测试或做自动进化
- 想先拿到一个低成本改进方向

注意：

- 当前实现里，分析接口实际走统一 AI provider 层，但生成 JSON 的入口按 Ollama 风格组织返回，所以优先建议先确保本地 Ollama 可用

## 7. 版本与测试怎么用

这是项目最核心的部分。

### 7.1 测试用例

一个 skill 想进入自动进化，先要有测试用例。

你有两种方式获得它：

1. 点击 `AI 自动生成测试用例`
2. 在管理台元数据目录里手工编写对应的 `test-cases.json`

当前支持的 validator 类型：

- `contains`
- `not_contains`
- `min_length`
- `json_valid`
- `regex`
- `length_range`

一个典型测试文件结构大致如下：

```json
{
  "cases": [
    {
      "id": "tc1",
      "name": "基础测试",
      "prompt": "请完成某个任务",
      "validators": [
        { "type": "contains", "value": "步骤 1" },
        { "type": "min_length", "value": 100 }
      ]
    }
  ]
}
```

建议：

- 每个 skill 先从 2 到 3 个关键测试开始
- 优先覆盖真正影响质量的核心输出
- 不要一开始堆太多 validator，先保证测试有效

### 7.2 运行测试

点击 `运行测试` 后，系统会：

1. 用当前 `SKILL.md` 执行所有测试用例
2. 展示每个用例的通过情况
3. 计算综合分数

这个步骤适合：

- 设置基线前先确认测试是否合理
- 修改 `SKILL.md` 后快速回归
- 自动进化前先知道当前水平

### 7.3 保存为基线

点击 `保存为基线` 后，系统会运行当前测试，并把当前 `SKILL.md` 保存成一份基线快照。

这个基线用于两类场景：

- 你手动修改 `SKILL.md` 后，文件监听器会自动比较新旧分数
- 你可以随时对比当前版本与基线，也可以恢复到基线

建议在这几个时点设基线：

- 你确认当前版本“基本可接受”之后
- 补完测试用例之后
- 完成一轮人工优化之后

### 7.4 开始自动进化

点击 `开始自动进化` 后，系统会执行这个流程：

1. 跑当前基线测试
2. 用 AI 生成一个小幅改进版 `SKILL.md`
3. 再跑同样的测试
4. 如果分数提高，就保留新版本
5. 如果没有提高，就回滚
6. 连续两轮没有改进，提前收敛
7. 全过程保留版本快照和进化日志

你可以设置最大轮数，默认是 `5`。

适合自动进化的前提：

- skill 的目标比较明确
- 输出能被测试规则约束
- 测试用例足够代表真实质量

不适合自动进化的情况：

- 纯风格型、强主观 skill
- 测试规则很弱，分数不能代表真实质量
- skill 目标本身还没定义清楚

### 7.5 历史与恢复

每次进化后，系统会记录：

- `evolution-log.jsonl`
- `versions/` 下的版本快照

这些文件位于管理台元数据目录，不在原 skill 目录内。

你可以在历史面板里：

- 查看每轮分数变化
- 按来源筛选历史版本
- 查看候选版本 Diff
- 应用候选版本
- 恢复到某个历史版本或当前基线
- 查看当前版本与基线之间的 Diff

恢复会直接覆盖当前 `SKILL.md`，所以建议在明确回退目的时再做。

## 8. 如何编辑 SKILL.md

当前版本不在 Web 页面里直接编辑 `SKILL.md`。

推荐方式是：

1. 用本地编辑器直接修改对应 skill 目录里的 `SKILL.md`
2. 回到 Web 页面运行测试
3. 对照基线分数和 Diff 判断是否保留
4. 满意后保存为新的基线

这样做的好处是：

- 当前真实生效版本始终是本地文件
- 修改过程可以继续使用你熟悉的编辑器和 Git 工具
- Web 只负责治理动作：测试、分析、基线、历史、回退

如果当前 skill 已经设置过基线，且目录监听生效，那么你从外部编辑器直接改 `SKILL.md` 时，也会收到通知。

## 9. 文件监听与通知

系统启动后会监听 skills 目录下的 `SKILL.md` 变化。

当检测到外部修改时：

1. 页面右上角通知会收到变更提示
2. 如果该 skill 有测试用例，系统会自动重新跑测试
3. 会把新分数与基线比较
4. 如果分数大幅下降，系统会自动触发进化

这意味着你可以这样协作：

- 在编辑器里改 `SKILL.md`
- 在浏览器里看结果、通知、测试分数和基线 Diff
- 必要时恢复到基线或历史版本

## 10. 推荐使用流程

如果你是第一次用，建议按这个顺序：

1. 启动服务并确认能看到 skill 列表
2. 先处理阻断项多的 skill
3. 给 skill 选择合适类型
4. 跑一次 AI 分析，拿到问题和建议
5. 为关键 skill 生成或编写测试用例
6. 先手动运行测试，确认测试靠谱
7. 保存为基线
8. 再启动自动进化
9. 通过历史记录检查是否真的变好

如果你想长期治理 skill 库，建议形成下面的节奏：

- 新建 skill 后，先补 frontmatter 和 description
- 进入库前，至少补 2 个核心测试
- 每次大改后，重新保存基线
- 优先维护高价值、可验证的 skill

## 11. 常见问题

### 页面打开了，但列表是空的

先检查：

- `SKILLS_PATH` 是否指向正确目录
- 目录下是否每个 skill 都有 `SKILL.md`
- `/api/config` 返回的 `skills_path` 是否正确

### AI 分析或生成测试失败

通常是下面几类原因：

- 本地 Ollama 没启动
- `OLLAMA_MODEL` 不存在
- 没有配置 `ANTHROPIC_API_KEY`
- `AI_PROVIDER=openai_codex` 时没有配置 `OPENAI_API_KEY`
- `AI_PROVIDER=codex` 时本机没有安装或登录 Codex CLI
- 当前网络或代理配置导致模型调用失败

先确认：

```bash
echo $AI_PROVIDER
echo $OLLAMA_BASE_URL
echo $OLLAMA_MODEL
echo $OPENAI_CODEX_MODEL
codex doctor --summary
```

### 自动进化一直没有提升

通常不是“模型不行”，而是测试设计有问题。优先检查：

- 测试是否覆盖了核心目标
- validator 是否太弱
- 提示词目标是否本身模糊
- 这个 skill 是否其实不适合自动进化

### 修改后没有收到通知

先检查：

- 服务是否正常运行
- 页面顶部是否显示“文件监听中”
- 你修改的是不是 `SKILL.md`
- skills 目录是否就是当前被监听的目录

## 12. 当前版本已知边界

基于当前实现，有这些边界需要知道：

- UI 里可以查看测试，但当前没有提供完整的测试用例可视化编辑器，复杂场景仍建议直接编辑管理台元数据目录里的 `test-cases.json`
- AI 分析和测试生成依赖模型输出稳定 JSON，模型不稳定时可能失败
- 自动进化更适合小步优化，不适合大规模重写 skill
- `恢复版本` 是直接覆盖，不带二次 diff 对比
- 结构健康分是辅助指标，不等于真实效果分

## 13. 本地 smoke test

如果你在修改这个项目本身，建议每次改核心链路后运行：

```bash
python3 -m py_compile app.py scripts/smoke_local.py scripts/e2e_local.py
bash -n scripts/deploy.sh
./.venv/bin/python scripts/smoke_local.py
./.venv/bin/python scripts/e2e_local.py
```

这个脚本会创建临时 skills/meta 目录，验证元数据外置、写回保护、候选版本 Diff 和应用候选流程，不会污染真实 skill 目录。

其中 `scripts/e2e_local.py` 会使用 fake Codex CLI 覆盖主要 HTTP 路由，不启动端口，也不会调用真实模型。

## 14. 你真正该关心什么

如果只保留一个使用原则，就是这句：

不要把这个系统当成“自动写 skill 的工具”，而要把它当成“让 skill 变成可管理资产的工具”。

真正高价值的用法不是多跑几轮 AI，而是把你的 skill 库逐步变成：

- 有结构
- 有测试
- 有版本
- 可回退
- 可持续进化

这才是长期可沉淀的部分。
