# Skills Manager

Skills 管理与进化平台，Web 界面，本地运行。

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

## AI 分析功能

需要设置 Anthropic API Key：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

## Skill 类型分类

| 类型 | 说明 | 进化策略 |
|------|------|----------|
| 可验证型 | 输出有客观标准（代码生成、格式转换） | 自动进化，无需人工 |
| 锚点型 | 需对照人工审批样本评估 | 半自动，人工提供锚点 |
| 判断型 | 纯主观判断（内容风格类） | 只做维护，不自动进化 |
