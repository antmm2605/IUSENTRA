"""Azioni del deposito tributario telematico: salvataggi, controlli dei file, pacchetto, termini, depositi.

Base normativa in ``pct/ptt_sigit``. Nessuna azione deposita: il deposito si
fa dall'area riservata del PTT con SPID, CIE o CNS.
"""

from __future__ import annotations

import csv
import io
import time
import urllib.request
import zipfile
from datetime import date
from typing import Any

from flask import current_app

from pct.ptt_sigit import catalogo, regole
from pct.ptt_sigit.archivio import POSIZIONI
from web.services import ptt_sigit_contesto as contesto

_CAMPI_ATTO = ("tipo", "numero", "ufficio", "dataNotifica", "periodo", "tributo", "sanzioni", "indeterminabile", "materia",
               "tributo_tipo", "importo")


def _data(valore: Any) -> str:
    testo = str(valore or "").strip()[:10]
    if not testo:
        return ""
    try:
        return date.fromisoformat(testo).isoformat()
    except ValueError as exc:
        raise ValueError("Data non valida: usa il calendario (gg/mm/aaaa).") from exc


def _importo(valore: Any) -> str:
    testo = str(valore or "").strip().replace("€", "").replace(" ", "")
    if not testo:
        return ""
    normale = testo.replace(".", "").replace(",", ".") if "," in testo else testo
    try:
        return f"{float(normale):.2f}"
    except ValueError as exc:
        raise ValueError("Importo non valido.") from exc


def _atto(voce: dict[str, Any]) -> dict[str, Any]:
    atto = {k: voce.get(k) for k in _CAMPI_ATTO if k in voce}
    if atto.get("tipo") and atto["tipo"] not in catalogo.ATTI_IMPUGNATI:
        raise ValueError("Atto impugnato non presente nella Tabella B della NIR.")
    if atto.get("materia") and atto["materia"] not in catalogo.MATERIE:
        raise ValueError("Materia procedimentale non prevista dalla NIR.")
    if atto.get("tributo_tipo") and atto["tributo_tipo"] not in catalogo.TRIBUTI:
        raise ValueError("Tributo non previsto dalla NIR.")
    for chiave in ("tributo", "sanzioni", "importo"):
        if chiave in atto:
            atto[chiave] = _importo(atto[chiave])
    if "dataNotifica" in atto:
        atto["dataNotifica"] = _data(atto["dataNotifica"])
    atto["indeterminabile"] = bool(atto.get("indeterminabile"))
    for chiave in ("numero", "ufficio", "periodo"):
        atto[chiave] = str(atto.get(chiave) or "").strip()[:120]
    return atto


def salva_procedimento(fid: str, dati: dict[str, Any]) -> dict[str, Any]:
    contesto.fascicolo_tributario(fid)
    pulito: dict[str, Any] = {}
    if "corte" in dati:
        corte = catalogo.sede(str(dati["corte"] or "")) if dati["corte"] else None
        if dati["corte"] and corte is None:
            raise ValueError("Corte non presente nell'elenco del DGT.")
        pulito["corte"] = dati["corte"] or ""
        if corte:
            pulito["grado"] = corte["grado"]
    if "posizione" in dati:
        if dati["posizione"] not in POSIZIONI:
            raise ValueError("Posizione della parte non prevista.")
        pulito["posizione"] = dati["posizione"]
    if "atto" in dati and dati["atto"] and dati["atto"] not in catalogo.ATTI_PRINCIPALI + catalogo.ALTRI_ATTI:
        raise ValueError("Atto non previsto dalle Appendici A e C delle istruzioni PTT.")
    if "pubblicaUdienza" in dati and dati["pubblicaUdienza"] and dati["pubblicaUdienza"] not in catalogo.PUBBLICA_UDIENZA:
        raise ValueError("Modalità di trattazione non prevista.")
    for chiave in ("cutModalita", "cutEsenzione"):
        if dati.get(chiave) and dati[chiave] not in catalogo.MODALITA_CUT:
            raise ValueError("Modalità di pagamento del CUT non prevista.")
    for chiave in ("atto", "pubblicaUdienza", "cutModalita", "cutEsenzione", "cutEstremi", "rg", "note"):
        if chiave in dati:
            pulito[chiave] = str(dati[chiave] or "").strip()[:500]
    for chiave in ("notificaRicorso", "cutData"):
        if chiave in dati:
            pulito[chiave] = _data(dati[chiave])
    for chiave in ("sospensione", "prova"):
        if chiave in dati:
            pulito[chiave] = bool(dati[chiave])
    if "atti" in dati:
        pulito["atti"] = [_atto(v) for v in (dati["atti"] or [])[:20] if isinstance(v, dict)]
    if "sentenza" in dati:
        voce = dati["sentenza"] or {}
        pulito["sentenza"] = {k: str(voce.get(k) or "").strip()[:120] for k in ("corte", "numero", "sezione", "anno", "data")}
    return contesto.archivio().aggiorna_procedimento(fid, pulito)


def ruolo_documento(fid: str, documento: str, ruolo: str, tipologia: str = "", descrizione: str = "") -> None:
    fascicolo = contesto.fascicolo_tributario(fid)
    if not any(d.id == documento for d in fascicolo.documenti or []):
        raise LookupError("Documento non trovato nel fascicolo.")
    if ruolo == "allegato" and tipologia and tipologia not in catalogo.ALLEGATI:
        raise ValueError("Tipologia non presente nell'Appendice B delle istruzioni PTT.")
    contesto.archivio().imposta_documento(fid, documento, ruolo, tipologia, descrizione)


def _contenuto(fid: str, documento: str) -> bytes:
    from web.services.document_crypto import decrypt_doc

    percorso = contesto._runtime("get_fascicoli").percorso_documento_lettura(fid, documento)
    return decrypt_doc(percorso.read_bytes())


def controlla_file(fid: str) -> dict[str, Any]:
    """Controlli che il SIGIT fa dopo la trasmissione (PDF/A, elementi attivi, collegamenti), eseguiti prima dell'invio."""
    ctx = contesto.contesto(fid)
    file = []
    for doc in ctx["documenti"]:
        if doc["ruolo"] == "escludi":
            continue
        esiti = list(doc["esiti"])
        if regole.formato(doc["nome"]) == "pdf" and doc["firma"] != "cades":
            try:
                esiti += [e.to_dict() for e in regole.controlla_contenuto(_contenuto(fid, doc["id"]))]
            except Exception:
                current_app.logger.warning("Controllo PTT non eseguito su %s/%s", fid, doc["id"], exc_info=True)
                esiti.append({"codice": "LETTURA", "livello": "avviso", "messaggio": "File non leggibile per il controllo: verificalo nel SIGIT."})
        file.append({"id": doc["id"], "nome": doc["nome"], "ruolo": doc["ruolo"], "dimensione": doc["dimensione"], "esiti": esiti,
                     "bloccante": any(e["livello"] == "errore" for e in esiti)})
    deposito = [e.to_dict() for e in regole.controlla_deposito(file)]
    return {"file": file, "deposito": deposito, "conforme": not deposito and not any(f["bloccante"] for f in file),
            "controllatoIl": date.today().isoformat()}


def pacchetto(fid: str) -> tuple[bytes, str]:
    """Zip con i file da caricare nel SIGIT, nell'ordine (prima l'atto) e con l'indice delle impronte."""
    ctx = contesto.contesto(fid)
    ordinati = [d for d in ctx["documenti"] if d["ruolo"] == "atto"] + [d for d in ctx["documenti"] if d["ruolo"] == "allegato"]
    if not ordinati:
        raise ValueError("Nessun file da depositare: indica l'atto principale nella scheda Documenti.")
    buffer, indice = io.BytesIO(), io.StringIO()
    righe = csv.writer(indice, delimiter=";")
    righe.writerow(["Ordine", "File", "Ruolo", "Tipologia", "Firma", "SHA-256", "Controlli"])
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivio_zip:
        for numero, doc in enumerate(ordinati, start=1):
            nome = f"{numero:02d} {doc['nome']}"[: regole.LIMITE_NOME]
            archivio_zip.writestr(nome, _contenuto(fid, doc["id"]))
            righe.writerow([numero, nome, doc["ruolo"], doc["tipologia"], doc["firma"], doc["sha256"],
                            "; ".join(e["messaggio"] for e in doc["esiti"]) or "ok"])
        archivio_zip.writestr("Indice deposito PTT.csv", "﻿" + indice.getvalue())
    return buffer.getvalue(), f"Deposito PTT {ctx['fascicolo']['titolo'][:60]}.zip".replace("/", "-")


def registra_termine(fid: str, termine_id: str) -> dict[str, Any]:
    """Porta nello scadenziario un termine calcolato (costituzione, controdeduzioni, ricorso), senza doppioni."""
    from pct.scadenziario import TipoTermine

    ctx = contesto.contesto(fid)
    voce = next((t for t in ctx["termini"] if t["id"] == termine_id), None)
    if voce is None:
        raise LookupError("Termine non calcolabile: indica le date nel procedimento.")
    scadenziario = contesto._runtime("get_scadenziario")
    titolo = f"PTT - {voce['titolo']}"
    esistente = next((s for s in scadenziario.tutte(id_fascicolo=fid, solo_aperte=False) if s.titolo == titolo), None)
    if esistente is not None:
        return {"ok": True, "gia": True, "scadenza": voce["scadenza"]}
    scadenziario.nuova(titolo, TipoTermine.DEPOSITO_ATTO, voce["scadenza"], id_fascicolo=fid,
                       descrizione=voce["norma"], perentorio=bool(voce.get("perentorio")))
    return {"ok": True, "gia": False, "scadenza": voce["scadenza"]}


def aggiorna_deposito(fid: str, dati: dict[str, Any]) -> dict[str, Any]:
    contesto.fascicolo_tributario(fid)
    if not dati.get("id"):
        catalogo.deposito(str(dati.get("tipo") or ""))
    voce = {k: str(dati[k] or "").strip()[:300] for k in ("id", "tipo", "stato", "ricevuta", "rg", "note") if k in dati}
    return contesto.archivio().registra_deposito(fid, voce)


def _leggi(url: str, limite: int) -> tuple[int, bytes]:
    richiesta = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA-verifica-PTT"})
    with urllib.request.urlopen(richiesta, timeout=8) as risposta:  # noqa: S310 - URL fissi del SIGIT
        return risposta.status, risposta.read(limite)


_CONNESSIONE: dict[str, Any] = {}


def connessione() -> dict[str, Any]:
    """Raggiungibilità della pagina pubblica di accesso al PTT (nessuna credenziale, cache 10 minuti)."""
    if _CONNESSIONE and time.time() - _CONNESSIONE["quando"] < 600:
        return dict(_CONNESSIONE["esito"])
    inizio = time.time()
    try:
        stato, pagina = _leggi(catalogo.PORTALE, 200_000)
        raggiungibile = stato == 200 and b"Processo Tributario Telematico" in pagina
        esito = {"raggiungibile": raggiungibile, "millisecondi": int((time.time() - inizio) * 1000),
                 "messaggio": "Area riservata del PTT raggiungibile." if raggiungibile else "Il SIGIT ha risposto in modo inatteso."}
    except Exception as exc:
        esito = {"raggiungibile": False, "millisecondi": int((time.time() - inizio) * 1000),
                 "messaggio": f"SIGIT non raggiungibile: {type(exc).__name__}."}
    esito["verificatoIl"] = time.strftime("%d/%m/%Y %H:%M")
    esito["url"] = catalogo.PORTALE
    _CONNESSIONE.update({"quando": time.time(), "esito": esito})
    return dict(esito)


__all__ = ["aggiorna_deposito", "connessione", "controlla_file", "pacchetto", "registra_termine", "ruolo_documento", "salva_procedimento"]
