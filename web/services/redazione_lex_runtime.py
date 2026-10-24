"""Stesura delle parti narrative (blocchi «scrive_lex» della scheda) da parte di Lex nella redazione guidata.

Il codice decide, Lex scrive: dati del fascicolo risolti dalla scheda (gestionale + archivio delle letture, nessuna
lettura di documenti nella richiesta), scadenze dal calcolatore, Fonti della scheda con testo vigente e provenienza
dalla biblioteca dei codici e delle leggi. Lex gira solo su un provider locale (llama.cpp o Ollama): gli atti dello
studio non escono dal server. Revisione indipendente e stato della consegna accompagnano sempre i blocchi; nulla
viene inserito nell'atto senza che l'avvocato lo scelga.
Base normativa: le norme dichiarate in ciascuna scheda (``base_normativa``); art. 13 L. 247/2012 e art. 14 CDF
(responsabilita' dell'avvocato sull'atto, che resta bozza da revisionare).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lex.procedura_atti.fonti_scheda import fonti_per_scheda
from lex.procedura_atti.stesura_blocchi import risolvi_citazioni, scrivi_blocchi, termini_da_scadenze
from pct.schede_lex import blocco_scadenze, scadenze_calcolate

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")
PROVIDER_LOCALI = ("llamacpp", "ollama", "lmstudio")


def provider_locale(gateway) -> str:
    """Il primo provider locale abilitato, preferendo quello indicato in LEX_STESURA_PROVIDER."""
    preferito = os.getenv("LEX_STESURA_PROVIDER", "").strip()
    abilitati = [n for n in PROVIDER_LOCALI if n in getattr(gateway, "providers", {})
                 and gateway.config.providers[n].is_local]
    if preferito in abilitati:
        return preferito
    return abilitati[0] if abilitati else ""


def chiamata_gateway(gateway, user_id: str, provider: str):
    def chiama(sistema: str, messaggio: str):
        risposta = gateway.ask(user_id=user_id, prompt=messaggio, task="redazione_atto", requested_provider=provider,
                               system_prompt=sistema, max_tokens=4096,
                               extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        return risposta.content, f"{risposta.provider}:{risposta.model}"
    return chiama


def _testo_fatti(fascicolo: Any) -> str:
    try:
        from web.services.archivio_letture_runtime import fatti_fascicolo

        fatti = fatti_fascicolo(fascicolo) if fascicolo is not None else []
    except Exception:
        logger.warning("Fatti letti non disponibili per la stesura di Lex")
        fatti = []
    righe = []
    for f in fatti:
        d = f if isinstance(f, dict) else getattr(f, "__dict__", {})
        righe.append(" ".join(str(d.get(k) or "") for k in ("campo", "valore", "contesto") if d.get(k)))
    return "\n".join(r for r in righe if r.strip())


def nome_cliente(cliente: Any) -> str:
    if cliente is None:
        return ""
    rs = str(getattr(cliente, "ragione_sociale", "") or "").strip()
    return rs or f"{getattr(cliente, 'nome', '') or ''} {getattr(cliente, 'cognome', '') or ''}".strip()


def stesura(*, model_code: str, risolta: dict, fascicolo: Any, cliente: Any, oggetto: str, ruolo_assistito: str,
            biblioteca: Path, chiama_modello, campi_modello: list[str]) -> dict:
    oggi = datetime.now(ROME_TZ).date()
    from web.services.schede_fonti_runtime import repository

    fonti = fonti_per_scheda(risolta["scheda"], Path(biblioteca), repository=repository(Path(biblioteca)), oggi=oggi)
    scadenze = scadenze_calcolate(risolta)
    esito = scrivi_blocchi(chiama_modello=chiama_modello, oggetto=oggetto, risolta=risolta, fonti=fonti,
                           blocco_scadenze=blocco_scadenze(risolta), termini=termini_da_scadenze(scadenze),
                           fatti_testo=_testo_fatti(fascicolo), oggi=oggi, assistito=nome_cliente(cliente),
                           controparte=str(getattr(fascicolo, "controparte", "") or ""), campi_modello=campi_modello,
                           ruolo_assistito=ruolo_assistito)
    return {"modello": model_code, "blocchi": [{"blocco": b, "testo": risolvi_citazioni(t, fonti.fonti_ref), "campo": esito.campi.get(b, "")}
                                                for b, t in esito.blocchi.items()],
            "revisione": {k: [list(x) for x in v] for k, v in esito.revisione.items()},
            "statoConsegna": esito.stato_consegna, "modelloAi": esito.modello_ai,
            "fonti": [dict(r) for r in fonti.fonti_ref],
            "pendenzeFonti": list(fonti.pendenze), "scadenze": scadenze}
