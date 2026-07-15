"""Streamlit UI for MedGuard-Agent.

Two tabs:
1. Prescription Review (新增): paste a clinical case → structured risk report
2. Drug Safety QA (原 PharmAgent): natural-language drug safety questions
"""

import streamlit as st

from pharmagent.agent.graph import run_agent
from pharmagent.agent.llm import budget_tracker
from pharmagent.core.schemas import SafetyAssessment
from pharmagent.logging_config import setup_logging
from pharmagent.prescription.graph import run_prescription_review
from pharmagent.prescription.schemas import PrescriptionReport
from pharmagent.prescription.cn_labels import (
    cn_drug_name,
    cn_sex,
    cn_hepatic,
    cn_diagnosis,
    cn_freq,
    FINDING_TYPE_CN,
    SEVERITY_CN,
)

setup_logging("INFO")


@st.cache_resource(show_spinner=False)
def _warmup_models() -> str:
    """Pre-load embedding + rerank models so the first review is fast."""
    from pharmagent.core.embeddings import get_embedding_model
    from pharmagent.core.hybrid_retriever import _get_cross_encoder

    get_embedding_model()
    _get_cross_encoder()
    return "warm"

RISK_COLORS = {
    "low": "#28a745",
    "moderate": "#ffc107",
    "high": "#fd7e14",
    "critical": "#dc3545",
    "unknown": "#6c757d",
}

# ── Prescription review example cases ────────────────────────────────
PRESCRIPTION_EXAMPLES = [
    {
        "label": "妊娠 + ACEI（致畸禁忌）",
        "text": (
            "32岁女性，妊娠 24 周，因高血压就诊。"
            "处方：赖诺普利 10mg 每日一次。无药物过敏史。eGFR 95。肝功能正常。"
        ),
    },
    {
        "label": "二甲双胍 + 慢性肾病4期（乳酸酸中毒）",
        "text": (
            "68岁男性，2型糖尿病，慢性肾脏病4期。eGFR 18 mL/min/1.73m^2。"
            "当前处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次。"
            "无药物过敏史。肝功能正常。"
        ),
    },
    {
        "label": "华法林 + 阿司匹林 + 布洛芬（三重出血风险）",
        "text": (
            "74岁男性，房颤，骨关节炎。INR 3.2。"
            "处方：华法林 5mg 每日一次，阿司匹林 81mg 每日一次，"
            "布洛芬 600mg 每日三次 必要时。eGFR 70。无过敏。"
        ),
    },
    {
        "label": "司美格鲁肽 + MTC 家族史（禁忌）",
        "text": (
            "55岁男性，2型糖尿病，BMI 34。家族史：甲状腺髓样癌（MTC）。"
            "处方：司美格鲁肽 0.25mg 皮下注射 每周一次。eGFR 80。无过敏。"
        ),
    },
    {
        "label": "三联肾损伤（AKI 风险）",
        "text": (
            "70岁女性，高血压，慢性肾脏病 3a 期（eGFR 50）。"
            "处方：赖诺普利 20mg 每日一次，布洛芬 600mg 每日三次 必要时，"
            "氢氯噻嗪 25mg 每日一次。无过敏。肝功能正常。"
        ),
    },
    {
        "label": "阴性对照（无风险）",
        "text": (
            "40岁男性，轻度高血压。处方：赖诺普利 10mg 每日一次。"
            "eGFR 100。无过敏。肝功能正常。未使用其他药物。"
        ),
    },
]

# ── Original PharmAgent example queries ──────────────────────────────
EXAMPLE_QUERIES = [
    "肾功能不全患者使用二甲双胍的禁忌症有哪些？",
    "华法林与阿司匹林联用有哪些风险？",
    "司美格鲁肽对有胰腺炎病史的患者安全吗？",
    "赖诺普利的常见不良反应有哪些？",
    "68 岁 3 期 CKD 患者同时服用二甲双胍、赖诺普利和华法林是否安全？",
]

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="MedGuard-Agent — 临床处方审查智能体",
    page_icon="💊",
    layout="wide",
)

st.title("💊 MedGuard-Agent")
st.caption("证据约束的临床处方审查智能体")

# Pre-load models on first page render so the first review is fast.
with st.spinner("正在加载模型（首次约 30 秒，之后免重复加载）..."):
    _warmup_models()

# ── Tabs ─────────────────────────────────────────────────────────────
tab_rx, tab_qa = st.tabs(["📝 处方审查", "💬 药物安全问答"])

# ══════════════════════════════════════════════════════════════════════
# Tab 1: Prescription Review
# ══════════════════════════════════════════════════════════════════════
with tab_rx:
    st.markdown("### 📋 输入临床病例")
    st.caption("粘贴自由文本病例（中英文均可）：年龄、性别、诊断、eGFR、肝功能、INR、过敏史、处方药物")

    col_rx1, col_rx2 = st.columns([3, 1])
    with col_rx2:
        st.markdown("**示例病例**")
        for ex in PRESCRIPTION_EXAMPLES:
            if st.button(ex["label"], key=f"rx_ex_{ex['label']}", use_container_width=True):
                st.session_state["rx_input"] = ex["text"]

    with col_rx1:
        case_text = st.text_area(
            "临床病例",
            value=st.session_state.get("rx_input", ""),
            height=160,
            placeholder=(
                "示例：68岁男性，2型糖尿病，慢性肾脏病4期（eGFR 18）。"
                "处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次。"
                "无药物过敏史。肝功能正常。"
            ),
            label_visibility="collapsed",
        )

    run_rx = st.button("🔍 审查处方", type="primary", use_container_width=True)

    if run_rx and case_text.strip():
        with st.spinner("正在解析病例 → 检索证据 → 风险检查 → 证据核验 → 生成报告..."):
            report: PrescriptionReport = run_prescription_review(case_text.strip())

        st.divider()

        # ── Overall risk badge ────────────────────────────────────
        color = RISK_COLORS.get(report.overall_risk_level, "#6c757d")
        risk_cn = {"low": "低", "moderate": "中", "high": "高", "critical": "严重", "unknown": "未知"}.get(
            report.overall_risk_level, report.overall_risk_level
        )
        st.markdown(
            f'### 总体风险等级: <span style="color:{color}; font-weight:bold; font-size:1.4em;">'
            f"{risk_cn}</span>"
            f" &nbsp;（置信度: {report.confidence:.0%}）",
            unsafe_allow_html=True,
        )

        # ── Quality metrics row ───────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("证据覆盖率", f"{report.evidence_coverage:.0%}")
        m2.metric("未验证发现数", report.unverified_findings_count)
        m3.metric("幻觉标记", "⚠️ 是" if report.hallucination_flagged else "✅ 否")
        m4.metric("响应时间", f"{report.elapsed_seconds:.1f} 秒")

        # ── Summary ───────────────────────────────────────────────
        if report.summary:
            st.markdown("#### 审查总结")
            st.markdown(
                f'<div style="background:#f0f7ff; border-left:4px solid #4a9eff; '
                f'padding:12px 16px; border-radius:4px; white-space:pre-wrap; '
                f'line-height:1.6;">{report.summary}</div>',
                unsafe_allow_html=True,
            )

        # ── Patient case ──────────────────────────────────────────
        pc = report.patient_case
        with st.expander("🧑‍⚕️ 结构化病例", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("年龄", pc.age if pc.age is not None else "—")
            c2.metric("性别", cn_sex(pc.sex))
            c3.metric("eGFR", f"{pc.egfr}" if pc.egfr is not None else "—")
            c4.metric("肝功能", cn_hepatic(pc.liver_function))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("INR", f"{pc.inr}" if pc.inr is not None else "—")
            c6.metric("妊娠", "是" if pc.pregnancy else ("否" if pc.pregnancy is False else "—"))
            allergies_cn = ", ".join(cn_drug_name(a) for a in pc.allergies) if pc.allergies else "无"
            c7.metric("过敏", allergies_cn)
            c8.metric("解析置信度", f"{pc.parse_confidence:.0%}")

            if pc.diagnoses:
                diagnoses_cn = ", ".join(cn_diagnosis(d) for d in pc.diagnoses)
                st.markdown(f"**诊断：** {diagnoses_cn}")

            st.markdown("**处方药物：**")
            if pc.drugs:
                for d in pc.drugs:
                    parts = [cn_drug_name(d.name)]
                    if d.dose:
                        parts.append(d.dose)
                    if d.frequency:
                        parts.append(cn_freq(d.frequency))
                    if d.notes:
                        parts.append(f"({d.notes})")
                    st.markdown(f"- {' '.join(parts)}")
            else:
                st.markdown("- *(未识别到药物)*")

        # ── Findings ──────────────────────────────────────────────
        st.markdown("#### ⚠️ 风险发现")
        if report.findings:
            for i, f in enumerate(report.findings, 1):
                sev_color = RISK_COLORS.get(f.severity, "#6c757d")
                sev_cn = SEVERITY_CN.get(f.severity, f.severity)
                type_cn = FINDING_TYPE_CN.get(f.finding_type, f.finding_type)
                verified_icon = "✅ 已验证" if f.verified else "⚠️ 未验证"
                drugs_cn = ", ".join(cn_drug_name(d) for d in f.drugs_involved) if f.drugs_involved else "—"
                with st.container(border=True):
                    st.markdown(
                        f'**{i}. [{sev_cn}] {type_cn}** &nbsp; <span style="color:{sev_color};">●</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**涉及药物：** {drugs_cn}")
                    st.markdown(f"**描述：** {f.description}")
                    if f.recommendation:
                        st.markdown(f"**建议：** {f.recommendation}")
                    if f.evidence_doc_ids:
                        st.markdown(f"**证据文档：** {', '.join(f.evidence_doc_ids)}")
                    if f.verification_reason:
                        st.caption(f"核验状态：{verified_icon} — {f.verification_reason}")
        else:
            st.success("✅ 未发现用药风险")

        # ── Citations ─────────────────────────────────────────────
        if report.citations:
            with st.expander("📚 引用文献", expanded=False):
                for cit in report.citations:
                    st.markdown(f"- {cit}")

    elif run_rx:
        st.warning("请输入临床病例文本。")


# ══════════════════════════════════════════════════════════════════════
# Tab 2: Drug Safety QA (original PharmAgent)
# ══════════════════════════════════════════════════════════════════════
with tab_qa:
    st.markdown("### 💬 药物安全问答")
    st.caption("自然语言药物安全问答 — 检索药品说明书、医学文献与临床指南")

    col_qa1, col_qa2 = st.columns([3, 1])
    with col_qa2:
        st.markdown("**示例问题**")
        for eq in EXAMPLE_QUERIES:
            if st.button(eq[:40] + ("..." if len(eq) > 40 else ""), key=eq, use_container_width=True):
                st.session_state["query_input"] = eq

    with col_qa1:
        query = st.text_area(
            "输入药物安全问题",
            value=st.session_state.get("query_input", ""),
            height=80,
            placeholder="例如：华法林与阿司匹林联用有哪些风险？",
            label_visibility="collapsed",
        )

    run_clicked = st.button("🔍 分析", type="primary", use_container_width=True)

    if run_clicked and query.strip():
        st.session_state["query_count"] = st.session_state.get("query_count", 0) + 1

        with st.spinner("正在检索、评级、综合分析..."):
            assessment: SafetyAssessment = run_agent(query.strip())

        st.divider()

        color = RISK_COLORS.get(assessment.risk_level, "#6c757d")
        risk_cn = {"low": "低", "moderate": "中", "high": "高", "critical": "严重", "unknown": "未知"}.get(
            assessment.risk_level, assessment.risk_level
        )
        st.markdown(
            f'### 风险等级: <span style="color:{color}; font-weight:bold;">'
            f"{risk_cn}</span>"
            f" &nbsp;（置信度: {assessment.confidence:.0%}）",
            unsafe_allow_html=True,
        )

        st.markdown("#### 总结")
        st.info(assessment.summary)

        if assessment.evidence:
            st.markdown("#### 证据")
            for ev in assessment.evidence:
                finding = ev.get("finding", "")
                source = ev.get("source", "")
                st.markdown(f"- **{finding}** — *{source}*")

        if assessment.contraindications:
            st.markdown("#### 禁忌症")
            for ci in assessment.contraindications:
                st.markdown(f"- {ci}")

        if assessment.monitoring:
            st.markdown("#### 建议监测项")
            for mon in assessment.monitoring:
                st.markdown(f"- {mon}")

        if assessment.citations:
            with st.expander("📚 引用文献", expanded=False):
                for cit in assessment.citations:
                    st.markdown(f"- {cit}")

    elif run_clicked:
        st.warning("请输入问题。")


# ── Sidebar (shared) ─────────────────────────────────────────────────
with st.sidebar:
    st.header("关于")
    st.markdown(
        "**MedGuard-Agent** — 面向临床处方审查的医学智能体\n\n"
        "- **Tab 1 处方审查**：输入临床病例，输出结构化用药风险报告\n"
        "- **Tab 2 药物安全问答**：自然语言药物安全问答"
    )
    st.divider()
    st.header("LLM 调用预算")
    gen_remaining = budget_tracker.generator_budget_remaining
    router_remaining = budget_tracker.router_budget_remaining
    st.metric("生成器剩余调用次数", f"{gen_remaining:,}")
    st.metric("路由器剩余调用次数", f"{router_remaining:,}")
    if "query_count" in st.session_state:
        st.metric("本次会话问答次数", st.session_state["query_count"])
