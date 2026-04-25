"""Normalizzazione payload autorizzati per import guidato portali.

Il modulo non interroga portali e non legge HTML: trasforma payload gia'
ottenuti da Local Connector, PdA, Model Office o import manuale in una forma
compatibile con il wizard di acquisizione e con la UI fascicolo IUSENTRA.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


def _safe(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _first(mapping: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        text = str(value).strip()
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        return float(text)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "si", "s", "on", "ok"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        for key in (
            "items",
            "rows",
            "parti",
            "soggetti",
            "eventi",
            "udienze",
            "documenti",
            "allegati",
            "depositi",
            "comunicazioni",
            "istanze",
        ):
            inner = value.get(key)
            if isinstance(inner, list):
                return inner
        return [value]
    return [value]


def _hash_snapshot(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalizza_data(value: Any) -> str:
    text = _safe(value)
    if not text:
        return ""
    text = text.replace(".", "/").strip()
    for sep in ("T", " "):
        if sep in text and re.match(r"^\d{4}-\d{2}-\d{2}", text):
            text = text.split(sep, 1)[0]
            break
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text[:10] if len(text) >= 10 else text


def _party_name(row: dict[str, Any]) -> str:
    denominazione = _safe(_first(row, "denominazione", "ragione_sociale", "ragioneSociale", "ente"))
    if denominazione:
        return denominazione
    nome = _safe(_first(row, "nome", "first_name"))
    cognome = _safe(_first(row, "cognome", "last_name"))
    return " ".join(part for part in (cognome, nome) if part).strip()


def _normalizza_parte(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {"denominazione": _safe(raw)}
    return {
        "ruolo": _safe(_first(row, "ruolo", "qualifica", "tipoParte", "qualificaProcessuale")),
        "tipo": _safe(_first(row, "tipo", "tipo_soggetto", "tipoSoggetto")),
        "nome": _safe(_first(row, "nome", "first_name")),
        "cognome": _safe(_first(row, "cognome", "last_name")),
        "denominazione": _safe(_first(row, "denominazione", "ragione_sociale", "ragioneSociale", "ente")),
        "codice_fiscale": _safe(_first(row, "codice_fiscale", "codiceFiscale", "cf")),
        "partita_iva": _safe(_first(row, "partita_iva", "partitaIva", "piva")),
        "pec": _safe(_first(row, "pec", "email_pec", "emailPec")),
        "difensore": _safe(_first(row, "difensore", "avvocato", "legale")),
        "raw": row,
    }


def _normalizza_evento(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {"descrizione": _safe(raw)}
    return {
        "evento_uid": _safe(_first(row, "evento_uid", "eventoUid", "uid", "id", "id_evento")),
        "tipo_evento": _safe(_first(row, "tipo_evento", "tipoEvento", "tipo", "titolo", "evento")),
        "descrizione": _safe(_first(row, "descrizione", "description", "dettaglio", "note", "testo")),
        "data_evento": _normalizza_data(_first(row, "data_evento", "dataEvento", "data", "created_at")),
        "esito": _safe(_first(row, "esito", "stato")),
        "raw": row,
    }


def _normalizza_udienza(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {"data_udienza": _safe(raw)}
    return {
        "udienza_uid": _safe(_first(row, "udienza_uid", "udienzaUid", "uid", "id", "id_udienza")),
        "data_udienza": _normalizza_data(_first(row, "data_udienza", "dataUdienza", "data")),
        "ora": _safe(_first(row, "ora", "time", "orario")),
        "tipo": _safe(_first(row, "tipo", "tipo_udienza", "tipoUdienza")),
        "descrizione": _safe(_first(row, "descrizione", "note", "dettaglio")),
        "esito": _safe(_first(row, "esito", "stato")),
        "giudice": _safe(_first(row, "giudice", "relatore", "gip", "gup", "collegio")),
        "raw": row,
    }


def _servizio_da_sezione(sezione: str, tipo: str = "") -> str:
    text = f"{sezione} {tipo}".lower()
    if "istan" in text:
        return "DettaglioIstanze"
    if "comunic" in text or "canceller" in text or "notific" in text:
        return "ComunicazioneCancelleria"
    if "udienz" in text or "scadenz" in text:
        return "RicercaScadenze"
    return "DocumentiFascicolo"


def _normalizza_documento(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {"nome_file": _safe(raw)}
    nome = _safe(_first(row, "nome_file", "nomeFile", "nome", "filename", "file_name", "titolo"))
    doc_id = _safe(_first(row, "documento_uid", "documentoUid", "uid", "id", "id_documento", "idDocumento"))
    if not doc_id and nome:
        doc_id = hashlib.sha1(nome.encode("utf-8")).hexdigest()[:16]
    sezione = _safe(_first(row, "sezione", "categoria", "cartella"))
    tipo = _safe(_first(row, "classificazione", "tipo_documento", "tipoDocumento", "tipo"))
    tipo_atto = _safe(_first(row, "tipo_atto", "tipoAtto", "atto", "tipo"))
    data_deposito = _normalizza_data(_first(row, "data_deposito", "dataDeposito", "data_invio", "dataInvio", "data"))
    return {
        "id_documento": doc_id,
        "id_cat": _safe(_first(row, "id_cat", "idCat")),
        "id_repeatto": _safe(_first(row, "id_repeatto", "idReperto", "idRep")),
        "msg_id": _safe(_first(row, "msg_id", "message_id", "messageId")),
        "nome": nome,
        "tipo": tipo or tipo_atto or "Documento",
        "tipo_atto": tipo_atto or tipo or "Documento",
        "data_deposito": data_deposito,
        "mittente": _safe(_first(row, "depositante", "mittente", "firmatario", "autore")),
        "dimensione_bytes": _as_int(_first(row, "dimensione_bytes", "dimensioneBytes", "size", "size_bytes")),
        "disponibile": _as_bool(_first(row, "scaricabile", "disponibile", "downloadable", default=True), True),
        "id_deposito": _safe(_first(row, "id_deposito", "id_deposito_esterno", "deposito_uid", "depositoUid")),
        "servizio_portale": _safe(_first(row, "servizio_portale", "servizioPortale"))
        or _servizio_da_sezione(sezione, f"{tipo} {tipo_atto}"),
        "sezione_portale": sezione,
        "data_documento": _normalizza_data(_first(row, "data_documento", "dataDocumento")),
        "path_locale": _safe(_first(row, "path_locale", "pathLocale", "local_path", "path")),
        "sha256": _safe(_first(row, "sha256", "hash")),
        "raw": row,
    }


def _normalizza_comunicazione(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {"oggetto": _safe(raw)}
    return {
        "comunicazione_uid": _safe(_first(row, "comunicazione_uid", "comunicazioneUid", "uid", "id")),
        "tipo": _safe(_first(row, "tipo", "categoria", "canale")),
        "oggetto": _safe(_first(row, "oggetto", "subject", "titolo")),
        "data_comunicazione": _normalizza_data(_first(row, "data_comunicazione", "dataComunicazione", "data", "date")),
        "mittente": _safe(_first(row, "mittente", "from")),
        "destinatario": _safe(_first(row, "destinatario", "to")),
        "stato": _safe(_first(row, "stato", "esito")),
        "raw": row,
    }


def _normalizza_deposito(raw: Any) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {"tipo_atto": _safe(raw)}
    return {
        "deposito_uid": _safe(_first(row, "deposito_uid", "depositoUid", "uid", "id", "identificativo")),
        "tipo_atto": _safe(_first(row, "tipo_atto", "tipoAtto", "atto", "tipo")),
        "stato": _safe(_first(row, "stato", "status", "esito")),
        "data_invio": _normalizza_data(_first(row, "data_invio", "dataInvio", "data")),
        "data_esito": _normalizza_data(_first(row, "data_esito", "dataEsito")),
        "mittente": _safe(_first(row, "mittente", "depositante")),
        "messaggio_esito": _safe(_first(row, "messaggio_esito", "messaggioEsito", "messaggio", "note")),
        "atto_principale": _safe(_first(row, "atto_principale", "attoPrincipale", "nome_file", "nomeFile")),
        "servizio_portale": _safe(_first(row, "servizio_portale", "servizioPortale")),
        "raw": row,
    }


def _split_parti(portale: str, parti: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    assistiti: list[str] = []
    controparti: list[str] = []
    for parte in parti:
        name = _party_name(parte)
        if not name:
            continue
        ruolo = _safe(parte.get("ruolo")).lower()
        if portale == "pdp":
            target = controparti if any(t in ruolo for t in ("offesa", "civile", "persona offesa")) else assistiti
        else:
            target = controparti if any(t in ruolo for t in ("resistente", "contro", "conven", "ente")) else assistiti
        if name not in target:
            target.append(name)
    return assistiti, controparti


def _fascicolo_raw(portale: str, payload: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "pdp": ("fascicolo", "procedimento", "selection", "pdp"),
        "pat": ("fascicolo", "ricorso", "selection", "pat"),
        "ptt": ("fascicolo", "ricorso", "controversia", "selection", "ptt", "sigit"),
        "pst": ("fascicolo", "selection", "polisweb", "pst"),
    }.get(portale, ("fascicolo", "selection"))
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return dict(value)
    return dict(payload)


def normalize_authorized_portale_payload(portale: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Restituisce selection, documenti e payload strutturato per il wizard."""

    portale = _safe(portale).lower()
    if portale not in {"pst", "pdp", "pat", "ptt"}:
        raise ValueError(f"Portale non supportato: {portale}")
    payload = dict(raw.get("payload") or raw.get("raw_payload") or raw or {})
    fasc_raw = _fascicolo_raw(portale, payload)

    if portale == "pdp":
        numero = _safe(_first(fasc_raw, "numero", "numero_rg", "numeroRG", "nrg", "nr"))
        anno = _as_int(_first(fasc_raw, "anno", "anno_rg", "annoRG"))
        registro = _safe(_first(fasc_raw, "registro", "tipo_registro", "tipoRegistro", default="RGNR")) or "RGNR"
        ufficio = _safe(_first(fasc_raw, "ufficio", "ufficio_giudiziario", "ufficioGiudiziario", "tribunale", "procura", "nome_ufficio"))
        ufficio_codice = _safe(_first(fasc_raw, "ufficio_codice", "codice_ufficio", "codiceUfficio"))
        oggetto = _safe(_first(fasc_raw, "reato", "reato_ipotesi", "titolo_reato", "oggetto", "rubrica"))
        giudice = _safe(_first(fasc_raw, "giudice", "gip", "gup", "pm", "pubblico_ministero"))
        data_iscrizione = _normalizza_data(_first(fasc_raw, "data_iscrizione", "dataIscrizione"))
        data_udienza = _normalizza_data(_first(fasc_raw, "data_udienza", "dataUdienza"))
    elif portale == "pat":
        numero = _safe(_first(fasc_raw, "numero", "numero_ricorso", "numeroRicorso", "numero_rg", "numeroRG"))
        anno = _as_int(_first(fasc_raw, "anno", "anno_ricorso", "annoRicorso", "anno_rg", "annoRG"))
        registro = _safe(_first(fasc_raw, "registro", "tipo", "rito", default="RICORSO")) or "RICORSO"
        ufficio = _safe(_first(fasc_raw, "ufficio", "nome_ufficio", "nomeUfficio", "denominazioneUfficio", "tar"))
        ufficio_codice = _safe(_first(fasc_raw, "ufficio_codice", "codice_ufficio", "codiceUfficio"))
        oggetto = _safe(_first(fasc_raw, "oggetto", "oggetto_ricorso", "oggettoRicorso", "materia"))
        giudice = _safe(_first(fasc_raw, "giudice", "giudice_relatore", "giudiceRelatore", "relatore"))
        data_iscrizione = _normalizza_data(_first(fasc_raw, "data_iscrizione", "data_deposito", "dataDeposito"))
        data_udienza = _normalizza_data(_first(fasc_raw, "data_udienza", "dataUdienza"))
    elif portale == "ptt":
        numero = _safe(_first(fasc_raw, "numero", "numero_rgt", "numeroRgt", "numero_rg", "numeroRG"))
        anno = _as_int(_first(fasc_raw, "anno", "anno_rgt", "annoRgt", "anno_rg", "annoRG"))
        registro = _safe(_first(fasc_raw, "registro", "tipo", "grado", default="RGT")) or "RGT"
        ufficio = _safe(_first(fasc_raw, "ufficio", "commissione", "nome_commissione", "nomeCommissione", "corte"))
        ufficio_codice = _safe(_first(fasc_raw, "ufficio_codice", "codice_commissione", "codiceCommissione", "codice_ufficio"))
        oggetto = _safe(_first(fasc_raw, "oggetto", "oggetto_controversia", "oggettoControversia", "atto_impugnato", "materia"))
        giudice = _safe(_first(fasc_raw, "giudice", "giudice_relatore", "giudiceRelatore", "relatore"))
        data_iscrizione = _normalizza_data(_first(fasc_raw, "data_iscrizione", "data_deposito", "dataDeposito"))
        data_udienza = _normalizza_data(_first(fasc_raw, "data_udienza", "dataUdienza"))
    else:
        numero = _safe(_first(fasc_raw, "numero", "numero_rg", "numeroRG", "numeroRuolo"))
        anno = _as_int(_first(fasc_raw, "anno", "anno_rg", "annoRG", "annoRuolo"))
        registro = _safe(_first(fasc_raw, "registro", "ruolo", "tipo", default="RG")) or "RG"
        ufficio = _safe(_first(fasc_raw, "ufficio", "nome_ufficio", "nomeUfficio", "tribunale"))
        ufficio_codice = _safe(_first(fasc_raw, "ufficio_codice", "codice_ufficio", "codiceUfficio"))
        oggetto = _safe(_first(fasc_raw, "oggetto", "oggetto_fascicolo", "oggettoFascicolo"))
        giudice = _safe(_first(fasc_raw, "giudice"))
        data_iscrizione = _normalizza_data(_first(fasc_raw, "data_iscrizione", "dataIscrizione", "data_deposito"))
        data_udienza = _normalizza_data(_first(fasc_raw, "data_udienza", "dataUdienza"))

    parti_raw = _coerce_list(payload.get("parti") or payload.get("soggetti"))
    if not parti_raw:
        if portale == "pdp":
            parti_raw = [
                {"ruolo": "Imputato / indagato", "denominazione": value}
                for value in _coerce_list(fasc_raw.get("imputati") or fasc_raw.get("indagati"))
            ] + [
                {"ruolo": "Parte offesa", "denominazione": value}
                for value in _coerce_list(fasc_raw.get("parti_offese") or fasc_raw.get("persone_offese"))
            ]
        else:
            parti_raw = [
                {"ruolo": "Ricorrente", "denominazione": value}
                for value in _coerce_list(fasc_raw.get("ricorrenti") or fasc_raw.get("attori"))
            ] + [
                {"ruolo": "Resistente", "denominazione": value}
                for value in _coerce_list(fasc_raw.get("resistenti") or fasc_raw.get("convenuti"))
            ]
    parti = [_normalizza_parte(row) for row in parti_raw]
    assistiti, controparti = _split_parti(portale, parti)

    documenti = [_normalizza_documento(row) for row in _coerce_list(payload.get("documenti") or payload.get("allegati"))]
    eventi = [_normalizza_evento(row) for row in _coerce_list(payload.get("eventi"))]
    udienze = [_normalizza_udienza(row) for row in _coerce_list(payload.get("udienze"))]
    comunicazioni = [_normalizza_comunicazione(row) for row in _coerce_list(payload.get("comunicazioni"))]
    istanze = [_normalizza_evento(row) for row in _coerce_list(payload.get("istanze"))]
    depositi = [_normalizza_deposito(row) for row in _coerce_list(payload.get("depositi") or payload.get("invii"))]

    if data_udienza and not udienze:
        udienze.append(
            _normalizza_udienza(
                {
                    "data_udienza": data_udienza,
                    "tipo": "Udienza",
                    "giudice": giudice,
                    "descrizione": "Udienza rilevata dal payload autorizzato.",
                }
            )
        )

    external_id = _safe(
        _first(
            fasc_raw,
            "external_uid",
            "uid",
            "id",
            "id_fascicolo",
            "idFascicolo",
            "pat_uid",
            "pdp_uid",
            "ptt_uid",
            "sigit_uid",
        )
    )
    if not external_id:
        external_id = f"{portale.upper()}:{ufficio_codice or ufficio}:{registro}:{anno}:{numero}".replace(" ", "_")

    payload_structured = {
        "numero_rg": numero,
        "anno_rg": anno,
        "numero_ricorso": numero,
        "anno": anno,
        "numero_rgt": numero,
        "anno_rgt": anno,
        "ruolo": registro,
        "tipo_registro": registro,
        "tipo": registro,
        "stato": _safe(_first(fasc_raw, "stato", "stato_procedimento", "statoProcedimento")),
        "fase": _safe(_first(fasc_raw, "fase", "fase_procedimento", "faseProcedimento")),
        "reato": oggetto,
        "materia": _safe(_first(fasc_raw, "materia", "tipo_controversia", "tipoControversia")),
        "sezione": _safe(_first(fasc_raw, "sezione")),
        "giudice": giudice,
        "giudice_relatore": giudice,
        "data_iscrizione": data_iscrizione,
        "data_deposito": data_iscrizione,
        "data_udienza": data_udienza,
        "oggetto": oggetto,
        "oggetto_controversia": oggetto,
        "valore_controversia": _as_float(_first(fasc_raw, "valore", "valore_lite", "valoreLite", "valore_controversia")),
        "parti": assistiti + controparti,
        "imputati": assistiti,
        "parti_offese": controparti,
        "ricorrenti": assistiti,
        "resistenti": controparti,
        "controinteressati": [
            _party_name(_normalizza_parte(row))
            for row in _coerce_list(fasc_raw.get("controinteressati"))
            if _party_name(_normalizza_parte(row))
        ],
        "difensori": [
            _safe(value)
            for value in _coerce_list(payload.get("difensori") or fasc_raw.get("difensori"))
            if _safe(value)
        ],
        "codice_ufficio": ufficio_codice,
        "nome_ufficio": ufficio,
        "codice_commissione": ufficio_codice,
        "nome_commissione": ufficio,
        "eventi": eventi,
        "udienze": udienze,
        "comunicazioni": comunicazioni,
        "istanze": istanze,
        "depositi_telematici": depositi,
        "hash_snapshot": _hash_snapshot(payload),
        "imported_at": _now_iso(),
    }

    selection = {
        "external_id": external_id,
        "id_fascicolo": _safe(_first(fasc_raw, "id_fascicolo", "idFascicolo")),
        "numero": numero,
        "anno": anno,
        "ufficio_codice": ufficio_codice,
        "ufficio_nome": ufficio,
        "procedimento": registro,
        "sub_procedimento": _safe(_first(fasc_raw, "sub_procedimento", "subProcedimento")),
        "sezione": payload_structured["sezione"],
        "stato": payload_structured["stato"],
        "oggetto": oggetto,
        "parti": assistiti,
        "controparti": controparti,
        "ultima_attivita": data_udienza or data_iscrizione,
        "manual_mode": False,
        "payload": payload_structured,
    }
    return {
        "selection": selection,
        "documenti": documenti,
        "raw_payload": payload,
        "structured": payload_structured,
    }


__all__ = ["normalize_authorized_portale_payload"]
