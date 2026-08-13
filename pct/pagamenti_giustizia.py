"""Ricevute telematiche (RT) dei pagamenti di giustizia pagoPA.

Base normativa: art. 4 c.9 D.L. 193/2009 (pagamenti telematici di giustizia),
art. 5 CAD; schema ministeriale ``PagamentiTelematiciGiustizia`` (XSD 6.0.1 e
6.2.0 versionati in ``docs/specs/ministero/``, namespace
``http://www.digitpa.gov.it/schemas/2011/Pagamenti/``), vademecum pagamenti
PST (regole operative in ``docs/specs/ministero/PAGAMENTI_TELEMATICI_PST_PAT_PTT``).

La prova tecnica del pagamento nei servizi telematici e' la ricevuta
``RT.xml`` (il promemoria PDF non la sostituisce). Questo modulo la legge e la
verifica: esito, importo, IUV, data. Non esegue ne' avvia pagamenti: il
pagamento avviene sul canale ufficiale pagoPA/PST con autenticazione
dell'avvocato; qui si riconcilia solo la ricevuta scaricata.

Fail-closed: una RT con esito diverso da "eseguito" o con importo incoerente
con il contributo dichiarato in DatiAtto produce avvisi bloccanti/professionali
nella simulazione busta, mai un deposito silenziosamente difforme.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

# Esiti del pagamento come da XSD ministeriale (ctDatiVersamentoRT).
ESITI_RT: dict[str, str] = {
    "0": "Pagamento eseguito",
    "1": "Pagamento non eseguito",
    "2": "Pagamento parzialmente eseguito",
    "3": "Decorrenza termini",
    "4": "Decorrenza termini parziale",
}

# Tolleranza di riconciliazione importi (centesimo).
_TOLLERANZA_EURO = 0.005


@dataclass
class RicevutaTelematica:
    """RT pagoPA di giustizia normalizzata (schema PagamentiTelematiciGiustizia)."""

    esito_codice: str = ""
    importo_totale: float = 0.0
    iuv: str = ""  # identificativoUnivocoVersamento
    codice_contesto_pagamento: str = ""
    data_ricevuta: str = ""  # dataOraMessaggioRicevuta (ISO 8601)
    ente_beneficiario: str = ""
    pagatore: str = ""
    causale: str = ""
    iur: list[str] = field(default_factory=list)  # identificativoUnivocoRiscossione
    avvisi: list[str] = field(default_factory=list)

    @property
    def esito_label(self) -> str:
        return ESITI_RT.get(self.esito_codice, f"Esito sconosciuto ({self.esito_codice})")

    @property
    def pagamento_eseguito(self) -> bool:
        return self.esito_codice == "0" and self.importo_totale > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "esito_codice": self.esito_codice,
            "esito": self.esito_label,
            "importo_totale": round(self.importo_totale, 2),
            "iuv": self.iuv,
            "codice_contesto_pagamento": self.codice_contesto_pagamento,
            "data_ricevuta": self.data_ricevuta,
            "ente_beneficiario": self.ente_beneficiario,
            "pagatore": self.pagatore,
            "causale": self.causale,
            "iur": list(self.iur),
            "pagamento_eseguito": self.pagamento_eseguito,
            "avvisi": list(self.avvisi),
        }


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_text(root: ET.Element, localname: str) -> str:
    for el in root.iter():
        if _local(el.tag) == localname and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _find_all_text(root: ET.Element, localname: str) -> list[str]:
    return [
        el.text.strip()
        for el in root.iter()
        if _local(el.tag) == localname and el.text and el.text.strip()
    ]


def _sblocca_payload(data: bytes) -> bytes:
    """Se la RT e' firmata CAdES (.p7m), estrae il contenuto XML sottoscritto."""

    testa = data.lstrip()[:200]
    if testa.startswith(b"<?xml") or testa.startswith(b"<"):
        return data
    try:
        from pct.firma import estrai_contenuto_cades  # noqa: PLC0415

        payload = estrai_contenuto_cades(data)
        if payload:
            return payload
    except Exception:
        pass
    return data


def _parse_xml_sicuro(data: bytes) -> ET.Element:
    """Estrae l'eventuale CAdES e analizza XML senza DTD o entita'."""

    return DefusedET.fromstring(_sblocca_payload(data))


def e_ricevuta_telematica(data: bytes) -> bool:
    """True se i byte sono una RT pagoPA (radice ``RT`` dello schema ministeriale)."""

    try:
        root = _parse_xml_sicuro(data)
    except (ET.ParseError, DefusedXmlException):
        return False
    return _local(root.tag) == "RT"


def parse_rt(data: bytes) -> RicevutaTelematica | None:
    """Legge una RT.xml (anche .p7m) e la normalizza. None se non e' una RT."""

    try:
        root = _parse_xml_sicuro(data)
    except (ET.ParseError, DefusedXmlException):
        return None
    if _local(root.tag) != "RT":
        return None

    rt = RicevutaTelematica(
        esito_codice=_find_text(root, "codiceEsitoPagamento"),
        iuv=_find_text(root, "identificativoUnivocoVersamento"),
        codice_contesto_pagamento=_find_text(root, "CodiceContestoPagamento")
        or _find_text(root, "codiceContestoPagamento"),
        data_ricevuta=_find_text(root, "dataOraMessaggioRicevuta"),
        causale=_find_text(root, "causaleVersamento"),
        iur=_find_all_text(root, "identificativoUnivocoRiscossione"),
    )
    raw_importo = _find_text(root, "importoTotalePagato")
    try:
        rt.importo_totale = round(float(raw_importo), 2) if raw_importo else 0.0
    except ValueError:
        rt.avvisi.append(f"Importo totale non numerico nella RT: {raw_importo!r}")

    # Denominazioni: dentro enteBeneficiario/soggettoPagatore.
    for el in root.iter():
        name = _local(el.tag)
        if name == "enteBeneficiario" and not rt.ente_beneficiario:
            rt.ente_beneficiario = _find_text(el, "denominazioneBeneficiario")
        elif name == "soggettoPagatore" and not rt.pagatore:
            rt.pagatore = _find_text(el, "anagraficaPagatore")

    if not rt.esito_codice:
        rt.avvisi.append("La RT non riporta il codice esito del pagamento.")
    if not rt.iuv:
        rt.avvisi.append("La RT non riporta lo IUV (identificativo univoco versamento).")
    return rt


def verifica_rt_per_deposito(
    rt: RicevutaTelematica,
    *,
    importo_atteso: float | None = None,
    filename: str = "RT.xml",
    pagamento_richiesto: bool = True,
) -> list[dict[str, Any]]:
    """Controlli della RT nel contesto di un deposito. Formato issues della busta.

    Tutti gli esiti sono avvisi professionali (WARN), mai blocchi: la decisione
    sull'invio resta all'avvocato, che conferma e procede. Casi coperti:

    - esito diverso da "eseguito" o importo zero → avviso che la ricevuta non
      prova il pagamento (vademecum PST); se il deposito e' esente o prenotato
      a debito (es. autocertificazione reddituale art. 9 c.1-bis D.P.R.
      115/2002 nei giudizi di lavoro, o patrocinio a spese dello Stato) il
      pagamento non e' dovuto → avviso di probabile allegato errato;
    - importo diverso dal contributo dichiarato in DatiAtto → avviso
      (frazionamenti e diritti aggiuntivi sono legittimi: decide l'avvocato).
    """

    fonte = "Schema PagamentiTelematiciGiustizia (pagoPA) + vademecum pagamenti PST"
    issues: list[dict[str, Any]] = []
    if not rt.pagamento_eseguito:
        if pagamento_richiesto:
            issues.append(
                {
                    "code": "RT-ESITO-NEGATIVO",
                    "level": "WARN",
                    "title": f"Ricevuta {filename}: pagamento non provato",
                    "detail": (
                        f"La ricevuta telematica riporta esito '{rt.esito_label}' e importo "
                        f"{rt.importo_totale:.2f} EUR: non prova un pagamento eseguito. "
                        "Confermando, l'invio procede sotto responsabilita' professionale."
                    ),
                    "source": fonte,
                    "suggested_action": (
                        "Completa il pagamento su pagoPA/PST e scarica la RT con esito positivo, "
                        "oppure conferma e procedi se il pagamento e' provato altrimenti."
                    ),
                }
            )
        else:
            issues.append(
                {
                    "code": "RT-NON-NECESSARIA",
                    "level": "WARN",
                    "title": f"Ricevuta {filename}: allegato probabilmente errato",
                    "detail": (
                        f"Il deposito non dichiara un contributo pagato (esenzione o prenotazione "
                        f"a debito, D.P.R. 115/2002) ma e' allegata una ricevuta telematica con "
                        f"esito '{rt.esito_label}'."
                    ),
                    "source": fonte,
                    "suggested_action": (
                        "Verifica se l'allegato serve davvero a questo deposito o rimuovilo."
                    ),
                }
            )
        return issues
    if importo_atteso is not None and importo_atteso > 0:
        if abs(rt.importo_totale - float(importo_atteso)) > _TOLLERANZA_EURO:
            issues.append(
                {
                    "code": "RT-IMPORTO-DIFFORME",
                    "level": "WARN",
                    "title": f"Ricevuta {filename}: importo diverso dal contributo dichiarato",
                    "detail": (
                        f"La RT prova {rt.importo_totale:.2f} EUR ma il DatiAtto dichiara "
                        f"{float(importo_atteso):.2f} EUR di contributo unificato. Con pagamento "
                        "frazionato vanno allegate tutte le ricevute (vademecum PST)."
                    ),
                    "source": fonte,
                    "suggested_action": (
                        "Verifica l'importo dovuto o allega le ulteriori ricevute telematiche "
                        "dei versamenti frazionati."
                    ),
                }
            )
    return issues


def riepilogo_rt_allegate(
    allegati: list[tuple[str, bytes]],
    *,
    importo_atteso: float | None = None,
    pagamento_richiesto: bool = True,
) -> dict[str, Any]:
    """Analizza gli allegati di una busta: RT trovate, totale provato, issues.

    ``allegati``: coppie (filename, contenuto). Ritorna un riepilogo con le RT
    parse, la somma degli importi eseguiti e gli avvisi da propagare alla
    simulazione busta.
    """

    ricevute: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    totale = 0.0
    iuv_visti: set[str] = set()
    for filename, contenuto in allegati:
        rt = parse_rt(contenuto)
        if rt is None:
            continue
        if rt.iuv and rt.iuv in iuv_visti:
            issues.append(
                {
                    "code": "RT-DUPLICATA",
                    "level": "WARN",
                    "title": f"Ricevuta {filename}: IUV gia' presente in busta",
                    "detail": (
                        f"Lo IUV {rt.iuv} compare in piu' ricevute allegate: la stessa "
                        "ricevuta non puo' provare due versamenti."
                    ),
                    "source": "Vademecum pagamenti PST (stati DISPONIBILE/USATO)",
                    "suggested_action": "Rimuovi il duplicato o allega la ricevuta corretta.",
                }
            )
        if rt.iuv:
            iuv_visti.add(rt.iuv)
        ricevute.append({"filename": filename, **rt.to_dict()})
        if rt.pagamento_eseguito:
            totale += rt.importo_totale
        issues.extend(
            verifica_rt_per_deposito(
                rt,
                importo_atteso=None,
                filename=filename,
                pagamento_richiesto=pagamento_richiesto,
            )
        )
    totale = round(totale, 2)
    if ricevute and importo_atteso is not None and importo_atteso > 0:
        if abs(totale - float(importo_atteso)) > _TOLLERANZA_EURO:
            issues.append(
                {
                    "code": "RT-TOTALE-DIFFORME",
                    "level": "WARN",
                    "title": "Ricevute telematiche: totale diverso dal contributo dichiarato",
                    "detail": (
                        f"Le RT allegate provano {totale:.2f} EUR complessivi ma il DatiAtto "
                        f"dichiara {float(importo_atteso):.2f} EUR di contributo unificato."
                    ),
                    "source": "Schema PagamentiTelematiciGiustizia (pagoPA) + vademecum pagamenti PST",
                    "suggested_action": (
                        "Verifica l'importo dovuto o completa le ricevute dei versamenti frazionati."
                    ),
                }
            )
    return {
        "ricevute": ricevute,
        "totale_eseguito": totale,
        "issues": issues,
    }
