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

setup_logging("INFO")

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
            "32-year-old female, currently 24 weeks pregnant, presents for hypertension management. "
            "Prescription: lisinopril 10 mg daily. No known allergies. eGFR 95. Liver function normal."
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
        "label": "Semaglutide + MTC 家族史（禁忌）",
        "text": (
            "55-year-old male with T2DM, BMI 34. Family history of medullary thyroid carcinoma. "
            "Prescription: semaglutide 0.25 mg SC weekly. eGFR 80. No allergies."
        ),
    },
    {
        "label": "Triple whammy（AKI 风险）",
        "text": (
            "70-year-old female with hypertension, CKD stage 3a (eGFR 50). "
            "Prescription: lisinopril 20 mg daily, ibuprofen 600 mg TID PRN, "
            "hydrochlorothiazide 25 mg daily. No allergies. Liver normal."
        ),
    },
    {
        "label": "阴性对照（无风险）",
        "text": (
            "40-year-old male with mild hypertension. Prescription: lisinopril 10 mg daily. "
            "eGFR 100. No allergies. Liver normal. Not on any other medications."
        ),
    },
]

# ── Original PharmAgent example queries ──────────────────────────────
EXAMPLE_QUERIES = [
    "What are the contraindications for metformin in patients with renal impairment?",
    "What are the risks of taking warfarin and aspirin together?",
    "Is semaglutide safe for a patient with a history of pancreatitis?",
    "What are the common adverse effects of lisinopril?",
    "Is metformin safe for a 68-year-old patient with stage 3 CKD who is also taking lisinopril and warfarin?",
]

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="MedGuard-Agent — Clinical Prescription Review",
    page_icon="💊",
    layout="wide",
)

st.title("💊 MedGuard-Agent")
st.caption("Evidence-constrained clinical prescription review agent")

# ── Tabs ─────────────────────────────────────────────────────────────
tab_rx, tab_qa = st.tabs(["📝 处方审查 / Prescription Review", "💬 药物安全问答 / Drug Safety QA"])

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
                "e.g. 68-year-old male, T2DM, CKD stage 4 (eGFR 18). "
                "Rx: metformin 1000mg BID.\n\n"
                "或中文：68岁男性，2型糖尿病，慢性肾脏病4期。处方：二甲双胍 1000毫克 每日两次。"
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
        st.markdown(
            f'### 总体风险等级: <span style="color:{color}; font-weight:bold; font-size:1.4em;">'
            f"{report.overall_risk_level.upper()}</span>"
            f" &nbsp; (confidence: {report.confidence:.0%})",
            unsafe_allow_html=True,
        )

        # ── Quality metrics row ───────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("证据覆盖率", f"{report.evidence_coverage:.0%}")
        m2.metric("未验证 finding 数", report.unverified_findings_count)
        m3.metric("幻觉标记", "⚠️ 是" if report.hallucination_flagged else "✅ 否")
        m4.metric("响应时间", f"{report.elapsed_seconds:.1f}s")

        # ── Summary ───────────────────────────────────────────────
        if report.summary:
            st.markdown("#### 总结")
            st.info(report.summary)

        # ── Patient case ──────────────────────────────────────────
        pc = report.patient_case
        with st.expander("🧑‍⚕️ 结构化病例", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("年龄", pc.age if pc.age is not None else "—")
            c2.metric("性别", pc.sex)
            c3.metric("eGFR", f"{pc.egfr}" if pc.egfr is not None else "—")
            c4.metric("肝功能", pc.liver_function)

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("INR", f"{pc.inr}" if pc.inr is not None else "—")
            c6.metric("妊娠", "是" if pc.pregnancy else ("否" if pc.pregnancy is False else "—"))
            c7.metric("过敏", ", ".join(pc.allergies) if pc.allergies else "无")
            c8.metric("解析置信度", f"{pc.parse_confidence:.0%}")

            if pc.diagnoses:
                st.markdown(f"**诊断:** {', '.join(pc.diagnoses)}")

            st.markdown("**处方药物:**")
            if pc.drugs:
                for d in pc.drugs:
                    parts = [d.name]
                    if d.dose:
                        parts.append(d.dose)
                    if d.frequency:
                        parts.append(d.frequency)
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
                verified_icon = "✅" if f.verified else "⚠️"
                with st.container(border=True):
                    st.markdown(
                        f"**{i}. [{f.severity.upper()}]** {f.finding_type} &nbsp; {verified_icon}",
                        unsafe_allow_html=False,
                    )
                    st.markdown(
                        f'<span style="color:{sev_color};">●</span> '
                        f"**涉及药物:** {', '.join(f.drugs_involved) if f.drugs_involved else '—'}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**描述:** {f.description}")
                    if f.recommendation:
                        st.markdown(f"**建议:** {f.recommendation}")
                    if f.evidence_doc_ids:
                        st.markdown(f"**证据文档:** {', '.join(f.evidence_doc_ids)}")
                    if f.verification_reason:
                        st.caption(f"核验: {f.verification_reason}")
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
    st.caption("原 PharmAgent agentic RAG — 自然语言药物安全问题")

    col_qa1, col_qa2 = st.columns([3, 1])
    with col_qa2:
        st.markdown("**示例问题**")
        for eq in EXAMPLE_QUERIES:
            if st.button(eq[:40] + ("..." if len(eq) > 40 else ""), key=eq, use_container_width=True):
                st.session_state["query_input"] = eq

    with col_qa1:
        query = st.text_area(
            "Enter your drug safety question:",
            value=st.session_state.get("query_input", ""),
            height=80,
            placeholder="e.g., What are the risks of taking warfarin and aspirin together?",
            label_visibility="collapsed",
        )

    run_clicked = st.button("🔍 Analyze", type="primary", use_container_width=True)

    if run_clicked and query.strip():
        st.session_state["query_count"] = st.session_state.get("query_count", 0) + 1

        with st.spinner("Running PharmAgent... (querying, grading, synthesizing)"):
            assessment: SafetyAssessment = run_agent(query.strip())

        st.divider()

        color = RISK_COLORS.get(assessment.risk_level, "#6c757d")
        st.markdown(
            f'### Risk Level: <span style="color:{color}; font-weight:bold;">'
            f"{assessment.risk_level.upper()}</span>"
            f" &nbsp; (confidence: {assessment.confidence:.0%})",
            unsafe_allow_html=True,
        )

        st.markdown("#### Summary")
        st.info(assessment.summary)

        if assessment.evidence:
            st.markdown("#### Evidence")
            for ev in assessment.evidence:
                finding = ev.get("finding", "")
                source = ev.get("source", "")
                st.markdown(f"- **{finding}** — *{source}*")

        if assessment.contraindications:
            st.markdown("#### Contraindications")
            for ci in assessment.contraindications:
                st.markdown(f"- {ci}")

        if assessment.monitoring:
            st.markdown("#### Recommended Monitoring")
            for mon in assessment.monitoring:
                st.markdown(f"- {mon}")

        if assessment.citations:
            with st.expander("📚 Citations", expanded=False):
                for cit in assessment.citations:
                    st.markdown(f"- {cit}")

    elif run_clicked:
        st.warning("Please enter a query.")


# ── Sidebar (shared) ─────────────────────────────────────────────────
with st.sidebar:
    st.header("About")
    st.markdown(
        "**MedGuard-Agent** extends PharmAgent into a structured clinical "
        "prescription review agent.\n\n"
        "- **Tab 1**: 处方审查 — 输入病例，输出结构化风险报告\n"
        "- **Tab 2**: 药物安全问答 — 原 PharmAgent QA"
    )
    st.divider()
    st.header("Token Budget (Groq)")
    gen_remaining = budget_tracker.generator_budget_remaining
    router_remaining = budget_tracker.router_budget_remaining
    st.metric("Generator calls left", f"{gen_remaining:,}")
    st.metric("Router calls left", f"{router_remaining:,}")
    if "query_count" in st.session_state:
        st.metric("QA queries this session", st.session_state["query_count"])
