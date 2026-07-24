import { lazy, Suspense, useMemo, useState } from "react";
import { api } from "../api";
import type {
  ADRAnalysisReport,
  ADRExample,
  ChatCitation,
  EvidenceItem,
  GraphLink,
  GraphNode,
  Neo4jGraphPreview,
  Neo4jRelationship,
  PageChatMessage,
  Severity,
  SignalLevel,
  TimelineEvent,
} from "../types";

const Neo4j3DGraph = lazy(() => import("./Neo4j3DGraph"));

const SEVERITY_CN: Record<Severity, string> = {
  low: "低风险",
  moderate: "中等风险",
  high: "高风险",
  critical: "危急风险",
};

const SEVERITY_COLOR: Record<Severity, string> = {
  low: "#16a34a",
  moderate: "#d97706",
  high: "#ea580c",
  critical: "#dc2626",
};

const SIGNAL_CN: Record<SignalLevel, string> = {
  none: "无明显信号",
  weak: "弱信号",
  moderate: "中等信号",
  strong: "强信号",
};

interface Props {
  examples: ADRExample[];
}

type ADRTab = "extract" | "timeline" | "signal" | "causality" | "evidence" | "graph" | "report";

export default function ADRAnalysis({ examples }: Props) {
  const [caseText, setCaseText] = useState(examples[0]?.case_text ?? "");
  const [realtime, setRealtime] = useState(false);
  const [report, setReport] = useState<ADRAnalysisReport | null>(null);
  const [activeTab, setActiveTab] = useState<ADRTab>("graph");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const runAnalysis = async () => {
    if (!caseText.trim()) {
      setError("请输入病例或选择一个演示病例");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.analyzeADR(caseText, realtime);
      setReport(result);
      setActiveTab("graph");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async () => {
    if (!report) return;
    setPdfLoading(true);
    setPdfError(null);
    try {
      const blob = await api.downloadADRReportPdf(report);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `medguard-adr-${report.case_id || "report"}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : String(e));
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-slate-100 shadow-lg shadow-slate-950/10">
        <div className="border-b border-slate-800 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-cyan-300">Clinical Case Mode</p>
              <h2 className="mt-1 text-xl font-semibold">临床个案 ADR 全流程分析</h2>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
                LLM 先解析病例语义，九大专业 Agent 再完成抽取、处方风险、FAERS 信号、因果评分、证据融合和 Neo4j 图谱构建。
              </p>
            </div>
            <label className="flex items-center gap-2 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200">
              <input
                type="checkbox"
                checked={realtime}
                onChange={(e) => setRealtime(e.target.checked)}
                className="h-4 w-4 accent-cyan-400"
              />
              启用实时 openFDA 查询
            </label>
          </div>
        </div>
        <div className="grid gap-4 p-5 lg:grid-cols-[1.25fr_0.75fr]">
          <div>
            <textarea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              rows={7}
              className="w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              placeholder="粘贴病例、主诉或处方文本..."
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                onClick={runAnalysis}
                disabled={loading}
                className="rounded-md bg-cyan-400 px-5 py-2 text-sm font-semibold text-cyan-950 transition-colors hover:bg-cyan-300 disabled:bg-slate-700"
              >
                {loading ? "多 Agent 分析中..." : "开始 ADR 分析"}
              </button>
              {error && <span className="text-sm text-red-300">{error}</span>}
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs text-slate-400">稳定演示病例</p>
            <div className="grid max-h-52 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-1">
              {examples.map((ex) => (
                <button
                  key={ex.id}
                  onClick={() => setCaseText(ex.case_text)}
                  className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-left transition-colors hover:border-cyan-400/70 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-400"
                >
                  <div className="text-sm font-medium text-slate-100">{ex.label}</div>
                  <div className="mt-0.5 text-xs text-slate-400">
                    {ex.drug} / {ex.adr}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {loading && (
        <section className="rounded-lg border border-slate-200 bg-white p-8 text-center">
          <div className="mb-3 inline-block h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
          <p className="text-sm font-medium text-slate-700">正在执行九大 Agent ADR 分析流程</p>
          <p className="mt-1 text-xs text-slate-500">抽取、检索、量化、评分、融合、图谱构建会按顺序完成</p>
        </section>
      )}

      {report && !loading && (
        <div className="grid items-start gap-5 xl:grid-cols-[1fr_320px]">
          <div className="space-y-5">
            <SummaryPanel report={report} onDownloadPdf={downloadPdf} pdfLoading={pdfLoading} pdfError={pdfError} />
            <AgentFlow report={report} />
            <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="flex gap-1 overflow-x-auto border-b border-slate-200 px-4 pt-3">
                <TabButton active={activeTab === "extract"} onClick={() => setActiveTab("extract")}>抽取结果</TabButton>
                <TabButton active={activeTab === "timeline"} onClick={() => setActiveTab("timeline")}>时间轴</TabButton>
                <TabButton active={activeTab === "signal"} onClick={() => setActiveTab("signal")}>FAERS 信号</TabButton>
                <TabButton active={activeTab === "causality"} onClick={() => setActiveTab("causality")}>因果评分</TabButton>
                <TabButton active={activeTab === "evidence"} onClick={() => setActiveTab("evidence")}>证据链</TabButton>
                <TabButton active={activeTab === "graph"} onClick={() => setActiveTab("graph")}>Neo4j 3D 图谱</TabButton>
                <TabButton active={activeTab === "report"} onClick={() => setActiveTab("report")}>完整报告</TabButton>
              </div>
              <div className="p-5">
                {activeTab === "extract" && <ExtractionView report={report} />}
                {activeTab === "timeline" && <TimelineView events={report.timeline} />}
                {activeTab === "signal" && <SignalView report={report} />}
                {activeTab === "causality" && <CausalityView report={report} />}
                {activeTab === "evidence" && <EvidenceView evidence={report.evidence_chain} />}
                {activeTab === "graph" && <GraphView report={report} />}
                {activeTab === "report" && <ReportText report={report} />}
              </div>
            </section>
          </div>
          <AIAssistantPanelLive report={report} />
        </div>
      )}
    </div>
  );
}

function SummaryPanel({
  report,
  onDownloadPdf,
  pdfLoading,
  pdfError,
}: {
  report: ADRAnalysisReport;
  onDownloadPdf: () => void;
  pdfLoading: boolean;
  pdfError: string | null;
}) {
  const risk = report.summary.overall_risk_level;
  const sourceText =
    report.source_mode === "realtime_openfda"
      ? "实时 openFDA"
      : report.source_mode === "offline_faers"
        ? "离线 FAERS 官方缓存"
        : report.source_mode === "fallback_demo"
          ? "实时失败，回退本地 demo"
          : "本地演示 FAERS";
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-slate-500">综合结论</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">
            {report.summary.suspected_drug} 与 {report.summary.suspected_adr}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full px-3 py-1 text-sm font-semibold text-white" style={{ backgroundColor: SEVERITY_COLOR[risk] }}>
            {SEVERITY_CN[risk]}
          </span>
          <button
            onClick={onDownloadPdf}
            disabled={pdfLoading}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition-colors hover:border-slate-500 hover:bg-slate-50 disabled:border-slate-200 disabled:text-cyan-900"
          >
            {pdfLoading ? "生成 PDF 中" : "下载 PDF 报告"}
          </button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Metric label="疑似药物" value={report.summary.suspected_drug} />
        <Metric label="疑似 ADR" value={report.summary.suspected_adr} />
        <Metric label="FAERS 信号" value={SIGNAL_CN[report.summary.signal_level]} />
        <Metric label="因果等级" value={report.summary.causality_level} />
        <Metric label="数据来源" value={sourceText} />
      </div>
      <div className="mt-4 rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-relaxed text-blue-950">
        {report.summary.recommendation}
      </div>
      {pdfError && <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{pdfError}</p>}
    </section>
  );
}

function AgentFlow({ report }: { report: ADRAnalysisReport }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950 p-5 text-slate-100 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">九大专业 Agent 协同链路</h3>
          <p className="mt-1 text-xs text-slate-400">LLM 语义理解 + 专业 Agent 计算/检索/校验 + 结构化输出</p>
        </div>
        <span className="rounded border border-cyan-400/40 bg-cyan-400/10 px-2 py-1 text-xs text-cyan-200">multi-agent trace</span>
      </div>
      <div className="grid gap-3 md:grid-cols-3 2xl:grid-cols-5">
        {report.agent_steps.map((step, idx) => (
          <div key={`${step.name}-${idx}`} className="min-h-36 rounded-md border border-slate-700 bg-slate-900/80 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-cyan-300">Agent {idx + 1}</span>
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)]" />
            </div>
            <div className="mt-2 break-words text-sm font-semibold text-slate-100">{step.name}</div>
            {step.role && <div className="mt-1 text-xs text-cyan-200">{step.role}</div>}
            {step.data_source && <div className="mt-2 text-[11px] text-slate-400">数据源：{step.data_source}</div>}
            <p className="mt-2 text-xs leading-relaxed text-slate-300">{step.summary}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExtractionView({ report }: { report: ADRAnalysisReport }) {
  const ex = report.extraction;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-800">结构化 ADR 个案</h3>
        <div className="space-y-3">
          {ex.suspected_drugs.map((drug) => (
            <InfoBlock key={`${drug.name}-${drug.role}`} label={`药物：${drug.name}`} value={`${drug.role}；${drug.evidence_text}`} />
          ))}
          {ex.adverse_events.map((event) => (
            <InfoBlock key={event.name} label={`ADR：${event.name}`} value={`${event.original_text}；${event.evidence_text}`} />
          ))}
        </div>
      </div>
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-800">因果线索</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="抽取置信度" value={`${Math.round(ex.extraction_confidence * 100)}%`} />
          <Metric label="停药反应" value={ex.dechallenge.available ? ex.dechallenge.result : "未描述"} />
          <Metric label="再给药" value={ex.rechallenge.available ? ex.rechallenge.result : "未描述"} />
          <Metric label="合并用药" value={ex.concomitant_drugs.join("；") || "无"} />
        </div>
      </div>
    </div>
  );
}

function TimelineView({ events }: { events: TimelineEvent[] }) {
  return (
    <div className="space-y-3">
      {events.length === 0 && <p className="text-sm text-slate-500">当前报告未抽取到明确时间轴。</p>}
      {events.map((event, idx) => (
        <div key={`${event.event_type}-${idx}`} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">{idx + 1}</div>
            {idx < events.length - 1 && <div className="w-px flex-1 bg-slate-200" />}
          </div>
          <div className="pb-4">
            <div className="text-sm font-semibold text-slate-800">{event.label}</div>
            <div className="mt-0.5 text-xs text-slate-500">{event.time_text}</div>
            <p className="mt-1 text-sm text-slate-700">{event.description}</p>
            <p className="mt-1 text-xs text-blue-700">{event.risk_relevance}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function SignalView({ report }: { report: ADRAnalysisReport }) {
  const s = report.faers_signal;
  const table = s.contingency_table ?? {};
  const maxTrend = Math.max(...s.yearly_trend.map((p) => p.reports), 1);
  const hasContingency = ["a", "b", "c", "d"].every((key) => typeof table[key as "a" | "b" | "c" | "d"] === "number");
  const sourceLabel =
    s.source_mode === "offline_faers"
      ? "真实离线 FAERS 缓存"
      : s.source_mode === "realtime_openfda"
        ? "实时 openFDA API"
        : s.source_mode === "fallback_demo"
          ? "openFDA 失败回退 demo"
          : "本地 demo 信号";
  const sourceTone =
    s.source_mode === "offline_faers"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : s.source_mode === "realtime_openfda"
        ? "border-blue-200 bg-blue-50 text-blue-800"
        : "border-amber-200 bg-amber-50 text-amber-800";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">信号来源与计算口径</h3>
          <p className="mt-1 text-sm text-slate-600">{s.source || sourceLabel}；{s.deduplicated ? "已按病例键去重" : "未声明完整去重"}。</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${sourceTone}`}>{sourceLabel}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Metric label="报告数" value={s.report_count.toLocaleString()} />
        <Metric label="严重病例" value={s.serious_count.toLocaleString()} />
        <Metric label="死亡报告" value={s.death_count.toLocaleString()} />
        <Metric label="住院报告" value={s.hospitalization_count.toLocaleString()} />
        <Metric label="ROR" value={s.ror?.toString() ?? "—"} />
        <Metric label="PRR" value={s.prr?.toString() ?? "—"} />
      </div>
      <p className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">{s.clinical_interpretation}</p>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h4 className="mb-2 text-sm font-semibold text-slate-800">年度趋势</h4>
          <div className="flex h-48 items-end gap-2 rounded-md border border-slate-200 p-3">
            {s.yearly_trend.length > 0 ? (
              s.yearly_trend.map((point) => (
                <div key={point.year} className="flex flex-1 flex-col items-center justify-end gap-1">
                  <div className="w-full rounded-t bg-blue-500" style={{ height: `${(point.reports / maxTrend) * 150}px` }} />
                  <span className="text-[11px] text-slate-500">{point.year}</span>
                </div>
              ))
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">当前来源未返回年度趋势；不使用伪造趋势占位。</div>
            )}
          </div>
        </div>
        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">二乘二表</h4>
          {hasContingency ? (
            <div className="overflow-hidden rounded-md border border-slate-200">
              <table className="w-full text-sm">
                <tbody>
                  <ContingencyRow label="目标药物 + 目标 ADR" value={table.a ?? 0} />
                  <ContingencyRow label="目标药物 + 其他 ADR" value={table.b ?? 0} />
                  <ContingencyRow label="其他药物 + 目标 ADR" value={table.c ?? 0} />
                  <ContingencyRow label="其他药物 + 其他 ADR" value={table.d ?? 0} />
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">当前来源未提供完整二乘二表；仅展示已返回的信号摘要。</div>
          )}
          <p className="mt-2 text-xs leading-relaxed text-slate-500">ROR/PRR 是自发报告不成比例指标，只提示报告关联，不能证明因果关系。</p>
        </div>
      </div>
      <ul className="grid gap-2 text-sm text-slate-600 lg:grid-cols-2">
        {s.limitations.map((item) => (
          <li key={item} className="rounded border border-amber-100 bg-amber-50 px-3 py-2">{item}</li>
        ))}
      </ul>
    </div>
  );
}

function ContingencyRow({ label, value }: { label: string; value: number }) {
  return (
    <tr className="border-b border-slate-100 last:border-b-0">
      <td className="bg-slate-50 px-3 py-2 text-slate-600">{label}</td>
      <td className="px-3 py-2 text-right font-semibold text-slate-900">{value.toLocaleString()}</td>
    </tr>
  );
}

function CausalityView({ report }: { report: ADRAnalysisReport }) {
  const c = report.causality;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Naranjo 得分" value={String(c.naranjo_score)} />
        <Metric label="Naranjo 分类" value={c.naranjo_category} />
        <Metric label="WHO-UMC" value={c.who_umc_category} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2 pr-3">评分项</th>
              <th className="py-2 pr-3">分值</th>
              <th className="py-2">依据</th>
            </tr>
          </thead>
          <tbody>
            {c.criteria.map((item) => (
              <tr key={item.criterion} className="border-b border-slate-100">
                <td className="py-2 pr-3 font-medium text-slate-800">{item.criterion}</td>
                <td className={`py-2 pr-3 font-semibold ${item.score > 0 ? "text-green-700" : item.score < 0 ? "text-red-700" : "text-slate-500"}`}>
                  {item.score > 0 ? `+${item.score}` : item.score}
                </td>
                <td className="py-2 text-slate-600">{item.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EvidenceView({ evidence }: { evidence: EvidenceItem[] }) {
  const groups = [
    { key: "high", label: "高置信证据" },
    { key: "moderate", label: "中置信证据" },
    { key: "low", label: "低置信证据" },
  ] as const;
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {groups.map((group) => {
        const items = evidence.filter((item) => item.strength === group.key);
        return (
          <div key={group.key} className="rounded-md border border-slate-200 p-3">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">{group.label}</h3>
            <div className="space-y-3">
              {items.map((item, idx) => (
                <div key={`${item.source}-${idx}`} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-800">{item.source}</span>
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">{item.source_type}</span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-slate-700">{item.summary}</p>
                  <p className="mt-2 text-xs text-slate-500">{item.stance}</p>
                </div>
              ))}
              {items.length === 0 && <p className="text-sm text-slate-400">暂无该等级证据</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GraphView({ report }: { report: ADRAnalysisReport }) {
  return <GraphView3D report={report} />;
}

function GraphView3D({ report }: { report: ADRAnalysisReport }) {
  const [selected, setSelected] = useState<GraphNode | null>(report.graph.nodes[0] ?? null);
  const [selectedLink, setSelectedLink] = useState<GraphLink | null>(null);
  const graphPreview = useMemo(() => adrGraphToNeo4jPreview(report), [report]);
  const selectedNode = selected ?? report.graph.nodes[0] ?? null;
  const highRiskNodes = report.graph.nodes.filter((node) => report.graph.highlighted_path.includes(node.id));
  const connectedLinks = selectedNode ? report.graph.links.filter((link) => link.source === selectedNode.id || link.target === selectedNode.id) : [];

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <div className="space-y-3">
        <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950 p-3">
          <div className="mb-3 flex items-start justify-between gap-3 text-slate-100">
            <div>
              <h3 className="text-sm font-semibold">Neo4j 3D ADR 证据图谱</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">WebGL force graph 展示 Drug / ADR / Evidence / Lab / Agent 节点；点击节点或边查看证据抽屉。</p>
            </div>
            <span className="rounded-full border border-rose-400/40 bg-rose-400/10 px-3 py-1 text-xs font-semibold text-rose-100">高危路径 {highRiskNodes.length} 节点</span>
          </div>
          <Suspense fallback={<div className="flex h-[430px] items-center justify-center rounded-md border border-slate-800 bg-slate-950 text-sm text-slate-400">正在加载 3D 图谱引擎...</div>}>
            <Neo4j3DGraph
              graph={graphPreview}
              selectedNodeId={selectedNode?.id}
              onNodeClick={(nodeId) => {
                setSelected(report.graph.nodes.find((node) => node.id === nodeId) ?? null);
                setSelectedLink(null);
              }}
              onLinkClick={(relationship) => setSelectedLink(findGraphLink(report.graph.links, relationship))}
            />
          </Suspense>
          <div className="mt-3 grid gap-2 text-xs text-slate-300 sm:grid-cols-3">
            <GraphLegend label="Drug" color="#60a5fa" />
            <GraphLegend label="ADR" color="#f87171" />
            <GraphLegend label="Evidence" color="#22d3ee" />
          </div>
        </div>
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-rose-950">高危路径</h4>
            <span className="text-xs font-semibold text-rose-700">{report.graph.highlighted_path.length} hops</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {highRiskNodes.map((node, index) => (
              <button key={node.id} onClick={() => setSelected(node)} className="rounded-md border border-rose-200 bg-white px-2 py-1 text-xs font-semibold text-rose-900 transition-colors hover:border-rose-400">
                {index + 1}. {node.label}
              </button>
            ))}
            {highRiskNodes.length === 0 && <span className="text-sm text-rose-700">当前报告未标注高危路径。</span>}
          </div>
        </div>
      </div>

      <aside className="rounded-lg border border-slate-800 bg-slate-950 p-4 text-slate-100">
        <h3 className="text-sm font-semibold">证据抽屉</h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">展示来自当前报告的节点、关系和证据链，不新增外部结论。</p>
        {selectedNode ? (
          <div className="mt-4">
            <div className="text-lg font-semibold">{selectedNode.label}</div>
            <div className="mt-2 text-xs text-slate-400">{selectedNode.type}</div>
            {selectedNode.risk && (
              <div className="mt-3 inline-flex rounded px-2 py-1 text-xs text-white" style={{ backgroundColor: SEVERITY_COLOR[selectedNode.risk] }}>
                {SEVERITY_CN[selectedNode.risk]}
              </div>
            )}
            <p className="mt-4 text-sm leading-relaxed text-slate-300">{selectedNode.detail || "暂无详情"}</p>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-400">请选择图谱节点。</p>
        )}

        {selectedLink && (
          <div className="mt-4 rounded-md border border-cyan-400/30 bg-cyan-400/10 p-3">
            <div className="text-xs font-semibold text-cyan-200">选中关系</div>
            <div className="mt-1 text-sm font-semibold text-white">{selectedLink.label}</div>
            <p className="mt-2 text-xs leading-relaxed text-cyan-50">{selectedLink.evidence || "该关系未提供额外证据文本。"}</p>
          </div>
        )}

        <div className="mt-4">
          <h4 className="text-xs font-semibold text-slate-300">相邻关系</h4>
          <div className="mt-2 space-y-2">
            {connectedLinks.map((link) => (
              <button key={`${link.source}-${link.target}-${link.type}`} onClick={() => setSelectedLink(link)} className="w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-left text-xs transition-colors hover:border-cyan-500/60">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-100">{link.label}</span>
                  <span className="text-slate-500">{link.type}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-slate-400">{link.evidence || "无额外证据文本"}</p>
              </button>
            ))}
            {connectedLinks.length === 0 && <p className="text-xs text-slate-500">当前节点暂无相邻关系。</p>}
          </div>
        </div>

        <div className="mt-4">
          <h4 className="text-xs font-semibold text-slate-300">报告证据链</h4>
          <div className="mt-2 max-h-56 space-y-2 overflow-y-auto pr-1">
            {report.evidence_chain.slice(0, 6).map((item, index) => (
              <div key={`${item.source}-${index}`} className="rounded-md border border-slate-800 bg-slate-900 px-3 py-2">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-semibold text-cyan-200">{item.source}</span>
                  <span className="text-slate-500">{item.strength}</span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-slate-400">{item.summary}</p>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function GraphLegend({ label, color }: { label: string; color: string }) {
  return (
    <div className="flex items-center gap-2 rounded border border-slate-800 bg-slate-900 px-2 py-1">
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 12px ${color}` }} />
      <span>{label}</span>
    </div>
  );
}

function findGraphLink(links: GraphLink[], relationship: Neo4jRelationship) {
  return (
    links.find((link) => link.source === relationship.source && link.target === relationship.target && toNeo4jRelType(link.type) === relationship.type) ??
    links.find((link) => link.source === relationship.target && link.target === relationship.source && toNeo4jRelType(link.type) === relationship.type) ??
    null
  );
}

function adrGraphToNeo4jPreview(report: ADRAnalysisReport): Neo4jGraphPreview {
  return {
    nodes: report.graph.nodes.map((node) => ({
      id: node.id,
      labels: [toNeo4jNodeLabel(node.type)],
      properties: {
        name: node.label,
        detail: node.detail,
        risk: node.risk,
        adr_type: node.type,
        highlighted: report.graph.highlighted_path.includes(node.id),
      },
    })),
    relationships: report.graph.links.map((link) => ({
      source: link.source,
      target: link.target,
      type: toNeo4jRelType(link.type),
      properties: {
        label: link.label,
        risk: link.risk,
        evidence: link.evidence,
      },
    })),
    cypher_examples: ["MATCH p=(d:Drug)-[:HAS_SIDE_EFFECT|INCREASES_RISK|SUPPORTED_BY*1..2]->(a:SideEffect) RETURN p LIMIT 25"],
  };
}

function toNeo4jNodeLabel(type: GraphNode["type"]) {
  if (type === "drug") return "Drug";
  if (type === "adr") return "SideEffect";
  if (type === "lab") return "Lab";
  if (type === "evidence" || type === "signal") return "Evidence";
  if (type === "patient_factor") return "PatientFactor";
  if (type === "recommendation") return "Recommendation";
  if (type === "agent") return "Agent";
  return "Mechanism";
}

function toNeo4jRelType(type: GraphLink["type"]) {
  if (type === "suspected_cause") return "HAS_SIDE_EFFECT";
  if (type === "increases_risk") return "INCREASES_RISK";
  if (type === "supported_by") return "SUPPORTED_BY";
  if (type === "detected_signal") return "DETECTED_SIGNAL";
  if (type === "monitored_by") return "MONITORED_BY";
  if (type === "evaluated_by") return "EVALUATED_BY";
  return "RECOMMENDED_ACTION";
}

function AIAssistantPanelLive({ report }: { report: ADRAnalysisReport }) {
  type AssistantMessage = PageChatMessage & {
    citations?: ChatCitation[];
    confidence?: number;
    used_agents?: string[];
  };
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const quickQuestions = [
    "为什么判断为 probable/likely？",
    "ROR 和 PRR 分别代表什么？",
    "这个病例最关键的停药或监测建议是什么？",
    "哪些证据只能支持相关性，不能证明因果？",
  ];

  const submitQuestion = async (text = question) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const userMessage: AssistantMessage = { role: "user", content: trimmed };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setQuestion("");
    setError(null);
    setLoading(true);
    try {
      const history = messages.map(({ role, content }) => ({ role, content }));
      const result = await api.chatADR(trimmed, report, history);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: result.answer,
          citations: result.citations,
          confidence: result.confidence,
          used_agents: result.used_agents,
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <aside className="rounded-lg border border-slate-800 bg-slate-950 p-4 text-slate-100 shadow-sm xl:sticky xl:top-24">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">常驻智能问答</h3>
          <p className="mt-1 text-xs text-slate-400">调用外部 LLM，基于当前报告和证据链回答</p>
        </div>
        <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(103,232,249,0.9)]" />
      </div>
      <div className="mt-4 rounded-md border border-slate-700 bg-slate-900 p-3">
        <p className="text-xs text-slate-400">当前上下文</p>
        <p className="mt-1 text-sm text-slate-200">{report.summary.suspected_drug} / {report.summary.suspected_adr}</p>
        <p className="mt-2 text-xs text-slate-400">已加载 {report.evidence_chain.length} 条证据、{report.graph.nodes.length} 个图谱节点。</p>
      </div>
      <div className="mt-4 space-y-2">
        {quickQuestions.map((item) => (
          <button key={item} onClick={() => submitQuestion(item)} disabled={loading} className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-left text-xs text-slate-200 transition-colors hover:bg-slate-800 disabled:opacity-60">
            {item}
          </button>
        ))}
      </div>
      <div className="mt-4 max-h-80 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs leading-relaxed text-slate-400">
            问答会读取当前病例报告、FAERS 信号、因果评分、证据链和图谱节点；未配置 LLM API 时会提示去系统配置页配置。
          </div>
        )}
        {messages.map((message, index) => <ChatBubble key={`${message.role}-${index}`} message={message} />)}
        {loading && <div className="rounded-md border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100">ReportQAAgent 正在生成带证据引用的回答...</div>}
      </div>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={4}
        className="mt-4 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
        placeholder="输入追问，例如：解释华法林和布洛芬联用出血机制"
      />
      <button onClick={() => submitQuestion()} disabled={loading || !question.trim()} className="mt-2 w-full rounded-md bg-cyan-500 px-3 py-2 text-sm font-semibold text-cyan-950 transition-colors hover:bg-cyan-400 disabled:bg-slate-700 disabled:text-white">
        {loading ? "问答 Agent 运行中" : "调度问答 Agent"}
      </button>
      {error && <p className="mt-3 rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-200">{error}</p>}
    </aside>
  );
}

function ChatBubble({ message }: { message: PageChatMessage & { citations?: ChatCitation[]; confidence?: number; used_agents?: string[] } }) {
  const isUser = message.role === "user";
  return (
    <div className={`rounded-md border px-3 py-2 text-sm leading-relaxed ${isUser ? "border-slate-700 bg-slate-900 text-white" : "border-cyan-400/30 bg-cyan-950/80 text-white"}`}>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{isUser ? "User" : "ReportQAAgent"}</div>
      <p className="preserve-whitespace mt-1">{message.content}</p>
      {!isUser && message.used_agents && message.used_agents.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {message.used_agents.map((agent) => <span key={agent} className="rounded border border-slate-600 px-1.5 py-0.5 text-[10px] text-slate-300">{agent}</span>)}
          {typeof message.confidence === "number" && <span className="rounded border border-emerald-400/40 px-1.5 py-0.5 text-[10px] text-emerald-200">置信度 {Math.round(message.confidence * 100)}%</span>}
        </div>
      )}
      {!isUser && message.citations && message.citations.length > 0 && (
        <div className="mt-2 space-y-1">
          {message.citations.slice(0, 4).map((citation) => (
            <div key={`${citation.source}-${citation.summary}`} className="rounded bg-slate-950/60 px-2 py-1 text-[11px] text-slate-300">
              <span className="text-cyan-200">[{citation.source}]</span> {citation.summary}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ReportText({ report }: { report: ADRAnalysisReport }) {
  return (
    <div className="space-y-4">
      <pre className="preserve-whitespace rounded-md border border-slate-200 bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-700">{report.final_report}</pre>
      <div>
        <h4 className="mb-2 text-sm font-semibold text-slate-800">系统限制</h4>
        <ul className="space-y-2 text-sm text-slate-600">
          {report.limitations.map((item) => <li key={item} className="rounded border border-slate-200 bg-slate-50 px-3 py-2">{item}</li>)}
        </ul>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${active ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
      {children}
    </button>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-2">
      <div className="text-sm font-semibold text-slate-800">{label}</div>
      <p className="mt-1 text-sm text-slate-600">{value}</p>
    </div>
  );
}
