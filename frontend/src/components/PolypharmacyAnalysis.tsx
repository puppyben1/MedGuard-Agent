import { lazy, Suspense, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import type {
  HigherOrderRisk,
  PairwiseInteraction,
  PolypharmacyRecommendation,
  PolypharmacyReport,
  Severity,
  SingleDrugRisk,
} from "../types";

const Neo4j3DGraph = lazy(() => import("./Neo4j3DGraph"));

const SEVERITY_CN: Record<Severity, string> = {
  low: "低",
  moderate: "中",
  high: "高",
  critical: "严重",
};

const SEVERITY_CLASS: Record<Severity, string> = {
  low: "bg-emerald-100 text-emerald-800 border-emerald-200",
  moderate: "bg-amber-100 text-amber-800 border-amber-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  critical: "bg-red-100 text-red-800 border-red-200",
};

export default function PolypharmacyAnalysis() {
  const [drugsText, setDrugsText] = useState("warfarin, ibuprofen, omeprazole");
  const [age, setAge] = useState("78");
  const [egfr, setEgfr] = useState("");
  const [diagnoses, setDiagnoses] = useState("atrial fibrillation");
  const [externalEvidencePath, setExternalEvidencePath] = useState("");
  const [report, setReport] = useState<PolypharmacyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const analyze = async () => {
    const drugs = splitList(drugsText);
    if (drugs.length < 2) {
      setError("至少输入 2 个药物");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await api.analyzePolypharmacy({
        drugs,
        patient: {
          age: age ? Number(age) : null,
          eGFR: egfr ? Number(egfr) : null,
          diagnoses: splitList(diagnoses),
          labs: {},
        },
        external_evidence_path: externalEvidencePath.trim() || undefined,
      });
      setReport(next);
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
      const blob = await api.downloadPolypharmacyReportPdf(report);
      downloadBlob(blob, "medguard-polypharmacy-report.pdf");
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : String(e));
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-slate-100 shadow-lg shadow-slate-950/10">
        <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
          <p className="text-xs font-semibold text-cyan-300">Polypharmacy Mode</p>
          <h2 className="mt-1 text-xl font-semibold">多药高阶风险分析</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
            面向三联及以上用药组合，基于规则、患者因素、SIDER/MedDRA、FAERS 离线信号和可选外部 DDI/DrugBank 风格证据做可解释机制分析。
          </p>
        </div>
        <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-[1fr_320px]">
          <label className="block">
            <span className="text-xs font-medium text-slate-400">药物列表</span>
            <textarea
              value={drugsText}
              onChange={(e) => setDrugsText(e.target.value)}
              rows={6}
              className="mt-1 min-h-36 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              placeholder="warfarin, ibuprofen, omeprazole"
            />
          </label>
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs font-medium text-slate-400">年龄</span>
              <input
                value={age}
                onChange={(e) => setAge(e.target.value)}
                className="mt-1 min-h-11 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-400">eGFR</span>
              <input
                value={egfr}
                onChange={(e) => setEgfr(e.target.value)}
                className="mt-1 min-h-11 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400"
                placeholder="可选"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-400">诊断背景</span>
              <input
                value={diagnoses}
                onChange={(e) => setDiagnoses(e.target.value)}
                className="mt-1 min-h-11 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-400">外部 DDI/DrugBank 风格证据路径</span>
              <input
                value={externalEvidencePath}
                onChange={(e) => setExternalEvidencePath(e.target.value)}
                className="mt-1 min-h-11 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-400"
                placeholder="可选，如 data/interactions/drug_interactions.csv"
              />
            </label>
            <button
              onClick={analyze}
              disabled={loading}
              className="min-h-11 w-full rounded-md bg-cyan-400 px-4 py-2 text-sm font-semibold text-cyan-950 transition-colors hover:bg-cyan-300 disabled:bg-cyan-900 disabled:text-cyan-100"
            >
              {loading ? "分析中" : "分析高阶风险"}
            </button>
          </div>
        </div>
        {error && <p className="mx-4 mb-4 rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-red-200 sm:mx-5">{error}</p>}
      </section>

      {report ? (
        <div className="space-y-5">
          <Summary report={report} onDownloadPdf={downloadPdf} pdfLoading={pdfLoading} />
          {pdfError && (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              PDF 导出失败：{pdfError}
            </p>
          )}
          <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              <HigherOrderPanel risks={report.higher_order_risks} />
              <PairwisePanel interactions={report.pairwise_interactions} />
              <SingleDrugPanel risks={report.single_drug_risks} />
            </div>
            <RecommendationPanel recommendations={report.recommendations} limitations={report.limitations} />
          </section>
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-800">机制图谱</h3>
                <p className="mt-1 text-sm text-slate-500">Drug / Mechanism / SideEffect 节点，仅展示当前规则、本地证据和可选外部证据链路。</p>
              </div>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{report.mechanism_graph.nodes.length} nodes</span>
            </div>
            <Suspense fallback={<div className="flex h-72 items-center justify-center rounded-md bg-slate-950 text-sm text-slate-400">加载 3D 图谱...</div>}>
              <Neo4j3DGraph graph={report.mechanism_graph} compact />
            </Suspense>
          </section>
        </div>
      ) : (
        <section className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          输入 2 个及以上药物和患者因素后，查看单药风险、两两相互作用、高阶机制和审慎建议。
        </section>
      )}
    </div>
  );
}

function Summary({
  report,
  onDownloadPdf,
  pdfLoading,
}: {
  report: PolypharmacyReport;
  onDownloadPdf: () => void;
  pdfLoading: boolean;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-slate-500">综合高阶风险</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">{report.drugs.join(" + ")}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${SEVERITY_CLASS[report.overall_risk_level]}`}>
            {SEVERITY_CN[report.overall_risk_level]}
          </span>
          <button
            onClick={onDownloadPdf}
            disabled={pdfLoading}
            className="min-h-10 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:border-cyan-400 disabled:opacity-50"
          >
            {pdfLoading ? "生成 PDF..." : "下载 PDF 报告"}
          </button>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="单药风险" value={report.single_drug_risks.length.toString()} />
        <Metric label="两两相互作用" value={report.pairwise_interactions.length.toString()} />
        <Metric label="高阶风险" value={report.higher_order_risks.length.toString()} />
        <Metric label="source" value={report.source_type} />
      </div>
    </section>
  );
}

function HigherOrderPanel({ risks }: { risks: HigherOrderRisk[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <h3 className="text-base font-semibold text-slate-800">高阶风险</h3>
      <div className="mt-3 space-y-3">
        {risks.map((risk) => (
          <RiskCard key={`${risk.risk}-${risk.drugs.join("-")}`} title={risk.risk} severity={risk.severity} subtitle={risk.drugs.join(" + ")}>
            <p>{risk.mechanism}</p>
            <p className="mt-2 text-slate-500">{risk.rationale}</p>
          </RiskCard>
        ))}
        {risks.length === 0 && <EmptyText>未命中内置高阶风险规则；这不代表无风险。</EmptyText>}
      </div>
    </section>
  );
}

function PairwisePanel({ interactions }: { interactions: PairwiseInteraction[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <h3 className="text-base font-semibold text-slate-800">两两相互作用</h3>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {interactions.map((item) => (
          <RiskCard key={`${item.risk}-${item.drugs.join("-")}`} title={item.risk} severity={item.severity} subtitle={item.drugs.join(" + ")}>
            <p>{item.mechanism}</p>
            <p className="mt-2 text-slate-500">{item.recommendation}</p>
            <p className="mt-2 text-xs text-slate-400">source: {item.evidence_source}</p>
          </RiskCard>
        ))}
        {interactions.length === 0 && <EmptyText>未命中两两相互作用证据。</EmptyText>}
      </div>
    </section>
  );
}

function SingleDrugPanel({ risks }: { risks: SingleDrugRisk[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <h3 className="text-base font-semibold text-slate-800">单药证据</h3>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {risks.map((risk) => (
          <RiskCard key={`${risk.drug}-${risk.risk}`} title={risk.risk} severity={risk.severity} subtitle={risk.drug}>
            <p>{risk.rationale}</p>
            <p className="mt-2 text-xs text-slate-400">source: {risk.evidence_source}</p>
          </RiskCard>
        ))}
        {risks.length === 0 && <EmptyText>未命中单药风险证据。</EmptyText>}
      </div>
    </section>
  );
}

function RecommendationPanel({
  recommendations,
  limitations,
}: {
  recommendations: PolypharmacyRecommendation[];
  limitations: string[];
}) {
  return (
    <aside className="rounded-lg border border-slate-800 bg-slate-950 p-4 text-slate-100 shadow-sm sm:p-5 xl:sticky xl:top-24">
      <h3 className="text-base font-semibold">处置建议</h3>
      <div className="mt-3 space-y-3">
        {recommendations.map((item) => (
          <div key={`${item.priority}-${item.text}`} className="rounded-md border border-slate-800 bg-slate-900 p-3">
            <div className="text-xs font-semibold text-cyan-300">{item.priority}</div>
            <p className="mt-1 text-sm leading-relaxed">{item.text}</p>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">{item.rationale}</p>
          </div>
        ))}
      </div>
      <h4 className="mt-5 text-sm font-semibold text-slate-200">限制说明</h4>
      <ul className="mt-2 space-y-2 text-xs leading-relaxed text-slate-400">
        {limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </aside>
  );
}

function RiskCard({
  title,
  subtitle,
  severity,
  children,
}: {
  title: string;
  subtitle: string;
  severity: Severity;
  children: ReactNode;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${SEVERITY_CLASS[severity]}`}>{SEVERITY_CN[severity]}</span>
      </div>
      <div className="mt-3 text-sm leading-relaxed text-slate-600">{children}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function EmptyText({ children }: { children: ReactNode }) {
  return <p className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">{children}</p>;
}

function splitList(value: string) {
  return value
    .split(/[,\n，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
