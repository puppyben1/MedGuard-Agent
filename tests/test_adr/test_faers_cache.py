from __future__ import annotations

from pathlib import Path

from pharmagent.adr.faers_cache import build_faers_cache, faers_status, query_faers_signal


def test_build_faers_cache_and_query_signal(tmp_path: Path) -> None:
    source = tmp_path / "faers_ascii"
    source.mkdir()
    (source / "DEMO25Q4.txt").write_text(
        "\n".join(
            [
                "primaryid$caseid$fda_dt$sex",
                "1$100$20250101$F",
                "2$101$20250102$M",
                "3$102$20250103$F",
                "4$103$20250104$M",
            ]
        ),
        encoding="utf-8",
    )
    (source / "DRUG25Q4.txt").write_text(
        "\n".join(
            [
                "primaryid$caseid$drugname$role_cod",
                "1$100$Warfarin$PS",
                "2$101$Warfarin$PS",
                "3$102$Ibuprofen$PS",
                "4$103$Metformin$PS",
            ]
        ),
        encoding="utf-8",
    )
    (source / "REAC25Q4.txt").write_text(
        "\n".join(
            [
                "primaryid$caseid$pt",
                "1$100$Gastrointestinal bleeding",
                "2$101$Headache",
                "3$102$Gastrointestinal bleeding",
                "4$103$Nausea",
            ]
        ),
        encoding="utf-8",
    )
    (source / "OUTC25Q4.txt").write_text(
        "\n".join(
            [
                "primaryid$caseid$outc_cod",
                "1$100$HO",
                "2$101$OT",
                "3$102$DE",
            ]
        ),
        encoding="utf-8",
    )

    cache_path = tmp_path / "faers.sqlite"
    status = build_faers_cache(source, cache_path, source_label="FAERS 2025Q4 test")
    assert status.available is True
    assert status.case_count == 4
    assert status.drug_case_count == 4

    reloaded = faers_status(cache_path)
    assert reloaded.available is True
    assert reloaded.source_label == "FAERS 2025Q4 test"

    signal = query_faers_signal("warfarin", "gastrointestinal bleeding", cache_path)
    assert signal.source_mode == "offline_faers"
    assert signal.report_count == 1
    assert signal.serious_count == 1
    assert signal.hospitalization_count == 1
    assert signal.death_count == 0
    assert signal.contingency_table == {"a": 1, "b": 1, "c": 1, "d": 1}
    assert signal.ror == 1.0
    assert signal.prr == 1.0
    assert signal.serious_ratio == 1.0
    assert signal.yearly_trend[0].year == 2025
