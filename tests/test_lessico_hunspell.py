"""Il dizionario italiano si legge come lo legge Hunspell: radici più regole.

Il difetto che questi test impediscono: leggere il solo `.dic` e fermarsi alle
radici. «udienza» c'è, «udienze» no — nasce dalla regola `SFX Q a e [^gc]a` del
file `.aff`. Un correttore che non applica le regole non conosce i plurali, i
femminili e le forme verbali, cioè quasi tutto l'italiano scritto in un atto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from legal_ocr.lessico import hunspell
from legal_ocr.lessico.hunspell import Affisso, DizionarioItaliano, _condizione, _sigle, dizionario_italiano

AFF = """SET UTF-8
TRY aioertnsclmd

SFX Q N 2
SFX Q a e [^gc]a
SFX Q a he [gc]a

SFX D Y 1
SFX D 0 mente .

PFX T Y 1
PFX T 0 l' [aeiou]
"""
DIC = """4
udienza/Q
banca/Q
perentorio/D
atto/T
"""


@pytest.fixture()
def dizionario(tmp_path: Path, monkeypatch) -> DizionarioItaliano:
    (tmp_path / "it_IT.aff").write_text(AFF, encoding="utf-8")
    (tmp_path / "it_IT.dic").write_text(DIC, encoding="utf-8")
    monkeypatch.setattr(hunspell, "PERCORSI_AFF", (str(tmp_path / "it_IT.aff"),))
    dizionario_italiano.cache_clear()
    esito = dizionario_italiano()
    yield esito
    dizionario_italiano.cache_clear()


def test_le_radici_del_dizionario_si_conoscono(dizionario):
    assert dizionario.disponibile
    assert set(dizionario.radici) == {"udienza", "banca", "perentorio", "atto"}
    assert dizionario.radici["udienza"] == frozenset({"Q"})


@pytest.mark.parametrize(
    ("parola", "attesa"),
    [
        ("udienza", True),      # radice
        ("udienze", True),      # SFX Q: togli «a», metti «e»
        ("banca", True),
        ("banche", True),       # SFX Q con la condizione [gc]a
        ("bance", False),       # la condizione non lo permette
        ("perentorio", True),
        ("perentoriomente", True),  # SFX D: aggiunge «mente»
        ("atto", True),
        ("l'atto", True),       # PFX T sulla vocale iniziale
        ("udienzo", False),
        ("cornparsa", False),
    ],
)
def test_le_flessioni_dichiarate_dal_file_aff_si_riconoscono(dizionario, parola, attesa):
    assert dizionario.conosce(parola) is attesa


def test_senza_dizionario_installato_niente_si_rompe(tmp_path, monkeypatch):
    monkeypatch.setattr(hunspell, "PERCORSI_AFF", (str(tmp_path / "assente.aff"),))
    dizionario_italiano.cache_clear()
    vuoto = dizionario_italiano()
    assert vuoto.disponibile is False
    assert vuoto.conosce("udienza") is False
    dizionario_italiano.cache_clear()


def test_serve_la_coppia_aff_e_dic(tmp_path, monkeypatch):
    (tmp_path / "it_IT.aff").write_text(AFF, encoding="utf-8")
    monkeypatch.setattr(hunspell, "PERCORSI_AFF", (str(tmp_path / "it_IT.aff"),))
    dizionario_italiano.cache_clear()
    assert dizionario_italiano().disponibile is False
    dizionario_italiano.cache_clear()


def test_le_sigle_seguono_il_modo_dichiarato_da_flag():
    assert _sigle("QTU", "char") == ("Q", "T", "U")
    assert _sigle("QTUV", "long") == ("QT", "UV")
    assert _sigle("1,22,333", "num") == ("1", "22", "333")
    assert _sigle("", "char") == ()


def test_la_condizione_hunspell_diventa_espressione_regolare():
    assert _condizione(".", suffisso=True) is None
    fine = _condizione("[^gc]a", suffisso=True)
    assert fine is not None and fine.search("udienza") and not fine.search("banca")
    inizio = _condizione("[aeiou]", suffisso=False)
    assert inizio is not None and inizio.search("atto") and not inizio.search("banca")


def test_un_affisso_non_applicabile_non_produce_radici():
    regola = Affisso(sigla="Q", toglie="a", mette="e", condizione=None, incrociabile=False)
    assert regola.base("udienze", suffisso=True) == "udienza"
    assert regola.base("udienza", suffisso=True) == ""  # non finisce con «e»
    assert regola.base("e", suffisso=True) == "a"


def test_il_dizionario_di_sistema_reale_se_installato():
    """Dove il pacchetto `hunspell-it` è installato, le forme flesse si riconoscono."""
    reale = dizionario_italiano()
    if not reale.disponibile:
        pytest.skip("dizionario italiano di sistema non installato in questo ambiente")
    assert reale.conosce("udienza") and reale.conosce("udienze")
    assert reale.conosce("ricorrente") and reale.conosce("ricorrenti")
    assert not reale.conosce("cornparsa")
