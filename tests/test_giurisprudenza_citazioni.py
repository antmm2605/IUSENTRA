"""Lettore delle citazioni nelle decisioni: norme applicate e precedenti (esempi dalle forme reali dei testi)."""

from pct.giurisprudenza_citazioni import norme_citate, precedenti_citati

TESTO = ("Il ricorso denuncia, ai sensi dell'art.360, comma 1, n. 3 cod. proc. civ., violazione dell'art. 7, legge n. 300/1970, "
         "dell'art. 55 bis d.lgs. n. 165/2001 e dell'art. 2087 c.c.; l'avviso ex art. 415 - bis cod. proc. pen. era stato ricevuto. "
         "Si veda, per tutte: Cass. S.U. 27 dicembre 2019, n. 34476 e Cass. 14 aprile 2017, n. 8758; v. anche Cass., Sez. U, n. 24418 "
         "del 2010 e Corte cost. n. 194 del 2018. Richiamato l'art. 63, comma 2, del d.lgs. 30 marzo 2001, n. 165.")


def test_norme_dei_codici_e_delle_leggi():
    norme = {(n["sigla"], n["articolo"], n["comma"]) for n in norme_citate(TESTO)}
    assert ("c.p.c.", "360", "1") in norme
    assert ("L. 300/1970", "7", "") in norme
    assert ("D.Lgs. 165/2001", "55-bis", "") in norme
    assert ("c.c.", "2087", "") in norme
    assert ("c.p.p.", "415-bis", "") in norme


def test_precedenti_con_data_prima_del_numero_e_sezioni_unite():
    precedenti = {(p["organo_giudicante"], p["sezione"], p["numero_sentenza"], p["anno_sentenza"]) for p in precedenti_citati(TESTO, anno_decisione=2025)}
    assert ("Corte di Cassazione", "U", "34476", 2019) in precedenti
    assert ("Corte di Cassazione", "", "8758", 2017) in precedenti
    assert ("Corte di Cassazione", "U", "24418", 2010) in precedenti
    assert ("Corte costituzionale", "", "194", 2018) in precedenti


def test_un_precedente_non_puo_essere_successivo_alla_decisione():
    assert precedenti_citati("Cass. n. 1234/2027", anno_decisione=2025) == []


def test_atto_con_data_prima_del_numero():
    assert ("D.Lgs. 165/2001", "63", "2") in {(n["sigla"], n["articolo"], n["comma"]) for n in norme_citate(TESTO)}
