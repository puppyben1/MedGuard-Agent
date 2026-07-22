import { useEffect, useState } from "react";
import { api } from "./api";
import type { ADRExamplesResponse, ExamplesResponse, HealthResponse } from "./types";
import PrescriptionReview from "./components/PrescriptionReview";
import DrugSafetyQA from "./components/DrugSafetyQA";
import ADRAnalysis from "./components/ADRAnalysis";

type Tab = "prescription" | "qa" | "adr";

export default function App() {
  const [tab, setTab] = useState<Tab>("prescription");
  const [examples, setExamples] = useState<ExamplesResponse | null>(null);
  const [adrExamples, setAdrExamples] = useState<ADRExamplesResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api.examples().then(setExamples).catch(() => {});
    api.adrExamples().then(setAdrExamples).catch(() => {});
    const refreshHealth = () => api.health().then(setHealth).catch(() => {});
    refreshHealth();
    const id = setInterval(refreshHealth, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl">💊</span>
            <div>
              <h1 className="text-lg font-bold text-slate-800">MedGuard-Agent</h1>
              <p className="text-xs text-slate-500">证据约束的临床处方审查智能体</p>
            </div>
          </div>
          {health && (
            <div className="text-xs text-slate-600 flex gap-4">
              <span>
                生成器剩余调用次数{" "}
                <span className="font-semibold text-slate-800">
                  {health.generator_budget_remaining.toLocaleString()}
                </span>
              </span>
              <span>
                路由器剩余调用次数{" "}
                <span className="font-semibold text-slate-800">
                  {health.router_budget_remaining.toLocaleString()}
                </span>
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Tabs */}
      <nav className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 flex gap-1">
          <TabButton active={tab === "prescription"} onClick={() => setTab("prescription")}>
            📝 处方审查
          </TabButton>
          <TabButton active={tab === "qa"} onClick={() => setTab("qa")}>
            💬 药物安全问答
          </TabButton>
          <TabButton active={tab === "adr"} onClick={() => setTab("adr")}>
            ADR 全流程分析
          </TabButton>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {tab === "prescription" && examples && <PrescriptionReview examples={examples.prescription_examples} onReviewDone={() => api.health().then(setHealth)} />}
        {tab === "qa" && examples && <DrugSafetyQA examples={examples.qa_examples} onAskDone={() => api.health().then(setHealth)} />}
        {tab === "adr" && adrExamples && <ADRAnalysis examples={adrExamples.adr_examples} />}
      </main>

      <footer className="max-w-6xl mx-auto px-4 py-6 text-center text-xs text-slate-400">
        MedGuard-Agent · 仅供临床决策辅助，不能替代专业医师判断
      </footer>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
        active
          ? "border-blue-600 text-blue-600"
          : "border-transparent text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}
