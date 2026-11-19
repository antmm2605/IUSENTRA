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
    assert "da verificare" in P.ufficio("Tribunale", "Modugno")


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
