"""Allineamento SIGP verso il fascicolo IUSENTRA ordinario."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from flask import g

from pct.fascicoli import TipoAttivita, TipoDocumento, TipoFascicolo
from pct.pst_servizi_catalogo import SERVIZIO_PST_DOCUMENTI_FASCICOLO
from web.helpers import get_fascicoli


def sincronizza_sigp_con_fascicolo(
    *,
    snapshot: dict,
    documenti: list[dict],
    storage_root: Path,
    registrato_da: str = "IUSENTRA",
) -> dict:
    """Porta catalogo, eventi e file SIGP nel fascicolo gestionale visibile."""
    snapshot = dict(snapshot or {})
    snapshot["documenti"] = list(documenti or [])
    local_id = _ensure_fascicolo_gestionale(snapshot)
    fascicoli = get_fascicoli()
    depositi_count = 0
    for id_deposito, gruppo in _depositi_per_documenti(documenti).items():
        if not id_deposito:
            continue
        portale_docs = _documenti_portale_payload(gruppo)
        primo = gruppo[0] if gruppo else {}
        fascicoli.sincronizza_deposito_portale(
            local_id,
            fonte="PST/SIGP",
            id_deposito_esterno=id_deposito,
            tipo_atto=str(primo.get("tipo_atto") or primo.get("classificazione") or "Documenti fascicolo"),
            data_deposito=_data_iso(primo.get("data_deposito") or primo.get("data_documento")),
            mittente=str(primo.get("depositante") or ""),
            documenti_portale=portale_docs,
            registrato_da=registrato_da or _utente_corrente_label(),
            note="Catalogo SIGP acquisito da pagina unica.",
            nome_atto_principale=str(primo.get("nome_file") or ""),
            stato="IMPORTATO_DA_PORTALE",
            servizio_portale=SERVIZIO_PST_DOCUMENTI_FASCICOLO,
        )
        depositi_count += 1
    attivita_count = _sync_eventi_e_udienze(fascicoli, local_id, snapshot)
    file_importati = _importa_file_scaricati(fascicoli, local_id, documenti, storage_root)
    fascicoli.aggiorna(
        local_id,
        last_sync_at=datetime.now().isoformat(),
        sync_status="SINCRONIZZATO",
        document_sync_enabled=True,
        events_sync_enabled=True,
    )
    return {
        "fascicolo_locale_id": local_id,
        "fascicolo_url": f"/fascicoli/{local_id}#sezione-documenti-fascicolo",
        "documenti_catalogati": len(documenti),
        "depositi": depositi_count,
        "attivita_importate": attivita_count,
        "file_importati": file_importati,
    }


def _utente_corrente_label() -> str:
    utente = g.get("utente_corrente") if hasattr(g, "get") else None
    return str(getattr(utente, "username", "") or "IUSENTRA")


def _data_iso(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except ValueError:
            continue
    if "/" in text:
        parts = text.split(" ", 1)[0].split("/")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
    return text[:10]


def _nome_parte(parte: dict) -> str:
    return " ".join(
        part
        for part in [
            str(parte.get("denominazione") or "").strip(),
            str(parte.get("nome") or "").strip(),
            str(parte.get("cognome") or "").strip(),
        ]
        if part
    ).strip()


def _parti_principali(snapshot: dict) -> tuple[str, str]:
    parti = list(snapshot.get("parti") or [])
    assistito = ""
    controparte = ""
    for parte in parti:
        ruolo = str(parte.get("ruolo") or "").casefold()
        nome = _nome_parte(parte)
        if not nome:
            continue
        if not assistito and any(key in ruolo for key in ("attore", "ricorrente", "istante")):
            assistito = nome
        elif not controparte and any(key in ruolo for key in ("convenuto", "resistente", "controparte")):
            controparte = nome
    if not assistito and parti:
        assistito = _nome_parte(parti[0])
    if not controparte and len(parti) > 1:
        controparte = _nome_parte(parti[1])
    return assistito, controparte


def _ensure_fascicolo_gestionale(snapshot: dict) -> str:
    fascicolo_sigp = snapshot.get("fascicolo") or {}
    fascicoli = get_fascicoli()
    local_id = str(fascicolo_sigp.get("fascicolo_locale_id") or "").strip()
    if local_id and fascicoli.get(local_id):
        return local_id

    numero_rg = str(fascicolo_sigp.get("numero_rg") or "").strip()
    anno_rg = str(fascicolo_sigp.get("anno_rg") or "").strip()
    rg = "/".join(part for part in (numero_rg, anno_rg) if part)
    assistito, controparte = _parti_principali(snapshot)
    oggetto = str(fascicolo_sigp.get("oggetto") or "").strip()
    titolo_parti = " / ".join(part for part in (assistito, controparte) if part) or oggetto or "Fascicolo SIGP"
    titolo = f"RG {rg} - {titolo_parti}" if rg else titolo_parti
    try:
        anno_int = int(anno_rg or 0)
    except ValueError:
        anno_int = 0
    created = fascicoli.nuovo(
        titolo=titolo,
        tipo=TipoFascicolo.CIVILE,
        nome_cliente=assistito,
        controparte=controparte,
        tribunale=str(fascicolo_sigp.get("ufficio") or ""),
        numero_rg=rg or numero_rg,
        anno_rg=anno_int,
        giudice=str(fascicolo_sigp.get("giudice") or ""),
        sezione=str(fascicolo_sigp.get("sezione") or ""),
        oggetto=oggetto,
        data_apertura=_data_iso(fascicolo_sigp.get("data_iscrizione")) or date.today().isoformat(),
        data_prima_udienza=_data_iso(fascicolo_sigp.get("data_prima_comparizione")),
        data_prossima_udienza=_data_iso(fascicolo_sigp.get("data_ultima_udienza")),
        source="PST/SIGP",
        source_external_id=str(fascicolo_sigp.get("sigp_uid") or ""),
        last_sync_at=datetime.now().isoformat(),
        sync_status="SINCRONIZZATO",
        document_sync_enabled=True,
        events_sync_enabled=True,
    )
    return created.id


def _documenti_portale_payload(documenti: list[dict]) -> list[dict]:
    rows = []
    for documento in documenti:
        rows.append(
            {
                "id_documento": str(documento.get("documento_uid") or documento.get("id_documento") or "").strip(),
                "id_cat": str(documento.get("id_cat") or "").strip(),
                "id_repeatto": str(documento.get("id_repeatto") or "").strip(),
                "msg_id": str(documento.get("msg_id") or "").strip(),
                "nome": str(documento.get("nome_file") or documento.get("nome_originario") or "").strip(),
                "tipo": str(documento.get("classificazione") or documento.get("tipo_atto") or "").strip(),
                "data_deposito": _data_iso(documento.get("data_deposito") or documento.get("data_documento")),
                "mittente": str(documento.get("depositante") or "").strip(),
                "dimensione_bytes": int(documento.get("dimensione_bytes") or 0),
                "disponibile": bool(documento.get("scaricabile", True)),
                "id_deposito": str(documento.get("id_deposito") or documento.get("documento_uid") or "").strip(),
                "tipo_atto": str(documento.get("tipo_atto") or documento.get("classificazione") or "").strip(),
            }
        )
    return rows


def _depositi_per_documenti(documenti: list[dict]) -> dict[str, list[dict]]:
    gruppi: dict[str, list[dict]] = {}
    for documento in documenti:
        key = str(documento.get("id_deposito") or "").strip()
        if not key:
            key = "__".join(
                part
                for part in [
                    _data_iso(documento.get("data_deposito") or documento.get("data_documento")),
                    str(documento.get("depositante") or "").strip(),
                    str(documento.get("tipo_atto") or documento.get("classificazione") or "").strip(),
                ]
                if part
            ) or str(documento.get("documento_uid") or documento.get("id") or "").strip()
        gruppi.setdefault(key, []).append(documento)
    return gruppi


def _sync_eventi_e_udienze(fascicoli, local_id: str, snapshot: dict) -> int:
    fascicolo = fascicoli.get(local_id)
    if not fascicolo:
        return 0
    existing = {
        (str(att.titolo or "").casefold(), str(att.data or ""), str(att.descrizione or "").casefold())
        for att in fascicolo.attivita
    }
    created = 0
    for evento in snapshot.get("eventi") or []:
        titolo = str(evento.get("tipo_evento") or "Evento da portale").strip()
        descrizione = str(evento.get("descrizione") or "").strip()
        data = _data_iso(evento.get("data_evento")) or date.today().isoformat()
        key = (titolo.casefold(), data, descrizione.casefold())
        if key in existing:
            continue
        tipo = TipoAttivita.ISCRIZIONE_A_RUOLO if "iscr" in (titolo + " " + descrizione).casefold() else TipoAttivita.DEPOSITO_ATTI
        fascicoli.aggiungi_attivita(local_id, tipo, data, titolo, descrizione=descrizione, note="Importato da SIGP/PST")
        existing.add(key)
        created += 1
    for udienza in snapshot.get("udienze") or []:
        titolo = str(udienza.get("tipo") or "Udienza da portale").strip()
        descrizione = str(udienza.get("descrizione") or "").strip()
        data = _data_iso(udienza.get("data_udienza")) or date.today().isoformat()
        key = (titolo.casefold(), data, descrizione.casefold())
        if key in existing:
            continue
        fascicoli.aggiungi_attivita(local_id, TipoAttivita.UDIENZA, data, titolo, descrizione=descrizione, note="Importata da SIGP/PST")
        existing.add(key)
        created += 1
    return created


def _tipo_documento_sigp(documento: dict) -> TipoDocumento:
    text = " ".join(str(documento.get(key) or "") for key in ("tipo_atto", "classificazione", "nome_file")).upper()
    if "SENTENZA" in text:
        return TipoDocumento.SENTENZA
    if "ORDINANZA" in text:
        return TipoDocumento.ORDINANZA
    if "DECRETO" in text:
        return TipoDocumento.DECRETO
    if "VERBALE" in text:
        return TipoDocumento.VERBALE
    if "RICORSO" in text:
        return TipoDocumento.RICORSO
    if "CITAZIONE" in text:
        return TipoDocumento.CITAZIONE
    if "COMUNICAZIONE" in text:
        return TipoDocumento.COMUNICAZIONE
    if "ALLEGAT" in text:
        return TipoDocumento.ALLEGATO
    return TipoDocumento.ATTO_GIUDIZIARIO


def _importa_file_scaricati(fascicoli, local_id: str, documenti: list[dict], storage_root: Path) -> int:
    fascicolo = fascicoli.get(local_id)
    if not fascicolo:
        return 0
    existing_ids = {
        str(getattr(doc, "id_documento_portale", "") or "").strip()
        for doc in fascicolo.documenti
        if str(getattr(doc, "id_documento_portale", "") or "").strip()
    }
    imported = 0
    for documento in documenti:
        path_rel = str(documento.get("path_locale") or "").strip()
        portal_id = str(documento.get("documento_uid") or "").strip()
        if not path_rel or (portal_id and portal_id in existing_ids):
            continue
        file_path = storage_root / path_rel
        if not file_path.exists() or not file_path.is_file():
            continue
        content = file_path.read_bytes()
        if not content:
            continue
        fascicoli.aggiungi_documento(
            local_id,
            nome_file=str(documento.get("nome_file") or file_path.name),
            tipo=_tipo_documento_sigp(documento),
            contenuto=content,
            note="Importato dal fascicolo SIGP con copia ministeriale scaricata tramite canale locale.",
            tags=[
                "Portale telematico",
                "SIGP",
                "Giudice di Pace",
                str(documento.get("classificazione") or documento.get("tipo_atto") or "").strip(),
            ],
            data_documento=_data_iso(documento.get("data_documento") or documento.get("data_deposito")),
            caricato_da="SIGP/PST",
            fonte_documento="PORTALE_TELEMATICO",
            nome_originale=str(documento.get("nome_originario") or documento.get("nome_file") or file_path.name),
            nome_portale=str(documento.get("nome_file") or ""),
            classificazione_portale=str(documento.get("classificazione") or ""),
            tipo_atto_portale=str(documento.get("tipo_atto") or ""),
            servizio_portale=SERVIZIO_PST_DOCUMENTI_FASCICOLO,
            mittente_portale=str(documento.get("depositante") or ""),
            data_deposito_portale=_data_iso(documento.get("data_deposito")),
            id_documento_portale=portal_id,
            id_repeatto_portale=str(documento.get("id_repeatto") or ""),
        )
        if portal_id:
            existing_ids.add(portal_id)
        imported += 1
    return imported
