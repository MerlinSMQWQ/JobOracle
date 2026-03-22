from __future__ import annotations

from .models import MemoryState, Message


class MemorySummarizer:
    def update(self, memory: MemoryState, messages: list[Message]) -> MemoryState:
        memory.active_topic = self._infer_active_topic(messages)
        memory.open_questions = self._infer_open_questions(memory)
        memory.active_goals = self._infer_active_goals(memory, messages)
        memory.decision_stage = self._infer_decision_stage(memory)
        memory.conversation_summary = self._build_summary(memory, messages)
        return memory

    def _infer_active_topic(self, messages: list[Message]) -> str:
        if not messages:
            return ""
        latest = messages[-1].content
        if "城市" in latest or "深圳" in latest or "广州" in latest or "杭州" in latest:
            return "城市与岗位机会判断"
        if "简历" in latest or "面试" in latest or "准备" in latest:
            return "求职准备与投递策略"
        if "岗位" in latest or "工作" in latest:
            return "目标岗位分析"
        return "就业咨询"

    def _infer_decision_stage(self, memory: MemoryState) -> str:
        if memory.open_questions:
            return "补充背景信息"
        if memory.last_report_brief:
            return "报告后迭代"
        if memory.profile:
            return "定向分析"
        return "初步探索"

    def _build_summary(self, memory: MemoryState, messages: list[Message]) -> str:
        parts: list[str] = []
        if memory.profile:
            fields = ", ".join(sorted(memory.profile.keys()))
            parts.append(f"已沉淀画像字段：{fields}")
        if memory.active_topic:
            parts.append(f"当前主题：{memory.active_topic}")
        user_messages = [message.content for message in messages if message.role == "user"]
        if user_messages:
            parts.append(f"最近用户关注：{user_messages[-1][:80]}")
        return " | ".join(parts)

    def _infer_open_questions(self, memory: MemoryState) -> list[str]:
        questions: list[str] = []
        profile = memory.profile
        if not profile.get("education"):
            questions.append("学历")
        if not profile.get("major"):
            questions.append("专业")
        if not profile.get("target_roles"):
            questions.append("目标岗位")
        if not profile.get("target_cities"):
            questions.append("目标城市")
        if not profile.get("skills"):
            questions.append("技能")
        return questions[:3]

    def _infer_active_goals(self, memory: MemoryState, messages: list[Message]) -> list[str]:
        goals = list(memory.active_goals)
        latest_user_messages = [message.content for message in messages if message.role == "user"]
        if latest_user_messages:
            latest = latest_user_messages[-1]
            if latest not in goals:
                goals.append(latest[:60])
        return goals[-3:]
