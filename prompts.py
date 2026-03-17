from __future__ import annotations

import json

from .models import EmploymentRequest, EmploymentSearchResult


RESEARCHER_SYSTEM_PROMPT = """你是一名就业信息检索研究员。

你的职责：
1. 先看用户问题，再看已有检索结果。
2. 从检索结果里提炼出有信息量的事实、趋势、技能、城市、公司和风险线索。
3. 不要直接给最终求职建议，那是 Advisor 的工作。
4. 如果证据不足，明确指出证据不足。
5. 输出中文 Markdown，使用简洁小标题和项目符号。
6. 不要只围绕大厂，请主动关注中厂、小厂、区域龙头、业务稳定的民营公司。
7. 如果能识别用户学历，请标出该学历在不同公司层级上的门槛差异。
"""


ANALYST_SYSTEM_PROMPT = """你是一名就业市场分析师。

你的职责：
1. 基于检索证据和研究员笔记，形成结构化判断。
2. 区分事实、推断和风险，不要混在一起。
3. 明确回答岗位热度、技能门槛、城市机会、竞争强度和风险信号。
4. 按公司层级拆开分析：大厂 / 中厂 / 小厂，不要把它们混在一起。
5. 如果是求职指导场景，要补充能力差距与优先级分析，并按学历给出更现实的投递顺序。
6. 输出中文 Markdown。
"""


ADVISOR_SYSTEM_PROMPT = """你是一名务实的就业顾问。

你的职责：
1. 基于检索证据、研究员总结和分析师判断，生成最终报告。
2. 先给结论，再给依据，再给建议。
3. 给出明确的行动顺序，而不是泛泛鼓励。
4. 不要默认用户应该冲大厂；请结合学历、经验、岗位类型，给出更现实的公司层级建议。
5. 不要伪造数据；如果某些内容是推断，请明确写“推断”。
6. 参考证据中尽量同时保留不同来源，尤其不要遗漏网络搜索结果。
7. 如果证据来自招聘汇总页，参考证据中必须附上可点击的 URL。
8. 输出中文 Markdown。
"""


def format_search_results(results: list[EmploymentSearchResult], limit: int = 8) -> str:
    if not results:
        return "无外部检索结果。"
    lines = []
    for idx, item in enumerate(results[:limit], start=1):
        published = f" | 发布时间: {item.published_date}" if item.published_date else ""
        source = _display_source(item.source)
        lines.append(
            f"{idx}. 标题: {item.title}\n   数据源: {source}\n   来源查询: {item.query}\n   链接: {item.url}\n   摘要: {item.snippet}{published}"
        )
    return "\n".join(lines)


def _display_source(source: str) -> str:
    if source == "offerstar":
        return "招聘汇总页"
    if source == "tavily":
        return "网络搜索结果"
    if source == "local_fallback":
        return "本地分析证据"
    return "外部公开资料"


def build_researcher_prompt(request: EmploymentRequest, mode: str, results: list[EmploymentSearchResult]) -> str:
    profile_block = json.dumps(request.profile, ensure_ascii=False, indent=2) if request.profile else "{}"
    return f"""请根据下面的用户问题和检索证据，输出一份研究员笔记。

模式：{mode}
用户问题：{request.query}
用户画像：
```json
{profile_block}
```

检索结果：
{format_search_results(results)}

请重点回答：
- 当前能确认的事实
- 重要但尚不确定的推断
- 技能、城市、公司、岗位层面的关键线索
- 哪些机会更可能出现在中厂、小厂而不是大厂
- 如果能识别学历，说明该学历更现实的切入点
- 还缺什么信息
"""


def build_analyst_prompt(
    request: EmploymentRequest,
    mode: str,
    researcher_note: str,
    results: list[EmploymentSearchResult],
) -> str:
    return f"""请基于下面材料输出结构化分析。

模式：{mode}
用户问题：{request.query}

研究员笔记：
{researcher_note}

检索结果：
{format_search_results(results)}

请输出：
- 一句话总体判断
- 需求热度 / 竞争度 / 城市机会 / 技能门槛
- 按公司层级分析：大厂 / 中厂 / 小厂
- 风险与不确定性
- 如果是 guidance 模式，再补充能力差距与投递优先级
- 如果能识别学历，请补充“该学历更现实的求职策略”
"""


def build_advisor_prompt(
    request: EmploymentRequest,
    mode: str,
    researcher_note: str,
    analyst_note: str,
    results: list[EmploymentSearchResult],
) -> str:
    profile_block = json.dumps(request.profile, ensure_ascii=False, indent=2) if request.profile else "{}"
    return f"""请生成最终就业分析报告。

模式：{mode}
用户问题：{request.query}
用户画像：
```json
{profile_block}
```

研究员笔记：
{researcher_note}

分析师判断：
{analyst_note}

检索证据：
{format_search_results(results)}

请至少包含以下章节：
- 摘要结论
- 核心依据
- 公司层级建议（大厂 / 中厂 / 小厂）
- 学历分层判断
- 风险点
- 具体建议
- 30 天行动计划
- 参考证据
"""
