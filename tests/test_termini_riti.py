"""Motore unico dei termini: processo amministrativo, tributario e penale; 617, 481, 1137, 669-octies.

Risposte note calcolate a mano (art. 155 c.p.c.; art. 172 c.p.p.; L. 742/1969), norme lette nell'archivio Normattiva
del software il 19-20/11/2026. Lo stesso motore serve scadenziario, modello della causa e harness di Lex.
"""

from __future__ import annotations

from datetime import date

import pytest

from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

MODELLI = {t.code: t for t in DEFAULT_TEMPLATES}


def scadenza(codice: str, dal: date) -> str:
    return ItalianDeadlineCalculator().calculate_template(dal, MODELLI[codice])["deadline"]


@pytest.mark.parametrize("codice, dal, atteso", [
    # c.p.a.: 15/07 + 60 con sospensione (16 a luglio, 30 a settembre, 14 a ottobre) → 14/10/2026.
    ("AMM_RICORSO_29", date(2026, 7, 15), "2026-10-14"),
    ("AMM_APPALTI_120", date(2026, 9, 1), "2026-10-01"),
    # 31/10/2026 è sabato e l'01/11 domenica e festa: proroga al 02/11 (art. 155, commi 4-5, c.p.c.).
    ("AMM_DEPOSITO_45", date(2026, 10, 1), "2026-11-02"),
    ("AMM_COSTITUZIONE_46", date(2026, 9, 1), "2026-11-02"),
    ("AMM_APPELLO_92", date(2026, 7, 15), "2026-10-14"),
    # Tributario: stesso computo (art. 21 d.lgs. 546/1992; art. 1 l. 742/1969); 02/03 + 60 = 01/05 festivo, 02/05 sabato → 04/05.
    ("TRIB_RICORSO_21", date(2026, 7, 15), "2026-10-14"),
    ("TRIB_RICORSO_21", date(2026, 3, 2), "2026-05-04"),
    ("TRIB_COSTITUZIONE_22", date(2026, 10, 5), "2026-11-04"),
    ("TRIB_APPELLO_51", date(2026, 7, 15), "2026-10-14"),
    # Penale: 24/07 + 15 con sospensione → 08/09; dal 18/09 + 15 = 03/10 sabato, niente proroga (art. 172 c.p.p.).
    ("PEN_OPPOSIZIONE_DECRETO_461", date(2026, 7, 24), "2026-09-08"),
    ("PEN_OPPOSIZIONE_DECRETO_461", date(2026, 9, 18), "2026-10-03"),
    ("PEN_OPPOSIZIONE_ARCHIVIAZIONE_408", date(2026, 11, 2), "2026-11-23"),  # 22/11 domenica → 23/11
    ("PEN_OPPOSIZIONE_ARCHIVIAZIONE_408_VIOLENZA", date(2026, 11, 2), "2026-12-02"),
    ("PEN_IMPUGNAZIONE_585_15", date(2026, 11, 2), "2026-11-17"),
    ("PEN_IMPUGNAZIONE_585_45", date(2026, 10, 1), "2026-11-16"),  # 15/11 domenica → 16/11
    # Querela: tre mesi, termine sostanziale, niente sospensione feriale (art. 124 c.p.).
    ("PEN_QUERELA_124", date(2026, 6, 10), "2026-09-10"),
    # Art. 617 c.p.c.: niente sospensione feriale (art. 92 R.D. 12/1941; Cass. ord. 21568/2017): 25/07 + 20 = 14/08.
    ("ESE_OPPOSIZIONE_ATTI_617", date(2026, 7, 25), "2026-08-14"),
    # Art. 481 c.p.c.: novanta giorni, termine sostanziale senza sospensione feriale: 20/07 + 90 = 18/10.
    ("ESE_PRECETTO_EFFICACIA_90GG", date(2026, 7, 20), "2026-10-18"),
    # Art. 1137 c.c.: sospensione feriale (Corte cost. 49/1990): 11 giorni a luglio, 19 a settembre → 19/09.
    ("CIV_IMPUGNAZIONE_DELIBERA_1137", date(2026, 7, 20), "2026-09-19"),
])
def test_termini_a_risposta_nota(codice, dal, atteso):
    assert scadenza(codice, dal) == atteso


def test_617_corretto_con_nuova_versione_del_modello():
    modello = MODELLI["ESE_OPPOSIZIONE_ATTI_617"]
    assert modello.suspend_august is False and modello.version >= 2 and "92 R.D. 12/1941" in modello.reference_law


def test_669_octies_dichiara_il_dubbio_quando_attraversa_agosto():
    calcolatore = ItalianDeadlineCalculator()
    estate = calcolatore.calculate_template(date(2026, 7, 15), MODELLI["CIV_MERITO_669_OCTIES"])
    assert estate["deadline"] == "2026-09-14" and "Sospensione feriale controversa" in estate["dubbio"]
    assert estate["requiresLegalReview"] is True
    inverno = calcolatore.calculate_template(date(2026, 1, 15), MODELLI["CIV_MERITO_669_OCTIES"])
    assert inverno["deadline"] == "2026-03-16" and "dubbio" not in inverno


def test_ricorso_tributario_con_accertamento_con_adesione():
    from pct.termini_riti import ricorso_tributario

    assert ricorso_tributario(date(2026, 3, 2))["scadenza"] == "2026-05-04"
    # Istanza di adesione: termine sospeso novanta giorni (art. 6, comma 3, d.lgs. 218/1997): 02/03 + 150 = 30/07.
    assert ricorso_tributario(date(2026, 3, 2), istanza_adesione=date(2026, 3, 20))["scadenza"] == "2026-07-30"
    # Dopo lo schema in contraddittorio preventivo: trenta giorni (art. 6, comma 2-bis): 02/03 + 90 = 31/05 domenica → 01/06.
    assert ricorso_tributario(date(2026, 3, 2), istanza_adesione=date(2026, 3, 10), dopo_schema=True)["scadenza"] == "2026-06-01"


def _modello(tipo, testo, oggi):
    from pct.ragionamento import FontiCausa, ragiona

    documento = {"id": "A", "nome": "atto.pdf", "natura": "provvedimento", "etichetta": "Atto", "testo": testo, "data_documento": ""}
    return ragiona(FontiCausa(fascicolo={"id": "F", "numero_rg": "1", "anno_rg": "2026", "tipo": tipo},
                              studio={"avvocati": ["Avv. Mario Rossi"]}, documenti=[documento], oggi=oggi))


@pytest.mark.parametrize("tipo, testo, oggi, codice, atteso", [
    ("TRIBUTARIO", "AGENZIA DELLE ENTRATE AVVISO DI ACCERTAMENTO IRPEF 2021. Atto notificato il 15/07/2026 a mezzo PEC.",
     date(2026, 7, 20), "ricorso_tributario", "2026-10-14"),
    ("AMMINISTRATIVO", "COMUNE DI BARI Determina di aggiudicazione della gara; comunicata in data 01/09/2026.",
     date(2026, 9, 2), "ricorso_tar_appalti", "2026-10-01"),
    ("AMMINISTRATIVO", "COMUNE DI LECCE ORDINANZA DI DEMOLIZIONE n. 5 notificata il 15/07/2026 al sig. Russo.",
     date(2026, 7, 20), "ricorso_tar", "2026-10-14"),
    ("PENALE", "TRIBUNALE DI NAPOLI DECRETO PENALE DI CONDANNA nei confronti di FERRI LUIGI notificato il 24/07/2026.",
     date(2026, 7, 25), "opposizione_decreto_penale", "2026-09-08"),
    ("PENALE", "PROCURA AVVISO DELLA RICHIESTA DI ARCHIVIAZIONE per delitto commesso con violenza alla persona, "
               "notificato il 02/11/2026.", date(2026, 11, 3), "opposizione_archiviazione", "2026-12-02"),
])
def test_il_modello_della_causa_usa_lo_stesso_motore(tipo, testo, oggi, codice, atteso):
    causa = _modello(tipo, testo, oggi)
    (voce,) = [c for c in causa.conclusioni if c.codice == codice]
    assert causa.rito.codice == tipo.lower() and voce.stato == "da_fare" and voce.onerato == "noi"
    assert voce.termine.scadenza == atteso and voce.termine.perentorio is True


def test_senza_data_di_notifica_nessun_termine_inventato():
    causa = _modello("TRIBUTARIO", "AGENZIA DELLE ENTRATE AVVISO DI ACCERTAMENTO IRPEF 2021.", date(2026, 7, 20))
    (voce,) = causa.conclusioni if len(causa.conclusioni) == 1 else [c for c in causa.conclusioni if c.codice == "ricorso_tributario"]
    assert voce.stato == "dubbio" and voce.termine is None and voce.dubbi[0].codice == "decorrenza_ignota"
