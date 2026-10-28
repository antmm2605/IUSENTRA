"""Stesura delle parti narrative (blocchi «scrive_lex» della scheda) da parte di Lex nella redazione guidata.

Il codice decide, Lex scrive: dati del fascicolo risolti dalla scheda (gestionale + archivio delle letture, nessuna
lettura di documenti nella richiesta), scadenze dal calcolatore, Fonti della scheda con testo vigente e provenienza
dalla biblioteca dei codici e delle leggi. Lex usa il provider locale configurato, anche sul PC dello studio
tramite rete privata cifrata: nessun ripiego su altri modelli quando il provider è esplicito. Revisione indipendente e stato della consegna accompagnano sempre i blocchi; nulla
viene inserito nell'atto senza che l'avvocato lo scelga.
Base normativa: le norme dichiarate in ciascuna scheda (``base_normativa``); art. 13 L. 247/2012 e art. 14 CDF
(responsabilita' dell'avvocato sull'atto, che resta bozza da revisionare).
"""
from __future__ import annotations

import logging
import os
import sqlite3
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
    """Provider esplicito vincolante; scelta locale automatica solo senza configurazione."""
    preferito = os.getenv("LEX_STESURA_PROVIDER", "").strip()
    abilitati = [n for n in PROVIDER_LOCALI if n in getattr(gateway, "providers", {})
                 and gateway.config.providers[n].is_local]
    if preferito:
        return preferito if preferito in abilitati else ""
    return abilitati[0] if abilitati else ""


def chiamata_gateway(gateway, user_id: str, provider: str):
    def chiama(sistema: str, messaggio: str):
        misura = None
        if callable(getattr(chiama, "misura_prompt", None)):
            import requests
            try:
                misura = chiama.misura_prompt(sistema, messaggio)
            except requests.RequestException as exc:
                raise ValueError("Il servizio locale non ha consentito la verifica del contesto: nessuna stesura parziale è stata inviata") from exc
            if misura["tokens_input"] + 4096 > misura["contesto"]:
                raise ValueError("Il prompt supera il contesto reale del modello: nessuna fonte è stata troncata o inviata parzialmente")
            chiama.ultimo_preflight = misura
        risposta = gateway.ask(user_id=user_id, prompt=messaggio, task="redazione_atto", requested_provider=provider, allow_external=False,
                               system_prompt=sistema, max_tokens=4096,
                               extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        chiama.ultimo_uso = {"tokens_input":getattr(risposta,"tokens_input",None),"tokens_output":getattr(risposta,"tokens_output",None)}
        if misura is not None:
            actual = getattr(risposta,"tokens_input",None)
            chiama.ultimo_uso["tokens_input_misurati"]=misura["tokens_input"]
            chiama.ultimo_uso["ricezione_integrale_riscontrata"]=type(actual) is int and actual==misura["tokens_input"]
            if chiama.ultimo_uso["ricezione_integrale_riscontrata"] is not True:
                raise ValueError("Il conteggio del prompt ricevuto non corrisponde al tokenizer verificato: stesura non attestabile, nessun inserimento nell'atto")
        return risposta.content, f"{risposta.provider}:{risposta.model}"
    runtime = getattr(gateway, "providers", {}).get(provider)
    if provider == "llamacpp" and callable(getattr(runtime, "misura_prompt", None)):
        chiama.misura_prompt = runtime.misura_prompt
    return chiama


def _fatti_archiviati(fascicolo: Any) -> list:
    try:
        from web.services.archivio_letture_runtime import fatti_fascicolo

        return fatti_fascicolo(fascicolo) if fascicolo is not None else []
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        raise ValueError("Le letture del fascicolo non sono disponibili: riprovare prima della stesura.") from exc

def _testo_fatti(fascicolo: Any, *, fatti: list | None = None) -> str:
    fatti = _fatti_archiviati(fascicolo) if fatti is None else fatti

    righe = []
    for f in fatti:  # gia' filtrati dall'archivio: solo verificati, plausibili o corretti dall'avvocato
        leggi = (lambda k: f.get(k)) if isinstance(f, dict) else (lambda k: getattr(f, k, ""))
        if str(leggi("verifica") or "") in {"respinto", "respinta", "ignorata"} or leggi("categoria") == "evento" and leggi("campo") == "impronta_testo_atto":
            continue
        etichetta = str(leggi("etichetta") or leggi("campo") or leggi("categoria") or "")
        stato = "verificato" if leggi("verifica") in {"verificata", "corretta"} else "letto, da confermare"
        righe.append(f"- {leggi('categoria')} / {etichetta}: {leggi('valore')} ({stato})")
    return "\n".join(r for r in righe if r.strip())



def _eventi_normativi(fatti: list) -> dict:
    import re
    from datetime import date

    eventi={};discordanti=set()
    for fact in fatti:
        get=(lambda k:fact.get(k)) if isinstance(fact,dict) else (lambda k:getattr(fact,k,""))
        key=str(get("campo") or "")
        sha=str(get("sha256") or "")
        value=str(get("valore") or "")
        if get("verifica") not in {"verificata","corretta"} or not key or not re.fullmatch(r"[0-9a-fA-F]{64}",sha):
            continue
        try:
            when=datetime.strptime(value,"%d/%m/%Y").date() if "/" in value else date.fromisoformat(value)
        except ValueError:
            continue
        if key in eventi and eventi[key]["data"]!=when.isoformat():
            discordanti.add(key);continue
        eventi[key]={"data":when.isoformat(),"confermato":True,"fonte_sha256":sha}
    return {k:v for k,v in eventi.items() if k not in discordanti}

def nome_cliente(cliente: Any) -> str:
    if cliente is None:
        return ""
    rs = str(getattr(cliente, "ragione_sociale", "") or "").strip()
    return rs or f"{getattr(cliente, 'nome', '') or ''} {getattr(cliente, 'cognome', '') or ''}".strip()


def stesura(*, model_code: str, risolta: dict, fascicolo: Any, cliente: Any, oggetto: str, ruolo_assistito: str,
            biblioteca: Path, chiama_modello, campi_modello: list[str], studio_db=None) -> dict:
    oggi = datetime.now(ROME_TZ).date()
    from web.services.schede_fonti_runtime import RepositoryFontiStudio

    # Una mancanza della biblioteca non autorizza mai a scrivere nell'archivio generale.
    if Path(biblioteca).name == "normattiva.sqlite":
        from lex.retrieval.normativa_catalog import library_path
        biblioteca=library_path(Path(biblioteca))
    if not Path(biblioteca).is_file():
        # Un mount non disponibile non deve diventare una nuova biblioteca vuota.
        # L'archivio viene predisposto dalla procedura nativa di acquisizione,
        # mai sostituito durante la stesura con un database creato implicitamente.
        raise ValueError("Biblioteca normativa configurata non disponibile: ripristinare l'archivio prima della stesura; nessun database vuoto è stato creato")
    fonti = fonti_per_scheda(risolta["scheda"], Path(biblioteca), repository=RepositoryFontiStudio(Path(biblioteca), studio_db), oggi=oggi)
    from lex.normativa.biblioteca.ricerca_fonti import integra_fonti

    fatti_letti = _fatti_archiviati(fascicolo)
    fatti = _testo_fatti(fascicolo,fatti=fatti_letti)
    richiesta_fonti = f"Atto: {risolta.get('titolo', model_code)}\nParte assistita: {nome_cliente(cliente)}\nRuolo: {ruolo_assistito}\nRichiesta: {oggetto}"
    ricerca_fonti = integra_fonti(fonti, richiesta=richiesta_fonti, fatti=fatti, biblioteca=Path(biblioteca),
                                  chiama_modello=chiama_modello, oggi=oggi,eventi=_eventi_normativi(fatti_letti))
    scadenze = scadenze_calcolate(risolta)
    esito = scrivi_blocchi(chiama_modello=chiama_modello, oggetto=oggetto, risolta=risolta, fonti=fonti,
                           blocco_scadenze=blocco_scadenze(risolta), termini=termini_da_scadenze(scadenze),
                           fatti_testo=fatti, oggi=oggi, assistito=nome_cliente(cliente),
                           controparte=str(getattr(fascicolo, "controparte", "") or ""), campi_modello=campi_modello,
                           ruolo_assistito=ruolo_assistito)
    return {"modello": model_code, "blocchi": [{"blocco": b, "testo": risolvi_citazioni(t, fonti.fonti_ref), "campo": esito.campi.get(b, "")}
                                                for b, t in esito.blocchi.items()],
            "revisione": {k: [list(x) for x in v] for k, v in esito.revisione.items()},
            "statoConsegna": esito.stato_consegna, "modelloAi": esito.modello_ai,
            "fonti": [dict(r, testo=fonti.fonti.get(int(r["n"]), "")) for r in fonti.fonti_ref],
            "pendenzeFonti": list(fonti.pendenze), "ricercaFonti": ricerca_fonti, "lettureFonti": esito.letture_fonti, "scadenze": scadenze,
            "primaStesura": esito.prima_stesura, "numeroStesure": esito.numero_stesure,
            "revisionePrimaStesura": esito.revisione_prima_stesura}
