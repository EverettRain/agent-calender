"""System prompts and message builders for extract / verify stages."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.llm.schema import generate_schema_str, verify_schema_str


def _now_in_tz(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")


EXTRACT_SYSTEM_TEMPLATE = """\
你是一个日程信息抽取器。从用户的一段自然语言里识别出所有独立的待办意图，输出严格 JSON。

【当前时间】{now}（时区 {tz}）— 用它来解析"明天/下周/今晚"等相对时间。
【输出位置】整个输出必须是合法 JSON 对象，结构如下：
{schema}

【两类待办的区别】
- event: 有明确的"开始时间"或"发生时间"，如"明天 14 点开会"、"周三下午 2-4 点上课"。
  * target_at = 开始时刻
  * 时间段事件用 end_at 或 duration_minutes 表达
  * advance_reminders_minutes 默认必须 [0]（到点提醒）
- deadline: 有明确的"截止时间/在...之前"，如"周五前交报告"、"5 月 30 日前提交申请"。
  * target_at = 截止时刻；若原文只给日期没给时刻，按当日 23:59 处理
  * end_at 和 duration_minutes 必须为 null
  * advance_reminders_minutes 默认必须 [1440, 60]（提前 1 天 + 提前 1 小时）

【advance_reminders_minutes 的规则（重要）】
- **永远给出非空合理列表**，event 用 [0]，deadline 用 [1440, 60] 作为默认
- 只有当用户原文里**显式**说"不要提醒/不用提醒/静默/不发通知"时，才返回 []
- 如果用户说"提前一周提醒" → [10080]；"提前 30 分钟" → [30]；"提前一天和一小时" → [1440, 60]
- 即便用户没提"提醒"二字，也要按默认值给出，不要返回 []

【一次输入可能有多条待办】
原文可能在一句话里包含多件事，要全部分别建条，但同一件事不要拆。
"""

EXTRACT_FEWSHOT = [
    {
        "role": "user",
        "content": "明天下午两点和张三在中关村开会",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "reminders": [
                    {
                        "kind": "event",
                        "title": "和张三开会",
                        "description": None,
                        "target_at": "<TOMORROW>T14:00:00+08:00",
                        "end_at": None,
                        "duration_minutes": None,
                        "location": "中关村",
                        "participants": ["张三"],
                        "advance_reminders_minutes": [0],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "user",
        "content": "周五前要交季度总结报告",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "reminders": [
                    {
                        "kind": "deadline",
                        "title": "交季度总结报告",
                        "description": None,
                        "target_at": "<FRIDAY>T23:59:00+08:00",
                        "end_at": None,
                        "duration_minutes": None,
                        "location": None,
                        "participants": [],
                        "advance_reminders_minutes": [1440, 60],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "user",
        "content": "明天 14 点和张三开个会，另外周五前要交报告",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "reminders": [
                    {
                        "kind": "event",
                        "title": "和张三开会",
                        "description": None,
                        "target_at": "<TOMORROW>T14:00:00+08:00",
                        "end_at": None,
                        "duration_minutes": None,
                        "location": None,
                        "participants": ["张三"],
                        "advance_reminders_minutes": [0],
                    },
                    {
                        "kind": "deadline",
                        "title": "交报告",
                        "description": None,
                        "target_at": "<FRIDAY>T23:59:00+08:00",
                        "end_at": None,
                        "duration_minutes": None,
                        "location": None,
                        "participants": [],
                        "advance_reminders_minutes": [1440, 60],
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
]


VERIFY_SYSTEM_TEMPLATE = """\
你是一个日程抽取结果的审核器。给你原文和一个抽取出来的 JSON 数组，只判断**实质性错误**。宁可放过也不要苛刻——只有确实出错时才判不通过。

【当前时间】{now}（时区 {tz}）
【输出位置】整个输出必须是合法 JSON 对象：
{schema}

【只在以下"实质性错误"时判不通过】
1. 漏抽：原文里明确的某个独立待办，整条没有出现在数组里。
2. 凭空捏造**待办条目**：数组里多出了一条原文根本没提到的事情（注意：是"多了一整条事项"，不是"多了字段"）。
3. 时间明显错误：日期/时刻与原文或相对时间（基于当前时间）解析得明显不符（差一天、上午下午搞反等）。
4. 分类明显错误：明明是"截止/在…之前/deadline"却标成 event，或反之。

【以下都属于"系统允许的正常行为"，绝对不要因此判不通过】
- `advance_reminders_minutes` 是系统按 kind 自动补的默认提醒（event 常见 [0]，deadline 常见 [1440,60]），原文没提也正常。
- deadline 原文只给日期没给时刻时，系统补成当天 23:59，正常。
- 标题是对原文的合理概括/截断，只要意思对就行，不要求逐字一致。
- description / location / participants 为 null 或为空，正常。
- 字段比原文"多"出来但属于上述默认值/合理补全，不算捏造。

【输出原则】
- 通过（绝大多数情况）：pass=true, issues=[]
- 仅当命中上面 4 条实质性错误之一时：pass=false, issues=[具体、可操作的问题]
  例：["第 2 条把'周五前交报告'标成了 event，应为 deadline", "原文提到的'周一体检'没有抽取出来"]
- 不要给出修订后的 JSON，只列问题即可。
"""


def build_extract_messages(
    text: str,
    tz: str,
    *,
    prior_attempt: dict | None = None,
    feedback_issues: list[str] | None = None,
) -> list[dict[str, str]]:
    now = _now_in_tz(tz)
    system = EXTRACT_SYSTEM_TEMPLATE.format(
        now=now,
        tz=tz,
        schema=generate_schema_str(),
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(EXTRACT_FEWSHOT)

    if prior_attempt is not None and feedback_issues:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"原文：{text}\n\n"
                    f"上一次抽取结果：\n{json.dumps(prior_attempt, ensure_ascii=False, indent=2)}\n\n"
                    f"审核意见（需要修正）：\n- "
                    + "\n- ".join(feedback_issues)
                    + "\n\n请基于反馈修正后重新输出完整 JSON。"
                ),
            }
        )
    else:
        messages.append({"role": "user", "content": f"原文：{text}"})

    return messages


def build_verify_messages(
    text: str,
    parsed: dict,
    tz: str,
) -> list[dict[str, str]]:
    now = _now_in_tz(tz)
    system = VERIFY_SYSTEM_TEMPLATE.format(
        now=now,
        tz=tz,
        schema=verify_schema_str(),
    )
    user = (
        f"原文：{text}\n\n"
        f"抽取结果：\n{json.dumps(parsed, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
