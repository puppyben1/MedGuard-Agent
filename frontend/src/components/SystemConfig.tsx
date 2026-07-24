import { useEffect, useState } from "react";
import { api } from "../api";
import type { FAERSStatus, HealthResponse, RuntimeConfigStatus, RuntimeConfigUpdate } from "../types";

type Provider = "groq" | "openai_compatible";

export default function SystemConfig() {
  const [status, setStatus] = useState<RuntimeConfigStatus | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [faers, setFaers] = useState<FAERSStatus | null>(null);
  const [form, setForm] = useState<RuntimeConfigUpdate>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((res) => {
      setStatus(res);
      setForm({
        llm_provider: res.llm_provider,
        llm_base_url: res.llm_base_url,
        router_model: res.router_model,
        generator_model: res.generator_model,
        strict_real_data: res.strict_real_data,
        neo4j_uri: res.neo4j_uri,
        neo4j_username: res.neo4j_username,
        neo4j_database: res.neo4j_database,
        side_effect_zip_path: res.side_effect_zip_path,
        require_real_sources: res.require_real_sources,
      });
    }).catch((e) => setError(e instanceof Error ? e.message : String(e)));
    api.health().then(setHealth).catch(() => {});
    api.faersStatus().then(setFaers).catch(() => {});
  }, []);

  const update = (patch: RuntimeConfigUpdate) => {
    setForm((prev) => ({ ...prev, ...patch }));
  };

  const save = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const next = await api.updateConfig(form);
      setStatus(next);
      setMessage("配置已保存。新的 LLM/openFDA 请求会优先使用运行时配置。");
      setForm((prev) => ({
        ...prev,
        llm_api_key: "",
        openfda_api_key: "",
        neo4j_password: "",
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-slate-800 bg-slate-950 p-5 text-slate-100 shadow-lg shadow-slate-950/10">
        <p className="text-xs font-semibold text-cyan-300">Runtime Configuration</p>
        <h2 className="mt-1 text-xl font-semibold">系统配置</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
          配置外部 LLM、openFDA、Neo4j 和本地 RAG 数据源。密钥保存在本机 `data/runtime/`，不会提交到 Git，也不会在前端回显。
        </p>
      </section>

      <div className="grid xl:grid-cols-[1fr_320px] gap-5 items-start">
        <div className="space-y-5">
          <ConfigSection title="LLM 智能问答 API" description="用于药物安全问答、LLM schema 抽取、报告解释和后续常驻问答面板。">
            <div className="grid md:grid-cols-2 gap-4">
              <Field label="Provider">
                <select
                  value={form.llm_provider ?? "openai_compatible"}
                  onChange={(e) => update({ llm_provider: e.target.value as Provider })}
                  className="config-input"
                >
                  <option value="openai_compatible">OpenAI-compatible / DeepSeek / Qwen / vLLM</option>
                  <option value="groq">Groq</option>
                </select>
              </Field>
              <Field label="API Key">
                <input
                  type="password"
                  value={form.llm_api_key ?? ""}
                  onChange={(e) => update({ llm_api_key: e.target.value })}
                  placeholder={status?.has_llm_api_key ? "已配置，留空则保持不变" : "粘贴 API Key"}
                  className="config-input"
                />
              </Field>
              <Field label="Base URL">
                <input
                  value={form.llm_base_url ?? ""}
                  onChange={(e) => update({ llm_base_url: e.target.value })}
                  placeholder="https://api.deepseek.com"
                  className="config-input"
                />
              </Field>
              <Field label="Router Model">
                <input
                  value={form.router_model ?? ""}
                  onChange={(e) => update({ router_model: e.target.value })}
                  placeholder="deepseek-chat"
                  className="config-input"
                />
              </Field>
              <Field label="Generator Model">
                <input
                  value={form.generator_model ?? ""}
                  onChange={(e) => update({ generator_model: e.target.value })}
                  placeholder="deepseek-chat"
                  className="config-input"
                />
              </Field>
            </div>
          </ConfigSection>

          <ConfigSection title="真实世界数据检测" description="用于 openFDA / FAERS 实时检测。开启严格真实数据后，失败不再回退 demo。">
            <div className="grid md:grid-cols-2 gap-4">
              <Field label="openFDA API Key">
                <input
                  type="password"
                  value={form.openfda_api_key ?? ""}
                  onChange={(e) => update({ openfda_api_key: e.target.value })}
                  placeholder={status?.has_openfda_api_key ? "已配置，留空则保持不变" : "可选，提高限流额度"}
                  className="config-input"
                />
              </Field>
              <label className="flex items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={Boolean(form.strict_real_data)}
                  onChange={(e) => update({ strict_real_data: e.target.checked })}
                  className="h-4 w-4 accent-cyan-600"
                />
                严格真实数据模式：openFDA 失败时不使用 demo 回退
              </label>
            </div>
          </ConfigSection>

          <ConfigSection title="Neo4j / RAG 数据源" description="用于 SIDER/MedDRA 图谱、GraphRAG 和真实数据检索。">
            <div className="grid md:grid-cols-2 gap-4">
              <Field label="Neo4j URI">
                <input value={form.neo4j_uri ?? ""} onChange={(e) => update({ neo4j_uri: e.target.value })} className="config-input" />
              </Field>
              <Field label="Neo4j User">
                <input value={form.neo4j_username ?? ""} onChange={(e) => update({ neo4j_username: e.target.value })} className="config-input" />
              </Field>
              <Field label="Neo4j Password">
                <input
                  type="password"
                  value={form.neo4j_password ?? ""}
                  onChange={(e) => update({ neo4j_password: e.target.value })}
                  placeholder={status?.has_neo4j_password ? "已配置，留空则保持不变" : "Neo4j 密码"}
                  className="config-input"
                />
              </Field>
              <Field label="Neo4j Database">
                <input value={form.neo4j_database ?? ""} onChange={(e) => update({ neo4j_database: e.target.value })} className="config-input" />
              </Field>
              <Field label="SIDER/MedDRA Zip Path">
                <input value={form.side_effect_zip_path ?? ""} onChange={(e) => update({ side_effect_zip_path: e.target.value })} className="config-input" />
              </Field>
              <label className="flex items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={Boolean(form.require_real_sources)}
                  onChange={(e) => update({ require_real_sources: e.target.checked })}
                  className="h-4 w-4 accent-cyan-600"
                />
                RAG/图谱必须使用真实来源数据
              </label>
            </div>
          </ConfigSection>

          <div className="flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-md bg-cyan-500 px-5 py-2 text-sm font-semibold text-cyan-950 transition-colors hover:bg-cyan-400 disabled:bg-slate-300"
            >
              {saving ? "保存中..." : "保存配置"}
            </button>
            {message && <span className="text-sm text-emerald-700">{message}</span>}
            {error && <span className="text-sm text-red-700">{error}</span>}
          </div>
        </div>

        <StatusPanel status={status} health={health} faers={faers} />
      </div>
    </div>
  );
}

function ConfigSection({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 text-sm text-slate-500">{description}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function StatusPanel({
  status,
  health,
  faers,
}: {
  status: RuntimeConfigStatus | null;
  health: HealthResponse | null;
  faers: FAERSStatus | null;
}) {
  const rows = status
    ? [
        ["LLM Key", status.has_llm_api_key ? "已配置" : "未配置"],
        ["openFDA Key", status.has_openfda_api_key ? "已配置" : "未配置"],
        ["严格真实数据", status.strict_real_data ? "开启" : "关闭"],
        ["Neo4j Password", status.has_neo4j_password ? "已配置" : "未配置"],
        ["SIDER Zip", status.side_effect_zip_available ? "可用" : "缺失"],
      ]
    : [];

  return (
    <aside className="xl:sticky xl:top-24 rounded-lg border border-slate-800 bg-slate-950 p-4 text-slate-100 shadow-sm">
      <h3 className="text-sm font-semibold">运行时状态</h3>
      <p className="mt-1 text-xs text-slate-400">所有密钥均脱敏显示。</p>
      <div className="mt-4 space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm">
            <span className="text-slate-400">{label}</span>
            <span className="font-semibold text-cyan-200">{value}</span>
          </div>
        ))}
      </div>
      {health && (
        <div className="mt-4 rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-300">
          <div className="font-semibold text-slate-100">开发调试预算</div>
          <div className="mt-2 flex justify-between">
            <span className="text-slate-400">生成器剩余</span>
            <span>{health.generator_budget_remaining.toLocaleString()}</span>
          </div>
          <div className="mt-1 flex justify-between">
            <span className="text-slate-400">路由器剩余</span>
            <span>{health.router_budget_remaining.toLocaleString()}</span>
          </div>
          <p className="mt-2 text-slate-500">这是 LLM 调用限额监控，不是业务指标。</p>
        </div>
      )}
      <div className="mt-4 rounded-md border border-slate-800 bg-slate-900 px-3 py-3 text-xs text-slate-300">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-semibold text-slate-100">FAERS 离线缓存</div>
            <p className="mt-1 leading-relaxed text-slate-400">用于 offline_faers 信号计算和二乘二表展示。</p>
          </div>
          <span
            className={`shrink-0 rounded-full border px-2 py-0.5 font-semibold ${
              faers?.available
                ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
                : "border-amber-300/40 bg-amber-300/10 text-amber-100"
            }`}
          >
            {faers?.available ? "可用" : "未接入"}
          </span>
        </div>
        {faers?.available ? (
          <div className="mt-3 space-y-2">
            <StatusRow label="来源标签" value={faers.source_label || faers.source_type} />
            <StatusRow label="病例数" value={faers.case_count.toLocaleString()} />
            <StatusRow label="药物记录" value={faers.drug_case_count.toLocaleString()} />
            <StatusRow label="ADR 记录" value={faers.reaction_case_count.toLocaleString()} />
            <StatusRow label="去重口径" value={faers.deduplicated ? "caseid / primaryid" : "未声明"} />
            <p className="break-all rounded border border-slate-800 bg-slate-950 px-2 py-1 text-slate-400">
              {faers.cache_path}
            </p>
          </div>
        ) : (
          <div className="mt-3 rounded border border-amber-300/30 bg-amber-300/10 px-3 py-2 leading-relaxed text-amber-100">
            {faers?.error || "尚未检测到本地 FAERS SQLite 缓存；ADR 会继续标注 demo/fallback/openFDA 来源。"}
          </div>
        )}
      </div>
      <div className="mt-4 rounded-md border border-amber-300/30 bg-amber-300/10 p-3 text-xs leading-relaxed text-amber-100">
        要求“所有数据真实”时，请开启严格真实数据模式，并完成 openFDA、RAG 数据和 Neo4j 配置；否则系统会明确标注 demo/fallback 数据来源。
      </div>
    </aside>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded border border-slate-800 bg-slate-950 px-2 py-1">
      <span className="text-slate-400">{label}</span>
      <span className="text-right font-semibold text-slate-100">{value}</span>
    </div>
  );
}
