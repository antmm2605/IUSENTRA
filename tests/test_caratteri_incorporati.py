"""I caratteri che il PDF si porta dentro, riusati per riscriverlo.

Un atto in *French Script MT* non si riproduce con i quattordici caratteri base
del PDF, e un equivalente metrico aperto quel carattere non ce l'ha. Sta pero'
dentro il documento: il PDF se lo porta incorporato.

La trappola, e la ragione di questi test: il carattere incorporato e' un
**sottoinsieme** — solo le lettere che quel documento usa. Scrivendoci una
parola nuova, le lettere che mancano non danno errore: escono bianche. Su un
atto che si deposita e' il difetto peggiore, perche' non si vede.
"""

from __future__ import annotations

import base64
import struct

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from pct.documento_fedele import caratteri_incorporati as C
from pct.documento_fedele.sorgente import DocumentoSorgente


@pytest.fixture(autouse=True)
def registro_pulito():
    C.azzera_per_prova()
    yield
    C.azzera_per_prova()


def _un_carattere_vero() -> bytes:
    """Un TrueType completo preso dal sistema, per le prove."""
    from pct import caratteri_reali

    tagli = caratteri_reali.tagli_per("Times New Roman")
    if not tagli:
        pytest.skip("su questa macchina non ci sono caratteri da incorporare")
    percorso = pdfmetrics.getFont(tagli["normal"]).face._ttf_data
    return percorso if isinstance(percorso, bytes) else b""


@pytest.fixture
def atto_con_carattere(tmp_path):
    """Un PDF che si porta dentro il suo carattere."""
    from pct import caratteri_reali

    tagli = caratteri_reali.tagli_per("Times New Roman")
    if not tagli:
        pytest.skip("su questa macchina non ci sono caratteri da incorporare")

    percorso = tmp_path / "incorporato.pdf"
    foglio = canvas.Canvas(str(percorso), pagesize=A4)
    foglio.setFont(tagli["normal"], 14)
    foglio.drawString(25 * mm, 250 * mm, "Patrocinante in Cassazione")
    foglio.showPage()
    foglio.save()
    return percorso


def test_il_carattere_si_tira_fuori_dal_documento(atto_con_carattere):
    with DocumentoSorgente(atto_con_carattere) as documento:
        trovati = C.caratteri_della_pagina(documento[0])

    assert trovati, "nessun carattere incorporato trovato"
    voce = next(iter(trovati.values()))
    assert voce["alias"].startswith("iu-")
    assert voce["dati"][:4] in (b"\x00\x01\x00\x00", b"true", b"ttcf", b"OTTO")


def test_lo_stesso_carattere_ha_sempre_lo_stesso_alias(atto_con_carattere):
    """Cosi' su venti pagine si registra una volta sola."""
    with DocumentoSorgente(atto_con_carattere) as documento:
        primo = C.caratteri_della_pagina(documento[0])
        secondo = C.caratteri_della_pagina(documento[0])
    assert [v["alias"] for v in primo.values()] == [v["alias"] for v in secondo.values()]


def test_il_blocco_di_stile_va_e_torna(atto_con_carattere):
    with DocumentoSorgente(atto_con_carattere) as documento:
        trovati = C.caratteri_della_pagina(documento[0])
    voce = next(iter(trovati.values()))

    blocco = C.blocco_stile(trovati)
    assert voce["alias"] in blocco and "@font-face" in blocco

    riletti = C.leggi_blocco_stile(blocco)
    assert riletti[voce["alias"]] == voce["dati"]


def test_non_si_incorpora_quello_che_ha_gia_un_equivalente(atto_con_carattere):
    """Times New Roman ha Liberation Serif: e' un carattere intero, non un
    sottoinsieme, e si puo' usare anche sul testo che l'avvocato riscrive."""
    with DocumentoSorgente(atto_con_carattere) as documento:
        trovati = C.caratteri_della_pagina(documento[0])
    alias = {v["alias"] for v in trovati.values()}

    da_portare = C.da_incorporare(trovati, alias)
    nomi = {n.lower() for n in da_portare}
    assert not any("liberation" in n or "times" in n for n in nomi), (
        "si sta incorporando un carattere che ha gia' un equivalente aperto"
    )


def test_quello_che_nessuno_usa_non_si_porta_dietro(atto_con_carattere):
    with DocumentoSorgente(atto_con_carattere) as documento:
        trovati = C.caratteri_della_pagina(documento[0])
    assert C.da_incorporare(trovati, set()) == {}


# ------------------------------------------------------- il controllo dei glifi

def test_il_controllo_dei_glifi_vede_le_lettere_che_mancano(atto_con_carattere):
    """E' quello che rende sicuro riusare un sottoinsieme.

    Senza, le lettere che l'avvocato aggiunge escono bianche e non se ne
    accorge nessuno.
    """
    with DocumentoSorgente(atto_con_carattere) as documento:
        trovati = C.caratteri_della_pagina(documento[0])
    voce = next(iter(trovati.values()))
    nome = C.registra(voce["alias"], voce["dati"])
    assert nome, "il carattere estratto non si e' registrato"

    assert C.copre(nome, "Patrocinante in Cassazione")
    assert C.copre(nome, "")
    # il sottoinsieme di un PDF non ha l'alfabeto intero
    assert not C.copre(nome, "Patrocinante in Cassazione ЖЯא")


def test_un_carattere_rotto_non_si_registra_e_non_copre_niente():
    assert C.registra("iu-rotto", b"non e' un carattere") is None
    assert not C.copre("iu-rotto", "qualunque cosa")


def test_i_caratteri_troppo_grossi_restano_fuori(atto_con_carattere, monkeypatch):
    """Duecento kilobyte per pagina non valgono la resa di una riga."""
    monkeypatch.setattr(C, "TAGLIA_MASSIMA", 10)
    with DocumentoSorgente(atto_con_carattere) as documento:
        assert C.caratteri_della_pagina(documento[0]) == {}
