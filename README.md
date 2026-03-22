<div align="center">
  <img src="assets/joboracle-logo.svg" width="180" alt="JobOracle logo" />

  # JobOracle

  <p><strong>面向命令行的轻量就业分析工具</strong></p>
  <p>输入就业问题，结合检索、用户画像与多角色推理，生成可落地的求职分析报告。</p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/CLI-First-1F2937?style=flat-square" alt="CLI First" />
    <img src="https://img.shields.io/badge/LLM-Multi--Agent-0F766E?style=flat-square" alt="LLM Multi-Agent" />
    <img src="https://img.shields.io/badge/Search-OfferStar%20%2B%20Tavily-C2410C?style=flat-square" alt="Search OfferStar and Tavily" />
    <img src="https://img.shields.io/badge/Layout-src-7C3AED?style=flat-square" alt="src layout" />
  </p>
</div>

---

## ✨ 概览

`JobOracle` 适合做这些事情：

- 就业行情分析
- 求职指导建议
- 城市机会对比
- OfferStar 岗位汇总页辅助检索
- Markdown 报告输出
- 无外部搜索或 LLM 时自动降级到本地规则模式

当前项目采用标准 `src` 布局，核心代码位于 [`src/JobOracle`](src/JobOracle)。

## 🧱 项目结构

```text
JobOracle/
├── assets/              # Logo 等静态资源
├── src/JobOracle/       # 核心实现
├── reports/             # 生成的 Markdown 报告
├── jobs_dataset/        # OfferStar 抓取快照（CSV / JSON）
├── .env.example         # 环境变量示例
└── pyproject.toml
```

## 🚀 安装

推荐使用 `uv`：

```bash
uv sync
```

如果你更习惯 `pip`：

```bash
pip install -e .
```

## ⚙️ 配置

默认读取项目根目录下的 `.env`。可以先参考 [`.env.example`](.env.example)。

主要变量：

- `EMPLOYMENT_API_KEY`
- `EMPLOYMENT_BASE_URL`
- `EMPLOYMENT_MODEL_NAME`
- `EMPLOYMENT_TIMEOUT_SECONDS`
- `EMPLOYMENT_REPORT_DIR`
- `EMPLOYMENT_SEARCH_API_KEY`
- `EMPLOYMENT_SEARCH_PROVIDER`
- `EMPLOYMENT_SEARCH_TIMEOUT_SECONDS`
- `EMPLOYMENT_MAX_SEARCH_RESULTS`

兼容旧变量名：

- `REPORT_ENGINE_API_KEY`
- `REPORT_ENGINE_BASE_URL`
- `REPORT_ENGINE_MODEL_NAME`
- `QUERY_ENGINE_API_KEY`
- `QUERY_ENGINE_BASE_URL`
- `QUERY_ENGINE_MODEL_NAME`
- `OPENAI_API_KEY`
- `TAVILY_API_KEY`

## 🧪 快速开始

推荐运行方式：

```bash
uv run src/JobOracle/cli.py "2026 年杭州算法岗就业行情如何"
```

如果已经执行过 `pip install -e .`，也可以：

```bash
python -m JobOracle.cli "2026 年杭州算法岗就业行情如何"
```

CLI 默认会输出这些过程信息：

- 分析模式
- 检索查询规划
- 检索结果数量
- OfferStar 抓取进度
- `Researcher / Analyst / Advisor` 阶段状态
- 最终报告保存位置

求职指导示例：

```bash
uv run src/JobOracle/cli.py "我是统计学本科，想去深圳找数据分析工作，应该怎么准备" \
  --mode guidance
```

仅输出最终结果：

```bash
uv run src/JobOracle/cli.py "2026 年杭州算法岗就业行情如何" --quiet
```

## 💬 多轮对话前端

当前项目已经提供一个临时 `Chainlit` 前端，用于验证多轮对话、记忆累积和“聊天 / 报告”两种模式。

启动方式：

```bash
uv run chainlit run src/JobOracle/ui/chainlit_app.py
```

如果你使用项目自带虚拟环境，也可以：

```bash
.venv/bin/chainlit run src/JobOracle/ui/chainlit_app.py
```

当前前端能力包括：

- 多轮聊天输入
- 会话自动维护
- 用户画像侧边展示
- 当前任务与待补充信息展示
- `生成报告`
- `导出 Markdown`
- `重置会话`

说明：

- 这是一层临时前端，目的是验证多轮交互体验。
- 核心逻辑仍然在 Python service 层，后续可以替换成其他 UI 方案。

## 👤 用户画像

JobOracle 支持通过 `--profile-json` 或 `--profile-file` 传入用户画像，并会自动做字段标准化。

推荐字段：

- `education`
- `school`
- `major`
- `graduation_year`
- `target_cities`
- `target_roles`
- `skills`
- `internship`
- `projects`
- `preferred_industries`

说明：

- 列表字段既支持 JSON 数组，也支持逗号分隔字符串。
- 支持一部分中文键名自动映射到标准字段。
- 画像会参与查询规划、提示词构建和最终报告生成。

使用 `--profile-json`：

```bash
uv run src/JobOracle/cli.py "我适合投什么数据岗位" \
  --mode guidance \
  --profile-json '{"education":"本科","school":"江西财经大学","major":"统计学","target_cities":["深圳","广州"],"target_roles":["数据分析","商业分析"],"skills":["Python","SQL","Tableau"],"internship":"电商运营实习","projects":["用户增长分析项目"],"preferred_industries":["互联网","消费"]}'
```

使用 `--profile-file`：

```bash
uv run src/JobOracle/cli.py "我适合投什么数据岗位" \
  --mode guidance \
  --profile-file profile.json
```

示例 `profile.json`：

```json
{
  "education": "本科",
  "school": "江西财经大学",
  "major": "统计学",
  "target_cities": ["深圳", "广州"],
  "target_roles": ["数据分析", "商业分析"],
  "skills": ["Python", "SQL", "Tableau"],
  "internship": "电商运营实习",
  "projects": ["用户增长分析项目"],
  "preferred_industries": ["互联网", "消费"]
}
```

## 🕸️ OfferStar 集成

如果希望在分析时顺带使用 OfferStar 公开岗位汇总数据：

```bash
uv run src/JobOracle/cli.py "我是武汉大学计算机毕业生，当前准备在武汉找工作，有什么建议吗" \
  --mode guidance \
  --use-offerstar \
  --offerstar-from-page 1 \
  --offerstar-to-page 5 \
  --offerstar-max-items 60
```

抓取快照会保存到 [`jobs_dataset/`](jobs_dataset)。

当前抓取逻辑：

- 支持页码范围抓取
- 如果范围中包含第 `1` 页，会优先抓取第 `1` 页
- 后续页码会随机打乱，避免总是只落在前几页公司
- 单城市问题会带上城市筛选
- 多城市问题不会强行缩成单城市筛选
- 当前分页参数按 `current=<页码>&pageSize=20` 构造

单独抓取 OfferStar：

```bash
uv run src/JobOracle/cli.py crawl-offerstar \
  --question "深圳 算法岗 华为 人工智能" \
  --from-page 1 \
  --to-page 5 \
  --max-items 100
```

手动指定筛选项：

```bash
uv run src/JobOracle/cli.py crawl-offerstar \
  --industry "人工智能" \
  --work-location "深圳" \
  --company "华为" \
  --positions "算法" \
  --from-page 1 \
  --to-page 5 \
  --max-items 100
```

## 🧠 内部流程

系统不是单次 LLM 直接输出，而是一个轻量三角色流程，且不依赖任何 Multi-Agent 框架：

1. `Researcher`
   负责信息检索和证据整理。
2. `Analyst`
   负责把证据转成结构化判断。
3. `Advisor`
   负责生成最终就业分析和行动建议。

检索层会优先尝试外部搜索和 OfferStar；如果外部能力不可用，则自动回退到本地推断证据。

系统也会尽量把宽泛岗位拆成更接近真实投递场景的细分方向，例如：

- `数据分析` -> `业务数据分析 / BI数据分析 / 增长分析`
- `算法` -> `算法工程师 / AI应用工程师 / 机器学习工程师`
- `产品` -> `B端产品经理 / 数据产品经理 / 增长产品经理`

## 🔌 没有 API 也能运行吗

如果没有可用的 LLM 配置，或者外部网络暂时不可用，系统会自动退回本地规则模式。此时依然会执行：

- 查询词规划
- 轻量证据生成
- 三角色协作
- Markdown 报告输出

## 🎯 设计原则

- 小而独立
- 面向命令行优先
- 不依赖复杂任务编排
- 先保证闭环，再逐步增强效果
