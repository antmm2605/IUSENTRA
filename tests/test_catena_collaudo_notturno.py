"""Il collaudo notturno della catena (pct/catena/collaudo.py) è superato con il codice di questo commit."""

from __future__ import annotations


def test_collaudo_notturno_superato():
    from pct.catena.collaudo import esegui_collaudo

    esito = esegui_collaudo()
    assert esito["superato"], [c for c in esito["casi"] if not c["superato"]]


def test_un_caso_guasto_rende_il_collaudo_non_superato_senza_fermarlo():
    from pct.catena.collaudo import CASI, esegui_caso

    def guasta(_caso):
        raise ValueError("fonte illeggibile")

    esito = esegui_caso(CASI[0], lettura=guasta)
    assert esito["superato"] is False and "ValueError" in esito["errore"]
