"""«Memoria conclusionale» è la comparsa conclusionale dell'art. 190 c.p.c. (verifica del 02/11/2026).

La regola generica delle memorie la leggeva come «Memoria difensiva».
"""

from pct.document_intelligence.catalog_resolver import _classify_indexed_content


def test_memoria_conclusionale_non_e_memoria_difensiva():
    testo = ("TRIBUNALE DI CITTÀ ESEMPIO\nR.G. n. 1234/2026\nMEMORIA CONCLUSIONALE EX ART. 190 C.P.C.\n"
             "nell'interesse di Mario Rossi contro Beta S.r.l.\nSi insiste per l'accoglimento delle conclusioni già precisate.")
    esito = _classify_indexed_content(testo)
    assert esito.label == "Comparsa conclusionale" and esito.confidence >= 90
