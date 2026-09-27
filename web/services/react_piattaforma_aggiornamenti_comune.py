"""Elementi comuni alle pagine React «Aggiornamenti legali» del pannello di piattaforma.

Le pagine `aggiornamenti-*` sostituiscono le viste storiche di
`web/blueprints/legal_updates_admin.py` (modelli `admin/legal_updates_*.html`).
Qui vivono:

- le etichette dei filtri Jinja del blueprint (`legal_update_action_label`,
  `legal_update_classification_label`, `legal_update_status_label`,
  `legal_update_staging_status_label`, `legal_update_staging_status_class`),
  riscritte in Python con gli accenti corretti;
- il motore condiviso (`build_legal_update_pipeline_runtime(tenant_slug="")`,
  come `_selected_tenant_slug()` della console storica);
- le tre azioni del motore (`/esegui/<action>`: scan, autopublish, cleanup) con
  gli stessi messaggi e gli stessi toni dei messaggi flash storici.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from web.services.react_piattaforma_sezioni import _t, azione, data_ora, esito, link

BASE = "/admin/aggiornamenti-legali"
INDIRIZZI = {
    "cruscotto": f"{BASE}/",
    "fonti": f"{BASE}/fonti",
    "acquisizione": f"{BASE}/staging",
    "catalogazione": f"{BASE}/analisi",
    "revisione": f"{BASE}/review",
    "archivio": f"{BASE}/archivio",
}
VOCI_SEZIONE = (
    ("cruscotto", "Panoramica del motore"),
    ("fonti", "Fonti"),
    ("acquisizione", "Acquisizione"),
    ("catalogazione", "Catalogazione"),
    ("revisione", "Coda revisioni"),
    ("archivio", "Archivio"),
)

ACTION_LABELS = {
    "NEWS_ONLY": "Notizia informativa",
    "NEW_NORMATIVE": "Nuova normativa",
    "UPDATE_NORMATIVE": "Aggiornamento normativo",
    "NEW_CASE_LAW": "Nuova giurisprudenza",
    "NEW_PRASSI": "Nuova prassi",
    "DUPLICATE": "Già presente in archivio",
    "OUT_OF_SCOPE": "Fuori perimetro",
    "NEEDS_REVIEW": "Controllo richiesto",
}
CLASSIFICATION_LABELS = {
    "NORMATIVA_NUOVA": "Normativa nuova",
    "NORMATIVA_AGGIORNAMENTO": "Aggiornamento normativo",
    "GIURISPRUDENZA": "Giurisprudenza",
    "PRASSI": "Prassi",
    "NEWS": "Notizia",
    "COMMENTO": "Commento",
    "DUPLICATO": "Duplicato",
    "INCERTO": "Da classificare",
}
STATUS_LABELS = {
    "pending": "In verifica",
    "approved": "Pronta alla pubblicazione",
    "published": "Pubblicata",
    "rejected": "Rifiutata",
    "closed": "Chiusa",
}
# Colori Bootstrap dei modelli storici → toni del pannello React.
TONI_CLASSE = {"success": "success", "primary": "info", "info": "info", "warning": "warning", "danger": "danger", "secondary": "", "light": ""}
TONI_STATO_REVISIONE = {"pending": "warning", "approved": "info", "published": "success", "rejected": "danger"}

NOMI_AZIONE_MOTORE = {"scan": "Ricerca nelle fonti", "autopublish": "Pubblicazione dei contenuti idonei", "cleanup": "Pulizia dei duplicati"}
MESSAGGI_AZIONE_MOTORE = {
    "scan": "Ricerca completata: archivio controllato, duplicati esclusi e nuovi contenuti pubblicati quando idonei.",
    "autopublish": "Pubblicazione automatica completata sui contenuti idonei.",
    "cleanup": "Pulizia archivio completata: i duplicati sono stati rimossi o accorpati.",
}

_APOSTROFO_FINALE = re.compile(r"\b(\w*?)(ch)?([aeiou])'(?=[\s.,;:!?)]|$)")
_ACCENTI = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}


# ------------------------------------------------------------------ testi


def accenti(value: Any) -> str:
    """«gia'», «autorita'», «perche'» dei testi di servizio → «già», «autorità», «perché»."""

    def _sostituisci(m: re.Match[str]) -> str:
        radice, ch, vocale = m.group(1), m.group(2) or "", m.group(3)
        if f"{radice}{ch}{vocale}".lower() == "po":
            return m.group(0)
        if ch and vocale == "e":
            return f"{radice}ché"
        return f"{radice}{ch}{_ACCENTI[vocale]}"

    return _APOSTROFO_FINALE.sub(_sostituisci, _t(value))


# Termini inglesi nei testi dei servizi, resi in italiano senza toccare i servizi.
TERMINI = (("RAG-only", "solo ricerca (RAG)"), ("Pubblicazione guarded", "Pubblicazione presidiata"), ("modalità guarded", "pubblicazione presidiata"), ("guarded", "presidiata"), ("a job separati", "in lavorazioni separate"))


def lessico(value: Any) -> str:
    """Testo di servizio in italiano: accenti al posto degli apostrofi e termini tradotti."""
    testo = accenti(value)
    for inglese, italiano in TERMINI:
        testo = testo.replace(inglese, italiano)
    return testo


def _pulisci(value: Any) -> str:
    return " ".join(_t(value).replace("_", " ").split()).strip()


def leggibile(value: Any, predefinito: str = "") -> str:
    """Codice tecnico reso leggibile (trattini bassi → spazi, iniziale maiuscola)."""
    return _pulisci(value).capitalize() or predefinito


def etichetta_azione(value: Any) -> str:
    return ACTION_LABELS.get(_t(value).upper(), leggibile(value, "Controllo richiesto"))


def etichetta_classificazione(value: Any) -> str:
    return CLASSIFICATION_LABELS.get(_t(value).upper(), leggibile(value, "Da classificare"))


def etichetta_stato(value: Any) -> str:
    return STATUS_LABELS.get(_t(value).lower(), leggibile(value, "In verifica"))


def etichetta_lavorazione(row: Any) -> str:
    """Filtro storico `legal_update_staging_status_label`."""
    riga = row if isinstance(row, dict) else {}
    if not riga.get("analysis_id"):
        return "Da analizzare"
    stato = _t(riga.get("review_status")).lower()
    proposta = _t(riga.get("proposed_action")).upper()
    if stato == "published":
        return "Pubblicato"
    if stato == "closed":
        return {"DUPLICATE": "Già presente", "OUT_OF_SCOPE": "Archiviato automaticamente"}.get(proposta, "Chiuso")
    if stato == "approved":
        return "Pronto alla pubblicazione"
    if stato == "rejected":
        return "Rifiutato"
    if proposta == "NEEDS_REVIEW":
        return "Classificato con controllo richiesto"
    if stato == "pending":
        return "Verifica fonti in corso"
    return "Classificato automaticamente"


def classe_lavorazione(row: Any) -> str:
    """Filtro storico `legal_update_staging_status_class` (colore Bootstrap)."""
    riga = row if isinstance(row, dict) else {}
    stato = _t(riga.get("review_status")).lower()
    proposta = _t(riga.get("proposed_action")).upper()
    if stato == "published":
        return "success"
    if stato == "approved":
        return "primary"
    if stato == "closed":
        return "secondary" if proposta != "OUT_OF_SCOPE" else "light"
    if stato == "rejected":
        return "danger"
    if riga.get("analysis_id"):
        return "info"
    return "warning"


def tono_lavorazione(row: Any) -> str:
    return TONI_CLASSE.get(classe_lavorazione(row), "")


def confidenza(value: Any) -> str:
    """`'%.2f'|format(...)` dei modelli storici, con la virgola decimale."""
    try:
        numero = float(value or 0)
    except (TypeError, ValueError):
        numero = 0.0
    return f"{numero:.2f}".replace(".", ",")


def data(value: Any, predefinito: str = "data non disponibile") -> str:
    """Filtro `fmt_data` (gg/mm/aaaa) con il testo storico per la data assente."""
    return data_ora(value)[:10] or predefinito


def unisci(*parti: Any, separatore: str = " · ") -> str:
    return separatore.join(_t(p) for p in parti if _t(p))


# ------------------------------------------------------------------ motore


def motore():
    """Il motore condiviso, come `build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())`."""
    from web.services.legal_update_surface import build_legal_update_pipeline_runtime

    return build_legal_update_pipeline_runtime(tenant_slug="")


def superficie(pipeline: Any) -> dict[str, Any]:
    """`_serialize_surface(pipeline, tenant_slug="")` della console storica."""
    from web.blueprints.legal_updates_admin import _serialize_surface

    return _serialize_surface(pipeline, tenant_slug="")


def revisore() -> str:
    """Il revisore è l'utente collegato, come `_reviewer_name()` della console storica."""
    from web.blueprints.legal_updates_admin import _reviewer_name

    return _reviewer_name()


def identificativo(valore: Any) -> int | None:
    """Gli indirizzi storici usano `<int:...>`: un valore non numerico non esiste."""
    testo = _t(valore)
    return int(testo) if testo.isdigit() and int(testo) > 0 else None


def azione_motore(chiave: str) -> dict[str, Any]:
    voci = {
        "scan": ("Avvia la ricerca (passo 1)", "primary", "Avviare ora la ricerca nelle fonti verdi del passo 1? L'archivio viene controllato prima, i duplicati restano esclusi."),
        "autopublish": ("Pubblica i contenuti idonei", "primary", "Pubblicare ora i contenuti idonei con la pubblicazione presidiata?"),
        "cleanup": ("Pulisci i duplicati", "danger", "Rimuovere o accorpare i duplicati dell'archivio condiviso da tutti gli studi?"),
    }
    etichetta, tono, conferma = voci[chiave]
    return azione(chiave, etichetta, tone=tono, confirm=conferma)


def esegui_motore(chiave: str) -> dict[str, Any]:
    """`execute_action(action)` storico: stesso servizio, stessi messaggi e toni."""
    from flask import current_app

    from web.services.legal_update_surface import run_legal_update_action

    try:
        risultato = run_legal_update_action(chiave, tenant_slug="")
        current_app.logger.info("Legal updates action %s -> %s", chiave, risultato)
        return esito(True, MESSAGGI_AZIONE_MOTORE.get(chiave, "Operazione completata."))
    except Exception as exc:
        current_app.logger.exception("Errore legal updates action %s", chiave)
        return esito(False, f"Errore durante l'azione «{NOMI_AZIONE_MOTORE.get(chiave, chiave)}»: {exc}")


def filtra(indirizzo: str, values: dict[str, Any], nomi: tuple[str, ...]) -> dict[str, Any]:
    """Filtri della vista storica (modulo GET): si riapre la stessa pagina con la query."""
    parametri = {n: _t(values.get(n)) for n in nomi if _t(values.get(n))}
    destinazione = f"{indirizzo}?{urlencode(parametri)}" if parametri else indirizzo
    return esito(True, "Filtri applicati.", tone="info", navigate=destinazione)


def opzioni(voci: dict[str, str], attuale: str, *, tutte: str) -> list[tuple[str, str]]:
    """Voci di un filtro; un valore della query fuori elenco resta selezionabile."""
    elenco = [("", tutte), *voci.items()]
    if attuale and attuale not in voci:
        elenco.append((attuale, attuale))
    return elenco


def collegamenti(attuale: str) -> list[dict[str, Any]]:
    return [link(etichetta, INDIRIZZI[chiave]) for chiave, etichetta in VOCI_SEZIONE if chiave != attuale]


__all__ = [
    "ACTION_LABELS",
    "BASE",
    "CLASSIFICATION_LABELS",
    "INDIRIZZI",
    "STATUS_LABELS",
    "TONI_STATO_REVISIONE",
    "accenti",
    "azione_motore",
    "classe_lavorazione",
    "collegamenti",
    "confidenza",
    "data",
    "esegui_motore",
    "etichetta_azione",
    "etichetta_classificazione",
    "etichetta_lavorazione",
    "etichetta_stato",
    "filtra",
    "identificativo",
    "leggibile",
    "lessico",
    "motore",
    "opzioni",
    "revisore",
    "superficie",
    "tono_lavorazione",
    "unisci",
]
