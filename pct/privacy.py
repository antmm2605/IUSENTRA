"""
Registro dei Trattamenti di Dati Personali (GDPR Art. 30).

Obbligatorio per titolari con >= 250 dipendenti; fortemente raccomandato
per studi legali di qualsiasi dimensione dal Garante Privacy.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field, asdict


@dataclass
class TrattamentoDati:
    """Singola attività di trattamento nel Registro ex Art. 30 GDPR."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8].upper())
    nome: str = ""
    finalita: str = ""
    categoria_dati: str = ""           # es. "identificativi, contatto, legali, sanitari"
    base_giuridica: str = ""           # contratto | obbligo legale | interesse legittimo | consenso
    soggetti_interessati: str = ""     # clienti, collaboratori, fornitori...
    destinatari: str = ""              # interni / esterni / autorità
    trasferimento_extra_ue: bool = False
    paese_destinazione: str = ""
    termine_conservazione: str = ""    # es. "10 anni ex art. 2220 c.c."
    misure_sicurezza: str = ""         # es. "cifratura AES-256, backup giornaliero"
    responsabile: str = ""             # nome del responsabile esterno (se presente)
    attivo: bool = True
    note: str = ""
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrattamentoDati":
        d = dict(d)
        d.setdefault("trasferimento_extra_ue", False)
        d.setdefault("paese_destinazione", "")
        d.setdefault("responsabile", "")
        d.setdefault("attivo", True)
        d.setdefault("note", "")
        d.setdefault("soggetti_interessati", d.pop("soggetti", ""))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class GestioneTrattamenti:
    """Repository JSON per il Registro dei Trattamenti."""

    def __init__(self, db_path: str = "./privacy/registro.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._trattamenti: dict[str, TrattamentoDati] = {}
        self._carica()
        if not self._trattamenti:
            self._crea_default()

    def _carica(self):
        if self.db_path.exists():
            try:
                raw = json.loads(self.db_path.read_text("utf-8"))
                self._trattamenti = {k: TrattamentoDati.from_dict(v) for k, v in raw.items()}
            except Exception:
                self._trattamenti = {}

    def _salva(self):
        self.db_path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._trattamenti.items()},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _crea_default(self):
        """Popola il registro con i trattamenti tipici di uno studio legale."""
        default = [
            TrattamentoDati(
                nome="Gestione clienti e pratiche legali",
                finalita="Erogazione di servizi legali, gestione fascicoli e procedimenti",
                categoria_dati="Dati anagrafici, contatti, dati giudiziari, dati economici",
                base_giuridica="Contratto (art. 6.1.b GDPR) / Obbligo legale (art. 6.1.c GDPR)",
                soggetti_interessati="Clienti persone fisiche e giuridiche",
                destinatari="Avvocati, collaboratori interni, autorità giudiziarie, controparte",
                termine_conservazione="10 anni dalla chiusura del rapporto (art. 2220 c.c.)",
                misure_sicurezza="Accesso con credenziali, audit log, backup cifrato",
            ),
            TrattamentoDati(
                nome="Gestione del personale e collaboratori",
                finalita="Rapporto di lavoro / collaborazione professionale",
                categoria_dati="Dati anagrafici, fiscali, bancari, presenze",
                base_giuridica="Contratto (art. 6.1.b GDPR) / Obbligo legale (art. 6.1.c GDPR)",
                soggetti_interessati="Dipendenti, praticanti, collaboratori",
                destinatari="Studio Legale, consulente del lavoro, INPS, Agenzia delle Entrate",
                termine_conservazione="10 anni dalla cessazione del rapporto",
                misure_sicurezza="Accesso limitato all'amministratore, backup cifrato",
            ),
            TrattamentoDati(
                nome="Comunicazioni e messaggistica con i clienti",
                finalita="Aggiornamento sullo stato delle pratiche, notifiche di scadenze",
                categoria_dati="Dati di contatto (email, telefono, PEC)",
                base_giuridica="Contratto (art. 6.1.b GDPR)",
                soggetti_interessati="Clienti",
                destinatari="Interni allo studio, provider email/SMS",
                termine_conservazione="Durata del rapporto + 5 anni",
                misure_sicurezza="Cifratura TLS/STARTTLS per email, accesso con credenziali",
            ),
        ]
        for t in default:
            self._trattamenti[t.id] = t
        self._salva()

    # ---- CRUD

    def nuovo(self, **campi) -> TrattamentoDati:
        t = TrattamentoDati(**{k: v for k, v in campi.items()
                               if k in TrattamentoDati.__dataclass_fields__})
        self._trattamenti[t.id] = t
        self._salva()
        return t

    def aggiorna(self, id_t: str, **campi) -> TrattamentoDati:
        t = self._get_o_errore(id_t)
        for k, v in campi.items():
            if hasattr(t, k):
                setattr(t, k, v)
        t.modificato_il = datetime.now().isoformat()
        self._salva()
        return t

    def elimina(self, id_t: str) -> None:
        self._get_o_errore(id_t)
        del self._trattamenti[id_t]
        self._salva()

    def get(self, id_t: str) -> Optional[TrattamentoDati]:
        return self._trattamenti.get(id_t)

    def tutti(self, solo_attivi: bool = False) -> List[TrattamentoDati]:
        ts = sorted(self._trattamenti.values(), key=lambda t: t.nome)
        if solo_attivi:
            ts = [t for t in ts if t.attivo]
        return ts

    def _get_o_errore(self, id_t: str) -> TrattamentoDati:
        t = self._trattamenti.get(id_t)
        if not t:
            raise KeyError(f"Trattamento '{id_t}' non trovato.")
        return t
