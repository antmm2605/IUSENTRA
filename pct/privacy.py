"""
Registro dei Trattamenti di Dati Personali (GDPR Art. 30).

Per gli studi legali il registro è presidio ordinario quando lo studio tratta
dati giudiziari, sanitari o opera con personale/collaboratori. La fonte
operativa salvata è il dossier Garante sul registro delle attività di
trattamento, consultato e versionato tra le fonti ufficiali 2026-06-02.
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
    garanzie_trasferimento_extra_ue: str = ""
    termine_conservazione: str = ""    # es. "10 anni ex art. 2220 c.c."
    misure_sicurezza: str = ""         # es. "cifratura AES-256, backup giornaliero"
    responsabile: str = ""             # nome del responsabile esterno (se presente)
    registro_responsabile: str = ""    # riferimento al registro del responsabile ex art. 30.2
    fonte_normativa: str = "GDPR art. 30; Garante registro attività di trattamento"
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
        d.setdefault("garanzie_trasferimento_extra_ue", "")
        d.setdefault("responsabile", "")
        d.setdefault("registro_responsabile", "")
        d.setdefault("fonte_normativa", "GDPR art. 30; Garante registro attività di trattamento")
        d.setdefault("attivo", True)
        d.setdefault("note", "")
        d.setdefault("soggetti_interessati", d.pop("soggetti", ""))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class GestioneTrattamenti:
    """Repository per il Registro dei Trattamenti (JSON o SQLite)."""

    def __init__(self, db_path: str = "./privacy/registro.json", studio_db=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._trattamenti: dict[str, TrattamentoDati] = {}
        self._carica()
        if not self._trattamenti:
            self._crea_default()

    def _carica(self):
        if self._studio_db is not None:
            try:
                rows = self._studio_db.conn.execute(
                    "SELECT dati_json FROM privacy_trattamenti"
                ).fetchall()
                self._trattamenti = {}
                for row in rows:
                    dati = row[0] if row[0] else None
                    if dati:
                        try:
                            t = TrattamentoDati.from_dict(json.loads(dati))
                            self._trattamenti[t.id] = t
                        except Exception:
                            pass
            except Exception:
                self._trattamenti = {}
            return
        from pct import cache as _cache
        try:
            raw = _cache.load(self.db_path)
            self._trattamenti = {k: TrattamentoDati.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._trattamenti = {}

    def _salva(self):
        if self._studio_db is not None:
            def _insert(conn, t):
                d = t.to_dict()
                conn.execute(
                    """
                    INSERT INTO privacy_trattamenti
                    (id, nome, finalita, categoria_dati, base_giuridica,
                     soggetti_interessati, destinatari, trasferimento_extra_ue,
                     paese_destinazione, termine_conservazione,
                     misure_sicurezza, responsabile, attivo, note,
                     creato_il, modificato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        t.id, t.nome, t.finalita, t.categoria_dati,
                        t.base_giuridica, t.soggetti_interessati,
                        t.destinatari,
                        1 if t.trasferimento_extra_ue else 0,
                        t.paese_destinazione, t.termine_conservazione,
                        t.misure_sicurezza, t.responsabile,
                        1 if t.attivo else 0, t.note,
                        t.creato_il, t.modificato_il,
                        json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella(
                "privacy_trattamenti", list(self._trattamenti.values()), _insert
            )
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._trattamenti.items()})

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
                fonte_normativa="GDPR art. 30; Garante registro attività di trattamento",
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
                fonte_normativa="GDPR art. 30; Garante registro attività di trattamento",
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
                fonte_normativa="GDPR art. 30; Garante registro attività di trattamento",
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
