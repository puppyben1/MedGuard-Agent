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
  const [report, setReport] = useState<PolypharmacyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = async () => {
    const drugs = drugsText.split(/[,\n，]+/).map((item) => item.trim()).filter(Boolean);
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
          diagnoses: diagnoses.split(/[,\n，]+/).map((item) => item.trim()).filter(Boolean),
          labs: {},
        },
      });
      setReport(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-slate-100 shadow-lg shadow-slate-950/10">
        <div className="border-b border-slate-800 px-5 py-4">
          <p className="text-xs font-semibold text-cyan-300">Polypharmacy Mode</p>
          <h2 className="mt-1 text-xl font-semibold">多药高阶风险分析</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
            面向三联及以上用药组合，基于规则、患者因素、SIDER/MedDRA 和 FAERS 离线信号做可解释机制分析；当前不输出未经校准的风险增幅。
          </p>
        </div>
        <div className="grid gap-4 p-5 lg:grid-cols-[1fr_280px]">
          <div>
            <label className="text-xs font-medium text-slate-400">药物列表</label>
            <textarea
              value={drugsText}
              onChange={(e) => setDrugsText(e.target.value)}
              rows={5}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              placeholder="warfarin, ibuprofen, omeprazole"
            />
          </div>
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs font-medium text-slate-400">年龄</span>
              <input
                value={age}
                onChange={(e) => setAge(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-400">eGFR</span>
              <input
                value={egfr}
                onChange={(e) => setEgfr(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400"
                placeholder="可选"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-400">诊断</span>
              <input
                value={diagnoses}
                onChange={(e) => setDiagnoses(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400"
              />
            </label>
            <button
              onClick={analyze}
              disabled={loading}
              className="w-full rounded-md bg-cyan-400 px-4 py-2 text-sm font-semibold text-cyan-950 transition-colors hover:bg-cyan-300 disabled:bg-cyan-900 disabled:text-cyan-100"
            >
              {loading ? "分析中" : "分析高阶风险"}
            </button>
          </div>
        </div>
        {error && <p className="mx-5 mb-5 rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">{error}</p>}
      </section>

      {report ? (
        <div className="space-y-5">
          <Summary report={report} />
          <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              <HigherOrderPanel risks={report.higher_order_risks} />
              <PairwisePanel interactions={report.pairwise_interactions} />
              <SingleDrugPanel risks={report.single_drug_risks} />
            </div>
            <RecommendationPanel recommendations={report.recommendations} limitations={report.limitations} />
          </section>
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-800">机制图谱</h3>
                <p className="mt-1 text-sm text-slate-500">Drug / Mechanism / SideEffect 节点，仅展示当前规则和本地证据链路。</p>
              </div>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{report.mechanism_graph.nodes.length} nodes</span>
            </div>
            <Suspense fallback={<div className="h-72 rounded-md bg-slate-950 text-slate-400 flex items-center justify-center text-sm">加载 3D 图谱...</div>}>
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

function Summary({ report }: { report: PolypharmacyReport }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-slate-500">综合高阶风险</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">{report.drugs.join(" + ")}</h3>
        </div>
        <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${SEVERITY_CLASS[report.overall_risk_level]}`}>
          {SEVERITY_CN[report.overall_risk_level]}
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-4">
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
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-800">高阶风险</h3>
      <div className="mt-3 space-y-3">
        {risks.map((risk) => (
          <RiskBlock key={risk.risk} severity={risk.severity} title={risk.risk} meta={risk.evidence_level}>
            <p>{risk.mechanism}</p>
            <p className="mt-2 text-xs text-slate-500">{risk.rationale}</p>
          </RiskBlock>
        ))}
        {risks.length === 0 && <p className="text-sm text-slate-500">未命中内置高阶风险规则。</p>}
      </div>
    </section>
  );
}

function PairwisePanel({ interactions }: { interactions: PairwiseInteraction[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-800">两两相互作用</h3>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {interactions.map((item) => (
          <RiskBlock key={`${item.drugs.join("-")}-${item.risk}`} severity={item.severity} title={item.drugs.join(" + ")} meta={item.risk}>
            <p>{item.mechanism}</p>
            <p className="mt-2 text-xs text-slate-500">{item.recommendation}</p>
          </RiskBlock>
        ))}
        {interactions.length === 0 && <p className="text-sm text-slate-500">未命中内置两两相互作用规则。</p>}
      </div>
    </section>
  );
}

function SingleDrugPanel({ risks }: { risks: SingleDrugRisk[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-800">单药证据</h3>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {risks.map((risk) => (
          <RiskBlock key={`${risk.drug}-${risk.risk}`} severity={risk.severity} title={risk.drug} meta={risk.risk}>
            <p>{risk.rationale}</p>
            <p className="mt-2 text-xs text-slate-500">{risk.evidence_source}</p>
          </RiskBlock>
        ))}
        {risks.length === 0 && <p className="text-sm text-slate-500">未命中单药风险或本地 RAG 证据。</p>}
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
    <aside className="rounded-lg border border-slate-800 bg-slate-950 p-5 text-slate-100 shadow-sm xl:sticky xl:top-24">
      <h3 className="text-base font-semibold">处置建议</h3>
      <div className="mt-3 space-y-3">
        {recommendations.map((item) => (
          <div key={`${item.priority}-${item.text}`} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2">
            <div className="text-xs font-semibold text-cyan-300">{item.priority}</div>
            <p className="mt-1 text-sm leading-relaxed text-slate-100">{item.text}</p>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">{item.rationale}</p>
          </div>
        ))}
      </div>
      <h4 className="mt-5 text-xs font-semibold text-slate-300">限制说明</h4>
      <ul className="mt-2 space-y-2 text-xs leading-relaxed text-slate-400">
        {limitations.map((item) => (
          <li key={item} className="rounded border border-slate-800 bg-slate-900/60 px-2 py-2">{item}</li>
        ))}
      </ul>
    </aside>
  );
}

function RiskBlock({
  severity,
  title,
  meta,
  children,
}: {
  severity: Severity;
  title: string;
  meta: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
          <p className="mt-1 text-xs text-slate-500">{meta}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${SEVERITY_CLASS[severity]}`}>
          {SEVERITY_CN[severity]}
        </span>
      </div>
      <div className="mt-2 text-sm leading-relaxed text-slate-700">{children}</div>
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
