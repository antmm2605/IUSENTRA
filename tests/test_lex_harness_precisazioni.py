"""Precisazioni prudenti e lato nell'esecuzione (24/11/2026): frasi nuove, mai i banchi."""
from __future__ import annotations

import pytest

from lex.harness import rispondi
from lex.harness.chiarimenti import materia_da_chiarire
from lex.harness.significato import area, voci


@pytest.mark.parametrize("regola", ["consumatore", "competenza_pagamento", "negoziazione_obbligatoria"])
def test_strumento_scelto_senza_importo_chiede_il_dato_e_non_fallisce(regola):
    nome = next(v.nome for v in voci() if v.regola == regola)
    r = rispondi(f"ho una questione con un negozio (strumento: {nome})")
    assert r is not None and r.regola == "chiarimento_dati" and "valore della causa" in r.testo


def test_mai_una_precisazione_con_una_sola_opzione_e_opzioni_della_stessa_area():
    for domanda in ("il vicino ha alzato un muro sul confine e mi toglie la luce", "la banca mi ha messo in centrale rischi",
                    "ho un problema con un contratto, mi aiuti?"):
        r = rispondi(domanda)
        if r is not None and r.regola == "chiarimento_strumento":
            scelte = r.registro["scelte"]
            assert len(scelte) >= 2
            nomi = [s.rsplit("(strumento: ", 1)[1].rstrip(")") for s in scelte]
            aree = {area(v.regola) for v in voci() if v.nome in nomi}
            assert len(aree) == 1


@pytest.mark.parametrize("domanda", ["Prepara il ricorso per cassazione ex art. 360 c.p.c. per vizio di motivazione",
                                     "Entro quando l'appello ai sensi dell'art. 593 c.p.p.?"])
def test_con_un_articolo_di_codice_niente_civile_o_penale(domanda):
    assert materia_da_chiarire(domanda) is None


@pytest.mark.parametrize("domanda,regola", [
    ("Mi hanno pignorato l'auto ma è intestata a me, non al debitore: sono il terzo, cosa faccio?", "es_opposizione_terzo"),
    ("Mi stanno pignorando la casa, voglio pagare per evitare la vendita all'asta", "es_conversione_pignoramento"),
    ("Ho ricevuto un precetto per un debito del 2012 ormai prescritto, come mi difendo?", "opposizione_precetto"),
    ("Mi hanno pignorato la pensione: possono prendermela tutta?", "pignoramento_terzi"),
    ("La sentenza di separazione è del 2024, ora voglio cambiare il collocamento dei figli", "modifica_condizioni"),
])
def test_lato_e_rimedi_vicini(domanda, regola):
    r = rispondi(domanda)
    assert r is not None and r.regola == regola, r.regola if r else None
