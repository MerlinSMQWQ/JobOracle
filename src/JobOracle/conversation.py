from __future__ import annotations

from dataclasses import dataclass, field

from .memory.models import RuntimeContext


@dataclass(slots=True)
class ConversationDecision:
    mode: str
    reply: str = ""
    follow_up_question: str = ""
    suggested_actions: list[str] = field(default_factory=list)
    should_search: bool = False
    response_style: str = "advisory"
    fallback_reply: str = ""


class ConversationPlanner:
    REPORT_TRIGGERS = ("生成报告", "输出报告", "总结成报告", "完整报告")

    def decide(self, context: RuntimeContext) -> ConversationDecision:
        latest = context.latest_user_message.strip()
        if any(trigger in latest for trigger in self.REPORT_TRIGGERS):
            return ConversationDecision(mode="report")
        follow_up_question = self._maybe_follow_up(context)
        fallback_reply = self._build_chat_reply(context)
        if context.open_questions:
            return ConversationDecision(
                mode="chat",
                reply=fallback_reply,
                follow_up_question=follow_up_question,
                suggested_actions=self._suggest_actions(context),
                should_search=self._should_search(context),
                response_style=self._response_style(context),
                fallback_reply=fallback_reply,
            )
        return ConversationDecision(
            mode="chat",
            reply=fallback_reply,
            suggested_actions=self._suggest_actions(context),
            should_search=self._should_search(context),
            response_style=self._response_style(context),
            fallback_reply=fallback_reply,
        )

    def _build_chat_reply(self, context: RuntimeContext) -> str:
        profile = context.profile or {}
        latest = context.latest_user_message.strip()
        cities = profile.get("target_cities") if isinstance(profile.get("target_cities"), list) else []
        roles = profile.get("target_roles") if isinstance(profile.get("target_roles"), list) else []
        skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []
        education = str(profile.get("education") or "").strip()
        major = str(profile.get("major") or "").strip()

        lines: list[str] = []
        lines.append("### 当前判断")
        lines.append(self._build_judgement(latest, cities, roles, education, major, skills))
        lines.append("")
        lines.append("### 下一步建议")
        lines.append(self._build_next_step(latest, cities, roles, skills, context))
        if profile:
            lines.append("")
            lines.append("### 已记录信息")
            lines.append(self._build_profile_snapshot(profile))
        return "\n".join(lines).strip()

    def _build_judgement(
        self,
        latest: str,
        cities: list[object],
        roles: list[object],
        education: str,
        major: str,
        skills: list[object],
    ) -> str:
        if "中厂" in latest or "小厂" in latest:
            if education == "本科":
                return "按你现在的背景，本科 + 统计学 + 数据分析这条线，更适合先把中厂作为主投目标，再用少量业务清晰的小厂补充机会和面试反馈。"
            return "如果你的目标是尽快拿到第一批真实反馈，通常建议先把中厂和业务稳定的小厂一起纳入投递池，但优先级要看岗位匹配度。"
        if "广州" in latest and ("深圳" in latest or "深圳" in [str(city) for city in cities]):
            return "深圳通常岗位密度更高、竞争也更强；广州机会相对分散一些，但对很多候选人来说节奏可能更友好，适合一起放进对比池。"
        if "准备" in latest or "简历" in latest or "面试" in latest:
            role_text = "、".join(str(role) for role in roles[:2]) if roles else "目标岗位"
            return f"你现在更适合先围绕 {role_text} 补齐可验证能力，再反推简历和项目表达，而不是先泛泛投递。"
        if "适合" in latest or "什么岗位" in latest:
            role_text = "、".join(str(role) for role in roles[:2]) if roles else "先拆出 1 到 2 个更具体岗位方向"
            return f"从你目前的信息看，可以先把主投方向收敛到 {role_text} 这类更容易验证能力的岗位，再决定是否扩到相邻岗位。"
        background = " ".join(item for item in [education, major] if item).strip()
        city_text = "、".join(str(city) for city in cities[:2]) if cities else "目标城市"
        role_text = "、".join(str(role) for role in roles[:2]) if roles else "目标岗位"
        skill_text = "、".join(str(skill) for skill in skills[:3]) if skills else "现有技能"
        if background:
            return f"结合你目前的 {background} 背景、{city_text} 偏好，以及 {skill_text}，已经可以开始对 {role_text} 做更有针对性的判断。"
        return "我们已经可以开始缩小问题范围，但还需要把你的目标岗位和背景信息再收拢一点，这样建议会更稳。"

    def _build_next_step(
        self,
        latest: str,
        cities: list[object],
        roles: list[object],
        skills: list[object],
        context: RuntimeContext,
    ) -> str:
        if "中厂" in latest or "小厂" in latest:
            return "- 先按“中厂主投、小厂补充”的顺序排一轮投递名单。\n- 如果你愿意，我下一步可以直接帮你拆成：哪些类型的中厂值得优先投，哪些小厂需要避开。"
        if "广州" in latest and cities:
            role_text = "、".join(str(role) for role in roles[:2]) if roles else "相关岗位"
            return f"- 我建议下一步直接比较深圳和广州在 {role_text} 上的岗位密度、公司层级和竞争强度。\n- 如果你愿意，我也可以继续细拆成“中厂优先”还是“小厂优先”。"
        if "准备" in latest or "简历" in latest or "面试" in latest:
            skill_text = "、".join(str(skill) for skill in skills[:4]) if skills else "真实 JD 高频技能"
            return f"- 先收集 20 个左右真实 JD，看 {skill_text} 是否覆盖主要要求。\n- 再决定是补项目、调简历，还是直接投第一轮试水。"
        if context.open_questions:
            return f"- 你现在的信息已经足够做初步判断。\n- 再补一个关键信息后，建议会更稳：{context.open_questions[0]}。"
        return "- 如果你想要更完整的结论，可以继续补充背景，或者直接让我基于当前上下文生成一份完整报告。"

    def _build_profile_snapshot(self, profile: dict[str, object]) -> str:
        ordered_keys = [
            ("education", "学历"),
            ("school", "学校"),
            ("major", "专业"),
            ("target_cities", "目标城市"),
            ("target_roles", "目标岗位"),
            ("skills", "技能"),
        ]
        parts = []
        for key, label in ordered_keys:
            value = profile.get(key)
            if isinstance(value, list):
                rendered = "、".join(str(item) for item in value) if value else "未补充"
            else:
                rendered = str(value) if value else "未补充"
            parts.append(f"- {label}: {rendered}")
        return "\n".join(parts)

    def _maybe_follow_up(self, context: RuntimeContext) -> str:
        latest = context.latest_user_message.strip()
        if not context.open_questions:
            return ""
        low_information = len(latest) <= 10 or latest in {"怎么样", "如何", "那广州呢？", "那广州呢", "那深圳呢", "那深圳呢？"}
        if low_information:
            return f"为了让建议更准确，我还想确认一下你的{context.open_questions[0]}。"
        if len(context.profile) < 3:
            return f"如果你愿意，再补一下你的{context.open_questions[0]}，我可以把建议收得更具体。"
        return ""

    def _suggest_actions(self, context: RuntimeContext) -> list[str]:
        actions = ["继续分析", "生成完整报告"]
        if context.active_topic == "城市与岗位机会判断":
            actions.insert(1, "继续比较城市")
        return actions[:3]

    def _should_search(self, context: RuntimeContext) -> bool:
        latest = context.latest_user_message.strip()
        if not latest:
            return False
        search_markers = (
            "城市",
            "深圳",
            "广州",
            "杭州",
            "上海",
            "北京",
            "成都",
            "武汉",
            "机会",
            "岗位",
            "需求",
            "行情",
            "趋势",
            "技能",
            "薪资",
            "热度",
            "中厂",
            "小厂",
            "大厂",
        )
        non_search_markers = ("帮我生成报告", "生成报告", "输出报告", "总结成报告")
        if any(marker in latest for marker in non_search_markers):
            return False
        return any(marker in latest for marker in search_markers)

    def _response_style(self, context: RuntimeContext) -> str:
        latest = context.latest_user_message.strip()
        if "中厂" in latest or "小厂" in latest or "大厂" in latest:
            return "company_tier"
        if any(marker in latest for marker in ("城市", "深圳", "广州", "杭州", "上海", "北京")):
            return "comparison"
        if any(marker in latest for marker in ("简历", "面试", "准备")):
            return "preparation"
        return "advisory"
