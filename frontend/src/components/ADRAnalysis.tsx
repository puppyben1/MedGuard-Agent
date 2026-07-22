import { useMemo, useState } from "react";
import { api } from "../api";
import type {
  ADRAnalysisReport,
  ADRExample,
  EvidenceItem,
  GraphNode,
  Severity,
  SignalLevel,
  TimelineEvent,
} from "../types";

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

  return (
    <div className="space-y-5">
      <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold text-slate-800">ADR 全流程分析</h2>
            <p className="text-sm text-slate-500 mt-1">
              输入病例后，系统会串联 ADR 抽取、FAERS 信号、处方风险、因果评价、证据链和图谱展示。
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700 bg-slate-50 px-3 py-2 rounded-md border border-slate-200">
            <input
              type="checkbox"
              checked={realtime}
              onChange={(e) => setRealtime(e.target.checked)}
              className="h-4 w-4 accent-blue-600"
            />
            启用实时 openFDA 查询
          </label>
        </div>

        <div className="mt-4 grid lg:grid-cols-[1.25fr_0.75fr] gap-4">
          <div>
            <textarea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              rows={7}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              placeholder="粘贴病例、主诉或处方文本..."
            />
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={runAnalysis}
                disabled={loading}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white text-sm font-medium rounded-md transition-colors"
              >
                {loading ? "分析中..." : "开始 ADR 分析"}
              </button>
              {error && <span className="text-sm text-red-600">{error}</span>}
            </div>
          </div>

          <div>
            <p className="text-xs text-slate-500 mb-2">8 个稳定演示病例</p>
            <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-2 max-h-48 overflow-y-auto pr-1">
              {examples.map((ex) => (
                <button
                  key={ex.id}
                  onClick={() => setCaseText(ex.case_text)}
                  className="text-left px-3 py-2 bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 rounded-md transition-colors"
                >
                  <div className="text-sm font-medium text-slate-800">{ex.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {ex.drug} / {ex.adr}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {loading && (
        <section className="bg-white border border-slate-200 rounded-lg p-8 text-center">
          <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3" />
          <p className="text-sm text-slate-600">正在执行多 Agent ADR 分析流程...</p>
        </section>
      )}

      {report && !loading && (
        <>
          <SummaryPanel report={report} />
          <AgentFlow report={report} />
          <section className="bg-white border border-slate-200 rounded-lg shadow-sm">
            <div className="px-4 pt-3 border-b border-slate-200 flex gap-1 overflow-x-auto">
              <TabButton active={activeTab === "extract"} onClick={() => setActiveTab("extract")}>抽取结果</TabButton>
              <TabButton active={activeTab === "timeline"} onClick={() => setActiveTab("timeline")}>时间轴</TabButton>
              <TabButton active={activeTab === "signal"} onClick={() => setActiveTab("signal")}>FAERS 信号</TabButton>
              <TabButton active={activeTab === "causality"} onClick={() => setActiveTab("causality")}>因果评分</TabButton>
              <TabButton active={activeTab === "evidence"} onClick={() => setActiveTab("evidence")}>证据链</TabButton>
              <TabButton active={activeTab === "graph"} onClick={() => setActiveTab("graph")}>3D 图谱</TabButton>
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
        </>
      )}
    </div>
  );
}

function SummaryPanel({ report }: { report: ADRAnalysisReport }) {
  const risk = report.summary.overall_risk_level;
  const sourceText =
    report.source_mode === "realtime_openfda"
      ? "实时 openFDA"
      : report.source_mode === "fallback_demo"
        ? "实时失败，回退本地 demo"
        : "本地演示 FAERS";
  return (
    <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
      <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
        <div>
          <p className="text-xs text-slate-500">综合结论</p>
          <h3 className="text-lg font-semibold text-slate-900 mt-1">
            {report.summary.suspected_drug} 与 {report.summary.suspected_adr}
          </h3>
        </div>
        <span
          className="px-3 py-1 rounded-full text-sm font-semibold text-white"
          style={{ backgroundColor: SEVERITY_COLOR[risk] }}
        >
          {SEVERITY_CN[risk]}
        </span>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <Metric label="疑似药物" value={report.summary.suspected_drug} />
        <Metric label="疑似 ADR" value={report.summary.suspected_adr} />
        <Metric label="FAERS 信号" value={SIGNAL_CN[report.summary.signal_level]} />
        <Metric label="因果等级" value={report.summary.causality_level} />
        <Metric label="数据来源" value={sourceText} />
      </div>
      <div className="mt-4 bg-blue-50 border-l-4 border-blue-400 px-4 py-3 text-sm text-slate-700 leading-relaxed">
        {report.summary.recommendation}
      </div>
    </section>
  );
}

function AgentFlow({ report }: { report: ADRAnalysisReport }) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
      <h3 className="text-base font-semibold text-slate-800 mb-3">多 Agent 执行流程</h3>
      <div className="grid md:grid-cols-3 xl:grid-cols-6 gap-3">
        {report.agent_steps.map((step, idx) => (
          <div key={step.name} className="relative bg-slate-50 border border-slate-200 rounded-md p-3 min-h-28">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-blue-700">Step {idx + 1}</span>
              <span className="w-2 h-2 rounded-full bg-green-500" />
            </div>
            <div className="text-sm font-semibold text-slate-800 mt-2">{step.name}</div>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">{step.summary}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExtractionView({ report }: { report: ADRAnalysisReport }) {
  const ex = report.extraction;
  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-800 mb-3">结构化 ADR 个案</h3>
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
        <h3 className="text-sm font-semibold text-slate-800 mb-3">因果线索</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          <Metric label="抽取置信度" value={`${Math.round(ex.extraction_confidence * 100)}%`} />
          <Metric label="停药反应" value={ex.dechallenge.available ? ex.dechallenge.result : "未描述"} />
          <Metric label="再给药" value={ex.rechallenge.available ? ex.rechallenge.result : "未描述"} />
          <Metric label="合并用药" value={ex.concomitant_drugs.join("，") || "无"} />
        </div>
        {ex.objective_evidence.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {ex.objective_evidence.map((item) => (
              <span key={item} className="px-2 py-1 text-xs bg-emerald-50 text-emerald-700 border border-emerald-100 rounded">
                {item}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineView({ events }: { events: TimelineEvent[] }) {
  return (
    <div className="space-y-3">
      {events.map((event, idx) => (
        <div key={`${event.event_type}-${idx}`} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-semibold flex items-center justify-center">
              {idx + 1}
            </div>
            {idx < events.length - 1 && <div className="w-px flex-1 bg-slate-200" />}
          </div>
          <div className="pb-4">
            <div className="text-sm font-semibold text-slate-800">{event.label}</div>
            <div className="text-xs text-slate-500 mt-0.5">{event.time_text}</div>
            <p className="text-sm text-slate-700 mt-1">{event.description}</p>
            <p className="text-xs text-blue-700 mt-1">{event.risk_relevance}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function SignalView({ report }: { report: ADRAnalysisReport }) {
  const s = report.faers_signal;
  const maxTrend = Math.max(...s.yearly_trend.map((p) => p.reports), 1);
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <Metric label="报告数" value={s.report_count.toLocaleString()} />
        <Metric label="严重病例" value={s.serious_count.toLocaleString()} />
        <Metric label="死亡报告" value={s.death_count.toLocaleString()} />
        <Metric label="ROR" value={s.ror?.toString() ?? "—"} />
        <Metric label="PRR" value={s.prr?.toString() ?? "—"} />
      </div>
      <p className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-md px-3 py-2">
        {s.clinical_interpretation}
      </p>
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <h4 className="text-sm font-semibold text-slate-800 mb-2">年度趋势</h4>
          <div className="h-48 border border-slate-200 rounded-md p-3 flex items-end gap-2">
            {s.yearly_trend.map((point) => (
              <div key={point.year} className="flex-1 flex flex-col items-center justify-end gap-1">
                <div className="w-full bg-blue-500 rounded-t" style={{ height: `${(point.reports / maxTrend) * 150}px` }} />
                <span className="text-[11px] text-slate-500">{point.year}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-slate-800 mb-2">限制说明</h4>
          <ul className="text-sm text-slate-600 space-y-2">
            {s.limitations.map((item) => (
              <li key={item} className="bg-amber-50 border border-amber-100 px-3 py-2 rounded">{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function CausalityView({ report }: { report: ADRAnalysisReport }) {
  const c = report.causality;
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-3">
        <Metric label="Naranjo 得分" value={String(c.naranjo_score)} />
        <Metric label="Naranjo 分类" value={c.naranjo_category} />
        <Metric label="WHO-UMC" value={c.who_umc_category} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
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
  return (
    <div className="grid md:grid-cols-2 gap-3">
      {evidence.map((item, idx) => (
        <div key={`${item.source}-${idx}`} className="border border-slate-200 rounded-md p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-slate-800">{item.source}</span>
            <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full">{item.strength}</span>
          </div>
          <p className="text-sm text-slate-700 mt-2 leading-relaxed">{item.summary}</p>
          <p className="text-xs text-slate-500 mt-2">{item.source_type} / {item.stance}</p>
        </div>
      ))}
    </div>
  );
}

function GraphView({ report }: { report: ADRAnalysisReport }) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const layout = useMemo(() => layoutNodes(report.graph.nodes), [report.graph.nodes]);
  const selectedNode = selected ?? report.graph.nodes[0] ?? null;

  return (
    <div className="grid lg:grid-cols-[1fr_280px] gap-4">
      <div className="relative min-h-[520px] rounded-lg overflow-hidden border border-slate-800 bg-[#07111f]">
        <div className="absolute inset-0 adr-grid-bg" />
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 900 520" preserveAspectRatio="none">
          {report.graph.links.map((link, idx) => {
            const s = layout[link.source];
            const t = layout[link.target];
            if (!s || !t) return null;
            const color = link.risk ? SEVERITY_COLOR[link.risk] : "#38bdf8";
            return (
              <g key={`${link.source}-${link.target}-${idx}`}>
                <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke={color} strokeWidth={link.risk === "critical" ? 3 : 1.6} opacity={0.72} />
                <text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 4} fill="#cbd5e1" fontSize="11" textAnchor="middle">{link.label}</text>
              </g>
            );
          })}
        </svg>
        {report.graph.nodes.map((node) => {
          const pos = layout[node.id];
          if (!pos) return null;
          const color = node.risk ? SEVERITY_COLOR[node.risk] : node.type === "evidence" ? "#38bdf8" : "#22c55e";
          const inPath = report.graph.highlighted_path.includes(node.id);
          return (
            <button
              key={node.id}
              onClick={() => setSelected(node)}
              className="absolute -translate-x-1/2 -translate-y-1/2 text-center group"
              style={{
                left: `${(pos.x / 900) * 100}%`,
                top: `${(pos.y / 520) * 100}%`,
                transform: `translate(-50%, -50%) translateZ(${pos.z}px)`,
              }}
            >
              <span
                className={`block mx-auto rounded-full border transition-transform group-hover:scale-110 ${inPath ? "w-16 h-16" : "w-12 h-12"}`}
                style={{
                  background: `radial-gradient(circle at 35% 30%, #ffffff, ${color})`,
                  borderColor: color,
                  boxShadow: `0 0 ${inPath ? 30 : 18}px ${color}`,
                }}
              />
              <span className="block mt-2 max-w-28 text-[11px] text-slate-100 leading-tight drop-shadow">
                {node.label}
              </span>
            </button>
          );
        })}
        <div className="absolute left-4 top-4 text-slate-100">
          <div className="text-sm font-semibold">ADR 证据图谱</div>
          <div className="text-xs text-slate-400 mt-1">高危路径已高亮，点击节点查看解释</div>
        </div>
      </div>

      <aside className="bg-slate-900 text-slate-100 rounded-lg p-4 border border-slate-700">
        <h3 className="text-sm font-semibold mb-3">节点详情</h3>
        {selectedNode ? (
          <div>
            <div className="text-lg font-semibold">{selectedNode.label}</div>
            <div className="mt-2 text-xs text-slate-400">{selectedNode.type}</div>
            {selectedNode.risk && (
              <div className="mt-3 inline-flex px-2 py-1 rounded text-xs text-white" style={{ backgroundColor: SEVERITY_COLOR[selectedNode.risk] }}>
                {SEVERITY_CN[selectedNode.risk]}
              </div>
            )}
            <p className="text-sm text-slate-300 leading-relaxed mt-4">{selectedNode.detail || "暂无详情"}</p>
          </div>
        ) : (
          <p className="text-sm text-slate-400">请选择图谱节点。</p>
        )}
      </aside>
    </div>
  );
}

function ReportText({ report }: { report: ADRAnalysisReport }) {
  return (
    <div className="space-y-4">
      <pre className="preserve-whitespace text-sm text-slate-700 leading-relaxed bg-slate-50 border border-slate-200 rounded-md p-4 font-sans">
        {report.final_report}
      </pre>
      <div>
        <h4 className="text-sm font-semibold text-slate-800 mb-2">系统限制</h4>
        <ul className="text-sm text-slate-600 space-y-2">
          {report.limitations.map((item) => (
            <li key={item} className="bg-slate-50 border border-slate-200 rounded px-3 py-2">{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-2 text-sm font-medium border-b-2 whitespace-nowrap ${
        active ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-md px-3 py-2 border border-slate-100">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-slate-800 mt-0.5 break-words">{value}</div>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-slate-200 rounded-md px-3 py-2">
      <div className="text-sm font-semibold text-slate-800">{label}</div>
      <p className="text-sm text-slate-600 mt-1">{value}</p>
    </div>
  );
}

function layoutNodes(nodes: GraphNode[]): Record<string, { x: number; y: number; z: number }> {
  const center = { x: 450, y: 250, z: 80 };
  const positions: Record<string, { x: number; y: number; z: number }> = {};
  const adr = nodes.find((node) => node.type === "adr");
  if (adr) positions[adr.id] = center;

  const radiusX = 300;
  const radiusY = 170;
  const rest = nodes.filter((node) => node.id !== adr?.id);
  rest.forEach((node, idx) => {
    const angle = (idx / Math.max(rest.length, 1)) * Math.PI * 2 - Math.PI / 2;
    positions[node.id] = {
      x: 450 + Math.cos(angle) * radiusX,
      y: 250 + Math.sin(angle) * radiusY,
      z: idx % 2 === 0 ? 45 : -25,
    };
  });
  return positions;
}
