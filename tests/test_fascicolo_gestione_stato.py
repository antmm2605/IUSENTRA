"""Pannello Gestione: un fascicolo definito con archivio pronto non appare «Aperto»."""

from pathlib import Path

PAGINA = Path(__file__).resolve().parents[1] / "frontend" / "src" / "components" / "FascicoliPage.tsx"


def test_select_di_gestione_mappa_da_archiviare_su_definito():
    sorgente = PAGINA.read_text(encoding="utf-8")
    assert "defaultValue={statoSelezionabile(f.status)}" in sorgente
    assert "valore === 'DA_ARCHIVIARE' ? 'DEFINITO' : valore" in sorgente
    assert "defaultValue={f.status.toUpperCase()}" not in sorgente


def test_gli_stati_del_bridge_contengono_definito():
    from pct.fascicoli import StatoFascicolo

    assert "DEFINITO" in {item.value for item in StatoFascicolo}
    assert "DA_ARCHIVIARE" not in {item.value for item in StatoFascicolo}


def _schede(tipo):
    from types import SimpleNamespace

    from web.services.react_fascicoli_bridge import _telematic

    return [item["label"] for item in _telematic(SimpleNamespace(id="F1", tipo=tipo))]


def test_servizi_telematici_solo_quelli_della_materia():
    assert _schede("CIVILE") == ["Deposito telematico", "PolisWeb / PST", "Checklist deposito"]
    assert _schede("PENALE") == ["Deposito telematico", "PDP Penale"]
    assert "PolisWeb / PST" not in _schede("AMMINISTRATIVO")
    assert "PDP Penale" not in _schede("TRIBUTARIO")


def test_udienza_trascorsa_e_ultima_non_prossima():
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from web.services.react_fascicoli_bridge import _hearing_row, _next_hearing_value

    oggi = datetime.now(ZoneInfo("Europe/Rome")).date()
    passata = (oggi - timedelta(days=200)).isoformat()
    futura = (oggi + timedelta(days=20)).isoformat()
    vecchio = SimpleNamespace(data_prossima_udienza=passata, attivita=[])
    assert _hearing_row(vecchio)[0] == "Ultima udienza"
    agenda = [SimpleNamespace(titolo="Udienza", tipo="UDIENZA", data_ora=f"{futura}T09:00:00", data="")]
    assert _next_hearing_value(vecchio, agenda) == futura
    assert _hearing_row(vecchio, agenda)[0] == "Prossima udienza"
    # dato naive e aware mescolati nell'agenda
    misto = [SimpleNamespace(titolo="Udienza", tipo="", data_ora=f"{futura}T09:00:00+01:00", data="")]
    assert _next_hearing_value(SimpleNamespace(data_prossima_udienza="", attivita=[]), misto) == futura


def test_avanzamento_senza_doppioni_codici_e_passaggi_fittizi():
    from types import SimpleNamespace

    from web.services.react_fascicoli_bridge import _history

    voce = dict(data="2026-07-09", descrizione="Riconciliazione automatica documenti duplicati", note="Assorbiti 7 record")
    fascicolo = SimpleNamespace(avanzamento=[
        SimpleNamespace(data="2026-07-08", descrizione="Sentenza indicizzata", stato_precedente="IN_CORSO", stato_nuovo="DEFINITO",
                        note="Sentenza n. 313/2025; RG n. 1306/2024; Documento: docai-130dfaa379b247f8a46a323667cec4e5", avvocato=""),
        SimpleNamespace(stato_precedente="DEFINITO", stato_nuovo="DEFINITO", avvocato="", **voce),
        SimpleNamespace(stato_precedente="DEFINITO", stato_nuovo="DEFINITO", avvocato="", **voce),
    ])
    storia = _history(fascicolo)
    assert len(storia) == 2
    assert (storia[0]["from"], storia[0]["to"]) == ("In corso", "Definito")
    assert "docai" not in storia[0]["notes"] and storia[0]["notes"].endswith("1306/2024")
    assert (storia[1]["from"], storia[1]["to"]) == ("", "")


def test_pannelli_documenti_comunicazioni_soggetti_audit_leggibili():
    sorgente = PAGINA.read_text(encoding="utf-8")
    # Documenti: prima l'elenco, poi gli strumenti di caricamento su richiesta
    assert sorgente.index("<CatalogazioneDocumentalePanel") < sorgente.index('className="iu-fas-aggiungi-documenti"')
    # Comunicazioni: una ricevuta per impronta, documenti monitorati richiudibili
    assert "unaVoltaPerContenuto(data.documents.filter(isNotificationCommunicationDocument))" in sorgente
    assert 'className="iu-fas-relata-list iu-fas-relata-monitorati"' in sorgente
    # Soggetti: le parti lette dal portale non spariscono quando non sono ancora registrate
    assert "<PartiLetteDalPortale nomi={partiLetteDaRegistrare(f.sourceSnapshot, data.parties)}/>" in sorgente
    # Nessun gergo tecnico in vista
    assert "catalogo SQL" not in sorgente and "Il bundle si abilita" not in sorgente
