# TODO

1. 检查当前目录状态与现有文件
2. 确认 GitHub 仓库可访问、默认分支与远端状态
3. 将当前目录初始化并绑定到目标 GitHub 仓库
4. 将目录名对齐为仓库名
5. 验证 git 状态与远程配置

## Review

- 已确认远端仓库存在，默认分支为 `main`
- 已将目录重命名为 `shennong-skills-pl`
- 已接入远端仓库 `.git`，当前目录已由目标 GitHub 仓库接管
- 当前本地文件相对远端为未提交状态，尚未提交或推送

## 2026-04-22 一键部署脚本

1. 阅读当前启动方式与依赖
2. 设计最小可用部署流程
3. 增加一键部署脚本与环境样例
4. 更新 README 使用说明
5. 验证脚本语法与基本命令

### Review

- 已新增 `scripts/deploy.sh`，支持 `init/start/stop/restart/status/logs`
- 已新增 `.env.example`，把端口、skills 路径和 API Key 收敛到环境变量
- 已让 `app.py` 支持读取 `APP_HOST` 与 `APP_PORT`
- 已补齐 `watchdog` 依赖，避免部署后文件监听能力缺失
- 已验证 `bash -n scripts/deploy.sh`、`python3 -m py_compile app.py`、`./scripts/deploy.sh help`、`./scripts/deploy.sh status`
- 已发现并绕过机器默认 `pip` 私有源问题，脚本现支持 `PIP_INDEX_URL`
- 已将 watcher 固定为 polling 模式，避免 macOS FSEvents 权限问题导致服务崩溃
- 已完成真实接口验收：首页 `200`、`/api/config` 正常、`/api/skills` 返回 28 个技能
- 已补入 `httpx[socks]`，修复 SOCKS 代理环境下 AI 分析报 `socksio` 缺失的问题
- 已将 `AI 分析` 切换为本地 Ollama，默认模型 `glm4:latest`
- 已把所有模型调用收敛到统一 provider 选择层，默认 `auto` 优先本地 Ollama

## 2026-04-22 结构检查分层

1. 盘点当前结构检查规则与前端展示
2. 将检查结果改为阻断项/风险项/优化项
3. 调整侧边栏与详情展示文案
4. 保留健康分，但降级为次要指标
5. 验证接口与页面渲染

### Review

- 已将结构检查输出改为 `blocking / risk / optimization` 三层
- 已为每条检查补充 `impact`，明确“不修会造成什么影响”
- 已让侧边栏优先显示阻断/风险/优化计数，不再只给一个笼统告警数
- 已让详情页分层展示结构检查结果，并把健康分降为次要参考
- 已验证 `/api/skills` 与 `/api/skills/<id>` 都已返回新的分层字段

## 2026-04-22 基线快照与历史回退

1. 为 skill 增加基线快照语义
2. 删除 Web 编辑能力
3. 增加版本历史、分页、筛选与恢复
4. 增加当前版本与基线版本 diff
5. 增加总览摘要缓存与手动重生成
6. 验证核心接口与页面渲染

### Review

- 已为版本快照补充 `source / created_at / score` 元数据
- 已新增基线状态、恢复到基线、摘要重生成、基线 diff 等接口
- 已将 Web 主交互收敛为 `运行测试 / 保存为基线 / 恢复到基线`
- 已移除 Web 编辑 `SKILL.md` 的路径
- 已支持历史分页、来源筛选、`pre-restore` 标记与恢复
- 已支持连续行块粒度的结构化 diff，并提供展开/收起
- 已支持摘要缓存，且在 `SKILL.md` 修改时间变化时自动失效

## 2026-04-22 用户使用指南

1. 阅读 README、后端路由与前端交互
2. 反推出当前系统的真实使用路径
3. 新增独立用户指南文档
4. 在 README 增加入口，避免说明分散

### Review

- 已新增 `docs/user-guide.md`，覆盖启动、配置、界面、测试、进化、版本恢复与常见问题
- 文档内容基于当前实现，不是泛化模板
- 已在 `README.md` 增加用户指南入口，降低首次使用门槛

## 2026-05-09 文档对齐与本地验证

1. 复查 README、用户指南、前端页面和后端路由
2. 修正用户指南中遗留的 Web 编辑页描述
3. 将使用路径统一为本地编辑 `SKILL.md`，Web 负责测试、基线、Diff 和回退
4. 执行语法检查与接口 smoke test
5. 启动本地服务并做页面级 smoke test

### Review

- 已将 `docs/user-guide.md` 对齐当前两栏标签页：`总览`、`版本与测试`
- 已删除“编辑页直接保存 SKILL.md”的旧描述
- 已明确当前真实工作流：本地编辑器修改，Web 负责治理动作
- 已验证 `python3 -m py_compile app.py`、`bash -n scripts/deploy.sh`
- 已通过 Flask test client 验证 `/api/config` 与 `/api/skills` 返回 `200`
- 本地 7890 与 7891 端口被 `MiaoSS` 占用或干扰，已改用 `17989` 做 smoke test
- 页面级验证发现并修复 `connectNotifications is not defined`
- 已确认页面可渲染 32 个 skill，点击 skill 后显示 `总览`、`版本与测试`
- 已确认文件监听状态显示为 `文件监听中`，新页面无新增 console error

## 2026-05-25 推送与部署 smoke test

1. 推送本地领先远端的基线工作流提交
2. 用真实 skills 目录启动本地服务
3. 验证核心 API 与页面主路径
4. 修复启动脚本在空 pip 参数下的 Bash 兼容问题
5. 提交并推送本次修复

### Review

- 已将 `5534bf6 feat: add skills manager baseline workflow` 推送到 GitHub `main`
- 发现 `scripts/deploy.sh` 在 macOS Bash + `set -u` 下，空 `pip_args` 展开会触发 `unbound variable`
- 已修复空 pip 参数分支，避免默认部署路径直接失败
- 已验证 `bash -n scripts/deploy.sh`、`python3 -m py_compile app.py`、`./.venv/bin/python -m py_compile app.py`
- 已以前台方式启动服务到 `http://127.0.0.1:17989`，`SKILLS_PATH=/Users/yangchao/.codex/skills`
- 已验证 `/api/config` 返回 `200`，`/api/skills` 返回 20 个 skill
- 已用浏览器验证页面渲染、skill 点击、`版本与测试` 标签切换和基线操作区展示
- 浏览器 console 未发现 error/warning
- 当前环境下 Browser 截图接口超时，但 DOM 与交互 smoke test 已通过

## 2026-05-27 hatch-pet 治理样本

1. 用真实安装目录读取 `hatch-pet`
2. 复现健康检查中的阻断项
3. 判断阻断项是真问题还是检查器误报
4. 修复依赖检查和工作流识别规则
5. 沉淀治理样本文档与候选测试用例
6. 验证修复后的 API 结果

### Review

- 已确认 `hatch-pet` 初始健康检查为 `D / 0`，包含 29 个阻断项
- 根因是检查器把运行时产物、占位路径和 `scripts/` 下真实脚本误判为缺失依赖
- 已调整 `app.py`，让依赖检查区分静态依赖、生成产物、占位路径和脚本目录
- 已让工作流检测识别 `Default Workflow` 与 `Visible Progress Plan`
- 修复后 `hatch-pet` 健康检查变为 `B / 87`，阻断项降为 0
- 剩余问题为中文触发词不足和缺少 README，符合真实治理优先级
- 已新增 `docs/sample-governance-hatch-pet.md`
- 已新增 `docs/samples/hatch-pet-test-cases.json` 作为候选测试协议，暂不写入外部 skill 目录

## 2026-05-27 管理台元数据外置

1. 盘点当前写入 skill 目录的管理台状态
2. 新增独立元数据目录
3. 将 meta、测试用例、版本快照、进化日志迁到外部目录
4. 保留对旧版 skill 目录内元数据的只读兼容与自动迁移
5. 更新 README、用户指南和部署脚本
6. 用临时 skill 目录验证不再污染被管理目录

### Review

- 已新增默认元数据目录 `runtime/meta`
- 支持通过 `SKILLS_MANAGER_META_DIR` 自定义元数据目录
- `.skill-meta.json` 改为外部 `meta.json`
- `test-cases.json` 改为外部保存，同时兼容读取旧目录内文件
- `.versions/` 改为外部 `versions/`
- `evolution-log.jsonl` 改为外部保存
- `/api/config` 已返回 `meta_path`
- Web 顶部 skills 路径增加元数据目录提示
- `scripts/deploy.sh` 已透传 `SKILLS_MANAGER_META_DIR` 和 AI provider 相关环境变量
- 已用临时 skill 目录验证：保存类型、保存测试用例、保存版本快照均不再写入被管理 skill 目录
- 已将官方 `hatch-pet` 目录里的旧 `.skill-meta.json` 迁到 `/tmp/hatch-pet.skill-meta.legacy.json` 备份
- 已确认迁移后 `hatch-pet` 详情仍可读取外部 meta，且官方 skill 目录不再包含管理台缓存文件

## 2026-05-27 外部 skill 写回保护

1. 识别外部安装 skill 根目录
2. 对恢复历史版本和恢复基线增加写回确认
3. 让自动进化在外部 skill 上默认只保存候选版本
4. 在详情页标记写保护状态
5. 更新配置文档和用户指南
6. 验证受保护 skill 不会被静默覆盖

### Review

- 默认将 `~/.codex/skills` 视为写保护根目录
- 支持通过 `SKILLS_MANAGER_PROTECTED_ROOTS` 自定义写保护根目录
- `/api/skills/<id>` 已返回 `write_protection`
- 恢复历史版本和恢复基线在写保护 skill 上要求 `confirm_write=true`
- 自动进化在写保护 skill 上默认保存 `evolution-candidate`，不覆盖真实 `SKILL.md`
- Web 详情页对写保护 skill 显示 `写保护` 标记
- Web 恢复操作已增加外部 skill 写回确认文案

## 2026-05-27 候选版本应用流程

1. 区分 `evolution-candidate` 历史版本
2. 增加候选版本 Diff 接口
3. 增加应用候选接口
4. 应用前保存 `pre-apply-candidate` 快照
5. Web 历史列表增加候选筛选、候选 Diff 和应用按钮
6. 验证写保护 skill 应用候选仍需显式确认

### Review

- 历史筛选新增 `候选`
- `evolution-candidate` 在历史列表中显示为 `候选`
- 新增候选 Diff：当前 `SKILL.md` 对比候选版本
- 新增应用候选：应用前保存 `pre-apply-candidate`
- 写保护 skill 应用候选仍要求 `confirm_write=true`
- Web 支持先看候选 Diff，再显式应用候选

## 2026-05-27 本地 smoke test 固化

1. 新增本地 smoke 脚本
2. 用临时 skills/meta 目录验证核心 API
3. 覆盖元数据外置、写回保护、候选 Diff、候选应用、自动进化候选保存
4. 补充前端内联 JS 语法检查
5. 更新 README 和用户指南

### Review

- 已新增 `scripts/smoke_local.py`
- smoke 脚本不启动端口，不调用真实模型，不访问真实 skill 目录
- 已验证保存类型和测试用例不会污染被管理 skill 目录
- 已验证写保护恢复不带确认返回 `409`，带确认可恢复
- 已验证候选 Diff、候选应用和 `pre-apply-candidate` 快照
- 已验证写保护自动进化只保存 `evolution-candidate`，不覆盖 `SKILL.md`
- 已集成 `node --check` 前端内联 JS 语法检查

## 2026-05-27 最小 CI

1. 新增 GitHub Actions smoke workflow
2. 安装 Python 依赖
3. 执行 Python 和部署脚本语法检查
4. 执行本地 smoke test
5. 本地验证 workflow YAML 和 smoke 命令

### Review

- 已新增 `.github/workflows/smoke.yml`
- CI 在 push 到 `main` 和 pull request 时运行
- CI 使用 Python 3.11
- CI 执行 `python -m py_compile app.py scripts/smoke_local.py`
- CI 执行 `bash -n scripts/deploy.sh`
- CI 执行 `python scripts/smoke_local.py`
- 已本地验证 workflow YAML 可解析

## 2026-05-28 页面内写回确认

1. 盘点前端原生 `confirm/alert` 使用点
2. 新增复用的页面内 modal
3. 将恢复版本、恢复基线、应用候选改为页面内确认
4. 将失败/成功提示改为页面内提示
5. 验证 JS 语法、smoke test 与真实页面确认流程

### Review

- 已新增页面内 modal，统一承接确认与提示
- 已移除前端原生 `confirm/alert`
- 写保护恢复、恢复基线和应用候选会显示明确的写回风险说明
- 写保护确认按钮显示为 `确认写回`
- 已用真实页面验证应用候选 modal 可打开、可取消，取消后不写回官方 `hatch-pet/SKILL.md`

## 2026-05-28 Skillfully 产品调研

1. 调研 Skillfully 官网、Guide 与 Blog 公开信息
2. 提炼其 QA、analytics、feedback loop、skill contract 方法论
3. 对照本项目“本机 skills 管理与专属技能迭代”定位
4. 列出值得引入和暂不建议引入的功能
5. 生成调研文档

### Review

- 已新增 `docs/skillfully-product-research.md`
- 判断 Skillfully 核心价值是“发布后真实反馈闭环”，不是单纯 skill 编写器
- 对本项目最值得引入的是本地运行反馈、skill contract 检查、使用看板、反馈聚类和候选 Diff 审批
- 不建议现阶段引入公开发布目录、云端 workspace、多作者协作和强依赖外部 runtime tracking

## 2026-06-09 本地 Codex AI Provider

1. 盘点现有 AI provider 适配层
2. 设计本地 `codex exec` 的只读调用方式
3. 新增 `codex` provider 与 `auto` 选择逻辑
4. 更新部署环境变量与使用文档
5. 扩展 smoke test 覆盖 Codex provider 命令拼接

### Review

- 已新增 `openai_codex` provider，通过 OpenAI Python SDK 调用 Codex 模型，默认模型 `gpt-5.2-codex`
- 已新增 `codex` provider，通过本机 `codex exec` 非交互调用，使用只读沙箱、永不请求审批和临时 session
- `auto` 选择顺序为 Ollama、Anthropic、OpenAI Codex API、本地 Codex CLI，保留原有 Anthropic 优先级
- 已更新 `.env.example`、部署脚本、README 和用户指南
- 已扩展 smoke test，用 fake Codex CLI 验证本地 Codex provider，不依赖真实账号
- 已补充 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY` 代理配置说明与部署透传，便于本地 Codex CLI 走代理

## 2026-06-10 本地部署全功能测试

1. 复查当前未提交改动与测试入口
2. 运行语法检查、本地 smoke test 和 Codex provider 定向验证
3. 使用临时 skills/meta 目录本地部署服务
4. 覆盖配置、列表、详情、类型、测试用例、运行测试、基线、历史、Diff、恢复、候选应用、摘要、AI 分析、生成测试、自动进化、通知接口
5. 用浏览器验证 UI 主路径

### Review

- 已通过 `python3 -m py_compile app.py scripts/smoke_local.py`
- 已通过 `bash -n scripts/deploy.sh`
- 已通过 `./.venv/bin/python scripts/smoke_local.py`
- 已用临时 skills/meta 目录和 fake Codex CLI 覆盖 Flask API 主链路：配置、列表、详情、类型保存、AI 分析、生成测试、读取测试、运行测试、保存基线、历史、基线 diff、普通恢复、写保护恢复阻断/确认、候选 diff、候选应用阻断/确认、摘要重生成、自动进化 SSE、通知 SSE
- 已确认 `AI_PROVIDER=codex` 配置在 `/api/config` 中正确识别，fake Codex provider 可完成 JSON 与文本返回
- 真实本地 Codex 调用在当前工具沙箱内被阻止：Codex CLI 需要写 `~/.codex/state_5.sqlite`，沙箱只读；沙箱外升级执行申请连续超时，未能完成真实模型调用
- 本地 Flask 端口部署在当前工具沙箱内被阻止：绑定 `127.0.0.1:18089` 返回 `Operation not permitted`；沙箱外启动申请超时，因此未完成浏览器级页面点击验证
- 部署脚本可进入安装与启动流程，但当前沙箱下传入代理变量后 pip 会尝试走代理并输出连接 warning；依赖已安装时不影响后续测试
- 之后经用户明确要求继续，已获得沙箱外启动权限并完成真实浏览器测试：页面可加载，列表展示 `demo-skill`/`protected-skill`，详情页、AI 分析、版本与测试、生成测试、运行测试、保存基线、写保护标识、写保护恢复确认 modal 均通过；浏览器 console 未发现 error/warn
- 测试完成后尝试停止沙箱外 Flask 进程 `PID=82790`，普通沙箱无权限，升级 `kill 82790` 被审批系统拒绝；需要用户在本机终端手动执行 `kill 82790` 或关闭对应 Python 进程

## 2026-06-10 开源收口与 E2E 固化

1. 停止上轮浏览器测试遗留的 Flask 服务
2. 将临时 API 全链路测试沉淀为 `scripts/e2e_local.py`
3. 补充 `LICENSE`、`SECURITY.md`、`CONTRIBUTING.md`
4. 将默认监听地址从 `0.0.0.0` 收敛为 `127.0.0.1`
5. 更新 README、用户指南和 CI workflow
6. 运行语法检查、smoke test 和 E2E test

### Review

- 已停止上轮本地测试遗留的 `127.0.0.1:18089` Flask 服务，端口已释放
- 已新增 `scripts/e2e_local.py`，使用临时 skills/meta 目录和 fake Codex CLI 覆盖主要 Flask 路由，不启动端口、不调用真实模型、不污染真实 skill
- 已新增 `LICENSE`，当前采用 MIT License
- 已新增 `SECURITY.md`，明确无认证、本地优先、写回风险、密钥和公网暴露边界
- 已新增 `CONTRIBUTING.md`，说明开发环境、验证命令、改动范围和安全规则
- 已将 `app.py`、`scripts/deploy.sh`、`.env.example` 的默认监听地址改为 `127.0.0.1`
- 已更新 README、用户指南和 GitHub Actions workflow，把 `scripts/e2e_local.py` 纳入标准验证
- 已通过 `python3 -m py_compile app.py scripts/smoke_local.py scripts/e2e_local.py`
- 已通过 `bash -n scripts/deploy.sh`
- 已通过 `./.venv/bin/python scripts/smoke_local.py`
- 已通过 `./.venv/bin/python scripts/e2e_local.py`

## 2026-06-10 Skillfully-style 本地反馈采集闭环

1. 复查现有元数据、写保护、Diff、页面内 modal 和测试脚本
2. 新增本地反馈配置、snippet 生成、安装 Diff 与写保护确认
3. 新增 agent 自动回传反馈接口和外置 `feedback.jsonl`
4. 在 skill 详情页展示反馈采集状态、安装动作和最近反馈
5. 扩展 smoke/E2E 覆盖反馈配置、安装、回传、读取和重复安装
6. 更新 README、用户指南和本 TODO review

### Review

- 已新增 `POST /api/feedback/runs`，支持 agent 按 token/install_id 回传 `positive/neutral/negative` 结构化反馈
- 已新增 `GET/POST /api/skills/<skill_id>/feedback/config`、`POST /api/skills/<skill_id>/feedback/install` 和 `GET /api/skills/<skill_id>/feedback`
- 反馈配置写入外置 `meta.json`，运行反馈写入外置 `feedback.jsonl`，不污染被管理 skill 目录
- feedback snippet 带 `skills-manager-feedback` 稳定标记，重复安装会替换原片段，不重复追加
- 写保护 skill 安装 snippet 时复用 `confirm_write` 和页面内确认 modal，安装前保存 `pre-feedback-install` 快照
- skill 详情页已增加 `反馈采集` 区域，支持启用、查看 snippet、查看安装 Diff、安装到 `SKILL.md` 和展示最近反馈
- 已更新 `.env.example`、README 和用户指南，补充 `SKILLS_MANAGER_PUBLIC_URL` 与本地反馈采集说明
- 已通过 `python3 -m py_compile app.py scripts/smoke_local.py scripts/e2e_local.py`
- 已通过 `bash -n scripts/deploy.sh`
- 已通过 `./.venv/bin/python scripts/smoke_local.py`
- 已通过 `./.venv/bin/python scripts/e2e_local.py`
- 已通过 `git diff --check`
- 已用临时 skills/meta 目录启动本地服务并完成浏览器验证：反馈区初始状态、启用、snippet 预览、安装 Diff、写保护确认、安装后状态和最近反馈列表均正常，浏览器 console 无 error/warn
- 最终复验已确认安装入口收敛为先查看 Diff，再从 Diff 区确认安装，避免绕过安装前审查
