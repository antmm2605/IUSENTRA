"""Azioni del deposito amministrativo telematico: dati del procedimento, Excel parti, pacchetto, riepilogo.

Nessuna azione tocca il Portale dell'Avvocato: IUSENTRA prepara e verifica,
l'avvocato compila il Formweb, firma il riepilogo e invia (art. 136 c.p.a.;
regole tecnico-operative d.P.C.S. 2025). La prova di connessione legge solo le
pagine pubbliche del portale.
"""

from __future__ import annotations

import io
import re
import time
import urllib.request
import zipfile
from typing import Any

from flask import current_app

from pct.fascicoli import TipoDocumento
from pct.pat_formweb import catalogo, excel_parti, regole, riepilogo
from pct.pat_formweb.archivio import POSIZIONI
from web.services import pat_formweb_contesto as contesto

_CONNESSIONE: dict[str, Any] = {}
_RUOLI_DEPOSITO = {"atto", "procura", "allegato", "notifica", "contributo"}


def salva_procedimento(fid: str, dati: dict[str, Any]) -> dict[str, Any]:
    contesto.fascicolo_amministrativo(fid)
    pulito: dict[str, Any] = {}
    if "sede" in dati:
        if dati["sede"] and dati["sede"] not in {c for c, _ in catalogo.SEDI.values()}:
            raise ValueError("Sede non presente nell'elenco del Portale dell'Avvocato.")
        pulito["sede"] = dati["sede"]
    if "tipoRicorso" in dati:
        sede = pulito.get("sede") or contesto.contesto(fid)["procedimento"].get("sede") or ""
        codici = {v["codice"] for v in catalogo.tipi_ricorso(sede)}
        if dati["tipoRicorso"] and dati["tipoRicorso"] not in codici:
            raise ValueError("Tipo di ricorso non previsto per questa sede.")
        pulito["tipoRicorso"] = dati["tipoRicorso"]
    if "nrg" in dati:
        valore = re.sub(r"\D", "", str(dati["nrg"] or ""))
        if valore and len(valore) != 9:
            raise ValueError("NRG di 9 cifre: anno e numero, es. 202600123.")
        pulito["nrg"] = valore
    if "posizione" in dati and dati["posizione"] not in POSIZIONI:
        raise ValueError("Posizione dell'assistito non prevista.")
    if "cuTipologia" in dati and dati["cuTipologia"] and dati["cuTipologia"] not in catalogo.CONTRIBUTO:
        raise ValueError("Tipologia del contributo unificato non prevista dal Formweb.")
    if "oggetto" in dati and len(str(dati["oggetto"] or "")) > regole.LIMITE_OGGETTO:
        raise ValueError("L'oggetto supera i 16.000 caratteri ammessi dal Formweb.")
    if "istanze" in dati:
        pulito["istanze"] = [i for i in dati["istanze"] or [] if i in catalogo.ISTANZE_SEGNALABILI]
    if "attoImpugnato" in dati:
        voce = dati["attoImpugnato"] or {}
        pulito["attoImpugnato"] = {k: str(voce.get(k) or "").strip()[:200] for k in ("organo", "tipo", "numero", "anno")}
    for chiave in ("posizione", "cuTipologia", "oggetto", "materia", "esenzione", "fax"):
        if chiave in dati:
            pulito[chiave] = str(dati[chiave] or "").strip()
    for chiave in ("pnrr", "anteCausam", "cassazionista"):
        if chiave in dati:
            pulito[chiave] = bool(dati[chiave])
    if "valore" in dati:
        try:
            pulito["valore"] = float(str(dati["valore"] or 0).replace(".", "").replace(",", ".")) or None
        except ValueError as exc:
            raise ValueError("Valore della controversia non valido.") from exc
    return contesto.archivio().aggiorna_procedimento(fid, pulito)


def ruolo_parte(fid: str, soggetto: str, ruolo: str) -> None:
    contesto.fascicolo_amministrativo(fid)
    contesto.archivio().imposta_ruolo(fid, soggetto, ruolo)


def ruolo_documento(fid: str, documento: str, ruolo: str, descrizione: str = "") -> None:
    fascicolo = contesto.fascicolo_amministrativo(fid)
    if not any(d.id == documento for d in fascicolo.documenti):
        raise LookupError("Documento non presente nel fascicolo.")
    contesto.archivio().imposta_documento(fid, documento, ruolo, descrizione)


def excel(fid: str, ruolo: str) -> tuple[bytes, str]:
    if ruolo not in {"ricorrente", "resistente", "controinteressato"}:
        raise ValueError("Ruolo non previsto dal Formweb.")
    parti = [p for p in contesto.contesto(fid)["parti"] if p["ruolo"] == ruolo]
    plurale = {"ricorrente": "ricorrenti", "resistente": "resistenti", "controinteressato": "controinteressati"}[ruolo]
    return excel_parti.genera(parti), f"Excel_Parti_{plurale}.xlsx"


def _contenuto(fid: str, documento: str) -> bytes:
    from web.services.document_crypto import decrypt_doc

    percorso = contesto._runtime("get_fascicoli").percorso_documento_lettura(fid, documento)
    return decrypt_doc(percorso.read_bytes())


def pacchetto(fid: str) -> tuple[bytes, str]:
    """Zip dei file da caricare con i nomi accettati dal Formweb e un indice con ruolo e impronta SHA-256."""
    ctx = contesto.contesto(fid)
    scelti = [d for d in ctx["documenti"] if d["ruolo"] in _RUOLI_DEPOSITO]
    if not scelti:
        raise ValueError("Nessun documento scelto per il deposito.")
    righe = ["Ruolo;Nome per il Formweb;Descrizione;SHA-256;Esito controlli"]
    uscita = io.BytesIO()
    with zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as archivio:
        for doc in scelti:
            dati = _contenuto(fid, doc["id"])
            controllo = regole.controlla_file(doc["nomeProposto"], dati, doc["ruolo"])
            archivio.writestr(doc["nomeProposto"], dati)
            esiti = "; ".join(e.messaggio for e in controllo.esiti) or "conforme"
            righe.append(";".join([doc["ruolo"], doc["nomeProposto"], doc["descrizione"].replace(";", ","), controllo.sha256, esiti]))
        archivio.writestr("Indice deposito.csv", "\n".join(righe).encode("utf-8-sig"))
    return uscita.getvalue(), f"Deposito PAT {regole.nome_formweb(ctx['fascicolo']['titolo'] or fid)[:60]}.zip"


def verifica_riepilogo(fid: str, nome: str, dati: bytes, tipo: str, salva: bool = True) -> dict[str, Any]:
    if not dati:
        raise ValueError("Carica il riepilogo generato dal Formweb.")
    catalogo.deposito(tipo)
    ctx = contesto.contesto(fid)
    attesi = [{"nome": d["nomeProposto"], "sha256": d["sha256"], "atteso": True}
              for d in ctx["documenti"] if d["ruolo"] in _RUOLI_DEPOSITO and d["sha256"]]
    esito = riepilogo.verifica(dati, nome, attesi).to_dict()
    if salva and esito["leggibile"]:
        gestore = contesto._runtime("get_fascicoli")
        documento = gestore.aggiungi_documento(fid, regole.nome_formweb(nome or "Riepilogo deposito.pdf"), TipoDocumento.ALTRO,
                                               dati, note="Riepilogo deposito Formweb PAT verificato da IUSENTRA",
                                               tags=["PAT", "riepilogo Formweb"], firmato=esito["firma"] in {"pades", "cades"})
        # Il riepilogo è la prova del deposito, non un file da depositare di nuovo.
        contesto.archivio().imposta_documento(fid, documento.id, "escludi", "Riepilogo deposito Formweb")
        try:
            from web.services.registro_letture_runtime import documento_aggiornato

            documento_aggiornato(fid, documento)
        except Exception:
            current_app.logger.warning("Registro letture non aggiornato per il riepilogo PAT di %s", fid, exc_info=True)
    stato = "riepilogo verificato" if esito["conforme"] else "in preparazione"
    deposito = contesto.archivio().registra_deposito(fid, {"tipo": tipo, "stato": stato, "riepilogo": esito})
    return {"ok": True, "esito": esito, "deposito": deposito}


def aggiorna_deposito(fid: str, dati: dict[str, Any]) -> dict[str, Any]:
    contesto.fascicolo_amministrativo(fid)
    if not dati.get("id"):
        catalogo.deposito(str(dati.get("tipo") or ""))
    voce = {k: dati[k] for k in ("id", "tipo", "stato", "identificativo", "note") if k in dati}
    return contesto.archivio().registra_deposito(fid, voce)


def _leggi(url: str, limite: int) -> tuple[int, bytes]:
    richiesta = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA verifica raggiungibilita"})
    with urllib.request.urlopen(richiesta, timeout=6) as risposta:  # noqa: S310 - URL fisso del portale pubblico
        return risposta.status, risposta.read(limite)


def connessione() -> dict[str, Any]:
    """Il Portale dell'Avvocato risponde? Legge solo pagine pubbliche; esito in cache 10 minuti."""
    if _CONNESSIONE and time.monotonic() - _CONNESSIONE["quando"] < 600:
        return _CONNESSIONE["esito"]
    inizio = time.monotonic()
    try:
        stato, pagina = _leggi(catalogo.PORTALE + "/", 200_000)
        stato_modulistica, _ = _leggi(catalogo.PORTALE + "/assets/configs/env.js", 20_000)
        raggiungibile = stato == 200 and stato_modulistica == 200 and b"<siga-root" in pagina
        esito = {"raggiungibile": raggiungibile, "stato": stato, "millisecondi": int((time.monotonic() - inizio) * 1000),
                 "messaggio": "Portale dell'Avvocato raggiungibile: accesso con SPID, CIE o CNS." if raggiungibile
                 else f"Il portale risponde in modo inatteso (HTTP {stato})."}
    except Exception as exc:
        esito = {"raggiungibile": False, "stato": 0, "millisecondi": int((time.monotonic() - inizio) * 1000),
                 "messaggio": f"Portale non raggiungibile: {type(exc).__name__}."}
    _CONNESSIONE.update(quando=time.monotonic(), esito=esito)
    return esito


__all__ = ["aggiorna_deposito", "connessione", "excel", "pacchetto", "ruolo_documento", "ruolo_parte",
           "salva_procedimento", "verifica_riepilogo"]
