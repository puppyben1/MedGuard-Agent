# MedGuard-Agent — 证据约束的临床处方审查智能体

> 输入自由文本病例（中英文均可），输出结构化用药风险报告，每条风险发现均可溯源到药品说明书或医学文献。

**第八届中国研究生人工智能创新大赛** 参赛项目。

---

## 目录

- [核心能力](#核心能力)
- [界面演示](#界面演示)
- [系统架构](#系统架构)
- [三层安全防线](#三层安全防线)
- [混合检索](#混合检索)
- [中英文双语支持](#中英文双语支持)
- [评估结果](#评估结果)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [API 文档](#api-文档)
- [项目结构](#项目结构)
- [开发日志](#开发日志)
- [许可证](#许可证)

---

## 核心能力

**双模式智能体**：

| 模式 | 流程 | 输入 | 输出 |
|------|------|------|------|
| **处方审查** | 7 节点 LangGraph | 自由文本病例（年龄/性别/诊断/eGFR/肝功能/INR/过敏史/处方药物） | `PrescriptionReport`：风险等级 + 逐条 finding + 证据 + 置信度 |
| **药物安全问答** | 6 节点 agentic RAG | 自然语言问题 | `SafetyAssessment`：风险等级 + 证据 + 禁忌 + 监测建议 + 引用 |

**覆盖的风险维度**：药物相互作用、绝对禁忌、剂量风险、肾功能风险、肝功能风险、妊娠/哺乳风险、过敏交叉反应、需要监测。

---

## 界面演示

React + TypeScript + Tailwind CSS 前端，完全中文化界面。

### 主界面

![主界面](docs/images/ui-home.png)

### 处方审查 — 病例输入

![处方审查输入](docs/images/ui-prescription-input.png)

### 处方审查 — 风险报告

![处方审查报告](docs/images/ui-prescription-report.png)

### 药物安全问答

![药物安全问答](docs/images/ui-qa.png)

### 评估结果

![评估结果](docs/images/ui-evaluation.png)

---

## 系统架构

### 处方审查流水线（7 节点 LangGraph）

```
病例文本（自由文本，中英文均可）
    │
    ▼
┌─────────────────────┐
│  节点1: 病例解析     │  LLM 主解析 + 正则回退 → PatientCase
│  parse_case         │  （年龄/性别/eGFR/肝功能/INR/过敏/药物）
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点2: 子查询构建   │  逐药物 + 逐药物对 + 逐诊断
│  build_queries      │  （携带患者上下文）
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点3: 混合检索     │  BM25 + ChromaDB + RRF 融合 + Cross-Encoder 重排
│  retrieve           │  （三知识库并行检索，去重聚合）
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点4: 文档评分     │  LLM 逐文档相关性打分，丢弃无关 chunk
│  grade_docs         │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点5: 处方检查     │  确定性规则（11 条）+ LLM 证据驱动 finding
│  check_prescription │  （基于检索证据生成结构化风险发现）
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点6: 证据核验     │  逐 finding 核验：关键词预检 → LLM 兜底
│  verify_evidence    │  （高/危级未验证 → 触发幻觉标记）
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点7: 报告生成     │  PrescriptionReport：风险等级 + findings +
│  compile_report     │  证据覆盖 + 幻觉标记 + 引用 + 耗时
└─────────────────────┘
```

### 药物安全问答流水线（6 节点 agentic RAG）

```
用户问题
    │
    ▼
┌─────────────────────┐
│  节点1: 分析路由     │  分类问题类型、识别药物、选择知识库
│  analyze_route      │  （含中文药名归一化与 OOV 检测）
└─────────┬───────────┘
          │ 合法查询              非法查询 ──► 拒绝（含原因）
          ▼
┌─────────────────────┐
│  节点2: 检索         │  混合检索（BM25 + 向量）
│  retrieve           │  FDA 说明书 / PubMed / 临床指南
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点3: 文档评分     │  LLM 相关性打分，丢弃无关 chunk
│  grade_docs         │
└─────────┬───────────┘
          │ 相关文档足够？
          │ 否 ──► ┌──────────────────┐
          │        │ 节点4: 查询重写   │ ──► 回到节点2（最多 2 次重试）
          │        └──────────────────┘
          │ 是
          ▼
┌─────────────────────┐
│  节点5: 生成         │  LLM 综合结构化安全评估，含内联引用
│  generate           │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  节点6: 幻觉检查     │  验证：(a) 每条 claim 有源文档支撑
│  check_hallucination│  (b) 回答确实针对用户问题
└─────────┬───────────┘
          │ 失败？──► 回到节点5（最多 1 次重试）
          │ 通过
          ▼
     最终安全评估
     （风险等级 · 证据 · 禁忌 · 监测 · 引用）
```

---

## 三层安全防线

确定性规则保证已知绝对禁忌永不漏报，LLM 证据约束保证 finding 可溯源，独立 evidence_verifier 兜底抗幻觉。

### 确定性规则层（11 条硬编码安全规则）

| 规则 | 触发条件 | 严重度 |
|------|----------|--------|
| 妊娠致畸 | ACEI/ARB/华法林/甲氨蝶呤 + `pregnancy=true` | critical |
| 二甲双胍 + 严重 CKD | 二甲双胍 + eGFR < 30 | critical |
| 二甲双胍 + 中度 CKD | 二甲双胍 + eGFR 30–45 | high（renal_risk） |
| 抗凝 + 抗血小板 | 华法林/DOAC + 阿司匹林/氯吡格雷 | high |
| 抗凝 + NSAID | 华法林/DOAC + 布洛芬/萘普生等 | high |
| 超治疗 INR | INR ≥ 4 且合并出血风险药物 | high（≥5 → critical） |
| GLP-1 + MTC/MEN 2 | 司美格鲁肽/利拉鲁肽 + 个人/家族史 | critical |
| 过敏精确匹配 | 文献过敏史与当前处方药物匹配 | critical |
| 青霉素→头孢交叉 | 青霉素过敏 + 头孢菌素处方 | moderate |
| 三重肾损伤 | NSAID + ACEI/ARB + eGFR < 60 | moderate / high |
| 肝毒性 + 肝功能异常 | 对乙酰氨基酚/他汀/异烟肼 + 中重度肝异常 | moderate / high |

### LLM 证据驱动层

基于检索到的文档 snippet 生成结构化 finding，每条 finding 必须引用 `evidence_doc_ids`。多窗口滑动锚点 + 词重叠 fallback 把 snippet 映射回 doc_id。

### 证据核验层

`evidence_verifier` 对每条 finding 执行三级核验：

| 路径 | 流程 | 结果 |
|------|------|------|
| Path A | checker 提供 doc_id → 关键词预检通过 | verified=True |
| Path B | checker 提供 doc_id → 关键词预检失败 → LLM verifier 兜底 | LLM 判定 |
| Path C | checker 无 doc_id（确定性规则来源） | rule-based verified，不触发幻觉 |

**高/危级 finding 未验证 → `hallucination_flagged=True`**，在报告中醒目提示药师复核。

---

## 混合检索

每个知识库使用 **BM25 + ChromaDB 向量 + RRF + Cross-Encoder** 四步流水线：

1. **BM25**（关键词匹配）— 精确药名与医学术语匹配
2. **ChromaDB 向量检索**（`all-MiniLM-L6-v2`）— 语义相似召回
3. **Reciprocal Rank Fusion（RRF）** — 融合两路排序结果
4. **Cross-Encoder 重排**（`cross-encoder/ms-marco-MiniLM-L-6-v2`）— 终精排

### 三大知识库

| 来源 | 内容 | 用途 |
|------|------|------|
| **FDA DailyMed** | 官方药品说明书 XML（~15 万药物） | 警告、剂量、禁忌的事实基准 |
| **PubMed（MedRAG）** | 2390 万生物医学研究 snippet | 相互作用与不良事件的发表证据 |
| **StatPearls/Textbooks** | 9330 篇临床参考文章 | 循证临床指南与诊疗规范 |

### 离线模式

已强制启用 HuggingFace 离线模式（`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`local_files_only=True`），避免模型加载时尝试连接 `huggingface.co` 导致 30 秒超时。模型首次运行时下载缓存，之后完全本地推理。

---

## 中英文双语支持

### 病例解析

- **LLM 主解析**：支持中英文混合病例文本，输出结构化 `PatientCase`
- **正则回退**：LLM 失败时用正则表达式提取年龄/性别/eGFR/药物
- **中文药名映射**：60+ 中文药名→英文通用名（`二甲双胍→metformin`、`华法林→warfarin` 等）
- **中文剂量识别**：`毫克/微克/毫升/片/粒` + `每日一次/每天两次` 等中文频次

### 中文问答

- **查询归一化**：`normalize_query_language()` 把中文药名/临床术语翻译为英文，供检索索引匹配
- **ASCII 字母边界**：使用 `(?<![a-z])...(?![a-z])` 替代 `\b`，避免 Unicode 下中文字符被当作 `\w` 导致 "metformin的" 不匹配
- **临床术语映射**：`禁忌症→contraindications`、`不良反应→adverse effects`、`相互作用→drug interactions` 等

### 中文显示

- 60+ 英文药名→中文显示名（`cn_drug_name()`）
- 诊断、性别、肝功能、频次、finding 类型、严重度全套中文标签（`cn_labels.py`）
- 前端完全中文化

---

## 评估结果

10 个 golden case（中英文混合），覆盖妊娠、严重 CKD、三重出血、黑框警告、过敏交叉、三重肾损伤、阴性对照等场景。

| 指标 | 目标 | 实际 | 说明 |
|------|------|------|------|
| Micro Recall | > 0.85 | **0.909** | 期望 finding 的召回率 |
| Micro F1 | > 0.80 | 0.541 | 精确率与召回率的调和均值 |
| Evidence hit rate | > 0.80 | **1.000** | finding 有源文档支撑的比例 |
| Hallucination rate | < 0.10 | **0.000** | 高/危级 finding 无证据支撑的比例 |
| Avg response time | < 30s | **16.8s** | 端到端单 case 平均耗时 |

**关键结论**：Recall 与 Evidence hit rate 达标，Hallucination rate 为 0（无任何高危 finding 缺失证据）。F1 偏低是因为系统会保守地多报 finding（宁可多报不漏报），符合医疗安全优先原则。

运行评估：

```bash
python -m pharmagent.evaluation.prescription_eval
```

结果写入 `data/prescription_eval_results.json` 与 `prescription_eval_results.md`。

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 智能体编排 | LangGraph | 状态化、可循环的 AI 工作流 |
| LLM 推理 | DeepSeek / Groq（Llama 3.x） | DeepSeek 为主，Groq 为备选；均支持免费额度 |
| 向量数据库 | ChromaDB | 嵌入式、零配置、Apache 2.0 |
| 关键词检索 | rank-bm25 | 与向量检索互补，精确药名匹配 |
| Embedding | sentence-transformers（`all-MiniLM-L6-v2`） | 本地 CPU 推理，<50ms/次 |
| 重排 | Cross-Encoder（`ms-marco-MiniLM-L-6-v2`） | 终精排提升精度 |
| 后端 API | FastAPI + Uvicorn | 4 个端点，CORS 已配置 |
| 前端 | React 18 + Vite + TypeScript + Tailwind CSS | 完全中文化界面 |
| 配置 | pydantic-settings | 类型安全的环境变量管理 |
| 日志 | structlog | 结构化 JSON 日志 |
| 可观测性 | Langfuse（可选，自托管） | 追踪每个智能体决策 |
| 测试 | pytest | 35 项单元测试全通过 |

---

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- DeepSeek 或 Groq API Key（免费额度即可）

### 1. 克隆并安装后端

```bash
git clone https://github.com/puppyben1/MedGuard-Agent.git
cd MedGuard-Agent
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 或 GROQ_API_KEY
```

### 3. 构建索引（首次运行，约 5-10 分钟）

```bash
python scripts/ingest_demo.py
```

下载并索引 22 种常用门诊药物的 FDA 说明书、PubMed 文献、临床指南到 ChromaDB 与 BM25。

### 4. 启动后端

```bash
python -m uvicorn pharmagent.api.main:app --port 8000 --host 0.0.0.0
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用。

### 编程方式调用

```python
from pharmagent.prescription.graph import run_prescription_review

case_text = """
68岁男性，2型糖尿病，慢性肾脏病4期。eGFR 18 mL/min/1.73m^2。
当前处方：二甲双胍 1000毫克 每日两次，格列吡嗪 5mg 每日一次。
无药物过敏史。肝功能正常。
"""

report = run_prescription_review(case_text)
print(report.overall_risk_level)        # 'critical'
print(report.evidence_coverage)         # finding 有证据支撑的比例
print(report.hallucination_flagged)     # 高/危级 finding 缺证据时为 True
for f in report.findings:
    print(f.severity, f.finding_type, f.drugs_involved, f.verified)
```

---

## API 文档

后端启动后访问 http://localhost:8000/docs 查看 Swagger UI。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 + LLM 预算剩余 |
| `/api/prescription` | POST | 处方审查（病例文本 → 报告） |
| `/api/qa` | POST | 药物安全问答（问题 → 评估） |
| `/api/examples` | GET | 示例病例与问题 |

**处方审查请求示例**：

```json
{
  "case_text": "74岁男性，房颤，骨关节炎。INR 3.2。处方：华法林 5mg 每日一次，阿司匹林 81mg 每日一次，布洛芬 600mg 每日三次 必要时。eGFR 70。无过敏。"
}
```

**问答请求示例**：

```json
{
  "query": "肾功能不全患者使用二甲双胍的禁忌症有哪些？"
}
```

---

## 项目结构

```
MedGuard-Agent/
├── pharmagent/
│   ├── agent/                          # 药物安全问答智能体（6 节点）
│   │   ├── graph.py                    # LangGraph 状态图定义
│   │   ├── nodes.py                    # 各节点逻辑（分析/检索/评分/重写/生成/幻觉检查）
│   │   ├── state.py                    # AgentState TypedDict
│   │   └── llm.py                      # LLM 客户端 + 预算追踪
│   ├── api/                            # FastAPI 后端
│   │   ├── main.py                     # 应用入口（CORS、路由注册）
│   │   └── routes/                     # 4 个 API 端点
│   │       ├── prescription.py         # /api/prescription
│   │       ├── qa.py                   # /api/qa
│   │       └── examples.py             # /api/examples
│   ├── core/                           # 共享基础设施
│   │   ├── hybrid_retriever.py         # BM25 + ChromaDB + RRF + Cross-Encoder
│   │   ├── document_grader.py          # LLM 相关性打分
│   │   ├── query_rewriter.py           # 检索失败时查询重写
│   │   ├── synthesizer.py              # 安全评估生成
│   │   ├── hallucination_checker.py    # 忠实度 + 回答相关性验证
│   │   ├── safety_guardrails.py        # 确定性安全防线（OOV 检测、风险升级）
│   │   ├── schemas.py                  # SafetyAssessment Pydantic 模型
│   │   ├── vectorstore.py              # ChromaDB 客户端
│   │   ├── bm25_store.py               # BM25 索引持久化
│   │   └── embeddings.py               # Sentence-Transformer 向量化
│   ├── prescription/                   # 处方审查子包（7 节点）
│   │   ├── graph.py                    # 处方审查 LangGraph
│   │   ├── case_parser.py              # 病例文本 → PatientCase（LLM + 正则）
│   │   ├── prescription_checker.py     # 11 条确定性规则 + LLM finding
│   │   ├── evidence_verifier.py        # 逐 finding 证据核验（三级）
│   │   ├── cn_labels.py                # 中文显示标签与翻译
│   │   ├── schemas.py                  # PatientCase / PrescriptionFinding / PrescriptionReport
│   │   └── state.py                    # PrescriptionState TypedDict
│   ├── ingestion/                      # 数据摄取与索引构建
│   │   ├── dailymed.py                 # DailyMed XML 下载解析
│   │   ├── medrag_loader.py            # PubMed + StatPearls 加载
│   │   ├── chunker.py                  # 文本分块
│   │   └── build_index.py              # 索引构建流水线
│   ├── evaluation/                     # 评估
│   │   ├── prescription_eval.py        # 处方审查评估脚本
│   │   ├── prescription_golden_set.py  # 10 个 golden case
│   │   └── run_eval.py                 # QA 评估脚本
│   ├── ui/                             # 旧版 Streamlit UI（已弃用，保留兼容）
│   ├── __init__.py                     # 离线模式环境变量设置
│   ├── config.py                       # 集中式配置
│   └── logging_config.py               # structlog 配置
├── frontend/                           # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── PrescriptionReview.tsx  # 处方审查组件
│   │   │   └── DrugSafetyQA.tsx        # 药物问答组件
│   │   ├── App.tsx                     # 应用根组件
│   │   ├── api.ts                      # API 调用封装
│   │   ├── labels.ts                   # 前端中文标签
│   │   └── types.ts                    # TypeScript 类型定义
│   ├── package.json
│   ├── vite.config.ts                  # Vite 配置（含 /api 代理到 8000）
│   └── tailwind.config.js
├── scripts/
│   ├── ingest_demo.py                  # 演示数据摄取（22 种药物）
│   └── enrich_pubmed.py                # PubMed 数据补充
├── tests/                              # 35 项单元测试
├── docs/images/                        # UI 截图
├── data/                               # 索引与评估结果（gitignore）
├── .env.example                        # 环境变量模板
├── pyproject.toml                      # Python 项目配置
└── README.md
```

---

## 开发日志

详细的开发过程记录见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

### 主要版本

| 版本 | 内容 |
|------|------|
| v0.3.0 | React + FastAPI 重构，全中文界面，离线模式修复，中文药名检测修复 |
| v0.2.0 | MedGuard-Agent 处方审查子包初版（7 节点 LangGraph） |
| v0.1.0 | PharmAgent 药物安全问答（6 节点 agentic RAG） |

---

## 许可证

MIT License — 见 [LICENSE](LICENSE)。
