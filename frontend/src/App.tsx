/*
THESIS: MedGuard-Agent opens as a clinical safety scanner, refusing the generic dark dashboard hero.
OWN-WORLD: cool laboratory whites, graphite text, cyan instrument light, sparse risk color, and a translucent Halo scan ring.
STORY: a judge sees the case-to-evidence mechanism, checks runtime readiness, then enters one operational workflow.
FIRST VIEWPORT: compact top bar, left vertical module index, large Halo object center-left, proof copy and readiness stack at right.
FORM: clinical instrument deck, chosen as the primary structure for a competition demo surface.
*/
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { ADRExamplesResponse, ExamplesResponse, RuntimeConfigStatus } from "./types";
import PrescriptionReview from "./components/PrescriptionReview";
import DrugSafetyQA from "./components/DrugSafetyQA";
import ADRAnalysis from "./components/ADRAnalysis";
import ResearchMining from "./components/ResearchMining";
import PolypharmacyAnalysis from "./components/PolypharmacyAnalysis";
import SystemConfig from "./components/SystemConfig";

type Tab = "prescription" | "qa" | "adr" | "research" | "polypharmacy" | "config";

const NAV_ITEMS: { id: Tab; label: string; description: string; metric: string }[] = [
  { id: "adr", label: "ADR 全流程分析", description: "九大 Agent 个案会诊", metric: "Signal" },
  { id: "prescription", label: "处方审查", description: "规则 + RAG 证据核验", metric: "Review" },
  { id: "qa", label: "药物安全问答", description: "证据约束多轮咨询", metric: "RAG" },
  { id: "research", label: "科研批量挖掘", description: "SIDER/MedDRA 图谱", metric: "Graph" },
  { id: "polypharmacy", label: "多药高阶风险", description: "规则 + 图谱机制分析", metric: "HODDI" },
  { id: "config", label: "系统配置", description: "外部 API 与真实数据源", metric: "Runtime" },
];

const PIPELINE = [
  "病例语义解析",
  "药物/事件抽取",
  "FAERS 信号",
  "因果评分",
  "证据链报告",
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
    const id = setInterval(refreshConfig, 15000);
    return () => clearInterval(id);
  }, []);

  const activeItem = useMemo(
    () => NAV_ITEMS.find((item) => item.id === tab) ?? NAV_ITEMS[0],
    [tab],
  );

  return (
    <div className="clinical-shell min-h-screen text-slate-950">
      <div className="mx-auto flex min-h-screen w-full max-w-[1480px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <TopBar config={config} />
        <HeroDeck activeTab={tab} setTab={setTab} config={config} />

        <section className="workbench-shell mt-5">
          <div className="workbench-head">
            <div>
              <p className="section-kicker">Active Workbench</p>
              <h2>{activeItem.label}</h2>
              <p>{activeItem.description}</p>
            </div>
            <div className="workbench-mode">{activeItem.metric}</div>
          </div>

          <nav className="module-tabs" aria-label="MedGuard 功能模块">
            {NAV_ITEMS.map((item) => (
              <ModuleTab
                key={item.id}
                active={tab === item.id}
                onClick={() => setTab(item.id)}
                label={item.label}
                description={item.description}
              />
            ))}
          </nav>

          <main className="workbench-body">
            {tab === "prescription" && (
              examples ? (
                <PrescriptionReview
                  examples={examples.prescription_examples}
                  onReviewDone={() => api.config().then(setConfig)}
                />
              ) : (
                <LoadingWorkbench label="正在载入处方审查示例" />
              )
            )}
            {tab === "qa" && (
              examples ? (
                <DrugSafetyQA
                  examples={examples.qa_examples}
                  onAskDone={() => api.config().then(setConfig)}
                />
              ) : (
                <LoadingWorkbench label="正在载入药物安全问答示例" />
              )
            )}
            {tab === "adr" && (
              adrExamples ? (
                <ADRAnalysis examples={adrExamples.adr_examples} />
              ) : (
                <LoadingWorkbench label="正在载入 ADR 个案分析示例" />
              )
            )}
            {tab === "research" && <ResearchMining />}
            {tab === "polypharmacy" && <PolypharmacyAnalysis />}
            {tab === "config" && <SystemConfig />}
          </main>
        </section>

        <footer className="px-2 py-5 text-center text-xs text-slate-500">
          MedGuard-Agent 仅供临床决策辅助，不能替代医生或临床药师判断；FAERS/openFDA 信号代表报告关联，不等于因果证明。
        </footer>
      </div>
    </div>
  );
}

function TopBar({ config }: { config: RuntimeConfigStatus | null }) {
  return (
    <header className="topbar">
      <div className="brand-mark" aria-hidden="true">
        MG
      </div>
      <div className="min-w-0">
        <h1>MedGuard-Agent</h1>
        <p>多智能体药物安全风险分析与证据约束报告系统</p>
      </div>
      <div className="topbar-status">
        <StatusPill label="LLM" ok={Boolean(config?.has_llm_api_key)} />
        <StatusPill label="openFDA" ok={Boolean(config?.has_openfda_api_key || config?.strict_real_data)} />
        <StatusPill label="SIDER" ok={Boolean(config?.side_effect_zip_available)} />
      </div>
    </header>
  );
}

function HeroDeck({
  activeTab,
  setTab,
  config,
}: {
  activeTab: Tab;
  setTab: (tab: Tab) => void;
  config: RuntimeConfigStatus | null;
}) {
  const readyCount = [
    config?.has_llm_api_key,
    config?.has_openfda_api_key || config?.strict_real_data,
    config?.side_effect_zip_available,
  ].filter(Boolean).length;

  return (
    <section className="hero-deck">
      <div className="hero-index" aria-label="功能序列">
        <span className="hero-index-number">01</span>
        {NAV_ITEMS.slice(0, 4).map((item, index) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={activeTab === item.id ? "is-active" : ""}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            {item.metric}
          </button>
        ))}
      </div>

      <div className="halo-stage" aria-hidden="true">
        <div className="halo-orbit halo-orbit-back" />
        <div className="halo-orbit halo-orbit-front" />
        <div className="halo-core" />
        <div className="halo-sweep" />
        <span className="halo-node halo-node-a" />
        <span className="halo-node halo-node-b" />
        <span className="halo-node halo-node-c" />
      </div>

      <div className="hero-copy">
        <p className="section-kicker">Clinical Halo Intelligence</p>
        <h2>把自由文本病例扫描成可审计的 ADR 证据链。</h2>
        <p className="hero-lede">
          系统先抽取药物、事件和时间线，再联动 FAERS/openFDA 信号、Naranjo/WHO-UMC 因果评分与 RAG 证据核验，最终生成带不确定性说明的药物安全报告。
        </p>

        <div className="hero-actions">
          <button type="button" className="primary-action" onClick={() => setTab("adr")}>
            启动 ADR 分析
          </button>
          <button type="button" className="secondary-action" onClick={() => setTab("prescription")}>
            查看处方审查
          </button>
        </div>

        <div className="readiness-panel">
          <div>
            <span>Runtime readiness</span>
            <strong>{readyCount}/3</strong>
          </div>
          <div className="readiness-grid">
            <ReadinessDot label="LLM" ok={Boolean(config?.has_llm_api_key)} />
            <ReadinessDot label="openFDA" ok={Boolean(config?.has_openfda_api_key || config?.strict_real_data)} />
            <ReadinessDot label="SIDER/MedDRA" ok={Boolean(config?.side_effect_zip_available)} />
          </div>
        </div>
      </div>

      <div className="pipeline-strip" aria-label="分析流程">
        {PIPELINE.map((step, index) => (
          <div key={step}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function ModuleTab({
  active,
  onClick,
  label,
  description,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={active ? "module-tab is-active" : "module-tab"}
    >
      <span>{label}</span>
      <small>{description}</small>
    </button>
  );
}

function StatusPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={ok ? "status-pill is-ready" : "status-pill"}>
      <span>{label}</span>
      <strong>{ok ? "就绪" : "待配置"}</strong>
    </div>
  );
}

function ReadinessDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={ok ? "readiness-dot is-ready" : "readiness-dot"}>
      <i aria-hidden="true" />
      {label}
    </span>
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
