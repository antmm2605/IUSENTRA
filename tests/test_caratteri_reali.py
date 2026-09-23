"""I caratteri veri al posto dei quattordici di base.

Chi riesporta un PDF ha, di suo, solo le metriche Adobe: Times non e' Times New
Roman, Helvetica non e' Arial, e l'uno per cento di differenza in larghezza, su
una riga giustificata, sposta le parole in mezzo di piu' di un millimetro.

Gli equivalenti metrici aperti — Liberation, Carlito, Caladea — hanno le stesse
larghezze carattere per carattere. Questi test tengono ferme due cose: che si
sostituisca solo fra equivalenti veri, e che senza caratteri sul sistema non
succeda niente di male.
"""

from __future__ import annotations

import pytest

from pct import caratteri_reali


@pytest.fixture(autouse=True)
def registro_pulito():
    caratteri_reali.azzera_per_prova()
    yield
    caratteri_reali.azzera_per_prova()


def _ce_ne_sono() -> bool:
    return bool(caratteri_reali.registro())


def test_senza_caratteri_sul_sistema_non_succede_niente(monkeypatch):
    """Il ripiego resta quello di prima: i quattordici di base."""
    monkeypatch.setattr(caratteri_reali, "CARTELLE", ())
    caratteri_reali.azzera_per_prova()
    assert caratteri_reali.registro() == {}
    assert caratteri_reali.tagli_per("Times New Roman") is None


def test_l_etichetta_del_convertitore_non_decide():
    """«F1» non e' un carattere: e' un'etichetta, e dietro c'e' il nome vero."""
    if not _ce_ne_sono():
        pytest.skip("su questa macchina non ci sono i caratteri aperti")
    tagli = caratteri_reali.tagli_per("'F1', 'Times New Roman', serif")
    assert tagli is not None
    assert "LiberationSerif" in tagli["normal"]


def test_si_sostituisce_solo_fra_equivalenti_metrici():
    """Book Antiqua non ha un equivalente aperto: meglio il ripiego dichiarato.

    Mettergli al posto un DejaVu Serif — serif lo e', ma con larghezze sue —
    aveva portato quel documento dal 30% al 6% di parole al loro posto.
    """
    if not _ce_ne_sono():
        pytest.skip("su questa macchina non ci sono i caratteri aperti")
    assert caratteri_reali.tagli_per("'Book Antiqua', serif") is None
    assert caratteri_reali.tagli_per("'Garamond', serif") is None


def test_il_nome_generico_non_e_un_riconoscimento():
    """«Helvetica» e' quello che si scrive quando non si e' riconosciuto niente."""
    if not _ce_ne_sono():
        pytest.skip("su questa macchina non ci sono i caratteri aperti")
    assert caratteri_reali.tagli_per("'Helvetica', 'Arial', sans-serif") is None


def test_le_famiglie_che_contano_sono_coperte():
    if not _ce_ne_sono():
        pytest.skip("su questa macchina non ci sono i caratteri aperti")
    attese = {
        "Times New Roman": "LiberationSerif",
        "Arial": "LiberationSans",
        "Courier New": "LiberationMono",
        "Calibri": "Carlito",
        "Cambria": "Caladea",
    }
    for dichiarata, famiglia in attese.items():
        tagli = caratteri_reali.tagli_per(dichiarata)
        assert tagli, f"{dichiarata} non e' coperta"
        assert famiglia in tagli["normal"], f"{dichiarata} -> {tagli['normal']}"
        assert set(tagli) == {"normal", "bold", "italic", "bold_italic"}


def test_una_famiglia_entra_solo_col_corredo_completo(monkeypatch, tmp_path):
    """Mezzo corredo e' peggio di nessuno: il corsivo tornerebbe tondo."""
    (tmp_path / "LiberationSerif-Regular.ttf").write_bytes(b"non e' un carattere")
    monkeypatch.setattr(caratteri_reali, "CARTELLE", (tmp_path,))
    caratteri_reali.azzera_per_prova()
    assert caratteri_reali.tagli_per("Times New Roman") is None
