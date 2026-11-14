"""I pannelli del fascicolo serviti come «pannelli pronti» e le regole per salvarli.

Ogni voce collega un endpoint GET esistente (il suo motore resta l'unico calcolo) al nome del pannello, al
parametro della rotta che identifica il fascicolo e ai parametri della richiesta che non cambiano il payload.
Le regole di salvataggio escludono gli errori. La Lettura conserva l'ultimo esito consultivo
anche durante le verifiche; l'impronta SQL rende visibili gli esiti successivi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pct import __version__ as APP_VERSION

VERSIONE_PANNELLI = f"{APP_VERSION}:quadro-processuale-v26"

# Parametri che non cambiano il payload: anti-cache dei browser e segnali della richiesta.
PARAMETRI_IGNORATI_SEMPRE = frozenset({"_", "t", "ts", "nocache"})


def _json(corpo: bytes) -> Any:
    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def esito_valido(corpo: bytes) -> bool:
    """Il payload descrive un risultato, non un errore: si può salvare."""
    dati = _json(corpo)
    if not isinstance(dati, dict):
        return dati is not None
    if dati.get("ok") is False or dati.get("errore") or dati.get("error"):
        return False
    return not dati.get("mock_fallback")


def _lettura_valida(corpo: bytes) -> bool:
    dati = _json(corpo) or {}
    lettura = dati.get("lettura") if isinstance(dati, dict) else None
    if not esito_valido(corpo) or not isinstance(lettura, dict):
        return False
    # Il flag descrive i presìdi in corso, non un errore della Lettura.
    # Gli esiti completi e le variazioni del registro invalidano l'impronta.
    return True


def _letture_valide(corpo: bytes) -> bool:
    dati = _json(corpo) or {}
    letture = dati.get("letture") if isinstance(dati, dict) else None
    return esito_valido(corpo) and isinstance(letture, dict) and not letture.get("degradato")


@dataclass(frozen=True)
class Pannello:
    nome: str
    endpoint: str
    parametro_fascicolo: str = "id_fasc"
    # Percorso canonico della richiesta (``{fid}`` = fascicolo).
    percorso: str = ""
    # Pannello della prima apertura: il ricalcolo in sfondo lo prepara anche prima che l'avvocato lo chieda,
    # per i fascicoli aperti di recente.
    prima_apertura: bool = False
    parametri_ignorati: frozenset[str] = field(default_factory=frozenset)
    # Parametri con cui la richiesta non è una consultazione (es. «aggiorna» della Lettura): si calcola sempre.
    parametri_di_calcolo: frozenset[str] = field(default_factory=frozenset)
    memorizzabile: Callable[[bytes], bool] = esito_valido
    # Parte del payload che dipende dall'utente e dal momento dell'apertura: si ricompone a ogni risposta.
    ricomponi: str = ""
    # Dipendenze incorporate nel payload salvato. Le righe ricomposte a ogni accesso non richiedono invalidazione.
    dipende_da: tuple[str, ...] = ()
    # Con ``confirm_revision=1`` la risposta porta la revisione dei domini letta adesso (aggiornamento dal vivo
    # della pagina): il payload si serve dal salvato e la revisione si legge al momento.
    domini_revisione: tuple[str, ...] = ()


_UI = "/api/v1/ui/fascicoli/{fid}"
# Gli stessi domini che la vista del dettaglio conferma con ``confirm_revision=1`` (api_v1_react).
DOMINI_DETTAGLIO = ("clienti", "soggetti", "fascicoli", "agenda", "scadenze", "comunicazioni", "fatturazione",
                    "incassi", "preventivi", "timesheet")

PANNELLI: tuple[Pannello, ...] = (
    Pannello("dettaglio", "api_v1_react.fascicolo_react_dettaglio", percorso=_UI, prima_apertura=True,
             parametri_ignorati=frozenset({"confirm_revision"}), ricomponi="lettura_del_dettaglio",
             domini_revisione=DOMINI_DETTAGLIO),
    Pannello("quadro", "api_v1_react.fascicolo_react_quadro", percorso=_UI + "/quadro", prima_apertura=True,
             ricomponi="quadro_da_lettura"),
    Pannello("scadenze", "api_v1_react.fascicolo_react_scadenze", percorso=_UI + "/scadenze", prima_apertura=True, dipende_da=("lettura",)),
    Pannello("documenti", "api_v1_react.fascicolo_react_documenti", percorso=_UI + "/documenti", prima_apertura=True),
    Pannello("lettura", "api_v1_react.fascicolo_react_lettura", percorso=_UI + "/lettura", prima_apertura=True,
             parametri_di_calcolo=frozenset({"aggiorna"}), memorizzabile=_lettura_valida, ricomponi="stato_presidi_lettura"),
    Pannello("regia", "api_v1_react.fascicolo_regia_operativa", percorso=_UI + "/regia", prima_apertura=True, dipende_da=("lettura",)),
    Pannello("obblighi-notifica", "api_v1_react.fascicolo_react_obblighi_notifica",
             percorso=_UI + "/obblighi-notifica", prima_apertura=True, dipende_da=("lettura",)),
    Pannello("attivita", "api_v1_react.fascicolo_react_attivita", percorso=_UI + "/attivita"),
    Pannello("depositi", "api_v1_react.fascicolo_react_depositi", percorso=_UI + "/depositi"),
    Pannello("relata", "api_v1_react.fascicolo_react_relata", percorso=_UI + "/relata"),
    Pannello("lex", "api_v1_react.fascicolo_react_lex", percorso=_UI + "/lex"),
    Pannello("letture", "api_v1_react.fascicolo_react_letture", percorso=_UI + "/letture", parametri_ignorati=frozenset({"visto"}),
             memorizzabile=_letture_valide, ricomponi="novita_letture"),
    Pannello("letture-parti", "api_v1_react.fascicolo_react_letture_parti", percorso=_UI + "/letture/parti"),
    Pannello("letture-prospetti", "api_v1_react.fascicolo_react_letture_prospetti", percorso=_UI + "/letture/prospetti"),
    Pannello("letture-sentenza", "api_v1_react.fascicolo_react_letture_sentenza", percorso=_UI + "/letture/sentenza", prima_apertura=True),
    Pannello("provenienza-ai", "api_v1_react.fascicolo_react_provenienza_ai", percorso=_UI + "/provenienza-ai"),
    Pannello("conto-economico", "api_v1_react.fascicolo_react_conto_economico", percorso=_UI + "/conto-economico", prima_apertura=True, dipende_da=("lettura",)),
    Pannello("checklist", "api_v1_react.fascicolo_regia_checklist", percorso=_UI + "/checklist"),
    Pannello("redazione-atti-contesto", "api_v1_react.redazione_atti_contesto_fascicolo",
             percorso="/api/v1/ui/redazione-atti/fascicoli/{fid}/contesto", parametro_fascicolo="id_fascicolo",
             dipende_da=("lettura",)),
    Pannello("catalogazione-documentale", "api_v1_documenti_ai.catalogazione_documentale_fascicolo", percorso=_UI + "/catalogazione-documentale",
             parametro_fascicolo="fascicolo_id"),
    Pannello("guida-pratica", "api_v1_guida_pratica.guida_pratica_fascicolo", percorso=_UI + "/guida-pratica"),
    Pannello("passaggi", "api_v1_passaggi.fascicolo_passaggi", percorso=_UI + "/passaggi"),
)

PER_ENDPOINT = {p.endpoint: p for p in PANNELLI}
DIPENDENTI = {nome: tuple(p.nome for p in PANNELLI if nome in p.dipende_da) for nome in {p.nome for p in PANNELLI}}
PRIMA_APERTURA = tuple(p for p in PANNELLI if p.prima_apertura)
