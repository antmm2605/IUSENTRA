"""Regression guards following the real ROM/8080 check of 05/09/2026."""
import pytest

from pct.mediazione_directory_repository import MediazioneDirectoryRepository
from pct.mediazione_official_offices import parse_office_page
from web.services.mediazione_directory_surface import enrich_locations, office_detail


def page(number="11", count=2, selected=1):
    rows = "".join(
        "<tr><td>" + legal + "</td><td>Via Roma 1</td><td>Bologna</td><td>40125</td>"
        "<td>BO</td><td>Emilia-Romagna</td><td>051123</td><td></td><td>a@example.test</td><td>p@example.test</td></tr>"
        for legal in ["Si", "No"]
    )
    return (f'<input type="hidden" name="hfRom" value="{number}">'
            f'<input type="hidden" name="tot2" value="{count}">'
            '<table id="gvAlboODM_Sedi"><tr>'
            + ''.join(f'<th>{x}</th>' for x in ["Sede Legale", "Indirizzo", "Comune", "CAP", "Prov.", "Regione"])
            + '</tr>' + rows + f'<tr><td><select name="pager"><option value="{selected}" selected>{selected}</option></select></td></tr></table>').encode()


def test_parser_preserves_colocated_offices_and_contact_roles():
    offices, total, pages, _, selector = parse_office_page(page(), "11")
    assert total == len(offices) == 2
    assert pages == 1 and selector == "pager"
    assert [o["legal"] for o in offices] == [True, False]
    assert offices[0]["email"] == "a@example.test"
    assert offices[0]["pec"] == "p@example.test"


def test_parser_rejects_wrong_organism_page_and_changed_columns():
    with pytest.raises(ValueError, match="organismo"):
        parse_office_page(page(number="12"), "11")
    with pytest.raises(ValueError, match="pagina"):
        parse_office_page(page(selected=2), "11", 1)
    with pytest.raises(ValueError, match="colonne"):
        parse_office_page(page().replace(b"Comune", b"Localita"), "11")


def seed(tmp_path):
    path = tmp_path / "mediazione_directory.db"
    repo = MediazioneDirectoryRepository(path)
    repo.import_registry([{"registry_kind": "organismo", "registration_number": "11", "name": "Organismo controllato", "is_active": True}],
                         source="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX", checked_at="2026-09-05T11:00:00+00:00")
    offices, total, pages, _, _ = parse_office_page(page(), "11")
    snapshot = dict(offices=offices, expected_count=total, pages=pages, source_url="https://mediazione.giustizia.it/ROM/AlboOdMDettaglioSedi.aspx?ROM=11",
                    checked_at="2026-09-05T11:00:00+00:00", content_sha256="a" * 64)
    return repo, path, snapshot


def test_sql_primary_rejects_incomplete_inventory_and_updates_atomically(tmp_path):
    repo, path, snapshot = seed(tmp_path)
    with pytest.raises(ValueError):
        repo.save_offices("11", {**snapshot, "expected_count": 3})
    assert not repo.office_snapshots()
    repo.save_offices("11", snapshot)
    config = {"MEDIAZIONE_DIRECTORY_DB": path}
    assert office_detail("11", config)["expected_count"] == 2
    rows = enrich_locations([{"registryNumber": "11", "registryKind": "organismo"}], config)
    assert rows[0]["officeCount"] == 2
    assert rows[0]["locations"] == [{"region": "Emilia-Romagna", "province": "BO", "city": "Bologna"}]
    repo.save_offices("11", {**snapshot, "expected_count": 1, "offices": snapshot["offices"][:1]})
    assert office_detail("11", config)["expected_count"] == 1


def test_missing_public_directory_is_explicit_and_never_creates_tenant_files(tmp_path):
    assert office_detail("11", {}) == {"ok": True, "available": False}
    path = tmp_path / "not-installed.db"
    assert not office_detail("11", {"MEDIAZIONE_DIRECTORY_DB": path})["available"]
    assert not path.exists()


def test_registry_page_never_loads_case_dashboard_news_or_ai():
    from types import SimpleNamespace
    from web.services.react_legal_intelligence_bridge import build_react_legal_intelligence_payload

    def forbidden(*args, **kwargs):
        raise AssertionError("Una directory pubblica non deve caricare fascicoli, notizie o AI.")

    manager = SimpleNamespace(mediazione_registry_snapshot=lambda **kw: {"rows": [], "total_rows": 0}, build_dashboard_snapshot=forbidden)
    payload = build_react_legal_intelligence_payload(
        get_legal_intelligence=lambda: manager, get_legal_update_pipeline=forbidden,
        get_fascicoli=forbidden, get_clienti=forbidden, get_agenda=forbidden,
        get_scadenziario=forbidden, page="mediazione", config={})
    assert payload["contracts"]["external_fetch"] is False
    assert payload["contracts"]["ai_generation"] is False
    assert len(payload["records"]) == 3
