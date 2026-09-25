"""Depositi PDP di un fascicolo: preparazione, controlli, scheda per il portale, ricevute, stati.

L'invio resta un gesto dell'avvocato nel PDP (provvedimento DGSIA
11/07/2023 art. 4 e 7): IUSENTRA compone il deposito, lo controlla prima,
prepara la scheda con i dati da inserire nel portale nello stesso ordine
delle sue maschere, poi registra ricevuta di deposito ed esito. Il deposito
è eseguito al rilascio della ricevuta di accettazione ed è tempestivo entro
le ore 24 del giorno di scadenza (art. 87 co. 6-bis D.Lgs. 150/2022).
"""

from __future__ import annotations

from typing import Any

from flask import current_app, g

from pct.fascicoli import TipoDocumento
from pct.penale_pdp import calendario, catalogo, stati
from pct.penale_pdp.controlli import Richiesta, avviso_indagini_nei_titoli, controlla
from pct.penale_pdp.controlli_file import FileDeposito
from pct.penale_pdp.regole_atti import etichetta_menu
from pct.penale_pdp.sede import sede_pdp
from pct.penale_pdp.ricevute import confronta_ricevuta, leggi_ricevuta, testo_pdf
from web.services import penale_pdp_contesto as contesto

RUOLI_FILE = ("principale", "contestuale", "abilitante", "allegato")


def _attore() -> str:
    utente = g.get("utente_corrente")
    return str(getattr(utente, "username", "") or getattr(utente, "nome", "") or "")


def _leggi(fid: str, documento_id: str) -> tuple[str, bytes]:
    from web.services.fascicolo_documento_ocr import leggi_documento

    return leggi_documento(current_app.extensions["core_runtime"]["get_fascicoli"](), fid, documento_id)


def _registro_label(registri: list[dict[str, Any]], ufficio: str) -> str:
    registro = next((r for r in registri if r["office_code"] == ufficio), None)
    if not registro:
        return ""
    return f"{ufficio.split('-')[0]}: {registro['register_type']}{registro['register_year']}/{registro['register_number']}"


TIPO_LEGALE = {"P02": "Fiducia"}  # maschera di nomina del PDP: «Tipo Legale» (FIDUCIA)


def _sede(nome: str) -> dict[str, str]:
    try:
        from pct.uffici_giudiziari import get_gestore

        return sede_pdp(nome, get_gestore().carica())
    except Exception:
        current_app.logger.warning("Distretto PDP non ricavato per %s", nome, exc_info=True)
        return {"distretto": "", "circondario": ""}


def scheda_portale(fid: str, deposito: dict[str, Any]) -> dict[str, Any]:
    """I dati da inserire nel PDP, nell'ordine delle sue maschere (verificate sul portale 6.11.10)."""
    fascicolo = contesto.fascicolo_penale(fid)
    caso = contesto.caso(fid)
    registri = contesto.archivio().registri(caso["id"])
    registro = next((r for r in registri if r["office_code"] == deposito["office_code"]), None)
    voce = catalogo.voce(deposito["act_name"])
    principale = bool(deposito["is_main_act"])
    percorso = (f"Depositi → {etichetta_menu(deposito['act_name']) or (voce.nome if voce else '')}" if principale
                else "Consultazioni → Procedimenti Autorizzati → seleziona il procedimento → «Deposita Atto Successivo»")
    sede_nome = (registro or {}).get("office_name") or fascicolo.tribunale or ""
    sede = _sede(sede_nome)
    sezioni = [
        {"titolo": "Dove", "voci": [{"etichetta": "Percorso nel PDP", "valore": percorso}]},
        {"titolo": "Ufficio destinazione", "voci": [
            {"etichetta": "Tipo ufficio", "valore": catalogo.etichetta_ufficio(deposito["office_code"])},
            {"etichetta": "Distretto", "valore": sede["distretto"] or "da scegliere sul PDP"},
            {"etichetta": "Circondario/Circolo", "valore": sede["circondario"] or "da scegliere sul PDP"},
            {"etichetta": "Sede/Ufficio", "valore": sede_nome},
        ]},
    ]
    if principale and registro:
        sezioni.append({"titolo": "Identificazione procedimento", "voci": [
            {"etichetta": "Ufficio registro", "valore": catalogo.etichetta_ufficio(registro["office_code"])},
            {"etichetta": "Numero", "valore": registro["register_number"]},
            {"etichetta": "Anno", "valore": registro["register_year"]},
            {"etichetta": "Registro", "valore": {"N": "Noti", "I": "Ignoti"}.get(registro["register_type"], registro["register_type"])},
            {"etichetta": "Sede ufficio", "valore": registro.get("office_name") or sede_nome},
            {"etichetta": "Magistrato", "valore": registro["magistrate"] or "facoltativo"},
        ]})
    sezioni.append({"titolo": "Atto", "voci": [
        {"etichetta": "Tipo atto", "valore": voce.nome if voce else deposito["act_name"]},
        *[{"etichetta": str(k).replace("_", " ").capitalize(), "valore": str(v)} for k, v in (deposito["data_json"] or {}).items() if v not in ("", None)],
    ]})
    tipo_legale = [{"etichetta": "Tipo legale", "valore": TIPO_LEGALE[deposito["act_name"]]}] if deposito["act_name"] in TIPO_LEGALE else []
    sezioni.append({"titolo": "Soggetti rappresentati", "voci": [
        *[{"etichetta": f"Ruolo: {s.get('ruoloEtichetta') or s.get('ruolo', '')}", "valore": s.get("nome", "")} for s in deposito["subjects_json"] or []],
        *tipo_legale,
    ]})
    sezioni.append({"titolo": "Documenti da caricare", "voci": [
        {"etichetta": f"{f['ruolo'].capitalize()}" + (f" · {f['oggetto']}" if f.get("oggetto") else ""),
         "valore": f["nome"], "nota": f"SHA-256 {f['sha256'][:16]}…"} for f in deposito["files_json"] or []
    ]})
    return {"sezioni": sezioni, "canale": calendario.canale(deposito["office_code"], atto=deposito["act_name"])}


def prepara(fid: str, dati: dict[str, Any], deposito_id: str = "") -> dict[str, Any]:
    """Compone e controlla il deposito; lo salva come bozza o «pronto per il PDP»."""
    fascicolo = contesto.fascicolo_penale(fid)
    caso = contesto.caso(fid)
    arch = contesto.archivio()
    codice = str(dati.get("atto") or "").upper()
    voce = catalogo.voce(codice)
    if voce is None:
        raise ValueError("Scegli l'atto dal catalogo del PDP.")
    ufficio = str(dati.get("ufficio") or contesto.ufficio_corrente(caso, arch.registri(caso["id"]))).upper()
    per_id = {s["id"]: s for s in arch.soggetti(caso["id"])}
    soggetti = [contesto.soggetto_json(per_id[i]) for i in dati.get("soggetti") or [] if i in per_id]
    file: list[FileDeposito] = []
    for voce_file in dati.get("file") or []:
        ruolo = str(voce_file.get("ruolo") or "")
        if ruolo not in RUOLI_FILE or not voce_file.get("documentoId"):
            continue
        nome, contenuto = _leggi(fid, str(voce_file["documentoId"]))
        file.append(FileDeposito(ruolo=ruolo, nome=nome, dati=contenuto, oggetto=str(voce_file.get("oggetto") or ""),
                                 documento_id=str(voce_file["documentoId"]), tipo_atto=str(voce_file.get("tipoAtto") or "").upper()))
    avviso = dati["avvisoIndagini"] if "avvisoIndagini" in dati else avviso_indagini_nei_titoli(d.nome for d in fascicolo.documenti)
    esito = controlla(Richiesta(
        atto=codice, ufficio=ufficio, soggetti=[{"nome": s["nome"], "ruolo": s["ruolo"]} for s in soggetti], file=file,
        dati=dict(dati.get("dati") or {}), procedimento_autorizzato=bool(caso.get("authorized")),
        avocato_pg=bool(caso.get("avocato_pg")), avviso_indagini_presente=bool(avviso),
        procura_speciale_dichiarata=bool(dati.get("procuraSpeciale")), cf_avvocato=caso.get("defense_counsel_cf") or contesto.cf_avvocato(),
        uffici_registro=tuple(r["office_code"] for r in arch.registri(caso["id"])),
    ))
    campi = {
        "act_name": codice, "is_main_act": int(voce.principale), "office_code": ufficio,
        "office_name": catalogo.etichetta_ufficio(ufficio), "register_label": _registro_label(arch.registri(caso["id"]), ufficio),
        "subjects_json": soggetti, "files_json": esito["file"], "data_json": dict(dati.get("dati") or {}),
        "checks_json": {k: esito[k] for k in ("pronto", "errori", "avvisi", "esiti")} | {"procuraSpeciale": bool(dati.get("procuraSpeciale"))},
        "status": "PRONTO" if esito["pronto"] else "BOZZA",
    }
    if deposito_id:
        attuale = arch.deposito(caso["id"], deposito_id)
        if attuale["status"] not in {"BOZZA", "PRONTO"}:
            raise ValueError("Il deposito è già stato inviato: non si modifica, se ne prepara uno nuovo.")
        deposito = arch.aggiorna_deposito(caso["id"], deposito_id, **campi)
    else:
        deposito = arch.crea_deposito(caso["id"], creato_da=_attore(), **campi)
    return {"deposito": contesto.deposito_json(deposito), "scheda": scheda_portale(fid, deposito)}


def dettaglio(fid: str, deposito_id: str) -> dict[str, Any]:
    caso = contesto.caso(fid)
    deposito = contesto.archivio().deposito(caso["id"], deposito_id)
    return {"deposito": contesto.deposito_json(deposito), "scheda": scheda_portale(fid, deposito)}


def _salva_nel_fascicolo(fid: str, nome: str, contenuto: bytes, nota: str) -> str:
    gestore = current_app.extensions["core_runtime"]["get_fascicoli"]()
    documento = gestore.aggiungi_documento(fid, nome, TipoDocumento.DEPOSITO_PCT, contenuto, note=nota,
                                           caricato_da=_attore(), fonte_documento="PORTALE_TELEMATICO", nome_originale=nome)
    try:
        from web.services.registro_letture_runtime import documento_aggiornato

        documento_aggiornato(fid, documento)
    except Exception:
        current_app.logger.warning("Registro letture non aggiornato per la ricevuta PDP", exc_info=True)
    return documento.id


def _verifica(caso: dict[str, Any], deposito: dict[str, Any], letti: dict[str, Any]) -> dict[str, Any]:
    voce = catalogo.voce(deposito["act_name"])
    return confronta_ricevuta(
        letti, identificativo=deposito["sending_id"] or "", cf_avvocato=caso.get("defense_counsel_cf") or contesto.cf_avvocato(),
        ufficio_codice=deposito["office_code"] or "", registri=contesto.archivio().registri(caso["id"]),
        nome_atto=voce.nome if voce else "", soggetti=deposito["subjects_json"] or [], file_preparati=deposito["files_json"] or [],
    )


def registra_ricevuta(fid: str, deposito_id: str, *, contenuto: bytes = b"", nome: str = "", manuale: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ricevuta di deposito o di esito: legge i dati, li confronta con il deposito preparato, aggiorna lo stato."""
    caso = contesto.caso(fid)
    arch = contesto.archivio()
    deposito = arch.deposito(caso["id"], deposito_id)
    letti = leggi_ricevuta(testo_pdf(contenuto)) if contenuto else {"tipo": "deposito", "mancanti": []}
    manuale = manuale or {}
    letto = str(letti.get("identificativo") or "")
    scritto = str(manuale.get("identificativo") or "").strip()
    correzione = bool(scritto) and scritto != deposito["sending_id"]
    if letto and deposito["sending_id"] and letto != deposito["sending_id"] and not correzione:
        raise ValueError(f"Questa ricevuta riguarda il deposito {letto}, non il {deposito['sending_id']}: caricala sul deposito giusto.")
    identificativo = str(letto or scritto or deposito["sending_id"] or "").strip()
    stato = stati.normalizza(manuale.get("stato") or "") or letti.get("stato") or ("INVIATO" if identificativo else deposito["status"])
    if not identificativo:
        raise ValueError("Non trovo l'identificativo AAAA/NNNNNNN: scrivilo come lo vedi sulla ricevuta.")
    doppione = arch.per_identificativo(caso["id"], identificativo)
    if doppione and doppione["id"] != deposito_id:
        raise ValueError(f"L'identificativo {identificativo} è già registrato su un altro deposito.")
    campi: dict[str, Any] = {"sending_id": identificativo, "status": stato,
                             "sent_at": str(manuale.get("dataInvio") or letti.get("dataInvio") or deposito["sent_at"] or "")}
    if letti.get("motivazione") or manuale.get("motivazione"):
        campi["rejection_reason"] = str(manuale.get("motivazione") or letti["motivazione"])
    if contenuto:
        e_esito = letti.get("tipo") == "esito"
        documento_id = _salva_nel_fascicolo(fid, nome or f"{'esito' if e_esito else 'ricevuta'}-pdp-{identificativo.replace('/', '-')}.pdf",
                                            contenuto, f"{'Esito' if e_esito else 'Ricevuta'} PDP {identificativo}")
        campi["outcome_document_id" if e_esito else "receipt_document_id"] = documento_id
        if not e_esito:
            campi["receipt_check_json"] = _verifica(caso, {**deposito, "sending_id": identificativo}, letti)
    aggiornato = arch.aggiorna_deposito(caso["id"], deposito_id, **campi)
    dopo_cambio_stato(fid, aggiornato)
    return {"deposito": contesto.deposito_json(aggiornato), "letti": letti}


ATTI_CHE_AUTORIZZANO = frozenset({"P02", "P49", "P10", "P26", "P30", "P27", "PBT"})


def dopo_cambio_stato(fid: str, deposito: dict[str, Any]) -> None:
    """Nomina o costituzione accolta: il PDP rende autorizzato il procedimento (manuale, «Procedimenti autorizzati»)."""
    if deposito["status"] == "ACCOLTO" and deposito["act_name"] in ATTI_CHE_AUTORIZZANO:
        contesto.aggiorna_procedimento(fid, {"autorizzato": True, "fonte": f"Deposito {deposito['sending_id'] or ''} accolto".strip()})


def aggiorna_stato(fid: str, deposito_id: str, dati: dict[str, Any]) -> dict[str, Any]:
    caso = contesto.caso(fid)
    stato = stati.normalizza(str(dati.get("stato") or ""))
    if stato not in {c for c, _, _ in stati.STATI_UFFICIALI}:
        raise ValueError("Stato non previsto dal PDP.")
    campi: dict[str, Any] = {"status": stato}
    if dati.get("motivazione"):
        campi["rejection_reason"] = str(dati["motivazione"])[:1000]
    if dati.get("dataArrivo"):
        campi["arrived_at"] = str(dati["dataArrivo"])
    aggiornato = contesto.archivio().aggiorna_deposito(caso["id"], deposito_id, **campi)
    dopo_cambio_stato(fid, aggiornato)
    return {"deposito": contesto.deposito_json(aggiornato)}


def elimina(fid: str, deposito_id: str) -> None:
    caso = contesto.caso(fid)
    contesto.archivio().elimina_deposito(caso["id"], deposito_id)


__all__ = ["aggiorna_stato", "dettaglio", "dopo_cambio_stato", "elimina", "prepara", "registra_ricevuta", "scheda_portale"]
