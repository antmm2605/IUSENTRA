"""Una PEC dell'ufficio che cita il ruolo del fascicolo deve collegarsi.

Il collegatore diceva gia' nel suo commento che «il solo RG dedotto dal testo
resta insufficiente; il solo RG certificato dall'ufficio no». Il codice pero'
guardava soltanto se l'unica ragione fosse «RG coincidente», senza chiedersi
da dove venisse quel numero: una comunicazione del Tribunale di Santa Maria
Capua Vetere con in oggetto «3001/2025/LAV», sul fascicolo che ha esattamente
quel ruolo in quel tribunale, restava in `link_candidates` insieme ad altre
dodici, e la lettura del fascicolo le segnalava come lacune da colmare.

Il collegamento ora chiede tre prove indipendenti, e nessuna delle tre da
sola basta: il numero di ruolo, il mittente che e' quell'ufficio su dominio
ministeriale, e un atto del procedimento nel messaggio.
"""

from __future__ import annotations

import pytest

from pct.pec_pipeline import profilo_processuale_presente, ufficio_giudiziario_mittente

MITTENTE_UFFICIO = (
    '"Per conto di: tribunale.santamariacapuavetere@civile.ptel.giustiziacert.it"'
    " <posta-certificata@legalmail.it>"
)


def _messaggio(mittente: str = MITTENTE_UFFICIO, *, profilo: dict | None = None) -> dict:
    return {
        "headers": {"from": mittente, "subject": "POSTA CERTIFICATA: COMUNICAZIONE 3001/2025/LAV"},
        "fields": {"mittente": {"value": {"name": mittente, "email": "posta-certificata@legalmail.it"}}},
        "procedural_profile": profilo if profilo is not None else {"eventi": [{"evento": "accettazione deposito"}]},
    }


# ------------------------------------------------- chi ha spedito davvero


def test_l_ufficio_si_legge_dal_per_conto_di():
    """Nella PEC il mittente di trasporto e' il gestore: l'ufficio sta dentro."""

    assert ufficio_giudiziario_mittente(_messaggio()) == "santamariacapuavetere"


def test_l_ufficio_del_mittente_combacia_col_tribunale_del_fascicolo():
    import re

    del_fascicolo = re.sub(r"[^a-z]", "", "TRIBUNALE DI SANTA MARIA CAPUA VETERE".lower())

    assert ufficio_giudiziario_mittente(_messaggio()) in del_fascicolo


def test_una_corte_d_appello_viene_riconosciuta():
    mittente = '"Per conto di: corte.appello.reggiocalabria@civile.ptel.giustiziacert.it" <posta-certificata@legalmail.it>'

    assert ufficio_giudiziario_mittente(_messaggio(mittente)) == "appelloreggiocalabria"


def test_un_privato_non_e_un_ufficio():
    assert ufficio_giudiziario_mittente(_messaggio("Mario Rossi <mario@studio.legalmail.it>")) == ""


def test_il_nome_non_basta_senza_il_dominio_ministeriale():
    """Chiunque puo' scriversi «tribunale» nel nome visualizzato: il dominio no."""

    finto = '"Tribunale di Palmi" <tizio@gmail.com>'

    assert ufficio_giudiziario_mittente(_messaggio(finto)) == ""


def test_un_dominio_che_somiglia_non_passa():
    finto = '"Per conto di: tribunale.palmi@giustiziacert.it.example.com" <x@example.com>'

    assert ufficio_giudiziario_mittente(_messaggio(finto)) == ""


# ------------------------------------------------- l'atto del procedimento


def test_un_evento_processuale_conta_come_atto():
    assert profilo_processuale_presente(_messaggio()) is True


@pytest.mark.parametrize(
    "profilo",
    [
        {"oggetto_evento": "fissazione udienza"},
        {"descrizione_evento": "accettazione deposito"},
        {"cancelleria": "Cancelleria lavoro"},
        {"giudice": "Dott.ssa Bianchi"},
    ],
)
def test_anche_un_solo_dato_processuale_conta(profilo):
    assert profilo_processuale_presente(_messaggio(profilo=profilo)) is True


def test_una_ricevuta_senza_atto_non_conta():
    """Una busta vuota di contenuto processuale lascia l'RG come indizio."""

    assert profilo_processuale_presente(_messaggio(profilo={})) is False
    assert profilo_processuale_presente(_messaggio(profilo={"eventi": []})) is False


# ------------------------------------------------- il punteggio, sul caso reale


def _fascicolo(numero_rg="3001", anno_rg="2025", tribunale="TRIBUNALE DI SANTA MARIA CAPUA VETERE"):
    from types import SimpleNamespace

    return SimpleNamespace(
        id="5E864356",
        titolo="Affinito II ricorso c. MIM",
        numero="2026/205",
        numero_rg=numero_rg,
        anno_rg=anno_rg,
        tribunale=tribunale,
        nome_cliente="Affinito Antonio",
        controparte="MIM",
        attore_principale="",
        oggetto="222050 - Retribuzione",
    )


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """Il collegatore con un archivio fascicoli finto: qui si misura il punteggio."""

    import pct.fascicoli as modulo_fascicoli
    from pct.pec_pipeline import PecAuditRepository

    stato = {"fascicoli": [_fascicolo()]}

    class ArchivioFinto:
        def __init__(self, *_a, **_k):
            pass

        def tutti(self, archiviati=False):
            return list(stato["fascicoli"])

    monkeypatch.setattr(modulo_fascicoli, "GestioneFascicoli", ArchivioFinto)
    repo = PecAuditRepository(
        tmp_path / "audit.sqlite",
        tenant_id="studio-prova",
        fascicoli_db_path=tmp_path / "fascicoli.json",
    )
    return repo, stato


def _parsed(mittente=MITTENTE_UFFICIO, *, profilo=None, rg="3001/2025"):
    return {
        "headers": {"from": mittente, "subject": f"POSTA CERTIFICATA: COMUNICAZIONE {rg}/LAV"},
        "fields": {"mittente": {"value": {"name": mittente, "email": "posta-certificata@legalmail.it"}}},
        "body": {"text": f"Comunicazione relativa al procedimento {rg}."},
        "rg_candidates": [rg],
        "procedural_profile": profilo if profilo is not None else {"eventi": [{"evento": "accettazione deposito"}]},
    }


def test_la_pec_dell_ufficio_col_ruolo_del_fascicolo_supera_la_soglia(repository):
    """Il caso che restava in `link_candidates`: adesso si collega."""

    repo, _ = repository

    _, candidati = repo._fascicoli_candidates(_parsed())

    assert candidati, "nessun candidato: il fascicolo non e' stato nemmeno considerato"
    migliore = candidati[0]
    assert "RG citato dall'ufficio giudiziario del fascicolo" in migliore["reasons"]
    assert migliore["score"] >= 0.78
    assert set(migliore["reasons"]) != {"RG coincidente"}


def test_un_ufficio_diverso_non_basta(repository):
    """Stesso numero di ruolo, altro tribunale: resta un indizio."""

    repo, stato = repository
    stato["fascicoli"] = [_fascicolo(tribunale="TRIBUNALE DI PALMI")]

    _, candidati = repo._fascicoli_candidates(_parsed())

    assert candidati[0]["reasons"] == ["RG coincidente"]
    assert candidati[0]["score"] < 0.78


def test_senza_atto_processuale_resta_un_indizio(repository):
    """Una busta senza contenuto processuale non certifica niente."""

    repo, _ = repository

    _, candidati = repo._fascicoli_candidates(_parsed(profilo={}))

    assert candidati[0]["reasons"] == ["RG coincidente"]
    assert candidati[0]["score"] < 0.78


def test_un_mittente_privato_col_ruolo_giusto_resta_un_indizio(repository):
    """E' il punto di tutta la modifica: l'RG nudo non deve bastare."""

    repo, _ = repository

    _, candidati = repo._fascicoli_candidates(_parsed("Mario Rossi <mario@studio.legalmail.it>"))

    assert candidati[0]["reasons"] == ["RG coincidente"]
    assert candidati[0]["score"] < 0.78


def test_un_ruolo_diverso_non_collega_niente(repository):
    repo, _ = repository

    _, candidati = repo._fascicoli_candidates(_parsed(rg="9999/2020"))

    ragioni = candidati[0]["reasons"] if candidati else []
    assert "RG citato dall'ufficio giudiziario del fascicolo" not in ragioni
    assert "RG coincidente" not in ragioni
