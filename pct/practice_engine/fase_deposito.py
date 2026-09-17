"""La fase di deposito: i controlli della busta valgono quando si deposita.

Il presidio del fascicolo e il deposito telematico devono dire la stessa cosa,
perché la verità è una sola: la busta si valida quando esiste. Un fascicolo
importato dal portale contiene copie di atti già depositati da altri — non
sono PDF/A, non sono firmati, non devono esserlo — e un fascicolo definito non
ha nulla da depositare. Applicare a quei documenti i controlli della busta
(PDF/A ex art. 12 D.M. 44/2011, firma CAdES, limiti dimensionali delle
specifiche DGSIA) produce blocchi che non riguardano l'avvocato e che il
percorso di deposito reale non produce mai, perché lì i documenti sono quelli
scelti per la busta.

Qui si dichiara quando quei controlli sono pertinenti:

- **preparazione**: l'avvocato ha scelto i documenti della busta
  (`profilo_deposito.preparazione_busta`) o esiste una sessione di deposito
  aperta: i controlli valgono, sui documenti scelti;
- **in corso**: la busta è stata inviata e si attendono le ricevute: i
  controlli restano visibili come storia del deposito;
- **non richiesta**: profilo non depositabile, fascicolo definito o
  archiviato, fascicolo importato dal portale senza busta in preparazione,
  oppure semplicemente nessun deposito preparato. I controlli della busta non
  si eseguono e non bloccano: si eseguiranno quando l'avvocato preparerà il
  deposito.

Base normativa dei controlli rinviati: D.M. 44/2011 artt. 12 e 14 e
Specifiche tecniche DGSIA per la busta telematica; art. 196-quater disp. att.
c.p.c. per l'obbligo di deposito telematico degli atti del processo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Stati di un deposito che, se presenti, dicono che la busta esiste già.
STATI_DEPOSITO_APERTI = {"IN_PREPARAZIONE", "PRONTO", "INVIATO", "ACCETTATO_PEC", "CONSEGNATO", "IN_ATTESA_CONTROLLI", "WARN_CONTROLLI"}
STATI_DEPOSITO_CHIUSI = {"CONTROLLI_OK", "ACCETTATO_CANCELLERIA", "ACQUISITO", "RIFIUTATO_CANCELLERIA", "ERRORE_CONTROLLI", "ERRORE"}
STATI_FASCICOLO_SENZA_DEPOSITO = {"DEFINITO", "CHIUSO", "ARCHIVIATO"}
MESSAGGIO_NON_RICHIESTA = (
    "Nessun deposito in preparazione: i controlli della busta (PDF/A, firma digitale, dimensioni) "
    "si eseguono quando prepari il deposito, sui documenti che scegli per la busta."
)


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split()).strip()


@dataclass(frozen=True, slots=True)
class FaseDeposito:
    """Se i controlli della busta sono pertinenti, e perché."""

    codice: str  # preparazione | in_corso | non_richiesta
    motivo: str
    documenti_busta: tuple[str, ...] = ()

    @property
    def in_deposito(self) -> bool:
        return self.codice in {"preparazione", "in_corso"}

    def to_dict(self) -> dict[str, Any]:
        return {"codice": self.codice, "motivo": self.motivo, "inDeposito": self.in_deposito, "documenti": list(self.documenti_busta)}


def _in_busta(voce: Any) -> str:
    """L'identificativo del documento se quella riga finisce davvero nella busta."""
    if not isinstance(voce, dict):
        return _testo(voce)
    if "selected" in voce and not bool(voce.get("selected")):
        return ""
    if _testo(voce.get("role")) == "fuori_busta":
        return ""
    return _testo(voce.get("id") or voce.get("documento_id") or voce.get("documentId"))


def _preparazione(fascicolo: Any) -> dict[str, Any]:
    profilo = getattr(fascicolo, "profilo_deposito", {}) or {}
    profilo = profilo if isinstance(profilo, dict) else {}
    preparazione = profilo.get("preparazione_busta")
    return preparazione if isinstance(preparazione, dict) else {}


def _busta_preparata(fascicolo: Any) -> tuple[str, ...]:
    """Gli identificativi dei documenti che l'avvocato ha scelto per la busta."""
    documenti = _preparazione(fascicolo).get("documents")
    scelti = [_in_busta(voce) for voce in (documenti if isinstance(documenti, list) else [])]
    return tuple(dict.fromkeys(identificativo for identificativo in scelti if identificativo))


def _tipo_deposito_scelto(fascicolo: Any) -> str:
    """Il tipo di deposito telematico scelto: da solo dice che si sta depositando."""
    preparazione = _preparazione(fascicolo)
    return _testo(preparazione.get("tipo_deposito_telematico_label") or preparazione.get("tipo_deposito_telematico_key"))


def _depositi_ordinati(fascicolo: Any) -> list[Any]:
    depositi = [voce for voce in list(getattr(fascicolo, "depositi_pct", []) or []) if voce is not None]
    return sorted(depositi, key=lambda voce: _testo(getattr(voce, "timestamp", "")))


def _depositi_del_fascicolo(fascicolo: Any) -> list[str]:
    return [_testo(getattr(voce, "stato", "")).upper() for voce in _depositi_ordinati(fascicolo)]


def _deposito_aperto(fascicolo: Any) -> Any:
    """L'ultimo deposito ancora in attesa di esito, se c'è."""
    for voce in reversed(_depositi_ordinati(fascicolo)):
        if _testo(getattr(voce, "stato", "")).upper() in STATI_DEPOSITO_APERTI:
            return voce
    return None


def fase_deposito(fascicolo: Any, *, profilo: Any = None, sessione: Any = None) -> FaseDeposito:
    """La fase di deposito del fascicolo, con il motivo in italiano."""
    scelti = _busta_preparata(fascicolo)
    stato_sessione = _testo(getattr(sessione, "status", "")).upper() if sessione is not None else ""
    if stato_sessione in STATI_DEPOSITO_APERTI:
        return FaseDeposito("in_corso", f"Deposito in corso ({stato_sessione.replace('_', ' ').lower()}): i controlli della busta restano visibili.", scelti)
    aperto = _deposito_aperto(fascicolo)
    if aperto is not None:
        stato = _testo(getattr(aperto, "stato", "")).upper()
        etichetta = ETICHETTE_DEPOSITO.get(stato, (stato.replace("_", " ").lower(), ""))[0]
        documenti = tuple(_testo(voce) for voce in list(getattr(aperto, "documenti_ids", []) or []) if _testo(voce))
        return FaseDeposito("in_corso", f"Deposito in corso: {etichetta.lower()}.", documenti or scelti)
    if scelti:
        return FaseDeposito("preparazione", f"Busta in preparazione: {len(scelti)} document{'o scelto' if len(scelti) == 1 else 'i scelti'} per il deposito.", scelti)
    tipo = _tipo_deposito_scelto(fascicolo)
    if tipo:
        return FaseDeposito("preparazione", f"Busta in preparazione ({tipo}): scegli i documenti da inserire nella busta.")
    if profilo is not None and not bool(getattr(profilo, "depositable", True)):
        return FaseDeposito("non_richiesta", "Questa procedura non prevede deposito telematico.")
    stato_fascicolo = _testo(getattr(fascicolo, "stato", "")).upper()
    if stato_fascicolo in STATI_FASCICOLO_SENZA_DEPOSITO:
        return FaseDeposito("non_richiesta", f"Fascicolo {stato_fascicolo.lower()}: non c'è una busta da depositare.")
    if _depositi_del_fascicolo(fascicolo):
        return FaseDeposito("non_richiesta", "Il deposito di questo fascicolo è già stato eseguito: prepara una nuova busta per depositare un altro atto.")
    if _testo(getattr(fascicolo, "source", "")):
        return FaseDeposito(
            "non_richiesta",
            f"Fascicolo importato dal portale {_testo(getattr(fascicolo, 'source', '')).upper()}: i documenti sono copie degli atti già depositati. "
            + MESSAGGIO_NON_RICHIESTA,
        )
    return FaseDeposito("non_richiesta", MESSAGGIO_NON_RICHIESTA)


# Lo stato del deposito come lo racconta il flusso ufficiale PCT (D.M. 44/2011,
# quattro fasi: accettazione PEC, avvenuta consegna, controlli automatici, esito
# della cancelleria). Il presidio non può dire «non inviato» quando il fascicolo
# porta un deposito accettato.
ETICHETTE_DEPOSITO: dict[str, tuple[str, str]] = {
    "INVIATO": ("Inviato, in attesa delle ricevute", "IN_ATTESA_RICEVUTE"),
    "ACCETTATO": ("Accettato dal gestore PEC", "IN_ATTESA_RICEVUTE"),
    "ACCETTATO_PEC": ("Accettato dal gestore PEC", "IN_ATTESA_RICEVUTE"),
    "CONSEGNATO": ("Consegnato al sistema ministeriale", "IN_ATTESA_RICEVUTE"),
    "IN_ATTESA_CONTROLLI": ("In attesa dei controlli automatici", "IN_ATTESA_RICEVUTE"),
    "WARN_CONTROLLI": ("Controlli automatici con avvisi", "IN_ATTESA_RICEVUTE"),
    "ERRORE_CONTROLLI": ("Controlli automatici con errori", "BLOCCATO_DA_ERRORI"),
    "CONTROLLI_OK": ("Controlli automatici superati", "IN_ATTESA_RICEVUTE"),
    "ACCETTATO_CANCELLERIA": ("Accettato dalla cancelleria", "ACQUISITO"),
    "RIFIUTATO_CANCELLERIA": ("Rifiutato dalla cancelleria", "BLOCCATO_DA_ERRORI"),
    "RIFIUTATO": ("Rifiutato", "BLOCCATO_DA_ERRORI"),
    "ERRORE": ("Errore nell'invio", "BLOCCATO_DA_ERRORI"),
}


@dataclass(frozen=True, slots=True)
class DepositoReale:
    """L'ultimo deposito telematico registrato nel fascicolo, come lo vede il PCT."""

    presente: bool
    stato: str = ""
    etichetta: str = ""
    stato_operativo: str = ""
    data: str = ""
    tipo_atto: str = ""
    identificativo: str = ""
    esito_controlli: str = ""

    @property
    def data_it(self) -> str:
        """La data del deposito in formato italiano, per il testo mostrato all'avvocato."""
        from pct.formatting import format_date_it

        return format_date_it(self.data) or self.data[:10]

    def to_dict(self) -> dict[str, Any]:
        return {
            "presente": self.presente, "stato": self.stato, "etichetta": self.etichetta, "statoOperativo": self.stato_operativo,
            "data": self.data, "dataIt": self.data_it, "tipoAtto": self.tipo_atto, "id": self.identificativo,
            "esitoControlli": self.esito_controlli,
        }


def deposito_reale(fascicolo: Any) -> DepositoReale:
    """L'ultimo deposito del fascicolo: è la verità sullo stato dell'invio."""
    depositi = list(getattr(fascicolo, "depositi_pct", []) or [])
    if not depositi:
        return DepositoReale(presente=False)
    ultimo = sorted(depositi, key=lambda voce: _testo(getattr(voce, "timestamp", "")))[-1]
    stato = _testo(getattr(ultimo, "stato", "")).upper()
    etichetta, operativo = ETICHETTE_DEPOSITO.get(stato, (stato.replace("_", " ").capitalize() or "Stato non noto", "DEPOSITO_INVIATO"))
    return DepositoReale(
        presente=True, stato=stato, etichetta=etichetta, stato_operativo=operativo,
        data=_testo(getattr(ultimo, "timestamp", "")), tipo_atto=_testo(getattr(ultimo, "tipo_atto", "")),
        identificativo=_testo(getattr(ultimo, "id", "")), esito_controlli=_testo(getattr(ultimo, "esito_controlli", "")),
    )


__all__ = ["DepositoReale", "ETICHETTE_DEPOSITO", "FaseDeposito", "MESSAGGIO_NON_RICHIESTA", "STATI_DEPOSITO_APERTI", "STATI_DEPOSITO_CHIUSI", "deposito_reale", "fase_deposito"]


def fase_presidio(fascicolo: Any, fase: FaseDeposito) -> FaseDeposito:
    """Read-only scope: an already sent envelope is monitored, not prepared again.

    This does not change the actual deposit workflow or its validators.
    A preparation saved after the latest transmission remains a new draft.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    def istante(value: Any) -> float:
        try:
            dt = datetime.fromisoformat(_testo(value).replace("Z", "+00:00"))
            return (dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo("Europe/Rome"))).timestamp()
        except (ValueError, TypeError):
            return 0.0
    depositi = [d for d in _depositi_ordinati(fascicolo) if _testo(getattr(d, "stato", "")) in ETICHETTE_DEPOSITO]
    if not depositi:
        return fase
    ultimo = depositi[-1]
    if istante(_preparazione(fascicolo).get("updated_at")) > istante(getattr(ultimo, "timestamp", "")):
        return fase
    stato = _testo(getattr(ultimo, "stato", ""))
    data = DepositoReale(presente=True, data=_testo(getattr(ultimo, "timestamp", ""))).data_it
    etichetta = ETICHETTE_DEPOSITO[stato][0]
    return FaseDeposito("monitoraggio", f"Deposito del {data}: {etichetta.lower()}. I controlli di firma e dimensione si riferiscono alla busta inviata; saranno ripetuti quando prepari un nuovo deposito.", fase.documenti_busta)
