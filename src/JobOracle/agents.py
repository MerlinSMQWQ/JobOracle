from __future__ import annotations

from .llm_client import EmploymentLLMClient
from .models import EmploymentRequest, EmploymentSearchResult
from .profile import summarize_profile
from .prompts import (
    ADVISOR_SYSTEM_PROMPT,
    ANALYST_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    build_advisor_prompt,
    build_analyst_prompt,
    build_researcher_prompt,
)


class ResearcherAgent:
    def __init__(self, llm_client: EmploymentLLMClient):
        self.llm_client = llm_client

    def run(self, request: EmploymentRequest, mode: str, results: list[EmploymentSearchResult]) -> tuple[str, bool]:
        try:
            return (
                self.llm_client.generate_text(
                    RESEARCHER_SYSTEM_PROMPT,
                    build_researcher_prompt(request, mode, results),
                    temperature=0.2,
                ),
                True,
            )
        except Exception:
            return self._fallback(request, mode, results), False

    def _fallback(self, request: EmploymentRequest, mode: str, results: list[EmploymentSearchResult]) -> str:
        education = _infer_education_level(request)
        role_tracks = _infer_role_tracks(request)
        lines = [
            "## 研究员笔记",
            "",
            f"- 场景模式：{mode}",
            f"- 检索证据数：{len(results)}",
            f"- 识别到的学历层级：{education}",
            f"- 拆分后的岗位方向：{', '.join(role_tracks)}",
        ]
        if results:
            lines.append("- 当前证据主要集中在以下主题：")
            for item in results[:5]:
                lines.append(f"  - {item.title}: {item.snippet}")
        else:
            lines.append("- 当前没有外部检索证据，只能基于问题本身做初步判断。")
        if request.profile:
            lines.append(f"- 已提供用户画像字段：{', '.join(sorted(request.profile.keys()))}")
            lines.append(f"- 用户画像摘要：{summarize_profile(request.profile)}")
        lines.append("- 本轮检索已尝试补充中厂、小厂、民营公司和更现实的就业入口。")
        if education == "本科":
            lines.append("- 对本科学历来说，更现实的分层通常是：冲刺少量大厂，同时重点布局中厂、区域龙头和业务清晰的小厂。")
        elif education == "专科":
            lines.append("- 对专科学历来说，优先寻找技能要求明确、业务急需执行力的中小厂岗位，通常比盯大厂更有效。")
        elif education in {"硕士", "博士"}:
            lines.append("- 对研究生学历来说，可以保留更高门槛岗位，但仍需同步覆盖中厂和技术导向团队，避免只押注头部公司。")
        lines.append("- 仍需重点核实：岗位持续招聘情况、技能要求是否一致、企业稳定性。")
        return "\n".join(lines)


class AnalystAgent:
    def __init__(self, llm_client: EmploymentLLMClient):
        self.llm_client = llm_client

    def run(
        self,
        request: EmploymentRequest,
        mode: str,
        researcher_note: str,
        results: list[EmploymentSearchResult],
    ) -> tuple[str, bool]:
        try:
            return (
                self.llm_client.generate_text(
                    ANALYST_SYSTEM_PROMPT,
                    build_analyst_prompt(request, mode, researcher_note, results),
                    temperature=0.25,
                ),
                True,
            )
        except Exception:
            return self._fallback(request, mode, researcher_note, results), False

    def _fallback(
        self,
        request: EmploymentRequest,
        mode: str,
        researcher_note: str,
        results: list[EmploymentSearchResult],
    ) -> str:
        education = _infer_education_level(request)
        role_tracks = _infer_role_tracks(request)
        demand = "中等"
        competition = "中等"
        if any(token in request.query for token in ("AI", "ai", "算法", "大模型", "产品")):
            competition = "较高"
        if any(token in request.query for token in ("深圳", "上海", "杭州", "北京")):
            demand = "较高"
        company_tier_lines = _company_tier_assessment(request, education)
        lines = [
            "## 分析师判断",
            "",
            f"- 总体判断：围绕“{request.query}”的就业判断需要把需求热度和个人匹配度分开看。",
            f"- 学历分层：{education}",
            f"- 需求热度：{demand}",
            f"- 竞争强度：{competition}",
            f"- 更具体的岗位切口：{', '.join(role_tracks)}",
            "- 技能门槛：建议优先以真实 JD 高频技能为准，而不是只看经验帖。",
            "- 风险信号：热门方向容易出现叙事过热、岗位名称泛化、经验要求上移等问题。",
        ]
        if request.profile:
            lines.append(f"- 用户画像摘要：{summarize_profile(request.profile)}")
        lines.extend(company_tier_lines)
        if mode == "guidance":
            lines.append("- 指导补充：应优先确定主投岗位，再围绕该岗位准备简历、项目和面试故事。")
            lines.append(f"- 更现实的投递顺序：{_guidance_priority_by_education(education)}")
        if results:
            lines.append(f"- 证据基础：本轮共参考 {len(results)} 条检索结果。")
        else:
            lines.append("- 证据基础：当前主要依赖本地规则推断，结论置信度有限。")
        lines.append("")
        lines.append("### 研究员原始笔记摘要")
        lines.append(researcher_note)
        return "\n".join(lines)


class AdvisorAgent:
    def __init__(self, llm_client: EmploymentLLMClient):
        self.llm_client = llm_client

    def run(
        self,
        request: EmploymentRequest,
        mode: str,
        researcher_note: str,
        analyst_note: str,
        results: list[EmploymentSearchResult],
    ) -> tuple[str, bool]:
        try:
            return (
                self.llm_client.generate_markdown(
                    ADVISOR_SYSTEM_PROMPT,
                    build_advisor_prompt(request, mode, researcher_note, analyst_note, results),
                ),
                True,
            )
        except Exception:
            return self._fallback(request, mode, researcher_note, analyst_note, results), False

    def _fallback(
        self,
        request: EmploymentRequest,
        mode: str,
        researcher_note: str,
        analyst_note: str,
        results: list[EmploymentSearchResult],
    ) -> str:
        education = _infer_education_level(request)
        role_tracks = _infer_role_tracks(request)
        title = f"{request.query} - {'就业指导报告' if mode == 'guidance' else '就业行情分析报告'}"
        lines = [
            f"# {title}",
            "",
            "> 说明：当前报告由轻量三角色流程生成。若外部搜索或 LLM 不可用，部分内容会退回本地规则推断。",
            "",
            "## 一、摘要结论",
            "",
            f"- 本次问题归类为：{mode}",
            "- 当前建议不要只看单一岗位热度，而要同时判断岗位需求、个人匹配和企业稳定性。",
            f"- 用户画像摘要：{summarize_profile(request.profile)}",
            "",
            "## 二、用户画像解读",
            "",
            f"- 画像概览：{summarize_profile(request.profile)}",
            "",
            "## 三、Researcher 检索摘要",
            "",
            researcher_note,
            "",
            "## 四、Analyst 结构化判断",
            "",
            analyst_note,
            "",
            "## 五、公司层级建议",
            "",
            f"- 学历识别：{education}",
            f"- 建议优先尝试的细分岗位：{', '.join(role_tracks)}",
            f"- 更建议重点关注：{_company_focus_by_education(education, request.query)}",
            f"- 不建议的默认策略：{_avoidance_note_by_education(education)}",
            "",
            "## 六、Advisor 建议",
            "",
        ]
        if mode == "guidance":
            lines.extend(
                [
                    f"- 先把目标岗位收敛到 1 到 2 类，并且优先选与你当前学历更匹配的公司层级：{_company_focus_by_education(education, request.query)}。",
                    f"- 在岗位选择上，不要只投一个大类，建议优先从这些更具体的岗位切口切入：{_guidance_track_suggestion(role_tracks)}。",
                    "- 用真实 JD 倒推能力缺口，优先补最常见、最可证明的技能，不要只做泛项目。",
                    "- 投递时不要把大厂当主战场，应把更高成功率的中厂、小厂和业务明确团队放到前排。",
                    f"- 对当前学历更现实的顺序是：{_guidance_priority_by_education(education)}",
                ]
            )
        else:
            lines.extend(
                [
                    "- 判断行情时优先看持续招聘、技能要求稳定性和企业业务方向，不要被大厂叙事带偏。",
                    f"- 观察行情时，不要只看一个大岗位名，建议拆开看：{', '.join(role_tracks)}。",
                    "- 比较城市时不要只看薪资，还要看中厂、小厂数量、岗位密度、企业质量和竞争人数。",
                    "- 对热门岗位保持警惕，很多热度来自内容平台讨论，不一定对应真实需求，尤其不一定对应普通学历候选人的真实机会。",
                ]
            )
        lines.extend(
            [
                "",
                "## 七、30 天行动计划",
                "",
                f"- 第 1 周：围绕 {', '.join(role_tracks[:3])} 收集 20 到 30 个真实 JD，统计高频技能和经验要求。",
                f"- 第 2 周：优先挑选适合 {education} 学历切入的公司层级，调整简历和项目表达。",
                "- 第 3 周：先投一轮中厂和小厂，再少量冲刺高门槛公司，并记录反馈、面试题和拒绝原因。",
                "- 第 4 周：根据反馈优化岗位选择、公司层级和投递策略。",
                "",
                "## 八、参考证据",
                "",
            ]
        )
        if results:
            for idx, item in enumerate(results[:8], start=1):
                source_label = _source_label(item.source)
                target_url = item.url or "#"
                lines.append(f"- {idx}. [{item.title}]({target_url})")
                lines.append(f"  - 数据源：{source_label}")
                lines.append(f"  - 查询：{item.query}")
                if item.published_date:
                    lines.append(f"  - 发布时间：{item.published_date}")
                if item.source == "offerstar":
                    lines.append(f"  - 招聘汇总页链接：{target_url}")
                lines.append(f"  - 摘要：{item.snippet}")
        else:
            lines.append("- 当前无外部检索结果，报告主要基于本地规则推断。")
        return "\n".join(lines)


def _infer_education_level(request: EmploymentRequest) -> str:
    joined = f"{request.query} {request.profile}".lower()
    if "博士" in joined:
        return "博士"
    if "硕士" in joined or "研究生" in joined:
        return "硕士"
    if "本科" in joined:
        return "本科"
    if "专科" in joined or "大专" in joined:
        return "专科"
    if "中专" in joined:
        return "中专"
    return "未说明"


def _company_tier_assessment(request: EmploymentRequest, education: str) -> list[str]:
    role = request.query
    if education == "本科":
        return [
            "- 大厂：可以少量冲刺，但不适合当成唯一主线，除非你有强实习、强项目或很硬的学校背景。",
            "- 中厂：通常是更值得重点布局的层级，要求没有大厂那么整齐划一，但很看重能否快速上手。",
            f"- 小厂：如果岗位是 {role} 这类偏执行和业务结合的方向，小厂可能更愿意给机会，但要更重视业务稳定性。",
        ]
    if education == "专科":
        return [
            "- 大厂：通常不应作为主要目标，投入产出比偏低。",
            "- 中厂：应作为重点目标，尤其是业务明确、团队缺人、强调落地的岗位。",
            "- 小厂：更可能提供第一份相关经验，但必须筛掉流程混乱、培养弱、业务不稳的公司。",
        ]
    if education in {"硕士", "博士"}:
        return [
            "- 大厂：可以保留一定比例冲刺，尤其是算法、研究和数据方向。",
            "- 中厂：不应忽视，很多中厂对高学历也有需求，而且上手空间更大。",
            "- 小厂：如果方向匹配且业务扎实，也可能比头部公司提供更快的成长速度。",
        ]
    return [
        "- 大厂：不建议默认作为唯一目标，应看个人经历和岗位要求是否匹配。",
        "- 中厂：通常是更现实也更值得重点关注的层级。",
        "- 小厂：适合补第一份相关经历，但要严格筛选公司质量。",
    ]


def _guidance_priority_by_education(education: str) -> str:
    if education == "本科":
        return "中厂主投 -> 小厂保底与练手 -> 少量冲刺大厂"
    if education == "专科":
        return "中小厂主投 -> 区域龙头和业务稳定公司 -> 谨慎少量尝试高门槛岗位"
    if education in {"硕士", "博士"}:
        return "大厂与优质中厂并行 -> 技术导向团队优先 -> 小厂作为补充选择"
    return "中厂主投 -> 小厂补充 -> 大厂谨慎冲刺"


def _company_focus_by_education(education: str, query: str) -> str:
    if education == "本科":
        return f"中厂、区域龙头、业务稳定的民营公司，以及少量与你的 {query} 方向高度匹配的大厂岗位"
    if education == "专科":
        return f"中小厂、区域公司、对实际技能要求明确的 {query} 相关岗位"
    if education in {"硕士", "博士"}:
        return f"技术导向的大厂团队、优质中厂和与 {query} 强相关的成长型公司"
    return f"中厂、小厂和业务清晰的 {query} 相关团队"


def _avoidance_note_by_education(education: str) -> str:
    if education == "本科":
        return "不要把全部精力都押在大厂校招或高热度岗位上"
    if education == "专科":
        return "不要默认和头部学历背景候选人走同一竞争路径"
    if education in {"硕士", "博士"}:
        return "不要只盯头部公司，忽视更容易获得成长空间的中厂"
    return "不要只跟着热度投递，而忽视成功率更高的岗位层级"


def _source_label(source: str) -> str:
    if source == "offerstar":
        return "招聘汇总页"
    if source == "tavily":
        return "网络搜索结果"
    if source == "local_fallback":
        return "本地分析证据"
    return "外部公开资料"


def _infer_role_tracks(request: EmploymentRequest) -> list[str]:
    question = request.query
    lower = question.lower()
    tracks: list[str] = []
    if "数据分析" in question:
        tracks.extend(["业务数据分析", "BI数据分析", "增长分析"])
    if "算法" in question or "大模型" in question or "ai" in lower:
        tracks.extend(["算法工程师", "AI应用工程师", "机器学习工程师"])
    if "产品" in question:
        tracks.extend(["B端产品经理", "数据产品经理", "增长产品经理"])
    if "运营" in question:
        tracks.extend(["用户运营", "增长运营", "内容运营"])
    if "开发" in question or "后端" in question or "前端" in question:
        tracks.extend(["后端开发", "前端开发", "测试开发"])
    if not tracks:
        tracks.extend(["目标岗位", "相关执行岗", "相关支持岗"])
    deduped: list[str] = []
    for item in tracks:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _guidance_track_suggestion(role_tracks: list[str]) -> str:
    if not role_tracks:
        return "先拆出 2 到 3 个更具体的岗位方向"
    if len(role_tracks) == 1:
        return role_tracks[0]
    return "、".join(role_tracks[:3])
