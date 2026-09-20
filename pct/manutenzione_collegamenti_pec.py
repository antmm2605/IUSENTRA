"""Ricalcola il collegamento delle PEC rimaste senza fascicolo.

Dalla 2.337.0 una PEC che cita il numero di ruolo del fascicolo si collega
quando arriva dall'ufficio giudiziario di quel procedimento e porta un atto.
La regola vale pero' per i messaggi che vengono lavorati da quel momento: il
collegamento delle PEC gia' passate era stato deciso con la regola vecchia e
salvato, e nessuno ci ripassa sopra da solo.

Qui si ripassa. `esamina` legge e basta: usa la stessa funzione di decisione
del collegatore e dice quanti messaggi si collegherebbero, senza scrivere
niente. `ricollega` esegue davvero, sugli stessi messaggi.

La logica sta qui, non nella rotta: la console e la riga di comando devono
fare esattamente la stessa cosa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

#: Gli stati in cui resta una PEC che non e' stata collegata a un fascicolo.
STATI_DA_RIVEDERE = ("link_candidates",)


@dataclass
class EsitoStudio:
    """Cosa succederebbe, o cos'e' successo, ai messaggi di uno studio."""

    studio: str
    esaminati: int = 0
    gia_collegati: int = 0
    collegabili: int = 0
    ricollegati: int = 0
    senza_candidato: int = 0
    solo_rg: int = 0
    errore: str = ""
    esempi: list[dict[str, Any]] = field(default_factory=list)

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "studio": self.studio,
            "esaminati": self.esaminati,
            "gia_collegati": self.gia_collegati,
            "collegabili": self.collegabili,
            "ricollegati": self.ricollegati,
            "senza_candidato": self.senza_candidato,
            "solo_rg": self.solo_rg,
            "errore": self.errore,
            "esempi": self.esempi[:5],
        }


def messaggi_da_rivedere(repo: Any) -> list[str]:
    """Gli id dei messaggi fermi senza collegamento, dal piu' recente."""
    segnaposti = ",".join("?" for _ in STATI_DA_RIVEDERE)
    with repo.connect() as conn:
        righe = conn.execute(
            f"SELECT id FROM pec_messages WHERE tenant_id = ? AND status IN ({segnaposti}) "
            "AND COALESCE(linked_fascicolo_id,'') = '' ORDER BY received_at DESC",
            (repo.tenant_id, *STATI_DA_RIVEDERE),
        ).fetchall()
    return [str(riga["id"]) for riga in righe]


def _decisione_per(repo: Any, message_id: str) -> dict[str, Any] | None:
    """Cosa deciderebbe il collegatore adesso, senza scrivere niente."""
    from pct.pec_pipeline import decidi_collegamento

    with repo.connect() as conn:
        riga = repo.latest_parsed_row(conn, message_id)
        if riga is None:
            return None
        parsed = json.loads(riga["parsed_json"])
    _, candidati = repo._fascicoli_candidates(parsed)
    return decidi_collegamento(candidati)


def esamina(repo: Any, *, studio: str = "", limite: int = 0) -> EsitoStudio:
    """Quanti messaggi si collegherebbero con la regola di oggi. Non scrive."""
    esito = EsitoStudio(studio=studio or getattr(repo, "tenant_id", "") or "default")
    try:
        identificativi = messaggi_da_rivedere(repo)
        if limite > 0:
            identificativi = identificativi[:limite]
        for message_id in identificativi:
            esito.esaminati += 1
            try:
                decisione = _decisione_per(repo, message_id)
            except Exception as exc:  # un messaggio illeggibile non ferma gli altri
                esito.esempi.append({"messaggio": message_id, "errore": str(exc)[:160]})
                continue
            if decisione is None:
                esito.senza_candidato += 1
                continue
            if decisione["fascicolo_id"]:
                esito.collegabili += 1
                esito.esempi.append(
                    {
                        "messaggio": message_id,
                        "fascicolo": decisione["fascicolo_id"],
                        "punteggio": round(decisione["score"], 3),
                        "motivi": decisione["reasons"],
                    }
                )
            elif decisione["rg_only"]:
                esito.solo_rg += 1
            else:
                esito.senza_candidato += 1
    except Exception as exc:
        esito.errore = str(exc)
    return esito


def ricollega(repo: Any, *, studio: str = "", limite: int = 0) -> EsitoStudio:
    """Rifa' il collegamento sui messaggi che la regola di oggi collegherebbe.

    Si tocca solo chi risulta collegabile: su un messaggio che resterebbe
    dov'e' non si riscrive niente, cosi' l'operazione si puo' ripetere senza
    lasciare tracce inutili nel registro dei collegamenti.
    """
    esito = esamina(repo, studio=studio, limite=limite)
    if esito.errore or not esito.collegabili:
        return esito
    identificativi = messaggi_da_rivedere(repo)
    if limite > 0:
        identificativi = identificativi[:limite]
    da_fare = []
    for message_id in identificativi:
        try:
            decisione = _decisione_per(repo, message_id)
        except Exception:
            continue
        if decisione and decisione["fascicolo_id"]:
            da_fare.append(message_id)
    for message_id in da_fare:
        try:
            risultato = repo.link_fascicolo(message_id, actor="manutenzione collegamenti")
            if str((risultato or {}).get("fascicolo_id") or ""):
                esito.ricollegati += 1
        except Exception as exc:
            esito.esempi.append({"messaggio": message_id, "errore": str(exc)[:160]})
    return esito


def _riepilogo(esiti: list[EsitoStudio], *, applicato: bool) -> dict[str, Any]:
    esaminati = sum(e.esaminati for e in esiti)
    collegabili = sum(e.collegabili for e in esiti)
    ricollegati = sum(e.ricollegati for e in esiti)
    errori = [e.errore for e in esiti if e.errore]
    if applicato:
        messaggio = f"Collegate {ricollegati} PEC su {esaminati} esaminate."
    else:
        messaggio = (
            f"{collegabili} PEC su {esaminati} si collegherebbero con la regola di oggi. "
            "Nessuna modifica eseguita."
        )
    return {
        "ok": not errori,
        "ricollegamento_eseguito": bool(applicato),
        "esaminati": esaminati,
        "collegabili": collegabili,
        "ricollegati": ricollegati,
        "solo_rg": sum(e.solo_rg for e in esiti),
        "senza_candidato": sum(e.senza_candidato for e in esiti),
        "errori": errori,
        "studi": [e.come_dizionario() for e in esiti],
        "messaggio": messaggio,
    }


__all__ = [
    "EsitoStudio",
    "STATI_DA_RIVEDERE",
    "esamina",
    "messaggi_da_rivedere",
    "ricollega",
]
