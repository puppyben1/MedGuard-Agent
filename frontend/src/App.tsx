/*
THESIS: MedGuard-Agent presents as a drug-safety research platform, not a generic admin dashboard.
OWN-WORLD: bright biomedical platform surfaces, blue-cyan molecular graph lines, dark slate workbench panels, and restrained clinical risk color.
STORY: a judge immediately understands the ADR pipeline, sees the real-source boundary, then enters the usable analysis workbench.
FIRST VIEWPORT: fixed platform nav, left hero offer and CTAs, right interactive-looking evidence graph console, with source readiness below.
FORM: MolHuiTu-inspired research platform landing/workbench hybrid, adapted to MedGuard's clinical safety constraints.
*/
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { ADRExamplesResponse, ExamplesResponse, RuntimeConfigStatus } from "./types";
import ADRAnalysis from "./components/ADRAnalysis";
import DrugSafetyQA from "./components/DrugSafetyQA";
import PolypharmacyAnalysis from "./components/PolypharmacyAnalysis";
import PrescriptionReview from "./components/PrescriptionReview";
import ResearchMining from "./components/ResearchMining";
import SystemConfig from "./components/SystemConfig";

type Tab = "adr" | "prescription" | "qa" | "research" | "polypharmacy" | "config";

const NAV_ITEMS: { id: Tab; label: string; description: string; metric: string }[] = [
  { id: "adr", label: "ADR 全流程", description: "个案抽取、信号、因果、报告", metric: "ADR" },
  { id: "research", label: "科研挖掘", description: "PubMed / BioDEX / GraphRAG", metric: "RAG" },
  { id: "polypharmacy", label: "多药风险", description: "规则、图谱、外部 DDI 证据", metric: "DDI" },
  { id: "prescription", label: "处方审查", description: "规则 + RAG 证据核验", metric: "Rx" },
  { id: "qa", label: "安全问答", description: "报告上下文常驻问答", metric: "QA" },
  { id: "config", label: "系统配置", description: "真实数据源与 API", metric: "Ops" },
];

const ARCHITECTURE = [
  {
    title: "LLM Schema 抽取",
    body: "从病例文本抽取疑似药物、ADR、时间轴、停药/再挑战和缺失信息；失败时明确进入 fallback。",
    source: "runtime LLM / fallback",
  },
  {
    title: "FAERS / openFDA 信号",
    body: "优先使用离线官方季度缓存或实时 openFDA；二乘二表、ROR/PRR 和来源类型分开展示。",
    source: "offline_faers / realtime_openfda",
  },
  {
    title: "SIDER/MedDRA RAG",
    body: "把本地 SIDER/MedDRA 构建为 JSONL、BM25、Chroma 与 Neo4j import 产物，作为可审计证据补充。",
    source: "offline_real_dataset",
  },
  {
    title: "Neo4j 3D 证据图谱",
    body: "Drug、SideEffect、Evidence、Mechanism 节点按类型着色，支持 live graph 查询和一跳/两跳展开。",
    source: "neo4j_live / graph_preview",
  },
];

const SCENARIOS = [
  ["临床 ADR 个案", "病例到证据链、因果评分、PDF 报告"],
  ["科研批量挖掘", "摘要、CSV、JSONL、PubMed、BioDEX"],
  ["多药高阶风险", "华法林 + NSAID + PPI 等组合机制"],
  ["真实数据运维", "Neo4j、FAERS、RAG、DDI 源缺失诊断"],
];

export default function App() {
  const [tab, setTab] = useState<Tab>("adr");
  const [examples, setExamples] = useState<ExamplesResponse | null>(null);
  const [adrExamples, setAdrExamples] = useState<ADRExamplesResponse | null>(null);
  const [config, setConfig] = useState<RuntimeConfigStatus | null>(null);

  useEffect(() => {
    api.examples().then(setExamples).catch(() => {});
    api.adrExamples().then(setAdrExamples).catch(() => {});
    const refreshConfig = () => api.config().then(setConfig).catch(() => {});
    refreshConfig();
    const id = window.setInterval(refreshConfig, 15000);
    return () => window.clearInterval(id);
  }, []);

  const activeItem = useMemo(() => NAV_ITEMS.find((item) => item.id === tab) ?? NAV_ITEMS[0], [tab]);

  return (
    <div className="platform-shell min-h-screen">
      <TopNav setTab={setTab} />

      <main className="mx-auto w-full max-w-[1480px] px-4 pb-8 pt-4 sm:px-6 lg:px-8">
        <HeroPlatform config={config} setTab={setTab} />
        <ArchitectureBand />
        <ScenarioBand />

        <section id="workbench" className="workbench-platform">
          <div className="workbench-platform__head">
            <div>
              <p className="platform-kicker">Active Workbench</p>
              <h2>{activeItem.label}</h2>
              <p>{activeItem.description}</p>
            </div>
            <span>{activeItem.metric}</span>
          </div>

          <nav className="platform-tabs" aria-label="MedGuard 功能模块">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={tab === item.id ? "is-active" : ""}
                onClick={() => setTab(item.id)}
              >
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </button>
            ))}
          </nav>

          <div className="workbench-platform__body">
            {tab === "adr" && (
              adrExamples ? <ADRAnalysis examples={adrExamples.adr_examples} /> : <LoadingWorkbench label="正在载入 ADR 个案分析示例" />
            )}
            {tab === "research" && <ResearchMining />}
            {tab === "polypharmacy" && <PolypharmacyAnalysis />}
            {tab === "prescription" && (
              examples ? (
                <PrescriptionReview examples={examples.prescription_examples} onReviewDone={() => api.config().then(setConfig)} />
              ) : (
                <LoadingWorkbench label="正在载入处方审查示例" />
              )
            )}
            {tab === "qa" && (
              examples ? (
                <DrugSafetyQA examples={examples.qa_examples} onAskDone={() => api.config().then(setConfig)} />
              ) : (
                <LoadingWorkbench label="正在载入药物安全问答示例" />
              )
            )}
            {tab === "config" && <SystemConfig />}
          </div>
        </section>

        <footer className="platform-footer">
          MedGuard-Agent 仅供临床决策辅助和科研展示；FAERS/openFDA/SIDER/MedDRA/Neo4j 结果均按来源类型标注，不等同于个体因果证明。
        </footer>
      </main>
    </div>
  );
}

function TopNav({ setTab }: { setTab: (tab: Tab) => void }) {
  return (
    <header className="platform-nav">
      <div className="platform-nav__inner">
        <button type="button" className="platform-brand" onClick={() => setTab("adr")}>
          <span>MG</span>
          <strong>MedGuard-Agent</strong>
        </button>
        <nav aria-label="平台导航">
          <a href="#architecture">核心技术架构</a>
          <a href="#scenarios">应用场景</a>
          <a href="#workbench">进入工作台</a>
          <button type="button" onClick={() => setTab("config")}>系统配置</button>
        </nav>
      </div>
    </header>
  );
}

function HeroPlatform({ config, setTab }: { config: RuntimeConfigStatus | null; setTab: (tab: Tab) => void }) {
  const readyCount = [
    config?.has_llm_api_key,
    config?.has_openfda_api_key || config?.strict_real_data,
    config?.side_effect_zip_available,
  ].filter(Boolean).length;

  return (
    <section className="platform-hero">
      <div className="platform-hero__copy">
        <p className="platform-kicker">AI Pharmacovigilance Platform</p>
        <h1>药物安全 ADR 多 Agent 分析平台</h1>
        <p>
          面向比赛展示和药学科研原型：把自由文本病例、文献摘要、FAERS/openFDA 信号、SIDER/MedDRA RAG 与 Neo4j 图谱组织成可追溯的药物安全证据链。
        </p>
        <div className="platform-actions">
          <button type="button" className="primary-action" onClick={() => setTab("adr")}>立即分析 ADR</button>
          <button type="button" className="secondary-action" onClick={() => setTab("research")}>查看科研挖掘</button>
        </div>
        <div className="source-readiness" aria-label="真实数据源状态">
          <Readiness label="LLM" ok={Boolean(config?.has_llm_api_key)} />
          <Readiness label="openFDA" ok={Boolean(config?.has_openfda_api_key || config?.strict_real_data)} />
          <Readiness label="SIDER/MedDRA" ok={Boolean(config?.side_effect_zip_available)} />
          <strong>{readyCount}/3 ready</strong>
        </div>
      </div>

      <div className="evidence-console" aria-label="MedGuard evidence graph visual">
        <div className="console-header">
          <span />
          <span />
          <span />
          <strong>Evidence Chain Runtime</strong>
        </div>
        <div className="molecular-stage">
          <div className="graph-node graph-node--drug">Drug</div>
          <div className="graph-node graph-node--adr">ADR</div>
          <div className="graph-node graph-node--faers">FAERS</div>
          <div className="graph-node graph-node--rag">RAG</div>
          <div className="graph-node graph-node--neo4j">Neo4j</div>
          <svg viewBox="0 0 520 360" role="img" aria-label="Drug ADR evidence graph">
            <path d="M112 178 C182 80 288 86 408 124" />
            <path d="M112 178 C190 246 282 274 410 220" />
            <path d="M220 82 C254 150 292 204 410 220" />
            <path d="M220 82 C262 70 328 74 408 124" />
            <path d="M112 178 C190 172 266 174 338 278" />
          </svg>
        </div>
        <div className="console-metrics">
          <Metric label="证据引用" value="citations" />
          <Metric label="因果评分" value="Naranjo" />
          <Metric label="图谱查询" value="Cypher" />
        </div>
      </div>
    </section>
  );
}

function ArchitectureBand() {
  return (
    <section id="architecture" className="platform-band">
      <div className="band-heading">
        <p className="platform-kicker">Core Architecture</p>
        <h2>从病例到证据图谱的真实化链路</h2>
        <p>每个模块都保留来源标签：demo、fallback、offline real dataset、realtime API、neo4j live 分开显示。</p>
      </div>
      <div className="architecture-grid">
        {ARCHITECTURE.map((item) => (
          <article key={item.title} className="architecture-card">
            <span>{item.source}</span>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ScenarioBand() {
  return (
    <section id="scenarios" className="scenario-band">
      <div className="band-heading">
        <p className="platform-kicker">Applications</p>
        <h2>比赛演示的四条主线</h2>
      </div>
      <div className="scenario-grid">
        {SCENARIOS.map(([title, body]) => (
          <article key={title}>
            <h3>{title}</h3>
            <p>{body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Readiness({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={ok ? "readiness-chip is-ready" : "readiness-chip"}>
      <i aria-hidden="true" />
      {label}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LoadingWorkbench({ label }: { label: string }) {
  return (
    <div className="loading-workbench">
      <div className="loading-ring" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}
