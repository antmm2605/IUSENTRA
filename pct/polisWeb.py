"""
pct/polisWeb.py — Integrazione con il Portale Servizi Telematici (PST)
                   del Ministero della Giustizia.

Offre due blocchi funzionali:

A) CONSULTAZIONE (lettura):
   - RicercaFascicoliRegistro: cerca pratiche nel registro civile/penale
   - ConsultazioneAvanzataDocumenti: recupera documenti dal fascicolo telematico
   → Usa i web service SOAP ufficiali PST (autenticazione con certificato P12)

B) DEPOSITO (scrittura):
   - Il deposito civile avviene già via PEC + busta .enc (pct/deposito.py)
   - PolisWeb NON è il canale di deposito: è un portale di consultazione
   → Per il deposito usare DepositoCivile in pct/deposito.py

Requisiti:
  - pip install zeep  (SOAP client)
  - Certificato P12 del professionista (già configurato come PCT_FIRMA_P12)

Riferimenti:
  - Specifiche PST/PCT: https://pst.giustizia.it/PST/it/page_1_0.wp
  - DM 44/2011 e Provvedimento DGSIA del 18/7/2011
"""
from __future__ import annotations

import os
import re
import ssl
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pct.pst_servizi_catalogo import SERVIZIO_PST_DOCUMENTI_FASCICOLO
from pct.uffici_giudiziari import risolvi_base_pst, risolvi_codice_ministero, risolvi_ufficio

# ---------------------------------------------------------------- PST endpoints
# I web service del PST sono accessibili con autenticazione a certificato.
# Dal 2026 l'endpoint storico wspa.giustizia.it risulta legacy: il gestionale
# richiede quindi che l'eventuale proxy attivo venga configurato esplicitamente.
_PST_LEGACY_BASE = "https://wspa.giustizia.it/wspa"
_WSP_BASE = (os.getenv("PCT_PST_BASE_URL", _PST_LEGACY_BASE) or _PST_LEGACY_BASE).strip()
_PST_SERVICE_ALIASES = {
    "JPW_CASS": "JPW_CASSCI",
}
_PST_QBUILDER_NAMESPACES = {
    "JPW_SICID": "urn:CONS-SICC-BE",
    "JPW_SIECIC": "urn:CONS-SIECIC-BE",
    "JPW_SIGP": "urn:CONS-SIGP-BE",
    "JPW_CASSCI": "urn:CONS-CASSCI",
    "JPW_CASSPE": "urn:CONS-CASSPE",
}
_CF_PATTERN = re.compile(r"\b([A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z])\b")


def _pst_endpoint_legacy(base_url: str) -> bool:
    return base_url.startswith(_PST_LEGACY_BASE)


def _pst_endpoint_legacy_message() -> str:
    return (
        "L'endpoint PST configurato in IUSENTRA punta ancora a wspa.giustizia.it, "
        "host legacy non più pubblicato nel DNS pubblico. "
        "Con il nuovo registro uffici IUSENTRA prova a comporre automaticamente il proxy corretto; "
        "se l'ufficio non ha metadati PST configurare PCT_PST_BASE_URL completo o almeno il root proxy."
    )


def _wsdl_ricerca(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/RicercaFascicoliRegistroService?wsdl"


def _wsdl_consultazione(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/ConsultazioneAvanzataDocumentiService?wsdl"


def _pst_servizio_proxy(base_url: str) -> str:
    parti = [p for p in (base_url or "").rstrip("/").split("/") if p]
    servizio = (parti[-1] if parti else "").upper()
    return _PST_SERVICE_ALIASES.get(servizio, servizio)


def _pst_namespace_qbuilder(base_url: str) -> str:
    return _PST_QBUILDER_NAMESPACES.get(_pst_servizio_proxy(base_url), "")


def _pst_usa_qbuilder(base_url: str) -> bool:
    return bool(_pst_namespace_qbuilder(base_url))


def _strip_namespaces(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _parse_qbuilder_row(row_el: ET.Element) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    sub_rows: Dict[str, List[Dict[str, Any]]] = {}

    for child in list(row_el):
        tag = child.tag.split("}")[-1]
        if tag == "property":
            key = (child.attrib.get("name") or "").strip()
            if key:
                row[key] = (child.text or "").strip()
        elif tag == "subRows":
            cls_name = (child.attrib.get("class") or "subRows").strip()
            rows: List[Dict[str, Any]] = []
            for sub in list(child):
                sub_tag = sub.tag.split("}")[-1]
                if sub_tag != "row":
                    continue
                rows.append(_parse_qbuilder_row(sub))
            sub_rows.setdefault(cls_name, []).extend(rows)

    if sub_rows:
        row["_sub_rows"] = sub_rows
    return row


def _parse_qbuilder_row_list(xml_text: str) -> List[Dict[str, Any]]:
    try:
        root = _strip_namespaces(ET.fromstring(xml_text))
    except ET.ParseError:
        return []

    righe: List[Dict[str, Any]] = []
    for ret in root.findall(".//return"):
        for child in list(ret):
            tag = child.tag.split("}")[-1]
            if tag == "subRows":
                continue
            if tag == "row":
                righe.append(_parse_qbuilder_row(child))
                continue
            for nested in list(child):
                nested_tag = nested.tag.split("}")[-1]
                if nested_tag == "row":
                    righe.append(_parse_qbuilder_row(nested))
    return righe


def _qbuilder_numero_rg(row: Dict[str, Any]) -> str:
    valore = (
        row.get("NUMERORUOLO")
        or row.get("N_R_G")
        or row.get("NUMERORG")
        or row.get("NUMERORUOLOGENERALE")
        or ""
    )
    valore = str(valore).strip()
    if not valore:
        return ""
    if valore.isdigit():
        return str(int(valore))
    return valore


def _qbuilder_tipo_documento(tipo: str) -> str:
    valore = (tipo or "").strip()
    if not valore or valore in {"%", "*"}:
        return "Documento"
    if "}" in valore:
        valore = valore.rsplit("}", 1)[-1]
    if ":" in valore:
        valore = valore.rsplit(":", 1)[-1]
    return valore or "Documento"


def _qbuilder_parti_dettaglio(row: Dict[str, Any]) -> List[Dict[str, str]]:
    dettagli: List[Dict[str, str]] = []
    sub_rows = row.get("_sub_rows") or {}
    for gruppo, righe in sub_rows.items():
        if gruppo not in {"InfoParte", "Parte", "ParteProcessuale"}:
            continue
        for parte in righe:
            cognome = (parte.get("COGNOME") or "").strip()
            nome = (parte.get("NOME") or "").strip()
            cognome_nome = (parte.get("COGNOMENOME") or "").strip()
            full_name = (parte.get("NOMINATIVO") or "").strip()
            if not full_name:
                if cognome and nome:
                    full_name = f"{cognome} {nome}"
                else:
                    full_name = cognome_nome
            if not full_name:
                continue
            dettagli.append(
                {
                    "nome": re.sub(r"\s+", " ", full_name),
                    "cognome": re.sub(r"\s+", " ", cognome),
                    "nome_proprio": re.sub(r"\s+", " ", nome),
                    "tipo": (parte.get("TIPOPARTE") or parte.get("PARTE") or "").strip(),
                    "codice_fiscale": (parte.get("CODICEFISCALEPARTE") or parte.get("CODICEFISCALE") or "").strip(),
                    "avvocato": (parte.get("AVVOCATO") or parte.get("NOMEAVVOCATO") or "").strip(),
                    "cf_avvocato": (parte.get("CODICEFISCALEAVVOCATO") or parte.get("CFAVVOCATO") or "").strip(),
                }
            )
    return dettagli


def _map_qbuilder_fascicolo(row: Dict[str, Any]) -> FascicoloPolisWeb:
    codice_ufficio = (
        row.get("IDUFFICIO")
        or row.get("CODICEUFFICIO")
        or row.get("UFFICIO")
        or ""
    ).strip()
    ufficio = risolvi_ufficio(codice_ufficio) if codice_ufficio else None
    parti_dettaglio = _qbuilder_parti_dettaglio(row)
    parti = [p["nome"] for p in parti_dettaglio if p.get("nome")]

    if not parti:
        for key in ("ATTOREPRINCIPALE", "CONVENUTOPRINCIPALE", "PARTEPRINCIPALE"):
            valore = (row.get(key) or "").strip()
            if valore:
                parti.append(valore)

    return FascicoloPolisWeb(
        numero_rg=_qbuilder_numero_rg(row),
        anno_rg=int((row.get("ANNORUOLO") or row.get("ANNORG") or 0) or 0),
        ruolo=(row.get("RUOLODESCRIZIONE") or row.get("RUOLO") or "").strip(),
        stato=(row.get("STATOFASCICOLODESCRIZIONE") or row.get("STATOFASCICOLO") or "").strip(),
        oggetto=(row.get("OGGETTOFASCICOLO") or row.get("OGGETTO") or "").strip(),
        sezione=(row.get("SEZIONE") or row.get("DESCRIZIONESEZIONE") or "").strip(),
        giudice=(row.get("GIUDICE") or row.get("MAGISTRATO") or "").strip(),
        data_iscrizione=_parse_data((row.get("DATAISCRIZIONERUOLO") or row.get("DATAISCRIZIONE") or "").strip()),
        data_udienza=_parse_data((row.get("DATAPROSSIMAUDIENZA") or row.get("DATAUDIENZA") or "").strip()),
        parti=parti,
        parti_dettaglio=parti_dettaglio,
        codice_ufficio=codice_ufficio,
        nome_ufficio=(ufficio or {}).get("nome", "") if isinstance(ufficio, dict) else "",
        note="",
    )


def _map_qbuilder_documento(row: Dict[str, Any]) -> DocumentoPolisWeb:
    id_documento = (
        row.get("IDDOCUMENTO")
        or row.get("NUMERODOCUMENTO")
        or row.get("IDDOCMITTENTE")
        or ""
    ).strip()
    tipo = _qbuilder_tipo_documento(row.get("TIPO") or row.get("TIPODOCUMENTO") or "")
    nome = (row.get("NOMEFILE") or row.get("NOME") or "").strip()
    if not nome:
        nome = f"Documento_{id_documento}.pdf" if id_documento else "Documento.pdf"
    return DocumentoPolisWeb(
        id_documento=id_documento,
        nome=nome,
        tipo=tipo,
        data_deposito=(row.get("DATADEPOSITO") or row.get("DATACREAZIONE") or "").strip(),
        mittente=(row.get("AUTORE") or row.get("MITTENTE") or "").strip(),
        dimensione_bytes=int((row.get("DIMENSIONE") or 0) or 0),
        disponibile=(row.get("STATO") or "").strip().lower() != "non disponibile",
        id_deposito=(row.get("IDBUSTA") or row.get("IDDEPOSITO") or "").strip(),
        tipo_atto=tipo,
    )


_DOCUMENTO_SOAP_ATTRS = (
    "idDocumento",
    "id",
    "nomeFile",
    "nome",
    "tipoDocumento",
    "tipo",
    "dataDeposito",
    "mittente",
    "cfMittente",
    "dimensione",
    "disponibile",
    "idDeposito",
    "idBusta",
    "tipoAtto",
    "descTipoAtto",
    "tipoAtta",
)


def _soap_getattr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _soap_documento_fields(obj: Any) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for name in _DOCUMENTO_SOAP_ATTRS:
            value = obj.get(name)
            if value not in (None, "", [], ()):
                values[name] = value
        return values

    for name in _DOCUMENTO_SOAP_ATTRS:
        value = _soap_getattr(obj, name)
        if value not in (None, "", [], ()):
            values[name] = value
    return values


def _is_soap_documento_item(obj: Any) -> bool:
    fields = _soap_documento_fields(obj)
    return any(
        fields.get(name) not in (None, "")
        for name in ("idDocumento", "nomeFile", "nome", "tipoDocumento", "tipo", "dataDeposito", "idDeposito", "idBusta")
    )


def _collect_soap_documenti(payload: Any) -> List[Any]:
    items: List[Any] = []
    stack: List[Any] = [payload]
    seen: set[int] = set()
    attr_candidates = (
        "documenti",
        "documento",
        "return",
        "return_",
        "returns",
        "item",
        "items",
        "listaDocumenti",
        "elencoDocumenti",
        "result",
        "value",
        "_value_1",
    )

    while stack:
        current = stack.pop(0)
        if current is None or isinstance(current, (str, bytes, int, float, bool)):
            continue
        if isinstance(current, (list, tuple, set)):
            stack.extend(list(current))
            continue

        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)

        if _is_soap_documento_item(current):
            items.append(current)
            continue

        if isinstance(current, dict):
            for name in attr_candidates:
                value = current.get(name)
                if value not in (None, "", [], ()):
                    stack.append(value)
            continue

        for name in attr_candidates:
            value = _soap_getattr(current, name)
            if value not in (None, "", [], ()):
                stack.append(value)

    return items


def _matches_parte_filters(fascicolo: FascicoloPolisWeb, nome_parte: Optional[str], codice_fiscale_parte: Optional[str]) -> bool:
    nome = (nome_parte or "").strip().upper()
    cf = (codice_fiscale_parte or "").strip().upper()
    if not nome and not cf:
        return True

    for parte in fascicolo.parti:
        if nome and nome in (parte or "").upper():
            return True

    for parte in getattr(fascicolo, "parti_dettaglio", []) or []:
        nome_full = (parte.get("nome") or "").upper()
        cf_full = (parte.get("codice_fiscale") or "").upper()
        if nome and nome in nome_full:
            return True
        if cf and cf == cf_full:
            return True

    return False


def _soap_fault_message(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""

    for node in root.iter():
        tag = node.tag.split("}")[-1].lower()
        if tag in {"faultstring", "reason", "text"}:
            text = (node.text or "").strip()
            if text:
                return text
    return ""


# ================================================================ Dataclass risultati

@dataclass
class FascicoloPolisWeb:
    """
    Pratica trovata nel registro del tribunale tramite PolisWeb.
    Da usare come sorgente per l'importazione nel fascicolo interno.
    """
    numero_rg: str
    anno_rg: int
    ruolo: str                  # CIVILE_COGNIZIONE | ESECUZIONI | FALLIMENTI | …
    stato: str                  # PENDENTE | DEFINITO | SOSPESO
    oggetto: str                # oggetto della causa
    sezione: str = ""
    giudice: str = ""
    data_iscrizione: str = ""   # YYYY-MM-DD
    data_udienza: str = ""      # prossima udienza
    parti: List[str] = field(default_factory=list)
    parti_dettaglio: List[Dict[str, str]] = field(default_factory=list)
    note: str = ""
    codice_ufficio: str = ""    # codice MinGiust del tribunale
    nome_ufficio: str = ""


@dataclass
class DocumentoPolisWeb:
    """Documento presente nel fascicolo telematico del tribunale."""
    id_documento: str
    nome: str
    tipo: str                   # ATTO | ALLEGATO | INDICE | PROVVEDIMENTO | …
    data_deposito: str          # YYYY-MM-DD
    mittente: str
    dimensione_bytes: int = 0
    disponibile: bool = True
    # Raggruppamento per busta/deposito (tutti i file della stessa busta condividono id_deposito)
    id_deposito: str = ""       # identificativo univoco della busta telematica
    tipo_atto: str = ""         # tipo atto della busta (es. "Decreto Ingiuntivo", "Memoria")


@dataclass
class RisultatoImportazione:
    """Esito dell'importazione di una pratica da PolisWeb."""
    successo: bool
    id_fascicolo_locale: Optional[str] = None
    messaggio: str = ""
    fascicolo_polis: Optional[FascicoloPolisWeb] = None
    documenti_importati: int = 0
    depositi_importati: int = 0
    avvisi: List[str] = field(default_factory=list)


def _chiave_deposito_polisweb(documento: DocumentoPolisWeb) -> str:
    data = _parse_data(documento.data_deposito)
    mittente = (documento.mittente or "").strip()
    return (documento.id_deposito or f"__{data}__{mittente}").strip()


def _documento_polisweb_principale(documento: DocumentoPolisWeb) -> bool:
    tipo = (documento.tipo or "").upper()
    nome = (documento.nome or "").upper()
    return any(
        token in tipo or token in nome
        for token in (
            "ATTO",
            "RICORSO",
            "CITAZIONE",
            "COMPARSA",
            "MEMORIA",
            "OPPOSIZIONE",
            "PROVVEDIMENTO",
            "SENTENZA",
            "ORDINANZA",
            "DECRETO",
        )
    )


def _tipo_atto_gruppo_polisweb(documenti: List[DocumentoPolisWeb]) -> str:
    for doc in documenti:
        label = (doc.tipo_atto or "").strip()
        if label:
            return label
    for doc in documenti:
        label = (doc.tipo or "").strip()
        if label:
            return label.replace("_", " ").strip()
    return "Deposito telematico"


def _nome_atto_principale_gruppo_polisweb(documenti: List[DocumentoPolisWeb]) -> str:
    for doc in documenti:
        if _documento_polisweb_principale(doc) and (doc.nome or "").strip():
            return doc.nome.strip()
    for doc in documenti:
        if (doc.nome or "").strip():
            return doc.nome.strip()
    return ""


def _documento_polisweb_to_dict(documento: DocumentoPolisWeb) -> Dict[str, Any]:
    return {
        "id_documento": (documento.id_documento or "").strip(),
        "nome": (documento.nome or "").strip(),
        "tipo": (documento.tipo or "").strip(),
        "data_deposito": _parse_data(documento.data_deposito),
        "mittente": (documento.mittente or "").strip(),
        "dimensione_bytes": int(documento.dimensione_bytes or 0),
        "disponibile": bool(documento.disponibile),
        "id_deposito": _chiave_deposito_polisweb(documento),
        "tipo_atto": (documento.tipo_atto or _tipo_atto_gruppo_polisweb([documento])).strip(),
    }


def _gruppa_documenti_polisweb_per_deposito(documenti_pw: Optional[List[DocumentoPolisWeb]]) -> List[Dict[str, Any]]:
    gruppi: Dict[str, Dict[str, Any]] = {}
    for doc in sorted(
        documenti_pw or [],
        key=lambda item: (
            _parse_data(item.data_deposito),
            _chiave_deposito_polisweb(item),
            (item.nome or "").strip(),
        ),
        reverse=True,
    ):
        chiave = _chiave_deposito_polisweb(doc)
        if chiave not in gruppi:
            gruppi[chiave] = {
                "id_deposito": chiave,
                "tipo_atto": "",
                "data_deposito": _parse_data(doc.data_deposito),
                "mittente": (doc.mittente or "").strip(),
                "documenti": [],
                "nome_atto_principale": "",
            }
        gruppi[chiave]["documenti"].append(doc)

    depositi: List[Dict[str, Any]] = []
    for gruppo in gruppi.values():
        docs = gruppo["documenti"]
        gruppo["tipo_atto"] = _tipo_atto_gruppo_polisweb(docs)
        gruppo["nome_atto_principale"] = _nome_atto_principale_gruppo_polisweb(docs)
        gruppo["documenti_portale"] = [_documento_polisweb_to_dict(doc) for doc in docs]
        depositi.append(gruppo)

    depositi.sort(
        key=lambda gruppo: (gruppo.get("data_deposito") or "", gruppo.get("id_deposito") or ""),
        reverse=True,
    )
    return depositi


def _sincronizza_depositi_documentali_polisweb(
    *,
    fascicolo_locale,
    gestione_fascicoli,
    documenti_pw: Optional[List[DocumentoPolisWeb]],
    avvocato_referente: str = "",
    fonte: str = "PolisWeb / PST",
) -> tuple[Any, int, int]:
    gruppi = _gruppa_documenti_polisweb_per_deposito(documenti_pw)
    if not gruppi:
        return fascicolo_locale, 0, 0

    for gruppo in gruppi:
        descrizione = (
            f"{len(gruppo['documenti_portale'])} documenti ufficiali censiti da {fonte}."
        )
        gestione_fascicoli.sincronizza_deposito_portale(
            fascicolo_locale.id,
            fonte=fonte,
            id_deposito_esterno=gruppo["id_deposito"],
            tipo_atto=gruppo["tipo_atto"],
            data_deposito=gruppo["data_deposito"],
            mittente=gruppo["mittente"],
            documenti_portale=gruppo["documenti_portale"],
            registrato_da=avvocato_referente,
            note=descrizione,
            nome_atto_principale=gruppo["nome_atto_principale"],
            stato="IMPORTATO_DA_PST",
            servizio_portale=SERVIZIO_PST_DOCUMENTI_FASCICOLO,
        )
    fascicolo_locale = gestione_fascicoli.get(fascicolo_locale.id) or fascicolo_locale
    return fascicolo_locale, len(gruppi), sum(len(gruppo["documenti_portale"]) for gruppo in gruppi)


# ================================================================ Helper: riconcilia soggetti

def _is_persona_giuridica(nome: str) -> bool:
    """Euristica: il nome contiene indicatori di forma giuridica o ente."""
    indicatori = (
        "SRL", "S.R.L", "SPA", "S.P.A", "SAS", "S.A.S", "SNC", "S.N.C",
        "SRLS", "S.R.L.S", "SAP", "SOCIETA", "SOCIETÀ", "ASSOCIAZIONE",
        "FONDAZIONE", "COOPERATIVA", "CONDOMINIO", "COMUNE DI", "MINISTERO",
        "AGENZIA", "ISTITUTO", "ENTE ", "STUDIO LEGALE",
    )
    return any(ind in nome.upper() for ind in indicatori)


def _split_nome_cognome(
    nome_completo: str,
    *,
    cognome_hint: str = "",
    nome_hint: str = "",
) -> tuple[str, str]:
    """
    Divide un nominativo PST in (cognome, nome).

    Se il portale espone già i campi strutturati li usa come fonte primaria.
    In fallback applica due euristiche:
    - tutto maiuscolo -> formato PST classico "COGNOME NOME"
    - testo misto     -> formato più naturale "Nome Cognome"
    """
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip()).title()

    cognome_hint = _normalize(cognome_hint)
    nome_hint = _normalize(nome_hint)
    if cognome_hint or nome_hint:
        return cognome_hint, nome_hint

    nome_completo = re.sub(r"\s+", " ", (nome_completo or "").strip())
    parti = nome_completo.split()
    if not parti:
        return "", ""
    if len(parti) == 1:
        return parti[0].title(), ""
    if nome_completo.upper() == nome_completo:
        cognome = " ".join(p.title() for p in parti[:-1])
        nome = " ".join(p.title() for p in parti[-1:])
    else:
        nome = " ".join(p.title() for p in parti[:-1])
        cognome = " ".join(p.title() for p in parti[-1:])
    return cognome, nome


def _nome_normalizzato(nome: str) -> str:
    return re.sub(r"\s+", " ", (nome or "").strip()).upper()


def _iter_parti_pst(
    nomi: List[str],
    dettagli: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    parti: List[Dict[str, str]] = []
    visti: set[tuple[str, str]] = set()

    for dettaglio in dettagli or []:
        nome = re.sub(r"\s+", " ", (dettaglio.get("nome") or "").strip())
        cf = (dettaglio.get("codice_fiscale") or "").strip().upper()
        if not nome:
            continue
        chiave = (_nome_normalizzato(nome), cf)
        if chiave in visti:
            continue
        visti.add(chiave)
        parti.append(
            {
                "nome": nome,
                "cognome": re.sub(r"\s+", " ", (dettaglio.get("cognome") or "").strip()),
                "nome_proprio": re.sub(r"\s+", " ", (dettaglio.get("nome_proprio") or "").strip()),
                "codice_fiscale": cf,
                "tipo": (dettaglio.get("tipo") or "").strip(),
                "avvocato": (dettaglio.get("avvocato") or "").strip(),
                "cf_avvocato": (dettaglio.get("cf_avvocato") or "").strip().upper(),
            }
        )

    for nome_raw in nomi or []:
        nome = re.sub(r"\s+", " ", (nome_raw or "").strip())
        if not nome:
            continue
        chiave = (_nome_normalizzato(nome), "")
        if chiave in visti:
            continue
        visti.add(chiave)
        parti.append(
            {
                "nome": nome,
                "cognome": "",
                "nome_proprio": "",
                "codice_fiscale": "",
                "tipo": "",
                "avvocato": "",
                "cf_avvocato": "",
            }
        )

    return parti


def _cerca_cliente_pst(gestione_clienti, nome: str, codice_fiscale: str = ""):
    nome_norm = _nome_normalizzato(nome)
    cf = (codice_fiscale or "").strip().upper()

    for cliente in gestione_clienti.tutti():
        identificativo = (getattr(cliente, "identificativo_fiscale", "") or "").strip().upper()
        if cf and identificativo == cf:
            return cliente

    for cliente in gestione_clienti.tutti():
        nome_cliente = _nome_normalizzato(cliente.nome_completo)
        if nome_norm and (nome_norm == nome_cliente or nome_norm in nome_cliente or nome_cliente in nome_norm):
            return cliente

    return None


def _crea_cliente_pst(
    gestione_clienti,
    nome: str,
    codice_fiscale: str,
    riferimento: str,
    portale: str,
    *,
    cognome_hint: str = "",
    nome_hint: str = "",
):
    from pct.clienti import StatoCliente, TipoCliente

    nota_auto = f"Inserito automaticamente da {portale} — {riferimento}"
    nome = re.sub(r"\s+", " ", (nome or "").strip())
    codice_fiscale = (codice_fiscale or "").strip().upper()

    if _is_persona_giuridica(nome):
        return gestione_clienti.nuovo(
            tipo=TipoCliente.PERSONA_GIURIDICA,
            ragione_sociale=nome,
            codice_fiscale=codice_fiscale,
            stato=StatoCliente.POTENZIALE,
            note=nota_auto,
        )

    cognome, nome_pf = _split_nome_cognome(
        nome,
        cognome_hint=cognome_hint,
        nome_hint=nome_hint,
    )
    return gestione_clienti.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        cognome=cognome,
        nome=nome_pf,
        codice_fiscale=codice_fiscale,
        stato=StatoCliente.POTENZIALE,
        note=nota_auto,
    )


def _cerca_soggetto_pst(
    gestione_soggetti,
    nome: str,
    codice_fiscale: str = "",
    id_cliente: str = "",
):
    nome_norm = _nome_normalizzato(nome)
    cf = (codice_fiscale or "").strip().upper()

    for soggetto in gestione_soggetti.tutti():
        if id_cliente and soggetto.id_cliente == id_cliente and _nome_normalizzato(soggetto.nome_completo) == nome_norm:
            return soggetto

    for soggetto in gestione_soggetti.tutti():
        identificativo = (getattr(soggetto, "identificativo", "") or "").strip().upper()
        if cf and identificativo == cf:
            return soggetto

    for soggetto in gestione_soggetti.tutti():
        nome_soggetto = _nome_normalizzato(soggetto.nome_completo)
        if nome_norm and (nome_norm == nome_soggetto or nome_norm in nome_soggetto or nome_soggetto in nome_norm):
            return soggetto

    return None


def _crea_soggetto_pst(
    gestione_soggetti,
    nome: str,
    codice_fiscale: str = "",
    id_cliente: str = "",
    note: str = "",
    *,
    cognome_hint: str = "",
    nome_hint: str = "",
):
    from pct.soggetti import TipoSoggetto

    nome = re.sub(r"\s+", " ", (nome or "").strip())
    codice_fiscale = (codice_fiscale or "").strip().upper()

    if _is_persona_giuridica(nome):
        return gestione_soggetti.crea(
            TipoSoggetto.PERSONA_GIURIDICA,
            ragione_sociale=nome,
            codice_fiscale=codice_fiscale,
            id_cliente=id_cliente,
            note=note,
        )

    cognome, nome_pf = _split_nome_cognome(
        nome,
        cognome_hint=cognome_hint,
        nome_hint=nome_hint,
    )
    return gestione_soggetti.crea(
        TipoSoggetto.PERSONA_FISICA,
        cognome=cognome,
        nome=nome_pf,
        codice_fiscale=codice_fiscale,
        id_cliente=id_cliente,
        note=note,
    )


def _allinea_cliente_pst(
    gestione_clienti,
    cliente,
    *,
    nome: str,
    codice_fiscale: str = "",
    cognome_hint: str = "",
    nome_hint: str = "",
):
    from pct.clienti import TipoCliente

    if cliente is None:
        return None, False

    nome = re.sub(r"\s+", " ", (nome or "").strip())
    codice_fiscale = (codice_fiscale or "").strip().upper()
    updates: Dict[str, str] = {}

    if cliente.tipo == TipoCliente.PERSONA_GIURIDICA or _is_persona_giuridica(nome):
        if nome and not getattr(cliente, "ragione_sociale", ""):
            updates["ragione_sociale"] = nome
        if codice_fiscale and not getattr(cliente, "codice_fiscale", ""):
            updates["codice_fiscale"] = codice_fiscale
    else:
        cognome, nome_pf = _split_nome_cognome(
            nome,
            cognome_hint=cognome_hint,
            nome_hint=nome_hint,
        )
        if cognome and getattr(cliente, "cognome", "") != cognome:
            updates["cognome"] = cognome
        if nome_pf and getattr(cliente, "nome", "") != nome_pf:
            updates["nome"] = nome_pf
        if codice_fiscale and getattr(cliente, "codice_fiscale", "") != codice_fiscale:
            updates["codice_fiscale"] = codice_fiscale

    if not updates:
        return cliente, False
    return gestione_clienti.aggiorna(cliente.id, **updates), True


def _allinea_soggetto_pst(
    gestione_soggetti,
    soggetto,
    *,
    nome: str,
    codice_fiscale: str = "",
    cognome_hint: str = "",
    nome_hint: str = "",
    id_cliente: str = "",
):
    from pct.soggetti import TipoSoggetto

    if soggetto is None:
        return None, False

    nome = re.sub(r"\s+", " ", (nome or "").strip())
    codice_fiscale = (codice_fiscale or "").strip().upper()
    updates: Dict[str, str] = {}

    if soggetto.tipo == TipoSoggetto.PERSONA_GIURIDICA or _is_persona_giuridica(nome):
        if nome and not getattr(soggetto, "ragione_sociale", ""):
            updates["ragione_sociale"] = nome
        if codice_fiscale and not getattr(soggetto, "codice_fiscale", ""):
            updates["codice_fiscale"] = codice_fiscale
    else:
        cognome, nome_pf = _split_nome_cognome(
            nome,
            cognome_hint=cognome_hint,
            nome_hint=nome_hint,
        )
        if cognome and getattr(soggetto, "cognome", "") != cognome:
            updates["cognome"] = cognome
        if nome_pf and getattr(soggetto, "nome", "") != nome_pf:
            updates["nome"] = nome_pf
        if codice_fiscale and getattr(soggetto, "codice_fiscale", "") != codice_fiscale:
            updates["codice_fiscale"] = codice_fiscale

    if id_cliente and getattr(soggetto, "id_cliente", "") != id_cliente:
        updates["id_cliente"] = id_cliente

    if not updates:
        return soggetto, False
    return gestione_soggetti.aggiorna(soggetto.id, **updates), True


def _ruolo_parte_pst(idx: int, parte: Dict[str, str], id_cliente_principale: str, soggetto):
    from pct.soggetti import RuoloSoggetto

    tipo = _nome_normalizzato(parte.get("tipo", ""))
    if id_cliente_principale and getattr(soggetto, "id_cliente", "") == id_cliente_principale:
        return RuoloSoggetto.ASSISTITO

    parole_controparte = (
        "CONVENUT",
        "RESISTENT",
        "APPELLAT",
        "OPPOST",
        "ESECUTAT",
        "DEBITOR",
        "INTIMAT",
        "CONTROPARTE",
        "IMPUTAT",
    )
    if any(p in tipo for p in parole_controparte):
        return RuoloSoggetto.CONTROPARTE

    return RuoloSoggetto.ASSISTITO if idx == 0 else RuoloSoggetto.CONTROPARTE


def riconcilia_soggetti_pst(
    nomi: List[str],
    gestione_clienti,
    riferimento: str,
    portale: str = "PolisWeb",
) -> tuple[str, str, List[str]]:
    """
    Riconcilia una lista di nominativi (parti/imputati/ricorrenti) con
    l'anagrafica clienti del gestionale.

    Per ogni nominativo:
      - Se esiste un cliente con nome corrispondente → riutilizza
      - Se non esiste → crea automaticamente un nuovo cliente POTENZIALE

    Args:
        nomi:             Lista di nominativi (stringhe) restituiti dal portale.
        gestione_clienti: Istanza di GestioneClienti.
        riferimento:      Stringa usata nelle note (es. "RG 123/2024 — Tribunale di Milano").
        portale:          Nome del portale sorgente (PolisWeb/PDP/PAT).

    Returns:
        (id_cliente_principale, nome_cliente_principale, avvisi)
        dove id_cliente_principale è il cliente corrispondente alla prima parte valida.
    """
    from pct.clienti import TipoCliente, StatoCliente

    id_principale   = ""
    nome_principale = ""
    avvisi: List[str] = []
    clienti_cache = gestione_clienti.tutti()

    for i, nome_raw in enumerate(nomi):
        nome_raw = (nome_raw or "").strip()
        if not nome_raw:
            continue

        nome_up = nome_raw.upper()

        # Cerca cliente esistente (match parziale bidirezionale, case-insensitive)
        trovato = None
        for c in clienti_cache:
            nc_up = c.nome_completo.upper()
            if nome_up in nc_up or nc_up in nome_up:
                trovato = c
                break

        if trovato is None:
            try:
                nota_auto = (
                    f"Inserito automaticamente da {portale} — {riferimento}"
                )
                if _is_persona_giuridica(nome_raw):
                    trovato = gestione_clienti.nuovo(
                        tipo=TipoCliente.PERSONA_GIURIDICA,
                        ragione_sociale=nome_raw.title(),
                        stato=StatoCliente.POTENZIALE,
                        note=nota_auto,
                    )
                else:
                    cognome, nome = _split_nome_cognome(nome_raw)
                    trovato = gestione_clienti.nuovo(
                        tipo=TipoCliente.PERSONA_FISICA,
                        cognome=cognome,
                        nome=nome,
                        stato=StatoCliente.POTENZIALE,
                        note=nota_auto,
                    )
                # Aggiorna cache locale per evitare duplicati nelle iterazioni successive
                clienti_cache = gestione_clienti.tutti()
                avvisi.append(
                    f"Nuovo soggetto creato in anagrafica: "
                    f"«{trovato.nome_completo}» (stato: Potenziale)."
                )
            except Exception as e_crea:
                avvisi.append(
                    f"Impossibile creare il soggetto «{nome_raw}»: {e_crea}"
                )

        # Il primo soggetto elaborato con successo → cliente principale del fascicolo
        if i == 0 and trovato:
            id_principale   = trovato.id
            nome_principale = trovato.nome_completo

    return id_principale, nome_principale, avvisi


def _riconcilia_parti_dettaglio_polisweb(
    fascicolo_pw: FascicoloPolisWeb,
    gestione_clienti,
    riferimento: str,
    portale: str = "PolisWeb",
) -> tuple[str, str, List[str]]:
    id_principale = ""
    nome_principale = ""
    avvisi: List[str] = []

    for idx, parte in enumerate(_iter_parti_pst(fascicolo_pw.parti, fascicolo_pw.parti_dettaglio)):
        nome_raw = parte["nome"]
        codice_fiscale = parte.get("codice_fiscale", "")
        trovato = _cerca_cliente_pst(gestione_clienti, nome_raw, codice_fiscale)
        if trovato is not None:
            trovato, aggiornato = _allinea_cliente_pst(
                gestione_clienti,
                trovato,
                nome=nome_raw,
                codice_fiscale=codice_fiscale,
                cognome_hint=parte.get("cognome", ""),
                nome_hint=parte.get("nome_proprio", ""),
            )
            if aggiornato:
                avvisi.append(
                    f"Anagrafica cliente riallineata ai dati PST: «{trovato.nome_completo}»."
                )

        if trovato is None:
            try:
                trovato = _crea_cliente_pst(
                    gestione_clienti=gestione_clienti,
                    nome=nome_raw,
                    codice_fiscale=codice_fiscale,
                    riferimento=riferimento,
                    portale=portale,
                    cognome_hint=parte.get("cognome", ""),
                    nome_hint=parte.get("nome_proprio", ""),
                )
                avvisi.append(
                    f"Nuovo soggetto creato in anagrafica: "
                    f"«{trovato.nome_completo}» (stato: Potenziale)."
                )
            except Exception as e_crea:
                avvisi.append(
                    f"Impossibile creare il soggetto «{nome_raw}»: {e_crea}"
                )

        if idx == 0 and trovato:
            id_principale = trovato.id
            nome_principale = trovato.nome_completo

    return id_principale, nome_principale, avvisi


def _sincronizza_parti_pst_su_fascicolo(
    fascicolo_pw: FascicoloPolisWeb,
    fascicolo_locale,
    gestione_clienti,
    gestione_soggetti,
    id_cliente_principale: str,
    riferimento: str,
    portale: str = "PolisWeb",
) -> tuple[str, str, List[str]]:
    from pct.clienti import RiferimentoProcedimento

    avvisi: List[str] = []
    controparte = ""
    cf_controparte = ""

    if not gestione_soggetti:
        return controparte, cf_controparte, avvisi

    for idx, parte in enumerate(_iter_parti_pst(fascicolo_pw.parti, fascicolo_pw.parti_dettaglio)):
        nome = parte["nome"]
        codice_fiscale = parte.get("codice_fiscale", "")
        cliente = _cerca_cliente_pst(gestione_clienti, nome, codice_fiscale)
        if cliente is not None:
            cliente, aggiornato_cliente = _allinea_cliente_pst(
                gestione_clienti,
                cliente,
                nome=nome,
                codice_fiscale=codice_fiscale,
                cognome_hint=parte.get("cognome", ""),
                nome_hint=parte.get("nome_proprio", ""),
            )
            if aggiornato_cliente:
                avvisi.append(
                    f"Anagrafica cliente riallineata ai dati PST: «{cliente.nome_completo}»."
                )
        id_cliente_assoc = cliente.id if cliente else (id_cliente_principale if idx == 0 else "")
        soggetto = _cerca_soggetto_pst(
            gestione_soggetti=gestione_soggetti,
            nome=nome,
            codice_fiscale=codice_fiscale,
            id_cliente=id_cliente_assoc,
        )
        if soggetto is not None:
            soggetto, aggiornato_soggetto = _allinea_soggetto_pst(
                gestione_soggetti,
                soggetto,
                nome=nome,
                codice_fiscale=codice_fiscale,
                cognome_hint=parte.get("cognome", ""),
                nome_hint=parte.get("nome_proprio", ""),
                id_cliente=id_cliente_assoc,
            )
            if aggiornato_soggetto:
                avvisi.append(
                    f"Anagrafica soggetto riallineata ai dati PST: «{soggetto.nome_completo}»."
                )

        if soggetto is None:
            tipo_parte = (parte.get("tipo") or "").strip()
            nota = f"Importato automaticamente da {portale} — {riferimento}"
            if tipo_parte:
                nota = f"{nota} (parte PST: {tipo_parte})"
            soggetto = _crea_soggetto_pst(
                gestione_soggetti=gestione_soggetti,
                nome=nome,
                codice_fiscale=codice_fiscale,
                id_cliente=id_cliente_assoc,
                note=nota,
                cognome_hint=parte.get("cognome", ""),
                nome_hint=parte.get("nome_proprio", ""),
            )
            avvisi.append(f"Nuova parte creata nel database soggetti: «{soggetto.nome_completo}».")

        ruolo = _ruolo_parte_pst(idx, parte, id_cliente_principale, soggetto)
        note_parte = "Importato da PolisWeb"
        if parte.get("tipo"):
            note_parte = f"{note_parte} — tipo PST: {parte['tipo']}"
        gestione_soggetti.aggiungi_parte(
            fascicolo_locale.id,
            soggetto.id,
            ruolo=ruolo,
            note=note_parte,
        )

        if ruolo.value == "CONTROPARTE" and not controparte:
            controparte = soggetto.nome_completo
            cf_controparte = codice_fiscale

    if id_cliente_principale:
        cliente_principale = gestione_clienti.get(id_cliente_principale)
        if cliente_principale and not any(
            p.numero_rg == fascicolo_pw.numero_rg
            and p.anno == fascicolo_pw.anno_rg
            and p.tribunale == fascicolo_pw.nome_ufficio
            for p in cliente_principale.procedimenti
        ):
            gestione_clienti.aggiungi_procedimento(
                id_cliente_principale,
                RiferimentoProcedimento(
                    numero_rg=fascicolo_pw.numero_rg,
                    anno=fascicolo_pw.anno_rg,
                    tribunale=fascicolo_pw.nome_ufficio,
                    descrizione=fascicolo_pw.oggetto,
                    data_apertura=fascicolo_pw.data_iscrizione or fascicolo_locale.data_apertura,
                    attivo=fascicolo_locale.stato.value not in {"DEFINITO", "ARCHIVIATO"},
                ),
            )

    return controparte, cf_controparte, avvisi


def _titolo_fascicolo_polisweb(fascicolo_pw: FascicoloPolisWeb) -> str:
    base = f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}"
    oggetto = (fascicolo_pw.oggetto or "").strip()
    return f"{base} — {oggetto[:80]}" if oggetto else base


def _titolo_generico_fascicolo_polisweb(titolo: str, fascicolo_pw: FascicoloPolisWeb) -> bool:
    titolo = (titolo or "").strip()
    base = f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}"
    if titolo in {"", base, f"{base} —", f"{base} –", f"{base} -", f"{base} ?"}:
        return True
    if not titolo.startswith(base):
        return False
    suffisso = titolo[len(base):].strip()
    return not suffisso.strip("—–-? ")


def _data_apertura_generica_polisweb(fascicolo_locale) -> bool:
    data_apertura = _parse_data(getattr(fascicolo_locale, "data_apertura", ""))
    if not data_apertura:
        return True
    creato_il = _parse_data(getattr(fascicolo_locale, "creato_il", ""))
    if creato_il and data_apertura == creato_il:
        return True
    note = getattr(fascicolo_locale, "note", "") or ""
    match = re.search(r"Importato da PolisWeb il (\d{4}-\d{2}-\d{2})", note)
    return bool(match and data_apertura == match.group(1))


def _attivita_polisweb_presente(fascicolo_locale, tipo, data_attivita: str, titolo: str) -> bool:
    titolo_norm = _nome_normalizzato(titolo)
    data_norm = _parse_data(data_attivita)
    return any(
        att.tipo == tipo
        and _parse_data(att.data) == data_norm
        and _nome_normalizzato(att.titolo) == titolo_norm
        for att in getattr(fascicolo_locale, "attivita", []) or []
    )


def _sincronizza_metadati_fascicolo_polisweb(
    fascicolo_pw: FascicoloPolisWeb,
    fascicolo_locale,
    gestione_fascicoli,
    gestione_clienti,
    avvocato_referente: str = "",
    gestione_soggetti=None,
    documenti_pw: Optional[List[DocumentoPolisWeb]] = None,
) -> RisultatoImportazione:
    from pct.fascicoli import TipoAttivita, stato_fascicolo_da_descrizione_portale

    riferimento = f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg} — {fascicolo_pw.nome_ufficio}"
    avvisi: List[str] = []
    oggi_iso = date.today().isoformat()
    data_iscrizione = _parse_data(fascicolo_pw.data_iscrizione)
    data_udienza = _parse_data(fascicolo_pw.data_udienza)

    id_cliente = fascicolo_locale.id_cliente or ""
    nome_cliente = fascicolo_locale.nome_cliente or ""

    if fascicolo_pw.parti or fascicolo_pw.parti_dettaglio:
        id_cliente_sync, nome_cliente_sync, avvisi_clienti = _riconcilia_parti_dettaglio_polisweb(
            fascicolo_pw=fascicolo_pw,
            gestione_clienti=gestione_clienti,
            riferimento=riferimento,
            portale="PolisWeb",
        )
        avvisi.extend(avvisi_clienti)
        if not id_cliente and id_cliente_sync:
            id_cliente = id_cliente_sync
        if not nome_cliente and nome_cliente_sync:
            nome_cliente = nome_cliente_sync

    campi_update: Dict[str, Any] = {}
    if id_cliente and not fascicolo_locale.id_cliente:
        campi_update["id_cliente"] = id_cliente
    if nome_cliente and not fascicolo_locale.nome_cliente:
        campi_update["nome_cliente"] = nome_cliente
    if fascicolo_pw.numero_rg and fascicolo_pw.numero_rg != (getattr(fascicolo_locale, "numero_rg", "") or ""):
        campi_update["numero_rg"] = fascicolo_pw.numero_rg
    if fascicolo_pw.anno_rg and int(fascicolo_pw.anno_rg or 0) != int(getattr(fascicolo_locale, "anno_rg", 0) or 0):
        campi_update["anno_rg"] = fascicolo_pw.anno_rg
    if fascicolo_pw.nome_ufficio and not fascicolo_locale.tribunale:
        campi_update["tribunale"] = fascicolo_pw.nome_ufficio
    if fascicolo_pw.oggetto and not fascicolo_locale.oggetto:
        campi_update["oggetto"] = fascicolo_pw.oggetto
    if fascicolo_pw.sezione and not fascicolo_locale.sezione:
        campi_update["sezione"] = fascicolo_pw.sezione
    if fascicolo_pw.giudice and not fascicolo_locale.giudice:
        campi_update["giudice"] = fascicolo_pw.giudice
    if data_iscrizione and (
        not _parse_data(fascicolo_locale.data_apertura)
        or _data_apertura_generica_polisweb(fascicolo_locale)
    ):
        campi_update["data_apertura"] = data_iscrizione
    if data_udienza:
        data_prima_attuale = _parse_data(fascicolo_locale.data_prima_udienza)
        data_prossima_attuale = _parse_data(fascicolo_locale.data_prossima_udienza)
        if not data_prima_attuale or data_udienza < data_prima_attuale:
            campi_update["data_prima_udienza"] = data_udienza
        if data_udienza >= oggi_iso and (
            not data_prossima_attuale or data_udienza < data_prossima_attuale
        ):
            campi_update["data_prossima_udienza"] = data_udienza
    if _titolo_generico_fascicolo_polisweb(fascicolo_locale.titolo, fascicolo_pw):
        campi_update["titolo"] = _titolo_fascicolo_polisweb(fascicolo_pw)
    stato_portale = stato_fascicolo_da_descrizione_portale(
        fascicolo_pw.stato,
        default=None,
    )
    if stato_portale and stato_portale != fascicolo_locale.stato:
        campi_update["stato"] = stato_portale

    if campi_update:
        fascicolo_locale = gestione_fascicoli.aggiorna(fascicolo_locale.id, **campi_update)

    if data_iscrizione and not _attivita_polisweb_presente(
        fascicolo_locale,
        TipoAttivita.ISCRIZIONE_A_RUOLO,
        data_iscrizione,
        "Iscrizione a ruolo (importata da PolisWeb)",
    ):
        gestione_fascicoli.aggiungi_attivita(
            fascicolo_locale.id,
            tipo=TipoAttivita.ISCRIZIONE_A_RUOLO,
            data=data_iscrizione,
            titolo="Iscrizione a ruolo (importata da PolisWeb)",
            descrizione=f"Pratica sincronizzata da PolisWeb - RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
            avvocato=avvocato_referente,
        )
        fascicolo_locale = gestione_fascicoli.get(fascicolo_locale.id) or fascicolo_locale

    if data_udienza and not _attivita_polisweb_presente(
        fascicolo_locale,
        TipoAttivita.UDIENZA,
        data_udienza,
        "Udienza (importata da PolisWeb)",
    ):
        gestione_fascicoli.aggiungi_attivita(
            fascicolo_locale.id,
            tipo=TipoAttivita.UDIENZA,
            data=data_udienza,
            titolo="Udienza (importata da PolisWeb)",
            descrizione=f"Udienza automaticamente sincronizzata da PolisWeb — RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
            avvocato=avvocato_referente,
        )
        fascicolo_locale = gestione_fascicoli.get(fascicolo_locale.id) or fascicolo_locale

    try:
        controparte, cf_controparte, avvisi_parti = _sincronizza_parti_pst_su_fascicolo(
            fascicolo_pw=fascicolo_pw,
            fascicolo_locale=fascicolo_locale,
            gestione_clienti=gestione_clienti,
            gestione_soggetti=gestione_soggetti,
            id_cliente_principale=id_cliente,
            riferimento=riferimento,
            portale="PolisWeb",
        )
        avvisi.extend(avvisi_parti)
        campi_parti: Dict[str, Any] = {}
        if controparte and not fascicolo_locale.controparte:
            campi_parti["controparte"] = controparte
        if cf_controparte and not fascicolo_locale.cf_controparte:
            campi_parti["cf_controparte"] = cf_controparte
        if campi_parti:
            fascicolo_locale = gestione_fascicoli.aggiorna(fascicolo_locale.id, **campi_parti)
    except Exception as e:
        avvisi.append(f"Parti del procedimento non sincronizzate: {e}")

    if not id_cliente:
        avvisi.append(
            "Nessun soggetto valido nelle parti della causa. "
            "Assegnare il cliente manualmente."
        )

    depositi_importati = 0
    documenti_importati = 0
    if documenti_pw:
        try:
            fascicolo_locale, depositi_importati, documenti_importati = _sincronizza_depositi_documentali_polisweb(
                fascicolo_locale=fascicolo_locale,
                gestione_fascicoli=gestione_fascicoli,
                documenti_pw=documenti_pw,
                avvocato_referente=avvocato_referente,
                fonte="PolisWeb / PST",
            )
        except Exception as e:
            avvisi.append(f"Metadati depositi/documenti PolisWeb non sincronizzati: {e}")

    messaggio = (
        f"Pratica RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg} "
        "sincronizzata sul fascicolo esistente."
    )
    if depositi_importati or documenti_importati:
        messaggio += (
            f" Censiti {depositi_importati} depositi e "
            f"{documenti_importati} documenti ufficiali da PolisWeb."
        )

    return RisultatoImportazione(
        successo=True,
        id_fascicolo_locale=fascicolo_locale.id,
        messaggio=messaggio,
        fascicolo_polis=fascicolo_pw,
        documenti_importati=documenti_importati,
        depositi_importati=depositi_importati,
        avvisi=avvisi,
    )


# ================================================================ Client PolisWeb

class ClientPolisWeb:
    """
    Client per l'accesso ai web service del PST (Portale Servizi Telematici).

    Autentica via certificato digitale P12 del professionista e fornisce:
    - ricerca_fascicoli(): cerca pratiche per RG, anno, tribunale
    - consulta_documenti(): lista documenti in un fascicolo
    - importa_fascicolo(): importa una pratica PolisWeb nel gestionale locale

    Tutti i metodi gestiscono il caso in cui zeep non sia installato
    (sollevano ImportError con istruzioni).
    """

    def __init__(
        self,
        p12_path: str = "",
        p12_password: bytes = b"",
        codice_fiscale_avvocato: str = "",
        timeout: int = 30,
        # ── Formato PEM alternativo al P12 ───────────────────────────────────
        cert_pem_path: str = "",
        key_pem_path: str = "",
        key_pem_password: Optional[bytes] = None,
    ):
        """
        Args:
            p12_path:                 Percorso al file PKCS#12 del professionista.
            p12_password:             Password del certificato P12.
            codice_fiscale_avvocato:  CF dell'avvocato (necessario per alcune query).
            timeout:                  Timeout HTTP in secondi.
            cert_pem_path:            Percorso al certificato PEM (.crt/.pem).
                                      Usare come alternativa al P12 quando il provider
                                      non rilascia il formato PKCS#12.
            key_pem_path:             Percorso alla chiave privata PEM (.key/.pem).
            key_pem_password:         Password della chiave privata PEM (None = non cifrata).
        """
        self.p12_path         = p12_path
        self.p12_password     = p12_password
        self.cert_pem_path    = cert_pem_path
        self.key_pem_path     = key_pem_path
        self.key_pem_password = key_pem_password
        self.cf_avvocato      = codice_fiscale_avvocato.upper()
        self.timeout          = timeout
        self._zeep_cache: Dict[str, Any] = {}
        self._session_cache: Dict[str, Any] = {}

    # ---------------------------------------------------------------- Ricerca fascicoli

    def ricerca_fascicoli(
        self,
        tribunale: str,
        numero_rg: Optional[str] = None,
        anno_rg: Optional[int] = None,
        nome_parte: Optional[str] = None,
        codice_fiscale_parte: Optional[str] = None,
        max_risultati: int = 50,
    ) -> List[FascicoloPolisWeb]:
        """
        Cerca fascicoli nel registro del tribunale tramite PST SOAP.

        Args:
            tribunale:            Nome del tribunale (es. "MILANO") o codice ufficio.
            numero_rg:            Numero RG (facoltativo).
            anno_rg:              Anno RG (facoltativo).
            nome_parte:           Nome di una parte (attore/convenuto).
            codice_fiscale_parte: CF di una parte.
            max_risultati:        Numero massimo di risultati.

        Returns:
            Lista di FascicoloPolisWeb.

        Raises:
            ImportError: se zeep non è installato.
            ConnectionError: se il PST non è raggiungibile.
            PermissionError: se il certificato non è valido / scaduto.
        """
        base_pst = self._risolvi_base_pst(tribunale)
        codice_pst = self._risolvi_codice_ufficio(tribunale)

        if _pst_usa_qbuilder(base_pst):
            xml = self._execute_qbuilder(
                base_pst,
                self._soap_ricerca_fascicoli_qbuilder(
                    base_pst=base_pst,
                    codice_ufficio=codice_pst,
                    numero_rg=numero_rg,
                    anno_rg=anno_rg,
                    nome_parte=nome_parte,
                    codice_fiscale_parte=codice_fiscale_parte,
                ),
            )
            fascicoli = self._parse_fascicoli_qbuilder_xml(xml)
            if fascicoli and len(fascicoli) <= min(max_risultati, 10):
                fascicoli = self._arricchisci_fascicoli_con_profilo(base_pst, fascicoli)
            if not (numero_rg and anno_rg) and (nome_parte or codice_fiscale_parte):
                fascicoli = [
                    f for f in fascicoli
                    if _matches_parte_filters(f, nome_parte, codice_fiscale_parte)
                ]
            return fascicoli[:max_risultati]

        client = self._get_client(_wsdl_ricerca(base_pst))

        request_dict = {
            "codiceFiscaleAvvocato": self.cf_avvocato,
            "codiceUfficio": codice_pst,
            "maxRisultati": max_risultati,
        }
        if numero_rg:
            request_dict["numeroRG"] = numero_rg
        if anno_rg:
            request_dict["annoRG"] = anno_rg
        if nome_parte:
            request_dict["nominativoParte"] = nome_parte
        if codice_fiscale_parte:
            request_dict["codiceFiscaleParte"] = codice_fiscale_parte.upper()

        try:
            risposta = client.service.ricercaFascicoli(**request_dict)
        except Exception as e:
            raise ConnectionError(f"Errore chiamata PST: {e}") from e

        return self._parse_fascicoli(risposta)

    # ---------------------------------------------------------------- Consultazione documenti

    def consulta_documenti(
        self,
        codice_ufficio: str,
        numero_rg: str,
        anno_rg: int,
    ) -> List[DocumentoPolisWeb]:
        """
        Recupera l'elenco dei documenti depositati nel fascicolo telematico.

        Args:
            codice_ufficio: Codice MinGiust del tribunale.
            numero_rg:      Numero RG della causa.
            anno_rg:        Anno RG.

        Returns:
            Lista di DocumentoPolisWeb.
        """
        base_pst = self._risolvi_base_pst(codice_ufficio)
        codice_pst = self._risolvi_codice_ufficio(codice_ufficio)

        if _pst_usa_qbuilder(base_pst):
            xml = self._execute_qbuilder(
                base_pst,
                self._soap_documenti_qbuilder(
                    base_pst=base_pst,
                    codice_ufficio=codice_pst,
                    numero_rg=numero_rg,
                    anno_rg=anno_rg,
                ),
            )
            return self._parse_documenti_qbuilder_xml(xml)

        client = self._get_client(_wsdl_consultazione(base_pst))
        try:
            risposta = client.service.consultazioneAvanzataDocumenti(
                codiceFiscaleAvvocato=self.cf_avvocato,
                codiceUfficio=codice_pst,
                numeroRG=numero_rg,
                annoRG=anno_rg,
            )
        except Exception as e:
            raise ConnectionError(f"Errore consultazione PST: {e}") from e

        return self._parse_documenti(risposta)

    def _precarica_documenti_importazione(
        self,
        fascicolo_pw: FascicoloPolisWeb,
        documenti_pw: Optional[List[DocumentoPolisWeb]] = None,
    ) -> tuple[List[DocumentoPolisWeb], List[str]]:
        if documenti_pw is not None:
            return list(documenti_pw), []

        if not (fascicolo_pw.codice_ufficio and fascicolo_pw.numero_rg and fascicolo_pw.anno_rg):
            return [], []

        try:
            documenti = self.consulta_documenti(
                fascicolo_pw.codice_ufficio,
                fascicolo_pw.numero_rg,
                fascicolo_pw.anno_rg,
            )
            return list(documenti or []), []
        except Exception as e:
            return [], [f"Metadati depositi/documenti PolisWeb non acquisiti: {e}"]

    # ---------------------------------------------------------------- Import pratica

    def importa_fascicolo(
        self,
        fascicolo_pw: FascicoloPolisWeb,
        gestione_fascicoli,        # GestioneFascicoli instance
        gestione_clienti,          # GestioneClienti instance
        avvocato_referente: str = "",
        gestione_soggetti=None,
        documenti_pw: Optional[List[DocumentoPolisWeb]] = None,
    ) -> RisultatoImportazione:
        """
        Importa una pratica PolisWeb come nuovo Fascicolo nel gestionale.

        Il metodo:
        1. Cerca il cliente tra le parti (per CF o nome)
        2. Crea o riutilizza il Cliente
        3. Crea il Fascicolo con tutti i dati disponibili
        4. Aggiunge le attività processuali note (udienza prossima)

        Args:
            fascicolo_pw:       Pratica PolisWeb da importare.
            gestione_fascicoli: Istanza di GestioneFascicoli.
            gestione_clienti:   Istanza di GestioneClienti.
            avvocato_referente: Username avvocato responsabile.

        Returns:
            RisultatoImportazione con id_fascicolo_locale se successo.
        """
        try:
            from pct.fascicoli import (
                TipoFascicolo,
                StatoFascicolo,
                TipoAttivita,
                stato_fascicolo_da_descrizione_portale,
            )

            data_iscrizione = _parse_data(fascicolo_pw.data_iscrizione) or date.today().isoformat()
            data_udienza = _parse_data(fascicolo_pw.data_udienza)
            data_prossima_udienza = data_udienza if data_udienza and data_udienza >= date.today().isoformat() else ""

            # 1. Mappa il tipo ruolo → TipoFascicolo
            tipo_map = {
                "CIVILE_COGNIZIONE":   TipoFascicolo.CIVILE,
                "ESECUZIONI":          TipoFascicolo.CIVILE,
                "FALLIMENTI":          TipoFascicolo.CIVILE,
                "PENALE":              TipoFascicolo.PENALE,
                "LAVORO":              TipoFascicolo.LAVORO,
                "FAMIGLIA":            TipoFascicolo.FAMIGLIA,
                "MINORI":              TipoFascicolo.FAMIGLIA,
                "VOLONTARIA":          TipoFascicolo.ALTRO,
            }
            tipo_fascicolo = tipo_map.get(
                fascicolo_pw.ruolo.upper(), TipoFascicolo.CIVILE
            )
            stato = stato_fascicolo_da_descrizione_portale(
                fascicolo_pw.stato,
                default=StatoFascicolo.APERTO,
            )

            # 2. Riconcilia tutte le parti con l'anagrafica clienti.
            #    Cerca ogni soggetto; se non esiste lo crea come POTENZIALE.
            rif = f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg} — {fascicolo_pw.nome_ufficio}"
            id_cliente, nome_cliente, avvisi = _riconcilia_parti_dettaglio_polisweb(
                fascicolo_pw=fascicolo_pw,
                gestione_clienti=gestione_clienti,
                riferimento=rif,
                portale="PolisWeb",
            )

            documenti_pw_effettivi, avvisi_documenti = self._precarica_documenti_importazione(
                fascicolo_pw,
                documenti_pw=documenti_pw,
            )
            avvisi.extend(avvisi_documenti)

            # 3. Crea fascicolo
            fasc = gestione_fascicoli.nuovo(
                titolo=_titolo_fascicolo_polisweb(fascicolo_pw),
                tipo=tipo_fascicolo,
                id_cliente=id_cliente,
                nome_cliente=nome_cliente,
                tribunale=fascicolo_pw.nome_ufficio,
                numero_rg=fascicolo_pw.numero_rg,
                anno_rg=fascicolo_pw.anno_rg,
                sezione=fascicolo_pw.sezione,
                giudice=fascicolo_pw.giudice,
                oggetto=fascicolo_pw.oggetto,
                stato=stato,
                avvocato_referente=avvocato_referente,
                data_apertura=data_iscrizione,
                data_prima_udienza=data_udienza or "",
                data_prossima_udienza=data_prossima_udienza,
                note=fascicolo_pw.note or f"Importato da PolisWeb il {date.today()}",
            )

            # 4. Aggiungi prossima udienza come attività
            try:
                gestione_fascicoli.aggiungi_attivita(
                    fasc.id,
                    tipo=TipoAttivita.ISCRIZIONE_A_RUOLO,
                    data=data_iscrizione,
                    titolo="Iscrizione a ruolo (importata da PolisWeb)",
                    descrizione=f"Pratica importata da PolisWeb - RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
                    avvocato=avvocato_referente,
                )
            except Exception as e:
                avvisi.append(f"Iscrizione a ruolo non registrata: {e}")

            if data_udienza:
                try:
                    gestione_fascicoli.aggiungi_attivita(
                        fasc.id,
                        tipo=TipoAttivita.UDIENZA,
                        data=data_udienza,
                        titolo="Udienza (importata da PolisWeb)",
                        descrizione=f"Udienza automaticamente importata da PolisWeb — RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
                        avvocato=avvocato_referente,
                    )
                except Exception as e:
                    avvisi.append(f"Udienza non importata: {e}")

            try:
                controparte, cf_controparte, avvisi_parti = _sincronizza_parti_pst_su_fascicolo(
                    fascicolo_pw=fascicolo_pw,
                    fascicolo_locale=fasc,
                    gestione_clienti=gestione_clienti,
                    gestione_soggetti=gestione_soggetti,
                    id_cliente_principale=id_cliente,
                    riferimento=rif,
                    portale="PolisWeb",
                )
                avvisi.extend(avvisi_parti)
                if controparte or cf_controparte:
                    fasc = gestione_fascicoli.aggiorna(
                        fasc.id,
                        controparte=controparte,
                        cf_controparte=cf_controparte,
                    )
            except Exception as e:
                avvisi.append(f"Parti del procedimento non sincronizzate: {e}")

            if not id_cliente:
                avvisi.append(
                    "Nessun soggetto valido nelle parti della causa. "
                    "Assegnare il cliente manualmente."
                )

            depositi_importati = 0
            documenti_importati = 0
            if documenti_pw_effettivi:
                try:
                    fasc, depositi_importati, documenti_importati = _sincronizza_depositi_documentali_polisweb(
                        fascicolo_locale=fasc,
                        gestione_fascicoli=gestione_fascicoli,
                        documenti_pw=documenti_pw_effettivi,
                        avvocato_referente=avvocato_referente,
                        fonte="PolisWeb / PST",
                    )
                except Exception as e:
                    avvisi.append(f"Metadati depositi/documenti PolisWeb non sincronizzati: {e}")

            messaggio = f"Pratica RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg} importata."
            if depositi_importati or documenti_importati:
                messaggio += (
                    f" Censiti {depositi_importati} depositi e "
                    f"{documenti_importati} documenti ufficiali da PolisWeb."
                )

            return RisultatoImportazione(
                successo=True,
                id_fascicolo_locale=fasc.id,
                messaggio=messaggio,
                fascicolo_polis=fascicolo_pw,
                documenti_importati=documenti_importati,
                depositi_importati=depositi_importati,
                avvisi=avvisi,
            )

        except Exception as e:
            return RisultatoImportazione(
                successo=False,
                messaggio=f"Errore durante l'importazione: {e}",
                fascicolo_polis=fascicolo_pw,
            )

    def sincronizza_fascicolo_esistente(
        self,
        fascicolo_pw: FascicoloPolisWeb,
        fascicolo_locale,
        gestione_fascicoli,
        gestione_clienti,
        avvocato_referente: str = "",
        gestione_soggetti=None,
        documenti_pw: Optional[List[DocumentoPolisWeb]] = None,
    ) -> RisultatoImportazione:
        """Completa un fascicolo già presente con i dati più ricchi provenienti da PolisWeb."""
        try:
            documenti_pw_effettivi, avvisi_documenti = self._precarica_documenti_importazione(
                fascicolo_pw,
                documenti_pw=documenti_pw,
            )
            risultato = _sincronizza_metadati_fascicolo_polisweb(
                fascicolo_pw=fascicolo_pw,
                fascicolo_locale=fascicolo_locale,
                gestione_fascicoli=gestione_fascicoli,
                gestione_clienti=gestione_clienti,
                avvocato_referente=avvocato_referente,
                gestione_soggetti=gestione_soggetti,
                documenti_pw=documenti_pw_effettivi,
            )
            risultato.avvisi.extend(avvisi_documenti)
            return risultato
        except Exception as e:
            return RisultatoImportazione(
                successo=False,
                id_fascicolo_locale=getattr(fascicolo_locale, "id", None),
                messaggio=f"Errore durante la sincronizzazione: {e}",
                fascicolo_polis=fascicolo_pw,
            )

    # ---------------------------------------------------------------- SOAP helpers

    def _get_client(self, wsdl_url: str):
        """
        Crea (e memorizza in cache) un client zeep con autenticazione
        tramite certificato client.
        """
        if wsdl_url in self._zeep_cache:
            return self._zeep_cache[wsdl_url]

        try:
            import zeep
            import zeep.transports
        except ImportError:
            raise ImportError("Installa zeep: pip install zeep")

        parsed = urlparse(wsdl_url)
        pst_host = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else _WSP_BASE
        session = self._build_requests_session(pst_host)
        transport = zeep.transports.Transport(session=session, timeout=self.timeout)
        client = zeep.Client(wsdl=wsdl_url, transport=transport)
        self._zeep_cache[wsdl_url] = client
        return client

    def _build_requests_session(self, pst_host: str):
        from requests import Session

        if _pst_endpoint_legacy(pst_host):
            raise RuntimeError(_pst_endpoint_legacy_message())

        session = Session()
        usa_pem = (
            self.cert_pem_path and self.key_pem_path
            and os.path.exists(self.cert_pem_path)
            and os.path.exists(self.key_pem_path)
        )

        if usa_pem:
            if self.key_pem_password:
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives import serialization
                with open(self.key_pem_path, "rb") as f:
                    key_data = f.read()
                private_key = serialization.load_pem_private_key(
                    key_data, password=self.key_pem_password, backend=default_backend()
                )
                key_pem_plain = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
                tmp = tempfile.NamedTemporaryFile(suffix=".key", delete=False)
                tmp.write(key_pem_plain)
                tmp.flush()
                session.cert = (self.cert_pem_path, tmp.name)
            else:
                session.cert = (self.cert_pem_path, self.key_pem_path)
        elif self.p12_path and os.path.exists(self.p12_path):
            try:
                from requests_pkcs12 import Pkcs12Adapter
            except ImportError:
                raise ImportError("Installa requests-pkcs12: pip install requests-pkcs12")
            adapter = Pkcs12Adapter(
                pkcs12_filename=self.p12_path,
                pkcs12_password=self.p12_password,
            )
            session.mount(pst_host, adapter)
        else:
            raise FileNotFoundError(
                "Nessun certificato disponibile per l'autenticazione al PST. "
                "Configurare P12 (PCT_FIRMA_P12) oppure PEM (PCT_FIRMA_CERT + PCT_FIRMA_KEY)."
            )

        return session

    def _get_session(self, base_url: str):
        cache_key = base_url.rstrip("/")
        if cache_key in self._session_cache:
            return self._session_cache[cache_key]

        parsed = urlparse(cache_key)
        pst_host = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else _WSP_BASE
        session = self._build_requests_session(pst_host)
        self._session_cache[cache_key] = session
        return session

    def _execute_qbuilder(self, base_url: str, body: str) -> str:
        if not self.cf_avvocato:
            raise ValueError("Configurare il codice fiscale dell'avvocato (PCT_CF_AVVOCATO) per il PST.")

        session = self._get_session(base_url)
        try:
            response = session.post(
                base_url.rstrip("/"),
                data=body.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "",
                    "X-WASP-User": self.cf_avvocato,
                },
                timeout=self.timeout,
            )
        except Exception as e:
            raise ConnectionError(f"Errore chiamata PST: {e}") from e

        text_resp = response.text or ""
        fault = _soap_fault_message(text_resp)
        if response.status_code >= 400:
            raise ConnectionError(
                f"Errore chiamata PST: HTTP {response.status_code} {response.reason or ''}".strip()
            )
        if fault:
            raise ConnectionError(f"Errore chiamata PST: {fault}")
        return text_resp

    def _soap_qbuilder_envelope(self, body_inner: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">'
            '<SOAP-ENV:Header/>'
            f'<SOAP-ENV:Body>{body_inner}</SOAP-ENV:Body>'
            '</SOAP-ENV:Envelope>'
        )

    def _soap_qbuilder_execute_body(
        self,
        base_pst: str,
        codice_ufficio: str,
        name: str,
        values: List[tuple[str, str, Any]],
        order_by: str = "",
    ) -> str:
        ns = _pst_namespace_qbuilder(base_pst)
        valori = ''.join(
            f'<value name="{k}" type="{tipo}">{"" if v is None else v}</value>'
            for k, tipo, v in values
        )
        order_xml = f'<orderBy><entry property="{order_by}" mode="asc"/></orderBy>' if order_by else '<orderBy/>'
        body = (
            f'<execute xmlns="{ns}">'
            f'<domain><InvocationDomain name="JPW" role="AVV" group="{codice_ufficio}"/></domain>'
            f'<name>{name}</name>'
            f'<valueSet>{valori}</valueSet>'
            f'{order_xml}'
            '</execute>'
        )
        return self._soap_qbuilder_envelope(body)

    def _soap_ricerca_fascicoli_qbuilder(
        self,
        base_pst: str,
        codice_ufficio: str,
        numero_rg: Optional[str],
        anno_rg: Optional[int],
        nome_parte: Optional[str],
        codice_fiscale_parte: Optional[str],
    ) -> str:
        if numero_rg and anno_rg:
            return self._soap_qbuilder_execute_body(
                base_pst,
                codice_ufficio,
                'RicercaInformazioniFascicoloPerTipo',
                [
                    ('tipo', 'string', 'RGN'),
                    ('idUfficio', 'string', codice_ufficio),
                    ('annoRuolo', 'long', anno_rg),
                    ('numeroRuolo', 'string', numero_rg),
                ],
                order_by='ANNORUOLO, NUMERORUOLO',
            )

        return self._soap_qbuilder_execute_body(
            base_pst,
            codice_ufficio,
            'RicercaInformazioniFascicoloPerPartiGiudiceDate',
            [
                ('idUfficio', 'string', codice_ufficio),
                ('cognomeNome', 'string', nome_parte or ''),
                ('codiceFiscale', 'string', (codice_fiscale_parte or '').upper()),
                ('giudice', 'string', ''),
                ('dataRuoloDa', 'string', ''),
                ('dataRuoloA', 'string', ''),
            ],
            order_by='ANNORUOLO, NUMERORUOLO',
        )

    def _soap_documenti_qbuilder(self, base_pst: str, codice_ufficio: str, numero_rg: str, anno_rg: int) -> str:
        return self._soap_qbuilder_execute_body(
            base_pst,
            codice_ufficio,
            'DocumentiFascicolo',
            [
                ('idUfficio', 'string', codice_ufficio),
                ('annoRuolo', 'long', anno_rg),
                ('numeroRuolo', 'string', numero_rg),
                ('subProc', 'string', ''),
            ],
        )

    def _soap_profilo_fascicolo_qbuilder(self, base_pst: str, codice_ufficio: str, fascicolo: FascicoloPolisWeb) -> str:
        return self._soap_qbuilder_execute_body(
            base_pst,
            codice_ufficio,
            'ProfiloFascicolo',
            [
                ('idUfficio', 'string', codice_ufficio),
                ('annoRuolo', 'long', fascicolo.anno_rg),
                ('numeroRuolo', 'string', fascicolo.numero_rg),
                ('subProc', 'string', ''),
            ],
        )

    def _risolvi_codice_ufficio(self, nome_o_codice: str) -> str:
        """Risolve nome tribunale -> codice ufficio MinGiust."""
        return risolvi_codice_ministero(nome_o_codice)

    def _risolvi_base_pst(self, nome_o_codice: str) -> str:
        return risolvi_base_pst(nome_o_codice, base_url=_WSP_BASE)

    # ---------------------------------------------------------------- Parser risposte SOAP

    def _parse_fascicoli(self, risposta: Any) -> List[FascicoloPolisWeb]:
        """Converte la risposta SOAP in lista di FascicoloPolisWeb."""
        fascicoli = []
        try:
            items = risposta.fascicoli or risposta.fascicolo or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                f = FascicoloPolisWeb(
                    numero_rg=str(getattr(item, 'numeroRG', '') or ''),
                    anno_rg=int(getattr(item, 'annoRG', 0) or 0),
                    ruolo=str(getattr(item, 'ruolo', 'CIVILE_COGNIZIONE') or ''),
                    stato=str(getattr(item, 'stato', 'PENDENTE') or ''),
                    oggetto=str(getattr(item, 'oggetto', '') or ''),
                    sezione=str(getattr(item, 'sezione', '') or ''),
                    giudice=str(getattr(item, 'giudice', '') or ''),
                    data_iscrizione=_parse_data(getattr(item, 'dataIscrizione', None)),
                    data_udienza=_parse_data(getattr(item, 'dataUdienza', None)),
                    parti=_parse_parti(getattr(item, 'parti', None)),
                    codice_ufficio=str(getattr(item, 'codiceUfficio', '') or ''),
                    nome_ufficio=str(getattr(item, 'nomeUfficio', '') or ''),
                )
                fascicoli.append(f)
        except (AttributeError, TypeError, ValueError):
            pass
        return fascicoli

    def _parse_fascicoli_qbuilder_xml(self, xml_text: str) -> List[FascicoloPolisWeb]:
        fascicoli: List[FascicoloPolisWeb] = []
        for row in _parse_qbuilder_row_list(xml_text):
            fascicolo = _map_qbuilder_fascicolo(row)
            setattr(fascicolo, 'parti_dettaglio', _qbuilder_parti_dettaglio(row))
            fascicoli.append(fascicolo)
        return fascicoli

    def _parse_documenti(self, risposta: Any) -> List[DocumentoPolisWeb]:
        """Converte la risposta SOAP in lista di DocumentoPolisWeb."""
        documenti: List[DocumentoPolisWeb] = []
        visti: set[tuple[str, str, str, str, str, str]] = set()
        try:
            for item in _collect_soap_documenti(risposta):
                fields = _soap_documento_fields(item)
                disponibile_raw = fields.get('disponibile', True)
                if isinstance(disponibile_raw, str):
                    disponibile = disponibile_raw.strip().lower() != "false"
                else:
                    disponibile = bool(disponibile_raw)
                try:
                    dimensione = int(fields.get('dimensione', 0) or 0)
                except (TypeError, ValueError):
                    dimensione = 0
                d = DocumentoPolisWeb(
                    id_documento=str(fields.get('idDocumento', fields.get('id', '')) or ''),
                    nome=str(fields.get('nomeFile', fields.get('nome', '')) or ''),
                    tipo=str(fields.get('tipoDocumento', fields.get('tipo', 'ATTO')) or ''),
                    data_deposito=_parse_data(fields.get('dataDeposito')),
                    mittente=str(fields.get('mittente', fields.get('cfMittente', '')) or ''),
                    dimensione_bytes=dimensione,
                    disponibile=disponibile,
                    id_deposito=str(fields.get('idBusta', fields.get('idDeposito', '')) or ''),
                    tipo_atto=str(fields.get('tipoAtto', fields.get('descTipoAtto', fields.get('tipoAtta', ''))) or ''),
                )
                chiave = (
                    d.id_documento,
                    d.nome,
                    d.tipo,
                    d.data_deposito,
                    d.mittente,
                    d.id_deposito,
                )
                if chiave in visti:
                    continue
                visti.add(chiave)
                documenti.append(d)
        except (AttributeError, TypeError, ValueError):
            pass
        return documenti

    def _parse_documenti_qbuilder_xml(self, xml_text: str) -> List[DocumentoPolisWeb]:
        return [_map_qbuilder_documento(row) for row in _parse_qbuilder_row_list(xml_text)]

    def _arricchisci_fascicoli_con_profilo(self, base_pst: str, fascicoli: List[FascicoloPolisWeb]) -> List[FascicoloPolisWeb]:
        arricchiti: List[FascicoloPolisWeb] = []
        for fascicolo in fascicoli:
            codice_ufficio = fascicolo.codice_ufficio or self._risolvi_codice_ufficio(fascicolo.nome_ufficio)
            if not codice_ufficio:
                arricchiti.append(fascicolo)
                continue
            try:
                xml = self._execute_qbuilder(
                    base_pst,
                    self._soap_profilo_fascicolo_qbuilder(base_pst, codice_ufficio, fascicolo),
                )
                profili = self._parse_fascicoli_qbuilder_xml(xml)
            except Exception:
                arricchiti.append(fascicolo)
                continue
            if not profili:
                arricchiti.append(fascicolo)
                continue
            profilo = profili[0]
            for attr in ('ruolo', 'stato', 'oggetto', 'sezione', 'giudice', 'data_iscrizione', 'data_udienza', 'nome_ufficio'):
                valore = getattr(profilo, attr, '') or getattr(fascicolo, attr, '')
                setattr(fascicolo, attr, valore)
            if getattr(profilo, 'parti', None):
                fascicolo.parti = profilo.parti
                setattr(fascicolo, 'parti_dettaglio', getattr(profilo, 'parti_dettaglio', []))
            arricchiti.append(fascicolo)
        return arricchiti

# ================================================================ Demo / offline

class ClientPolisWebDemo(ClientPolisWeb):
    """
    Implementazione demo (offline) per sviluppo e test senza connessione PST.
    Restituisce dati fittizi verosimili.
    """

    def _nome_ufficio_demo(self, codice_o_nome: str) -> str:
        try:
            import os
            from pct.uffici_giudiziari import get_gestore
            gestore = get_gestore(os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"))
            uff = next((u for u in gestore.carica() if u.get("codice") == codice_o_nome), None)
            return uff["nome"] if uff else f"Ufficio {codice_o_nome}"
        except Exception:
            return f"Ufficio {codice_o_nome}"

    def __init__(self):
        # Non richiede certificato
        self.p12_path = ""
        self.p12_password = b""
        self.cf_avvocato = "DEMO"
        self.timeout = 5
        self._zeep_cache = {}
        self._session_cache = {}

    def ricerca_fascicoli(self, tribunale: str, numero_rg=None,
                          anno_rg=None, nome_parte=None,
                          codice_fiscale_parte=None,
                          max_risultati: int = 50) -> List[FascicoloPolisWeb]:
        """Ritorna fascicoli demo."""
        anno = anno_rg or date.today().year
        return [
            FascicoloPolisWeb(
                numero_rg=numero_rg or "1234",
                anno_rg=anno,
                ruolo="CIVILE_COGNIZIONE",
                stato="PENDENTE",
                oggetto="Causa di risarcimento danni — Demo",
                sezione="Prima sezione civile",
                giudice="Dr. Mario Rossi",
                data_iscrizione=f"{anno}-01-15",
                data_udienza=f"{date.today().year + (1 if date.today().month >= 10 else 0)}-03-20",
                parti=["Mario Bianchi", "Alfa S.p.A."],
                note="Dato demo — collegare al PST con certificato reale",
                codice_ufficio=tribunale if tribunale.isdigit() else "0000000",
                nome_ufficio=self._nome_ufficio_demo(tribunale),
            )
        ]

    def consulta_documenti(self, codice_ufficio, numero_rg, anno_rg) -> List[DocumentoPolisWeb]:
        """
        Dati demo: simula un fascicolo telematico con 4 buste realistiche
        (Decreto Ingiuntivo, Comparsa di risposta, Memoria, Provvedimento cancelleria).
        """
        anno = str(anno_rg)
        # Busta 1 — Ricorso per Decreto Ingiuntivo (depositato dall'avvocato ricorrente)
        busta1 = [
            DocumentoPolisWeb(
                id_documento="DEMO-B1-001", nome=f"DI_ricorso_{numero_rg}_{anno}.pdf.p7m",
                tipo="ATTO", data_deposito=f"{anno}-01-15",
                mittente="avv.demo@pec.it", dimensione_bytes=312320,
                id_deposito="BUSTA-DI-001", tipo_atto="Decreto Ingiuntivo",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B1-002", nome="DI_procura_alle_liti.pdf.p7m",
                tipo="ALLEGATO", data_deposito=f"{anno}-01-15",
                mittente="avv.demo@pec.it", dimensione_bytes=98304,
                id_deposito="BUSTA-DI-001", tipo_atto="Decreto Ingiuntivo",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B1-003", nome="DI_indice_documenti.xml",
                tipo="INDICE", data_deposito=f"{anno}-01-15",
                mittente="avv.demo@pec.it", dimensione_bytes=4096,
                id_deposito="BUSTA-DI-001", tipo_atto="Decreto Ingiuntivo",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B1-004", nome="DI_contratto_fornitura.pdf.p7m",
                tipo="ALLEGATO", data_deposito=f"{anno}-01-15",
                mittente="avv.demo@pec.it", dimensione_bytes=204800,
                id_deposito="BUSTA-DI-001", tipo_atto="Decreto Ingiuntivo",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B1-005", nome="DI_fatture_insolute.pdf.p7m",
                tipo="ALLEGATO", data_deposito=f"{anno}-01-15",
                mittente="avv.demo@pec.it", dimensione_bytes=153600,
                id_deposito="BUSTA-DI-001", tipo_atto="Decreto Ingiuntivo",
            ),
        ]
        # Busta 2 — Decreto Ingiuntivo emesso dalla cancelleria
        busta2 = [
            DocumentoPolisWeb(
                id_documento="DEMO-B2-001", nome=f"decreto_ingiuntivo_{numero_rg}_{anno}.pdf",
                tipo="PROVVEDIMENTO", data_deposito=f"{anno}-01-28",
                mittente="cancelleria@tribunale.giustiziapec.it", dimensione_bytes=87040,
                id_deposito="BUSTA-DI-PROV-002", tipo_atto="Provvedimento — Decreto Ingiuntivo",
                disponibile=True,
            ),
        ]
        # Busta 3 — Opposizione al Decreto Ingiuntivo (controparte)
        busta3 = [
            DocumentoPolisWeb(
                id_documento="DEMO-B3-001", nome="opposizione_DI.pdf.p7m",
                tipo="ATTO", data_deposito=f"{anno}-02-20",
                mittente="avv.controparte@pec.it", dimensione_bytes=198656,
                id_deposito="BUSTA-OPP-003", tipo_atto="Opposizione a Decreto Ingiuntivo",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B3-002", nome="opposizione_procura.pdf.p7m",
                tipo="ALLEGATO", data_deposito=f"{anno}-02-20",
                mittente="avv.controparte@pec.it", dimensione_bytes=81920,
                id_deposito="BUSTA-OPP-003", tipo_atto="Opposizione a Decreto Ingiuntivo",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B3-003", nome="opposizione_indice.xml",
                tipo="INDICE", data_deposito=f"{anno}-02-20",
                mittente="avv.controparte@pec.it", dimensione_bytes=3072,
                id_deposito="BUSTA-OPP-003", tipo_atto="Opposizione a Decreto Ingiuntivo",
            ),
        ]
        # Busta 4 — Memoria difensiva (avvocato ricorrente in sede di opposizione)
        busta4 = [
            DocumentoPolisWeb(
                id_documento="DEMO-B4-001", nome="memoria_difensiva.pdf.p7m",
                tipo="ATTO", data_deposito=f"{anno}-03-10",
                mittente="avv.demo@pec.it", dimensione_bytes=265216,
                id_deposito="BUSTA-MEM-004", tipo_atto="Memoria Difensiva",
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-B4-002", nome="memoria_documenti_nuovi.pdf.p7m",
                tipo="ALLEGATO", data_deposito=f"{anno}-03-10",
                mittente="avv.demo@pec.it", dimensione_bytes=122880,
                id_deposito="BUSTA-MEM-004", tipo_atto="Memoria Difensiva",
            ),
        ]
        return busta1 + busta2 + busta3 + busta4


class ClientPolisWebImportOnly(ClientPolisWebDemo):
    """
    Client logico per importazioni PST già autenticate dal browser / Local Signer.

    Non richiede certificati lato server e non effettua consultazioni remote:
    importa soltanto i metadati del fascicolo e gli eventuali documenti già
    prelevati dal canale locale.
    """

    def _precarica_documenti_importazione(
        self,
        fascicolo_pw: FascicoloPolisWeb,
        documenti_pw: Optional[List[DocumentoPolisWeb]] = None,
    ) -> tuple[List[DocumentoPolisWeb], List[str]]:
        if documenti_pw is not None:
            return list(documenti_pw), []
        return [], []


# ================================================================ Utils


# Sezioni wizard fascicolo PST (usate da classifica_sezione_pst e dal template pst_wizard.html)
PST_SEZIONI_WIZARD: List[Dict[str, Any]] = [
    {
        "id": "attivita_processuali",
        "label": "Attività processuali",
        "icon": "bi-file-earmark-arrow-up-fill",
        "colore": "primary",
        "descrizione": "Atti depositati dalle parti: ricorsi, citazioni, memorie, opposizioni, comparse.",
    },
    {
        "id": "documenti_fascicolo",
        "label": "Documenti fascicolo",
        "icon": "bi-paperclip",
        "colore": "secondary",
        "descrizione": "Allegati, indici documenti e file di corredo ai depositi.",
    },
    {
        "id": "udienze_scadenze",
        "label": "Udienze e scadenze",
        "icon": "bi-calendar-event-fill",
        "colore": "info",
        "descrizione": "Verbali di udienza, calendari e scadenze processuali.",
    },
    {
        "id": "comunicazioni_cancelleria",
        "label": "Comunicazioni di cancelleria",
        "icon": "bi-megaphone-fill",
        "colore": "success",
        "descrizione": "Provvedimenti, decreti, sentenze, ordinanze e comunicazioni della cancelleria.",
    },
    {
        "id": "istanze",
        "label": "Istanze",
        "icon": "bi-envelope-paper-fill",
        "colore": "warning",
        "descrizione": "Istanze, richieste e relativi esiti presenti sul portale.",
    },
]

_PST_SEZIONE_ID_MAP = {s["id"]: s for s in PST_SEZIONI_WIZARD}


def classifica_sezione_pst(doc: "DocumentoPolisWeb") -> str:
    """
    Classifica un DocumentoPolisWeb nella sezione wizard corrispondente.
    Ritorna uno degli id: attivita_processuali | documenti_fascicolo |
                          udienze_scadenze | comunicazioni_cancelleria | istanze

    La logica è allineata con sezionePstDaCatalogoItem() in dettaglio.html.
    """
    tipo_atto = (doc.tipo_atto or doc.tipo or "").lower()
    nome = (doc.nome or "").lower()
    mittente = (doc.mittente or "").lower()
    testo = f"{tipo_atto} {nome}"

    if "istanza" in testo:
        return "istanze"

    if any(k in testo for k in ("verbale udienza", "verbaleudienza", "verbale", "udienza")):
        return "udienze_scadenze"

    if any(k in testo for k in ("ordinanza", "decreto", "sentenza", "provvedimento")):
        return "comunicazioni_cancelleria"
    if doc.tipo in ("PROVVEDIMENTO",):
        return "comunicazioni_cancelleria"
    if "cancelleria" in mittente:
        return "comunicazioni_cancelleria"

    if any(nome.endswith(ext) for ext in (".eml", ".msg", ".xml")):
        return "comunicazioni_cancelleria"
    if any(k in testo for k in ("comunicazione", "pec", "ricevuta", "esito")):
        return "comunicazioni_cancelleria"

    if doc.tipo in ("ALLEGATO", "INDICE"):
        return "documenti_fascicolo"

    return "attivita_processuali"


def raggruppa_per_sezioni_wizard(
    documenti: List["DocumentoPolisWeb"],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Raggruppa una lista di DocumentoPolisWeb per sezione wizard e per deposito.

    Ritorna un dict: {sezione_id: [{id_deposito, tipo_atto, data_deposito, mittente, documenti[]}]}
    """
    from collections import OrderedDict

    sezioni: Dict[str, OrderedDict] = {s["id"]: OrderedDict() for s in PST_SEZIONI_WIZARD}

    for doc in sorted(documenti, key=lambda d: d.data_deposito or "", reverse=True):
        sezione_id = classifica_sezione_pst(doc)
        chiave = doc.id_deposito or f"__{doc.data_deposito}__{doc.mittente}"
        gruppi = sezioni[sezione_id]
        if chiave not in gruppi:
            gruppi[chiave] = {
                "id_deposito": doc.id_deposito or chiave,
                "tipo_atto": doc.tipo_atto or doc.tipo.replace("_", " ").title(),
                "data_deposito": doc.data_deposito,
                "mittente": doc.mittente,
                "documenti": [],
            }
        gruppi[chiave]["documenti"].append(doc)

    return {sid: list(gruppi.values()) for sid, gruppi in sezioni.items()}


def _parse_data(valore: Any) -> str:
    """Converte una data SOAP in stringa ISO YYYY-MM-DD."""
    if not valore:
        return ""
    if isinstance(valore, (datetime, date)):
        return valore.strftime("%Y-%m-%d")
    testo = str(valore).strip()
    candidati = [testo]
    if len(testo) >= 10:
        candidati.append(testo[:10])
    for candidato in candidati:
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(candidato, formato).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return testo[:10]


def _parse_parti(valore: Any) -> List[str]:
    """Estrae la lista delle parti dalla risposta SOAP."""
    if not valore:
        return []
    if isinstance(valore, list):
        return [str(p) for p in valore]
    if hasattr(valore, "parte"):
        parti = valore.parte
        if not isinstance(parti, list):
            parti = [parti]
        return [str(p.nominativo or p) for p in parti]
    return [str(valore)]


def crea_client(
    p12_path: Optional[str] = None,
    p12_password: Optional[bytes] = None,
    cf_avvocato: str = "",
    demo: bool = False,
    cert_pem_path: Optional[str] = None,
    key_pem_path: Optional[str] = None,
    key_pem_password: Optional[bytes] = None,
) -> ClientPolisWeb:
    """
    Factory: crea il client PolisWeb appropriato.

    Supporta due formati di certificato (in ordine di priorità):
      1. P12/PFX — PCT_FIRMA_P12 + PCT_FIRMA_PASSWORD
      2. PEM     — PCT_FIRMA_CERT + PCT_FIRMA_KEY [+ PCT_FIRMA_KEY_PASSWORD]

    Args:
        p12_path:         Percorso al P12 (None = usa PCT_FIRMA_P12 da env).
        p12_password:     Password P12 (None = usa PCT_FIRMA_PASSWORD da env).
        cf_avvocato:      Codice fiscale avvocato (None = usa PCT_CF_AVVOCATO da env).
        demo:             True = usa ClientPolisWebDemo (no connessione reale).
        cert_pem_path:    Percorso al cert PEM (None = usa PCT_FIRMA_CERT da env).
        key_pem_path:     Percorso alla chiave PEM (None = usa PCT_FIRMA_KEY da env).
        key_pem_password: Password chiave PEM (None = usa PCT_FIRMA_KEY_PASSWORD da env).

    Returns:
        ClientPolisWeb o ClientPolisWebDemo.

    Raises:
        FileNotFoundError: se nessun certificato è configurato o trovato su disco.
    """
    if demo:
        return ClientPolisWebDemo()

    cf = cf_avvocato or os.getenv("PCT_CF_AVVOCATO", "")

    # ── Formato P12 ──────────────────────────────────────────────────────────
    p12 = p12_path or os.getenv("PCT_FIRMA_P12", "")
    pwd = p12_password or os.getenv("PCT_FIRMA_PASSWORD", "").encode()
    if p12 and os.path.exists(p12):
        return ClientPolisWeb(
            p12_path=p12,
            p12_password=pwd,
            codice_fiscale_avvocato=cf,
        )

    # ── Formato PEM ──────────────────────────────────────────────────────────
    cert = cert_pem_path or os.getenv("PCT_FIRMA_CERT", "")
    key  = key_pem_path  or os.getenv("PCT_FIRMA_KEY", "")
    key_pwd_str = os.getenv("PCT_FIRMA_KEY_PASSWORD", "")
    key_pwd = key_pem_password or (key_pwd_str.encode() if key_pwd_str else None)

    if cert and key and os.path.exists(cert) and os.path.exists(key):
        return ClientPolisWeb(
            cert_pem_path=cert,
            key_pem_path=key,
            key_pem_password=key_pwd,
            codice_fiscale_avvocato=cf,
        )

    # ── Nessun certificato disponibile ───────────────────────────────────────
    raise FileNotFoundError(
        "Nessun certificato configurato per l'accesso al PST.\n"
        "Opzione A — P12/PFX: impostare PCT_FIRMA_P12 e PCT_FIRMA_PASSWORD nel file .env\n"
        "Opzione B — PEM:     impostare PCT_FIRMA_CERT e PCT_FIRMA_KEY nel file .env\n"
        "In alternativa configurare i percorsi in Impostazioni → Firma Digitale."
    )

