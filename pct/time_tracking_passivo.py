"""Time tracking passivo: proposte di timesheet dal segnale audit.

Il gestionale registra gia' ogni azione rilevante (``EventoAudit``: apertura
fascicoli e documenti, modifiche, depositi). Questo modulo raggruppa quegli
eventi in sessioni di lavoro per utente e fascicolo e le trasforma in
proposte di voce timesheet in stato BOZZA: nessun minuto diventa mai
fatturabile da solo — l'avvocato conferma, e solo allora nasce la
``VoceTimesheet`` (origine "tracking_passivo") agganciabile ai compensi a
tempo ex art. 22-bis (``pct/compensi_a_tempo.py``, D.M. 55/2014).

La documentazione dell'attivita' svolta e' anche la prova richiesta dalla
disciplina dell'equo compenso: ogni proposta conserva il conteggio e i tipi
delle operazioni rilevate, con orari di inizio e fine.

Fail-closed: idempotente per (utente, fascicolo, finestra); le sessioni sotto
la durata minima non generano proposte; le proposte scartate non si
ripresentano.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Prassi configurabili dello studio (non norme): finestra di inattivita' che
# chiude una sessione e durata minima perche' valga una proposta.
GAP_SESSIONE_MINUTI = 15
DURATA_MINIMA_MINUTI = 5
# Un solo evento non misura una durata: si propone l'unita' minima di prassi
# forense (6 minuti = 0,1 ora), sempre soggetta a conferma.
DURATA_EVENTO_SINGOLO_MINUTI = 6

# Azioni audit considerate lavoro sul fascicolo (prefissi).
_AZIONI_RILEVANTI = (
    "fascicoli.",
    "documenti.",
    "deposito.",
    "polisweb.",
    "scadenziario.",
    "template_atti.",
    "editor.",
)

_ETICHETTE_AZIONE = {
    "fascicoli": "consultazione fascicolo",
    "documenti": "lavoro sui documenti",
    "deposito": "deposito telematico",
    "polisweb": "consultazione registri",
    "scadenziario": "gestione scadenze",
    "template_atti": "redazione atti",
    "editor": "redazione atti",
}


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or "")[:26])
    except ValueError:
        return None


@dataclass
class SessioneLavoro:
    """Sessione continuativa di lavoro di un utente su un fascicolo."""

    utente_id: str
    username: str
    fascicolo_id: str
    inizio: str  # ISO
    fine: str  # ISO
    eventi: int = 0
    categorie: list[str] = field(default_factory=list)

    @property
    def durata_minuti(self) -> int:
        inizio = _parse_ts(self.inizio)
        fine = _parse_ts(self.fine)
        if inizio is None or fine is None:
            return 0
        minuti = int((fine - inizio).total_seconds() // 60)
        return max(minuti, DURATA_EVENTO_SINGOLO_MINUTI)

    def chiave(self) -> str:
        """Chiave idempotente: stessa finestra → stessa proposta, mai doppioni."""

        return f"{self.utente_id}|{self.fascicolo_id}|{self.inizio[:16]}"

    def descrizione(self) -> str:
        attivita = ", ".join(dict.fromkeys(self.categorie)) or "attivita' sul fascicolo"
        ora_inizio = self.inizio[11:16] or "?"
        ora_fine = self.fine[11:16] or "?"
        return (
            f"Attivita' rilevata automaticamente ({self.eventi} operazioni: {attivita}) "
            f"dalle {ora_inizio} alle {ora_fine}"
        )


def _azione_rilevante(azione: str) -> str:
    """Ritorna l'etichetta della categoria se l'azione conta come lavoro."""

    pulita = str(azione or "").strip().lower()
    for prefisso in _AZIONI_RILEVANTI:
        if pulita.startswith(prefisso):
            return _ETICHETTE_AZIONE.get(prefisso.rstrip("."), prefisso.rstrip("."))
    return ""


def sessioni_da_eventi(
    eventi: list[Any],
    *,
    gap_minuti: int = GAP_SESSIONE_MINUTI,
    durata_minima_minuti: int = DURATA_MINIMA_MINUTI,
) -> list[SessioneLavoro]:
    """Raggruppa gli eventi audit in sessioni per (utente, fascicolo).

    Un buco di inattivita' oltre ``gap_minuti`` chiude la sessione. Le sessioni
    con un solo evento o durata sotto il minimo valgono l'unita' minima solo se
    hanno almeno 2 operazioni; un'operazione isolata non genera proposte
    (fail-closed contro il rumore).
    """

    per_gruppo: dict[tuple[str, str], list[Any]] = {}
    for evento in eventi or []:
        if str(getattr(evento, "esito", "OK") or "OK") != "OK":
            continue
        if str(getattr(evento, "risorsa_tipo", "") or "") != "fascicolo":
            continue
        fascicolo_id = str(getattr(evento, "risorsa_id", "") or "").strip()
        utente_id = str(getattr(evento, "id_utente", "") or "").strip()
        if not fascicolo_id or not utente_id:
            continue
        if not _azione_rilevante(getattr(evento, "azione", "")):
            continue
        if _parse_ts(getattr(evento, "timestamp", "")) is None:
            continue
        per_gruppo.setdefault((utente_id, fascicolo_id), []).append(evento)

    sessioni: list[SessioneLavoro] = []
    for (utente_id, fascicolo_id), gruppo in per_gruppo.items():
        ordinati = sorted(gruppo, key=lambda e: str(getattr(e, "timestamp", "")))
        corrente: SessioneLavoro | None = None
        precedente: datetime | None = None
        for evento in ordinati:
            ts = _parse_ts(getattr(evento, "timestamp", ""))
            categoria = _azione_rilevante(getattr(evento, "azione", ""))
            if corrente is None or precedente is None or (ts - precedente).total_seconds() > gap_minuti * 60:
                if corrente is not None:
                    sessioni.append(corrente)
                corrente = SessioneLavoro(
                    utente_id=utente_id,
                    username=str(getattr(evento, "username", "") or ""),
                    fascicolo_id=fascicolo_id,
                    inizio=str(getattr(evento, "timestamp", "")),
                    fine=str(getattr(evento, "timestamp", "")),
                )
            corrente.fine = str(getattr(evento, "timestamp", ""))
            corrente.eventi += 1
            if categoria:
                corrente.categorie.append(categoria)
            precedente = ts
        if corrente is not None:
            sessioni.append(corrente)

    valide = []
    for sessione in sessioni:
        if sessione.eventi < 2:
            continue  # operazione isolata: niente proposta
        if sessione.durata_minuti < durata_minima_minuti:
            continue
        valide.append(sessione)
    valide.sort(key=lambda s: s.inizio)
    return valide


class StatoProposta:
    BOZZA = "BOZZA"
    CONFERMATA = "CONFERMATA"
    SCARTATA = "SCARTATA"


class GestioneTrackingPassivo:
    """Repository tenant-aware delle proposte di time tracking passivo (JSON)."""

    def __init__(self, db_path: str = "./timesheet/tracking_passivo.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._proposte: dict[str, dict[str, Any]] = {}
        self._carica()

    def _carica(self) -> None:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._proposte = {k: v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError):
            self._proposte = {}

    def _salva(self) -> None:
        self.db_path.write_text(
            json.dumps(self._proposte, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ genera
    def genera_da_eventi(self, eventi: list[Any]) -> list[dict[str, Any]]:
        """Crea proposte BOZZA dalle sessioni rilevate. Idempotente per chiave."""

        chiavi_note = {str(p.get("chiave") or "") for p in self._proposte.values()}
        nuove: list[dict[str, Any]] = []
        for sessione in sessioni_da_eventi(eventi):
            chiave = sessione.chiave()
            if chiave in chiavi_note:
                continue
            proposta = {
                "id": uuid.uuid4().hex[:12].upper(),
                "chiave": chiave,
                "stato": StatoProposta.BOZZA,
                "utente_id": sessione.utente_id,
                "username": sessione.username,
                "fascicolo_id": sessione.fascicolo_id,
                "inizio": sessione.inizio,
                "fine": sessione.fine,
                "minuti": sessione.durata_minuti,
                "eventi": sessione.eventi,
                "descrizione": sessione.descrizione(),
                "creato_il": datetime.now().isoformat(timespec="seconds"),
            }
            self._proposte[proposta["id"]] = proposta
            chiavi_note.add(chiave)
            nuove.append(proposta)
        if nuove:
            self._salva()
        return nuove

    # ------------------------------------------------------------------ coda
    def bozze(self, *, utente_id: str = "") -> list[dict[str, Any]]:
        rows = [
            dict(p) for p in self._proposte.values()
            if p.get("stato") == StatoProposta.BOZZA
            and (not utente_id or p.get("utente_id") == utente_id)
        ]
        rows.sort(key=lambda p: str(p.get("inizio") or ""), reverse=True)
        return rows

    def get(self, proposta_id: str) -> dict[str, Any] | None:
        row = self._proposte.get(proposta_id)
        return dict(row) if row else None

    # ------------------------------------------------------------------ esiti
    def conferma(
        self,
        proposta_id: str,
        *,
        crea_voce_timesheet: Callable[[dict[str, Any]], Any],
        minuti: int | None = None,
        descrizione: str = "",
    ) -> dict[str, Any]:
        """Conferma dell'avvocato: crea la voce timesheet e chiude la proposta.

        ``crea_voce_timesheet`` riceve il payload della voce (fascicolo,
        minuti, descrizione, origine) e ritorna la voce creata: la persistenza
        resta nel dominio timesheet. L'avvocato puo' correggere minuti e
        descrizione prima della conferma.
        """

        proposta = self._proposte.get(proposta_id)
        if proposta is None:
            raise KeyError(f"Proposta {proposta_id} non trovata.")
        if proposta.get("stato") != StatoProposta.BOZZA:
            raise ValueError("Proposta gia' definita: solo le bozze si confermano.")
        minuti_finali = int(minuti if minuti is not None else proposta.get("minuti") or 0)
        if minuti_finali <= 0:
            raise ValueError("Minuti non validi: la voce timesheet richiede una durata positiva.")
        voce = crea_voce_timesheet(
            {
                "id_fascicolo": proposta.get("fascicolo_id") or "",
                "id_utente": proposta.get("utente_id") or "",
                "username": proposta.get("username") or "",
                "data_attivita": str(proposta.get("inizio") or "")[:10],
                "minuti": minuti_finali,
                "descrizione": descrizione.strip() or str(proposta.get("descrizione") or ""),
                "origine": "tracking_passivo",
                "note": f"Proposta automatica {proposta_id} confermata dall'avvocato.",
            }
        )
        voce_id = voce.get("id", "") if isinstance(voce, dict) else getattr(voce, "id", "")
        proposta["stato"] = StatoProposta.CONFERMATA
        proposta["minuti"] = minuti_finali
        proposta["voce_timesheet_id"] = str(voce_id or "")
        proposta["definito_il"] = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return dict(proposta)

    def scarta(self, proposta_id: str, *, motivo: str = "") -> dict[str, Any]:
        proposta = self._proposte.get(proposta_id)
        if proposta is None:
            raise KeyError(f"Proposta {proposta_id} non trovata.")
        proposta["stato"] = StatoProposta.SCARTATA
        proposta["motivo_scarto"] = motivo.strip()
        proposta["definito_il"] = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return dict(proposta)
