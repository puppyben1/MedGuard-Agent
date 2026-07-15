import { useState } from "react";
import { api } from "../api";
import type { ExampleCase, PrescriptionReport } from "../types";
import {
  FINDING_TYPE_CN,
  SEVERITY_CN,
  SEVERITY_COLOR,
  cnDiagnosis,
  cnDrugName,
  cnFreq,
  cnHepatic,
  cnSex,
} from "../labels";

interface Props {
  examples: ExampleCase[];
  onReviewDone?: () => void;
}

export default function PrescriptionReview({ examples, onReviewDone }: Props) {
  const [caseText, setCaseText] = useState("");
  const [report, setReport] = useState<PrescriptionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!caseText.trim()) {
      setError("请输入临床病例文本");
      return;
    }
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const r = await api.reviewPrescription(caseText);
      setReport(r);
      onReviewDone?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Input section */}
      <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
        <h2 className="text-base font-semibold text-slate-800 mb-2">📋 输入临床病例</h2>
        <p className="text-sm text-slate-500 mb-3">
          粘贴自由文本病例（中英文均可）：年龄、性别、诊断、eGFR、肝功能、INR、过敏史、处方药物
        </p>
        <textarea
          value={caseText}
          onChange={(e) => setCaseText(e.target.value)}
          placeholder="例如：74岁男性，房颤，骨关节炎。INR 3.2。处方：华法林 5mg 每日一次，阿司匹林 81mg 每日一次，布洛芬 600mg 每日三次 必要时。eGFR 70。无过敏。"
          rows={5}
          className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
        />

        {/* Example chips */}
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-xs text-slate-500 self-center">示例病例：</span>
          {examples.map((ex) => (
            <button
              key={ex.label}
              onClick={() => setCaseText(ex.text)}
              className="px-2.5 py-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full transition-colors"
            >
              {ex.label}
            </button>
          ))}
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white text-sm font-medium rounded-md transition-colors"
          >
            {loading ? "审查中…" : "开始审查"}
          </button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </section>

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-8 text-center">
          <div className="inline-block animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mb-3" />
          <p className="text-sm text-slate-600">正在解析病例、检索证据、审查处方…</p>
          <p className="text-xs text-slate-400 mt-1">通常需要 15-30 秒</p>
        </div>
      )}

      {/* Report */}
      {report && !loading && <ReportView report={report} />}
    </div>
  );
}

function ReportView({ report }: { report: PrescriptionReport }) {
  const r = report;
  const riskColor = SEVERITY_COLOR[r.overall_risk_level] ?? "#6b7280";

  return (
    <div className="space-y-4">
      {/* Top metrics */}
      <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">总体风险等级：</span>
            <span
              className="px-2.5 py-0.5 text-sm font-bold text-white rounded-full"
              style={{ backgroundColor: riskColor }}
            >
              {SEVERITY_CN[r.overall_risk_level] ?? r.overall_risk_level}
            </span>
            <span className="text-xs text-slate-500">
              （置信度：{(r.confidence * 100).toFixed(0)}%）
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Metric label="证据覆盖率" value={`${(r.evidence_coverage * 100).toFixed(0)}%`} />
          <Metric label="未验证发现数" value={String(r.unverified_findings_count)} />
          <Metric
            label="幻觉标记"
            value={r.hallucination_flagged ? "⚠️ 是" : "✅ 否"}
          />
          <Metric label="响应时间" value={`${r.elapsed_seconds.toFixed(1)} 秒`} />
        </div>
      </section>

      {/* Summary */}
      {r.summary && (
        <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-2">📝 审查总结</h3>
          <div className="bg-blue-50 border-l-4 border-blue-400 px-4 py-3 text-sm text-slate-700 preserve-whitespace leading-relaxed">
            {r.summary}
          </div>
        </section>
      )}

      {/* Patient case */}
      <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-3">🧑‍⚕️ 结构化病例</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          <Metric label="年龄" value={r.patient_case.age != null ? String(r.patient_case.age) : "—"} />
          <Metric label="性别" value={cnSex(r.patient_case.sex)} />
          <Metric label="eGFR" value={r.patient_case.egfr != null ? String(r.patient_case.egfr) : "—"} />
          <Metric label="肝功能" value={cnHepatic(r.patient_case.liver_function)} />
          <Metric label="INR" value={r.patient_case.inr != null ? String(r.patient_case.inr) : "—"} />
          <Metric
            label="妊娠"
            value={
              r.patient_case.pregnancy === true
                ? "是"
                : r.patient_case.pregnancy === false
                  ? "否"
                  : "—"
            }
          />
          <Metric
            label="过敏"
            value={
              r.patient_case.allergies.length > 0
                ? r.patient_case.allergies.map(cnDrugName).join("，")
                : "无"
            }
          />
          <Metric label="解析置信度" value={`${(r.patient_case.parse_confidence * 100).toFixed(0)}%`} />
        </div>

        {r.patient_case.diagnoses.length > 0 && (
          <p className="text-sm text-slate-700 mb-2">
            <span className="font-medium">诊断：</span>
            {r.patient_case.diagnoses.map(cnDiagnosis).join("，")}
          </p>
        )}

        <p className="text-sm font-medium text-slate-700 mb-1">处方药物：</p>
        {r.patient_case.drugs.length > 0 ? (
          <ul className="text-sm text-slate-700 list-disc list-inside space-y-0.5">
            {r.patient_case.drugs.map((d, i) => {
              const parts = [cnDrugName(d.name)];
              if (d.dose) parts.push(d.dose);
              if (d.frequency) parts.push(cnFreq(d.frequency));
              if (d.notes) parts.push(`(${d.notes})`);
              return <li key={i}>{parts.join(" ")}</li>;
            })}
          </ul>
        ) : (
          <p className="text-sm text-slate-400 italic">未识别到药物</p>
        )}
      </section>

      {/* Findings */}
      <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
        <h3 className="text-base font-semibold text-slate-800 mb-3">⚠️ 风险发现</h3>
        {r.findings.length === 0 ? (
          <p className="text-sm text-green-700 bg-green-50 px-3 py-2 rounded">
            ✅ 未发现用药风险或禁忌
          </p>
        ) : (
          <div className="space-y-3">
            {r.findings.map((f, i) => {
              const color = SEVERITY_COLOR[f.severity] ?? "#6b7280";
              return (
                <div
                  key={i}
                  className="border border-slate-200 rounded-md p-3 hover:border-slate-300 transition-colors"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-semibold text-slate-800">
                      {i + 1}. [{SEVERITY_CN[f.severity] ?? f.severity}]{" "}
                      {FINDING_TYPE_CN[f.finding_type] ?? f.finding_type}
                    </span>
                    <span style={{ color }}>●</span>
                  </div>
                  <p className="text-sm text-slate-700 mb-1">
                    <span className="font-medium">涉及药物：</span>
                    {f.drugs_involved.length > 0
                      ? f.drugs_involved.map(cnDrugName).join("，")
                      : "—"}
                  </p>
                  <p className="text-sm text-slate-700 mb-1">
                    <span className="font-medium">描述：</span>
                    {f.description}
                  </p>
                  {f.recommendation && (
                    <p className="text-sm text-slate-700 mb-1">
                      <span className="font-medium">建议：</span>
                      {f.recommendation}
                    </p>
                  )}
                  {f.evidence_doc_ids.length > 0 && (
                    <p className="text-sm text-slate-700 mb-1">
                      <span className="font-medium">证据文档：</span>
                      {f.evidence_doc_ids.join(", ")}
                    </p>
                  )}
                  {f.verification_reason && (
                    <p className="text-xs text-slate-500">
                      核验状态：{f.verified ? "✅ 已验证" : "⚠️ 未验证"} —{" "}
                      {f.verification_reason}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Citations */}
      {r.citations.length > 0 && (
        <section className="bg-white rounded-lg shadow-sm border border-slate-200 p-5">
          <h3 className="text-base font-semibold text-slate-800 mb-3">📚 引用文献</h3>
          <ul className="text-sm text-slate-600 space-y-1">
            {r.citations.map((c, i) => (
              <li key={i} className="leading-relaxed">
                {c}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-md px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-slate-800 mt-0.5">{value}</div>
    </div>
  );
}
