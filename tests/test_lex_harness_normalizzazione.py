"""Normalizzazione tollerante e ingresso dei racconti senza punto interrogativo (24/11/2026). Frasi nuove, mai i banchi."""
from __future__ import annotations

import pytest

from lex.harness.comprensione import comprendi
from lex.harness.fatti import leggi_fatti
from lex.harness.fattispecie import scegli
from lex.harness.normalizzazione import correggi_refusi, normalizza_richiesta


@pytest.mark.parametrize("scritto,atteso", [("stipendo", "stipendio"), ("condutore", "conduttore"), ("sfrato", "sfratto"),
                                            ("opposizone", "opposizione")])
def test_refusi_corretti_solo_con_un_candidato(scritto, atteso):
    assert correggi_refusi(f"il {scritto} del cliente") == f"il {atteso} del cliente"


@pytest.mark.parametrize("testo", ["Il signor Brambillasca è stato licenziato", "art. 2087 c.c. del 12/03/2026 per 15.000 euro",
                                   "il dipendente è licenziato", "le lavoratrici licenziate",
                                   "l'amministratore ha distratto fondi della società"])
def test_nomi_numeri_date_e_flessioni_non_si_toccano(testo):
    from lex.harness.normalizzazione import senza_accenti

    assert correggi_refusi(senza_accenti(testo)) == senza_accenti(testo)


def test_linguaggio_comune_affiancato_dal_termine_tecnico():
    t = normalizza_richiesta("Il padrone di casa trattiene la cauzione dell'affitto")
    assert t.startswith("Il padrone di casa") and "locatore" in t and "locazione" in t


RACCONTI = [
    ("Il mio inquilino non mi paga l'affitto da cinque mesi e voglio riavere la casa", "sfratto_morosita"),
    ("Mi hanno notificato un precetto da 7.000 euro ma avevo già pagato tutto con bonifico, voglio oppormi",
     "opposizione_precetto"),
    ("Il mio capo mi ha licenziato a voce la settimana scorsa senza nessuna lettera", "impugnazione_licenziamento"),
]


@pytest.mark.parametrize("testo,regola", RACCONTI)
def test_racconti_senza_punto_interrogativo_entrano_e_trovano_la_regola(testo, regola):
    c = comprendi(testo)
    assert c.per_harness, c
    from lex.harness.normalizzazione import normalizza_richiesta as n

    r = scegli(c, leggi_fatti(n(testo)))
    assert r is not None and r[0] == regola


@pytest.mark.parametrize("testo", ["ciao, buongiorno", "grazie mille", "mostrami le scadenze di domani",
                                   "apri il fascicolo Rossi"])
def test_saluti_e_comandi_restano_fuori(testo):
    assert not comprendi(testo).per_harness
