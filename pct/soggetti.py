"""
pct/soggetti.py — Anagrafica soggetti e parti processuali

Un Soggetto è qualsiasi persona fisica o giuridica che può essere coinvolta
in un procedimento con un ruolo specifico (controparte, difensore, testimone, ecc.).
Un soggetto può anche coincidere con un Cliente dello studio (campo id_cliente).

Struttura dati:
  soggetti/anagrafica.json  — List[Soggetto]
  soggetti/parti.json       — Dict[id_fascicolo, List[ParteProcessuale]]
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pct.clienti import Indirizzo, Recapiti


def normalizza_identificativo_anagrafico(value: Any) -> str:
    """Normalizza C.F./P.IVA per confronti tra anagrafiche."""

    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def normalizza_nome_anagrafico(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _record_name(value: Any) -> str:
    direct = str(getattr(value, "nome_completo", "") or "").strip()
    if direct:
        return direct
    ragione = str(getattr(value, "ragione_sociale", "") or "").strip()
    if ragione:
        return ragione
    parts = [str(getattr(value, field, "") or "").strip() for field in ("cognome", "nome")]
    return " ".join(part for part in parts if part).strip()


def chiavi_anagrafiche_record(value: Any) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for field in ("codice_fiscale", "partita_iva", "identificativo", "identificativo_fiscale"):
        normalized = normalizza_identificativo_anagrafico(getattr(value, field, ""))
        if normalized:
            keys.add(("identificativo", normalized))
    name = normalizza_nome_anagrafico(_record_name(value))
    if name:
        keys.add(("nome", name))
    return keys


def chiavi_anagrafiche_clienti(clienti: list[Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for cliente in clienti:
        keys.update(chiavi_anagrafiche_record(cliente))
    return keys


def soggetto_coincide_con_cliente(soggetto: Any, clienti: list[Any]) -> bool:
    id_cliente = str(getattr(soggetto, "id_cliente", "") or "").strip()
    if id_cliente and any(str(getattr(cliente, "id", "") or "").strip() == id_cliente for cliente in clienti):
        return True
    subject_keys = chiavi_anagrafiche_record(soggetto)
    if not subject_keys:
        return False
    return bool(subject_keys & chiavi_anagrafiche_clienti(clienti))


# ── Enumerazioni ────────────────────────────────────────────────────────────

class TipoSoggetto(Enum):
    PERSONA_FISICA            = "PERSONA_FISICA"
    PERSONA_GIURIDICA         = "PERSONA_GIURIDICA"
    PUBBLICA_AMMINISTRAZIONE  = "PUBBLICA_AMMINISTRAZIONE"
    ENTE                      = "ENTE"
    CONDOMINIO                = "CONDOMINIO"
    ASSOCIAZIONE              = "ASSOCIAZIONE"
    PROFESSIONISTA            = "PROFESSIONISTA"


class RuoloSoggetto(Enum):
    ASSISTITO              = "ASSISTITO"              # Co-cliente / assistito aggiuntivo
    CONTROPARTE            = "CONTROPARTE"
    DIFENSORE_CONTROPARTE  = "DIFENSORE_CONTROPARTE"
    TESTIMONE              = "TESTIMONE"
    PERITO_CTP             = "PERITO_CTP"         # Consulente Tecnico di Parte
    PERITO_CTU             = "PERITO_CTU"         # Consulente Tecnico d'Ufficio
    CORRISPONDENTE         = "CORRISPONDENTE"     # Avvocato domiciliatario
    GIUDICE                = "GIUDICE"
    PM                     = "PM"                 # Pubblico Ministero
    NOTAIO                 = "NOTAIO"
    MEDIATORE              = "MEDIATORE"
    CURATORE               = "CURATORE"
    GARANTE                = "GARANTE"
    INTERVENIENTE          = "INTERVENIENTE"
    CREDITORE              = "CREDITORE"
    DEBITORE               = "DEBITORE"
    ALTRO                  = "ALTRO"

    @property
    def label(self) -> str:
        labels = {
            "ASSISTITO":             "Assistito / co-cliente",
            "CONTROPARTE":           "Controparte",
            "DIFENSORE_CONTROPARTE": "Difensore controparte",
            "TESTIMONE":             "Testimone",
            "PERITO_CTP":            "Perito CTP",
            "PERITO_CTU":            "Perito CTU",
            "CORRISPONDENTE":        "Corrispondente / domiciliatario",
            "GIUDICE":               "Giudice",
            "PM":                    "Pubblico Ministero",
            "NOTAIO":                "Notaio",
            "MEDIATORE":             "Mediatore",
            "CURATORE":              "Curatore",
            "GARANTE":               "Garante",
            "INTERVENIENTE":         "Interveniente",
            "CREDITORE":             "Creditore",
            "DEBITORE":              "Debitore",
            "ALTRO":                 "Altro",
        }
        return labels.get(self.value, self.value)

    @property
    def colore_bootstrap(self) -> str:
        colori = {
            "ASSISTITO":             "success",
            "CONTROPARTE":           "danger",
            "DIFENSORE_CONTROPARTE": "danger",
            "TESTIMONE":             "warning",
            "PERITO_CTP":            "info",
            "PERITO_CTU":            "info",
            "CORRISPONDENTE":        "primary",
            "GIUDICE":               "dark",
            "PM":                    "dark",
            "NOTAIO":                "secondary",
            "MEDIATORE":             "success",
            "CURATORE":              "secondary",
            "GARANTE":               "warning",
            "INTERVENIENTE":         "info",
            "CREDITORE":             "primary",
            "DEBITORE":              "danger",
            "ALTRO":                 "secondary",
        }
        return colori.get(self.value, "secondary")


# ── Modelli ─────────────────────────────────────────────────────────────────

@dataclass
class Soggetto:
    """Anagrafica di un soggetto (persona fisica o giuridica)."""

    id:   str
    tipo: TipoSoggetto

    # --- Persona fisica
    nome:             str = ""
    cognome:          str = ""
    codice_fiscale:   str = ""
    data_nascita:     str = ""   # YYYY-MM-DD
    luogo_nascita:    str = ""
    provincia_nascita: str = ""
    sesso:            str = ""   # M / F

    # --- Persona giuridica
    ragione_sociale:       str = ""
    partita_iva:           str = ""
    forma_giuridica:       str = ""   # Srl, SpA, SAS…
    rappresentante_legale: str = ""

    # --- Professionale (avvocati, periti, ecc.)
    qualifica:      str = ""   # Avvocato, Geometra, CTU, ecc.
    ordine:         str = ""   # es. Ordine Avvocati di Roma
    numero_iscrizione: str = ""

    # --- Recapiti e indirizzo
    indirizzo: Indirizzo = field(default_factory=Indirizzo)
    recapiti:  Recapiti  = field(default_factory=Recapiti)

    # --- Collegamento opzionale a un Cliente dello studio
    id_cliente: str = ""

    # --- Note e tag
    note: str = ""
    tag:  List[str] = field(default_factory=list)

    # --- Metadati
    creato_il:    str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat())

    # ── Proprietà ──

    @property
    def nome_completo(self) -> str:
        if self.tipo in (TipoSoggetto.PERSONA_GIURIDICA, TipoSoggetto.PUBBLICA_AMMINISTRAZIONE,
                         TipoSoggetto.ENTE, TipoSoggetto.CONDOMINIO, TipoSoggetto.ASSOCIAZIONE):
            return self.ragione_sociale or "—"
        parts = [self.cognome, self.nome]
        return " ".join(p for p in parts if p) or "—"

    @property
    def identificativo(self) -> str:
        if self.tipo in (TipoSoggetto.PERSONA_GIURIDICA, TipoSoggetto.PUBBLICA_AMMINISTRAZIONE,
                         TipoSoggetto.ENTE, TipoSoggetto.CONDOMINIO, TipoSoggetto.ASSOCIAZIONE):
            return self.partita_iva or self.codice_fiscale or ""
        return self.codice_fiscale or ""

    @property
    def sigla_tipo(self) -> str:
        _sigla = {
            TipoSoggetto.PERSONA_FISICA: "PF",
            TipoSoggetto.PERSONA_GIURIDICA: "PG",
            TipoSoggetto.PUBBLICA_AMMINISTRAZIONE: "PA",
            TipoSoggetto.ENTE: "EN",
            TipoSoggetto.CONDOMINIO: "CO",
            TipoSoggetto.ASSOCIAZIONE: "AS",
            TipoSoggetto.PROFESSIONISTA: "PR",
        }
        return _sigla.get(self.tipo, "PF")

    # ── Serde ──

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Soggetto":
        d = dict(d)
        d["tipo"] = TipoSoggetto(d.get("tipo", "PERSONA_FISICA"))
        ind = d.get("indirizzo") or {}
        rec = d.get("recapiti") or {}
        d["indirizzo"] = Indirizzo(**{k: v for k, v in ind.items() if k in Indirizzo.__dataclass_fields__})
        d["recapiti"]  = Recapiti(**{k: v for k, v in rec.items()  if k in Recapiti.__dataclass_fields__})
        campi = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in campi})


@dataclass
class ParteProcessuale:
    """Collegamento tra un Soggetto e un Fascicolo, con ruolo specifico."""

    id:           str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    id_soggetto:  str = ""
    ruolo:        RuoloSoggetto = RuoloSoggetto.ALTRO
    note:         str = ""
    data_aggiunta: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "id_soggetto":   self.id_soggetto,
            "ruolo":         self.ruolo.value,
            "note":          self.note,
            "data_aggiunta": self.data_aggiunta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ParteProcessuale":
        d = dict(d)
        d["ruolo"] = RuoloSoggetto(d.get("ruolo", "ALTRO"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Gestione ─────────────────────────────────────────────────────────────────

class GestioneSoggetti:
    """CRUD per soggetti e parti processuali."""

    def __init__(self, soggetti_path: str, parti_path: str, studio_db=None):
        self.soggetti_path = soggetti_path
        self.parti_path    = parti_path
        self._studio_db = studio_db
        self._soggetti: Optional[List[Soggetto]] = None
        self._parti:    Optional[Dict[str, list]] = None

    @staticmethod
    def _recapiti_payload(payload: dict[str, Any]) -> dict[str, Any]:
        recapiti = payload.get("recapiti")
        return recapiti if isinstance(recapiti, dict) else {}

    @staticmethod
    def _parte_sql_payload(id_fascicolo: str, parte: dict[str, Any] | ParteProcessuale) -> dict[str, Any]:
        payload = parte.to_dict() if isinstance(parte, ParteProcessuale) else dict(parte or {})
        payload["id_fascicolo"] = str(id_fascicolo or payload.get("id_fascicolo") or "")
        if not payload.get("id"):
            stable = "|".join(
                str(payload.get(field) or "")
                for field in ("id_fascicolo", "id_soggetto", "ruolo", "data_aggiunta")
            )
            payload["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"iusentra:soggetti_parti:{stable}"))[:12]
        return payload

    # ── Soggetti ──

    def _carica(self) -> List[Soggetto]:
        if self._soggetti is None:
            if self._studio_db is not None:
                self._soggetti = []
                for row in self._studio_db.carica_tabella("soggetti"):
                    if not isinstance(row, dict):
                        continue
                    try:
                        self._soggetti.append(Soggetto.from_dict(row))
                    except Exception:
                        continue
                return self._soggetti
            try:
                with open(self.soggetti_path, encoding="utf-8") as f:
                    raw = json.load(f)
                self._soggetti = [Soggetto.from_dict(d) for d in raw]
            except (FileNotFoundError, ValueError):
                self._soggetti = []
        return self._soggetti

    def _salva(self) -> None:
        if self._studio_db is not None:
            def _insert(conn, s: Soggetto) -> None:
                d = s.to_dict()
                rec = self._recapiti_payload(d)
                conn.execute(
                    """
                    INSERT INTO soggetti
                    (id, tipo, nome, cognome, ragione_sociale, codice_fiscale,
                     partita_iva, qualifica, id_cliente, email, telefono,
                     creato_il, modificato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        s.id,
                        s.tipo.value,
                        s.nome,
                        s.cognome,
                        s.ragione_sociale,
                        s.codice_fiscale,
                        s.partita_iva,
                        s.qualifica,
                        s.id_cliente or None,
                        rec.get("email", ""),
                        rec.get("telefono", "") or rec.get("cellulare", ""),
                        s.creato_il,
                        s.modificato_il,
                        json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("soggetti", self._soggetti or [], _insert)
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.soggetti_path)), exist_ok=True)
        with open(self.soggetti_path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in (self._soggetti or [])], f,
                      ensure_ascii=False, indent=2)

    def tutti(self) -> List[Soggetto]:
        return list(self._carica())

    def cerca(self, q: str = "", tipo: str = "") -> List[Soggetto]:
        tutti = self._carica()
        if q:
            q_low = q.lower()
            tutti = [
                s for s in tutti
                if q_low in s.nome_completo.lower()
                or q_low in (s.identificativo or "").lower()
                or q_low in (s.recapiti.email or "").lower()
                or q_low in (s.recapiti.pec or "").lower()
                or q_low in (s.qualifica or "").lower()
            ]
        if tipo:
            tutti = [s for s in tutti if s.tipo.value == tipo]
        return sorted(tutti, key=lambda s: s.nome_completo.lower())

    def get(self, id_soggetto: str) -> Optional[Soggetto]:
        return next((s for s in self._carica() if s.id == id_soggetto), None)

    def crea(self, tipo: TipoSoggetto, **kwargs) -> Soggetto:
        soggetti = self._carica()
        s = Soggetto(
            id=str(uuid.uuid4())[:12],
            tipo=tipo,
            **{k: v for k, v in kwargs.items() if k in Soggetto.__dataclass_fields__ and k not in ("id", "tipo")},
        )
        soggetti.append(s)
        self._soggetti = soggetti
        self._salva()
        return s

    def aggiorna(self, id_soggetto: str, **kwargs) -> Soggetto:
        soggetti = self._carica()
        s = next((x for x in soggetti if x.id == id_soggetto), None)
        if not s:
            raise KeyError(f"Soggetto {id_soggetto!r} non trovato")
        for k, v in kwargs.items():
            if hasattr(s, k) and k not in ("id", "creato_il"):
                setattr(s, k, v)
        s.modificato_il = datetime.now().isoformat()
        self._soggetti = soggetti
        self._salva()
        return s

    def elimina(self, id_soggetto: str) -> None:
        soggetti = self._carica()
        self._soggetti = [s for s in soggetti if s.id != id_soggetto]
        self._salva()

    # ── Parti processuali ──

    def _carica_parti(self) -> Dict[str, list]:
        if self._parti is None:
            if self._studio_db is not None:
                grouped: Dict[str, list] = {}
                for row in self._studio_db.carica_tabella("soggetti_parti"):
                    if not isinstance(row, dict):
                        continue
                    id_fascicolo = str(row.get("id_fascicolo") or "").strip()
                    if not id_fascicolo:
                        continue
                    payload = dict(row)
                    payload.pop("id_fascicolo", None)
                    grouped.setdefault(id_fascicolo, []).append(payload)
                self._parti = grouped
                return self._parti
            try:
                with open(self.parti_path, encoding="utf-8") as f:
                    self._parti = json.load(f)
            except (FileNotFoundError, ValueError):
                self._parti = {}
        return self._parti

    def _salva_parti(self) -> None:
        if self._studio_db is not None:
            rows: list[dict[str, Any]] = []
            for id_fascicolo, parti in (self._parti or {}).items():
                for parte in list(parti or []):
                    rows.append(self._parte_sql_payload(id_fascicolo, parte))

            def _insert(conn, payload: dict[str, Any]) -> None:
                conn.execute(
                    """
                    INSERT INTO soggetti_parti
                    (id, id_fascicolo, id_soggetto, ruolo, note, data_aggiunta, dati_json)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        payload.get("id"),
                        payload.get("id_fascicolo") or None,
                        payload.get("id_soggetto") or None,
                        payload.get("ruolo") or "ALTRO",
                        payload.get("note", ""),
                        payload.get("data_aggiunta", ""),
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("soggetti_parti", rows, _insert)
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.parti_path)), exist_ok=True)
        with open(self.parti_path, "w", encoding="utf-8") as f:
            json.dump(self._parti or {}, f, ensure_ascii=False, indent=2)

    def parti_fascicolo(self, id_fascicolo: str) -> List[tuple]:
        """Restituisce List[(ParteProcessuale, Soggetto)] per il fascicolo."""
        parti_raw = self._carica_parti().get(id_fascicolo, [])
        result = []
        for p_dict in parti_raw:
            parte    = ParteProcessuale.from_dict(p_dict)
            soggetto = self.get(parte.id_soggetto)
            if soggetto:
                result.append((parte, soggetto))
        return result

    def aggiungi_parte(
        self,
        id_fascicolo: str,
        id_soggetto:  str,
        ruolo:        RuoloSoggetto,
        note:         str = "",
    ) -> ParteProcessuale:
        parti = self._carica_parti()
        # Evita duplicati (stesso soggetto, stesso ruolo)
        fasc_raw = parti.get(id_fascicolo, [])
        for p in fasc_raw:
            if p.get("id_soggetto") == id_soggetto and p.get("ruolo") == ruolo.value:
                return ParteProcessuale.from_dict(p)   # già presente
        parte = ParteProcessuale(id_soggetto=id_soggetto, ruolo=ruolo, note=note)
        fasc_raw.append(parte.to_dict())
        parti[id_fascicolo] = fasc_raw
        self._parti = parti
        self._salva_parti()
        return parte

    def rimuovi_parte(self, id_fascicolo: str, id_parte: str) -> None:
        parti = self._carica_parti()
        parti[id_fascicolo] = [
            p for p in parti.get(id_fascicolo, [])
            if p.get("id") != id_parte
        ]
        self._parti = parti
        self._salva_parti()

    def fascicoli_con_soggetto(self, id_soggetto: str) -> List[str]:
        """IDs dei fascicoli in cui compare il soggetto."""
        return [
            id_f for id_f, pp in self._carica_parti().items()
            if any(p.get("id_soggetto") == id_soggetto for p in pp)
        ]
