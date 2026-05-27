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
