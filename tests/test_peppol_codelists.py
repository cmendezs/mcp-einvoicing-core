"""Tests for the Peppol eDEC code list parser and lookup functions
(CORE-PEPPOL-NETLIST-1). Uses synthetic Genericode fixtures written to
tmp_path, not the real specs/peppol/codelists/ files, so these tests do not
depend on that directory's presence (mirrors the rest of this test suite;
also keeps tests independent of the deployer-supplied data the module itself
never bundles).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_einvoicing_core.peppol import codelists


def _write_gc(
    directory: Path,
    filename: str,
    *,
    short_name: str,
    version: str,
    columns: list[str],
    rows: list[dict[str, str]],
) -> Path:
    column_xml = "\n".join(
        f'    <Column Id="{c}" Use="required"><ShortName>{c}</ShortName><Data Type="string" /></Column>'
        for c in columns
    )
    row_xml_parts = []
    for row in rows:
        values = "\n".join(
            f'      <Value ColumnRef="{k}"><SimpleValue>{v}</SimpleValue></Value>'
            for k, v in row.items()
        )
        row_xml_parts.append(f"    <Row>\n{values}\n    </Row>")
    rows_xml = "\n".join(row_xml_parts)

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<gc:CodeList xmlns:gc="http://docs.oasis-open.org/codelist/ns/genericode/1.0/" xmlns="">
  <Identification>
    <ShortName>{short_name}</ShortName>
    <Version>{version}</Version>
    <CanonicalUri>urn:test:{short_name}</CanonicalUri>
    <CanonicalVersionUri>urn:test:{short_name}{version}</CanonicalVersionUri>
  </Identification>
  <ColumnSet>
{column_xml}
  </ColumnSet>
  <SimpleCodeList>
{rows_xml}
  </SimpleCodeList>
</gc:CodeList>"""
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestParseGenericode:
    def test_parses_identification_columns_and_rows(self, tmp_path: Path) -> None:
        path = _write_gc(
            tmp_path,
            "Transport-profiles-v9.7.gc",
            short_name="Peppol Code Lists - Transport profiles",
            version="9.7",
            columns=["protocol", "profile-id", "state"],
            rows=[
                {"protocol": "AS4", "profile-id": "peppol-transport-as4-v2_0", "state": "active"},
                {"protocol": "AS2", "profile-id": "busdox-transport-as2-ver1p0", "state": "removed"},
            ],
        )
        cl = codelists.parse_genericode(path.read_bytes())
        assert cl.short_name == "Peppol Code Lists - Transport profiles"
        assert cl.version == "9.7"
        assert cl.canonical_uri == "urn:test:Peppol Code Lists - Transport profiles"
        assert cl.columns == ("protocol", "profile-id", "state")
        assert len(cl.rows) == 2
        assert cl.rows[0] == {
            "protocol": "AS4",
            "profile-id": "peppol-transport-as4-v2_0",
            "state": "active",
        }

    def test_raises_on_missing_identification(self) -> None:
        bad_xml = b"""<?xml version="1.0"?>
<gc:CodeList xmlns:gc="http://docs.oasis-open.org/codelist/ns/genericode/1.0/">
  <ColumnSet></ColumnSet>
</gc:CodeList>"""
        with pytest.raises(ValueError):
            codelists.parse_genericode(bad_xml)


class TestCodelistDirConfiguration:
    def test_raises_when_env_var_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_PEPPOL_CODELIST_DIR", raising=False)
        with pytest.raises(codelists.CodelistNotConfiguredError, match="EINVOICING_PEPPOL_CODELIST_DIR"):
            codelists.load_codelist("transport_profiles")

    def test_raises_when_dir_does_not_exist(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path / "nonexistent"))
        with pytest.raises(codelists.CodelistNotConfiguredError, match="is not a directory"):
            codelists.load_codelist("transport_profiles")

    def test_raises_when_specific_file_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path))
        with pytest.raises(codelists.CodelistNotConfiguredError, match="No file matching"):
            codelists.load_codelist("document_types")

    def test_loads_when_configured(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _write_gc(
            tmp_path,
            "Transport-profiles-v9.7.gc",
            short_name="Transport profiles",
            version="9.7",
            columns=["protocol", "state"],
            rows=[{"protocol": "AS4", "state": "active"}],
        )
        monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path))
        cl = codelists.load_codelist("transport_profiles")
        assert cl.version == "9.7"

    def test_picks_highest_version_when_multiple_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _write_gc(
            tmp_path, "Transport-profiles-v9.6.gc", short_name="old", version="9.6",
            columns=["state"], rows=[{"state": "active"}],
        )
        _write_gc(
            tmp_path, "Transport-profiles-v9.7.gc", short_name="new", version="9.7",
            columns=["state"], rows=[{"state": "active"}],
        )
        monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path))
        cl = codelists.load_codelist("transport_profiles")
        assert cl.version == "9.7"


@pytest.fixture
def configured_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    _write_gc(
        tmp_path, "Document-types-v9.7.gc", short_name="doctypes", version="9.7",
        columns=["scheme", "value", "state"],
        rows=[
            {"scheme": "busdox-docid-qns", "value": "urn:invoice", "state": "active"},
            {"scheme": "busdox-docid-qns", "value": "urn:old-invoice", "state": "removed"},
        ],
    )
    _write_gc(
        tmp_path, "Processes-v9.7.gc", short_name="processes", version="9.7",
        columns=["scheme", "value", "state"],
        rows=[{"scheme": "cenbii-procid-ubl", "value": "urn:proc1", "state": "active"}],
    )
    _write_gc(
        tmp_path, "Participant-identifier-schemes-v9.7.gc", short_name="schemes", version="9.7",
        columns=["schemeid", "iso6523", "state"],
        rows=[{"schemeid": "BE:EN", "iso6523": "0208", "state": "active"}],
    )
    _write_gc(
        tmp_path, "Transport-profiles-v9.7.gc", short_name="transport", version="9.7",
        columns=["protocol", "state"],
        rows=[{"protocol": "AS4", "state": "active"}],
    )
    _write_gc(
        tmp_path, "SPIS-Use-Case-v9.7.gc", short_name="spis", version="9.7",
        columns=["use-case-id", "state"],
        rows=[{"use-case-id": "MLS", "state": "active"}],
    )
    monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path))
    return tmp_path


class TestListFunctions:
    def test_list_document_type_ids_active_only_default(self, configured_dir: Path) -> None:
        rows = codelists.list_document_type_ids()
        assert len(rows) == 1
        assert rows[0]["value"] == "urn:invoice"

    def test_list_document_type_ids_all(self, configured_dir: Path) -> None:
        rows = codelists.list_document_type_ids(active_only=False)
        assert len(rows) == 2

    def test_list_process_ids(self, configured_dir: Path) -> None:
        rows = codelists.list_process_ids()
        assert rows == [{"scheme": "cenbii-procid-ubl", "value": "urn:proc1", "state": "active"}]

    def test_list_participant_id_schemes(self, configured_dir: Path) -> None:
        rows = codelists.list_participant_id_schemes()
        assert rows[0]["iso6523"] == "0208"

    def test_list_transport_profiles(self, configured_dir: Path) -> None:
        rows = codelists.list_transport_profiles()
        assert rows[0]["protocol"] == "AS4"

    def test_list_spis_use_case_ids(self, configured_dir: Path) -> None:
        rows = codelists.list_spis_use_case_ids()
        assert rows[0]["use-case-id"] == "MLS"


class TestCheckFunctions:
    def test_check_document_type_id_found_including_removed(self, configured_dir: Path) -> None:
        result = codelists.check_document_type_id_in_codelist("busdox-docid-qns", "urn:old-invoice")
        assert result["found"] is True
        assert result["state"] == "removed"

    def test_check_document_type_id_not_found(self, configured_dir: Path) -> None:
        result = codelists.check_document_type_id_in_codelist("bogus", "bogus")
        assert result == {"found": False, "scheme": "bogus", "value": "bogus"}

    def test_check_process_id(self, configured_dir: Path) -> None:
        assert codelists.check_process_id_in_codelist("cenbii-procid-ubl", "urn:proc1")["found"] is True
        assert codelists.check_process_id_in_codelist("x", "y")["found"] is False

    def test_check_participant_id_scheme_matches_iso6523_not_schemeid(self, configured_dir: Path) -> None:
        # Must match against the numeric ICD (iso6523), not the mnemonic (schemeid).
        found = codelists.check_participant_id_scheme_in_codelist("0208")
        assert found["found"] is True
        assert found["schemeid"] == "BE:EN"
        not_found = codelists.check_participant_id_scheme_in_codelist("BE:EN")
        assert not_found["found"] is False


class TestGetVersion:
    def test_reports_versions_when_fully_configured(self, configured_dir: Path) -> None:
        result = codelists.get_peppol_codelist_version()
        assert result["versions"] == {
            "document_types": "9.7",
            "participant_id_schemes": "9.7",
            "processes": "9.7",
            "transport_profiles": "9.7",
            "spis_use_case": "9.7",
        }
        assert result["errors"] == {}

    def test_reports_partial_errors_when_some_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _write_gc(
            tmp_path, "Transport-profiles-v9.7.gc", short_name="t", version="9.7",
            columns=["state"], rows=[{"state": "active"}],
        )
        monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path))
        result = codelists.get_peppol_codelist_version()
        assert result["versions"] == {"transport_profiles": "9.7"}
        assert set(result["errors"]) == {
            "document_types",
            "participant_id_schemes",
            "processes",
            "spis_use_case",
        }
