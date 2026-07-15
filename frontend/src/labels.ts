// Chinese display labels mirroring backend pharmagent/prescription/cn_labels.py
// so all user-facing text is Chinese regardless of backend output language.

import type { FindingType, HepaticFunction, Severity } from "./types";

export const SEX_CN: Record<string, string> = {
  male: "男性",
  female: "女性",
  unknown: "未知",
};

export const HEPATIC_CN: Record<HepaticFunction, string> = {
  normal: "正常",
  mild: "轻度异常",
  moderate: "中度异常",
  severe: "重度异常",
  unknown: "未知",
};

export const FINDING_TYPE_CN: Record<FindingType, string> = {
  drug_interaction: "药物相互作用",
  contraindication: "绝对禁忌",
  dose_risk: "剂量风险",
  renal_risk: "肾功能风险",
  hepatic_risk: "肝功能风险",
  pregnancy_risk: "妊娠风险",
  allergy_risk: "过敏风险",
  monitoring_required: "需要监测",
  missing_evidence: "证据缺失",
};

export const SEVERITY_CN: Record<Severity, string> = {
  low: "低",
  moderate: "中",
  high: "高",
  critical: "严重",
};

export const SEVERITY_COLOR: Record<Severity, string> = {
  low: "#16a34a",
  moderate: "#f59e0b",
  high: "#f97316",
  critical: "#dc2626",
};

const DRUG_CN: Record<string, string> = {
  metformin: "二甲双胍",
  warfarin: "华法林",
  lisinopril: "赖诺普利",
  semaglutide: "司美格鲁肽",
  aspirin: "阿司匹林",
  ibuprofen: "布洛芬",
  naproxen: "萘普生",
  acetaminophen: "对乙酰氨基酚",
  atorvastatin: "阿托伐他汀",
  simvastatin: "辛伐他汀",
  amlodipine: "氨氯地平",
  omeprazole: "奥美拉唑",
  losartan: "氯沙坦",
  hydrochlorothiazide: "氢氯噻嗪",
  gabapentin: "加巴喷丁",
  prednisone: "泼尼松",
  amoxicillin: "阿莫西林",
  azithromycin: "阿奇霉素",
  clopidogrel: "氯吡格雷",
  pantoprazole: "泮托拉唑",
  levothyroxine: "左甲状腺素",
  furosemide: "呋塞米",
  insulin: "胰岛素",
  glipizide: "格列吡嗪",
  empagliflozin: "恩格列净",
  liraglutide: "利拉鲁肽",
  rosuvastatin: "瑞舒伐他汀",
  valsartan: "缬沙坦",
  enalapril: "依那普利",
  ramipril: "雷米普利",
  diltiazem: "地尔硫卓",
  verapamil: "维拉帕米",
  digoxin: "地高辛",
  apixaban: "阿哌沙班",
  rivaroxaban: "利伐沙班",
  dabigatran: "达比加群",
  heparin: "肝素",
  enoxaparin: "依诺肝素",
  lithium: "碳酸锂",
  sertraline: "舍曲林",
  fluoxetine: "氟西汀",
  tramadol: "曲马多",
  glyburide: "格列本脲",
  penicillin: "青霉素",
  celecoxib: "塞来昔布",
  cephalexin: "头孢氨苄",
  cefuroxime: "头孢呋辛",
  ceftriaxone: "头孢曲松",
  cephalosporin: "头孢菌素",
};

const DIAGNOSIS_CN: Record<string, string> = {
  "atrial fibrillation": "房颤",
  af: "房颤",
  osteoporosis: "骨质疏松",
  osteoarthritis: "骨关节炎",
  "type 2 diabetes": "2型糖尿病",
  t2dm: "2型糖尿病",
  "type 2 diabetes mellitus": "2型糖尿病",
  diabetes: "糖尿病",
  hypertension: "高血压",
  htn: "高血压",
  "chronic kidney disease": "慢性肾脏病",
  ckd: "慢性肾脏病",
  "heart failure": "心力衰竭",
  hf: "心力衰竭",
  "coronary artery disease": "冠心病",
  cad: "冠心病",
  "deep vein thrombosis": "深静脉血栓",
  dvt: "深静脉血栓",
  "pulmonary embolism": "肺栓塞",
  pe: "肺栓塞",
  stroke: "脑卒中",
  hyperlipidemia: "高脂血症",
  hyperthyroidism: "甲亢",
  hypothyroidism: "甲减",
  "community-acquired pneumonia": "社区获得性肺炎",
  pneumonia: "肺炎",
  depression: "抑郁症",
  anxiety: "焦虑症",
  epilepsy: "癫痫",
  gout: "痛风",
  copd: "慢性阻塞性肺疾病",
  asthma: "哮喘",
  "atrial flutter": "房扑",
  "peripheral arterial disease": "外周动脉疾病",
  pad: "外周动脉疾病",
  "medullary thyroid cancer": "甲状腺髓样癌",
  mtc: "甲状腺髓样癌",
};

const FREQ_CN: Record<string, string> = {
  "once daily": "每日一次",
  qd: "每日一次",
  "q.d.": "每日一次",
  "twice daily": "每日两次",
  bid: "每日两次",
  "b.i.d.": "每日两次",
  "three times daily": "每日三次",
  tid: "每日三次",
  "t.i.d.": "每日三次",
  "four times daily": "每日四次",
  qid: "每日四次",
  "as needed": "必要时",
  prn: "必要时",
  "p.r.n.": "必要时",
  "every other day": "隔日一次",
  qod: "隔日一次",
  "at bedtime": "睡前",
  hs: "睡前",
};

export function cnDrugName(name: string): string {
  if (!name) return name;
  return DRUG_CN[name.trim().toLowerCase()] ?? name;
}

export function cnDiagnosis(text: string): string {
  if (!text) return text;
  const lower = text.trim().toLowerCase();
  if (DIAGNOSIS_CN[lower]) return DIAGNOSIS_CN[lower];
  let result = text;
  const entries = Object.entries(DIAGNOSIS_CN).sort((a, b) => b[0].length - a[0].length);
  for (const [en, cn] of entries) {
    const re = new RegExp(en.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    result = result.replace(re, cn);
  }
  return result;
}

export function cnFreq(freq: string): string {
  if (!freq) return "";
  return FREQ_CN[freq.trim().toLowerCase()] ?? freq;
}

export function cnSex(sex: string): string {
  return SEX_CN[sex] ?? sex;
}

export function cnHepatic(val: HepaticFunction): string {
  return HEPATIC_CN[val] ?? val;
}
