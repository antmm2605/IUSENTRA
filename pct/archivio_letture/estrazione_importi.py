"""Gli importi letti dai documenti diventano fatti dell'archivio.

Il presidio economico apriva i PDF dal disco a ogni richiesta dell'avvocato per
ricavare contributo unificato, compenso liquidato, esborsi e fondo spese: gli
stessi documenti, riletti ogni volta, dentro il tempo di risposta. Qui quella
lettura passa dove devono stare tutte: nei due motori, una volta sola, con il
collaudo e la prova.

Le regole di estrazione **non si riscrivono**: restano dove sono già dichiarate
e verificate, in `pct/fascicolo_sentenza_economica.py`
(`analyze_sentenza_tribunale_text` per la sentenza,
`extract_contributo_unificato_document_evidence` per il contributo unificato da
ricevuta o da PagoPA). Questo modulo le chiama e ne traduce l'esito in fatti,
così una regola economica si cambia in un punto solo e vale per tutti.

Base normativa degli importi letti: D.P.R. 115/2002 art. 13 (contributo
unificato e suoi scaglioni), D.M. 55/2014 e D.M. 147/2022 (liquidazione del
compenso e rimborso forfettario), art. 91 c.p.c. (condanna alle spese).
"""

from __future__ import annotations

from typing import Any
import re

from pct.registro_letture.fatti_repository import Fatto

from .ancoraggio import brano

VERSIONE_ESTRAZIONE_IMPORTI = "2026.09.18.importi.v3+ricevuta-telematica"

# Campo del fatto → etichetta italiana e norma che lo governa.
CAMPI_IMPORTO: dict[str, tuple[str, str]] = {
    "contributo_unificato": ("Contributo unificato", "D.P.R. 115/2002 art. 13"),
    "liquidazione_giudice": ("Compenso liquidato dal giudice", "D.M. 55/2014; art. 91 c.p.c."),
    "spese_esborsi": ("Spese ed esborsi", "art. 91 c.p.c."),
    "fondo_spese": ("Fondo spese", "art. 91 c.p.c."),
    "beneficio_cliente": ("Importo riconosciuto al cliente", "dispositivo della sentenza"),
}
# Oltre questa soglia un importo letto da un atto non è un compenso né una spesa:
# è un valore di causa o un numero letto male, e non si propone come fatto.
IMPORTO_MASSIMO = 10_000_000.0


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _importo(valore: Any) -> float | None:
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return None
    if numero <= 0 or numero > IMPORTO_MASSIMO:
        return None
    return round(numero, 2)


#: il giorno del versamento in una ricevuta: si accetta solo se ancorato a una
#: delle formule della ricevuta stessa, mai una data qualsiasi del documento
_RE_DATA_VERSAMENTO = re.compile(
    r"data\s+(?:del\s+)?(?:pagament\w+|versament\w+|esito|operazione)\s*[:\-]?\s*"
    r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
    re.I,
)


def data_dalla_ricevuta_telematica(testo: str) -> str:
    """Il giorno del versamento letto dalla RT pagoPA, non indovinato dal testo.

    La ricevuta telematica di giustizia e' un documento a struttura dichiarata
    (schema ``PagamentiTelematiciGiustizia``, namespace DigitPA): il giorno del
    versamento sta in ``dataEsitoSingoloPagamento``, e in sua mancanza nella
    data del messaggio di ricevuta. Leggerlo dallo schema e' piu' sicuro che
    cercarlo nella prosa, perche' la RT non ha prosa: cercare «data pagamento»
    in un XML non trova nulla.

    Base normativa: art. 4 c. 9 D.L. 193/2009 (pagamento telematico del
    contributo unificato) e specifiche pagoPA del Ministero della Giustizia.
    """
    from pct.pagamenti_giustizia import e_ricevuta_telematica, parse_rt
    from pct.registro_letture.verifica_date import interpreta_data

    grezzo = str(testo or "")
    if "<" not in grezzo or "RT" not in grezzo:
        return ""
    try:
        dati = grezzo.encode("utf-8", "ignore")
        if not e_ricevuta_telematica(dati):
            return ""
        ricevuta = parse_rt(dati)
    except Exception:
        return ""
    if ricevuta is None or not ricevuta.pagamento_eseguito:
        # Una RT con esito diverso da «eseguito» non prova un versamento:
        # dichiarare la sua data come giorno di pagamento sarebbe falso.
        return ""
    for candidata in (ricevuta.data_esito_pagamento, ricevuta.data_ricevuta):
        giorno = interpreta_data(str(candidata or "").split("T", 1)[0])
        if giorno:
            return giorno.strftime("%d/%m/%Y")
    return ""


def data_del_versamento(testo: str) -> str:
    """Il giorno del versamento dichiarato nella ricevuta, in formato italiano.

    All'avvocato la data serve quanto l'importo: una voce che dice «pagato» ma
    non quando non prova granche'. Si accetta solo la data ancorata alle
    formule della ricevuta — «data pagamento», «data versamento», «data esito»
    — oppure, quando la ricevuta e' la RT telematica, il campo che lo schema
    ministeriale dedica al versamento; e solo se e' una data del calendario:
    una data qualsiasi trovata nel documento non e' il giorno del versamento.
    """
    from pct.registro_letture.verifica_date import interpreta_data

    dallo_schema = data_dalla_ricevuta_telematica(testo)
    if dallo_schema:
        return dallo_schema
    trovata = _RE_DATA_VERSAMENTO.search(str(testo or ""))
    if not trovata:
        return ""
    giorno = interpreta_data(trovata.group(1))
    return giorno.strftime("%d/%m/%Y") if giorno else ""


def _fatto(campo: str, importo: float, *, titolo: str, testo: str, origine: str, natura: str = "") -> Fatto:
    etichetta, norma = CAMPI_IMPORTO[campo]
    posizione = testo.find(titolo[:40]) if titolo else -1
    contesto = brano(testo, posizione, posizione + len(titolo)) if posizione >= 0 else _testo(titolo)[:300]
    return Fatto(
        categoria="importo",
        campo=campo,
        valore=f"{importo:.2f}",
        valore_letto=_testo(titolo)[:200],
        etichetta=f"{etichetta} € {importo:,.2f}".replace(",", "§").replace(".", ",").replace("§", "."),
        contesto=contesto or _testo(titolo)[:300],
        posizione=max(0, posizione),
        origine=origine,
        prove=[{"codice": "norma", "esito": "ok", "dettaglio": norma}] + ([{"codice": "natura", "esito": "ok", "dettaglio": natura}] if natura else []),
    )


def importi_dalla_sentenza(testo: str, *, metadata: dict[str, Any] | None = None, origine: str = "") -> list[Fatto]:
    """Compenso liquidato, esborsi, fondo spese e beneficio dal dispositivo della sentenza."""
    from pct.fascicolo_sentenza_economica import analyze_sentenza_tribunale_text, validate_sentenza_fascicolo_context

    grezzo = str(testo or "")
    if not grezzo.strip():
        return []
    meta = metadata or {}
    try:
        esito = analyze_sentenza_tribunale_text(grezzo, meta)
    except Exception:
        return []
    if not getattr(esito, "found", False):
        return []
    fascicolo = meta.get("fascicolo")
    if fascicolo is None:
        # Senza il fascicolo non si puo' dire se questa sentenza sia la nostra:
        # una liquidazione attribuita alla pratica sbagliata diventa una voce in
        # parcella e una proforma verso un cliente che non c'entra. Chi legge un
        # documento deve dichiarare per quale fascicolo lo sta leggendo; qui non
        # si indovina e non si estrae nulla.
        return []
    try:
        contesto = validate_sentenza_fascicolo_context(
            text=grezzo,
            extraction=esito,
            fascicolo=fascicolo,
            metadata=meta,
            fascicolo_id=_testo(getattr(fascicolo, "id", "")),
        )
    except Exception:
        return []
    if not contesto.ok:
        # Una sentenza usata come precedente o materiale istruttorio può
        # stare nel fascicolo, ma non deve alimentare incassi, fatturazione
        # o passi economici se non conferma insieme cliente e RG.
        return []
    coppie = (
        ("liquidazione_giudice", esito.liquidazione_importo, esito.liquidazione_titolo),
        ("spese_esborsi", esito.spese_esborsi_importo, esito.spese_esborsi_titolo),
        ("fondo_spese", esito.fondo_spese_importo, esito.fondo_spese_titolo),
        ("beneficio_cliente", esito.beneficio_cliente_importo, esito.beneficio_cliente_titolo),
        ("contributo_unificato", esito.contributo_unificato_importo, esito.contributo_unificato_titolo),
    )
    fatti: list[Fatto] = []
    for campo, grezzo_importo, titolo in coppie:
        importo = _importo(grezzo_importo)
        if importo is None:
            continue
        fatti.append(_fatto(campo, importo, titolo=titolo or "", testo=grezzo, origine=origine, natura="dispositivo della sentenza"))
    return fatti


def importo_contributo_unificato(testo: str, *, metadata: dict[str, Any] | None = None, origine: str = "") -> list[Fatto]:
    """Il contributo unificato da una ricevuta di pagamento o da un modello PagoPA."""
    from pct.fascicolo_sentenza_economica import extract_contributo_unificato_document_evidence

    grezzo = str(testo or "")
    if not grezzo.strip():
        return []
    try:
        evidenza = extract_contributo_unificato_document_evidence(grezzo, metadata or {})
    except Exception:
        return []
    if not isinstance(evidenza, dict):
        return []
    if evidenza.get("esente") is True and re.search(r"contributo\s+unificato", grezzo, re.I) and re.search(r"esenzion|esent", grezzo, re.I):
        # This proves the document declares an exemption, not eligibility.
        return [Fatto(categoria="evento", campo="esenzione_cu_dichiarata", valore="dichiarazione_presente",
            etichetta="Dichiarazione di esenzione dal contributo unificato",
            contesto=_testo(evidenza.get("titolo") or "Esenzione dichiarata nel documento"),
            origine=origine, verifica="verificata" if origine == "nativo" else "plausibile",
            prove=[{"codice":"dichiarazione_esenzione", "esito":"ok", "dettaglio":"Dichiarazione presente; nessuna attestazione automatica dei requisiti reddituali."}])]
    importo = _importo(evidenza.get("importo"))
    if importo is None:
        return []
    natura = _testo(evidenza.get("natura") or evidenza.get("origine"))
    fatto = _fatto(
        "contributo_unificato", importo,
        titolo=_testo(evidenza.get("titolo") or evidenza.get("label")), testo=grezzo, origine=origine, natura=natura,
    )
    stato = _testo(evidenza.get("status"))
    if stato:
        fatto.prove = list(fatto.prove) + [{"codice": "stato", "esito": "ok", "dettaglio": stato}]
    quando = data_del_versamento(grezzo)
    if quando:
        fatto.prove = list(fatto.prove) + [{"codice": "data", "esito": "ok", "dettaglio": quando}]
    return [fatto]


def estrai_importi(testo: str, *, metadata: dict[str, Any] | None = None, origine: str = "") -> list[Fatto]:
    """Tutti gli importi che le regole dichiarate riconoscono nel documento, senza doppioni."""
    fatti = importi_dalla_sentenza(testo, metadata=metadata, origine=origine) + importo_contributo_unificato(testo, metadata=metadata, origine=origine)
    visti: set[tuple[str, str]] = set()
    unici: list[Fatto] = []
    for fatto in fatti:
        chiave = (fatto.campo, fatto.valore)
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(fatto)
    return unici


__all__ = [
    "CAMPI_IMPORTO", "IMPORTO_MASSIMO", "VERSIONE_ESTRAZIONE_IMPORTI",
    "data_dalla_ricevuta_telematica", "data_del_versamento",
    "estrai_importi", "importi_dalla_sentenza", "importo_contributo_unificato",
]
