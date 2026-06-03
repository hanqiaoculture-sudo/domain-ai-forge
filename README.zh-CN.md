# Domain AI Forge

**面向垂域 AI 实践的 model + harness + multi-agent 整体优化框架。**

Domain AI Forge 的目标是把垂域 AI 从“能演示的 demo”推进到“可评测、可复盘、可迭代、可开源协作的系统”。

## 一句话

Domain AI Forge 用统一接口把 **模型候选方案、领域评测 harness、多 agent workflow** 放进同一个优化闭环，让每一次 prompt、模型、检索、工具或 agent 改动都能被度量。

## 为什么要做

很多垂域 AI 项目的瓶颈不是“没有更强模型”，而是：

- 没有稳定的领域回归测试集
- agent workflow 看起来复杂，但无法证明更好
- 业务专家的判断标准没有进入工程系统
- prompt、RAG、工具、模型升级都缺少统一对比
- demo 成功以后，很难变成可运营产品

所以这个项目的核心观点是：

> 垂域 AI 的护城河不是单次回答，而是持续沉淀的 harness 和围绕 harness 优化的系统能力。

## 三层框架

### 1. Model

Model 是任何能回答任务的候选系统：

- 大模型 API
- 本地模型
- RAG pipeline
- 规则 baseline
- 多 agent 系统

关键是统一接口，方便同一套 harness 做公平对比。

### 2. Harness

Harness 是垂域 AI 的领域记忆，包含：

- 真实业务 case
- 期望行为
- 关键词和禁词
- 风险检查
- rubric
- 通过阈值
- 回归用例

每次线上失败，都应该变成下一版 harness 的测试资产。

### 3. Multi-Agent Model

多 agent 不是为了“显得高级”，而是为了把真实工作职责拆开：

- Planner：拆解任务
- Domain Expert：加入领域规则
- Tool User：调用工具或检索
- Critic：检查风险和完整性
- Responder：生成最终回答

只有当 agent 能让 harness 分数提高，或者减少某类风险，它才值得存在。

## 快速运行

```bash
cd domain-ai-forge
python3 examples/customer_support/run_demo.py
```

输出示例：

```text
Domain AI Forge demo
overall_score: 0.94
pass_rate: 1.00
best_candidate: multi_agent_support_v1
```

运行测试：

```bash
python3 -m unittest discover -s tests
```

## 100k 收藏目标怎么打

100k star 不是靠“写一个框架”自然发生的，它需要产品化的开源增长路径：

- **3 分钟跑通**：不需要 API key 就能看到完整闭环
- **强概念命名**：把“垂域 AI 优化”讲成一个大家愿意引用的范式
- **Domain Pack 生态**：让贡献者可以贡献一个行业包，而不是只能改核心代码
- **Benchmark 叙事**：持续发布垂域 case 和候选系统对比
- **工程可信度**：CI、测试、贡献指南、安全说明、issue 模板一开始就齐
- **中英双语传播**：国际开发者看 README，中文市场看愿景和方法论

更完整的策略见 [docs/100k_star_strategy_zh.md](docs/100k_star_strategy_zh.md)。

## 当前状态

- 已有零依赖 Python core
- 已有 deterministic model adapter
- 已有 harness scoring
- 已有 candidate comparison
- 已有 multi-agent composition
- 已有 customer support 示例
- 已有 JSONL case loader
- 已有 GitHub CI 和贡献入口

## 下一步

- 增加 domain pack registry
- 增加 OpenAI-compatible adapter
- 增加 LLM-as-judge scorer
- 增加 Markdown / JSON / HTML report export
- 增加真实行业 benchmark
- 增加更多垂域示例

