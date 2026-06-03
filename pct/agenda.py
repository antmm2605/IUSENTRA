"""
Agenda digitale per studi legali.

Gestione appuntamenti, udienze, scadenze processuali e reminder.
"""

import json
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict, field
from enum import Enum

from pct.ical_import import EventoImportato


class TipoAppuntamento(str, Enum):
    UDIENZA = "UDIENZA"
    CONSULTAZIONE = "CONSULTAZIONE"
    DEPOSITO = "DEPOSITO"
    SCADENZA = "SCADENZA"
    RIUNIONE = "RIUNIONE"
    ALTRO = "ALTRO"


class StatoAppuntamento(str, Enum):
    PROGRAMMATO = "PROGRAMMATO"
    CONFERMATO = "CONFERMATO"
    COMPLETATO = "COMPLETATO"
    ANNULLATO = "ANNULLATO"
    RINVIATO = "RINVIATO"


@dataclass
class Appuntamento:
    """Rappresenta un appuntamento nell'agenda dello studio."""

    id: str
    titolo: str
    tipo: TipoAppuntamento
    data_ora: str                        # ISO 8601: "2024-03-15T10:00:00"
    durata_minuti: int
    luogo: str
    stato: StatoAppuntamento = StatoAppuntamento.PROGRAMMATO
    note: str = ""
    cliente: str = ""
    cf_cliente: str = ""
    id_cliente: str = ""                 # FK → Cliente.id
    procedimento: str = ""               # es. RG 1234/2024
    tribunale: str = ""
    avvocato: str = ""
    reminder_minuti: int = 60            # reminder N minuti prima
    external_uid: str = ""               # UID RFC 5545 per sync esterne
    external_provider: str = ""          # google/outlook/apple/webcal/...
    external_source_url: str = ""        # URL ICS/WebCal sorgente
    external_profile_id: str = ""        # profilo sync interno
    external_organizer: str = ""         # organizzatore originario
    external_rrule: str = ""             # ricorrenza sorgente
    external_hash: str = ""              # impronta semplificata ultimo contenuto
    external_last_sync: str = ""         # ultimo sync riuscito
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def data_ora_dt(self) -> datetime:
        return datetime.fromisoformat(self.data_ora)

    @property
    def fine_dt(self) -> datetime:
        return self.data_ora_dt + timedelta(minutes=self.durata_minuti)

    @property
    def reminder_dt(self) -> datetime:
        return self.data_ora_dt - timedelta(minutes=self.reminder_minuti)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["stato"] = self.stato.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Appuntamento":
        d = dict(d)
        d["tipo"] = TipoAppuntamento(d["tipo"])
        d["stato"] = StatoAppuntamento(d["stato"])
        # rimuovi campi calcolati se presenti
        for k in ("data_ora_dt", "fine_dt", "reminder_dt"):
            d.pop(k, None)
        return cls(**d)


class Agenda:
    """
    Agenda digitale dello studio legale.

    Persiste gli appuntamenti su file JSON locale.
    Supporta ricerca per data, cliente, tipo e stato.
    """

    def __init__(self, db_path: str = "./agenda/appuntamenti.json", studio_db=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._appuntamenti: dict[str, Appuntamento] = {}
        self._carica()

    # ------------------------------------------------------------------ I/O

    def _carica(self) -> None:
        if self._studio_db is not None:
            import json as _json
            try:
                rows = self._studio_db.conn.execute(
                    "SELECT * FROM appuntamenti"
                ).fetchall()
                self._appuntamenti = {}
                for row in rows:
                    d = dict(row)
                    dati = d.get("dati_json")
                    try:
                        payload = _json.loads(dati) if dati else d
                        a = Appuntamento.from_dict(payload)
                        self._appuntamenti[a.id] = a
                    except Exception:
                        pass
            except Exception:
                self._appuntamenti = {}
            return
        from pct import cache as _cache
        dati = _cache.load(self.db_path)
        self._appuntamenti = {k: Appuntamento.from_dict(v) for k, v in dati.items()}

    def _salva(self) -> None:
        if self._studio_db is not None:
            import json as _json

            def _insert(conn, a):
                d = a.to_dict()
                conn.execute(
                    """
                    INSERT INTO appuntamenti
                    (id, tipo, stato, titolo, data_ora, durata_minuti, luogo,
                     descrizione, cliente, cf_cliente, procedimento, tribunale,
                     note, creato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        a.id, a.tipo.value, a.stato.value, a.titolo,
                        a.data_ora, a.durata_minuti, a.luogo,
                        a.note,  # descrizione = note per compatibilità schema
                        a.cliente, a.cf_cliente,
                        a.procedimento, a.tribunale,
                        a.note, a.creato_il,
                        _json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("appuntamenti", list(self._appuntamenti.values()), _insert)
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._appuntamenti.items()})

    # ------------------------------------------------------------------ CRUD

    def aggiungi(
        self,
        titolo: str,
        tipo: TipoAppuntamento,
        data_ora: str,
        durata_minuti: int = 60,
        luogo: str = "",
        allow_overlap: bool = False,
        **kwargs,
    ) -> Appuntamento:
        """
        Aggiunge un nuovo appuntamento.

        Args:
            titolo: Titolo dell'appuntamento
            tipo: Tipo (UDIENZA, CONSULTAZIONE, ...)
            data_ora: Data e ora ISO 8601 (es. "2024-03-15T10:00:00")
            durata_minuti: Durata prevista in minuti
            luogo: Luogo dell'appuntamento
            **kwargs: Campi opzionali (cliente, procedimento, note, ...)

        Returns:
            Appuntamento creato
        """
        # Controlla sovrapposizioni
        if not allow_overlap:
            sovrapposizioni = self._controlla_sovrapposizioni(data_ora, durata_minuti)
            if sovrapposizioni:
                titoli = ", ".join(a.titolo for a in sovrapposizioni)
                raise ValueError(
                    f"Sovrapposizione con appuntamento/i esistente/i: {titoli}"
                )

        app = Appuntamento(
            id=uuid.uuid4().hex[:8].upper(),
            titolo=titolo,
            tipo=tipo,
            data_ora=data_ora,
            durata_minuti=durata_minuti,
            luogo=luogo,
            **kwargs,
        )
        self._appuntamenti[app.id] = app
        self._salva()
        return app

    def modifica(self, id_app: str, **campi) -> Appuntamento:
        """Modifica i campi di un appuntamento esistente."""
        app = self._get_o_errore(id_app)
        for k, v in campi.items():
            if hasattr(app, k):
                setattr(app, k, v)
        app.modificato_il = datetime.now().isoformat()
        self._salva()
        return app

    def elimina(self, id_app: str) -> None:
        """Elimina un appuntamento."""
        self._get_o_errore(id_app)
        del self._appuntamenti[id_app]
        self._salva()

    def cambia_stato(self, id_app: str, stato: StatoAppuntamento) -> Appuntamento:
        """Aggiorna lo stato di un appuntamento."""
        return self.modifica(id_app, stato=stato)

    # ------------------------------------------------------------------ Query

    def get(self, id_app: str) -> Optional[Appuntamento]:
        return self._appuntamenti.get(id_app)

    def trova_per_uid_esterno(
        self,
        uid: str,
        *,
        provider: str = "",
        profile_id: str = "",
    ) -> Optional[Appuntamento]:
        uid = (uid or "").strip()
        if not uid:
            return None
        candidati = [
            app for app in self._appuntamenti.values()
            if (app.external_uid or "").strip() == uid
        ]
        if profile_id:
            match = next(
                (app for app in candidati if (app.external_profile_id or "") == profile_id),
                None,
            )
            if match:
                return match
        if provider:
            match = next(
                (app for app in candidati if (app.external_provider or "") == provider),
                None,
            )
            if match:
                return match
        return candidati[0] if candidati else None

    def tutti(self) -> List[Appuntamento]:
        return sorted(self._appuntamenti.values(), key=lambda a: a.data_ora)

    def per_giorno(self, giorno: date) -> List[Appuntamento]:
        """Appuntamenti di un giorno specifico."""
        return [
            a for a in self.tutti()
            if a.data_ora_dt.date() == giorno
        ]

    def per_settimana(self, inizio: date) -> List[Appuntamento]:
        """Appuntamenti della settimana che inizia da 'inizio'."""
        fine = inizio + timedelta(days=7)
        return [
            a for a in self.tutti()
            if inizio <= a.data_ora_dt.date() < fine
        ]

    def per_mese(self, anno: int, mese: int) -> List[Appuntamento]:
        return [
            a for a in self.tutti()
            if a.data_ora_dt.year == anno and a.data_ora_dt.month == mese
        ]

    def per_cliente(self, id_cliente: str) -> List[Appuntamento]:
        """Appuntamenti di un cliente per ID (ordinati per data desc)."""
        return sorted(
            [a for a in self._appuntamenti.values() if a.id_cliente == id_cliente],
            key=lambda a: a.data_ora,
            reverse=True,
        )

    def cerca(
        self,
        testo: Optional[str] = None,
        tipo: Optional[TipoAppuntamento] = None,
        stato: Optional[StatoAppuntamento] = None,
        cliente: Optional[str] = None,
        id_cliente: Optional[str] = None,
        da: Optional[date] = None,
        a: Optional[date] = None,
    ) -> List[Appuntamento]:
        """Ricerca appuntamenti con filtri multipli."""
        risultati = self.tutti()

        if testo:
            t = testo.lower()
            risultati = [
                a for a in risultati
                if t in a.titolo.lower()
                or t in a.note.lower()
                or t in a.cliente.lower()
                or t in a.procedimento.lower()
            ]
        if tipo:
            risultati = [a for a in risultati if a.tipo == tipo]
        if stato:
            risultati = [a for a in risultati if a.stato == stato]
        if cliente:
            risultati = [
                a for a in risultati
                if cliente.lower() in a.cliente.lower()
            ]
        if id_cliente:
            risultati = [a for a in risultati if a.id_cliente == id_cliente]
        if da:
            risultati = [a for a in risultati if a.data_ora_dt.date() >= da]
        if a:
            risultati = [a for a in risultati if a.data_ora_dt.date() <= a]

        return risultati

    def prossimi_reminder(self, entro_minuti: int = 60) -> List[Appuntamento]:
        """
        Restituisce gli appuntamenti il cui reminder scade entro N minuti.
        Utile per sistemi di notifica.
        """
        adesso = datetime.now()
        soglia = adesso + timedelta(minutes=entro_minuti)
        return [
            a for a in self.tutti()
            if a.stato == StatoAppuntamento.PROGRAMMATO
            and adesso <= a.reminder_dt <= soglia
        ]

    def scadenze_oggi(self) -> List[Appuntamento]:
        """Appuntamenti di oggi non ancora completati."""
        oggi = date.today()
        return [
            a for a in self.per_giorno(oggi)
            if a.stato not in (StatoAppuntamento.COMPLETATO, StatoAppuntamento.ANNULLATO)
        ]

    # ------------------------------------------------------------------ Utils

    def _get_o_errore(self, id_app: str) -> Appuntamento:
        app = self._appuntamenti.get(id_app)
        if not app:
            raise KeyError(f"Appuntamento '{id_app}' non trovato.")
        return app

    def _controlla_sovrapposizioni(
        self, data_ora: str, durata_minuti: int, exclude_id: str = ""
    ) -> List[Appuntamento]:
        """Restituisce appuntamenti che si sovrappongono con la finestra data."""
        nuovo_inizio = datetime.fromisoformat(data_ora)
        nuovo_fine = nuovo_inizio + timedelta(minutes=durata_minuti)

        sovrapposti = []
        for a in self._appuntamenti.values():
            if exclude_id and a.id == exclude_id:
                continue
            if a.stato in (StatoAppuntamento.ANNULLATO, StatoAppuntamento.COMPLETATO):
                continue
            if a.data_ora_dt < nuovo_fine and a.fine_dt > nuovo_inizio:
                sovrapposti.append(a)
        return sovrapposti

    def _normalizza_tipo_importato(self, tipo: TipoAppuntamento | str | None) -> TipoAppuntamento:
        if isinstance(tipo, TipoAppuntamento):
            return tipo
        try:
            return TipoAppuntamento(str(tipo or TipoAppuntamento.ALTRO.value))
        except ValueError:
            return TipoAppuntamento.ALTRO

    def _note_da_evento_importato(
        self,
        evento: EventoImportato,
        *,
        provider: str = "",
        source_url: str = "",
    ) -> str:
        parts: List[str] = []
        if evento.descrizione:
            parts.append(evento.descrizione.strip())
        if evento.organizzatore:
            parts.append(f"Organizzatore: {evento.organizzatore.strip()}")
        if evento.rrule:
            parts.append("Evento ricorrente: il gestionale sincronizza l'occorrenza presente nel feed.")
        provider_label = (provider or "Calendario esterno").replace("_", " ").replace("-", " ").strip().title()
        parts.append(f"Sincronizzato da: {provider_label}")
        if source_url:
            parts.append(f"Sorgente: {source_url}")
        if evento.uid:
            parts.append(f"UID esterno: {evento.uid}")
        return "\n".join(part for part in parts if part)

    def _payload_da_evento_importato(
        self,
        evento: EventoImportato,
        *,
        provider: str = "",
        source_url: str = "",
        profile_id: str = "",
        default_tipo: TipoAppuntamento | str | None = None,
        reminder_minuti: int = 60,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        event_uid = (evento.uid or "").strip()
        if evento.tutto_giorno:
            data_ora = f"{evento.data_ora}T09:00:00"
            durata = min(max(int(evento.durata_minuti or 1440), 60), 1440)
        else:
            data_ora = evento.data_ora
            durata = max(int(evento.durata_minuti or 60), 1)
        if not event_uid:
            event_uid = "|".join(
                [
                    (provider or "").strip(),
                    (profile_id or "").strip(),
                    (evento.titolo or "").strip(),
                    data_ora,
                    (evento.luogo or "").strip(),
                ]
            )

        stato = StatoAppuntamento.ANNULLATO if evento.stato_ical == "CANCELLED" else StatoAppuntamento.PROGRAMMATO
        external_hash = "|".join(
            [
                evento.titolo or "",
                data_ora,
                str(durata),
                evento.luogo or "",
                evento.descrizione or "",
                evento.stato_ical or "",
                evento.organizzatore or "",
                evento.rrule or "",
            ]
        )
        return {
            "titolo": (evento.titolo or "Evento calendario").strip(),
            "tipo": self._normalizza_tipo_importato(default_tipo),
            "data_ora": data_ora,
            "durata_minuti": durata,
            "luogo": (evento.luogo or "").strip(),
            "stato": stato,
            "note": self._note_da_evento_importato(evento, provider=provider, source_url=source_url),
            "reminder_minuti": max(int(reminder_minuti or 60), 0),
            "external_uid": event_uid,
            "external_provider": (provider or "").strip(),
            "external_source_url": (source_url or "").strip(),
            "external_profile_id": (profile_id or "").strip(),
            "external_organizer": (evento.organizzatore or "").strip(),
            "external_rrule": (evento.rrule or "").strip(),
            "external_hash": external_hash,
            "external_last_sync": current_time.isoformat(),
        }

    def upsert_da_evento_importato(
        self,
        evento: EventoImportato,
        *,
        provider: str = "",
        source_url: str = "",
        profile_id: str = "",
        default_tipo: TipoAppuntamento | str | None = None,
        reminder_minuti: int = 60,
        allow_overlap: bool = False,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        payload = self._payload_da_evento_importato(
            evento,
            provider=provider,
            source_url=source_url,
            profile_id=profile_id,
            default_tipo=default_tipo,
            reminder_minuti=reminder_minuti,
            now=now,
        )
        esistente = self.trova_per_uid_esterno(
            evento.uid,
            provider=provider,
            profile_id=profile_id,
        )

        if esistente:
            if not allow_overlap:
                conflitti = self._controlla_sovrapposizioni(
                    payload["data_ora"],
                    int(payload["durata_minuti"]),
                    exclude_id=esistente.id,
                )
                if conflitti:
                    return {
                        "outcome": "conflict",
                        "appuntamento": esistente,
                        "message": ", ".join(a.titolo for a in conflitti),
                    }
            campi_verifica = (
                "titolo",
                "tipo",
                "data_ora",
                "durata_minuti",
                "luogo",
                "stato",
                "note",
                "reminder_minuti",
                "external_source_url",
                "external_profile_id",
                "external_organizer",
                "external_rrule",
                "external_hash",
            )
            if all(getattr(esistente, key) == payload[key] for key in campi_verifica):
                return {
                    "outcome": "skipped",
                    "appuntamento": esistente,
                    "message": "Evento gia allineato.",
                }
            aggiornato = self.modifica(esistente.id, **payload)
            return {
                "outcome": "updated",
                "appuntamento": aggiornato,
                "message": "Evento esterno aggiornato.",
            }

        if not allow_overlap:
            conflitti = self._controlla_sovrapposizioni(
                payload["data_ora"],
                int(payload["durata_minuti"]),
            )
            if conflitti:
                return {
                    "outcome": "conflict",
                    "appuntamento": None,
                    "message": ", ".join(a.titolo for a in conflitti),
                }

        creato = self.aggiungi(
            titolo=payload.pop("titolo"),
            tipo=payload.pop("tipo"),
            data_ora=payload.pop("data_ora"),
            durata_minuti=payload.pop("durata_minuti"),
            luogo=payload.pop("luogo"),
            allow_overlap=allow_overlap,
            **payload,
        )
        return {
            "outcome": "created",
            "appuntamento": creato,
            "message": "Evento esterno creato.",
        }

    def statistiche(self) -> dict:
        """Riepilogo statistiche agenda."""
        tutti = self.tutti()
        oggi = date.today()
        return {
            "totale": len(tutti),
            "oggi": len(self.per_giorno(oggi)),
            "questa_settimana": len(self.per_settimana(oggi)),
            "questo_mese": len(self.per_mese(oggi.year, oggi.month)),
            "per_tipo": {
                t.value: sum(1 for a in tutti if a.tipo == t)
                for t in TipoAppuntamento
            },
            "per_stato": {
                s.value: sum(1 for a in tutti if a.stato == s)
                for s in StatoAppuntamento
            },
        }
