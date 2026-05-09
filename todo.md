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
