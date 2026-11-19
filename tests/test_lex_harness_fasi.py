"""Test «a risposta nota» per le fasi dell'harness di Lex: termini, competenza, procedibilità, fatti, controllo."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import procedura as P
from lex.harness.controllo import citazioni
from lex.harness.fatti import leggi_fatti
from lex.harness.norme import ISTANTANEA, contiene
from lex.harness.termini import termine_anni, termine_giorni, termine_mesi

archivio = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")


# ------------------------------------------------------------------ termini (art. 155 c.p.c., l. 742/1969)
@pytest.mark.parametrize("dal,giorni,feriale,sostanziale,atteso", [
    (date(2026, 7, 1), 60, True, False, date(2026, 9, 30)),     # a cavallo di agosto: 30 giorni a luglio + 30 a settembre
    (date(2026, 4, 20), 30, True, False, date(2026, 5, 20)),    # appello civile, nessuna interferenza
    (date(2026, 9, 15), 60, True, False, date(2026, 11, 16)),   # scade sabato 14/11 → lunedì 16/11 (art. 155, comma 5)
    (date(2026, 3, 10), 60, False, True, date(2026, 5, 9)),     # sostanziale: sabato 09/05 resta (decadenza art. 1667 c.c.)
    (date(2026, 9, 2), 60, False, True, date(2026, 11, 2)),     # sostanziale: domenica e festivo 01/11 → 02/11
    (date(2026, 7, 20), 30, False, False, date(2026, 8, 19)),   # lavoro: niente sospensione feriale (art. 3 l. 742/1969)
    (date(2026, 11, 3), 40, True, False, date(2026, 12, 14)),   # opposizione a d.i.: domenica 13/12 → 14/12
])
def test_termini_a_risposta_nota(dal, giorni, feriale, sostanziale, atteso):
    assert termine_giorni(dal, giorni, sospensione_feriale=feriale, sostanziale=sostanziale) == atteso


def test_termini_in_mesi_e_anni():
    assert termine_mesi(date(2026, 6, 30), 6, sostanziale=True) == date(2026, 12, 30)   # art. 13 l. 431/1998
    assert termine_mesi(date(2026, 9, 28), 3, sostanziale=True) == date(2026, 12, 28)   # querela, art. 124 c.p.
    assert termine_anni(date(2026, 2, 20), 2) == date(2028, 2, 21)                       # domenica 20/02/2028 → 21/02


def test_termine_a_ritroso_costituzione_convenuto():
    """Art. 166 c.p.c.: almeno settanta giorni prima dell'udienza; termine libero a ritroso (motore dello scadenziario)."""
    from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

    modello = next(t for t in DEFAULT_TEMPLATES if t.code == "CIV_COSTITUZIONE_CONVENUTO_166")
    esito = ItalianDeadlineCalculator().calculate_template(date(2027, 3, 15), modello)
    scad = date.fromisoformat(esito["deadline"])
    assert (date(2027, 3, 15) - scad).days >= 70 and scad.weekday() < 5


# ------------------------------------------------------------------ competenza per valore e uffici
@archivio
@pytest.mark.parametrize("valore,circolazione,atteso", [
    (8000, False, "Giudice di pace"), (10000, False, "Giudice di pace"), (10000.01, False, "Tribunale"),
    (22000, True, "Giudice di pace"), (26000, True, "Tribunale"), (50000, False, "Tribunale"),
])
def test_competenza_per_valore(valore, circolazione, atteso):
    assert P.giudice_per_valore(valore, circolazione=circolazione)[0] == atteso


def test_ufficio_solo_se_esiste():
    assert P.ufficio("Tribunale", "Bari") == "Tribunale di Bari"
    assert P.ufficio("Giudice di pace", "Altamura") == "Giudice di pace di Altamura"
    assert P.ufficio("Tribunale", "Modugno") == "Tribunale di Bari (competente per Modugno)"   # circondario dal Ministero
    assert "da verificare" in P.ufficio("Tribunale", "Paesefantasma")


# ------------------------------------------------------------------ procedibilità
@archivio
def test_negoziazione_soglia_inclusa_ed_esclusioni():
    assert "obbligatoria" in P.negoziazione_pagamento(50000)[0].testo
    assert "non è obbligatoria" in P.negoziazione_pagamento(50000.01)[0].testo
    assert "consumatori" in P.negoziazione_pagamento(3000, consumatore=True)[0].testo
    assert "ingiunzione" in P.negoziazione_pagamento(12000, monitorio=True)[0].testo
    assert "mediazione obbligatoria" in P.negoziazione_pagamento(2000, mediazione=True)[0].testo


@archivio
def test_mediazione_materie():
    assert "rientra nell'elenco" in P.mediazione_obbligatoria("locazione")[0].testo
    assert "non rientra" in P.mediazione_obbligatoria(None)[0].testo


# ------------------------------------------------------------------ norme e controllo
@archivio
def test_ancore_letterali_del_testo_vigente():
    assert contiene("cc:1385", "esigere il doppio della caparra")
    assert contiene("cpc:10", "gli interessi scaduti, le spese e i danni anteriori alla proposizione si sommano col capitale")
    assert not contiene("cpc:14", "gli interessi scaduti, le spese e i danni anteriori alla proposizione si sommano col capitale")
    assert contiene("l241:21nonies", "non superiore a sei mesi dal momento dell'adozione")


def test_citazioni_riconosciute():
    coppie = dict(citazioni("artt. 10 e 14 c.p.c.; art. 473-bis.11 c.p.c.; art. 21-nonies l. 241/1990; art. 204-bis cod. strada"))
    assert set(coppie.values()) == {"cpc:10", "cpc:14", "cpc:473bis11", "l241:21nonies", "dlgs285:204bis"}


# ------------------------------------------------------------------ fatti
def test_fatti_dal_racconto_strutturato():
    f = leggi_fatti("Data di oggi 16/11/2026 Parte assistita Luca Ferrandina (promissario acquirente, attore) Controparte "
                    "Giorgio Salvemini (promittente venditore, convenuto) Richiesta dell'avvocato Redigimi la citazione. "
                    "Fatti del fascicolo Il 12/02/2026 Ferrandina ha versato 25.000 euro a titolo di caparra confirmatoria. "
                    "Residenza del convenuto: Bari.")
    assert f.oggi == date(2026, 11, 16)
    assert (f.assistita.nome, f.controparte.nome, f.residenza_convenuto) == ("Luca Ferrandina", "Giorgio Salvemini", "Bari")
    assert f.importo("caparra").valore == 25000


# ------------------------------------------------------------------ regressioni dei difetti provati dalla revisione (19/11)
def test_ricorso_gdp_verbale_cds_con_sospensione_feriale():
    from lex.harness.termini import termine

    assert termine("CDS_RICORSO_GDP_30GG", date(2026, 7, 20)) == date(2026, 9, 21)   # 19/09 sabato → 21/09


@archivio
def test_verbale_cds_risposta_con_termine_del_modello():
    from lex.harness import rispondi

    r = rispondi("La mia cliente Anna Rossi ha ricevuto un verbale per autovelox: accertamento del 10/05/2026 nel territorio "
                 "del Comune di Bari, verbale notificato a Anna Rossi a mezzo posta il 20/07/2026. Prepara il ricorso al "
                 "giudice di pace.")
    assert "21/09/2026" in r.testo and "19/08/2026" not in r.testo


@archivio
def test_tutele_crescenti_solo_dal_7_marzo_2015_e_piccola_impresa():
    from lex.harness import rispondi

    prima = rispondi("Licenziamento per giustificato motivo oggettivo: la mia cliente Maria Bianchi è stata assunta il "
                     "02/03/2015 da Alfa s.r.l., 40 dipendenti, retribuzione 2.000 euro; lettera ricevuta il 10/11/2026. "
                     "Che tutela possiamo chiedere?")
    assert "assunto prima del 7 marzo 2015" in prima.testo and "tutele crescenti e non" not in prima.testo
    piccola = rispondi("Licenziamento per giustificato motivo oggettivo: la mia cliente Maria Bianchi è stata assunta il "
                       "10/03/2018 da Alfa s.r.l., 10 dipendenti, retribuzione 2.000 euro; lettera ricevuta il 10/11/2026. "
                       "Che tutela possiamo chiedere?")
    assert "dimezzati" in piccola.testo and "massimo diciotto mensilità € 36.000" in piccola.testo


@archivio
def test_caparra_senza_importi_scritti_fissi():
    from lex.harness import rispondi

    r = rispondi("Redigi un atto di citazione per la mia cliente Anna Neri, promissaria acquirente: il promittente venditore "
                 "Paolo Riva, residente a Bari, non si è presentato al rogito del 15/05/2026. Con il preliminare del "
                 "10/01/2026 ha versato 10.000 euro a titolo di caparra confirmatoria per un appartamento in Bari.")
    assert "€ 20.000" in r.testo and "supererebbe € 50.000" not in r.testo
    assert "1284" in r.testo


@archivio
def test_appalto_con_consumatore_niente_negoziazione_e_garanzia_di_conformita():
    from lex.harness import rispondi

    r = rispondi("Il mio cliente Mario Verdi ha commissionato a Infissi Rossi s.r.l. la fornitura e posa di finestre nella sua "
                 "abitazione di Monopoli, corrispettivo 7.000 euro. Consegna il 10/02/2026. Il 01/03/2026 scopre infiltrazioni; "
                 "denuncia i vizi con PEC del 10/03/2026; costo di ripristino 2.500 euro. Che azione possiamo fare?")
    assert "non è obbligatoria" in r.testo and "codice del consumo" in r.testo
    assert "Giudice di pace di Monopoli" in r.testo


def test_circondario_di_comune_non_sede():
    assert P.ufficio("Tribunale", "Modugno").startswith("Tribunale di Bari")


def test_errore_della_regola_dichiarato_e_registrato(monkeypatch, caplog):
    import lex.harness.http as H

    def guasto(*a, **k):
        raise RuntimeError("prova")

    monkeypatch.setattr(H, "rispondi", guasto)
    p = H.payload_harness("Redigi l'atto di citazione per la caparra versata dal mio cliente al promittente venditore.")
    assert p is not None and p["confidence"] == 0.0 and "Analisi non completata" in p["answer"]
    assert any("harness" in r.getMessage() for r in caplog.records)


@archivio
def test_prescrizione_interrotta_dalla_notifica_non_dal_deposito():
    import json
    from pathlib import Path

    from lex.harness import rispondi

    casi = json.loads((Path(__file__).parent / "lex_collaudo" / "casi_avvocato.json").read_text(encoding="utf-8"))["casi"]
    base = next(c["domanda"] for c in casi if c["id"] == "D4_1_02")
    # Scadenza 10/03/2016: dieci anni il 10/03/2026. Deposito prima (20/02/2026), notifica dopo (20/03/2026): prescritta.
    domanda = (base.replace("25/09/2026 - Metalcarb deposita", "20/02/2026 - Metalcarb deposita")
               .replace("20/10/2026 - viene notificato", "20/03/2026 - viene notificato"))
    r = rispondi(domanda.replace("Data di oggi 05/11/2026", "Data di oggi 05/04/2026"))
    assert "si eccepisce la prescrizione" in r.testo and "notificazione del ricorso e del decreto" in r.testo


def test_feriale_617_esclusa_e_1137_applicata():
    from lex.harness.termini import termine

    assert termine("LEX_ESE_OPPOSIZIONE_ATTI_617", date(2026, 7, 25)) == date(2026, 8, 14)   # art. 92 ord. giud.
    assert termine("LEX_CONDOMINIO_1137", date(2026, 7, 20)) == date(2026, 9, 19)            # Corte cost. 49/1990
