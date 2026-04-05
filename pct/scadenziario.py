"""
Scadenziario legale intelligente.

Funzionalità:
  - Calcolo automatico termini processuali (artt. 152-155 c.p.c.)
  - Festività italiane nazionali + sospensione feriale (1-31 agosto)
  - Tipi di termine: udienza, deposito, notifica, impugnazione, prescrizione…
  - Alert automatici a 7, 3, 1 giorno dalla scadenza (via messaggi)
  - Integrazione con fascicoli e agenda
  - Ricerca scadenze imminenti con filtri
"""

import calendar
import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


# ------------------------------------------------------------------ Enums

class TipoTermine(str, Enum):
    UDIENZA                = "UDIENZA"
    DEPOSITO_MEMORIA       = "DEPOSITO_MEMORIA"
    DEPOSITO_ATTO          = "DEPOSITO_ATTO"
    NOTIFICA               = "NOTIFICA"
    IMPUGNAZIONE           = "IMPUGNAZIONE"
    RISPOSTA_ECCEZIONE     = "RISPOSTA_ECCEZIONE"
    PAGAMENTO              = "PAGAMENTO"
    PRESCRIZIONE           = "PRESCRIZIONE"
    DECADENZA              = "DECADENZA"
    ADEMPIMENTO            = "ADEMPIMENTO"
    TERMINE_PERENTORIO     = "TERMINE_PERENTORIO"
    TERMINE_ORDINATORIO    = "TERMINE_ORDINATORIO"
    ALTRO                  = "ALTRO"


class PrioritaTermine(str, Enum):
    CRITICA = "CRITICA"   # < 3 giorni / termine perentorio
    ALTA    = "ALTA"      # 3–7 giorni
    MEDIA   = "MEDIA"     # 7–30 giorni
    BASSA   = "BASSA"     # > 30 giorni


class StatoTermine(str, Enum):
    APERTO      = "APERTO"
    COMPLETATO  = "COMPLETATO"
    ANNULLATO   = "ANNULLATO"
    SCADUTO     = "SCADUTO"


# ------------------------------------------------------------------ Festività italiane

def _calcola_pasqua(anno: int) -> date:
    """Algoritmo di Butcher per il calcolo della Pasqua."""
    a = anno % 19
    b = anno // 100
    c = anno % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    return date(anno, mese, giorno)


def festività_italiane(anno: int) -> List[date]:
    """Restituisce l'elenco delle festività nazionali italiane per l'anno."""
    pasqua = _calcola_pasqua(anno)
    pasquetta = pasqua + timedelta(days=1)
    return [
        date(anno, 1, 1),   # Capodanno
        date(anno, 1, 6),   # Epifania
        pasqua,              # Pasqua
        pasquetta,           # Lunedì dell'Angelo
        date(anno, 4, 25),  # Festa della Liberazione
        date(anno, 5, 1),   # Festa del Lavoro
        date(anno, 6, 2),   # Festa della Repubblica
        date(anno, 8, 15),  # Ferragosto
        date(anno, 11, 1),  # Ognissanti
        date(anno, 12, 8),  # Immacolata Concezione
        date(anno, 12, 25), # Natale
        date(anno, 12, 26), # Santo Stefano
    ]


def _festività_cache(anni: range) -> set:
    feste = set()
    for anno in anni:
        feste.update(festività_italiane(anno))
    return feste


def è_giorno_lavorativo(d: date, sospensione_feriale: bool = True) -> bool:
    """
    Restituisce True se il giorno è lavorativo (non weekend, non festività,
    non in sospensione feriale agosto).
    """
    if d.weekday() >= 5:  # sabato=5, domenica=6
        return False
    feste = _festività_cache(range(d.year - 1, d.year + 2))
    if d in feste:
        return False
    # Sospensione feriale: 1-31 agosto (art. 1 L. 742/1969)
    if sospensione_feriale and d.month == 8:
        return False
    return True


def prossimo_giorno_lavorativo(d: date, sospensione_feriale: bool = True) -> date:
    """Restituisce il primo giorno lavorativo >= d."""
    while not è_giorno_lavorativo(d, sospensione_feriale):
        d += timedelta(days=1)
    return d


# ------------------------------------------------------------------ Calcolo termini

def _aggiungi_mesi_calendario(d: date, mesi: int) -> date:
    totale = (d.month - 1) + mesi
    anno = d.year + (totale // 12)
    mese = (totale % 12) + 1
    giorno = min(d.day, calendar.monthrange(anno, mese)[1])
    return date(anno, mese, giorno)


def _aggiungi_anni_calendario(d: date, anni: int) -> date:
    anno = d.year + anni
    giorno = min(d.day, calendar.monthrange(anno, d.month)[1])
    return date(anno, d.month, giorno)


def _aggiungi_giorni_processuali(
    data_inizio: date,
    giorni: int,
    sospensione_feriale: bool = True,
    escludi_inizio: bool = True,
) -> date:
    if giorni <= 0:
        return data_inizio

    corrente = data_inizio + timedelta(days=1) if escludi_inizio else data_inizio
    contati = 0
    while True:
        if not (sospensione_feriale and corrente.month == 8):
            contati += 1
            if contati == giorni:
                return corrente
        corrente += timedelta(days=1)


def _aggiungi_giorni_lavorativi(
    data_inizio: date,
    giorni: int,
    sospensione_feriale: bool = True,
    escludi_inizio: bool = True,
) -> date:
    if giorni <= 0:
        return data_inizio

    corrente = data_inizio + timedelta(days=1) if escludi_inizio else data_inizio
    contati = 0
    while True:
        if è_giorno_lavorativo(corrente, sospensione_feriale):
            contati += 1
            if contati == giorni:
                return corrente
        corrente += timedelta(days=1)


def calcola_termine(
    data_inizio: date,
    giorni: int = 0,
    tipo: str = "liberi",
    sospensione_feriale: bool = True,
    escludi_inizio: bool = True,
    mesi: int = 0,
    anni: int = 0,
) -> date:
    """
    Calcola un termine legale.

    Args:
        data_inizio: data di decorrenza (es. notifica, udienza).
        giorni: numero di giorni del termine.
        tipo:
          - "liberi": termine processuale a giorni di calendario, con
            esclusione del dies a quo e proroga se la scadenza cade in giorno
            non lavorativo.
          - "continui": alias di retrocompatibilita di "liberi".
          - "lavorativi": conteggio per soli giorni lavorativi.
        sospensione_feriale: se True applica la sospensione feriale agostana.
        escludi_inizio: se True il dies a quo non è contato (art. 155 c.p.c.).
        mesi: termine espresso in mesi di calendario comune.
        anni: termine espresso in anni di calendario comune.
    Returns:
        Data di scadenza (prorogata al giorno lavorativo se cade in festività).
    """
    d = data_inizio
    tipo_norm = (tipo or "liberi").lower()

    if anni:
        d = _aggiungi_anni_calendario(d, anni)

    if mesi:
        d = _aggiungi_mesi_calendario(d, mesi)

    if giorni:
        if tipo_norm == "lavorativi":
            d = _aggiungi_giorni_lavorativi(
                d,
                giorni,
                sospensione_feriale=sospensione_feriale,
                escludi_inizio=escludi_inizio,
            )
        else:
            d = _aggiungi_giorni_processuali(
                d,
                giorni,
                sospensione_feriale=sospensione_feriale,
                escludi_inizio=escludi_inizio,
            )

    # Se la scadenza cade in giorno non lavorativo, proroga al successivo
    # (art. 155 co. 4 c.p.c.)
    d = prossimo_giorno_lavorativo(d, sospensione_feriale)
    return d


# Preset termini processuali comuni
PRESET_TERMINI: Dict[str, Dict[str, Any]] = {
    "impugnazione_sentenza_civile": {
        "label": "Impugnazione sentenza civile",
        "giorni": 30, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Art. 325 c.p.c. — 30 giorni dalla notifica della sentenza, con sospensione feriale se applicabile.",
    },
    "appello_breve": {
        "label": "Appello (termine breve)",
        "giorni": 30, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Art. 325 c.p.c. — 30 giorni dalla notifica della sentenza",
    },
    "appello_lungo": {
        "label": "Appello (termine lungo)",
        "giorni": 0, "mesi": 6, "tipo": "continui", "sospensione_feriale": False,
        "descrizione": "Art. 327 c.p.c. — 6 mesi dal deposito della sentenza, computati a mesi di calendario comune.",
    },
    "cassazione_breve": {
        "label": "Ricorso in Cassazione (breve)",
        "giorni": 60, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Art. 325 c.p.c. — 60 giorni dalla notifica",
    },
    "cassazione_lungo": {
        "label": "Ricorso in Cassazione (lungo)",
        "giorni": 0, "mesi": 6, "tipo": "continui", "sospensione_feriale": False,
        "descrizione": "Art. 327 c.p.c. — 6 mesi dal deposito, computati a mesi di calendario comune.",
    },
    "opposizione_decreto_ingiuntivo": {
        "label": "Opposizione decreto ingiuntivo",
        "giorni": 40, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Art. 641 c.p.c. — 40 giorni dalla notifica",
    },
    "memoria_ex_171_ter_n1": {
        "label": "Memoria art. 171-ter n. 1",
        "giorni": 40, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Prima memoria del rito ordinario post-Cartabia: 40 giorni prima dell'udienza.",
    },
    "memoria_ex_171_ter_n2": {
        "label": "Memoria art. 171-ter n. 2",
        "giorni": 20, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Seconda memoria del rito ordinario post-Cartabia: 20 giorni prima dell'udienza.",
    },
    "memoria_ex_171_ter_n3": {
        "label": "Memoria art. 171-ter n. 3",
        "giorni": 10, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Terza memoria del rito ordinario post-Cartabia: 10 giorni prima dell'udienza.",
    },
    "memoria_ex_183_co6_n1": {
        "label": "Memoria art. 183 co. 6 n. 1 (rito previgente)",
        "giorni": 30, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Preset legacy per fascicoli con rito previgente: 30 giorni.",
    },
    "memoria_ex_183_co6_n2": {
        "label": "Memoria art. 183 co. 6 n. 2 (rito previgente)",
        "giorni": 30, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Preset legacy per fascicoli con rito previgente: 30 giorni.",
    },
    "memoria_ex_183_co6_n3": {
        "label": "Memoria art. 183 co. 6 n. 3 (rito previgente)",
        "giorni": 20, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Preset legacy per fascicoli con rito previgente: 20 giorni.",
    },
    "comparsa_conclusionale": {
        "label": "Comparsa conclusionale",
        "giorni": 60, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Art. 190 c.p.c. — 60 giorni.",
    },
    "memoria_replica": {
        "label": "Memoria di replica",
        "giorni": 20, "tipo": "liberi", "sospensione_feriale": True,
        "descrizione": "Art. 190 c.p.c. — 20 giorni dopo la comparsa conclusionale.",
    },
    "prescrizione_ordinaria": {
        "label": "Prescrizione ordinaria",
        "giorni": 0, "anni": 10, "tipo": "continui", "sospensione_feriale": False,
        "descrizione": "Art. 2946 c.c. — 10 anni, computati secondo il calendario comune.",
    },
    "prescrizione_breve_5anni": {
        "label": "Prescrizione breve (5 anni)",
        "giorni": 0, "anni": 5, "tipo": "continui", "sospensione_feriale": False,
        "descrizione": "Art. 2948 c.c. — 5 anni, computati secondo il calendario comune.",
    },
}


# ------------------------------------------------------------------ Scadenza

@dataclass
class Scadenza:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    id_fascicolo: str = ""
    id_appuntamento: str = ""
    tipo: TipoTermine = TipoTermine.ALTRO
    priorita: PrioritaTermine = PrioritaTermine.MEDIA
    stato: StatoTermine = StatoTermine.APERTO
    titolo: str = ""
    descrizione: str = ""
    data_decorrenza: str = ""    # ISO date inizio termine
    data_scadenza: str = ""      # ISO date scadenza calcolata
    giorni_preavviso: List[int] = field(default_factory=lambda: [7, 3, 1])
    avvisi_inviati: List[int] = field(default_factory=list)  # giorni già notificati
    id_utente_responsabile: str = ""
    note: str = ""
    creata_il: str = field(default_factory=lambda: datetime.now().isoformat())
    completata_il: str = ""
    perentorio: bool = False

    @property
    def data_scadenza_obj(self) -> Optional[date]:
        if self.data_scadenza:
            return date.fromisoformat(self.data_scadenza)
        return None

    @property
    def giorni_alla_scadenza(self) -> Optional[int]:
        ds = self.data_scadenza_obj
        if ds:
            return (ds - date.today()).days
        return None

    @property
    def è_scaduta(self) -> bool:
        g = self.giorni_alla_scadenza
        return g is not None and g < 0 and self.stato == StatoTermine.APERTO

    @property
    def è_imminente(self, soglia: int = 7) -> bool:
        g = self.giorni_alla_scadenza
        return g is not None and 0 <= g <= soglia

    def _calcola_priorita(self) -> PrioritaTermine:
        g = self.giorni_alla_scadenza
        if g is None:
            return PrioritaTermine.BASSA
        if g <= 3 or self.perentorio and g <= 7:
            return PrioritaTermine.CRITICA
        if g <= 7:
            return PrioritaTermine.ALTA
        if g <= 30:
            return PrioritaTermine.MEDIA
        return PrioritaTermine.BASSA

    def aggiorna_priorita(self):
        self.priorita = self._calcola_priorita()

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["priorita"] = self.priorita.value
        d["stato"] = self.stato.value
        return d

    @staticmethod
    def from_dict(d: Dict) -> "Scadenza":
        d = dict(d)
        d["tipo"] = TipoTermine(d.get("tipo", "ALTRO"))
        d["priorita"] = PrioritaTermine(d.get("priorita", "MEDIA"))
        d["stato"] = StatoTermine(d.get("stato", "APERTO"))
        return Scadenza(**d)


# ------------------------------------------------------------------ Gestione

class GestioneScadenziario:
    """
    Gestisce il registro scadenze legali dello studio.
    """

    def __init__(self, db_path: str = "./scadenziario/scadenze.json", studio_db=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._scadenze: Dict[str, Scadenza] = {}
        self._carica()

    # ---- persistenza

    def _carica(self):
        if self._studio_db is not None:
            import json as _json
            try:
                rows = self._studio_db.conn.execute(
                    "SELECT * FROM scadenze"
                ).fetchall()
                self._scadenze = {}
                for row in rows:
                    d = dict(row)
                    dati = d.get("dati_json")
                    try:
                        payload = _json.loads(dati) if dati else d
                        if not dati:
                            payload["giorni_preavviso"] = _json.loads(d.get("giorni_preavviso") or "[]")
                            payload["avvisi_inviati"] = _json.loads(d.get("avvisi_inviati") or "[]")
                            payload.pop("dati_json", None)
                        s = Scadenza.from_dict(payload)
                        self._scadenze[s.id] = s
                    except Exception:
                        pass
            except Exception:
                self._scadenze = {}
            return
        from pct import cache as _cache
        try:
            raw = _cache.load(self.db_path)
            self._scadenze = {k: Scadenza.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._scadenze = {}

    def _salva(self):
        if self._studio_db is not None:
            import json as _json

            def _insert(conn, s):
                d = s.to_dict()
                conn.execute(
                    """
                    INSERT INTO scadenze
                    (id, tipo, stato, titolo, data_scadenza, priorita, perentorio,
                     note, id_fascicolo, id_appuntamento, id_utente,
                     giorni_preavviso, avvisi_inviati, completata_il, creato_il,
                     dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        s.id, s.tipo.value, s.stato.value, s.titolo,
                        s.data_scadenza, s.priorita.value,
                        1 if s.perentorio else 0,
                        s.note,
                        s.id_fascicolo or None,
                        s.id_appuntamento or None,
                        s.id_utente_responsabile,
                        _json.dumps(s.giorni_preavviso, ensure_ascii=False),
                        _json.dumps(s.avvisi_inviati, ensure_ascii=False),
                        s.completata_il, s.creata_il,
                        _json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("scadenze", list(self._scadenze.values()), _insert)
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._scadenze.items()})

    # ---- CRUD

    def nuova(
        self,
        titolo: str,
        tipo: TipoTermine,
        data_scadenza: str,
        id_fascicolo: str = "",
        descrizione: str = "",
        data_decorrenza: str = "",
        giorni_preavviso: Optional[List[int]] = None,
        id_utente_responsabile: str = "",
        note: str = "",
        perentorio: bool = False,
    ) -> Scadenza:
        if not titolo.strip():
            raise ValueError("Titolo obbligatorio")
        sc = Scadenza(
            tipo=tipo,
            titolo=titolo.strip(),
            descrizione=descrizione.strip(),
            data_decorrenza=data_decorrenza,
            data_scadenza=data_scadenza,
            id_fascicolo=id_fascicolo,
            giorni_preavviso=giorni_preavviso if giorni_preavviso is not None else [7, 3, 1],
            id_utente_responsabile=id_utente_responsabile,
            note=note,
            perentorio=perentorio,
        )
        sc.aggiorna_priorita()
        self._scadenze[sc.id] = sc
        self._salva()
        return sc

    def nuova_da_preset(
        self,
        preset_key: str,
        titolo: str,
        data_decorrenza: str,
        id_fascicolo: str = "",
        **kwargs,
    ) -> Scadenza:
        """Crea una scadenza usando un preset termine processuale."""
        preset = PRESET_TERMINI.get(preset_key)
        if not preset:
            raise ValueError(f"Preset '{preset_key}' non trovato")
        if not data_decorrenza or not data_decorrenza.strip():
            raise ValueError("Data decorrenza obbligatoria per il calcolo del termine")
        d_inizio = date.fromisoformat(data_decorrenza)
        d_scadenza = calcola_termine(
            data_inizio=d_inizio,
            giorni=preset.get("giorni", 0),
            tipo=preset["tipo"],
            sospensione_feriale=preset.get("sospensione_feriale", True),
            mesi=preset.get("mesi", 0),
            anni=preset.get("anni", 0),
        )
        return self.nuova(
            titolo=titolo,
            tipo=TipoTermine.TERMINE_PERENTORIO,
            data_scadenza=d_scadenza.isoformat(),
            id_fascicolo=id_fascicolo,
            descrizione=preset.get("descrizione", ""),
            data_decorrenza=data_decorrenza,
            **kwargs,
        )

    def aggiorna(self, id_sc: str, **kwargs) -> Scadenza:
        sc = self._get_or_raise(id_sc)
        campi_ok = {
            "titolo", "tipo", "priorita", "stato", "descrizione",
            "data_scadenza", "giorni_preavviso", "id_utente_responsabile",
            "note", "perentorio",
        }
        for k, v in kwargs.items():
            if k not in campi_ok:
                raise ValueError(f"Campo non modificabile: {k}")
            if k == "tipo":
                v = TipoTermine(v)
            setattr(sc, k, v)
        sc.aggiorna_priorita()
        self._salva()
        return sc

    def completa(self, id_sc: str, note: str = "") -> Scadenza:
        sc = self._get_or_raise(id_sc)
        sc.stato = StatoTermine.COMPLETATO
        sc.completata_il = datetime.now().isoformat()
        if note:
            sc.note = (sc.note + "\n" + note).strip()
        self._salva()
        return sc

    def elimina(self, id_sc: str):
        if id_sc not in self._scadenze:
            raise ValueError(f"Scadenza {id_sc!r} non trovata")
        del self._scadenze[id_sc]
        self._salva()

    # ---- query

    def get(self, id_sc: str) -> Optional[Scadenza]:
        return self._scadenze.get(id_sc)

    def tutte(
        self,
        stato: Optional[StatoTermine] = None,
        tipo: Optional[TipoTermine] = None,
        priorita: Optional[PrioritaTermine] = None,
        id_fascicolo: str = "",
        id_utente: str = "",
        solo_aperte: bool = True,
    ) -> List[Scadenza]:
        risultati = list(self._scadenze.values())
        if solo_aperte:
            risultati = [s for s in risultati if s.stato == StatoTermine.APERTO]
        if stato:
            risultati = [s for s in risultati if s.stato == stato]
        if tipo:
            risultati = [s for s in risultati if s.tipo == tipo]
        if priorita:
            risultati = [s for s in risultati if s.priorita == priorita]
        if id_fascicolo:
            risultati = [s for s in risultati if s.id_fascicolo == id_fascicolo]
        if id_utente:
            risultati = [s for s in risultati if s.id_utente_responsabile == id_utente]
        # Aggiorna priorità e ordina per data
        for s in risultati:
            s.aggiorna_priorita()
        return sorted(risultati, key=lambda s: s.data_scadenza or "9999-12-31")

    def imminenti(self, entro_giorni: int = 7) -> List[Scadenza]:
        """Scadenze aperte entro N giorni dalla data odierna."""
        oggi = date.today()
        limite = (oggi + timedelta(days=entro_giorni)).isoformat()
        result = [
            s for s in self._scadenze.values()
            if s.stato == StatoTermine.APERTO
            and s.data_scadenza
            and s.data_scadenza <= limite
        ]
        for s in result:
            s.aggiorna_priorita()
        return sorted(result, key=lambda s: s.data_scadenza)

    def scadute(self) -> List[Scadenza]:
        """Scadenze passate ancora nello stato APERTO (non completate)."""
        oggi = date.today().isoformat()
        result = [
            s for s in self._scadenze.values()
            if s.stato == StatoTermine.APERTO and s.data_scadenza < oggi
        ]
        # Aggiorna stato automaticamente
        for s in result:
            s.stato = StatoTermine.SCADUTO
        if result:
            self._salva()
        return sorted(result, key=lambda s: s.data_scadenza)

    def per_mese(self, anno: int, mese: int) -> List[Scadenza]:
        """Tutte le scadenze (qualsiasi stato) in un mese specifico."""
        prefisso = f"{anno:04d}-{mese:02d}"
        return [
            s for s in self._scadenze.values()
            if s.data_scadenza.startswith(prefisso)
        ]

    # ---- alert automatici

    def scadenze_da_notificare(self) -> List[Tuple[Scadenza, int]]:
        """
        Restituisce le scadenze che devono ricevere un avviso oggi.
        Tupla (scadenza, giorni_rimanenti).
        """
        oggi = date.today()
        da_notificare = []
        for sc in self._scadenze.values():
            if sc.stato != StatoTermine.APERTO or not sc.data_scadenza:
                continue
            ds = date.fromisoformat(sc.data_scadenza)
            g = (ds - oggi).days
            for soglia in sc.giorni_preavviso:
                if g == soglia and soglia not in sc.avvisi_inviati:
                    da_notificare.append((sc, g))
                    break
        return da_notificare

    def segna_avviso_inviato(self, id_sc: str, giorni: int):
        """Segna un avviso come già inviato."""
        sc = self._get_or_raise(id_sc)
        if giorni not in sc.avvisi_inviati:
            sc.avvisi_inviati.append(giorni)
        self._salva()

    def invia_avvisi(
        self,
        gm=None,
        avvocati_email: Optional[Dict[str, str]] = None,
    ) -> List[Dict]:
        """
        Invia gli avvisi automatici tramite GestioneMessaggi.
        Restituisce la lista degli avvisi inviati.
        """
        notifiche = self.scadenze_da_notificare()
        inviati = []
        for sc, giorni in notifiche:
            avviso = {
                "id_scadenza": sc.id,
                "titolo": sc.titolo,
                "data_scadenza": sc.data_scadenza,
                "giorni": giorni,
                "priorita": sc.priorita.value,
            }
            if gm and avvocati_email:
                email = avvocati_email.get(sc.id_utente_responsabile, "")
                if email:
                    try:
                        from .messaggi import TipoAutomazione, CanaleMsggio
                        gm.invia_da_template(
                            tipo=TipoAutomazione.AVVISO_SCADENZA,
                            canali=[CanaleMsggio.EMAIL],
                            destinatario_email=email,
                            variabili={
                                "nome": sc.id_utente_responsabile,
                                "scadenza": sc.data_scadenza,
                                "tipo_atto": sc.titolo,
                                "numero_fascicolo": sc.id_fascicolo or "—",
                                "giorni": str(giorni),
                                "priorita": sc.priorita.value,
                            },
                            id_fascicolo=sc.id_fascicolo,
                        )
                        avviso["email_inviata"] = email
                    except Exception as e:
                        avviso["errore_email"] = str(e)
            self.segna_avviso_inviato(sc.id, giorni)
            inviati.append(avviso)
        return inviati

    # ---- calendario

    def calendario_mese(self, anno: int, mese: int) -> Dict[str, List[Scadenza]]:
        """Restituisce un dict {data_iso: [scadenze]} per il mese."""
        scadenze_mese = self.per_mese(anno, mese)
        cal: Dict[str, List[Scadenza]] = {}
        for sc in scadenze_mese:
            cal.setdefault(sc.data_scadenza, []).append(sc)
        return cal

    # ---- statistiche

    def statistiche(self) -> Dict[str, Any]:
        tutte = list(self._scadenze.values())
        aperte = [s for s in tutte if s.stato == StatoTermine.APERTO]
        return {
            "totale": len(tutte),
            "aperte": len(aperte),
            "completate": sum(1 for s in tutte if s.stato == StatoTermine.COMPLETATO),
            "scadute": sum(1 for s in tutte if s.stato == StatoTermine.SCADUTO),
            "critiche": sum(1 for s in aperte if s.priorita == PrioritaTermine.CRITICA),
            "alte": sum(1 for s in aperte if s.priorita == PrioritaTermine.ALTA),
            "imminenti_7gg": len(self.imminenti(7)),
            "per_tipo": {
                t.value: sum(1 for s in aperte if s.tipo == t) for t in TipoTermine
            },
            "per_priorita": {
                p.value: sum(1 for s in aperte if s.priorita == p) for p in PrioritaTermine
            },
        }

    # ---- helper

    def _get_or_raise(self, id_sc: str) -> Scadenza:
        sc = self._scadenze.get(id_sc)
        if not sc:
            raise ValueError(f"Scadenza {id_sc!r} non trovata")
        return sc
