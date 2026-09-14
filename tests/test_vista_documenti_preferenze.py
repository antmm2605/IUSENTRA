"""Vista preferita dell'elenco documenti del fascicolo.

La preferenza decide come si apre ogni fascicolo: se un valore corrotto o fuori
catalogo passasse, l'avvocato aprirebbe i fascicoli su una vista vuota senza
capire perche'. Qui si verifica che ogni valore non riconosciuto torni al
predefinito invece di essere salvato.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from web.services import vista_documenti_preferenze as vista


@pytest.fixture()
def ancora(tmp_path):
    percorso = tmp_path / "fascicoli" / "fascicoli.json"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text("{}", encoding="utf-8")
    return percorso


def test_senza_preferenza_si_usa_la_vista_predefinita(ancora):
    esito = vista.carica(ancora)
    assert esito["configured"] is False
    assert esito["preferences"] == {"sort": "data_documento_desc", "section": "tutte", "status": "tutti"}


def test_la_vista_salvata_si_rilegge_uguale(ancora):
    scelta = {"sort": "nome_asc", "section": "atti", "status": "da_firmare"}
    salvato = vista.salva(ancora, scelta)
    assert salvato["ok"] is True and salvato["configured"] is True
    riletto = vista.carica(ancora)
    assert riletto["configured"] is True
    assert riletto["preferences"] == scelta
    assert riletto["updatedAt"] == salvato["updatedAt"]


@pytest.mark.parametrize(
    ("payload", "atteso"),
    [
        ({"sort": "inesistente"}, "data_documento_desc"),
        ({"sort": ""}, "data_documento_desc"),
        ({"sort": "caricamento_asc"}, "caricamento_asc"),
    ],
)
def test_un_ordinamento_fuori_catalogo_torna_al_predefinito(payload, atteso):
    assert vista.normalizza(payload)["sort"] == atteso


@pytest.mark.parametrize(
    ("sezione", "atteso"),
    [("da-verificare", "da-verificare"), ("sezione_che_non_esiste", "tutte"), (None, "tutte")],
)
def test_una_sezione_fuori_catalogo_torna_a_tutte(sezione, atteso):
    assert vista.normalizza({"section": sezione})["section"] == atteso


def test_uno_stato_fuori_catalogo_torna_a_tutti():
    assert vista.normalizza({"status": "archiviato"})["status"] == "tutti"
    assert vista.normalizza({"status": "da_verificare"})["status"] == "da_verificare"


def test_le_preferenze_si_leggono_anche_annidate():
    """Il POST rimanda l'intero payload salvato: va accettato com'e'."""
    annidato = {"preferences": {"sort": "nome_asc", "section": "allegati", "status": "tutti"}, "updatedAt": "x"}
    assert vista.normalizza(annidato)["section"] == "allegati"


def test_ripristinare_la_vista_cancella_la_preferenza(ancora):
    vista.salva(ancora, {"sort": "nome_asc", "section": "atti", "status": "da_firmare"})
    esito = vista.dimentica(ancora)
    assert esito["configured"] is False
    assert esito["preferences"] == vista.preferenze_predefinite()
    assert vista.carica(ancora)["configured"] is False


def test_una_preferenza_corrotta_non_blocca_l_apertura(ancora):
    """Un JSON illeggibile deve dare i predefiniti, non un errore in pagina."""
    vista.salva(ancora, {"sort": "nome_asc"})
    percorso = ancora.parent / "ui_preferences.db"
    with sqlite3.connect(str(percorso)) as conn:
        conn.execute("UPDATE ui_preferences SET dati_json = ? WHERE scope = ?", ("{non-json", vista.SEZIONE))
    esito = vista.carica(ancora)
    assert esito["preferences"] == vista.preferenze_predefinite()


def test_la_vista_convive_con_le_preferenze_dei_filtri_fascicoli(ancora):
    """Le due viste usano lo stesso archivio ma righe diverse: non si sovrascrivono."""
    percorso = ancora.parent / "ui_preferences.db"
    vista.salva(ancora, {"sort": "nome_asc", "section": "atti", "status": "tutti"})
    with sqlite3.connect(str(percorso)) as conn:
        conn.execute(
            "INSERT INTO ui_preferences (scope, updated_at, source, dati_json) VALUES (?,?,?,?)",
            ("fascicoli_filtri", "2026-01-01T00:00:00Z", "react_fascicoli", json.dumps({"preferences": {"sort": "rg"}})),
        )
    assert vista.carica(ancora)["preferences"]["sort"] == "nome_asc"
    with sqlite3.connect(str(percorso)) as conn:
        righe = conn.execute("SELECT scope FROM ui_preferences ORDER BY scope").fetchall()
    assert [r[0] for r in righe] == ["fascicoli_filtri", vista.SEZIONE]


def test_il_contratto_react_espone_il_salvataggio_della_vista():
    """Il pulsante e il percorso di salvataggio devono restare in pagina."""
    from pathlib import Path

    radice = Path(__file__).resolve().parents[1] / "frontend" / "src"
    toolbar = (radice / "components/fascicoloDocumenti/DocumentListToolbar.tsx").read_text(encoding="utf-8")
    hook = (radice / "components/fascicoloDocumenti/useDocumentListControls.ts").read_text(encoding="utf-8")
    servizio = (radice / "services/vistaDocumentiPreferenze.ts").read_text(encoding="utf-8")
    assert "Salva impostazioni" in toolbar
    assert "Ripristina predefinita" in toolbar
    assert "salvaVista" in hook and "ripristinaVista" in hook
    assert "/api/v1/ui/fascicoli/preferenze-vista-documenti" in servizio
    # La ricerca non entra nella vista: e' una domanda del momento.
    assert "{ sort, section, status }" in hook
    assert "style={{" not in toolbar
