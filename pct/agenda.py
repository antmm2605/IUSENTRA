"""
Agenda digitale per studi legali.

Gestione appuntamenti, udienze, scadenze processuali e reminder.
"""

import json
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict, field
from enum import Enum


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
    procedimento: str = ""               # es. RG 1234/2024
    tribunale: str = ""
    avvocato: str = ""
    reminder_minuti: int = 60            # reminder N minuti prima
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

    def __init__(self, db_path: str = "./agenda/appuntamenti.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._appuntamenti: dict[str, Appuntamento] = {}
        self._carica()

    # ------------------------------------------------------------------ I/O

    def _carica(self) -> None:
        if self.db_path.exists():
            with open(self.db_path, encoding="utf-8") as f:
                dati = json.load(f)
            self._appuntamenti = {
                k: Appuntamento.from_dict(v) for k, v in dati.items()
            }

    def _salva(self) -> None:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._appuntamenti.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    # ------------------------------------------------------------------ CRUD

    def aggiungi(
        self,
        titolo: str,
        tipo: TipoAppuntamento,
        data_ora: str,
        durata_minuti: int = 60,
        luogo: str = "",
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

    def cerca(
        self,
        testo: Optional[str] = None,
        tipo: Optional[TipoAppuntamento] = None,
        stato: Optional[StatoAppuntamento] = None,
        cliente: Optional[str] = None,
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
        self, data_ora: str, durata_minuti: int
    ) -> List[Appuntamento]:
        """Restituisce appuntamenti che si sovrappongono con la finestra data."""
        nuovo_inizio = datetime.fromisoformat(data_ora)
        nuovo_fine = nuovo_inizio + timedelta(minutes=durata_minuti)

        sovrapposti = []
        for a in self._appuntamenti.values():
            if a.stato in (StatoAppuntamento.ANNULLATO, StatoAppuntamento.COMPLETATO):
                continue
            if a.data_ora_dt < nuovo_fine and a.fine_dt > nuovo_inizio:
                sovrapposti.append(a)
        return sovrapposti

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
