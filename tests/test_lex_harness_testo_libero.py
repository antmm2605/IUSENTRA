"""Testo libero del widget: fatti, date, importi e parti scritti come li scrive l'avvocato (formulazioni nuove,
non le frasi dei 22 casi)."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness.fatti import leggi_fatti

archivio = pytest.mark.usefixtures()


@pytest.mark.parametrize("testo,nome", [
    ("Assisto Marta Colonna nella causa contro la Beta s.r.l.", "Marta Colonna"),
    ("Il mio cliente è Giovanni Lattanzio, conduttore.", "Giovanni Lattanzio"),
    ("Agisco per conto di Alfa Logistica s.r.l. per un credito.", "Alfa Logistica s.r.l."),
    ("Difendo Carla Mele, lavoratrice licenziata.", "Carla Mele"),
    ("Cliente: Rocco Bellino (opponente).", "Rocco Bellino"),
])
def test_parte_assistita_in_tutte_le_formulazioni(testo, nome):
    assert leggi_fatti(testo).assistita.nome == nome


def test_oggi_scritto_in_modo_discorsivo_non_e_un_fatto():
    f = leggi_fatti("Ti scrivo per un parere.\n\nOggi è il 03/12/2026. Assisto Ugo Rana.\n\nFatti:\n"
                    "- 15/01/2026 - contratto di fornitura.\n- 20/02/2026 - consegna della merce.")
    assert f.oggi == date(2026, 12, 3)
    assert [e.data for e in f.eventi] == [date(2026, 1, 15), date(2026, 2, 20)]


def test_ogni_voce_dell_elenco_e_un_fatto_a_se():
    from lex.harness.fattispecie.strumenti import data_di

    f = leggi_fatti("Prepara il ricorso.\n\nOggi è il 03/12/2026.\n\nFatti:\n- Contratto d'appalto del 15/01/2026 per lavori "
                    "a Lecce.\n- Consegna dell'opera il 20/02/2026.\n- Prima denuncia scritta: PEC del 20/06/2026.")
    assert data_di(f, r"consegna") == date(2026, 2, 20)
    assert data_di(f, r"denuncia") == date(2026, 6, 20)


def test_coerenza_notifica_uguale_a_oggi_e_importo_zero():
    from lex.harness.coerenza import verifica
    from lex.harness.modello import Analisi, Punto

    f = leggi_fatti("Oggi è il 03/12/2026. Assisto Ugo Rana.")
    a = Analisi("prova", "civile")
    a.termini = [Punto("Avviso notificato il 03/12/2026: ricorso entro il 01/02/2027.", [])]
    a.conclusione = [Punto("Credito di € 0 da recuperare.", [])]
    dubbi = verifica(a, f)
    assert any("coincide con la data di oggi" in d for d in dubbi) and any("pari a zero" in d for d in dubbi)


def test_creditore_procedente_non_e_opposizione_a_precetto():
    from lex.harness import rispondi

    r = rispondi("Mi serve un parere: possiamo pignorare?\n\nOggi è il 12/07/2027. Parte assistita: Enzo Ricci (creditore "
                 "procedente). Controparte: Dario Fumo (debitore).\n\nFatti:\n- 10/01/2027 - notificato a Dario Fumo l'atto "
                 "di precetto per euro 5.000 in forza di sentenza esecutiva.\n- Il debitore non ha proposto opposizione.\n"
                 "- Nessun pignoramento è stato ancora notificato.")
    assert r is not None and r.regola != "opposizione_precetto"


def test_fatture_fra_imprese_dopo_la_diffida_vanno_al_decreto_ingiuntivo():
    from lex.harness import rispondi

    r = rispondi("Assisto Gamma Serramenti s.r.l., con sede a Treviso. Delta Edilizia s.p.a. non paga le fatture n. 4 del "
                 "02/02/2026 di euro 3.100 e n. 9 del 03/03/2026 di euro 4.400, nonostante la messa in mora del 10/05/2026. "
                 "Come recuperiamo il credito?")
    assert r.regola == "decreto_ingiuntivo" and "€ 7.500" in r.testo and "Treviso" in r.testo and "€ 0" not in r.testo


def test_cinquecento_importi_rispondono_in_meno_di_un_secondo():
    import time

    from lex.harness.coerenza import verifica
    from lex.harness.modello import Analisi, Punto

    testo = "Assisto Ugo Rana. Oggi è il 03/12/2026. " + " ".join(
        f"Pagato con bonifico euro {100 + i} il {1 + i % 28:02d}/0{1 + i % 9}/2026." for i in range(500))
    t = time.monotonic()
    f = leggi_fatti(testo)
    a = Analisi("prova", "civile")
    a.conclusione = [Punto("Pagati € 99.999 in tutto; " + "; ".join(f"€ {100 + i}" for i in range(500)), [])]
    verifica(a, f)
    assert time.monotonic() - t < 1.0
