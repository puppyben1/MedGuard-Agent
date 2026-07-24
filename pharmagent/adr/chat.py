"""Context-grounded chat for ADR and research report pages."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from pharmagent.agent.llm import get_generator_llm
from pharmagent.adr.side_effect_rag import SideEffectSearchRequest, search_side_effects
from pharmagent.config import settings
from pharmagent.runtime_config import load_runtime_config

from .schemas import ADRChatRequest, ADRChatResponse, ChatCitation, EvidenceItem


class ChatConfigurationError(RuntimeError):
    """Raised when the user has not configured an external LLM."""


def answer_page_question(req: ADRChatRequest) -> ADRChatResponse:
    """Answer a page-level question using only current report context."""
    question = req.question.strip()
    if not question:
        raise ValueError("question 不能为空")
    _ensure_llm_configured()

    rag_hits = _retrieve_side_effect_context(req, question)
    context = _build_context(req)
    if rag_hits:
        context["sider_meddra_rag_hits"] = rag_hits
    citations = _build_citations(req)
    citations.extend(_rag_hits_to_citations(rag_hits))
    history = "\n".join(f"{item.role}: {item.content}" for item in req.history[-6:])
    citation_hint = "\n".join(f"- [{item.source}] {item.summary}" for item in citations[:8])

    system = SystemMessage(
        content=(
            "你是 MedGuard-Agent 的 ReportQAAgent。只允许基于用户当前页面报告、证据链、"
            "FAERS/openFDA 统计、Naranjo/WHO-UMC 评分、SIDER/MedDRA/Neo4j 上下文回答。"
            "禁止编造论文、病例、统计值或指南。证据不足时必须明确说明缺什么数据。"
            "回答使用中文，区分相关性、信号和因果关系，并在关键句后用 [来源] 标注依据。"
        )
    )
    human = HumanMessage(
        content=(
            f"页面模式：{req.mode}\n"
            f"用户问题：{question}\n\n"
            f"最近对话：\n{history or '无'}\n\n"
            f"可引用来源：\n{citation_hint or '当前上下文没有可引用来源'}\n\n"
            f"页面结构化上下文 JSON：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "请给出直接答案、证据解释、必要限制。不要给出没有来源支撑的外部事实。"
        )
    )

    llm = get_generator_llm()
    response = llm.invoke([system, human])
    answer = str(getattr(response, "content", response)).strip()
    return ADRChatResponse(
        answer=answer,
        citations=citations[:8],
        confidence=_estimate_confidence(req, citations),
        used_agents=_used_agents(req),
        limitations=_limitations(req),
    )


def _ensure_llm_configured() -> None:
    runtime = load_runtime_config()
    has_runtime_key = bool(runtime.llm.api_key)
    has_env_key = bool(settings.groq_api_key or settings.deepseek_api_key)
    if not has_runtime_key and not has_env_key:
        raise ChatConfigurationError("请先在「系统配置」页配置 LLM API Key，或在环境变量中设置 GROQ_API_KEY/DEEPSEEK_API_KEY。")


def _build_context(req: ADRChatRequest) -> dict[str, object]:
    if req.mode == "research":
        report = req.research_report
        if report is None:
            return {"mode": "research", "status": "no_research_report"}
        return {
            "mode": "research",
            "summary": report.summary,
            "agent_steps": [step.model_dump() for step in report.agent_steps],
            "findings": [item.model_dump() for item in report.findings[:30]],
            "top_drugs": [item.model_dump() for item in report.top_drugs],
            "adr_categories": [item.model_dump() for item in report.adr_categories],
            "confidence_distribution": [item.model_dump() for item in report.confidence_distribution],
            "neo4j_preview": report.graph_preview.model_dump(),
        }

    report = req.report
    if report is None:
        return {"mode": "adr", "status": "no_adr_report"}
    return {
        "mode": "adr",
        "summary": report.summary.model_dump(),
        "source_mode": report.source_mode,
        "extraction": report.extraction.model_dump(),
        "timeline": [item.model_dump() for item in report.timeline],
        "faers_signal": report.faers_signal.model_dump(),
        "prescription_risks": [item.model_dump() for item in report.prescription_risks],
        "causality": report.causality.model_dump(),
        "evidence_chain": [item.model_dump() for item in report.evidence_chain],
        "graph_highlighted_path": report.graph.highlighted_path,
        "graph_nodes": [item.model_dump() for item in report.graph.nodes],
        "limitations": report.limitations,
    }


def _build_citations(req: ADRChatRequest) -> list[ChatCitation]:
    if req.mode == "research":
        report = req.research_report
        if report is None:
            return []
        citations = [
            ChatCitation(source=item.pmid, source_type=item.source, summary=f"{item.drug} - {item.adverse_event}: {item.evidence_span}")
            for item in report.findings[:8]
        ]
        if report.graph_preview.nodes:
            citations.append(ChatCitation(source="Neo4j graph preview", source_type="graph", summary="当前科研 GraphRAG 图谱预览节点与关系。"))
        return citations

    report = req.report
    if report is None:
        return []
    citations = [_evidence_to_citation(item) for item in report.evidence_chain[:8]]
    citations.append(
        ChatCitation(
            source=report.faers_signal.source_mode,
            source_type="faers",
            summary=(
                f"{report.faers_signal.drug}/{report.faers_signal.adr}: "
                f"reports={report.faers_signal.report_count}, ROR={report.faers_signal.ror}, PRR={report.faers_signal.prr}"
            ),
        )
    )
    return citations


def _retrieve_side_effect_context(req: ADRChatRequest, question: str) -> list[dict[str, object]]:
    drug = ""
    adr = ""
    if req.mode == "adr" and req.report is not None:
        drug = req.report.summary.suspected_drug
        adr = req.report.summary.suspected_adr
    elif req.mode == "research" and req.research_report is not None and req.research_report.findings:
        first = req.research_report.findings[0]
        drug = first.drug
        adr = first.adverse_event
    try:
        response = search_side_effects(SideEffectSearchRequest(query=question, drug=drug, adr=adr, top_k=4))
    except Exception:
        return []
    return [hit.model_dump() for hit in response.hits]


def _rag_hits_to_citations(hits: list[dict[str, object]]) -> list[ChatCitation]:
    citations: list[ChatCitation] = []
    for hit in hits[:4]:
        side_effects = hit.get("matched_side_effects")
        first = side_effects[0] if isinstance(side_effects, list) and side_effects else {}
        term = first.get("term") if isinstance(first, dict) else ""
        cui = first.get("meddra_cui") if isinstance(first, dict) else ""
        citations.append(
            ChatCitation(
                source=f"SIDER/MedDRA {hit.get('drug_cid', '')}",
                source_type="offline_real_dataset",
                summary=f"{hit.get('drug_name', '')} - {term} ({cui})",
            )
        )
    return citations


def _evidence_to_citation(item: EvidenceItem) -> ChatCitation:
    return ChatCitation(source=item.source, source_type=item.source_type, summary=item.summary)


def _estimate_confidence(req: ADRChatRequest, citations: list[ChatCitation]) -> float:
    if not citations:
        return 0.35
    if req.mode == "adr" and req.report and req.report.faers_signal.source_mode == "realtime_openfda":
        return 0.84
    if req.mode == "research" and req.research_report and req.research_report.findings:
        return 0.78
    return 0.68


def _used_agents(req: ADRChatRequest) -> list[str]:
    if req.mode == "research":
        return ["ReportQAAgent", "SideEffectRAGAgent", "GraphRAGAgent", "ResearchMiningAgent", "EvidenceFusionAgent"]
    return ["ReportQAAgent", "SideEffectRAGAgent", "EvidenceFusionAgent", "FAERSSignalAgent", "CausalityAssessmentAgent"]


def _limitations(req: ADRChatRequest) -> list[str]:
    if req.mode == "research":
        if req.research_report is None:
            return ["尚未运行科研 Demo 或上传批量挖掘结果，回答只能说明缺失条件。"]
        return ["科研页当前基于已加载 findings 和图谱预览回答；未接入的外部 PubMed/DrugBank 实时检索不会被编造。"]
    if req.report is None:
        return ["尚未生成 ADR 分析报告，回答缺少病例上下文。"]
    return req.report.limitations[:3]
