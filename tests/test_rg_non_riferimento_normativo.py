"""Un riferimento normativo non è mai un numero di ruolo (difetto «RG 53/1994», 25/11/2026).

Nell'agenda dell'8080 la proposta «PEC con ordine di notifica: crea o collega il fascicolo della PEC»
compariva come «RG 53/1994»: l'estrattore dell'agenda aveva preso il numero della L. 53/1994 (notifiche
in proprio a mezzo PEC, art. 3-bis) dalla descrizione della proposta. Un R.G. valido richiede il proprio
contesto («R.G.», «RG n.», «ruolo generale», «N. … R.G.», il formato del portale).
Il promemoria a dieci giorni dalla ricezione cadeva di domenica (29/11/2026): non è un termine di legge,
quindi non si proroga in avanti (art. 155 c.p.c.) ma si anticipa all'ultimo giorno lavorativo.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from legal_ocr.formulario.riferimenti_normativi import atto_normativo_prima, e_numero_di_atto_normativo

TESTO_INVENTATO = (
    "Il provvedimento ordina al difensore di notificare il ricorso (L. 53/1994, art. 3-bis; "
    "legge n. 53 del 1994; l. 21 gennaio 1994, n. 53), con contributo unificato ai sensi del "
    "D.P.R. 115/2002 e secondo il rito novellato dal d.lgs. 149/2022. Crea o collega il fascicolo."
)
NORME = ("53/1994", "115/2002", "149/2022")


@pytest.mark.parametrize(
    ("testo", "numero"),
    [
        ("(L. 53/1994, art. 3-bis)", "53"),
        ("legge n. 53 del 1994", "53"),
        ("l. 21 gennaio 1994, n. 53", "53"),
        ("D.P.R. 115/2002", "115"),
        ("d.lgs. 149/2022", "149"),
        ("D.L. 179/2012", "179"),
        ("Reg. (UE) 2016/679", "2016"),
        ("d.m. 55/2014", "55"),
    ],
)
def test_sigla_di_atto_normativo_prima_del_numero(testo: str, numero: str) -> None:
    inizio = testo.index(numero)
    assert atto_normativo_prima(testo, inizio)
    assert e_numero_di_atto_normativo(testo, inizio, inizio + len(numero))


@pytest.mark.parametrize(
    "testo",
    ["R.G.L. 940/2023", "r.g.l. 656 /2025", "RG n. 656/2025", "N. 523/2026 R.G.", "udienza del 10/11/2026",
     "ruolo generale n. 77/2026", "crea o collega il fascicolo 860/2026"],
)
def test_i_veri_ruoli_restano(testo: str) -> None:
    inizio = next(i for i, c in enumerate(testo) if c.isdigit())
    assert atto_normativo_prima(testo, inizio) == ""


def test_agenda_non_legge_la_legge_53_1994_come_rg() -> None:
    from web.services.react_agenda_bridge import _extract_rg

    titolo = "PEC con ordine di notifica: crea o collega il fascicolo della PEC"
    assert _extract_rg(titolo, TESTO_INVENTATO) == ""
    # Un ruolo nudo vero accanto alla norma si legge ancora.
    assert _extract_rg(titolo, f"{TESTO_INVENTATO} Comunicazione 860/2026") == "RG 860/2026"


def test_scadenziario_non_legge_le_norme_come_rg() -> None:
    from web.services.react_scadenziario_bridge import _pec_rg_label

    assert _pec_rg_label(TESTO_INVENTATO) == ""
    assert _pec_rg_label("Notificazione ai sensi del D.L. 179/2012") == ""
    assert _pec_rg_label("Notificazione ai sensi del D.L. 179/2012 - proc. 860/2026") == "RG 860/2026"


def test_estrattori_di_ruolo_scartano_le_norme() -> None:
    from pct.agenda_del_fascicolo import _ruolo
    from pct.archivio_letture.estrazione_ruolo import estrai_ruoli
    from pct.controllo_studio.fonti import fascicolo_da_testo
    from pct.note_127_ter.udienza_riferita import normalizza_rg
    from pct.pec_change_receipt import normalize_rg
    from pct.pec_legal_workflow import estrai_registri
    from pct.pec_pipeline import extract_rg_candidates
    from pct.presidio_notifica_senza_fascicolo import numero_ruolo

    for estratto in (_ruolo(TESTO_INVENTATO), normalizza_rg(TESTO_INVENTATO), normalize_rg(TESTO_INVENTATO),
                     numero_ruolo({}, TESTO_INVENTATO)):
        assert estratto == ""
    assert fascicolo_da_testo(TESTO_INVENTATO, {norma: object() for norma in NORME}) is None
    assert estrai_ruoli(TESTO_INVENTATO, origine="nativo") == []
    assert estrai_ruoli("legge n. 53/1994 R.G.", origine="nativo") == []
    assert [f.valore for f in estrai_ruoli("R.G.L. 940/2023", origine="nativo")] == ["940/2023"]
    assert estrai_registri("L. 53/1994/CC e D.P.R. 115/2002 GDP") == []
    assert [r["numero"] for r in estrai_registri("RG 1234/2025 GDP")] == ["1234"]
    assert extract_rg_candidates(TESTO_INVENTATO) == []
    # Con il contesto del ruolo il numero si legge, anche nella stessa frase di una norma.
    assert numero_ruolo({}, "L. 53/1994 - Comunicazione 860/2026") == "860/2026"


def test_preparazione_udienza_non_associa_per_numero_di_legge() -> None:
    from web.services.preparazione_udienza_associazione import fascicolo_udienza

    appuntamento = SimpleNamespace(id="A1", procedimento="", titolo="Notifica ex L. 53/1994", id_fascicolo="",
                                   id_cliente="", cliente="", tribunale="", data_ora="2026-11-27T09:00:00")
    fascicolo = SimpleNamespace(id="F1", numero="2026/1", numero_rg="53", anno_rg="1994", rg_completo="53/1994",
                                nome_cliente="", id_cliente="", tribunale="", attivita=(), data_prossima_udienza="")
    # Senza ruolo vero occorrono cliente e ufficio: il numero della legge non basta ad associare.
    assert fascicolo_udienza(appuntamento, [fascicolo]) is None


def test_promemoria_di_domenica_si_anticipa_all_ultimo_giorno_lavorativo() -> None:
    from pct.presidio_notifica_senza_fascicolo import campi_proposta, data_promemoria

    # 19/11/2026 + 10 = domenica 29/11/2026 → venerdì 27/11/2026 (il sabato non è lavorativo).
    assert data_promemoria(date(2026, 11, 19), oggi=date(2026, 11, 19)) == date(2026, 11, 27)
    # Mai prima di oggi.
    assert data_promemoria(date(2026, 11, 19), oggi=date(2026, 11, 28)) == date(2026, 11, 28)
    # 15/12 + 10 = venerdì 25/12 (Natale) → giovedì 24/12.
    assert data_promemoria(date(2026, 12, 15), oggi=date(2026, 12, 15)) == date(2026, 12, 24)
    candidato = {"rule_id": "notif.detect.explicit_order.v1", "text_excerpt": "Manda al ricorrente di notificare"}
    campi = campi_proposta(message_id="pec_x", understanding={}, candidate=candidato,
                           received_at="2026-11-19T07:55:05Z", oggi=date(2026, 11, 19))
    assert campi["data_scadenza"] == "2026-11-27"
    assert campi["titolo"].endswith("il fascicolo della PEC")


def test_riconvalida_delle_proposte_gia_scritte(tmp_path) -> None:
    from pct.presidio_notifica_senza_fascicolo import PROFILO, campi_proposta, riconvalida_proposte
    from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine

    manager = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    candidato = {"rule_id": "notif.detect.explicit_order.v1", "text_excerpt": "Manda al ricorrente di notificare"}
    campi = campi_proposta(message_id="pec_a", understanding={}, candidate=candidato,
                           received_at="2026-11-19T07:55:05Z", oggi=date(2026, 11, 19))

    def nuova(titolo: str, data: str, stato: StatoTermine = StatoTermine.BOZZA):
        dati = dict(campi)
        dati.pop("titolo"), dati.pop("data_scadenza")
        return manager.nuova(titolo=titolo, tipo=TipoTermine.ADEMPIMENTO, data_scadenza=data,
                             id_fascicolo=dati.pop("id_fascicolo"), descrizione=dati.pop("descrizione"),
                             note=dati.pop("note"), stato=stato, **dati)

    falsa = nuova("PEC con ordine di notifica: crea o collega il fascicolo RG 53/1994", "2026-11-29")
    vera = nuova("PEC con ordine di notifica: crea o collega il fascicolo RG 860/2026 Tribunale di Vicenza", "2026-11-27")
    decisa = nuova("PEC con ordine di notifica: crea o collega il fascicolo RG 53/1994", "2026-11-29", StatoTermine.APERTO)
    esito = riconvalida_proposte(manager, oggi=date(2026, 11, 25))
    assert esito["rg_normativi"] == 1 and esito["date_anticipate"] == 1 and esito["errori"] == 0
    rettificata = manager.get(falsa.id)
    assert rettificata.titolo == "PEC con ordine di notifica: crea o collega il fascicolo della PEC"
    assert rettificata.data_scadenza[:10] == "2026-11-27"
    assert rettificata.stato == StatoTermine.BOZZA and rettificata.deadline_profile_code == PROFILO
    assert "Riconvalida automatica" in rettificata.note and "L. 53/1994" in rettificata.note
    assert manager.get(vera.id).titolo.endswith("RG 860/2026 Tribunale di Vicenza")
    assert manager.get(decisa.id).titolo.endswith("RG 53/1994")  # decisione dell'avvocato: non si tocca
    assert riconvalida_proposte(manager, oggi=date(2026, 11, 25))["ids"] == []  # idempotente


def test_riconvalida_dei_fatti_di_ruolo_che_sono_norme(tmp_path) -> None:
    from pct.registro_letture import Fatto, Oggetto, RegistroLetture

    registro = RegistroLetture(tmp_path / "registro.db")
    try:
        oggetto = Oggetto(tipo="documento", oggetto_id="D1", sha256="a" * 64)
        registro.registra_inventario("t", "F1", [oggetto])
        registro.registra_fatti("t", "F1", oggetto, "documenti", [
            Fatto(categoria="ruolo", campo="numero_ruolo", valore="53/1994", valore_letto="n. 53/1994 R.G.",
                  contesto="notifica ai sensi della legge n. 53/1994 R.G. del difensore", verifica="plausibile"),
            Fatto(categoria="ruolo", campo="numero_ruolo", valore="940/2023", valore_letto="R.G.L. 940/2023",
                  contesto="Tribunale di Ivrea R.G.L. 940/2023", verifica="verificata"),
        ], versione="storica")
        respinti = registro.riconvalida_fatti("t", "F1")
        assert [f.valore for f in respinti] == ["53/1994"]
        assert any("atto normativo" in p.get("dettaglio", "") for p in respinti[0].prove)
        rimasti = {f.valore: f.verifica for f in registro.fatti("t", "F1", verifiche=None)}
        assert rimasti == {"53/1994": "respinta", "940/2023": "verificata"}
    finally:
        registro.close()
