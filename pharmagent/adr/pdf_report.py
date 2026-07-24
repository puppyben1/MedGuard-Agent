"""HTML and PDF export for ADR case reports."""

from __future__ import annotations

import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from pharmagent.adr.schemas import ADRAnalysisReport, PolypharmacyReport, ResearchMiningReport

FONT_NAME = "STSong-Light"


def render_adr_report_html(report: ADRAnalysisReport) -> str:
    """Render a source-backed HTML ADR report."""
    rows = [
        ("疑似药物", report.summary.suspected_drug),
        ("疑似 ADR", report.summary.suspected_adr),
        ("综合风险", report.summary.overall_risk_level),
        ("因果等级", report.summary.causality_level),
        ("信号强度", report.summary.signal_level),
        ("数据来源", report.source_mode),
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>MedGuard ADR Report</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; margin: 32px; color: #0f172a; }}
    h1 {{ font-size: 24px; margin: 0 0 6px; }}
    h2 {{ margin-top: 26px; font-size: 16px; border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px; vertical-align: top; font-size: 13px; }}
    th {{ background: #f1f5f9; text-align: left; }}
    .muted {{ color: #64748b; font-size: 12px; }}
    .box {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 12px; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>MedGuard-Agent ADR 个案报告</h1>
  <div class="muted">case_id: {esc(report.case_id)} | source_mode: {esc(report.source_mode)}</div>
  <h2>病例摘要</h2>
  {table_html(["项目", "内容"], rows)}
  <h2>核心建议</h2>
  <div class="box">{para(report.summary.recommendation)}</div>
  <h2>抽取结果</h2>
  {table_html(["类型", "名称", "证据"], [(d.role, d.name, d.evidence_text) for d in report.extraction.suspected_drugs] + [("ADR", e.name, e.evidence_text) for e in report.extraction.adverse_events])}
  <h2>时间轴</h2>
  {table_html(["事件", "时间", "描述", "风险相关性"], [(e.label, e.time_text, e.description, e.risk_relevance) for e in report.timeline])}
  <h2>FAERS/openFDA 信号</h2>
  {table_html(["指标", "值"], [
      ("报告数", str(report.faers_signal.report_count)),
      ("严重病例", str(report.faers_signal.serious_count)),
      ("死亡报告", str(report.faers_signal.death_count)),
      ("住院报告", str(report.faers_signal.hospitalization_count)),
      ("ROR", str(report.faers_signal.ror)),
      ("PRR", str(report.faers_signal.prr)),
      ("解释", report.faers_signal.clinical_interpretation),
  ])}
  <h2>因果评分</h2>
  {table_html(["项目", "值"], [("Naranjo", str(report.causality.naranjo_score)), ("Naranjo 分类", report.causality.naranjo_category), ("WHO-UMC", report.causality.who_umc_category)])}
  <h2>证据链</h2>
  {table_html(["来源", "类型", "立场", "强度", "摘要"], [(e.source, e.source_type, e.stance, e.strength, e.summary) for e in report.evidence_chain])}
  <h2>图谱节点</h2>
  {table_html(["节点", "类型", "风险", "说明"], [(n.label, n.type, n.risk or "", n.detail) for n in report.graph.nodes])}
  <h2>限制说明</h2>
  <ul>{"".join(f"<li>{esc(item)}</li>" for item in report.limitations)}</ul>
  <h2>完整报告文本</h2>
  <div class="box">{para(report.final_report)}</div>
</body>
</html>"""


def render_adr_report_pdf(report: ADRAnalysisReport) -> bytes:
    """Render an ADR report as PDF bytes."""
    _register_fonts()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="MedGuard ADR Report",
        author="MedGuard-Agent",
    )
    styles = _styles()
    story: list[object] = []

    story.append(Paragraph("MedGuard-Agent ADR 个案报告", styles["Title"]))
    story.append(Paragraph(f"case_id: {safe(report.case_id)} | source_mode: {safe(report.source_mode)}", styles["Meta"]))
    story.append(Spacer(1, 6))
    story.append(_section("病例摘要", styles))
    story.append(_kv_table([
        ("疑似药物", report.summary.suspected_drug),
        ("疑似 ADR", report.summary.suspected_adr),
        ("综合风险", report.summary.overall_risk_level),
        ("因果等级", report.summary.causality_level),
        ("信号强度", report.summary.signal_level),
        ("数据来源", report.source_mode),
        ("建议", report.summary.recommendation),
    ], styles))

    story.append(_section("结构化抽取", styles))
    extraction_rows = [["类型", "名称", "证据"]]
    extraction_rows.extend([[d.role, d.name, d.evidence_text] for d in report.extraction.suspected_drugs])
    extraction_rows.extend([["ADR", e.name, e.evidence_text] for e in report.extraction.adverse_events])
    story.append(_table(extraction_rows, styles, widths=[32 * mm, 42 * mm, 88 * mm]))

    story.append(_section("病例时间轴", styles))
    timeline_rows = [["事件", "时间", "描述", "风险相关性"]]
    timeline_rows.extend([[e.label, e.time_text, e.description, e.risk_relevance] for e in report.timeline])
    story.append(_table(timeline_rows, styles, widths=[38 * mm, 28 * mm, 48 * mm, 48 * mm]))

    story.append(_section("FAERS/openFDA 信号", styles))
    story.append(_kv_table([
        ("报告数", str(report.faers_signal.report_count)),
        ("严重病例", str(report.faers_signal.serious_count)),
        ("死亡报告", str(report.faers_signal.death_count)),
        ("住院报告", str(report.faers_signal.hospitalization_count)),
        ("ROR", str(report.faers_signal.ror)),
        ("PRR", str(report.faers_signal.prr)),
        ("解释", report.faers_signal.clinical_interpretation),
    ], styles))

    story.append(_section("因果评分", styles))
    story.append(_kv_table([
        ("Naranjo 得分", str(report.causality.naranjo_score)),
        ("Naranjo 分类", report.causality.naranjo_category),
        ("WHO-UMC 分类", report.causality.who_umc_category),
    ], styles))
    if report.causality.criteria:
        story.append(_table(
            [["标准", "得分", "理由"], *[[c.criterion, str(c.score), c.rationale] for c in report.causality.criteria]],
            styles,
            widths=[52 * mm, 18 * mm, 92 * mm],
        ))

    story.append(PageBreak())
    story.append(_section("证据链", styles))
    story.append(_table(
        [["来源", "类型", "立场", "强度", "摘要"], *[[e.source, e.source_type, e.stance, e.strength, e.summary] for e in report.evidence_chain]],
        styles,
        widths=[34 * mm, 24 * mm, 18 * mm, 18 * mm, 68 * mm],
    ))

    story.append(_section("图谱节点和关键关系", styles))
    story.append(_table(
        [["节点", "类型", "风险", "说明"], *[[n.label, n.type, n.risk or "", n.detail] for n in report.graph.nodes[:18]]],
        styles,
        widths=[42 * mm, 26 * mm, 20 * mm, 74 * mm],
    ))
    if report.graph.links:
        story.append(_table(
            [["起点", "关系", "终点", "证据"], *[[l.source, l.label, l.target, l.evidence] for l in report.graph.links[:18]]],
            styles,
            widths=[35 * mm, 30 * mm, 35 * mm, 62 * mm],
        ))

    story.append(_section("限制说明", styles))
    story.append(ListFlowable([ListItem(Paragraph(safe(item), styles["Body"])) for item in report.limitations], bulletType="bullet"))
    story.append(_section("完整报告文本", styles))
    story.append(Paragraph(to_paragraph(report.final_report), styles["Body"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def render_research_report_pdf(report: ResearchMiningReport) -> bytes:
    """Render a research mining report as PDF bytes."""
    _register_fonts()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="MedGuard Research Mining Report",
        author="MedGuard-Agent",
    )
    styles = _styles()
    story: list[object] = []

    story.append(Paragraph("MedGuard-Agent 科研批量 ADR 挖掘报告", styles["Title"]))
    story.append(Paragraph("source_mode: current ResearchMiningReport; no fabricated PubMed/BioDEX results", styles["Meta"]))
    story.append(Spacer(1, 6))
    story.append(_section("摘要", styles))
    story.append(Paragraph(to_paragraph(report.summary), styles["Body"]))
    story.append(_section("核心统计", styles))
    story.append(_kv_table([
        ("ADE findings", str(len(report.findings))),
        ("Top drugs", str(len(report.top_drugs))),
        ("ADR categories", str(len(report.adr_categories))),
        ("Graph nodes", str(len(report.graph_preview.nodes))),
        ("Graph relationships", str(len(report.graph_preview.relationships))),
    ], styles))
    story.append(_section("Agent 流程", styles))
    story.append(_table(
        [["Agent", "Role", "Source", "Summary"], *[[s.name, s.role, s.data_source, s.summary] for s in report.agent_steps]],
        styles,
        widths=[38 * mm, 36 * mm, 34 * mm, 54 * mm],
    ))
    story.append(_section("ADE 结构化结果", styles))
    story.append(_table(
        [["PMID/Doc", "Drug", "ADR", "Confidence", "Evidence"], *[
            [f.pmid or f.document_id, f.drug, f.adverse_event, f"{f.confidence:.2f}", f.evidence_span]
            for f in report.findings[:40]
        ]],
        styles,
        widths=[28 * mm, 28 * mm, 34 * mm, 22 * mm, 50 * mm],
    ))
    story.append(_section("限制说明", styles))
    story.append(Paragraph(
        "本报告只导出当前批量挖掘结果。若输入来自用户粘贴文本、CSV 或 JSONL，系统不会补造未提供的 PMID、文献结论或真实世界指标。",
        styles["Body"],
    ))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def render_polypharmacy_report_pdf(report: PolypharmacyReport) -> bytes:
    """Render a polypharmacy risk report as PDF bytes."""
    _register_fonts()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="MedGuard Polypharmacy Report",
        author="MedGuard-Agent",
    )
    styles = _styles()
    story: list[object] = []

    story.append(Paragraph("MedGuard-Agent 多药高阶风险报告", styles["Title"]))
    story.append(Paragraph(f"source_type: {safe(report.source_type)}", styles["Meta"]))
    story.append(Spacer(1, 6))
    story.append(_section("组合摘要", styles))
    story.append(_kv_table([
        ("药物组合", " + ".join(report.drugs)),
        ("综合风险", report.overall_risk_level),
        ("患者年龄", str(report.patient.age or "未提供")),
        ("诊断", "；".join(report.patient.diagnoses) or "未提供"),
        ("eGFR", str(report.patient.eGFR or "未提供")),
        ("图谱节点", str(len(report.mechanism_graph.nodes))),
    ], styles))
    story.append(_section("单药风险", styles))
    story.append(_table(
        [["Drug", "Risk", "Severity", "Evidence", "Rationale"], *[
            [r.drug, r.risk, r.severity, r.evidence_source, r.rationale] for r in report.single_drug_risks
        ]],
        styles,
        widths=[26 * mm, 28 * mm, 20 * mm, 36 * mm, 52 * mm],
    ))
    story.append(_section("两两相互作用", styles))
    story.append(_table(
        [["Drugs", "Risk", "Severity", "Mechanism", "Recommendation"], *[
            [" + ".join(i.drugs), i.risk, i.severity, i.mechanism, i.recommendation]
            for i in report.pairwise_interactions
        ]],
        styles,
        widths=[32 * mm, 30 * mm, 20 * mm, 42 * mm, 38 * mm],
    ))
    story.append(_section("高阶风险", styles))
    story.append(_table(
        [["Drugs", "Risk", "Severity", "Evidence", "Rationale"], *[
            [" + ".join(r.drugs), r.risk, r.severity, r.evidence_level, r.rationale]
            for r in report.higher_order_risks
        ]],
        styles,
        widths=[34 * mm, 34 * mm, 20 * mm, 28 * mm, 46 * mm],
    ))
    story.append(_section("建议与限制", styles))
    story.append(_table(
        [["Priority", "Recommendation", "Rationale"], *[[r.priority, r.text, r.rationale] for r in report.recommendations]],
        styles,
        widths=[28 * mm, 72 * mm, 62 * mm],
    ))
    if report.limitations:
        story.append(ListFlowable([ListItem(Paragraph(safe(item), styles["Body"])) for item in report.limitations], bulletType="bullet"))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _register_fonts() -> None:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle("TitleCN", parent=base["Title"], fontName=FONT_NAME, fontSize=18, leading=24, textColor=colors.HexColor("#0f172a")),
        "Heading": ParagraphStyle("HeadingCN", parent=base["Heading2"], fontName=FONT_NAME, fontSize=12, leading=16, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#0f172a")),
        "Body": ParagraphStyle("BodyCN", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8.6, leading=12.5, textColor=colors.HexColor("#334155")),
        "Meta": ParagraphStyle("MetaCN", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8, leading=11, textColor=colors.HexColor("#64748b")),
        "Cell": ParagraphStyle("CellCN", parent=base["BodyText"], fontName=FONT_NAME, fontSize=7.6, leading=10.5, textColor=colors.HexColor("#334155")),
        "HeaderCell": ParagraphStyle("HeaderCellCN", parent=base["BodyText"], fontName=FONT_NAME, fontSize=7.8, leading=10.5, textColor=colors.HexColor("#0f172a")),
    }


def _section(title: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(title, styles["Heading"])


def _kv_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    return _table([["项目", "内容"], *rows], styles, widths=[34 * mm, 128 * mm])


def _table(rows: list[list[str]], styles: dict[str, ParagraphStyle], widths: list[float]) -> Table:
    converted = []
    for index, row in enumerate(rows):
        style = styles["HeaderCell"] if index == 0 else styles["Cell"]
        converted.append([Paragraph(to_paragraph(str(cell)), style) for cell in row])
    table = Table(converted, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _footer(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont(FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(16 * mm, 9 * mm, "MedGuard-Agent ADR Report - decision support only")
    canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def table_html(headers: list[str], rows: list[tuple[object, ...]]) -> str:
    if not rows:
        rows = [("无",) + ("",) * (len(headers) - 1)]
    header_html = "".join(f"<th>{esc(item)}</th>" for item in headers)
    row_html = "".join("<tr>" + "".join(f"<td>{para(str(cell))}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{row_html}</tbody></table>"


def para(value: str) -> str:
    return esc(value).replace("\n", "<br />")


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def safe(value: object) -> str:
    return str(value or "").replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")


def to_paragraph(value: str) -> str:
    return html.escape(safe(value)).replace("\n", "<br/>")
