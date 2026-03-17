# JobOracle

`JobOracle/` 是一个和主项目解耦的轻量就业分析工具。

它刻意不复用 BettaFish 那套较重的前后端、任务流、SSE、报告引擎，只保留一个最短闭环：

- 输入一个就业问题
- 可选输入用户画像
- 先做信息检索
- 再走轻量三角色协作
- 最后生成一份 Markdown 报告
- 默认保存到 `JobOracle/reports/`

## 当前内部流程

这个版本已经不是单个 LLM 直接输出，而是一个轻量的多角色流程：

1. `Researcher`
   负责信息检索和证据整理
2. `Analyst`
   负责把检索结果转成结构化判断
3. `Advisor`
   负责给出最终就业分析和行动建议

检索层参考了原项目 `QueryEngine/tools/search.py` 的思路：

- 把搜索封装成轻量工具层
- 先生成多条查询词
- 聚合搜索结果
- 把检索证据传给后续角色

如果配置了 `TAVILY_API_KEY` 或 `EMPLOYMENT_SEARCH_API_KEY`，会优先使用真实搜索。
如果搜索不可用，会自动退回本地证据模式，保证整体流程仍然可跑。

此外，系统现在会尽量把宽泛岗位拆成更具体的切口再分析，例如：

- `数据分析` -> `业务数据分析 / BI数据分析 / 增长分析`
- `算法` -> `算法工程师 / AI应用工程师 / 机器学习工程师`
- `产品` -> `B端产品经理 / 数据产品经理 / 增长产品经理`

这样报告会更接近真实投递和真实岗位筛选，而不是停留在很泛的大类概念上。

## 适合的场景

- 就业行情分析
- 岗位方向判断
- 城市机会对比
- 初步求职指导
- 转行准备建议

## 快速使用

在项目根目录运行：

```bash
python -m JobOracle.cli "2026 年杭州算法岗就业行情如何"
```

默认 CLI 会显示运行中间过程，包括：

- 当前分析模式
- 检索查询规划
- 检索结果数量
- Researcher / Analyst / Advisor 的阶段完成情况
- 最终保存位置

求职指导示例：

```bash
python -m JobOracle.cli "我是统计学本科，想去深圳找数据分析工作，应该怎么准备" --mode guidance
```

如果希望在分析时顺带调用 OfferStar 公开岗位汇总数据：

```bash
python -m JobOracle.cli "我是武汉大学计算机毕业生，当前准备在武汉找工作，有什么建议吗" \
  --mode guidance \
  --use-offerstar \
  --offerstar-from-page 1 \
  --offerstar-to-page 2 \
  --offerstar-max-items 20
```

当你在主分析流程里开启 `--use-offerstar` 时，抓到的岗位快照也会自动保存到：

- `JobOracle/jobs_dataset/`

带用户画像：

```bash
python -m JobOracle.cli "我适合投什么数据岗位" \
  --mode guidance \
  --profile-json '{"education":"统计学本科","internship":"电商运营实习","skills":["Python","SQL","Tableau"]}'
```

如果你只想保留最终输出，不看中间进度：

```bash
python -m JobOracle.cli "2026 年杭州算法岗就业行情如何" --quiet
```

抓取 OfferStar 公开岗位汇总页：

```bash
python -m JobOracle.cli crawl-offerstar \
  --question "深圳 算法岗 华为 人工智能" \
  --from-page 1 \
  --to-page 5 \
  --max-items 100
```

也可以手动指定筛选项：

```bash
python -m JobOracle.cli crawl-offerstar \
  --industry "人工智能" \
  --work-location "深圳" \
  --company "华为" \
  --positions "算法" \
  --from-page 1 \
  --to-page 5 \
  --max-items 100
```

## 配置方式

默认会读取项目根目录 `.env`。

如果把 `JobOracle` 单独拆出去，建议直接使用：

- [JobOracle/.env.example](/Users/a1234/WorkingSpace/python/BettaFish/JobOracle/.env.example)

优先读取这些变量：

- `EMPLOYMENT_API_KEY`
- `EMPLOYMENT_BASE_URL`
- `EMPLOYMENT_MODEL_NAME`

如果没配，会自动回退到：

- `REPORT_ENGINE_API_KEY`
- `REPORT_ENGINE_BASE_URL`
- `REPORT_ENGINE_MODEL_NAME`

再回退到：

- `QUERY_ENGINE_API_KEY`
- `QUERY_ENGINE_BASE_URL`
- `QUERY_ENGINE_MODEL_NAME`

搜索优先读取：

- `EMPLOYMENT_SEARCH_API_KEY`
- `TAVILY_API_KEY`

可选配置：

- `EMPLOYMENT_SEARCH_PROVIDER`
- `EMPLOYMENT_MAX_SEARCH_RESULTS`
- `EMPLOYMENT_SEARCH_TIMEOUT_SECONDS`

## 依赖安装

最小依赖写在：

- [JobOracle/requirements.txt](/Users/a1234/WorkingSpace/python/BettaFish/JobOracle/requirements.txt)

安装方式：

```bash
pip install -r JobOracle/requirements.txt
```

## OfferStar 低频采集说明

`crawl-offerstar` 是一个保守型采集器，设计目标是：

- 只抓公开列表页
- 用户自己决定抓多少页、最多保留多少条
- 默认按低频方式抓取
- 每次抓完都落地到本地 `csv/json`

安全策略：

- 默认按“约 10 秒 20 条”的目标速率控制
- 可以用 `--target-rows-per-10s` 调得更慢
- 建议优先做低频同步，不要把它做成用户每问一次就实时全站抓取

默认输出目录：

- `JobOracle/jobs_dataset/`

## 没有 API 也能运行吗

可以。

如果没有可用的 LLM 配置，或外部网络暂时不可用，工具会自动退回本地规则模式。

此时依然会执行：

- 查询词规划
- 轻量检索证据生成
- 三角色协作
- Markdown 报告输出

## 当前设计原则

- 小而独立
- 不绑定主站
- 不启动 Flask / Streamlit
- 不依赖复杂任务编排
- 先解决“够用”，再考虑“完备”
