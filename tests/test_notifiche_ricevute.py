"""Notifiche ricevute dalla controparte: atto, perfezionamento per il destinatario e termini (31/10/2026)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from pct.notifiche_ricevute import (
    atto_notificato,
    direzione_notifica,
    oggetto_di_notifica_l53,
    perfezionamento_destinatario,
    termini_da_notifica_ricevuta,
)

CONSEGNA = datetime(2026, 7, 10, 10, 0)


def test_oggetto_della_notifica_in_proprio():
    assert oggetto_di_notifica_l53("Notificazione ai sensi della legge n. 53 del 1994 - Rossi c. Bianchi")
    assert not oggetto_di_notifica_l53("Trasmissione documenti")


@pytest.mark.parametrize(
    ("casella", "mittente", "cartella", "attesa"),
    [
        ("studio@pec.it", "Avv. Rossi <rossi@pec.it>", "INBOX", "ricevuta"),
        ("studio@pec.it", "STUDIO@pec.it", "INBOX", "inviata"),
        ("studio@pec.it", "altro@pec.it", "Posta inviata", "inviata"),
        ("", "rossi@pec.it", "INBOX", ""),
    ],
)
def test_direzione_della_notifica(casella, mittente, cartella, attesa):
    assert direzione_notifica(casella=casella, mittente=mittente, cartella=cartella) == attesa


@pytest.mark.parametrize(
    ("consegna", "attesa"),
    [
        (datetime(2026, 7, 31, 22, 10), date(2026, 8, 1)),  # dopo le 21: il giorno dopo alle 7
        (datetime(2026, 7, 31, 6, 30), date(2026, 7, 31)),  # prima delle 7: stesso giorno alle 7
        (datetime(2026, 7, 31, 20, 59), date(2026, 7, 31)),
        (datetime(2026, 7, 31, 19, 30, tzinfo=timezone.utc), date(2026, 7, 31)),  # 21:30 a Roma
    ],
)
def test_perfezionamento_per_il_destinatario_art_147(consegna, attesa):
    if consegna.tzinfo is not None:
        attesa = date(2026, 8, 1)
    assert perfezionamento_destinatario(consegna) == attesa


@pytest.mark.parametrize(
    ("testo", "allegati", "codici"),
    [
        ("In forza del decreto ingiuntivo n. 123/2026", [], ["opposizione_decreto_ingiuntivo"]),
        ("ATTO DI PRECETTO", [], ["termine_adempimento_precetto", "opposizione_atti_esecutivi_precetto"]),
        ("RICORSO PER CASSAZIONE", [], ["controricorso"]),
        ("", ["Sentenza_Tribunale_Bari.pdf"], ["appello_breve"]),
        ("", ["Sentenza_Corte_d_Appello.pdf"], ["ricorso_cassazione_breve"]),
        ("ATTO DI APPELLO avverso la sentenza n. 45/2026; udienza del 15/12/2026", [], ["costituzione_appellato"]),
        ("ATTO DI CITAZIONE: cita a comparire all'udienza del 10/12/2026", [], ["costituzione_convenuto"]),
    ],
)
def test_ogni_atto_notificato_apre_il_suo_termine(testo, allegati, codici):
    proposte = termini_da_notifica_ricevuta(testo, consegna=CONSEGNA, nomi_allegati=allegati)
    assert [p["codice_termine"] for p in proposte] == codici
    assert all(p["create_in_scadenziario"] and p["human_review_required"] and p["peremptory"] for p in proposte)


def test_il_termine_decorre_dal_perfezionamento_e_quello_a_ritroso_dall_udienza():
    decreto = termini_da_notifica_ricevuta("decreto ingiuntivo", consegna=datetime(2026, 7, 31, 22, 10))[0]
    assert decreto["dies_a_quo_date"] == "2026-08-01" and decreto["duration_value"] == 40
    citazione = termini_da_notifica_ricevuta("atto di citazione, udienza del 10/12/2026", consegna=CONSEGNA)[0]
    assert citazione["dies_a_quo_date"] == "2026-12-10" and citazione["direction"] == "backward"


def test_senza_udienza_o_con_data_impossibile_il_termine_a_ritroso_non_si_propone():
    assert termini_da_notifica_ricevuta("atto di citazione", consegna=CONSEGNA) == []
    assert termini_da_notifica_ricevuta("atto di citazione, udienza del 31/02/2027", consegna=CONSEGNA) == []


def test_un_atto_non_riconosciuto_non_apre_termini():
    assert atto_notificato("Trasmissione documenti") is None
    assert termini_da_notifica_ricevuta("Trasmissione documenti", consegna=CONSEGNA) == []


# ── Dalla PEC letta allo scadenziario ──────────────────────────────────────


def _pec(testo: str, *, mittente: str = "Avv. Rossi <rossi@pec.avvocati.it>", casella: str = "studio@pec.it",
         oggetto: str = "Notificazione ai sensi della legge n. 53 del 1994", data: str = "Fri, 31 Jul 2026 22:10:05 +0200"):
    from email.message import EmailMessage

    from pct.pec_pipeline import parse_pec_message

    messaggio = EmailMessage()
    messaggio["From"], messaggio["To"], messaggio["Subject"], messaggio["Date"] = mittente, casella, oggetto, data
    messaggio.set_content(testo)
    parsed = parse_pec_message(messaggio.as_bytes())
    parsed["casella"] = {"account_email": casella, "folder": "INBOX"}
    return parsed


def test_il_decreto_ingiuntivo_notificato_apre_i_40_giorni_dal_perfezionamento():
    from pct.pec_pipeline import build_validation_report

    report = build_validation_report(_pec("Si notifica il decreto ingiuntivo n. 123/2026 del Tribunale di Bari."), [])
    proposta = report["deadline_proposal"]["legal_deadline_proposal"]
    # Consegna il 31/07 alle 22:10 → perfezionata il 01/08; agosto sospeso; 40° giorno sabato 10/10 → lunedì 12/10.
    assert proposta["ok"] is True and proposta["norma"] == "art. 641 c.p.c."
    assert proposta["dies_a_quo_date"] == "2026-08-01" and proposta["deadline"] == "2026-10-12"


def test_la_stessa_pec_inviata_dallo_studio_resta_una_notifica_in_uscita():
    from pct.notifiche_ricevute_pec import proposta_notifica_ricevuta

    parsed = _pec("Si notifica il decreto ingiuntivo n. 123/2026.", mittente="studio@pec.it")
    assert proposta_notifica_ricevuta(parsed, consegna_iso="2026-07-31T20:10:05Z") is None


def test_notifica_ricevuta_con_atto_non_riconosciuto_o_senza_data_resta_da_verificare():
    from pct.notifiche_ricevute_pec import proposta_notifica_ricevuta

    assert proposta_notifica_ricevuta(_pec("Si notifica l'atto allegato."), consegna_iso="2026-07-31T20:10:05Z")["ok"] is False
    assert proposta_notifica_ricevuta(_pec("decreto ingiuntivo"), consegna_iso="")["ok"] is False
    assert proposta_notifica_ricevuta(_pec("decreto ingiuntivo", oggetto="Trasmissione atti"), consegna_iso="x") is None


def test_in_materia_di_lavoro_niente_sospensione_feriale_e_il_precetto_porta_anche_il_secondo_termine():
    from pct.notifiche_ricevute_pec import proposta_notifica_ricevuta

    lavoro = proposta_notifica_ricevuta(
        _pec("Sezione Lavoro - si notifica la sentenza del Tribunale di Bari in materia di lavoro."),
        consegna_iso="2026-07-10T08:00:00Z",
    )
    assert lavoro["deadline"] == "2026-08-10"  # 30 giorni senza agosto sospeso: domenica 09/08 → lunedì 10/08
    precetto = proposta_notifica_ricevuta(_pec("ATTO DI PRECETTO"), consegna_iso="2026-03-02T08:00:00Z")
    assert [t["codice_termine"] for t in precetto["altri_termini"]] == ["opposizione_atti_esecutivi_precetto"]


def test_la_notifica_ricevuta_non_resta_in_attesa_di_ricevute_di_consegna():
    from pct.pec_legal_event_understanding import build_legal_event_understanding

    capito = build_legal_event_understanding(
        _pec("Si notifica il decreto ingiuntivo n. 123/2026."), {}, dies_a_quo_date="2026-07-31T20:10:05Z",
    )
    assert not any(item.get("creates_notification_candidate") for item in capito["notifications"])
    assert any(item.get("codice_termine") == "opposizione_decreto_ingiuntivo" for item in capito["deadlines"])


def test_la_torre_di_controllo_distingue_la_notifica_ricevuta_da_quella_da_preparare():
    from pct.pec_control_tower import classify_legal

    base = {"subject": "Notificazione ai sensi della legge n. 53 del 1994", "search_text": "decreto ingiuntivo"}
    ricevuta = classify_legal({**base, "sender": "rossi@pec.avvocati.it",
                               "casella": {"account_email": "studio@pec.it", "folder": "INBOX"}}, {})
    assert ricevuta["legal_category"] == "NOTIFICA_RICEVUTA"
    inviata = classify_legal({**base, "sender": "studio@pec.it",
                              "casella": {"account_email": "studio@pec.it", "folder": "INBOX"}}, {})
    assert inviata["legal_category"] == "NOTIFICA_CONTROPARTE"


def test_indirizzo_del_mittente_lineare_anche_su_intestazioni_costruite_ad_arte():
    """CodeQL py/polynomial-redos: la ricerca dell'indirizzo non deve degenerare su testi lunghi."""
    import time

    from pct.notifiche_ricevute import _indirizzo, direzione_notifica

    assert _indirizzo("Avv. Rossi <Mario.Rossi+pec@PEC.Avvocati.IT>") == "mario.rossi+pec@pec.avvocati.it"
    assert _indirizzo("x@@y") == "x@@y" and _indirizzo("@x") == "@x"
    assert direzione_notifica(casella="studio@pec.it", mittente="Studio <STUDIO@pec.it>") == "inviata"
    inizio = time.perf_counter()
    _indirizzo("+" * 200_000 + "@")
    assert time.perf_counter() - inizio < 0.5
