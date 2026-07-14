"""Golden evaluation set: 10 hand-crafted queries for RAGAS evaluation."""

GOLDEN_QUERIES = [
    # Single-drug queries (2)
    {
        "query": "What are the contraindications for metformin?",
        "expected_keywords": ["renal", "kidney", "lactic acidosis", "eGFR"],
        "query_type": "single_drug",
    },
    {
        "query": "What are the common adverse effects of lisinopril?",
        "expected_keywords": ["cough", "hyperkalemia", "hypotension", "angioedema"],
        "query_type": "single_drug",
    },
    # Drug interaction queries (3)
    {
        "query": "What are the risks of taking warfarin and aspirin together?",
        "expected_keywords": ["bleeding", "hemorrhage", "INR", "anticoagulant", "antiplatelet"],
        "query_type": "multi_drug_interaction",
    },
    {
        "query": "Does metformin interact with lisinopril?",
        "expected_keywords": ["hypoglycemia", "renal", "kidney", "blood pressure"],
        "query_type": "multi_drug_interaction",
    },
    {
        "query": "What are the interaction risks between warfarin and lisinopril?",
        "expected_keywords": ["bleeding", "INR", "anticoagulant"],
        "query_type": "multi_drug_interaction",
    },
    # Patient-specific queries (3)
    {
        "query": "Is metformin safe for a 68-year-old patient with stage 3 CKD who is also taking lisinopril and warfarin?",
        "expected_keywords": ["renal", "CKD", "dose adjustment", "eGFR", "monitoring"],
        "query_type": "patient_specific",
    },
    {
        "query": "Is semaglutide safe for a patient with a history of pancreatitis?",
        "expected_keywords": ["pancreatitis", "GLP-1", "contraindicated", "risk"],
        "query_type": "patient_specific",
    },
    {
        "query": "Can a patient with heart failure safely take lisinopril and metformin together?",
        "expected_keywords": ["heart failure", "ACE inhibitor", "lactic acidosis", "monitoring"],
        "query_type": "patient_specific",
    },
    # Adverse event queries (2)
    {
        "query": "What cardiovascular adverse events have been reported with semaglutide?",
        "expected_keywords": ["cardiovascular", "heart rate", "cardiac", "MACE"],
        "query_type": "single_drug",
    },
    {
        "query": "What are the hepatic risks associated with metformin use?",
        "expected_keywords": ["liver", "hepatic", "lactic acidosis", "rare"],
        "query_type": "single_drug",
    },
]
