"""Incarichi CTU e ausiliari del giudice nel fascicolo.

Base normativa: artt. 61-64 e 191-201 c.p.c. (consulente tecnico d'ufficio e
consulenti di parte); art. 195 c.3 c.p.c. come modificato dalla riforma
Cartabia (D.Lgs. 149/2022): l'ordinanza di nomina fissa i tre termini —
trasmissione della bozza di relazione alle parti, osservazioni delle parti,
deposito della relazione finale con la valutazione delle osservazioni.
Compensi dell'ausiliario: D.P.R. 115/2002 artt. 49-58 con la tabella e le vacazioni
del D.M. 30/05/2002 (calcolo in ``pct/ctu_compensi/``; termini della liquidazione:
art. 71, cento giorni per l'istanza, e art. 170, trenta giorni per l'opposizione); i tipi atto per il deposito telematico
dell'ausiliario (DepositoRelazioneCTU, DepositoIntegrazioneCTU,
DepositoIstanzaLiquidazioneCTU) sono gia' nel catalogo busta.

Fail-closed: le tre date della timeline vengono SEMPRE dall'ordinanza del
giudice (inserite dall'avvocato), mai calcolate dal software; le scadenze
proposte nello scadenziario nascono in BOZZA da confermare.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

FONTE_NORMATIVA = (
    "Artt. 191-201 c.p.c.; art. 195 c.3 c.p.c. (D.Lgs. 149/2022); "
    "D.P.R. 115/2002 artt. 49-58; D.M. 30/05/2002"
)

# Ruolo dello studio rispetto all'incarico.
RUOLI_STUDIO = ("PARTE", "AUSILIARIO")  # assistiamo una parte / assistiamo il CTU

STATI_INCARICO = (
    "NOMINATO",        # ordinanza di nomina ricevuta
    "GIURAMENTO",      # udienza di giuramento/conferimento
    "OPERAZIONI",      # operazioni peritali in corso
    "BOZZA_TRASMESSA", # bozza inviata alle parti (parte il termine osservazioni)
    "OSSERVAZIONI",    # finestra osservazioni delle parti
    "DEPOSITATA",      # relazione finale depositata
    "LIQUIDAZIONE",    # istanza di liquidazione / decreto
    "CHIUSO",
)


_CAMPI_DATA = ("data_nomina", "data_giuramento", "termine_bozza", "termine_osservazioni", "termine_deposito",
               "data_deposito_relazione", "data_comunicazione_decreto")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _iso_date(value: Any) -> str:
    raw = _norm(value)[:10]
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return ""


@dataclass
class ConsulenteParte:
    """CTP ex art. 201 c.p.c. nominato da una parte."""

    nome: str = ""
    parte: str = ""  # quale parte lo ha nominato
    email: str = ""
    telefono: str = ""
    note: str = ""


@dataclass
class IncaricoCtu:
    """Incarico peritale collegato a un fascicolo."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12].upper())
    fascicolo_id: str = ""
    ruolo_studio: str = "PARTE"
    stato: str = "NOMINATO"
    # Ausiliario nominato
    nome_ctu: str = ""
    albo: str = ""  # categoria/albo (D.M. 109/2023: albo telematico nazionale)
    email_ctu: str = ""
    pec_ctu: str = ""
    # Contenuto dell'incarico
    quesiti: str = ""  # quesiti formulati dal giudice
    data_nomina: str = ""  # data ordinanza di nomina
    data_giuramento: str = ""  # udienza ex art. 193 c.p.c.
    # Timeline art. 195 c.3 c.p.c. — date fissate dall'ordinanza del giudice.
    termine_bozza: str = ""  # trasmissione bozza alle parti
    termine_osservazioni: str = ""  # osservazioni delle parti
    termine_deposito: str = ""  # deposito relazione finale
    # Liquidazione (D.P.R. 115/2002): compimento delle operazioni e decreto di pagamento.
    data_deposito_relazione: str = ""  # relazione depositata: decorre l'art. 71 (100 giorni)
    data_comunicazione_decreto: str = ""  # decreto comunicato: decorre l'opposizione (art. 170)
    importo_liquidato: str = ""
    operazioni: list[dict[str, Any]] = field(default_factory=list)  # operazioni peritali (art. 90 disp. att. c.p.c.)
    compenso_input: dict[str, Any] = field(default_factory=dict)  # ultimi dati del calcolo del compenso
    consulenti_parte: list[ConsulenteParte] = field(default_factory=list)
    note: str = ""
    fonte_normativa: str = FONTE_NORMATIVA
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "IncaricoCtu":
        payload = dict(dati or {})
        ctp = payload.get("consulenti_parte")
        if isinstance(ctp, list):
            payload["consulenti_parte"] = [
                ConsulenteParte(**{k: v for k, v in riga.items() if k in ConsulenteParte.__dataclass_fields__})
                for riga in ctp
                if isinstance(riga, dict)
            ]
        return cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})

    # ------------------------------------------------------------------ timeline
    def timeline(self) -> list[dict[str, str]]:
        """Le tappe dell'incarico con le date note (vuote se non fissate)."""

        return [
            {"chiave": "nomina", "label": "Ordinanza di nomina", "data": self.data_nomina},
            {"chiave": "giuramento", "label": "Giuramento / conferimento (art. 193 c.p.c.)", "data": self.data_giuramento},
            {"chiave": "bozza", "label": "Trasmissione bozza alle parti (art. 195 c.3)", "data": self.termine_bozza},
            {"chiave": "osservazioni", "label": "Osservazioni delle parti (art. 195 c.3)", "data": self.termine_osservazioni},
            {"chiave": "deposito", "label": "Deposito relazione finale (art. 195 c.3)", "data": self.termine_deposito},
        ] + [
            tappa for tappa in (
                {"chiave": "relazione_depositata", "label": "Relazione depositata", "data": self.data_deposito_relazione},
                {"chiave": "decreto", "label": "Decreto di liquidazione comunicato", "data": self.data_comunicazione_decreto},
            ) if tappa["data"]
        ]

    def termini_incoerenti(self) -> list[str]:
        """Avvisi se l'ordine dei tre termini art. 195 non e' cronologico."""

        avvisi: list[str] = []
        sequenza = [
            ("bozza alle parti", self.termine_bozza),
            ("osservazioni delle parti", self.termine_osservazioni),
            ("deposito finale", self.termine_deposito),
        ]
        note = [(label, valore) for label, valore in sequenza if valore]
        for (label_a, a), (label_b, b) in zip(note, note[1:]):
            if a > b:
                avvisi.append(
                    f"Il termine per {label_b} ({b}) precede quello per {label_a} ({a}): "
                    "verifica le date dell'ordinanza."
                )
        return avvisi


def proposte_scadenze_incarico(incarico: IncaricoCtu) -> list[dict[str, str]]:
    """Scadenze proponibili (BOZZA) dalla timeline dell'incarico.

    Per lo studio che assiste una parte il termine operativo e' quello delle
    osservazioni; per lo studio che assiste il CTU rilevano bozza e deposito.
    Le date vengono dall'ordinanza: qui si propone, l'avvocato conferma.
    """

    proposte: list[dict[str, str]] = []

    def _aggiungi(data_termine: str, titolo: str, chiave: str) -> None:
        if not _iso_date(data_termine):
            return
        proposte.append(
            {
                "chiave": f"ctu:{incarico.id}:{chiave}",
                "titolo": titolo,
                "data_scadenza": _iso_date(data_termine),
                "fascicolo_id": incarico.fascicolo_id,
                "fonte": "Ordinanza di nomina CTU (art. 195 c.3 c.p.c.)",
            }
        )

    if incarico.ruolo_studio == "AUSILIARIO":
        _aggiungi(incarico.termine_bozza, f"CTU {incarico.nome_ctu}: trasmettere bozza alle parti", "bozza")
        _aggiungi(incarico.termine_deposito, f"CTU {incarico.nome_ctu}: depositare relazione finale", "deposito")
    else:
        _aggiungi(
            incarico.termine_osservazioni,
            f"Osservazioni alla bozza CTU {incarico.nome_ctu or ''}".strip(),
            "osservazioni",
        )
        _aggiungi(incarico.termine_deposito, "Deposito relazione CTU attesa", "deposito")
    proposte.extend(_proposte_liquidazione_e_operazioni(incarico))
    return proposte


def _proposte_liquidazione_e_operazioni(incarico: IncaricoCtu) -> list[dict[str, str]]:
    """Termini di legge della liquidazione (artt. 71 e 170 D.P.R. 115/2002) e operazioni future."""

    from pct.ctu_compensi.termini import termine_istanza, termine_opposizione

    termini = []
    if incarico.ruolo_studio == "AUSILIARIO":
        termini.append(termine_istanza(incarico.data_deposito_relazione))
    termini.append(termine_opposizione(incarico.data_comunicazione_decreto))
    proposte = [
        {"chiave": f"ctu:{incarico.id}:{t['chiave']}", "titolo": f"{t['titolo']} — CTU {incarico.nome_ctu}".strip(),
         "data_scadenza": t["data"], "fascicolo_id": incarico.fascicolo_id, "fonte": f"{t['norma']}. {t['nota']}"}
        for t in termini if t
    ]
    from zoneinfo import ZoneInfo

    oggi = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    for operazione in incarico.operazioni:
        if str(operazione.get("data") or "") >= oggi:
            proposte.append({
                "chiave": f"ctu:{incarico.id}:operazione-{operazione.get('id')}",
                "titolo": f"Operazioni peritali CTU {incarico.nome_ctu}: {operazione.get('descrizione') or operazione.get('tipo') or ''}".strip(),
                "data_scadenza": str(operazione["data"]), "fascicolo_id": incarico.fascicolo_id,
                "fonte": "Operazioni peritali (art. 194 c.p.c.; art. 90 disp. att. c.p.c.)"
                + (f" ore {operazione['ora']}" if operazione.get("ora") else "")
                + (f", {operazione['luogo']}" if operazione.get("luogo") else ""),
            })
    return proposte


class GestioneCtu:
    """Repository tenant-aware degli incarichi CTU (JSON)."""

    def __init__(self, db_path: str = "./ctu/incarichi.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._incarichi: dict[str, IncaricoCtu] = {}
        self._carica()

    def _carica(self) -> None:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._incarichi = {k: IncaricoCtu.from_dict(v) for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError):
            self._incarichi = {}

    def _salva(self) -> None:
        self.db_path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._incarichi.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def nuovo(self, **campi: Any) -> IncaricoCtu:
        incarico = IncaricoCtu(**{k: v for k, v in campi.items() if k in IncaricoCtu.__dataclass_fields__})
        if not _norm(incarico.fascicolo_id):
            raise ValueError("L'incarico CTU va collegato a un fascicolo.")
        if incarico.ruolo_studio not in RUOLI_STUDIO:
            raise ValueError(f"Ruolo studio non valido: {incarico.ruolo_studio}.")
        for campo in _CAMPI_DATA:
            valore = _norm(getattr(incarico, campo))
            if valore and not _iso_date(valore):
                raise ValueError(f"Data non valida per {campo}: atteso formato ISO (YYYY-MM-DD).")
        self._incarichi[incarico.id] = incarico
        self._salva()
        return incarico

    def get(self, incarico_id: str) -> IncaricoCtu | None:
        return self._incarichi.get(incarico_id)

    def per_fascicolo(self, fascicolo_id: str) -> list[IncaricoCtu]:
        rows = [i for i in self._incarichi.values() if i.fascicolo_id == fascicolo_id]
        rows.sort(key=lambda i: i.creato_il, reverse=True)
        return rows

    def aggiorna(self, incarico_id: str, **campi: Any) -> IncaricoCtu:
        incarico = self._incarichi.get(incarico_id)
        if incarico is None:
            raise KeyError(f"Incarico CTU {incarico_id} non trovato.")
        aggiornato = IncaricoCtu.from_dict({**incarico.to_dict(), **campi, "id": incarico.id})
        if aggiornato.stato not in STATI_INCARICO:
            raise ValueError(f"Stato non valido: {aggiornato.stato}.")
        for campo in _CAMPI_DATA:
            valore = _norm(getattr(aggiornato, campo))
            if valore and not _iso_date(valore):
                raise ValueError(f"Data non valida per {campo}: atteso formato ISO (YYYY-MM-DD).")
        aggiornato.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._incarichi[incarico.id] = aggiornato
        self._salva()
        return aggiornato

    def aggiungi_ctp(self, incarico_id: str, *, nome: str, parte: str, email: str = "", telefono: str = "") -> IncaricoCtu:
        incarico = self._incarichi.get(incarico_id)
        if incarico is None:
            raise KeyError(f"Incarico CTU {incarico_id} non trovato.")
        if not _norm(nome):
            raise ValueError("Il consulente di parte richiede il nome.")
        incarico.consulenti_parte.append(
            ConsulenteParte(nome=_norm(nome), parte=_norm(parte), email=_norm(email), telefono=_norm(telefono))
        )
        incarico.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return incarico

    # ------------------------------------------------ operazioni e compenso
    def aggiungi_operazione(self, incarico_id: str, dati: dict[str, Any]) -> IncaricoCtu:
        incarico = self._incarichi.get(incarico_id)
        if incarico is None:
            raise KeyError(f"Incarico CTU {incarico_id} non trovato.")
        giorno = _iso_date(dati.get("data"))
        if not giorno:
            raise ValueError("Indica la data dell'operazione peritale.")
        try:
            minuti = int(float(dati.get("minuti") or 0))
        except (TypeError, ValueError):
            minuti = 0
        if minuti < 0 or minuti > 24 * 60:
            raise ValueError("La durata dell'operazione non è valida.")
        ora = _norm(dati.get("ora"))[:5]
        incarico.operazioni.append({
            "id": uuid.uuid4().hex[:10], "data": giorno, "ora": ora if len(ora) == 5 and ora[2] == ":" else "",
            "tipo": _norm(dati.get("tipo"))[:30] or "operazione", "luogo": _norm(dati.get("luogo"))[:160],
            "descrizione": _norm(dati.get("descrizione"))[:300], "minuti": minuti,
            "presenza_giudice": bool(dati.get("presenza_giudice")),
        })
        incarico.operazioni.sort(key=lambda o: (o.get("data", ""), o.get("ora", "")))
        incarico.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return incarico

    def rimuovi_operazione(self, incarico_id: str, operazione_id: str) -> bool:
        incarico = self._incarichi.get(incarico_id)
        if incarico is None:
            return False
        prima = len(incarico.operazioni)
        incarico.operazioni = [o for o in incarico.operazioni if o.get("id") != operazione_id]
        if len(incarico.operazioni) == prima:
            return False
        self._salva()
        return True

    def salva_compenso(self, incarico_id: str, dati: dict[str, Any]) -> None:
        incarico = self._incarichi.get(incarico_id)
        if incarico is None:
            return
        consentiti = {"modalita", "voci", "posizione", "vacazioni", "termine_giorni", "aumento_urgenza", "aumento_eccezionale",
                      "motivazione_aumento", "componenti_collegio", "collegio_per_intero", "ritardo", "patrocinio",
                      "spese_documentate", "spese_viaggio", "contributo_perc", "iva_perc"}
        incarico.compenso_input = {k: v for k, v in (dati or {}).items() if k in consentiti}
        self._salva()

    # ------------------------------------------------------------ scadenziario
    def proponi_scadenze(
        self,
        incarico_id: str,
        *,
        get_scadenziario: Callable[[], Any],
        attore: str = "",
    ) -> int:
        """Crea nello scadenziario le proposte in BOZZA dalla timeline.

        Idempotente: il marcatore ``ctu:<id>:<tappa>`` nelle note evita i
        doppioni tra piu' esecuzioni.
        """

        from pct.scadenziario import StatoTermine, TipoTermine

        incarico = self._incarichi.get(incarico_id)
        if incarico is None:
            raise KeyError(f"Incarico CTU {incarico_id} non trovato.")
        manager = get_scadenziario()
        esistenti = " \n ".join(
            str(getattr(item, "note", "") or "")
            for item in manager.tutte(solo_aperte=False)
            if str(getattr(item, "id_fascicolo", "") or "") == incarico.fascicolo_id
        )
        creati = 0
        for proposta in proposte_scadenze_incarico(incarico):
            if proposta["chiave"] in esistenti:
                continue
            manager.nuova(
                titolo=proposta["titolo"],
                tipo=TipoTermine.ADEMPIMENTO,
                data_scadenza=proposta["data_scadenza"],
                id_fascicolo=proposta["fascicolo_id"],
                descrizione=proposta["fonte"],
                note=f"{proposta['chiave']}\nFonte: {proposta['fonte']}",
                id_utente_responsabile=attore,
                stato=StatoTermine.BOZZA,
            )
            creati += 1
        return creati
