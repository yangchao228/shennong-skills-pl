# Skills Manager

Skills 管理与进化平台，Web 界面，本地运行。

完整用户使用说明见：[docs/user-guide.md](docs/user-guide.md)

## 安装

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## 启动

```bash
# 自动检测 ~/.claude/skills 或 .claude/skills
./.venv/bin/python app.py

# 指定路径
SKILLS_PATH=/path/to/your/skills ./.venv/bin/python app.py

# 指定端口
./.venv/bin/python app.py 8080
```

打开 http://localhost:7890

默认只监听 `127.0.0.1`。当前项目没有登录鉴权，不要直接暴露到公网。

## 一键部署

适合本机或一台轻量 Linux 服务器直接跑起来。

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

默认会自动完成这些事：

- 创建 `.venv`
- 安装 `requirements.txt`
- 读取项目根目录 `.env`
- 后台启动服务
- 将运行状态写入 `runtime/`

如需自定义端口或 skills 目录，可编辑 `.env`：

```bash
APP_HOST=127.0.0.1
APP_PORT=7890
SKILLS_PATH=/path/to/your/skills
SKILLS_MANAGER_META_DIR=/path/to/manager-meta
SKILLS_MANAGER_PROTECTED_ROOTS=/path/to/protected/skills
SKILLS_MANAGER_PUBLIC_URL=http://127.0.0.1:7890
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENAI_CODEX_MODEL=gpt-5.2-codex
CODEX_COMMAND=codex
CODEX_MODEL=
CODEX_PROFILE=
CODEX_TIMEOUT_SECONDS=180
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
ALL_PROXY=socks5://127.0.0.1:7891
NO_PROXY=127.0.0.1,localhost
PIP_INDEX_URL=https://pypi.org/simple
PIP_TRUSTED_HOST=pypi.org
```

## AI 分析功能

项目现在统一通过一个 AI 适配层调用模型，不再在功能里写死 Claude。

默认策略：

- `AI_PROVIDER=auto`
- 优先使用当前可访问的本地 Ollama
- 若本地 Ollama 不可用，再回退到 Anthropic
- 若没有 Anthropic Key，但设置了 `OPENAI_API_KEY`，再回退到 OpenAI Codex API
- 若没有 OpenAI API Key，但本机可用 Codex CLI，再回退到本地 Codex

默认 Ollama 模型是 `glm4:latest`。

```bash
export AI_PROVIDER=auto
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=glm4:latest
python app.py
```

如果你的系统开了 `SOCKS` 代理，项目依赖里已经包含 `httpx[socks]`。
重新执行一次部署脚本即可自动补齐代理支持：

```bash
./scripts/deploy.sh restart
```

也可以显式指定 provider：

```bash
# 强制使用本地 ollama
export AI_PROVIDER=ollama

# 强制使用 anthropic
export AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export ANTHROPIC_MODEL=claude-sonnet-4-6

# 强制使用 OpenAI Python SDK 调用 Codex 模型
export AI_PROVIDER=openai_codex
export OPENAI_API_KEY=sk-...
export OPENAI_CODEX_MODEL=gpt-5.2-codex

# 强制使用本地 Codex CLI
export AI_PROVIDER=codex
export CODEX_COMMAND=codex
export CODEX_MODEL=gpt-5
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export ALL_PROXY=socks5://127.0.0.1:7891
```

现在这些能力都走统一 provider 选择：

- AI 分析
- AI 自动生成测试用例
- 运行测试时的模型调用
- 自动进化中的改进提案

`openai_codex` provider 使用 OpenAI Python SDK 直接调用 Codex 模型，需要 `OPENAI_API_KEY`。`codex` provider 使用本机 `codex exec` 非交互调用，并固定为只读沙箱、永不请求审批、临时 session，适合已经在本机完成 `codex login` 的用户。如果你只想使用本机开源模型，优先使用 Ollama。

## Skill 类型分类

| 类型 | 说明 | 进化策略 |
|------|------|----------|
| 可验证型 | 输出有客观标准（代码生成、格式转换） | 自动进化，无需人工 |
| 锚点型 | 需对照人工审批样本评估 | 半自动，人工提供锚点 |
| 判断型 | 纯主观判断（内容风格类） | 只做维护，不自动进化 |

## 基线与回退

当前版本管理采用最小方案：

- 当前真实生效版本始终是本地 `SKILL.md`
- 你可以在 Web 上把当前版本 `保存为基线`
- 之后手动修改本地文件，再回到 Web `运行测试`
- 如果不满意，可以 `恢复到基线`

补充说明：

- 管理台元数据默认写入项目内 `runtime/meta/`，不再写进被管理的 skill 目录
- `test-cases.json`、摘要缓存、测试结果、版本快照、进化日志、反馈配置和运行反馈都属于管理台元数据
- `~/.codex/skills` 下的外部安装 skill 默认启用写保护；恢复版本等覆盖 `SKILL.md` 的操作需要显式确认
- 写保护 skill 的自动进化会先保存候选版本，用户查看 Diff 后再显式应用
- `恢复到基线` 前会自动保存一个 `pre-restore` 快照，防止误操作
- 版本历史会展示来源、时间、分数
- 历史支持前端分页和筛选
- Web 不再负责编辑 `SKILL.md`，请直接在本地文件里修改

## 本地反馈采集

反馈采集参考 Skillfully 的方式：不是让用户事后回平台填表，而是在管理台中生成一段 feedback snippet，并由用户确认后安装进目标 `SKILL.md`。

启用后，支持访问本机 endpoint 的 agent 会在任务完成或阻塞后，按 snippet 指令向本地接口提交一次结构化反馈：

- `POST /api/feedback/runs`
- 默认 endpoint 来自当前访问地址，也可以用 `SKILLS_MANAGER_PUBLIC_URL` 固定
- 反馈数据保存到外置元数据目录的 `feedback.jsonl`
- 如果 agent 无法访问本机 endpoint，snippet 会要求追加一条 JSONL 到 fallback file，同样会被最近反馈列表读取
- 写保护 skill 安装 snippet 前仍需要显式确认
- snippet 带稳定标记，重复安装会更新原片段，不会重复追加

当前不接入云端运行追踪，也不读取聊天记录。无法访问本机 `localhost` 且无法写本地 fallback file 的纯网页聊天场景暂不属于自动回传范围。

## 用户指南

如果你不是在改代码，而是在实际使用这个系统，直接看这里：

- [用户使用指南](docs/user-guide.md)

## 本地验证

修改核心治理链路后，先跑本地 smoke test：

```bash
python3 -m py_compile app.py scripts/smoke_local.py scripts/e2e_local.py
bash -n scripts/deploy.sh
./.venv/bin/python scripts/smoke_local.py
./.venv/bin/python scripts/e2e_local.py
```

`smoke_local.py` 会用临时 skills/meta 目录验证元数据外置、写回保护、反馈采集、候选 Diff 和候选应用流程。

`e2e_local.py` 会用 Flask test client、临时 skills/meta 目录和 fake Codex CLI 覆盖主要 HTTP 路由，包括反馈 snippet 安装和 agent 风格回传；不启动端口、不调用真实模型、不访问真实 skill 目录。

## 安全

- 默认监听 `127.0.0.1`
- 当前没有认证层，不要直接公网暴露
- `.env`、`.venv`、`runtime/` 不应提交
- 对外部安装 skill，建议配置 `SKILLS_MANAGER_PROTECTED_ROOTS`
- 更多说明见 [SECURITY.md](SECURITY.md)
