import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type {
  ChatCitation,
  Neo4jGraphPreview,
  Neo4jQueryResponse,
  Neo4jStatus,
  PageChatMessage,
  ResearchBatchJob,
  ResearchMiningReport,
  SideEffectRAGStatus,
  SideEffectSearchResponse,
  SideEffectDatasetSummary,
} from "../types";

const Neo4j3DGraph = lazy(() => import("./Neo4j3DGraph"));

export default function ResearchMining() {
  const [dataset, setDataset] = useState<SideEffectDatasetSummary | null>(null);
  const [ragStatus, setRagStatus] = useState<SideEffectRAGStatus | null>(null);
  const [neo4jStatus, setNeo4jStatus] = useState<Neo4jStatus | null>(null);
  const [report, setReport] = useState<ResearchMiningReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.sideEffectDataset().then(setDataset).catch(() => {});
    api.sideEffectRagStatus().then(setRagStatus).catch(() => {});
    api.neo4jStatus().then(setNeo4jStatus).catch(() => {});
  }, []);

  const runDemo = async () => {
    setLoading(true);
    try {
      setReport(await api.researchDemo());
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="bg-slate-950 text-slate-100 border border-slate-800 rounded-lg shadow-sm p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-xs text-cyan-300 font-semibold">Research Mode</p>
            <h2 className="text-xl font-semibold mt-1">科研批量 ADR 挖掘</h2>
            <p className="text-sm text-slate-400 mt-2 max-w-3xl">
              面向 PubMed 摘要、批量病历和药物组合，执行批量 ADE 抽取、统计分析、高阶联用风险和 Neo4j GraphRAG 图谱检索。
            </p>
          </div>
          <button
            onClick={runDemo}
            disabled={loading}
            className="px-4 py-2 rounded-md bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-600 text-cyan-950 text-sm font-semibold transition-colors"
          >
            {loading ? "运行中..." : "运行科研 Demo"}
          </button>
        </div>
      </section>

      <div className="grid xl:grid-cols-[1fr_320px] gap-5 items-start">
        <div className="space-y-5">
          <DatasetPanel dataset={dataset} ragStatus={ragStatus} neo4jStatus={neo4jStatus} />
          <ResearchBatchPanel onReport={setReport} />
          {report ? (
            <>
              <ResearchAgentFlow report={report} />
              <ResearchStats report={report} />
              <FindingsTable report={report} />
              <Neo4jPreview graph={report.graph_preview} title="科研 GraphRAG Neo4j 图谱预览" />
            </>
          ) : (
            <section className="bg-white border border-slate-200 rounded-lg p-8 text-center text-sm text-slate-500">
              点击“运行科研 Demo”查看批量抽取、统计图表和 Neo4j 图谱模式。
            </section>
          )}
        </div>
        <ResearchAssistantPanelLive dataset={dataset} report={report} />
      </div>
    </div>
  );
}

function DatasetPanel({
  dataset,
  ragStatus,
  neo4jStatus,
}: {
  dataset: SideEffectDatasetSummary | null;
  ragStatus: SideEffectRAGStatus | null;
  neo4jStatus: Neo4jStatus | null;
}) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-slate-800">SIDER / MedDRA 数据底座</h3>
          <p className="text-sm text-slate-500 mt-1">用于 RAG 文档块和 Neo4j 药物副作用知识图谱。</p>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full ${dataset?.available ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
          {dataset?.available ? "本地数据已就绪" : "等待数据"}
        </span>
      </div>
      {dataset && (
        <>
          <div className="grid sm:grid-cols-3 gap-3 mt-4">
            {Object.entries(dataset.row_counts).map(([key, value]) => (
              <Metric key={key} label={key} value={value.toLocaleString()} />
            ))}
          </div>
          <div className="grid lg:grid-cols-2 gap-4 mt-4">
            <InfoList title="RAG 构建策略" items={dataset.rag_strategy} />
            <InfoList title="Neo4j 图谱 Schema" items={dataset.neo4j_schema} />
          </div>
          <IndexArtifactPanel dataset={dataset} />
          <SideEffectSearchPanel ragStatus={ragStatus} />
          <Neo4jLivePanel status={neo4jStatus} />
          {dataset.graph_preview.nodes.length > 0 && (
            <div className="mt-4">
              <Neo4jPreview graph={dataset.graph_preview} title="数据集 Neo4j 样例图谱" compact />
            </div>
          )}
        </>
      )}
    </section>
  );
}

function ResearchBatchPanel({ onReport }: { onReport: (report: ResearchMiningReport) => void }) {
  const [inputText, setInputText] = useState(
    [
      "PMID: 1001 Warfarin combined with ibuprofen was associated with gastrointestinal bleeding in older patients.",
      "PMID: 1002 Metformin use in renal impairment increased risk of lactic acidosis.",
      "PMID: 1003 Clozapine therapy was associated with agranulocytosis and requires blood monitoring.",
    ].join("\n"),
  );
  const [inputFormat, setInputFormat] = useState<"auto" | "plain" | "jsonl" | "csv">("auto");
  const [sourceLabel, setSourceLabel] = useState("user_provided_batch");
  const [job, setJob] = useState<ResearchBatchJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.researchJob(job.job_id);
        setJob(next);
        if (next.status === "completed" && next.report) {
          onReport(next.report);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        window.clearInterval(timer);
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job, onReport]);

  const submitBatch = async () => {
    if (!inputText.trim()) {
      setError("请粘贴摘要、CSV 或 JSONL 文本");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const submitted = await api.researchBatchExtract({
        input_text: inputText,
        input_format: inputFormat,
        source_label: sourceLabel || "user_provided_batch",
      });
      setJob(submitted);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const progress =
    job && job.total_documents > 0
      ? Math.round((job.processed_documents / job.total_documents) * 100)
      : 0;

  return (
    <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-slate-800">真实批量 ADE 抽取</h3>
          <p className="mt-1 text-sm leading-relaxed text-slate-500">
            处理用户提供的摘要、CSV 或 JSONL；第一版不联网检索 PubMed/BioDEX，也不会补全输入中不存在的证据。
          </p>
        </div>
        {job && (
          <span className={`rounded-full px-2 py-1 text-xs ${
            job.status === "completed"
              ? "bg-emerald-100 text-emerald-800"
              : job.status === "failed"
                ? "bg-red-100 text-red-800"
                : "bg-cyan-100 text-cyan-800"
          }`}>
            {job.status}
          </span>
        )}
      </div>
      <div className="mt-4 grid lg:grid-cols-[1fr_220px] gap-3">
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          rows={7}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
          placeholder="粘贴多条摘要，或粘贴包含 pmid,abstract/text 的 CSV/JSONL..."
        />
        <div className="space-y-3">
          <label className="block">
            <span className="text-xs font-medium text-slate-500">输入格式</span>
            <select
              value={inputFormat}
              onChange={(e) => setInputFormat(e.target.value as typeof inputFormat)}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            >
              <option value="auto">自动识别</option>
              <option value="plain">纯文本</option>
              <option value="jsonl">JSONL</option>
              <option value="csv">CSV</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-500">来源标签</span>
            <input
              value={sourceLabel}
              onChange={(e) => setSourceLabel(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
          </label>
          <button
            onClick={submitBatch}
            disabled={loading || Boolean(job && (job.status === "pending" || job.status === "running"))}
            className="w-full rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:bg-slate-300 disabled:text-slate-600"
          >
            {loading ? "提交中" : "启动批量抽取"}
          </button>
        </div>
      </div>
      {job && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3 text-xs text-slate-600">
            <span>Job {job.job_id}</span>
            <span>{job.processed_documents}/{job.total_documents} docs · {job.finding_count} findings</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full bg-cyan-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
          {job.status === "completed" && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                onClick={() => job.report && onReport(job.report)}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-slate-500"
              >
                查看抽取结果
              </button>
              <a
                href={api.researchJobExportUrl(job.job_id)}
                className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:border-emerald-300"
              >
                导出 CSV
              </a>
            </div>
          )}
          {job.status === "failed" && <p className="mt-2 text-xs text-red-700">{job.error}</p>}
        </div>
      )}
      {error && <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
    </section>
  );
}

function Neo4jLivePanel({ status }: { status: Neo4jStatus | null }) {
  const [drug, setDrug] = useState("warfarin");
  const [result, setResult] = useState<Neo4jQueryResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRelationship, setSelectedRelationship] = useState<Neo4jGraphPreview["relationships"][number] | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [depth, setDepth] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const available = Boolean(status?.configured && status.connected);
  const liveGraph = useMemo(() => resultToGraph(result), [result]);
  const relationTypes = useMemo(
    () => Array.from(new Set(liveGraph.relationships.map((rel) => rel.type))).sort(),
    [liveGraph.relationships],
  );
  const visibleGraph = useMemo(
    () => filterGraphByTypes(liveGraph, selectedTypes),
    [liveGraph, selectedTypes],
  );

  const runQuery = async () => {
    if (!drug.trim()) {
      setError("请输入药物名或 CID");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await api.neo4jDrugSideEffects(drug, 12));
      setSelectedNodeId(null);
      setSelectedRelationship(null);
      setSelectedTypes([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const expandNode = async (nodeId: string) => {
    if (!available || expanding) return;
    setSelectedNodeId(nodeId);
    setExpanding(true);
    setError(null);
    try {
      const expanded = await api.neo4jExpand(nodeId, depth, selectedTypes, 60);
      setResult((current) => mergeGraphResponses(current, expanded));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setExpanding(false);
    }
  };

  const toggleType = (type: string) => {
    setSelectedTypes((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type],
    );
  };

  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-800">Neo4j live 查询</h4>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            只在真实 Neo4j 已配置并连接成功时查询图数据库；不可用时不会回退到前端预览图谱。
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-1 text-xs ${available ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
          {available ? "connected" : status?.configured ? "连接失败" : "未配置"}
        </span>
      </div>
      <div className="mt-3 grid md:grid-cols-[1fr_auto] gap-2">
        <input
          value={drug}
          onChange={(e) => setDrug(e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
          placeholder="Drug name 或 CID，例如 warfarin / CID..."
        />
        <button
          onClick={runQuery}
          disabled={loading || !available}
          className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${
            loading || !available
              ? "bg-slate-200 text-slate-600"
              : "bg-slate-900 text-white hover:bg-slate-800"
          }`}
        >
          {loading ? "查询中" : "查询图谱"}
        </button>
      </div>
      {!available && (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
          {status?.error || "请先在系统配置页填写 Neo4j URI、用户、密码和 database，然后导入 CSV/Cypher。"}
        </p>
      )}
      {error && <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
      {result && (
        <div className="mt-3 space-y-3">
          <div className="grid sm:grid-cols-4 gap-2">
            <Metric label="节点" value={result.nodes.length.toLocaleString()} />
            <Metric label="关系" value={result.relationships.length.toLocaleString()} />
            <Metric label="source" value={result.source_type} />
            <Metric label="展开深度" value={`${depth} hop`} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">关系筛选</span>
            {relationTypes.length === 0 ? (
              <span className="text-xs text-slate-400">暂无关系类型</span>
            ) : (
              relationTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => toggleType(type)}
                  className={`rounded border px-2 py-1 text-[11px] transition-colors ${
                    selectedTypes.includes(type)
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-400"
                  }`}
                >
                  {type}
                </button>
              ))
            )}
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="ml-auto rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            >
              <option value={1}>展开 1 跳</option>
              <option value={2}>展开 2 跳</option>
            </select>
          </div>
          <Neo4jPreview
            graph={visibleGraph}
            title="Neo4j live 图谱结果"
            compact
            selectedNodeId={selectedNodeId}
            onNodeClick={expandNode}
            onRelationshipClick={setSelectedRelationship}
            selectedRelationship={selectedRelationship}
            statusText={expanding ? "expanding" : "live graph"}
          />
          <code className="mt-3 block max-h-28 overflow-auto rounded border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
            {result.cypher}
          </code>
        </div>
      )}
    </div>
  );
}

function SideEffectSearchPanel({ ragStatus }: { ragStatus: SideEffectRAGStatus | null }) {
  const [drug, setDrug] = useState("PGE1");
  const [adr, setAdr] = useState("haemorrhage");
  const [result, setResult] = useState<SideEffectSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = async () => {
    if (!drug.trim() && !adr.trim()) {
      setError("请输入药物名或 ADR 术语");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await api.searchSideEffects({ drug, adr, top_k: 5 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 rounded-md border border-slate-800 bg-slate-950 p-4 text-slate-100">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold">SIDER/MedDRA RAG 检索</h4>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            本地离线真实数据源，BM25 + Chroma 向量融合；返回药物-不良反应证据，不替代因果判断。
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-1 text-xs ${ragStatus?.available ? "bg-emerald-400/15 text-emerald-200" : "bg-amber-400/15 text-amber-200"}`}>
          {ragStatus?.available ? `${ragStatus.document_count.toLocaleString()} docs` : "未构建"}
        </span>
      </div>
      <div className="mt-3 grid md:grid-cols-[1fr_1fr_auto] gap-2">
        <input
          value={drug}
          onChange={(e) => setDrug(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
          placeholder="Drug，例如 warfarin"
        />
        <input
          value={adr}
          onChange={(e) => setAdr(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
          placeholder="ADR，例如 bleeding"
        />
        <button
          onClick={runSearch}
          disabled={loading || !ragStatus?.available}
          className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${
            loading || !ragStatus?.available
              ? "bg-slate-700 text-white"
              : "bg-cyan-500 text-cyan-950 hover:bg-cyan-400"
          }`}
        >
          {loading ? "检索中" : "检索"}
        </button>
      </div>
      {error && <p className="mt-3 rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">{error}</p>}
      {result && (
        <div className="mt-3 space-y-2">
          {result.hits.length === 0 ? (
            <p className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-400">没有命中本地 SIDER/MedDRA 文档块。</p>
          ) : (
            result.hits.slice(0, 4).map((hit) => (
              <div key={hit.doc_id} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-100">{hit.drug_name}</span>
                  <span className="text-[11px] text-cyan-200">{hit.drug_cid}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {hit.matched_side_effects.slice(0, 5).map((item) => (
                    <span key={`${hit.doc_id}-${item.meddra_cui}-${item.term}`} className="rounded border border-slate-600 px-2 py-1 text-[11px] text-slate-300">
                      {String(item.term)} {item.frequency_label ? `(${item.frequency_label})` : ""}
                    </span>
                  ))}
                </div>
              </div>
            ))
          )}
          {result.limitations.length > 0 && (
            <p className="text-[11px] leading-relaxed text-slate-500">{result.limitations[0]}</p>
          )}
        </div>
      )}
    </div>
  );
}

function IndexArtifactPanel({ dataset }: { dataset: SideEffectDatasetSummary }) {
  const manifest = dataset.index_manifest ?? {};
  const files = typeof manifest.files === "object" && manifest.files !== null ? manifest.files : {};
  const stats: Array<[string, unknown]> = [
    ["Drug 节点", manifest.drug_count],
    ["SideEffect 节点", manifest.side_effect_count],
    ["HAS_SIDE_EFFECT 边", manifest.relationship_count],
    ["RAG 文档块", manifest.rag_document_count],
  ];
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-800">离线索引产物</h4>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            由本地 SIDER/MedDRA 数据包生成，用于后续 RAG 检索、Neo4j CSV 导入和 Cypher 建库；不是 PubMed/DrugBank 实时检索结果。
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-1 text-xs ${dataset.index_available ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
          {dataset.index_available ? "已生成" : "未构建"}
        </span>
      </div>
      {dataset.index_available ? (
        <>
          <div className="mt-3 grid sm:grid-cols-4 gap-2">
            {stats.map(([label, value]) => (
              <Metric key={label} label={String(label)} value={typeof value === "number" ? value.toLocaleString() : "—"} />
            ))}
          </div>
          <div className="mt-3 grid lg:grid-cols-2 gap-2">
            {Object.entries(files).slice(0, 6).map(([key, value]) => (
              <code key={key} className="block rounded border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 overflow-x-auto">
                {key}: {value}
              </code>
            ))}
            {Object.keys(files).length === 0 && (
              <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                后端当前未返回 manifest 文件清单；请重新运行离线索引构建脚本以刷新产物摘要。
              </p>
            )}
          </div>
        </>
      ) : (
        <code className="mt-3 block rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 overflow-x-auto">
          python scripts/build_sider_meddra_index.py
        </code>
      )}
    </div>
  );
}

function ResearchAgentFlow({ report }: { report: ResearchMiningReport }) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
      <h3 className="text-base font-semibold text-slate-800 mb-3">科研模式 Agent 流程</h3>
      <div className="grid md:grid-cols-5 gap-3">
        {report.agent_steps.map((step, idx) => (
          <div key={step.name} className="border border-slate-200 bg-slate-50 rounded-md p-3">
            <div className="text-xs font-semibold text-blue-700">Agent {idx + 1}</div>
            <div className="text-sm font-semibold text-slate-800 mt-2 break-words">{step.name}</div>
            <div className="text-xs text-slate-500 mt-1">{step.role}</div>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">{step.summary}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ResearchStats({ report }: { report: ResearchMiningReport }) {
  return (
    <section className="grid lg:grid-cols-3 gap-4">
      <BarCard title="药物风险频次 TOP" data={report.top_drugs} color="#2563eb" />
      <BarCard title="ADR 分类分布" data={report.adr_categories} color="#dc2626" />
      <BarCard title="置信度分布" data={report.confidence_distribution} color="#059669" />
    </section>
  );
}

function FindingsTable({ report }: { report: ResearchMiningReport }) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-5">
      <h3 className="text-base font-semibold text-slate-800 mb-3">批量 ADE 结构化结果</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="py-2 pr-3">文献 ID</th>
              <th className="py-2 pr-3">药物</th>
              <th className="py-2 pr-3">不良反应</th>
              <th className="py-2 pr-3">置信度</th>
              <th className="py-2">证据片段</th>
            </tr>
          </thead>
          <tbody>
            {report.findings.map((finding) => (
              <tr key={finding.pmid} className="border-b border-slate-100">
                <td className="py-2 pr-3 text-slate-600">{finding.pmid}</td>
                <td className="py-2 pr-3 font-medium text-slate-800">{finding.drug}</td>
                <td className="py-2 pr-3 text-slate-800">{finding.adverse_event}</td>
                <td className="py-2 pr-3 text-emerald-700 font-semibold">{Math.round(finding.confidence * 100)}%</td>
                <td className="py-2 text-slate-600">{finding.evidence_span}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Neo4jPreview({
  graph,
  title,
  compact = false,
  selectedNodeId = null,
  onNodeClick,
  onRelationshipClick,
  selectedRelationship = null,
  statusText = "Neo4j mode",
}: {
  graph: Neo4jGraphPreview;
  title: string;
  compact?: boolean;
  selectedNodeId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onRelationshipClick?: (relationship: Neo4jGraphPreview["relationships"][number]) => void;
  selectedRelationship?: Neo4jGraphPreview["relationships"][number] | null;
  statusText?: string;
}) {
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? graph.nodes[0] ?? null;
  return (
    <section className="bg-slate-950 text-slate-100 border border-slate-800 rounded-lg shadow-sm p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-xs text-slate-400 mt-1">节点 labels 与关系 type 按 Neo4j 数据模型展示；点击节点可展开 live 查询</p>
        </div>
        <span className="text-xs text-cyan-200 border border-cyan-400/40 rounded px-2 py-1">{statusText}</span>
      </div>
      <div className={`grid ${compact ? "lg:grid-cols-[1fr_220px]" : "lg:grid-cols-[1fr_260px]"} gap-3`}>
        <Suspense
          fallback={
            <div className="flex min-h-72 items-center justify-center rounded-md border border-slate-800 bg-slate-950 text-sm text-slate-500">
              正在加载 3D 图谱引擎...
            </div>
          }
        >
          <Neo4j3DGraph
            graph={graph}
            compact={compact}
            selectedNodeId={selectedNodeId}
            onNodeClick={onNodeClick}
            onLinkClick={onRelationshipClick}
          />
        </Suspense>
        <aside className="rounded-md border border-slate-800 bg-slate-900 p-3">
          <h4 className="text-xs font-semibold text-slate-300">节点详情</h4>
          {selectedNode ? (
            <div className="mt-2">
              <div className="text-sm font-semibold text-white">{nodeLabel(selectedNode)}</div>
              <div className="mt-1 text-[11px] text-slate-400">{selectedNode.labels.join(" / ")}</div>
              <div className="mt-3 max-h-40 overflow-auto space-y-1">
                {Object.entries(selectedNode.properties).slice(0, 8).map(([key, value]) => (
                  <div key={key} className="text-[11px] text-slate-300">
                    <span className="text-slate-500">{key}: </span>{String(value)}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-xs text-slate-500">暂无节点</p>
          )}
          {selectedRelationship && (
            <div className="mt-4 border-t border-slate-800 pt-3">
              <h4 className="text-xs font-semibold text-slate-300">关系详情</h4>
              <div className="mt-2 text-sm font-semibold text-cyan-100">{selectedRelationship.type}</div>
              <div className="mt-1 text-[11px] text-slate-500">{selectedRelationship.source} → {selectedRelationship.target}</div>
              <div className="mt-2 max-h-28 overflow-auto space-y-1">
                {Object.entries(selectedRelationship.properties).slice(0, 6).map(([key, value]) => (
                  <div key={key} className="text-[11px] text-slate-300">
                    <span className="text-slate-500">{key}: </span>{String(value)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
      {graph.cypher_examples.length > 0 && (
        <div className="mt-3 space-y-2">
          {graph.cypher_examples.map((query) => (
            <code key={query} className="block text-xs text-cyan-100 bg-slate-900 border border-slate-700 rounded px-3 py-2 overflow-x-auto">
              {query}
            </code>
          ))}
        </div>
      )}
    </section>
  );
}

function resultToGraph(result: Neo4jQueryResponse | null): Neo4jGraphPreview {
  if (!result) return { nodes: [], relationships: [], cypher_examples: [] };
  return {
    nodes: result.nodes,
    relationships: result.relationships,
    cypher_examples: [result.cypher],
  };
}

function filterGraphByTypes(graph: Neo4jGraphPreview, types: string[]): Neo4jGraphPreview {
  if (types.length === 0) return graph;
  const relationships = graph.relationships.filter((rel) => types.includes(rel.type));
  const nodeIds = new Set(relationships.flatMap((rel) => [rel.source, rel.target]));
  return {
    ...graph,
    nodes: graph.nodes.filter((node) => nodeIds.has(node.id)),
    relationships,
  };
}

function mergeGraphResponses(current: Neo4jQueryResponse | null, next: Neo4jQueryResponse): Neo4jQueryResponse {
  if (!current) return next;
  const nodes = new Map(current.nodes.map((node) => [node.id, node]));
  next.nodes.forEach((node) => nodes.set(node.id, node));
  const relationships = new Map(current.relationships.map((rel) => [`${rel.source}-${rel.type}-${rel.target}`, rel]));
  next.relationships.forEach((rel) => relationships.set(`${rel.source}-${rel.type}-${rel.target}`, rel));
  return {
    ...next,
    cypher: next.cypher,
    rows: [...current.rows, ...next.rows],
    nodes: Array.from(nodes.values()),
    relationships: Array.from(relationships.values()),
    warnings: Array.from(new Set([...current.warnings, ...next.warnings])),
  };
}

function nodeLabel(node: { id: string; properties: Record<string, string | number | boolean | null> }) {
  return String(node.properties.name ?? node.properties.term ?? node.properties.cid ?? node.properties.cui ?? node.id);
}

export function ResearchAssistantPanel({ dataset, report }: { dataset: SideEffectDatasetSummary | null; report: ResearchMiningReport | null }) {
  return (
    <aside className="xl:sticky xl:top-24 bg-slate-950 text-slate-100 border border-slate-800 rounded-lg shadow-sm p-4">
      <h3 className="text-sm font-semibold">科研问答面板</h3>
      <p className="text-xs text-slate-400 mt-1">用于解释 RAG、Neo4j 图谱和批量挖掘结果。</p>
      <div className="mt-4 bg-slate-900 border border-slate-700 rounded-md p-3 text-sm text-slate-300">
        数据状态：{dataset?.available ? "SIDER/MedDRA 已加载" : "未加载"}
        <br />
        Findings：{report?.findings.length ?? 0}
      </div>
      {["如何把 SIDER 数据转成 RAG？", "Neo4j 中药物副作用边怎么定义？", "如何筛选高置信 ADE？"].map((q) => (
        <button key={q} className="mt-2 w-full text-left text-xs text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-md px-3 py-2 transition-colors">
          {q}
        </button>
      ))}
      <textarea rows={4} className="mt-4 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500" placeholder="输入科研追问..." />
      <button className="mt-2 w-full rounded-md bg-cyan-500 hover:bg-cyan-400 text-cyan-950 text-sm font-semibold px-3 py-2 transition-colors">
        调度科研问答 Agent
      </button>
    </aside>
  );
}

function ResearchAssistantPanelLive({ dataset, report }: { dataset: SideEffectDatasetSummary | null; report: ResearchMiningReport | null }) {
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
    "如何把 SIDER 数据转成 RAG 文档块？",
    "Neo4j 中药物副作用关系怎么定义？",
    "如何筛选高置信 ADE？",
  ];

  const submitQuestion = async (text = question) => {
    const trimmed = text.trim();
    if (!trimmed || loading || !report) return;
    const userMessage: AssistantMessage = { role: "user", content: trimmed };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setQuestion("");
    setError(null);
    setLoading(true);
    try {
      const history = messages.map(({ role, content }) => ({ role, content }));
      const result = await api.chatResearch(trimmed, report, history);
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
    <aside className="xl:sticky xl:top-24 bg-slate-950 text-slate-100 border border-slate-800 rounded-lg shadow-sm p-4">
      <h3 className="text-sm font-semibold">科研问答面板</h3>
      <p className="text-xs text-slate-400 mt-1">调用外部 LLM，解释 RAG、Neo4j 图谱和批量挖掘结果</p>
      <div className="mt-4 bg-slate-900 border border-slate-700 rounded-md p-3 text-sm text-slate-300">
        数据状态：{dataset?.available ? "SIDER/MedDRA 已加载" : "未加载"}
        <br />
        Findings：{report?.findings.length ?? 0}
      </div>
      <div className="mt-4 space-y-2">
        {quickQuestions.map((item) => (
          <button
            key={item}
            onClick={() => submitQuestion(item)}
            disabled={loading || !report}
            className="w-full text-left text-xs text-slate-200 bg-slate-900 hover:bg-slate-800 disabled:opacity-60 border border-slate-700 rounded-md px-3 py-2 transition-colors"
          >
            {item}
          </button>
        ))}
      </div>
      <div className="mt-4 max-h-80 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <div className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs leading-relaxed text-slate-400">
            先运行科研 Demo 后，问答会基于 findings、统计分布和 Neo4j 预览回答；不会编造未接入的 PubMed 或 DrugBank 实时结果。
          </div>
        )}
        {messages.map((message, index) => (
          <ResearchChatBubble key={`${message.role}-${index}`} message={message} />
        ))}
        {loading && (
          <div className="rounded-md border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs text-cyan-100">
            ResearchQAAgent 正在读取当前挖掘结果并生成回答...
          </div>
        )}
      </div>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={4}
        disabled={!report}
        className="mt-4 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-cyan-500"
        placeholder={report ? "输入科研追问..." : "请先运行科研 Demo"}
      />
      <button
        onClick={() => submitQuestion()}
        disabled={loading || !question.trim() || !report}
        className="mt-2 w-full rounded-md bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-700 disabled:text-white text-cyan-950 text-sm font-semibold px-3 py-2 transition-colors"
      >
        {loading ? "科研问答运行中" : "调度科研问答 Agent"}
      </button>
      {error && (
        <p className="mt-3 rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-200">
          {error}
        </p>
      )}
    </aside>
  );
}

function ResearchChatBubble({ message }: { message: PageChatMessage & { citations?: ChatCitation[]; confidence?: number; used_agents?: string[] } }) {
  const isUser = message.role === "user";
  return (
    <div className={`rounded-md border px-3 py-2 text-sm leading-relaxed ${isUser ? "border-slate-700 bg-slate-900 text-white" : "border-cyan-400/30 bg-cyan-950/80 text-white"}`}>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{isUser ? "User" : "ResearchQAAgent"}</div>
      <p className="mt-1 preserve-whitespace">{message.content}</p>
      {!isUser && message.used_agents && message.used_agents.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {message.used_agents.map((agent) => (
            <span key={agent} className="rounded border border-slate-600 px-1.5 py-0.5 text-[10px] text-slate-300">{agent}</span>
          ))}
          {typeof message.confidence === "number" && (
            <span className="rounded border border-emerald-400/40 px-1.5 py-0.5 text-[10px] text-emerald-200">
              置信度 {Math.round(message.confidence * 100)}%
            </span>
          )}
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

function InfoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-md p-3">
      <h4 className="text-sm font-semibold text-slate-800 mb-2">{title}</h4>
      <ul className="text-sm text-slate-600 space-y-2">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function BarCard({ title, data, color }: { title: string; data: { label: string; count: number }[]; color: string }) {
  const max = Math.max(...data.map((item) => item.count), 1);
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-sm p-4">
      <h3 className="text-sm font-semibold text-slate-800 mb-3">{title}</h3>
      <div className="space-y-2">
        {data.map((item) => (
          <div key={item.label}>
            <div className="flex justify-between text-xs text-slate-600 mb-1">
              <span>{item.label}</span>
              <span>{item.count}</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(item.count / max) * 100}%`, backgroundColor: color }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-md px-3 py-2 border border-slate-100">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-slate-800 mt-0.5">{value}</div>
    </div>
  );
}
