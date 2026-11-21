"""Stesura del modello di scrittura sopra lo schema deciso dal codice, con controllo e ritorno al testo deterministico.

Il motore deterministico decide tutto (norme vigenti, rimedio, giudice, termini, importi). Il modello riscrive solo le
sezioni argomentative in prosa forense; il controllore accetta la stesura se:
- ogni norma citata nella stesura è fra le norme dello schema (nessuna norma nuova);
- ogni data e ogni importo della stesura è nello schema, e tutte le date e gli importi di Conclusione e Termini
  dello schema sono nella stesura (nessuna scadenza persa o cambiata).
Altrimenti si riprova una volta e poi si consegna lo schema deterministico, dicendolo. Se il servizio del modello non
risponde, Lex lo dice in chiaro e consegna la parte deterministica.

Configurazione: LEX_HARNESS_SCRITTORE = «ollama:<modello>» oppure «openai:<url base>|<modello>» (server llama.cpp);
vuoto = solo deterministico. LEX_HARNESS_SCRITTORE_TIMEOUT in secondi (predefinito 120).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass

from .controllo import citazioni

_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
_IMPORTO = re.compile(r"€\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")
_SEZIONI_RISCRITTE = ("**Conclusione**", "**Come e perché**", "**Termini**", "**Avvertenze**")

ISTRUZIONI = (
    "Sei l'assistente di uno studio legale italiano. Riscrivi in italiano forense, chiaro e professionale, il PARERE che "
    "segue, in paragrafi discorsivi (niente elenchi puntati). Regole vincolanti: non aggiungere norme, sentenze, fatti, "
    "date o importi che non sono nel testo; riporta tutte le date e tutti gli importi esattamente come sono scritti "
    "(gg/mm/aaaa ed «€ 1.234»); cita le norme solo nella forma usata nel testo (es. «art. 1385 c.c.»); non cambiare le "
    "conclusioni. Rispondi solo con il testo riscritto."
)


@dataclass
class Stesura:
    testo: str
    scrittore: str
    accettata: bool
    motivo: str
    secondi: float


def _sezioni(testo: str) -> tuple[str, str, str]:
    """(prima, da riscrivere, dopo): il blocco va da «Conclusione» all'ultima delle sezioni argomentative consecutive."""
    righe = testo.split("\n")
    titoli = [(i, r.strip().split(" (")[0]) for i, r in enumerate(righe) if r.startswith("**") and r.strip().endswith(("**", ")"))]
    dentro = [i for i, t in titoli if t in _SEZIONI_RISCRITTE]
    if not dentro:
        return testo, "", ""
    inizio = dentro[0]
    fine = next((i for i, t in titoli if i > inizio and t not in _SEZIONI_RISCRITTE), len(righe))
    return "\n".join(righe[:inizio]), "\n".join(righe[inizio:fine]).strip(), "\n".join(righe[fine:])


def controlla(schema: str, stesura: str) -> str:
    """Vuoto se la stesura rispetta lo schema; altrimenti il motivo del rifiuto."""
    norme_schema = {k for _, k in citazioni(schema)}
    nuove = sorted({c for c, k in citazioni(stesura) if k not in norme_schema})
    if nuove:
        return "norme non presenti nello schema: " + ", ".join(nuove)
    date_schema, date_stesura = set(_DATA.findall(schema)), set(_DATA.findall(stesura))
    if date_stesura - date_schema:
        return "date nuove o cambiate: " + ", ".join(sorted(date_stesura - date_schema))
    if date_schema - date_stesura:
        return "date dello schema perse: " + ", ".join(sorted(date_schema - date_stesura))
    imp_schema, imp_stesura = {x.replace(" ", "") for x in _IMPORTO.findall(schema)}, {x.replace(" ", "") for x in _IMPORTO.findall(stesura)}
    if imp_stesura - imp_schema:
        return "importi nuovi o cambiati: " + ", ".join(sorted(imp_stesura - imp_schema))
    if imp_schema - imp_stesura:
        return "importi dello schema persi: " + ", ".join(sorted(imp_schema - imp_stesura))
    # Una norma sparita è un'affermazione persa (la mediazione obbligatoria, la tutela applicabile): la stesura deve
    # citare tutte le norme dello schema.
    norme_stesura = {k for _, k in citazioni(stesura)}
    perse = sorted({c for c, k in citazioni(schema) if k not in norme_stesura})
    if perse:
        return "norme dello schema perse: " + ", ".join(perse)
    if len(stesura.strip()) < 80:
        return "stesura vuota o troppo breve"
    return ""


def _chiama(scrittore: str, testo: str, timeout: float) -> str:
    tipo, _, resto = scrittore.partition(":")
    if tipo == "ollama":
        corpo = {"model": resto, "stream": False, "think": False, "keep_alive": os.environ.get("LEX_HARNESS_KEEP_ALIVE", "10m"),
                 "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1400},
                 "messages": [{"role": "system", "content": ISTRUZIONI}, {"role": "user", "content": testo}]}
        url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
        richiesta = urllib.request.Request(url, json.dumps(corpo).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(richiesta, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"]
    if tipo == "openai":
        base, _, modello = resto.partition("|")
        corpo = {"model": modello or "locale", "temperature": 0.1, "max_tokens": 1400,
                 "chat_template_kwargs": {"enable_thinking": False},
                 "messages": [{"role": "system", "content": ISTRUZIONI}, {"role": "user", "content": testo}]}
        richiesta = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(corpo).encode(),
                                           {"Content-Type": "application/json"})
        with urllib.request.urlopen(richiesta, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    raise ValueError(f"scrittore non riconosciuto: {scrittore}")


def _pulisci(testo: str) -> str:
    testo = re.sub(r"<think>.*?</think>", "", testo, flags=re.S)
    return testo.strip()


def scrivi(testo_deterministico: str, scrittore: str | None = None) -> Stesura:
    scrittore = scrittore if scrittore is not None else os.environ.get("LEX_HARNESS_SCRITTORE", "")
    if not scrittore:
        return Stesura(testo_deterministico, "deterministico", True, "", 0.0)
    prima, blocco, dopo = _sezioni(testo_deterministico)
    if not blocco:
        return Stesura(testo_deterministico, "deterministico", True, "nessuna sezione da riscrivere", 0.0)
    timeout = float(os.environ.get("LEX_HARNESS_SCRITTORE_TIMEOUT", "120"))
    t0 = time.monotonic()
    motivo = ""
    for _ in range(2):
        try:
            stesura = _pulisci(_chiama(scrittore, blocco, timeout))
        except Exception as exc:  # servizio assente, timeout, risposta non leggibile
            nota = (f"\n\n_Il modello di scrittura ({scrittore}) non è disponibile ({type(exc).__name__}): la risposta è "
                    "quella deterministica, con norme, calcoli e termini verificati._")
            return Stesura(testo_deterministico + nota, scrittore, False, f"servizio non disponibile: {type(exc).__name__}",
                           time.monotonic() - t0)
        motivo = controlla(blocco, stesura)
        if not motivo:
            testo = "\n".join(x for x in (prima, "**Parere**", stesura, dopo) if x)
            return Stesura(testo, scrittore, True, "", time.monotonic() - t0)
    nota = f"\n\n_La stesura del modello ({scrittore}) è stata scartata dal controllo ({motivo}): risposta deterministica._"
    return Stesura(testo_deterministico + nota, scrittore, False, motivo, time.monotonic() - t0)
