# MedGuard-Agent ADR SPEC

## 1. Product Context

`$impeccable init` 已在本仓库生成 `PRODUCT.md`，作为后续 UI 与产品决策的持久上下文。

本系统定位为：基于 LLM 语义理解、多智能体协作、多源证据检索、真实世界信号检测、因果评价和 Neo4j 风格知识图谱展示的药物不良反应智能警戒系统。

当前平台：Web。

核心用户：

- 临床药师和医生：审查处方、复盘 ADR 个案、查看证据链。
- 比赛评审：评估多 Agent 协作、数据真实性、可视化说服力。
- 医药科研用户：批量挖掘药物-ADE 关联并构建科研数据集。

## 2. Current Product Modes

### 2.1 处方审查

现有稳定能力。输入自由文本病例和处方，输出 `PrescriptionReport`，包含风险等级、逐条 finding、证据覆盖和幻觉标记。

### 2.2 药物安全问答

现有稳定能力。输入自然语言药物安全问题，走 agentic RAG 流程，输出风险等级、证据、禁忌、监测建议和引用。

### 2.3 临床个案 ADR 全流程分析

比赛展示主线。输入病例后执行九大 Agent：

1. `SemanticUnderstandingAgent`：LLM 前置语义理解。
2. `ADRExtractionAgent`：抽取药物、ADR、时间、症状和客观指标。
3. `PrescriptionRiskAgent`：识别处方和合并用药风险。
4. `FAERSSignalAgent`：查询本地 FAERS demo / openFDA，返回 ROR、PRR、报告数和严重比例。
5. `CausalityAssessmentAgent`：Naranjo + WHO-UMC 因果评价。
6. `EvidenceFusionAgent`：融合病例、实验室、统计和规则证据。
7. `GraphRAGAgent`：按 Neo4j 图谱模式组织药物-ADR-证据关系。
8. `VisualizationAgent`：生成时间轴、看板和图谱视图数据。
9. `ReportQAAgent`：生成专业报告并为问答面板提供上下文。

### 2.4 科研批量 ADR 挖掘

新增演示入口。第一版为 demo-first 原型：

- 展示批量 ADE 抽取结果。
- 展示药物风险频次、ADR 分类和置信度分布。
- 展示 Neo4j GraphRAG 图谱预览。
- 展示 SIDER/MedDRA 数据底座如何用于 RAG 与图谱构建。

## 3. Data Strategy

用户提供的数据包已复制到：

```text
data/incoming/adr_data.zip
```

该目录已加入 `.gitignore`，数据用于本地 RAG/Neo4j 构建，不直接提交到 Git。

数据内容：

- `drug_names.tsv`：Drug CID 与药物名称。
- `meddra_all_se.tsv.gz`：Drug 与 MedDRA 不良反应术语关系。
- `meddra_freq.tsv.gz`：Drug-ADR 频率信息，可作为图谱边权重和 RAG 排序特征。

RAG 策略：

- 按 drug CID 聚合药物名称、MedDRA PT/LLT 不良反应、频率和来源文件。
- 每个药物生成一个或多个结构化文档块。
- 检索结果必须保留 `drug_cid`、`meddra_cui`、`term`、`frequency`、`source_file`，用于证据溯源。

Neo4j 图谱模式：

```cypher
(:Drug {cid, name})
(:MedDRATerm {cui, term, level})
(:SideEffect {name, meddra_cui})
(:Drug)-[:HAS_SIDE_EFFECT {frequency, frequency_label, source}]->(:MedDRATerm)
(:MedDRATerm)-[:NORMALIZED_TO]->(:MedDRATerm)
```

## 4. Frontend Polish Spec

本轮 `$impeccable polish frontend` 的设计目标：

- 保留现有医疗工作台身份，不重做为营销页。
- App shell 采用深色科研产品框架，突出 MedGuard-Agent 的多 Agent 与数据可信机制。
- ADR 页面顶部明确标注 `Clinical Case Mode`，让评委快速理解执行链路。
- 九大 Agent 流程使用深色 trace 面板，展示 Agent 名称、角色、数据源和摘要。
- 右侧常驻问答面板先做上下文展示和操作入口，后续接入现有 QA/RAG。
- 证据链按高/中/低置信分组，避免列表堆叠。
- 3D 图谱用 Neo4j 模式叙事：Drug / ADR / Evidence / Lab 节点，高危路径高亮。
- 科研批量页面作为独立主入口，展示 SIDER/MedDRA 数据、RAG 构建策略和 Neo4j 图谱预览。

## 5. Current Implementation Files

后端：

- `pharmagent/adr/schemas.py`
- `pharmagent/adr/workflow.py`
- `pharmagent/adr/side_effect_data.py`
- `pharmagent/adr/research.py`
- `pharmagent/api/routes/adr.py`

前端：

- `frontend/src/App.tsx`
- `frontend/src/components/ADRAnalysis.tsx`
- `frontend/src/components/ResearchMining.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/index.css`

## 6. Open Work

### 6.1 当前尚未完全实现的目标能力

以下目标来自新版系统设想，但当前代码仍为未实现或演示占位：

- LLM 前置语义理解尚未成为 ADR 个案分析的真实主路径；当前 ADR 抽取仍以 demo 匹配和规则 fallback 为主。
- “所有数据均真实”尚未完全成立；当前 FAERS 有本地 demo/fallback，科研模式是 demo-first。
- 常驻智能问答面板已接入当前页面上下文和外部 LLM API；但尚未额外实时检索 PubMed/DrugBank/Neo4j。
- Naranjo 仍是简化解释性评分，不是完整 10 项逐项 LLM 匹配。
- FAERS 检测尚未使用官方季度原始数据离线去重、混杂校正和完整 ROR/PRR 二乘二表。
- PubMed 1000 条摘要批量处理、BioDEX 标注数据接入尚未实现。
- HODDI 高阶多药联用风险计算尚未实现，当前只有规则/demo 级别联用风险。
- DrugBank / Neo4j 持久图数据库尚未真正导入和查询；SIDER/MedDRA 已有离线索引构建脚本和本地生成产物状态展示。
- 3D 图谱已接入 react-force-graph-3d / Three.js 第一版；仍需继续增强大图性能、证据抽屉和高危路径表现。
- PDF 报告导出已完成第一版；仍需继续嵌入图谱截图、模板主题和科研/多药报告导出。

### 6.2 API 配置与真实数据要求

为支持真实运行检测，系统新增 `系统配置` 页面和后端运行时配置：

- 配置文件保存到 `data/runtime/api_config.json`，该目录已加入 `.gitignore`。
- 前端不会回显 API key，只显示是否已配置。
- LLM 问答、LLM schema 抽取和报告解释应优先使用运行时配置中的外部 API。
- openFDA 检测优先使用运行时配置中的 API key。
- 开启 `strict_real_data` 后，openFDA 失败不允许静默回退 demo 数据。
- RAG/Neo4j 配置记录 SIDER/MedDRA zip 路径、Neo4j URI、用户、数据库和密码状态。
- 主界面不展示 LLM 调用预算；预算只在系统配置页作为开发调试状态展示。
- 前端必须区分“真实数据已就绪 / 待配置 / demo fallback”，不能把演示数据包装成真实数据。

新增接口：

```text
GET  /api/config
POST /api/config
```

### 6.3 下一阶段真实化任务

1. 用配置页的外部 LLM API 接入 ADR LLM schema 抽取。
2. 用配置页的外部 LLM API 接入右侧常驻问答面板，回答必须引用当前报告证据。
3. 已实现 SIDER/MedDRA 离线索引脚本，生成：
   - RAG JSONL 文档块；
   - Neo4j import CSV；
   - Cypher 建库脚本；
   - manifest.json 构建摘要。
4. 接入 Neo4j driver，实现真实图谱查询接口。
5. 将科研批量 demo 替换为真实文本上传和批量抽取。
6. 将 FAERS 本地 demo 替换为官方季度数据缓存和离线信号检测。

### 6.4 当前真实化进展

- 已实现运行时 API 配置页。
- 已实现 LLM 运行时配置读取；ADR 抽取会在配置 LLM API key 后优先走真实 LLM schema 抽取。
- 已实现 openFDA 运行时 API key 读取。
- 已实现 `strict_real_data`：开启后 openFDA 失败不再回退 demo。
- 已实现常驻问答面板真实接入。
- 已实现 SIDER/MedDRA 离线索引构建脚本和本地索引产物状态展示。
- 已实现 SIDER/MedDRA RAG 真检索接口：本地 JSONL 文档块 + BM25 + Chroma 向量索引，问答会尝试检索该离线真实数据源作为补充证据。
- 已实现 Neo4j live 查询接口封装和前端交互预览：读取系统配置中的 URI/user/password/database，未配置或连接失败时明确报错，不回退 demo。
- 尚未完成：真正 3D 图谱、FAERS 官方季度离线计算、批量 PubMed/BioDEX 真实处理。

## 7. 2026-07-23 开发记录：常驻问答真实接入

本轮完成“1 开发”：ADR 页面与科研页面的右侧常驻问答面板不再是占位展示，已接入后端真实问答链路。

新增后端接口：
```text
POST /api/adr/chat
POST /api/adr/research/chat
```

实现要点：
- `ReportQAAgent` 会读取当前页面传入的结构化报告上下文，而不是脱离页面自由回答。
- ADR 问答上下文包含病例抽取、时间轴、FAERS/openFDA 信号、处方风险、Naranjo/WHO-UMC 因果评分、证据链和图谱节点。
- 科研问答上下文包含批量 findings、TOP 药物、ADR 分类、置信度分布和 Neo4j GraphRAG 预览。
- 回答由运行时配置中的外部 LLM API 生成；如果未配置 API Key，接口返回明确错误，提示到“系统配置”页配置。
- 返回结果包含 `answer`、`citations`、`confidence`、`used_agents` 和 `limitations`，前端会展示证据来源、参与 Agent 和置信度。

仍未完成：
- 问答当前基于页面已生成上下文，不会额外实时检索 PubMed/DrugBank/Neo4j。
- Neo4j 仍是预览图谱，尚未接入持久化 driver 查询。
- PubMed/BioDEX 批量真实处理与 FAERS 官方季度离线计算仍在下一阶段。

## 8. 2026-07-23 开发记录：SIDER/MedDRA 离线索引

本轮完成 SIDER/MedDRA 本地数据包的离线构建链路，面向后续 RAG 检索和 Neo4j 图数据库导入。

新增文件：
```text
pharmagent/adr/sider_index.py
scripts/build_sider_meddra_index.py
tests/test_adr/test_sider_index.py
```

生成产物默认输出到已忽略的本地目录：
```text
data/processed/sider_meddra/
```

产物包括：
- `rag_documents.jsonl`：按 drug CID 聚合的 SIDER/MedDRA RAG 文档块，保留 `source_type=offline_real_dataset`、`drug_cid`、`meddra_cui`、`frequency` 和 `source_file`。
- `neo4j/drugs.csv`、`neo4j/meddra_terms.csv`、`neo4j/drug_side_effect_edges.csv`、`neo4j/meddra_normalization_edges.csv`：Neo4j import CSV。
- `neo4j/import.cypher`：约束、节点导入和关系导入脚本。
- `manifest.json`：构建摘要和产物路径。

本地全量构建结果：
- Drug CID：1430
- MedDRA/SideEffect 节点：6061
- HAS_SIDE_EFFECT 边：153285
- NORMALIZED_TO 边：2075
- RAG 文档块：968

前端科研批量 ADR 挖掘页现在会展示离线索引产物是否已生成、核心计数和产物路径。该状态只说明本地 SIDER/MedDRA 数据包已经离线物化，不代表 PubMed、DrugBank 或 Neo4j driver 已经实时接入。

## 9. 2026-07-23 开发记录：SIDER/MedDRA RAG 真检索

本轮继续完成 P1：将已物化的 SIDER/MedDRA 文档块构建为可检索本地知识库，并接入问答上下文。

新增文件：
```text
pharmagent/adr/side_effect_rag.py
pharmagent/api/routes/rag.py
scripts/build_side_effect_rag.py
tests/test_adr/test_side_effect_rag.py
```

新增接口：
```text
GET  /api/rag/side-effects/status
POST /api/rag/side-effects/search
```

默认生成目录：
```text
data/side_effect_rag/
```

生成产物：
- `documents.jsonl`：面向 RAG 检索的文档块，字段包含 `doc_id`、`drug_cid`、`drug_name`、`side_effects`、`source_type=offline_real_dataset`。
- `bm25/`：BM25 稀疏检索索引。
- `chroma/`：Chroma 本地向量索引。当前使用确定性 hash embedding，避免现场运行依赖外部模型下载；因此只能作为轻量向量召回，不声称等价于医学语义 embedding。
- `manifest.json`：RAG 构建状态。

问答接入：
- `ReportQAAgent` 会根据当前病例/科研报告中的 drug 和 ADR，加上用户问题检索 SIDER/MedDRA RAG。
- 命中的离线真实证据会加入 LLM 上下文与 citations，`source_type` 标记为 `offline_real_dataset`。
- 若 RAG 索引未构建，问答不会编造 SIDER/MedDRA 结果。

前端更新：
- 科研批量 ADR 挖掘页新增 SIDER/MedDRA RAG 检索台，可直接输入药物和 ADR 查看本地索引命中。
- 页面明确标注该能力来自本地 SIDER/MedDRA 离线真实数据源，不代表 PubMed/DrugBank/FAERS 官方季度实时接入。

## 10. 2026-07-23 开发记录：Neo4j live 查询接口

本轮完成 P2 的后端真实查询基础：系统可以连接用户在系统配置页填写的 Neo4j 实例，并执行只读图查询。

新增文件：
```text
pharmagent/adr/neo4j_graph.py
pharmagent/api/routes/graph.py
tests/test_adr/test_neo4j_graph.py
```

新增接口：
```text
GET  /api/graph/status
POST /api/graph/query
POST /api/graph/expand
POST /api/graph/drug-side-effects
```

实现边界：
- Neo4j driver 从 `data/runtime/api_config.json` 中读取 URI、用户名、密码和 database。
- `/api/graph/query` 只允许只读 Cypher，阻止 `CREATE/MERGE/DELETE/SET/LOAD CSV` 等写入或导入语句。
- 未配置密码、未安装 driver 或连接失败时返回明确错误；不会回退到 demo 图谱。
- 当前前端科研页新增 Neo4j live 查询卡片，可显示配置/连接状态，并在连接成功后查询药物副作用边。

仍未完成：
- 需要用户实际运行 `neo4j/import.cypher` 导入前一阶段 CSV 后，live 查询才会返回真实图数据。
- 前端主图谱仍是 SVG/预览图谱；下一阶段可将 live 查询返回的 nodes/relationships 接入可展开图谱，再升级为 3D。

## 11. 2026-07-23 开发记录：Neo4j live 图谱前端交互

本轮在科研批量 ADR 挖掘页中继续推进 P2 前端展示，把 Neo4j live 查询结果从“计数/状态”升级为可交互图谱预览。

实现要点：
- `frontend/src/api.ts` 新增 `neo4jExpand(node_id, depth, relationship_types, limit)`。
- `Neo4jLivePanel` 支持：
  - 输入药物名或 CID 查询 `/api/graph/drug-side-effects`；
  - 将返回的 `nodes/relationships` 转为 Neo4j 图谱预览；
  - 显示节点数、关系数、source type 和实际 Cypher；
  - 按关系类型筛选；
  - 选择 1 跳或 2 跳展开深度；
  - 点击节点调用 `/api/graph/expand` 并合并新图数据；
  - 显示当前节点属性详情。

真实化边界：
- 只有 Neo4j 状态为 `configured=true` 且 `connected=true` 时查询按钮才可用。
- 未配置或连接失败时，页面只显示配置/连接错误，不展示伪造 live 图。
- 该阶段先稳定 `nodes/relationships` 数据契约；图谱渲染已在下一阶段替换为 Three.js / react-force-graph-3d。

## 12. 2026-07-23 开发记录：Neo4j 真 3D 图谱

本轮完成 P3 的前端图谱升级：科研批量 ADR 挖掘页的 Neo4j 图谱预览不再使用 SVG 伪 3D，而是通过 WebGL 渲染真正可旋转、可缩放、可点击的 3D 力导向图。

新增依赖：
```text
react-force-graph-3d
three
@types/three
```

新增文件：
```text
frontend/src/components/Neo4j3DGraph.tsx
```

实现要点：
- `Neo4jPreview` 统一使用 `Neo4j3DGraph` 渲染本地 SIDER/MedDRA 样例图、科研 GraphRAG 结果和 Neo4j live 查询结果。
- 3D 组件按节点类型着色：`Drug` 蓝色、`SideEffect/MedDRATerm` 红色、`Evidence` 青色、`Lab` 绿色、`Mechanism` 紫色。
- 关系按类型着色并启用流动粒子：`HAS_SIDE_EFFECT`、`INCREASES_RISK`、`SUPPORTED_BY`、`NORMALIZED_TO` 都有独立视觉编码。
- 支持 hover 高亮、点击节点聚焦相机、点击节点触发 live Neo4j 一跳/两跳展开、点击关系显示证据属性。
- 组件通过 `React.lazy` 按需加载，避免 Three.js 进入首屏主 bundle。

真实化边界：
- 本地数据集预览来自已构建的 SIDER/MedDRA 离线真实数据源，`source_type` 仍标记为 `offline_real_dataset`。
- Neo4j live 结果只来自 `/api/graph/*` 真实查询；未配置或连接失败时不会展示伪造 live 图。
- 3D 图谱只负责渲染和交互，不新增任何药物、ADR、文献或风险指标推断。

## 13. 2026-07-23 开发记录：FAERS 官方季度离线缓存第一版

本轮完成 P4 的后端第一版：系统可以把用户本地提供的 FAERS quarterly ASCII/CSV 数据构建为离线缓存，并基于去重 case 计算药物-ADR 不成比例信号。

新增文件：
```text
pharmagent/adr/faers_cache.py
pharmagent/api/routes/faers.py
scripts/build_faers_cache.py
tests/test_adr/test_faers_cache.py
```

新增接口：
```text
GET  /api/faers/status
POST /api/faers/signal
```

默认生成目录：
```text
data/faers/
```

构建方式：
```text
python scripts/build_faers_cache.py --source data/incoming/faers/2025q4 --source-label "FAERS 2025Q4"
```

实现要点：
- 支持从目录或 zip 读取 FAERS quarterly 文件，自动识别 `DEMO*`、`DRUG*`、`REAC*`、`OUTC*` ASCII/CSV/TSV 文件。
- 使用标准库 SQLite 作为第一版本地缓存，后续可替换为 DuckDB；接口和信号响应契约已按离线缓存场景设计。
- 按 `caseid` 优先、`primaryid` 兜底进行 case 去重。
- 计算二乘二表：`a=drug+adr`、`b=drug+non-adr`、`c=non-drug+adr`、`d=non-drug+non-adr`。
- 返回 `ROR`、`PRR`、报告数、严重病例数、死亡数、住院数、严重比例、年度趋势和性别分布。
- ADR 主流程 `FAERSSignalAgent` 在缓存存在时优先使用 `source_mode=offline_faers`；缓存不存在时才按原逻辑走实时 openFDA 或 demo/fallback。

真实化边界：
- 系统不会自动下载 FAERS 官方数据，也不会在缓存缺失时编造季度指标。
- 当前只做去重后的不成比例分析，未做混杂校正、暴露量校正或适应证偏倚控制。
- `offline_faers` 仍然是自发报告关联信号，不代表因果证明。

## 14. 2026-07-23 开发记录：科研批量真实处理第一版

本轮完成 P5 的第一版：科研批量 ADR 挖掘页可以处理用户提供的多条摘要、CSV 或 JSONL 文本，创建内存任务、轮询状态、生成结构化 findings、统计分布、Neo4j 预览图谱，并导出 CSV。

新增文件/接口：
```text
pharmagent/api/routes/research.py
tests/test_adr/test_research_batch.py

POST /api/research/batch-extract
GET  /api/research/jobs/{job_id}
GET  /api/research/jobs/{job_id}/export
```

实现要点：
- 输入支持 `plain`、`csv`、`jsonl` 和 `auto` 自动识别。
- 第一版任务系统为内存 job store：`pending/running/completed/failed`，返回 `job_id`、处理进度、finding 数量和完整 `ResearchMiningReport`。
- 抽取器采用保守规则：只有在同一证据句中同时命中药物和 ADR 术语时才产出 finding；不会为未出现的药物、ADR 或 PMID 补全证据。
- 输出复用科研页现有统计、findings 表和 3D Neo4j 图谱预览。
- CSV 导出包含 `document_id`、`pmid`、`drug`、`adverse_event`、`confidence`、`evidence_span` 和 `source`。

真实化边界：
- 当前处理的是用户提供文本，不会联网检索 PubMed/BioDEX。
- 当前不是医学 NER 模型，只是可审计的第一版保守抽取；后续可接入 LLM schema、PubMed E-utilities、BioDEX 数据集或 SciSpacy/MedCAT。
- 内存 job store 重启后会丢任务；比赛演示稳定，生产版需要 SQLite/Redis/Celery。

## 15. 2026-07-23 开发记录：多药高阶风险分析第一版

本轮完成 P6 的第一版：系统新增多药组合分析入口，支持输入 2 个及以上药物和患者因素，输出单药风险、两两相互作用、高阶机制风险、处置建议和 3D 机制图谱。

新增文件/接口：
```text
pharmagent/adr/polypharmacy.py
pharmagent/api/routes/polypharmacy.py
frontend/src/components/PolypharmacyAnalysis.tsx
tests/test_adr/test_polypharmacy.py

POST /api/polypharmacy/analyze
```

实现要点：
- 第一版使用规则 + 本地 SIDER/MedDRA RAG 辅助证据 + Neo4j 风格机制图，不训练 HODDI 模型。
- 内置高风险模式包括：
  - 抗凝药 + NSAID/抗血小板药：出血风险；
  - NSAID + ACEI/ARB + 利尿剂：triple whammy AKI 风险；
  - 二甲双胍 + eGFR < 30：乳酸酸中毒高危/禁忌场景；
  - 高龄/房颤背景下抗凝 + NSAID：高阶出血脆弱性。
- 前端新增“多药高阶风险”模块，展示综合风险等级、单药证据、两两机制、高阶机制、处置建议和 3D 机制图谱。

真实化边界：
- 当前不输出风险增幅百分比，不声称为 HODDI 或临床验证预测模型。
- 规则命中和本地 RAG/FAERS/SIDER 证据只支持风险识别与解释，不证明个体因果关系。
- 未命中规则不代表无风险；仍需结合剂量、适应证、肝肾功能、实验室指标和真实临床判断。

## 16. 2026-07-23 开发记录：ADR PDF 报告导出

本轮完成 P7 第一版：临床个案 ADR 分析结果可以导出为 PDF 报告，同时后端保留 HTML 报告渲染能力。

新增文件/接口：
```text
pharmagent/adr/pdf_report.py
tests/test_adr/test_pdf_report.py

POST /api/adr/report/html
POST /api/adr/report/pdf
```

实现要点：
- PDF 使用 `reportlab` 生成，测试使用 `pypdf` 验证可读性。
- 报告内容来自当前 `ADRAnalysisReport`，不会重新计算或补造证据。
- 内容包括病例摘要、核心建议、抽取结果、时间轴、FAERS/openFDA 信号、Naranjo/WHO-UMC 因果评分、证据链、图谱节点/关系、限制说明和完整报告文本。
- ADR 前端 Summary 区新增“下载 PDF 报告”按钮，下载当前报告的 PDF。

真实化边界：
- PDF 是当前系统分析结果的导出版，不代表临床最终诊断或监管级报告。
- 图谱截图尚未嵌入 PDF；第一版以节点/关系表保留可审计结构。
- 报告中的 FAERS/openFDA/SIDER/Neo4j 内容沿用原报告的 `source_mode` 和限制说明。

## 17. 后续剩余步骤

按当前完成度，剩余主要是：
- P5 增强：接入 PubMed query 拉取、BioDEX 数据导入、LLM schema 批量抽取和 SQLite/Redis 持久化任务队列。
- P6 增强：接入真实 DDI/DrugBank/文献证据源、把 FAERS 离线信号纳入组合证据摘要、增加剂量和实验室指标规则。
- P7 增强：嵌入图谱截图、增加报告模板主题、支持科研批量报告导出和多药风险报告导出。
- 展示增强：继续做最终演示打磨、移动端微调和 3D 图谱 bundle 优化。

## 18. 2026-07-23 开发记录：ADR 信号页真实来源展示

本轮完成展示增强的一部分：ADR 信号页现在会展示当前信号的来源、来源类型、去重状态和二乘二表。

实现要点：
- `OpenFDASignal` schema 增加 `source`、`source_type`、`deduplicated`、`contingency_table`、`serious_ratio` 字段。
- `offline_faers` 结果会把真实离线缓存的二乘二表传入 ADR 报告。
- `realtime_openfda` 结果会标注为实时 openFDA API，且 `deduplicated=false`。
- 前端 ADR 信号页按 `offline_faers` / `realtime_openfda` / `fallback_demo` / `local_demo` 分层展示来源标签。
- 若当前来源未返回年度趋势或完整二乘二表，页面明确提示，不使用伪造趋势或指标占位。

## 19. 2026-07-23 开发记录：系统配置页 FAERS 缓存状态

本轮完成系统配置页的 FAERS 离线缓存可见性增强。

实现要点：
- 系统配置页加载 `GET /api/faers/status`。
- 右侧运行状态面板新增“FAERS 离线缓存”区块。
- 已接入缓存时展示来源标签、病例数、药物记录数、ADR 记录数、去重口径和缓存路径。
- 未接入缓存时明确提示系统会继续标注 demo/fallback/openFDA 来源，不暗示真实 FAERS 已可用。

## 20. 2026-07-23 开发记录：ADR 3D 图谱证据抽屉与收尾

本轮完成 ADR 个案图谱页展示增强。

实现要点：
- ADR 图谱页签从旧 SVG 伪 3D 切换为 `Neo4j3DGraph` WebGL 组件。
- 当前 `ADRKnowledgeGraph` 会在前端映射为 Neo4j preview 结构，不新增或伪造证据。
- 右侧新增证据抽屉，展示选中节点、选中关系、相邻关系和报告证据链。
- 高危路径独立成块展示，可点击路径节点联动图谱选择。
- `Neo4j3DGraph` 继续按需加载，避免把 Three.js 主动打进首页主 bundle。
- 移除 ADR 图谱页旧 SVG 伪 3D 不可达代码和旧布局 helper。
- Vite `chunkSizeWarningLimit` 调整为 1600KB；当前大 chunk 是按需加载的 Three.js/WebGL 图谱包，主 bundle 保持约 240KB。

验证记录：
- Playwright mock ADR 报告进入图谱页，截图保存到 `data/runtime/adr-3d-graph.png`。
- 使用截图下半区像素采样确认 3D 图谱非空渲染；`react-force-graph-3d` 的 WebGL framebuffer 读取可能返回 0，因此最终判定以用户可见截图为准。
