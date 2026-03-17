<div align="center">
    <img src="assets/joboracle-logo.svg" width="55%" alt="JobOracle logo" />
</div>

# JobOracle

`JobOracle` 是一个轻量的就业分析工具：输入一个就业问题，可选附带用户画像，系统先做检索，再经过 `Researcher / Analyst / Advisor` 三个角色协作，最后产出一份 Markdown 报告。

当前代码采用标准 `src` 布局，核心实现位于 [`src/JobOracle`](/Users/a1234/WorkingSpace/python/JobOracle/src/JobOracle)。

## 功能概览

- 就业行情分析
- 求职指导建议
- 城市机会对比
- OfferStar 岗位汇总页辅助检索
- Markdown 报告输出
- 无外部搜索或 LLM 时自动降级到本地规则模式

## 项目结构

```text
JobOracle/
├── src/JobOracle/        # 核心实现
├── reports/              # 生成的 Markdown 报告
├── jobs_dataset/         # OfferStar 抓取快照（CSV / JSON）
├── .env.example          # 环境变量示例
└── pyproject.toml
```

根目录还保留了兼容入口，所以现有的一些导入方式和运行方式仍然可以使用。

## 安装依赖

推荐使用 `uv`：

```bash
uv sync
```

如果你更习惯 `pip`，也可以：

```bash
pip install -e .
```

## 配置

默认读取项目根目录下的 `.env`。可以先从 [`.env.example`](.env.example) 复制一份。

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

代码也兼容这些旧变量名：

- `REPORT_ENGINE_API_KEY`
- `REPORT_ENGINE_BASE_URL`
- `REPORT_ENGINE_MODEL_NAME`
- `QUERY_ENGINE_API_KEY`
- `QUERY_ENGINE_BASE_URL`
- `QUERY_ENGINE_MODEL_NAME`
- `OPENAI_API_KEY`
- `TAVILY_API_KEY`

## 快速开始

推荐运行方式：

```bash
uv run src/JobOracle/cli.py "2026 年杭州算法岗就业行情如何"
```

如果你已经执行过 `pip install -e .`，也可以按包方式运行：

```bash
python -m JobOracle.cli "2026 年杭州算法岗就业行情如何"
```

CLI 默认会输出中间过程，包括：

- 分析模式
- 检索查询规划
- 检索结果数量
- OfferStar 抓取进度
- Researcher / Analyst / Advisor 阶段状态
- 最终报告保存位置

求职指导示例：

```bash
uv run src/JobOracle/cli.py "我是统计学本科，想去深圳找数据分析工作，应该怎么准备" --mode guidance
```

带用户画像：

```bash
uv run src/JobOracle/cli.py "我适合投什么数据岗位" \
  --mode guidance \
  --profile-json '{"education":"本科","school":"江西财经大学","major":"统计学","target_cities":["深圳","广州"],"target_roles":["数据分析","商业分析"],"skills":["Python","SQL","Tableau"],"internship":"电商运营实习","projects":["用户增长分析项目"],"preferred_industries":["互联网","消费"]}'
```

也可以把画像写进 JSON 文件，再通过 `--profile-file` 传入：

```bash
uv run src/JobOracle/cli.py "我适合投什么数据岗位" \
  --mode guidance \
  --profile-file profile.json
```

当前推荐的用户画像字段：

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

其中列表字段支持数组，也支持用逗号分隔的字符串；代码会自动标准化。

只看最终输出，不显示中间进度：

```bash
uv run src/JobOracle/cli.py "2026 年杭州算法岗就业行情如何" --quiet
```

## OfferStar 集成

如果希望在分析时顺带调用 OfferStar 公开岗位汇总数据：

```bash
uv run src/JobOracle/cli.py "我是武汉大学计算机毕业生，当前准备在武汉找工作，有什么建议吗" \
  --mode guidance \
  --use-offerstar \
  --offerstar-from-page 1 \
  --offerstar-to-page 5 \
  --offerstar-max-items 60
```

当开启 `--use-offerstar` 时，抓取快照会自动保存到：

- [`jobs_dataset/`](/Users/a1234/WorkingSpace/python/JobOracle/jobs_dataset)

当前 OfferStar 抓取逻辑说明：

- 支持页码范围抓取
- 如果范围中包含第 `1` 页，会优先抓第 `1` 页
- 后续页码会随机打乱顺序，避免总是只吃到前几页公司
- 当问题中只出现一个城市时，会带上城市筛选
- 当问题中出现多个可接受城市时，不会强行缩成单个城市筛选
- 当前分页参数按 `current=<页码>&pageSize=20` 构造

也可以单独抓取 OfferStar：

```bash
uv run src/JobOracle/cli.py crawl-offerstar \
  --question "深圳 算法岗 华为 人工智能" \
  --from-page 1 \
  --to-page 5 \
  --max-items 100
```

或手动指定筛选项：

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

## 内部流程

系统不是单次 LLM 直接输出，而是一个轻量三角色流程：

1. `Researcher`
   负责信息检索和证据整理。
2. `Analyst`
   负责把证据转成结构化判断。
3. `Advisor`
   负责生成最终就业分析和行动建议。

检索层会优先尝试外部搜索和 OfferStar；如果外部能力不可用，则自动回退到本地推断证据，保证流程仍然可运行。

系统也会尽量把宽泛岗位进一步拆分成更接近真实投递场景的细分方向，例如：

- `数据分析` -> `业务数据分析 / BI数据分析 / 增长分析`
- `算法` -> `算法工程师 / AI应用工程师 / 机器学习工程师`
- `产品` -> `B端产品经理 / 数据产品经理 / 增长产品经理`

## 无 API 时能运行吗

可以。

如果没有可用的 LLM 配置，或者外部网络暂时不可用，系统会自动退回本地规则模式。此时依然会执行：

- 查询词规划
- 轻量证据生成
- 三角色协作
- Markdown 报告输出

## 设计原则

- 小而独立
- 面向命令行优先
- 不依赖复杂任务编排
- 先保证闭环，再逐步增强效果
