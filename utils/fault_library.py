"""Fault taxonomy utilities for attack/diagnosis prompt construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

_FAULT_PROMPT_EN: Dict[str, Dict[str, str]] = {
    "f1_1_tool_or_action_planning_error": {
        "description": "Wrong tool selection or an unreasonable action/call order inside a single agent.",
        "impact": "Often keeps the workflow running but degrades results, and can also damage later stages when a critical step is ordered incorrectly.",
        "prevalence_note": "No exact frequency was reported.",
    },
    "f1_2_response_format_error": {
        "description": "Invalid or unparseable output format that violates downstream structural expectations.",
        "impact": "Highly disruptive to execution because inter-component communication and parsing frequently break.",
        "prevalence_note": "One of the more frequent fine-grained failure types.",
    },
    "f1_3_response_content_deviation": {
        "description": "The response ignores constraints, answers the wrong thing, adds irrelevant content, or drifts away from the task goal.",
        "impact": "Usually does not stop the workflow immediately, but strongly degrades quality and compounds over long reasoning chains.",
        "prevalence_note": "One of the more frequent fine-grained failure types.",
    },
    "f1_4_knowledge_or_reasoning_limitation": {
        "description": "Missing knowledge, insufficient reasoning depth, or an incorrect conclusion.",
        "impact": "The most common effect is that execution completes but the answer is wrong, incomplete, or shallow.",
        "prevalence_note": "Among the highest-frequency categories with many observed cases.",
    },
    "f1_5_prompt_design_defect": {
        "description": "Unclear formatting requirements, ambiguous role definitions, missing examples, or insufficient constraints in the prompt.",
        "impact": "One of the most damaging quality-related failures: the system often completes execution but the final output is substantially degraded.",
        "prevalence_note": "Among the highest-frequency categories with many observed cases.",
    },
    "f1_6_language_or_encoding_defect": {
        "description": "Incompatible symbols, emoji, scripts, or character-encoding issues.",
        "impact": "More likely to directly break communication or parsing, making it a termination-prone failure type.",
        "prevalence_note": "No exact frequency was reported, but it appears more often in task-planning scenarios.",
    },
    "f1_7_tool_invocation_or_kb_retrieval_error": {
        "description": "A tool call fails inside an agent, or a knowledge-base / retrieval interface is used incorrectly.",
        "impact": "Often breaks the execution chain directly, especially when precise tool use or retrieval is required.",
        "prevalence_note": "More likely to appear in QA-style tasks.",
    },
    "f2_1_missing_input_validation": {
        "description": "Missing validation for whether an input exists and whether its format or type is correct.",
        "impact": "More likely to trigger execution errors or error propagation; one of the most common workflow-level problems.",
        "prevalence_note": "One of the most common workflow-level categories.",
    },
    "f2_2_unreasonable_node_dependency": {
        "description": "A downstream node depends on unavailable data, or the dependency chain is designed poorly.",
        "impact": "Often prevents downstream nodes from running and is a clear execution-terminating structural failure.",
        "prevalence_note": "One of the most common workflow-level categories, especially in long serial workflows.",
    },
    "f2_3_loops_and_deadlock": {
        "description": "Circular calls, missing stop conditions, or logical deadlock between agents.",
        "impact": "When it appears, it usually breaks execution directly and has a high termination rate.",
        "prevalence_note": "Relatively rare, but severe when it occurs.",
    },
    "f2_4_faulty_conditional_judgment": {
        "description": "An incorrect branch condition routes the workflow onto the wrong path.",
        "impact": "It may either terminate execution or keep running along an incorrect path and produce a wrong result.",
        "prevalence_note": "No exact frequency was reported.",
    },
    "f2_5_improper_task_decomposition": {
        "description": "Poor task decomposition causes duplication, conflict, or unclear responsibility across parallel or multi-node collaboration.",
        "impact": "Usually does not stop the system outright, but it clearly harms consistency and overall result quality.",
        "prevalence_note": "Relatively less common, but still a serious structural design issue.",
    },
    "f2_6_context_conflict": {
        "description": "Dialogue history, intermediate state, or shared context becomes inconsistent or misaligned.",
        "impact": "More often the system still completes execution, but the output becomes suboptimal or internally contradictory.",
        "prevalence_note": "No exact frequency was reported.",
    },
    "f2_7_cross_agent_tool_or_interface_mismatch": {
        "description": "Data formats, field structures, or interface protocols are incompatible across agents.",
        "impact": "Highly likely to cause downstream parsing failure and execution interruption; one of the most destructive workflow-level failures.",
        "prevalence_note": "No exact frequency was reported.",
    },
    "f3_1_network_and_resource_fluctuation": {
        "description": "Bandwidth shortage, latency jitter, insufficient compute, or other resource instability.",
        "impact": "Once triggered, it often causes direct runtime failure and is a classic platform-level interruption fault.",
        "prevalence_note": "Platform-level failures are less common overall, but this type does occur.",
    },
    "f3_2_service_unavailability": {
        "description": "The model service, API, or runtime platform is unavailable or unstable.",
        "impact": "One of the strongest execution-terminating failure types in the whole taxonomy and usually causes immediate task failure.",
        "prevalence_note": "Platform-level failures are less common overall, but this type is especially destructive.",
    },
}


@dataclass(frozen=True)
class FaultCandidate:
    """Normalized fault candidate used by prompt builders and analysis logic."""

    code: str
    description: str
    failure_rate: float
    execution_termination_rate: float
    suboptimal_quality_rate: float
    impact: str
    prevalence_note: str


def fault_candidates_for_prompt() -> List[Dict[str, Any]]:
    """Serialize the fault pool in English for prompt consumption."""
    lib = build_fault_library()
    return [
        {
            "code": fc.code,
            "description": _FAULT_PROMPT_EN.get(fc.code, {}).get("description", fc.description),
            "failure_rate": fc.failure_rate,
            "execution_termination_rate": fc.execution_termination_rate,
            "suboptimal_quality_rate": fc.suboptimal_quality_rate,
            "impact": _FAULT_PROMPT_EN.get(fc.code, {}).get("impact", fc.impact),
            "prevalence_note": _FAULT_PROMPT_EN.get(fc.code, {}).get(
                "prevalence_note", fc.prevalence_note
            ),
        }
        for fc in lib.values()
    ]


def build_two_stage_fault_library() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Build the full two-stage fault taxonomy with metrics and descriptions.

    Notes:
        - failure_rate: Average task failure rate after injecting this root cause.
        - execution_termination_rate: Ratio of runs that terminate abnormally.
        - suboptimal_quality_rate: Ratio of runs that finish with degraded quality.
        - prevalence_note: Qualitative prevalence description from report analysis.
    """

    return {
        "stage1_coarse": {
            "agent_level_failure": {
                "code": "agent_level_failure",
                "description": "故障发生在单个智能体内部，主要源于模型能力、提示设计、局部工具/检索调用或输出格式问题。",
                "failure_rate": 0.833,
                "execution_termination_rate": 0.388,
                "suboptimal_quality_rate": 0.445,
                "impact": "整体最常见；通常不会直接打断流程，而是更容易导致任务完成但答案质量差、内容偏离或不完整。",
                "prevalence_note": "该层级在异常数据集中占主导地位。"
            },
            "workflow_level_failure": {
                "code": "workflow_level_failure",
                "description": "故障来自多智能体协作、节点依赖、条件分支、上下文传递和接口对接等编排逻辑。",
                "failure_rate": 0.738,
                "execution_termination_rate": 0.475,
                "suboptimal_quality_rate": 0.263,
                "impact": "整体少于智能体级，但仍是重要瓶颈；更容易触发执行中断、路由错误、死锁或下游不可解析。",
                "prevalence_note": "该层级少于 agent-level，但缺少校验和不合理依赖是常见来源。"
            },
            "platform_level_failure": {
                "code": "platform_level_failure",
                "description": "故障归因于底层平台、模型服务、API、资源与运行环境波动。",
                "failure_rate": 0.900,
                "execution_termination_rate": 0.865,
                "suboptimal_quality_rate": 0.040,
                "impact": "总体出现比例较小，但一旦发生破坏性最强，往往直接导致任务终止而非仅质量下降。",
                "prevalence_note": "该层级总体占比较小，但后果最具破坏性。"
            },
        },

        "stage2_fine": {
            # =========================
            # Agent-level Failures
            # =========================
            "f1_1_tool_or_action_planning_error": {
                "code": "f1_1_tool_or_action_planning_error",
                "parent": "agent_level_failure",
                "description": "工具选择错误，或行动/调用顺序不合理。",
                "failure_rate": 0.797,
                "execution_termination_rate": 0.325,
                "suboptimal_quality_rate": 0.472,
                "impact": "更常表现为流程还能继续，但结果次优；也可能因关键步骤顺序错误导致后续链路受损。",
                "prevalence_note": "未单独给出精确出现占比。"
            },
            "f1_2_response_format_error": {
                "code": "f1_2_response_format_error",
                "parent": "agent_level_failure",
                "description": "输出格式无效、不可解析，或不符合下游预期结构。",
                "failure_rate": 0.895,
                "execution_termination_rate": 0.783,
                "suboptimal_quality_rate": 0.112,
                "impact": "高度破坏执行链路，常直接中断系统运行，因为组件间通信和解析会失败。",
                "prevalence_note": "属于较高频类别之一。"
            },
            "f1_3_response_content_deviation": {
                "code": "f1_3_response_content_deviation",
                "parent": "agent_level_failure",
                "description": "忽视提示约束、答非所问、输出冗余，或内容偏离任务目标。",
                "failure_rate": 0.827,
                "execution_termination_rate": 0.146,
                "suboptimal_quality_rate": 0.681,
                "impact": "通常不导致流程直接中止，但会显著拉低结果质量，在长链推理中易逐步累积。",
                "prevalence_note": "属于较高频类别之一。"
            },
            "f1_4_knowledge_or_reasoning_limitation": {
                "code": "f1_4_knowledge_or_reasoning_limitation",
                "parent": "agent_level_failure",
                "description": "知识缺失、推理不足，或得出错误结论。",
                "failure_rate": 0.746,
                "execution_termination_rate": 0.021,
                "suboptimal_quality_rate": 0.725,
                "impact": "最典型的影响是系统完成执行但答案错误、不完整或分析深度不足。",
                "prevalence_note": "其为最高频类别之一，且有五十多个实例。"
            },
            "f1_5_prompt_design_defect": {
                "code": "f1_5_prompt_design_defect",
                "parent": "agent_level_failure",
                "description": "输出格式要求不明确、角色定义含糊、缺少示例或约束不足。",
                "failure_rate": 0.901,
                "execution_termination_rate": 0.053,
                "suboptimal_quality_rate": 0.848,
                "impact": "对结果质量伤害最大之一，通常表现为系统能跑完，但整体输出劣化最明显。",
                "prevalence_note": "其为最高频类别之一，且实例较多。"
            },
            "f1_6_language_or_encoding_defect": {
                "code": "f1_6_language_or_encoding_defect",
                "parent": "agent_level_failure",
                "description": "符号、emoji、脚本或字符编码不兼容引发的异常。",
                "failure_rate": 0.816,
                "execution_termination_rate": 0.667,
                "suboptimal_quality_rate": 0.149,
                "impact": "更容易直接打断组件通信或解析流程，属于偏“执行终止型”故障。",
                "prevalence_note": "无精确频次，但在 task planning 任务中更常见。"
            },
            "f1_7_tool_invocation_or_kb_retrieval_error": {
                "code": "f1_7_tool_invocation_or_kb_retrieval_error",
                "parent": "agent_level_failure",
                "description": "智能体内部工具调用失败，或知识库/检索接口调用失败。",
                "failure_rate": 0.849,
                "execution_termination_rate": 0.724,
                "suboptimal_quality_rate": 0.125,
                "impact": "常直接破坏执行链路，尤其在依赖外部检索或精确工具调用的系统中影响显著。",
                "prevalence_note": "在问答类任务中更容易出现。"
            },

            # =========================
            # Workflow-level Failures
            # =========================
            "f2_1_missing_input_validation": {
                "code": "f2_1_missing_input_validation",
                "parent": "workflow_level_failure",
                "description": "缺少对输入变量是否存在、格式是否正确、类型是否匹配的必要校验。",
                "failure_rate": 0.730,
                "execution_termination_rate": 0.512,
                "suboptimal_quality_rate": 0.218,
                "impact": "更偏向引发执行异常或错误传播，是工作流级最常见问题之一。",
                "prevalence_note": "是 workflow-level 中最常见的类别之一。"
            },
            "f2_2_unreasonable_node_dependency": {
                "code": "f2_2_unreasonable_node_dependency",
                "parent": "workflow_level_failure",
                "description": "下游节点依赖不可用数据，或依赖链设计不合理。",
                "failure_rate": 0.773,
                "execution_termination_rate": 0.679,
                "suboptimal_quality_rate": 0.094,
                "impact": "常导致下游节点无法正常运行，属于明显的执行终止型结构故障。",
                "prevalence_note": "是 workflow-level 中最常见的类别之一；在 Coze 的长串行工作流中更突出。"
            },
            "f2_3_loops_and_deadlock": {
                "code": "f2_3_loops_and_deadlock",
                "parent": "workflow_level_failure",
                "description": "智能体间循环调用、停止条件缺失或逻辑卡死，导致无限执行或死锁。",
                "failure_rate": 0.721,
                "execution_termination_rate": 0.654,
                "suboptimal_quality_rate": 0.067,
                "impact": "一旦出现通常直接破坏执行，是典型的高终止率结构性故障。",
                "prevalence_note": "该类相对较少见，但一旦出现属于严重结构缺陷。"
            },
            "f2_4_faulty_conditional_judgment": {
                "code": "f2_4_faulty_conditional_judgment",
                "parent": "workflow_level_failure",
                "description": "分支判断错误，导致工作流被路由到错误路径。",
                "failure_rate": 0.714,
                "execution_termination_rate": 0.418,
                "suboptimal_quality_rate": 0.296,
                "impact": "既可能中断执行，也可能使流程继续但沿错误路径生成不正确结果。",
                "prevalence_note": "未给出精确出现占比。"
            },
            "f2_5_improper_task_decomposition": {
                "code": "f2_5_improper_task_decomposition",
                "parent": "workflow_level_failure",
                "description": "任务拆分不合理，并行或多节点协作后出现重复、冲突或职责不清。",
                "failure_rate": 0.687,
                "execution_termination_rate": 0.182,
                "suboptimal_quality_rate": 0.505,
                "impact": "通常不会让系统直接停掉，但会明显降低最终结果的一致性和质量。",
                "prevalence_note": "该类相对较少见，但属于严重的结构设计问题。"
            },
            "f2_6_context_conflict": {
                "code": "f2_6_context_conflict",
                "parent": "workflow_level_failure",
                "description": "对话历史、中间状态或共享上下文不一致、不对齐。",
                "failure_rate": 0.676,
                "execution_termination_rate": 0.117,
                "suboptimal_quality_rate": 0.559,
                "impact": "更常造成系统完成执行但中间信息不一致，从而输出次优或相互矛盾的结果。",
                "prevalence_note": "未给出精确出现占比。"
            },
            "f2_7_cross_agent_tool_or_interface_mismatch": {
                "code": "f2_7_cross_agent_tool_or_interface_mismatch",
                "parent": "workflow_level_failure",
                "description": "跨智能体传递的数据格式、字段结构或接口协议不兼容。",
                "failure_rate": 0.865,
                "execution_termination_rate": 0.762,
                "suboptimal_quality_rate": 0.103,
                "impact": "高度容易造成下游解析失败和执行中断，是 workflow-level 中破坏性最高的一类之一。",
                "prevalence_note": "未给出精确出现占比。"
            },

            # =========================
            # Platform-level Failures
            # =========================
            "f3_1_network_and_resource_fluctuation": {
                "code": "f3_1_network_and_resource_fluctuation",
                "parent": "platform_level_failure",
                "description": "带宽不足、延迟抖动、算力不足或资源波动。",
                "failure_rate": 0.896,
                "execution_termination_rate": 0.849,
                "suboptimal_quality_rate": 0.047,
                "impact": "一旦触发，往往直接导致运行失败，是典型的平台级中断型故障。",
                "prevalence_note": "平台级总体占比较小，但该类确实存在。"
            },
            "f3_2_service_unavailability": {
                "code": "f3_2_service_unavailability",
                "parent": "platform_level_failure",
                "description": "模型服务、API 或平台运行环境不可用或不稳定。",
                "failure_rate": 0.903,
                "execution_termination_rate": 0.881,
                "suboptimal_quality_rate": 0.032,
                "impact": "是整套 taxonomy 中最强的执行终止型故障之一，通常直接让任务失败。",
                "prevalence_note": "平台级总体占比较小，但该类后果最具破坏性。"
            },
        }
    }


def build_fault_library() -> Dict[str, FaultCandidate]:
    """Flatten stage-2 fault entries into ``code -> FaultCandidate`` mapping."""
    library = {}
    two_stage = build_two_stage_fault_library()
    for fault in two_stage["stage2_fine"].values():
        library[fault["code"]] = FaultCandidate(
            code=fault["code"],
            description=fault["description"],
            failure_rate=fault["failure_rate"],
            execution_termination_rate=fault["execution_termination_rate"],
            suboptimal_quality_rate=fault["suboptimal_quality_rate"],
            impact=fault["impact"],
            prevalence_note=fault["prevalence_note"],
        )
    return library