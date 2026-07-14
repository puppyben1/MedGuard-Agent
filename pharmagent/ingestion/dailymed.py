"""Download and parse FDA drug labels from the DailyMed REST API."""

from __future__ import annotations

import httpx
from lxml import etree

from pharmagent.logging_config import get_logger

logger = get_logger(__name__)

DAILYMED_SEARCH = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
DAILYMED_SPL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"

# SPL XML sections we care about (LOINC codes)
SECTION_LOINC = {
    "34071-1": "warnings",
    "34073-7": "drug_interactions",
    "34084-4": "adverse_reactions",
    "34070-3": "contraindications",
    "34068-7": "dosage_and_administration",
    "34089-3": "description",
    "43685-7": "warnings_and_precautions",
}

SPL_NS = {"spl": "urn:hl7-org:v3"}


def _extract_text(elem: etree._Element) -> str:
    """Recursively extract all text from an XML element."""
    parts: list[str] = []
    for text_node in elem.itertext():
        stripped = text_node.strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts)


def _parse_spl_xml(xml_bytes: bytes, drug_name: str, setid: str) -> list[dict]:
    """Parse SPL XML and extract relevant sections."""
    docs: list[dict] = []
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        logger.warning("xml_parse_failed", drug=drug_name, setid=setid)
        return docs

    for component in root.iter("{urn:hl7-org:v3}component"):
        for section in component.iter("{urn:hl7-org:v3}section"):
            code_elem = section.find("spl:code", SPL_NS)
            if code_elem is None:
                continue
            loinc = code_elem.get("code", "")
            section_name = SECTION_LOINC.get(loinc)
            if section_name is None:
                continue

            text_elem = section.find("spl:text", SPL_NS)
            if text_elem is None:
                continue
            text = _extract_text(text_elem)
            if len(text) < 20:
                continue

            docs.append(
                {
                    "drug_name": drug_name,
                    "section": section_name,
                    "text": text,
                    "source": "dailymed",
                    "source_url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
                }
            )
    return docs


def fetch_drug_labels(drug_names: list[str]) -> list[dict]:
    """Fetch and parse drug labels for a list of drug names from DailyMed."""
    all_docs: list[dict] = []

    with httpx.Client(timeout=30) as client:
        for drug in drug_names:
            logger.info("fetching_dailymed", drug=drug)
            try:
                resp = client.get(DAILYMED_SEARCH, params={"drug_name": drug, "pagesize": 1})
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("dailymed_search_failed", drug=drug, error=str(exc))
                continue

            results = data.get("data", [])
            if not results:
                logger.warning("no_results", drug=drug)
                continue

            setid = results[0].get("setid", "")
            if not setid:
                continue

            try:
                spl_resp = client.get(DAILYMED_SPL.format(setid=setid))
                spl_resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("spl_fetch_failed", drug=drug, error=str(exc))
                continue

            docs = _parse_spl_xml(spl_resp.content, drug, setid)
            logger.info("parsed_sections", drug=drug, count=len(docs))
            all_docs.extend(docs)

    return all_docs
