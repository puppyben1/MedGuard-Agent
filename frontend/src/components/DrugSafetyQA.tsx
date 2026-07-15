import { useState } from "react";
import { api } from "../api";
import type { SafetyAssessment } from "../types";

interface Props {
  examples: string[];
  onAskDone?: () => void;
}

export default function DrugSafetyQA({ examples, onAskDone }: Props) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SafetyAssessment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async () => {
    if (!query.trim()) {
      setError("请输入问题");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.askQuestion(query);
      setResult(r);
      onAskDone?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
        <h2 className="text-base font-semibold text-slate-800 mb-2">💬 药物安全问答</h2>
        <p className="text-sm text-slate-500 mb-3">
          自然语言药物安全问答 — 检索药品说明书、医学文献与临床指南
        </p>

        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            placeholder="例如：华法林与阿司匹林联用有哪些风险？"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleAsk}
            disabled={loading}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white text-sm font-medium rounded-md transition-colors whitespace-nowrap"
          >
            {loading ? "查询中…" : "提问"}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-xs text-slate-500 self-center">示例问题：</span>
          {examples.map((q) => (
            <button
              key={q}
              onClick={() => setQuery(q)}
              className="px-2.5 py-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full transition-colors"
            >
              {q}
            </button>
          ))}
        </div>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </section>

      {loading && (
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-8 text-center">
          <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3" />
          <p className="text-sm text-slate-600">正在检索与生成回答…</p>
        </div>
      )}

      {result && !loading && <AssessmentView assessment={result} />}
    </div>
  );
}

function AssessmentView({ assessment }: { assessment: SafetyAssessment }) {
  const a = assessment;
  const riskColor =
    {
      low: "#16a34a",
      moderate: "#f59e0b",
      high: "#f97316",
      critical: "#dc2626",
      unknown: "#6b7280",
    }[a.risk_level] ?? "#6b7280";

  return (
    <div className="space-y-4">
      {/* Risk level + confidence */}
      <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-slate-600">风险等级：</span>
          <span
            className="px-2.5 py-0.5 text-sm font-bold text-white rounded-full"
            style={{ backgroundColor: riskColor }}
          >
            {a.risk_level}
          </span>
          <span className="text-xs text-slate-500">
            置信度：{(a.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div className="bg-blue-50 border-l-4 border-blue-400 px-4 py-3 text-sm text-slate-700 preserve-whitespace leading-relaxed">
          {a.summary}
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {a.contraindications.length > 0 && (
          <Section title="🚫 禁忌症" items={a.contraindications} />
        )}
        {a.monitoring.length > 0 && <Section title="👁️ 需要监测" items={a.monitoring} />}
        {a.citations.length > 0 && <Section title="📚 引用文献" items={a.citations} />}
      </div>
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
      <h3 className="text-base font-semibold text-slate-800 mb-2">{title}</h3>
      <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
        {items.map((c, i) => (
          <li key={i} className="leading-relaxed">
            {c}
          </li>
        ))}
      </ul>
    </section>
  );
}
