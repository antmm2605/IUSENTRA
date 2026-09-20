"""Ricalcolo dei collegamenti PEC rimasti indietro.

La regola nuova — RG del fascicolo, mittente che e' quell'ufficio, atto del
procedimento — vale per i messaggi lavorati da quando e' entrata. Le PEC gia'
passate conservano il collegamento deciso con la regola vecchia, e nessuno ci
ripassa sopra da solo: sul fascicolo 5E864356 erano tredici.

Qui si verifica che l'analisi non scriva e che prometta esattamente quello
che l'applicazione poi fa: e' su quel numero che si decide se toccare dei
dati da cui dipendono dei termini.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from pct.manutenzione_collegamenti_pec import esamina, messaggi_da_rivedere, ricollega
from pct.pec_pipeline import decidi_collegamento

MITTENTE_UFFICIO = (
    '"Per conto di: tribunale.santamariacapuavetere@civile.ptel.giustiziacert.it"'
    " <posta-certificata@legalmail.it>"
)


def _parsed(rg="3001/2025", mittente=MITTENTE_UFFICIO, *, atto=True):
    return {
        "headers": {"from": mittente, "subject": f"POSTA CERTIFICATA: COMUNICAZIONE {rg}/LAV"},
        "fields": {"mittente": {"value": {"name": mittente, "email": "posta-certificata@legalmail.it"}}},
        "body": {"text": f"Procedimento {rg}."},
        "rg_candidates": [rg],
        "procedural_profile": {"eventi": [{"evento": "accettazione deposito"}]} if atto else {},
    }


class RepoFinto:
    """Il minimo che la manutenzione usa: la coda, il parsed e il collegamento."""

    def __init__(self, messaggi, *, fascicolo_per=None):
        self.tenant_id = "studio-prova"
        self.messaggi = dict(messaggi)
        self.collegati: dict[str, str] = {}
        self._fascicolo_per = fascicolo_per or {}

    # -- superficie usata da manutenzione_collegamenti_pec --
    def connect(self):
        repo = self

        class Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *_a):
                return False

            def execute(self_inner, _sql, params=()):
                rimasti = [k for k in repo.messaggi if k not in repo.collegati]
                return SimpleNamespace(fetchall=lambda: [{"id": k} for k in rimasti])

        return Conn()

    def latest_parsed_row(self, _conn, message_id):
        parsed = self.messaggi.get(message_id)
        if parsed is None:
            return None
        return {"id": f"v-{message_id}", "parsed_json": json.dumps(parsed)}

    def _fascicoli_candidates(self, parsed):
        rg = (parsed.get("rg_candidates") or [""])[0]
        candidato = self._fascicolo_per.get(rg)
        return {}, ([candidato] if candidato else [])

    def link_fascicolo(self, message_id, *, actor=""):
        parsed = self.messaggi[message_id]
        _, candidati = self._fascicoli_candidates(parsed)
        decisione = decidi_collegamento(candidati)
        if decisione["fascicolo_id"]:
            self.collegati[message_id] = decisione["fascicolo_id"]
        return {"fascicolo_id": decisione["fascicolo_id"], "status": decisione["status"]}


CERTIFICATO = {
    "id": "5E864356",
    "score": 0.92,
    "reasons": ["RG citato dall'ufficio giudiziario del fascicolo"],
}
SOLO_RG = {"id": "5E864356", "score": 0.58, "reasons": ["RG coincidente"]}


def _repo_collegabili(quanti=3):
    return RepoFinto(
        {f"pec_{i}": _parsed() for i in range(quanti)},
        fascicolo_per={"3001/2025": CERTIFICATO},
    )


# ------------------------------------------------------------------ analisi


def test_l_analisi_conta_i_messaggi_collegabili():
    esito = esamina(_repo_collegabili(3))

    assert esito.esaminati == 3
    assert esito.collegabili == 3
    assert esito.ricollegati == 0


def test_l_analisi_non_collega_niente():
    """Deve poter essere letta senza conseguenze."""

    repo = _repo_collegabili(3)

    esamina(repo)

    assert repo.collegati == {}


def test_il_solo_numero_di_ruolo_resta_fuori():
    repo = RepoFinto({"pec_1": _parsed()}, fascicolo_per={"3001/2025": SOLO_RG})

    esito = esamina(repo)

    assert esito.collegabili == 0
    assert esito.solo_rg == 1


def test_senza_candidati_lo_dice():
    repo = RepoFinto({"pec_1": _parsed(rg="9999/1999")}, fascicolo_per={})

    esito = esamina(repo)

    assert esito.collegabili == 0
    assert esito.senza_candidato == 1


def test_un_messaggio_illeggibile_non_ferma_gli_altri():
    repo = _repo_collegabili(2)
    repo.messaggi["pec_rotto"] = None

    esito = esamina(repo)

    assert esito.esaminati == 3
    assert esito.collegabili == 2


# ------------------------------------------------------------- applicazione


def test_l_applicazione_collega_quello_che_l_analisi_aveva_promesso():
    """La promessa e l'azione devono venire dalla stessa regola."""

    repo = _repo_collegabili(3)
    promessi = esamina(repo).collegabili

    esito = ricollega(repo)

    assert esito.ricollegati == promessi == 3
    assert set(repo.collegati) == {"pec_0", "pec_1", "pec_2"}


def test_non_tocca_i_messaggi_che_resterebbero_dove_sono():
    repo = RepoFinto(
        {"pec_buono": _parsed(), "pec_debole": _parsed(rg="7777/2020")},
        fascicolo_per={"3001/2025": CERTIFICATO, "7777/2020": SOLO_RG},
    )

    ricollega(repo)

    assert set(repo.collegati) == {"pec_buono"}


def test_rieseguire_non_ricollega_due_volte():
    repo = _repo_collegabili(2)
    ricollega(repo)

    assert ricollega(repo).ricollegati == 0


def test_senza_niente_da_fare_non_scrive():
    repo = RepoFinto({"pec_1": _parsed()}, fascicolo_per={"3001/2025": SOLO_RG})

    esito = ricollega(repo)

    assert esito.ricollegati == 0
    assert repo.collegati == {}


def test_il_limite_restringe_il_lavoro():
    repo = _repo_collegabili(5)

    assert ricollega(repo, limite=2).ricollegati == 2


def test_la_coda_elenca_solo_i_messaggi_senza_fascicolo():
    repo = _repo_collegabili(3)
    ricollega(repo, limite=1)

    assert len(messaggi_da_rivedere(repo)) == 2


@pytest.mark.parametrize("quanti", [0, 1, 7])
def test_il_conteggio_regge_su_code_di_misure_diverse(quanti):
    esito = esamina(_repo_collegabili(quanti))

    assert esito.esaminati == quanti
    assert esito.collegabili == quanti
