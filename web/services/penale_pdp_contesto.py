"""Il procedimento penale telematico di un fascicolo: caso PDP, registri, soggetti, quadro.

Ogni fascicolo penale ha un caso nel workflow PDP (``criminal_cases``). Qui
lo si crea dai dati del fascicolo, si tengono registri e soggetti
rappresentati e si costruisce il quadro che la sezione «Deposito penale
(PDP)» mostra all'avvocato. Base: manuale PDP e provvedimento DGSIA
11/07/2023 (art. 6: il procedimento è autorizzato quando il codice fiscale
del difensore è annotato nel registro).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from flask import current_app, g

from pct.fascicoli import TipoFascicolo
from pct.penale_pdp import calendario, catalogo, stati
from pct.penale_pdp.archivio import ArchivioPenale, iniziali
from pct.penale_pdp.controlli import avviso_indagini_nei_titoli

LINK_PDP = "https://servizipst.giustizia.it/PST/PAVVP/"
LINK_AVVISI = "https://servizipst.giustizia.it/PST/AvvisiPenale"
_UFFICI_PER_NOME = (
    (r"procura\s+generale", "PGCAP-U"),
    (r"procura.*(giudice\s+di\s+pace|gdp)", "PM-G"),
    (r"procura", "PM-U"),
    (r"riesame", "RIE"),
    (r"\bgip\b|\bgup\b|indagini\s+preliminari|udienza\s+preliminare", "GIP-U"),
    (r"assise\s+d.\s*appello", "CASAP-U"),
    (r"assise", "CAS-U"),
    (r"corte\s+d.?\s*appello|corte\s+di\s+appello", "CAP-U"),
    (r"giudice\s+di\s+pace", "GP-G"),
    (r"tribunale", "DIB-U"),
)
_RUOLO_DA_QUALIFICA = (
    (r"indagat|imputat|responsabile\s+amm", "IND"),
    (r"parte\s+civile", "CIV"),
    (r"persona\s+offesa|offes|querelant|denunciant", "OFF"),
    (r"responsabile\s+civile", "RES"),
    (r"civilmente\s+obbligat", "COB"),
)


def _runtime(nome: str) -> Any:
    return current_app.extensions["core_runtime"][nome]()


def repository():
    return _runtime("get_pdp_penale")


def archivio() -> ArchivioPenale:
    return ArchivioPenale(repository().conn)


def ufficio_da_nome(nome: str) -> str:
    testo = str(nome or "").casefold()
    return next((codice for schema, codice in _UFFICI_PER_NOME if re.search(schema, testo)), "")


def cf_avvocato() -> str:
    try:
        cfg = _runtime("get_config_studio").config
        return str(getattr(cfg.firma, "cf_avvocato", "") or getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
    except Exception:
        return ""


def fascicolo_penale(fid: str):
    fascicolo = _runtime("get_fascicoli").get(fid)
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    if fascicolo.tipo != TipoFascicolo.PENALE:
        raise ValueError("Il deposito penale è disponibile solo per i fascicoli penali.")
    return fascicolo


def _avvocato(fascicolo: Any) -> str:
    utente = g.get("utente_corrente")
    return str(fascicolo.avvocato_referente or fascicolo.avvocato_dominus
               or getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or "Avvocato").strip()


def caso(fid: str, *, crea: bool = True) -> dict[str, Any] | None:
    """Il caso PDP del fascicolo; alla prima apertura nasce dai dati del fascicolo."""
    fascicolo = fascicolo_penale(fid)
    repo = repository()
    casi = [c for c in repo.list_cases_for_practice(fid) if not c.get("archived")]
    if casi or not crea:
        return casi[0] if casi else None
    numero = str(fascicolo.numero_rg or "").strip()
    anno = int(fascicolo.anno_rg or datetime.now().year)
    ufficio = ufficio_da_nome(fascicolo.tribunale)
    nuovo = repo.create_case(
        practice_id=fid,
        office_name=str(fascicolo.tribunale or "").strip() or "Ufficio da indicare",
        # Il vincolo di unicità del workflow vale per ufficio, registro, numero, anno e difensore:
        # senza numero il caso resta legato al fascicolo finché il registro non è noto.
        register_number=numero or f"da-assegnare-{fid}",
        register_year=anno,
        assisted_party_name=str(fascicolo.nome_cliente or "").strip() or "Assistito da indicare",
        defense_counsel_name=_avvocato(fascicolo),
        defense_counsel_cf=cf_avvocato(),
        register_type=str(fascicolo.tipo_procedimento or "").strip(),
        judge_name=str(fascicolo.giudice or "").strip(),
        pdp_office_code=ufficio,
    )
    arch = archivio()
    if numero and ufficio:
        arch.salva_registro(nuovo["id"], office_code=ufficio, office_name=str(fascicolo.tribunale or ""),
                            register_type="N", register_number=numero, register_year=str(anno),
                            magistrate=str(fascicolo.giudice or ""), corrente=True, source="fascicolo")
    qualifica = str(getattr(fascicolo, "qualifica_giudiziale_titolare", "") or "").casefold()
    ruolo = next((codice for schema, codice in _RUOLO_DA_QUALIFICA if re.search(schema, qualifica)), "")
    if ruolo and fascicolo.nome_cliente:
        arch.salva_soggetto(nuovo["id"], full_name=fascicolo.nome_cliente, role_code=ruolo, source="fascicolo")
    return nuovo


def ufficio_corrente(caso_pdp: dict[str, Any], registri: list[dict[str, Any]]) -> str:
    corrente = next((r for r in registri if r.get("is_current")), registri[0] if registri else None)
    return (corrente or {}).get("office_code") or caso_pdp.get("pdp_office_code") or ""


def registro_json(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r["id"], "ufficio": r["office_code"], "ufficioEtichetta": catalogo.etichetta_ufficio(r["office_code"]),
            "ufficioNome": r["office_name"], "registro": r["register_type"], "numero": r["register_number"],
            "anno": r["register_year"], "magistrato": r["magistrate"], "corrente": bool(r["is_current"]),
            "protocollo": f"{r['office_code'].split('-')[0]}: {r['register_type']}{r['register_year']}/{r['register_number']}"}


def soggetto_json(s: dict[str, Any]) -> dict[str, Any]:
    return {"id": s["id"], "nome": s["full_name"], "iniziali": iniziali(s["full_name"]), "ruolo": s["role_code"],
            "ruoloEtichetta": catalogo.etichetta_ruolo(s["role_code"]), "codiceFiscale": s["tax_code"],
            "natura": s["subject_kind"], "fonte": s["source"]}


def deposito_json(d: dict[str, Any]) -> dict[str, Any]:
    voce = catalogo.voce(d["act_name"])
    return {
        "id": d["id"], "atto": d["act_name"], "attoNome": voce.nome if voce else d["act_name"],
        "principale": bool(d["is_main_act"]), "ufficio": d["office_code"],
        "ufficioEtichetta": catalogo.etichetta_ufficio(d["office_code"]) if d["office_code"] else d["office_name"],
        "registro": d["register_label"], "soggetti": d["subjects_json"] or [], "file": d["files_json"] or [],
        "dati": d["data_json"] or {}, "controlli": d["checks_json"] or {}, "stato": d["status"],
        "statoEtichetta": stati.etichetta(d["status"]), "statoTono": stati.TONI.get(d["status"], "neutral"),
        "definitivo": stati.e_definitivo(d["status"]), "identificativo": d["sending_id"], "dataInvio": d["sent_at"],
        "dataArrivo": d["arrived_at"], "motivazione": d["rejection_reason"], "ricevutaId": d["receipt_document_id"],
        "esitoId": d["outcome_document_id"], "verificaRicevuta": d["receipt_check_json"] or {}, "fonte": d["source"],
        "creatoIl": d["created_at"], "aggiornatoIl": d["updated_at"],
    }


def documenti_fascicolo(fascicolo: Any) -> list[dict[str, Any]]:
    elenco = []
    for doc in getattr(fascicolo, "documenti", []) or []:
        if getattr(doc, "eliminato_il", ""):
            continue
        elenco.append({"id": doc.id, "nome": doc.nome, "dimensione": int(doc.dimensione_bytes or 0),
                       "firmato": bool(doc.firmato_digitalmente), "data": doc.data_documento or str(doc.data_caricamento or "")[:10]})
    return sorted(elenco, key=lambda d: d["data"], reverse=True)


def quadro(fid: str) -> dict[str, Any]:
    fascicolo = fascicolo_penale(fid)
    caso_pdp = caso(fid)
    arch = archivio()
    registri = arch.registri(caso_pdp["id"])
    soggetti = arch.soggetti(caso_pdp["id"])
    ufficio = ufficio_corrente(caso_pdp, registri)
    documenti = documenti_fascicolo(fascicolo)
    return {
        "ok": True,
        "fascicolo": {"id": fid, "titolo": fascicolo.titolo,
                      "tribunale": fascicolo.tribunale, "rg": f"{fascicolo.numero_rg or ''}/{fascicolo.anno_rg or ''}".strip("/")},
        "procedimento": {
            "id": caso_pdp["id"], "autorizzato": bool(caso_pdp.get("authorized")),
            "fonteAutorizzazione": caso_pdp.get("authorized_source") or "", "autorizzatoIl": caso_pdp.get("authorized_at") or "",
            "avocatoPg": bool(caso_pdp.get("avocato_pg")), "ufficio": ufficio,
            "ufficioEtichetta": catalogo.etichetta_ufficio(ufficio) if ufficio else "",
            "avvocato": caso_pdp.get("defense_counsel_name") or "", "cfAvvocato": caso_pdp.get("defense_counsel_cf") or cf_avvocato(),
        },
        "canale": calendario.canale(ufficio) if ufficio else None,
        "registri": [registro_json(r) for r in registri],
        "soggetti": [soggetto_json(s) for s in soggetti],
        "depositi": [deposito_json(d) for d in arch.depositi(caso_pdp["id"])],
        "udienze": [{"id": u["id"], "quando": u["starts_at"], "ufficio": u["office_type"], "aula": u["room"],
                     "luogo": u["place"], "causale": u["reason"], "inAgenda": bool(u["agenda_id"])} for u in arch.udienze(caso_pdp["id"])],
        "documenti": documenti,
        "avvisoIndagini": avviso_indagini_nei_titoli(d["nome"] for d in documenti),
        "uffici": catalogo.uffici(), "ruoli": catalogo.ruoli(), "fasi": catalogo.fasi(), "registriTipi": catalogo.registri(),
        "stati": [{"codice": c, "etichetta": e, "descrizione": d} for c, e, d in stati.STATI_LOCALI + stati.STATI_UFFICIALI],
        "fonte": catalogo.fonte(),
        "link": {"pdp": LINK_PDP, "avvisi": LINK_AVVISI, "accessoAtti": f"/fascicoli/{fid}/penale/pdp"},
    }


def aggiorna_procedimento(fid: str, dati: dict[str, Any]) -> None:
    caso_pdp = caso(fid)
    modifiche: dict[str, Any] = {}
    if "autorizzato" in dati:
        autorizzato = bool(dati.get("autorizzato"))
        modifiche.update({"authorized": int(autorizzato),
                          "authorized_source": str(dati.get("fonte") or "Confermato dall'avvocato") if autorizzato else "",
                          "authorized_at": datetime.now().isoformat(timespec="seconds") if autorizzato else ""})
    if "avocatoPg" in dati:
        modifiche["avocato_pg"] = int(bool(dati.get("avocatoPg")))
    if dati.get("ufficio"):
        codice = str(dati["ufficio"]).upper()
        if codice not in {u["codice"] for u in catalogo.uffici()}:
            raise ValueError("Tipo ufficio non previsto dal PDP.")
        modifiche["pdp_office_code"] = codice
    if modifiche:
        repository().update_case(caso_pdp["id"], **modifiche)


def salva_registro(fid: str, dati: dict[str, Any]) -> dict[str, Any]:
    caso_pdp = caso(fid)
    ufficio = str(dati.get("ufficio") or "").upper()
    if ufficio not in {u["codice"] for u in catalogo.uffici()}:
        raise ValueError("Scegli l'ufficio fra quelli del PDP.")
    numero = re.sub(r"\D", "", str(dati.get("numero") or ""))
    anno = re.sub(r"\D", "", str(dati.get("anno") or ""))
    if not numero or len(anno) != 4:
        raise ValueError("Indica numero e anno del registro (es. 1096/2023).")
    registro = archivio().salva_registro(
        caso_pdp["id"], office_code=ufficio, office_name=str(dati.get("ufficioNome") or ""),
        register_type=str(dati.get("registro") or "N").upper()[:1], register_number=str(int(numero)), register_year=anno,
        magistrate=str(dati.get("magistrato") or ""), corrente=bool(dati.get("corrente")),
    )
    return registro_json(registro)


def salva_soggetto(fid: str, dati: dict[str, Any]) -> dict[str, Any]:
    caso_pdp = caso(fid)
    ruolo = str(dati.get("ruolo") or "").upper()
    if ruolo not in {r["codice"] for r in catalogo.ruoli()}:
        raise ValueError("Scegli il ruolo del soggetto fra quelli del PDP.")
    soggetto = archivio().salva_soggetto(
        caso_pdp["id"], full_name=str(dati.get("nome") or ""), role_code=ruolo,
        tax_code=str(dati.get("codiceFiscale") or ""), subject_kind="giuridica" if dati.get("natura") == "giuridica" else "fisica",
    )
    return soggetto_json(soggetto)


__all__ = [
    "LINK_AVVISI", "LINK_PDP", "aggiorna_procedimento", "archivio", "caso", "cf_avvocato", "deposito_json",
    "documenti_fascicolo", "fascicolo_penale", "quadro", "registro_json", "repository", "salva_registro",
    "salva_soggetto", "soggetto_json", "ufficio_corrente", "ufficio_da_nome",
]
