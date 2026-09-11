"""Voci della Ricerca Studio che descrivono lo stesso messaggio.

Una PEC puo' essere letta sia dal registro delle comunicazioni sia dalla
casella: finche' ogni sorgente produceva una voce propria, l'avvocato vedeva
lo stesso messaggio due volte, con due link diversi e nessun modo di capire
quale aprire.
"""

from __future__ import annotations

from pct.global_search.indexer import consolida_documenti
from pct.global_search.models import GlobalSearchDocument


def _voce(
    *,
    modulo: str,
    url: str,
    message_id: str,
    corpo: str = "",
    badges: list[str] | None = None,
    entity_type: str = "pec",
) -> GlobalSearchDocument:
    return GlobalSearchDocument(
        tenant_id="default",
        entity_type=entity_type,
        entity_id=f"{modulo}-{abs(hash(url)) % 10_000}",
        title="Notifica ai sensi del D.L. 179/2012",
        body=corpo,
        keywords=f"{modulo} pec",
        metadata={"message_id": message_id, "badges": list(badges or ["PEC"])},
        source_module=modulo,
        source_url=url,
    )


def test_la_stessa_pec_letta_da_due_sorgenti_diventa_una_voce_sola():
    registro = _voce(
        modulo="comunicazioni",
        url="/messaggi?focus=M1",
        message_id="<abc@pec.example.it>",
        corpo="riga di registro",
        badges=["PEC", "Comunicazione"],
    )
    casella = _voce(
        modulo="email",
        url="/email/messaggio/E9",
        #  Stesso messaggio, scritto con maiuscole e parentesi diverse.
        message_id="ABC@pec.example.it",
        corpo="corpo completo del messaggio ricevuto in casella",
        badges=["PEC", "INBOX"],
    )

    risultato = consolida_documenti([registro, casella])

    assert len(risultato) == 1
    unica = risultato[0]
    #  Il link porta al messaggio vero, non alla riga di registro: e' quello
    #  che l'avvocato vuole aprire.
    assert unica.source_url == "/email/messaggio/E9"
    #  Nulla va perso: l'altra posizione resta raggiungibile.
    assert unica.metadata["altre_posizioni"] == [
        {"url": "/messaggi?focus=M1", "modulo": "comunicazioni"}
    ]
    assert unica.metadata["sorgenti"] == ["comunicazioni", "email"]
    assert unica.metadata["badges"] == ["PEC", "INBOX", "Comunicazione"]
    #  Resta il corpo piu' ricco e la voce e' trovabile con i termini di
    #  entrambe le sorgenti.
    assert "corpo completo" in unica.body
    assert "comunicazioni" in unica.keywords and "email" in unica.keywords


def test_messaggi_diversi_non_vengono_accorpati():
    prima = _voce(modulo="email", url="/email/messaggio/E1", message_id="<uno@pec.it>")
    seconda = _voce(modulo="email", url="/email/messaggio/E2", message_id="<due@pec.it>")

    assert len(consolida_documenti([prima, seconda])) == 2


def test_senza_message_id_non_si_accorpa_nulla():
    """Senza identita' condivisa accorpare sarebbe un azzardo."""

    prima = _voce(modulo="comunicazioni", url="/messaggi?focus=A", message_id="")
    seconda = _voce(modulo="email", url="/email/messaggio/B", message_id="")

    assert len(consolida_documenti([prima, seconda])) == 2


def test_le_voci_che_non_sono_messaggi_restano_intatte():
    fascicolo = _voce(
        modulo="fascicoli",
        url="/fascicoli/F1",
        message_id="",
        entity_type="fascicolo",
    )
    documento = _voce(
        modulo="documenti",
        url="/fascicoli/F1/documenti/D1",
        message_id="",
        entity_type="documento",
    )

    risultato = consolida_documenti([fascicolo, documento])

    assert [voce.entity_type for voce in risultato] == ["fascicolo", "documento"]


def test_tenant_diversi_non_si_mescolano():
    """Due studi possono ricevere la stessa PEC: restano separate."""

    uno = _voce(modulo="email", url="/email/messaggio/E1", message_id="<x@pec.it>")
    due = _voce(modulo="email", url="/email/messaggio/E1", message_id="<x@pec.it>")
    due.tenant_id = "altro-studio"

    assert len(consolida_documenti([uno, due])) == 2


#  ---------------------------------------------------------------------------
#  Contesto unico delle sorgenti
#  ---------------------------------------------------------------------------


def test_top_bar_e_pagina_ricerca_dichiarano_le_stesse_sorgenti():
    """Un elenco piu' corto nella top bar cancellava sorgenti dall'indice.

    Quando l'indice risulta vuoto la top bar lo ricostruisce con il proprio
    contesto: se li' mancano messaggi, PEC ed email ordinaria — com'era —
    quelle voci spariscono dall'indice per tutti, e cercare una PEC non da'
    piu' risultati nemmeno dalla pagina Ricerca.
    """

    import re
    from pathlib import Path

    from web.services.global_search_context import SORGENTI_RICERCA

    radice = Path(__file__).resolve().parents[1]
    superfici = {
        "pagina Ricerca": radice / "web" / "blueprints" / "global_search.py",
        "top bar": radice / "web" / "services" / "topbar_operational.py",
    }

    for nome, percorso in superfici.items():
        sorgente = percorso.read_text(encoding="utf-8")
        inizio = sorgente.index("costruisci_contesto_ricerca(")
        blocco = sorgente[inizio : inizio + 1600]
        dichiarate = set(re.findall(r'"(\w+)":\s*get_', blocco))
        mancanti = [voce for voce in SORGENTI_RICERCA if voce not in dichiarate]
        assert not mancanti, f"{nome}: sorgenti non passate al contesto: {mancanti}"


def test_il_contesto_espone_le_comunicazioni_come_i_messaggi():
    """Gli adapter leggono le comunicazioni sotto un nome diverso."""

    from web.services.global_search_context import costruisci_contesto_ricerca

    sentinella = object()
    contesto = costruisci_contesto_ricerca(
        tenant_id="default",
        search_index_path="",
        factories={"messaggi": lambda: sentinella},
    )

    assert contesto["messaggi"] is sentinella
    assert contesto["comunicazioni"] is sentinella


def test_una_sorgente_non_disponibile_non_ferma_la_ricerca():
    """Meglio un indice parziale, segnalato, che nessun risultato."""

    from web.services.global_search_context import costruisci_contesto_ricerca

    segnalati: list[str] = []

    def esplode():
        raise RuntimeError("modulo non configurato")

    contesto = costruisci_contesto_ricerca(
        tenant_id="default",
        search_index_path="",
        factories={"fascicoli": lambda: "gestore", "email_pec": esplode},
        on_error=lambda nome, exc: segnalati.append(nome),
    )

    assert contesto["fascicoli"] == "gestore"
    assert contesto["email_pec"] is None
    assert segnalati == ["email_pec"]
