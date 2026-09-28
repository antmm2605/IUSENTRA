"""Chiamate SOAP 1.1 minime verso i servizi di firma remota (ARSS di Aruba e Actalis, SWS di Namirial).

Si costruisce solo l'XML che i WSDL pubblici descrivono (copie in
docs/specs/ministero/fonti_ufficiali/2026-09-28/firma/): elemento dell'operazione
qualificato con il namespace del servizio, figli non qualificati
(``elementFormDefault="unqualified"``), nell'ordine della sequenza dello schema.
"""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlparse

from lxml import etree

from pct.firma_remota.base import FirmaRemotaError

SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TIMEOUT_SECONDI = 45


def valida_endpoint(url: str) -> str:
    """Solo HTTPS verso un host vero: niente indirizzi locali presi dalla configurazione per errore."""
    indirizzo = str(url or "").strip()
    parti = urlparse(indirizzo)
    if parti.scheme != "https" or not parti.hostname:
        raise FirmaRemotaError("L'indirizzo del servizio di firma remota deve iniziare con https://.")
    if parti.hostname in {"localhost", "127.0.0.1", "::1"} or parti.hostname.endswith(".local"):
        raise FirmaRemotaError("L'indirizzo del servizio di firma remota non può essere un indirizzo locale.")
    return indirizzo


def elemento(nome: str, figli: Iterable[tuple[str, Any]] = ()) -> etree._Element:
    """Un elemento non qualificato con i figli nell'ordine dato (valori None saltati)."""
    nodo = etree.Element(nome)
    for chiave, valore in figli:
        if valore is None:
            continue
        if isinstance(valore, etree._Element):
            valore.tag = chiave
            nodo.append(valore)
            continue
        figlio = etree.SubElement(nodo, chiave)
        figlio.text = ("true" if valore else "false") if isinstance(valore, bool) else str(valore)
    return nodo


def chiama(url: str, namespace: str, operazione: str, argomenti: Iterable[tuple[str, Any]], *,
           sessione: Any = None, timeout: int = TIMEOUT_SECONDI) -> etree._Element:
    """Invia la richiesta e restituisce l'elemento ``<operazioneResponse>``; i Fault diventano FirmaRemotaError."""
    import requests

    busta = etree.Element(f"{{{SOAP_ENV}}}Envelope", nsmap={"soapenv": SOAP_ENV, "ns": namespace})
    corpo = etree.SubElement(busta, f"{{{SOAP_ENV}}}Body")
    richiesta = etree.SubElement(corpo, f"{{{namespace}}}{operazione}")
    for figlio in elemento("x", argomenti):
        richiesta.append(figlio)
    dati = etree.tostring(busta, xml_declaration=True, encoding="utf-8")
    client = sessione or requests
    try:
        risposta = client.post(valida_endpoint(url), data=dati, timeout=timeout, headers={
            "Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'})
    except requests.RequestException as exc:
        raise FirmaRemotaError("Il servizio di firma remota non risponde: riprova tra qualche istante.") from exc
    try:
        radice = etree.fromstring(risposta.content)
    except etree.XMLSyntaxError as exc:
        raise FirmaRemotaError(f"Risposta non valida dal servizio di firma remota (HTTP {risposta.status_code}).") from exc
    fault = radice.find(f".//{{{SOAP_ENV}}}Fault")
    if fault is not None:
        testo = (fault.findtext("faultstring") or "errore del servizio").strip()
        raise FirmaRemotaError(f"Il prestatore ha rifiutato la richiesta: {testo}")
    esito = radice.find(f".//{{{namespace}}}{operazione}Response")
    if esito is None:
        raise FirmaRemotaError(f"Risposta inattesa dal servizio di firma remota (HTTP {risposta.status_code}).")
    return esito


def testo(nodo: etree._Element | None, percorso: str) -> str:
    if nodo is None:
        return ""
    return str(nodo.findtext(percorso) or "").strip()


__all__ = ["chiama", "elemento", "testo", "valida_endpoint"]
