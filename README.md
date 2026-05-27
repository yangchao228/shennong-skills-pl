# Skills Manager

Skills 管理与进化平台，Web 界面，本地运行。

完整用户使用说明见：[docs/user-guide.md](docs/user-guide.md)

## 安装

```bash
pip install -r requirements.txt
```

## 启动

```bash
# 自动检测 ~/.claude/skills 或 .claude/skills
python app.py

# 指定路径
SKILLS_PATH=/path/to/your/skills python app.py

# 指定端口
python app.py 8080
```

打开 http://localhost:7890

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
APP_HOST=0.0.0.0
APP_PORT=7890
SKILLS_PATH=/path/to/your/skills
SKILLS_MANAGER_META_DIR=/path/to/manager-meta
SKILLS_MANAGER_PROTECTED_ROOTS=/path/to/protected/skills
ANTHROPIC_API_KEY=sk-ant-...
PIP_INDEX_URL=https://pypi.org/simple
PIP_TRUSTED_HOST=pypi.org
```

## AI 分析功能

项目现在统一通过一个 AI 适配层调用模型，不再在功能里写死 Claude。

默认策略：

- `AI_PROVIDER=auto`
- 优先使用当前可访问的本地 Ollama
- 若本地 Ollama 不可用，再回退到 Anthropic

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
```

现在这些能力都走统一 provider 选择：

- AI 分析
- AI 自动生成测试用例
- 运行测试时的模型调用
- 自动进化中的改进提案

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
- `test-cases.json`、摘要缓存、测试结果、版本快照和进化日志都属于管理台元数据
- `~/.codex/skills` 下的外部安装 skill 默认启用写保护；恢复版本等覆盖 `SKILL.md` 的操作需要显式确认
- 写保护 skill 的自动进化会先保存候选版本，用户查看 Diff 后再显式应用
- `恢复到基线` 前会自动保存一个 `pre-restore` 快照，防止误操作
- 版本历史会展示来源、时间、分数
- 历史支持前端分页和筛选
- Web 不再负责编辑 `SKILL.md`，请直接在本地文件里修改

## 用户指南

如果你不是在改代码，而是在实际使用这个系统，直接看这里：

- [用户使用指南](docs/user-guide.md)

## 本地验证

修改核心治理链路后，先跑本地 smoke test：

```bash
./.venv/bin/python scripts/smoke_local.py
```

它会用临时 skills/meta 目录验证元数据外置、写回保护、候选 Diff 和候选应用流程。
