# JobOracle 多轮对话与记忆功能计划

## 1. 当前目标

当前阶段只聚焦 3 件事：

1. 把 `JobOracle` 从单轮分析升级为多轮对话
2. 给多轮对话补上可用的记忆能力
3. 用 `Chainlit` 接一个临时前端验证交互形态

暂时不展开最终 CLI 产品形态，也不做长期记忆、向量检索或复杂前端。

## 2. 当前产品判断

现有 CLI 很适合单轮：

- 输入一个问题
- 执行一次分析
- 生成一份 Markdown 报告

但不适合多轮主交互，因为它不方便处理：

- 连续补充信息
- 自动维护会话
- 展示当前已记住的画像
- 在“短回复”和“生成报告”之间切换

因此当前方案是：

- 保留 CLI 作为开发和调试入口
- 先把多轮能力做在核心服务层
- 再用 `Chainlit` 做一个临时 Web 对话前端

## 3. 多轮对话的核心原则

### 3.1 能结构化的，尽量结构化

优先沉淀到 `profile` 的信息：

- 学历
- 学校
- 专业
- 毕业年份
- 目标城市
- 目标岗位
- 技能
- 实习经历
- 项目经历
- 目标行业

### 3.2 不能结构化的，用摘要保存

适合保存在摘要或任务状态中的信息：

- 当前在讨论什么
- 已经确认了什么
- 还缺什么信息
- 用户最近的决策方向

### 3.3 报告不是每轮都生成

多轮系统默认输出应该是对话回复，而不是每轮都跑完整报告链。

完整报告应由用户显式触发，例如：

- 点击“生成报告”
- 输入“帮我生成报告”
- 输入“总结成报告”

## 4. 记忆设计

当前只做三层记忆。

### 4.1 会话记忆

保存最近几轮消息，用于保证上下文连续性。

建议字段：

- `session_id`
- `message_id`
- `role`
- `content`
- `created_at`

### 4.2 用户画像记忆

保存用户在多轮中逐步透露的稳定信息。

这层尽量复用当前已有 `profile` 结构。

### 4.3 任务记忆

保存当前咨询状态。

建议字段：

- `active_topic`
- `active_goals`
- `open_questions`
- `decision_stage`
- `conversation_summary`
- `last_report_brief`

## 5. 建议的数据结构

```python
@dataclass(slots=True)
class Message:
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str


@dataclass(slots=True)
class MemoryState:
    session_id: str
    profile: dict[str, Any]
    conversation_summary: str
    active_topic: str
    active_goals: list[str]
    open_questions: list[str]
    decision_stage: str
    last_report_brief: str
    updated_at: str
```

## 6. 第一版存储方案

第一版优先简单可用。

推荐顺序：

1. 本地 `SQLite`
2. 如果实现速度优先，也可以先用本地 JSON

当前更推荐直接做 `SQLite`，因为后面会更容易管理：

- 多会话
- 消息历史
- 记忆状态
- 调试查询

## 7. 需要新增的模块

建议新增：

```text
src/JobOracle/
├── memory/
│   ├── models.py
│   ├── store.py
│   ├── extractor.py
│   ├── summarizer.py
│   └── manager.py
├── chat_service.py
├── conversation.py
└── ui/
    └── chainlit_app.py
```

职责如下。

### 7.1 `memory/models.py`

定义 `Message` 和 `MemoryState`。

### 7.2 `memory/store.py`

负责底层存储。

建议提供：

- `create_session()`
- `append_message()`
- `list_recent_messages()`
- `load_memory()`
- `save_memory()`

### 7.3 `memory/extractor.py`

从用户最新消息中抽取画像增量，并合并到 `profile`。

第一版先走规则和现有 `normalize_profile`，暂不引入复杂抽取。

### 7.4 `memory/summarizer.py`

负责维护：

- `conversation_summary`
- `open_questions`
- `active_goals`

第一版先做轻量规则版。

### 7.5 `memory/manager.py`

统一组织记忆更新流程，是多轮系统的核心入口。

### 7.6 `chat_service.py`

负责多轮对话主编排：

- 读取记忆
- 更新记忆
- 判断当前该短回复、追问还是生成报告
- 调用现有分析链

### 7.7 `conversation.py`

负责输出策略判断，例如：

- 当前轮走聊天回复
- 当前轮走追问
- 当前轮走报告生成

## 8. 对现有链路的改造

当前链路：

```text
CLI -> EmploymentRequest -> EmploymentAdvisor.analyze() -> Search -> Agents -> Report
```

建议升级为：

```text
Chat / Chainlit
  -> session_id
  -> MemoryManager.load()
  -> 更新 profile / summary / task state
  -> 由 Conversation 决定输出模式
  -> 若是 chat: 返回短回复
  -> 若是 report: 调用 EmploymentAdvisor 生成完整报告
  -> MemoryManager.save()
```

## 9. 输出模式

未来只保留两种核心模式。

### 9.1 Chat 模式

默认模式。

特点：

- 回答当前问题
- 必要时追问一个关键信息
- 明确利用已有记忆
- 不生成完整大报告

### 9.2 Report 模式

由用户显式触发。

特点：

- 基于当前会话累计记忆生成完整 Markdown 报告
- 继续复用现有 `Researcher -> Analyst -> Advisor` 链路
- 生成结果后写回 `last_report_brief`

## 10. 追问策略

第一版追问机制尽量简单：

- 每轮最多追问 1 个问题
- 只有缺失信息会显著影响建议时才追问
- 如果当前问题可以先回答，就先回答再补问

优先追问的字段：

- 学历
- 专业
- 目标城市
- 目标岗位
- 工作年限 / 是否应届
- 技能
- 实习或项目经历

## 11. Chainlit 的定位

`Chainlit` 当前只作为临时前端，不是最终产品形态。

它的作用是：

- 快速验证多轮交互体验
- 自动管理会话
- 展示聊天消息
- 放一个“生成报告”按钮
- 方便调试记忆是否正确更新

当前不需要围绕 `Chainlit` 做深度绑定，核心逻辑仍然放在 Python service 层。

## 12. MVP 实施顺序

### 第 1 步：记忆底座

先完成：

- `memory/models.py`
- `memory/store.py`
- `memory/manager.py`

目标：

- 能创建会话
- 能保存消息
- 能保存和读取 `MemoryState`

### 第 2 步：画像与摘要更新

完成：

- `memory/extractor.py`
- `memory/summarizer.py`

目标：

- 从多轮输入中累计 `profile`
- 维护 `conversation_summary`
- 维护 `open_questions`

### 第 3 步：多轮编排

完成：

- `chat_service.py`
- `conversation.py`

目标：

- 支持 chat 回复
- 支持追问
- 支持显式生成报告

### 第 4 步：接 Chainlit

完成：

- `ui/chainlit_app.py`

目标：

- 能在 Web 中连续对话
- 能点击按钮生成报告
- 能看到当前会话正常延续

## 13. 当前不做的事

当前先不做：

- 最终形态 CLI 美化
- 向量数据库
- 长期跨会话用户画像融合
- 复杂记忆召回排序
- 复杂状态机
- 重型前端框架

## 14. 当前结论

当前最重要的不是 UI，而是先把“多轮对话 + 记忆 + 报告显式触发”这条主链路做通。

当前执行方向已经明确：

1. 先做 memory
2. 再做 chat service
3. 再接 `Chainlit`
4. 报告只在用户触发时生成

这就是下一阶段的有效计划。
