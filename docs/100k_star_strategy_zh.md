# 100k Star 开源策略

这份文档是 Domain AI Forge 的增长打法。目标不是“把代码上传 GitHub”，而是把项目做成一个开发者愿意收藏、转发、贡献、二次开发的开源基础设施。

## 核心定位

不要把项目定位成“又一个 agent 框架”。这个赛道已经拥挤。

更强的定位是：

> 垂域 AI 系统优化框架：用 model + harness + multi-agent，把 AI 应用从 demo 推到可评测系统。

这个定位有三个好处：

- 比 agent 框架更高一层，避开红海
- 能同时吸引 founder、AI engineer、domain expert
- 能自然形成 domain pack 生态

## 项目名字和口号

当前建议：

- 项目名：Domain AI Forge
- 口号：From demo prompts to measurable vertical AI systems.
- 中文口号：从 demo prompt 到可评测的垂域 AI 系统。

## 100k Star 的四类用户

### 1. AI 工程师

他们关心：

- 能不能跑
- API 是否清楚
- 能不能接自己的模型
- 能不能证明 agent workflow 真的更好

项目要给他们：

- 3 分钟 demo
- 清晰 adapter 接口
- scoring harness
- benchmark report

### 2. 创业者和产品负责人

他们关心：

- 我的垂域 AI 怎么从 demo 变产品
- 怎么判断模型升级是否值得
- 怎么把业务专家经验变成系统资产

项目要给他们：

- 框架图
- 成熟度模型
- 行业 case
- 产品化 playbook

### 3. 研究者

他们关心：

- benchmark 是否可复现
- scorer 是否透明
- 多 agent 是否能量化比较

项目要给他们：

- 固定 case format
- 可复现 run report
- leaderboard
- 论文/技术报告式文档

### 4. 社区贡献者

他们关心：

- 我能贡献什么
- 贡献是否足够小
- 是否能被项目承认

项目要给他们：

- domain pack issue template
- good first issue
- contributor highlight
- domain pack registry

## 内容发布路线

### 第一波：概念发布

标题方向：

- We need harness-first vertical AI, not more agent demos
- The missing optimization loop for domain AI
- 垂域 AI 不缺 demo，缺的是 harness

核心内容：

- 解释 model + harness + multi-agent
- 展示 baseline vs multi-agent 的得分对比
- 强调不需要 API key 就能跑

### 第二波：行业案例

每个行业写一篇：

- Customer Support AI: from prompt to harness
- Legal Intake AI: how to evaluate risk before launch
- Sales Qualification AI: measuring follow-up quality

每篇都配一个 domain pack。

### 第三波：benchmark

发布：

- Domain AI Forge Benchmark v0.1
- 10 个垂域
- 每个垂域 20 到 100 个 case
- baseline / single model / multi-agent / RAG-agent 对比

## GitHub 首页要做到什么

README 第一屏必须回答：

- 这是什么
- 为什么现在需要
- 怎么 3 分钟跑起来
- 和普通 agent 框架有什么不同
- 我能贡献什么

推荐仓库 topics：

```text
ai
agents
llm
evaluation
multi-agent
vertical-ai
domain-ai
ai-testing
harness
benchmark
```

## 贡献机制

贡献入口要分层：

- 小贡献：scorer、case、README 修正
- 中贡献：domain pack、adapter、report exporter
- 大贡献：benchmark、registry、leaderboard

每个 domain pack 应包含：

- 领域说明
- 任务类型
- 5 到 100 个 case
- 关键词/禁词/rubric
- 风险说明

## 里程碑

### v0.1

- 核心接口
- demo
- harness
- multi-agent
- JSONL case loader
- README 和 CI

### v0.2

- domain pack loader
- report export
- OpenAI-compatible adapter
- LLM-as-judge scorer

### v0.3

- 5 个 domain pack
- benchmark report
- adapter registry

### v1.0

- 20 个 domain pack
- 稳定 API
- leaderboard
- 社区维护流程

## 最重要的判断标准

这个项目要持续问一个问题：

> 用户是不是因为这个项目，第一次清楚地知道自己的垂域 AI 应该如何评测和迭代？

如果答案是 yes，star 会跟着来。

