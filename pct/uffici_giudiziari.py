"""
pct/uffici_giudiziari.py — Gestore uffici giudiziari con cache persistente.

Mantiene un registro aggiornato di tutti gli uffici giudiziari italiani:
  • 140+ Tribunali ordinari
  • 23  Corti d'Appello
  • 140+ Procure della Repubblica (generate dal registro tribunali)
  • 23  Procure Generali (una per Corte d'Appello)
  • 26  Tribunali per i Minorenni
  • 26  Tribunali di Sorveglianza
  • 29  Corti d'Assise
  • 100+ Uffici del Giudice di Pace (capoluoghi + principali)
  • 20+ TAR (Tribunali Amministrativi Regionali) + Consiglio di Stato
  • Corte Suprema di Cassazione
  • 21  CGT (Corti di Giustizia Tributaria di Secondo Grado, ex CTR)
  • 107 CPT (Corti di Giustizia Tributaria di Primo Grado, ex CTP)
  • 1   CGARS (Consiglio di Giustizia Amministrativa Regione Siciliana)

Fonti per l'aggiornamento (priorità decrescente):
  1. PCT_UFFICI_URL         — endpoint JSON personalizzato
  2. PST REST pubblico      — Portale Servizi Telematici (MinGiust)
  3. Bundle interno         — fallback sempre disponibile

Cache:
  • Percorso: PCT_UFFICI_DB (default /data/uffici/uffici_giudiziari.json)
  • TTL:       PCT_UFFICI_TTL_GIORNI (default 7)
"""
from __future__ import annotations

import json
import hashlib
import logging
import os
import unicodedata
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- configurazione

_CACHE_PATH   = os.getenv("PCT_UFFICI_DB",          "/data/uffici/uffici_giudiziari.json")
_TTL_GIORNI   = int(os.getenv("PCT_UFFICI_TTL_GIORNI", "7"))
_REMOTO_URL   = os.getenv("PCT_UFFICI_URL", "")          # Compat: deve risolvere l'endpoint PST ufficiale.
_PST_UFFICI   = "https://pst.giustizia.it/PST/resources/rest/ricercaUfficiGiudiziari"
_PST_TIMEOUT  = 12  # secondi
_RIFERIMENTI_MINISTERO_PATH = Path(__file__).resolve().parent / "data" / "uffici_ministero.json"
_RIFERIMENTI_MINISTERO_EXTRA_PATH = Path(__file__).resolve().parent / "data" / "uffici_ministero_extra.json"
_PST_PROXY_PDA_URL = "https://pda.processotelematico.giustizia.it"
_PST_PROXY_SH_URL = "https://ext.processotelematico.giustizia.it"
_PST_LEGACY_BASE = "https://wspa.giustizia.it/wspa"
_PST_SERVIZI_DEFAULT = ("JPW_SICID", "JPW_SIECIC", "JPW_SIGP", "JPW_CASSCI", "JPW_CASSPE")
_PST_SERVIZI_ALIAS = {
    "JPW_CASS": "JPW_CASSCI",
}
_PST_QBUILDER_NAMESPACES = {
    "JPW_SICID": "urn:CONS-SICC-BE",
    "JPW_SIECIC": "urn:CONS-SIECIC-BE",
    "JPW_SIGP": "urn:CONS-SIGP-BE",
    "JPW_CASSCI": "urn:CONS-CASSCI",
    "JPW_CASSPE": "urn:CONS-CASSPE",
    "JPW_UNEP": "urn:CONS-UNEP",
}
_IPA_OPEN_DATA_URL = "https://www.indicepa.it/ipa-dati/dataset/pec-ente"
_PST_SERVIZI_UFFICI_URL = "https://pst.giustizia.it/PST/it/services.page"
_PST_DEPOSITO_ATTO_URL = (
    "https://pst.giustizia.it/PST/it/dettaglio_schede_utente.page?contentId=ACC239&modelId=12"
)
_USI_PEC_PROCESSUALI = {"deposito_pct", "deposito_penale", "deposito_amministrativo", "deposito_tributario"}
_TIPI_USO_PEC = {
    "PROCURA": "deposito_penale",
    "PROCURA_GENERALE": "deposito_penale",
    "CORTE_CASSAZIONE": "deposito_pct",
    "TRIBUNALE": "deposito_pct",
    "CORTE_APPELLO": "deposito_pct",
    "TM": "deposito_pct",
    "SORVEGLIANZA": "deposito_penale",
    "CORTE_ASSISE": "deposito_penale",
    "GDP": "deposito_pct",
    "UNEP": "richiesta_unep",
    "TAR": "deposito_amministrativo",
    "CDS": "deposito_amministrativo",
    "CGARS": "deposito_amministrativo",
    "CGT": "deposito_tributario",
    "CPT": "deposito_tributario",
}


def _endpoint_uffici_autorizzato(endpoint: str, nome_fonte: str) -> str:
    """Restituisce solo l'endpoint ufficiale PST ammesso per la sync uffici."""
    value = str(endpoint or "").strip()
    if not value:
        return ""
    if nome_fonte == "pst_public":
        return _PST_UFFICI
    parsed = urlparse(value)
    official = urlparse(_PST_UFFICI)
    if parsed.scheme.lower() != "https":
        return ""
    if (parsed.hostname or "").lower() != (official.hostname or "").lower():
        return ""
    if parsed.path.rstrip("/") != official.path.rstrip("/"):
        return ""
    return _PST_UFFICI

# ---------------------------------------------------------------- tipi

TIPI_UFFICIO = {
    "TRIBUNALE":         ("bi-building",            "Tribunale"),
    "CORTE_APPELLO":     ("bi-bank2",               "Corte d'Appello"),
    "PROCURA":           ("bi-shield-exclamation",  "Procura della Repubblica"),
    "PROCURA_GENERALE":  ("bi-shield-fill",         "Procura Generale"),
    "CORTE_CASSAZIONE":  ("bi-star-fill",           "Cassazione"),
    "TM":                ("bi-people-fill",         "Trib. Minorenni"),
    "SORVEGLIANZA":      ("bi-eye-fill",            "Trib. Sorveglianza"),
    "CORTE_ASSISE":      ("bi-hammer",              "Corte d'Assise"),
    "CORTE_APPELLO_SEZIONE": ("bi-diagram-3",        "Sez. Corte d'Appello"),
    "GDP":               ("bi-person-badge",        "Giudice di Pace"),
    "UNEP":              ("bi-send-check",          "UNEP"),
    "TAR":               ("bi-building-check",      "TAR"),
    "CDS":               ("bi-columns-gap",         "Consiglio di Stato"),
    "CGARS":             ("bi-shield-half",          "CGARS"),
    "CGT":               ("bi-receipt-cutoff",       "CGT — Secondo grado"),
    "CPT":               ("bi-receipt",              "CPT — Primo grado"),
}


# ================================================================ bundle interno

def _n(testo: str) -> str:
    """Normalizza slug (rimuove accenti, lowercase, senza spazi)."""
    nfkd = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().replace(" ", "")


def _uffici_hash(uffici: list[dict]) -> str:
    """Restituisce un hash stabile del contenuto logico del bundle/cache."""
    canonici = [
        {
            "codice": u.get("codice", ""),
            "nome": u.get("nome", ""),
            "distretto": u.get("distretto", ""),
            "pec": u.get("pec", ""),
            "tipo": u.get("tipo", ""),
            "codice_ministero": u.get("codice_ministero", ""),
            "codice_gl": u.get("codice_gl", ""),
            "servizio_pst_predefinito": u.get("servizio_pst_predefinito", ""),
            "nome_certificato_cifra": u.get("nome_certificato_cifra", ""),
            "certificato_mimetype": u.get("certificato_mimetype", ""),
        }
        for u in uffici
    ]
    canonici.sort(key=lambda u: (u["codice"], u["nome"], u["tipo"]))
    payload = json.dumps(canonici, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _uso_pec_ufficio(ufficio: dict) -> str:
    tipo = str(ufficio.get("tipo") or "").upper()
    return _TIPI_USO_PEC.get(tipo, "deposito_pct")


def _fonte_prevalente_ufficio(ufficio: dict) -> str:
    tipo = str(ufficio.get("tipo") or "").upper()
    if ufficio.get("pec_ministero") or ufficio.get("codice_ministero") or _servizi_jpw(ufficio):
        return "PST"
    if tipo in {"TAR", "CDS", "CGARS"}:
        return "sito_ufficiale"
    if tipo in {"CGT", "CPT"}:
        return "sito_ufficiale"
    return "bundle_interno"


def indirizzi_telematici_ufficio(ufficio: dict, *, data_rilevazione: str = "") -> list[dict]:
    """Restituisce gli indirizzi telematici senza mischiare uso processuale e amministrativo."""
    pec = str(ufficio.get("pec") or ufficio.get("pec_ministero") or "").strip().lower()
    if not pec:
        return []
    uso = _uso_pec_ufficio(ufficio)
    fonte = _fonte_prevalente_ufficio(ufficio)
    tipo = str(ufficio.get("tipo") or "").upper()
    url_fonte = _PST_SERVIZI_UFFICI_URL if uso in _USI_PEC_PROCESSUALI or tipo == "UNEP" else _IPA_OPEN_DATA_URL
    if fonte == "sito_ufficiale":
        url_fonte = ""
    return [
        {
            "pec": pec,
            "uso": uso,
            "fonte": fonte,
            "url_fonte": url_fonte,
            "data_rilevazione": data_rilevazione,
            "attiva": True,
            "note": (
                "PEC dell'ufficio UNEP per richieste e ritorni del relativo canale."
                if tipo == "UNEP"
                else (
                    "PEC per deposito telematico: usare solo per atti processuali."
                    if uso in _USI_PEC_PROCESSUALI
                    else "PEC amministrativa o protocollo: usare per comunicazioni generiche."
                )
            ),
        }
    ]


def fonti_uffici_giudiziari(ultimo_errore: str | None = None) -> list[dict]:
    """Registro fonti mostrabile nei report di verifica uffici/PEC."""
    return [
        {
            "id": "pst",
            "nome": "PST Giustizia",
            "ruolo": "fonte primaria per PEC e uffici collegati al deposito telematico",
            "uso": sorted(_USI_PEC_PROCESSUALI),
            "url": _PST_SERVIZI_UFFICI_URL,
            "stato": "monitorata",
            "errore": ultimo_errore or "",
        },
        {
            "id": "ipa",
            "nome": "IPA Open Data",
            "ruolo": "fonte secondaria per PEC amministrative, protocollo, AOO e UO",
            "uso": ["protocollo", "amministrativa"],
            "url": _IPA_OPEN_DATA_URL,
            "stato": "monitorata",
            "errore": "",
        },
        {
            "id": "sito_ufficiale",
            "nome": "Sito ufficiale ufficio",
            "ruolo": "fallback documentale o verifica manuale",
            "uso": ["verifica_manualizzata"],
            "url": "",
            "stato": "fallback_manuale",
            "errore": "",
        },
    ]


def _calcola_variazioni_uffici(base: list[dict], confronto: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    base_idx = {u["codice"]: u for u in base if u.get("codice")}
    confronto_idx = {u["codice"]: u for u in confronto if u.get("codice")}

    pec_modificate = []
    for codice, bu in base_idx.items():
        if codice not in confronto_idx:
            continue
        pec_b = (bu.get("pec") or "").strip().lower()
        pec_c = (confronto_idx[codice].get("pec") or "").strip().lower()
        if pec_b and pec_c and pec_b != pec_c:
            pec_modificate.append({
                "codice": codice,
                "nome": bu.get("nome", ""),
                "pec_bundle": bu.get("pec", ""),
                "pec_remoto": confronto_idx[codice].get("pec", ""),
                "uso": _uso_pec_ufficio(bu),
                "fonte_prevalente": _fonte_prevalente_ufficio(bu),
            })

    aggiunti = [u for codice, u in confronto_idx.items() if codice not in base_idx]
    rimossi = [u for codice, u in base_idx.items() if codice not in confronto_idx]
    return pec_modificate, aggiunti, rimossi


def _normalizza_servizio_pst_name(servizio: str) -> str:
    valore = str(servizio or "").strip().upper()
    if not valore:
        return ""
    return _PST_SERVIZI_ALIAS.get(valore, valore)


def _servizi_jpw(ufficio: dict) -> set[str]:
    return {
        _normalizza_servizio_pst_name(servizio)
        for servizio in (ufficio.get("servizi_ministero") or [])
        if _normalizza_servizio_pst_name(servizio).startswith("JPW_")
    }


def _cache_pst_metadata_non_allineata(cache_uffici: list[dict], bundle_uffici: list[dict]) -> bool:
    """Verifica che la cache conservi i metadati ministeriali usati dal resolver PST."""
    cache_idx = {u.get("codice"): u for u in cache_uffici if u.get("codice")}
    for bundle in bundle_uffici:
        codice = bundle.get("codice")
        bundle_services = _servizi_jpw(bundle)
        if not codice or not bundle_services:
            continue
        cached = cache_idx.get(codice)
        if not cached:
            return True
        for chiave in (
            "codice_ministero",
            "codice_gl",
            "servizio_pst_predefinito",
            "nome_certificato_cifra",
            "certificato_mimetype",
        ):
            valore_bundle = str(bundle.get(chiave) or "").strip()
            if valore_bundle and str(cached.get(chiave) or "").strip() != valore_bundle:
                return True
        if not bundle_services.issubset(_servizi_jpw(cached)):
            return True
    return False


@lru_cache(maxsize=1)
def _carica_riferimenti_ministero() -> dict[str, dict]:
    """Carica la mappatura interna → metadata ministeriali generata da ListaUfficiGiudiziari.xml."""
    if not _RIFERIMENTI_MINISTERO_PATH.exists():
        return {}
    try:
        raw = json.loads(_RIFERIMENTI_MINISTERO_PATH.read_text(encoding="utf-8"))
        mapping = raw.get("uffici", {}) if isinstance(raw, dict) else {}
        return mapping if isinstance(mapping, dict) else {}
    except Exception as exc:
        log.warning("Lettura snapshot ministeriale uffici fallita: %s", exc)
        return {}


@lru_cache(maxsize=1)
def _carica_riferimenti_ministero_extra() -> list[dict]:
    """Carica le righe PST ufficiali assenti dal vecchio bundle interno."""
    if not _RIFERIMENTI_MINISTERO_EXTRA_PATH.exists():
        return []
    try:
        raw = json.loads(_RIFERIMENTI_MINISTERO_EXTRA_PATH.read_text(encoding="utf-8"))
        rows = raw.get("uffici", []) if isinstance(raw, dict) else []
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        log.warning("Lettura snapshot ministeriale extra uffici fallita: %s", exc)
        return []


def _nome_da_descrizione_ministeriale(ref: dict) -> str:
    descrizione = str(ref.get("descrizione_ministero") or "").strip()
    tipo = str(ref.get("tipo_ministero") or "").strip().upper()
    if not descrizione:
        return str(ref.get("nome") or ref.get("codice_ministero") or "").strip()
    if tipo == "CA" and " - " in descrizione:
        return "Corte d'Appello di " + descrizione.split(" - ", 1)[1].strip()
    if tipo == "OR" and descrizione.lower().startswith("tribunale ordinario - "):
        return "Tribunale di " + descrizione.split(" - ", 1)[1].strip()
    if tipo == "GP" and descrizione.lower().startswith("giudice di pace - "):
        return "Ufficio del Giudice di Pace di " + descrizione.split(" - ", 1)[1].strip()
    if tipo == "SC" and "corte d'appello" in descrizione.lower():
        return descrizione.replace("Sezione Distaccata di ", "Sezione distaccata della ")
    return descrizione


def _tipo_interno_da_ministero(ref: dict) -> str:
    tipo = str(ref.get("tipo_ministero") or "").strip().upper()
    descrizione = str(ref.get("descrizione_ministero") or "").strip().lower()
    if tipo == "CA":
        return "CORTE_APPELLO"
    if tipo == "OR":
        return "TRIBUNALE"
    if tipo == "PC":
        return "PROCURA"
    if tipo == "PG":
        return "PROCURA_GENERALE"
    if tipo == "TM":
        return "TM"
    if tipo == "SV":
        return "SORVEGLIANZA"
    if tipo == "GP":
        return "GDP"
    if tipo == "UP":
        return "UNEP"
    if tipo == "SC":
        return "CORTE_APPELLO_SEZIONE" if "corte d'appello" in descrizione else "TRIBUNALE"
    return tipo or "TRIBUNALE"


def _ufficio_extra_da_riferimento_ministeriale(ref: dict) -> dict:
    codice_ministero = str(ref.get("codice_ministero") or "").strip()
    distretto = str(ref.get("distretto_ministero") or ref.get("distretto_gl") or "").strip()
    pec = str(ref.get("pec_ministero") or "").strip().lower()
    ufficio = {
        "codice": codice_ministero,
        "nome": _nome_da_descrizione_ministeriale(ref),
        "distretto": distretto,
        "pec": pec,
        "tipo": _tipo_interno_da_ministero(ref),
        "fonte_registro": "PST",
        "codice_interno_iusentra": "",
        "aggiunto_da_snapshot_ministeriale": True,
    }
    for chiave in (
        "codice_ministero",
        "codice_gl",
        "descrizione_ministero",
        "tipo_ministero",
        "tipo_ministero_descrizione",
        "comune_ministero",
        "distretto_ministero",
        "distretto_gl",
        "regione_ministero",
        "provincia_ministero",
        "pec_ministero",
        "nome_certificato_cifra",
        "certificato_mimetype",
        "servizi_ministero",
        "servizio_pst_predefinito",
    ):
        if chiave in ref:
            ufficio[chiave] = ref[chiave]
    return ufficio


def _applica_riferimenti_ministero(uffici: list[dict]) -> list[dict]:
    """Sovrascrive distretto/PEC con il riferimento ministeriale e aggiunge metadati PST."""
    riferimenti = _carica_riferimenti_ministero()
    if not riferimenti:
        return uffici
    arricchiti: list[dict] = []
    for ufficio in uffici:
        ref = riferimenti.get(ufficio.get("codice", ""))
        if not ref:
            arricchiti.append(ufficio)
            continue
        merged = dict(ufficio)
        distretto = ref.get("distretto_ministero") or ""
        pec = (ref.get("pec_ministero") or "").strip().lower()
        if distretto:
            merged["distretto"] = distretto
        if pec:
            merged["pec"] = pec
        for chiave in (
            "codice_ministero",
            "codice_gl",
            "descrizione_ministero",
            "tipo_ministero",
            "tipo_ministero_descrizione",
            "comune_ministero",
            "distretto_ministero",
            "distretto_gl",
            "regione_ministero",
            "provincia_ministero",
            "pec_ministero",
            "nome_certificato_cifra",
            "certificato_mimetype",
            "servizi_ministero",
            "servizio_pst_predefinito",
        ):
            if chiave in ref:
                merged[chiave] = ref[chiave]
        arricchiti.append(merged)
    codici_presenti = {
        str(ufficio.get("codice") or "").strip()
        for ufficio in arricchiti
        if str(ufficio.get("codice") or "").strip()
    }
    codici_ministero_presenti = {
        str(ufficio.get("codice_ministero") or "").strip()
        for ufficio in arricchiti
        if str(ufficio.get("codice_ministero") or "").strip()
    }
    for ref in _carica_riferimenti_ministero_extra():
        codice_ministero = str(ref.get("codice_ministero") or "").strip()
        if not codice_ministero:
            continue
        if codice_ministero in codici_presenti or codice_ministero in codici_ministero_presenti:
            continue
        extra = _ufficio_extra_da_riferimento_ministeriale(ref)
        arricchiti.append(extra)
        codici_presenti.add(str(extra.get("codice") or "").strip())
        codici_ministero_presenti.add(codice_ministero)
    return arricchiti


def _t(cod, nome, dist, slug):
    return {"codice": cod, "nome": f"Tribunale di {nome}", "distretto": dist,
            "pec": f"tribunale.{slug}@giustiziapec.it", "tipo": "TRIBUNALE"}


def _ca(cod, nome, slug):
    return {"codice": cod, "nome": f"Corte d'Appello di {nome}", "distretto": nome,
            "pec": f"ca.{slug}@giustiziapec.it", "tipo": "CORTE_APPELLO"}


def _pr(cod, nome, dist, slug):
    return {"codice": cod, "nome": f"Procura della Repubblica di {nome}", "distretto": dist,
            "pec": f"procura.{slug}@giustiziapec.it", "tipo": "PROCURA"}


def _tm(cod, nome, dist, slug):
    return {"codice": cod, "nome": f"Tribunale per i Minorenni di {nome}", "distretto": dist,
            "pec": f"tm.{slug}@giustiziapec.it", "tipo": "TM"}


def _ts(cod, nome, dist, slug):
    return {"codice": cod, "nome": f"Tribunale di Sorveglianza di {nome}", "distretto": dist,
            "pec": f"tsor.{slug}@giustiziapec.it", "tipo": "SORVEGLIANZA"}


def _pg(cod, nome, slug):
    return {"codice": cod, "nome": f"Procura Generale di {nome}", "distretto": nome,
            "pec": f"pg.{slug}@giustiziapec.it", "tipo": "PROCURA_GENERALE"}


def _assise(cod, nome, dist, slug):
    return {"codice": cod, "nome": f"Corte d'Assise di {nome}", "distretto": dist,
            "pec": f"assise.{slug}@giustiziapec.it", "tipo": "CORTE_ASSISE"}


def _gdp(cod, nome, dist, slug):
    return {"codice": cod, "nome": f"Ufficio del Giudice di Pace di {nome}", "distretto": dist,
            "pec": f"gdp.{slug}@giustiziapec.it", "tipo": "GDP"}


def _tar(cod, nome, regione, slug):
    return {"codice": cod, "nome": f"TAR {nome}", "distretto": regione,
            "pec": f"tar-{slug}@pec.giustizia-amministrativa.it", "tipo": "TAR"}


def _cgars(cod, nome, distretto, slug):
    return {"codice": cod, "nome": nome, "distretto": distretto,
            "pec": f"{slug}@pec.giustizia-amministrativa.it", "tipo": "CGARS"}

def _cgt(cod, nome_regione, citta, slug):
    return {"codice": cod, "nome": f"CGT {nome_regione}", "distretto": citta,
            "pec": f"cgt.{slug}@pec.mef.gov.it", "tipo": "CGT"}

def _cpt(cod, citta, slug, distretto):
    return {"codice": cod, "nome": f"CPT {citta}", "distretto": distretto,
            "pec": f"cpt.{slug}@pec.mef.gov.it", "tipo": "CPT"}


# Registro completo — aggiornato al 2025
# Fonte: Registro indirizzi PEC uffici giudiziari, art. 7 DM 44/2011
_BUNDLE_RAW: list[dict] = [

    # ================================================================ TRIBUNALI

    # — Torino
    _t("0530010","Torino",         "Torino",    "torino"),
    _t("0010010","Aosta",          "Torino",    "aosta"),
    _t("0530011","Alba",           "Torino",    "alba"),
    _t("0050010","Asti",           "Torino",    "asti"),
    _t("0060010","Alessandria",    "Torino",    "alessandria"),
    _t("0040010","Cuneo",          "Torino",    "cuneo"),
    _t("0530012","Ivrea",          "Torino",    "ivrea"),
    _t("0030010","Novara",         "Torino",    "novara"),
    _t("0530013","Verbania",       "Torino",    "verbania"),
    _t("0020010","Vercelli",       "Torino",    "vercelli"),
    _t("0530014","Acqui Terme",    "Torino",    "acqui"),

    # — Genova
    _t("0540010","Genova",         "Genova",    "genova"),
    _t("0540011","Chiavari",       "Genova",    "chiavari"),
    _t("0550010","Imperia",        "Genova",    "imperia"),
    _t("0540012","Massa",          "Genova",    "massa"),
    _t("0560010","La Spezia",      "Genova",    "la-spezia"),
    _t("0570010","Savona",         "Genova",    "savona"),
    _t("0540013","Sanremo",        "Genova",    "sanremo"),

    # — Milano
    _t("0580010","Milano",         "Milano",    "milano"),
    _t("0580011","Bergamo",        "Milano",    "bergamo"),
    _t("0600010","Brescia",        "Brescia",   "brescia"),
    _t("0580012","Busto Arsizio",  "Milano",    "bustoarsizio"),
    _t("0580013","Como",           "Milano",    "como"),
    _t("0610010","Cremona",        "Brescia",   "cremona"),
    _t("0580014","Lecco",          "Milano",    "lecco"),
    _t("0580015","Lodi",           "Milano",    "lodi"),
    _t("0610011","Mantova",        "Brescia",   "mantova"),
    _t("0580016","Monza",          "Milano",    "monza"),
    _t("0580017","Pavia",          "Milano",    "pavia"),
    _t("0580018","Sondrio",        "Milano",    "sondrio"),
    _t("0580019","Varese",         "Milano",    "varese"),

    # — Venezia
    _t("0620010","Venezia",        "Venezia",   "venezia"),
    _t("0620011","Belluno",        "Venezia",   "belluno"),
    _t("0640010","Padova",         "Venezia",   "padova"),
    _t("0630010","Rovigo",         "Venezia",   "rovigo"),
    _t("0620012","Treviso",        "Venezia",   "treviso"),
    _t("0640011","Vicenza",        "Venezia",   "vicenza"),
    _t("0650010","Verona",         "Venezia",   "verona"),

    # — Trieste
    _t("0660010","Trieste",        "Trieste",   "trieste"),
    _t("0660011","Gorizia",        "Trieste",   "gorizia"),
    _t("0660012","Pordenone",      "Trieste",   "pordenone"),
    _t("0670010","Udine",          "Trieste",   "udine"),

    # — Trento / Bolzano (autonomi)
    _t("0680010","Trento",         "Trento",    "trento"),
    _t("0680011","Rovereto",       "Trento",    "rovereto"),
    _t("0690010","Bolzano",        "Trento",    "bolzano"),

    # — Bologna
    _t("0700010","Bologna",        "Bologna",   "bologna"),
    _t("0700011","Ferrara",        "Bologna",   "ferrara"),
    _t("0700012","Forlì",          "Bologna",   "forli"),
    _t("0700013","Modena",         "Bologna",   "modena"),
    _t("0700014","Parma",          "Bologna",   "parma"),
    _t("0700015","Piacenza",       "Bologna",   "piacenza"),
    _t("0700016","Ravenna",        "Bologna",   "ravenna"),
    _t("0700017","Reggio Emilia",  "Bologna",   "reggioemilia"),
    _t("0700018","Rimini",         "Bologna",   "rimini"),

    # — Firenze
    _t("0710010","Firenze",        "Firenze",   "firenze"),
    _t("0710011","Arezzo",         "Firenze",   "arezzo"),
    _t("0710012","Grosseto",       "Firenze",   "grosseto"),
    _t("0710013","Livorno",        "Firenze",   "livorno"),
    _t("0710014","Lucca",          "Firenze",   "lucca"),
    _t("0710015","Massa Carrara",  "Firenze",   "massacarrara"),
    _t("0710016","Pisa",           "Firenze",   "pisa"),
    _t("0710017","Pistoia",        "Firenze",   "pistoia"),
    _t("0710018","Prato",          "Firenze",   "prato"),
    _t("0710019","Siena",          "Firenze",   "siena"),

    # — Perugia
    _t("0730010","Perugia",        "Perugia",   "perugia"),
    _t("0730011","Orvieto",        "Perugia",   "orvieto"),
    _t("0730012","Spoleto",        "Perugia",   "spoleto"),
    _t("0740010","Terni",          "Perugia",   "terni"),

    # — Ancona
    _t("0750010","Ancona",         "Ancona",    "ancona"),
    _t("0750011","Ascoli Piceno",  "Ancona",    "ascolipiceno"),
    _t("0750012","Fermo",          "Ancona",    "fermo"),
    _t("0750013","Macerata",       "Ancona",    "macerata"),
    _t("0750014","Pesaro",         "Ancona",    "pesaro"),
    _t("0750015","Urbino",         "Ancona",    "urbino"),

    # — Roma
    _t("0760010","Roma",           "Roma",      "roma"),
    _t("0760011","Civitavecchia",  "Roma",      "civitavecchia"),
    _t("0770010","Frosinone",      "Roma",      "frosinone"),
    _t("0780010","Latina",         "Roma",      "latina"),
    _t("0760012","Rieti",          "Roma",      "rieti"),
    _t("0760013","Tivoli",         "Roma",      "tivoli"),
    _t("0760014","Velletri",       "Roma",      "velletri"),
    _t("0790010","Viterbo",        "Roma",      "viterbo"),

    # — L'Aquila
    _t("0800010","L'Aquila",       "L'Aquila",  "laquila"),
    _t("0800011","Avezzano",       "L'Aquila",  "avezzano"),
    _t("0810010","Chieti",         "L'Aquila",  "chieti"),
    _t("0810011","Lanciano",       "L'Aquila",  "lanciano"),
    _t("0810012","Pescara",        "L'Aquila",  "pescara"),
    _t("0800012","Sulmona",        "L'Aquila",  "sulmona"),
    _t("0810013","Teramo",         "L'Aquila",  "teramo"),
    _t("0810014","Vasto",          "L'Aquila",  "vasto"),

    # — Campobasso (distretto autonomo)
    _t("0815010","Campobasso",     "Campobasso","campobasso"),
    _t("0815011","Isernia",        "Campobasso","isernia"),
    _t("0815012","Larino",         "Campobasso","larino"),

    # — Napoli
    _t("0820010","Napoli",         "Napoli",    "napoli"),
    _t("0820011","Napoli Nord",    "Napoli",    "napolinord"),
    _t("0830011","Ariano Irpino",  "Napoli",    "arianoirpino"),
    _t("0830010","Avellino",       "Napoli",    "avellino"),
    _t("0840010","Benevento",      "Napoli",    "benevento"),
    _t("0850010","Caserta",        "Napoli",    "caserta"),
    _t("0820012","Nola",           "Napoli",    "nola"),
    _t("0860010","Salerno",        "Napoli",    "salerno"),
    _t("0860011","Nocera Inferiore","Napoli",   "nocera"),
    _t("0820013","Torre Annunziata","Napoli",   "torreannunziata"),
    _t("0850011","Santa Maria Capua Vetere","Napoli","santamariacapuavetere"),
    _t("0860012","Vallo della Lucania","Napoli","vallo"),

    # — Potenza
    _t("0870010","Potenza",        "Potenza",   "potenza"),
    _t("0870011","Lagonegro",      "Potenza",   "lagonegro"),
    _t("0880010","Matera",         "Potenza",   "matera"),
    _t("0870012","Melfi",          "Potenza",   "melfi"),

    # — Catanzaro
    _t("0890010","Catanzaro",      "Catanzaro", "catanzaro"),
    _t("0900010","Cosenza",        "Catanzaro", "cosenza"),
    _t("0890011","Crotone",        "Catanzaro", "crotone"),
    _t("0890012","Lamezia Terme",  "Catanzaro", "lamezia"),
    _t("0900011","Paola",          "Catanzaro", "paola"),
    _t("0900012","Rossano",        "Catanzaro", "rossano"),
    _t("0890013","Vibo Valentia",  "Catanzaro", "vibovalentia"),

    # — Reggio Calabria
    _t("0910011","Palmi",          "Reggio Calabria", "palmi"),
    _t("0910010","Reggio Calabria","Reggio Calabria", "reggiocalabria"),

    # — Palermo
    _t("0920010","Palermo",        "Palermo",   "palermo"),
    _t("0920011","Agrigento",      "Palermo",   "agrigento"),
    _t("0930011","Marsala",        "Palermo",   "marsala"),
    _t("0920012","Sciacca",        "Palermo",   "sciacca"),
    _t("0920013","Termini Imerese","Palermo",   "terminiimerese"),
    _t("0930010","Trapani",        "Palermo",   "trapani"),

    # — Messina
    _t("0940010","Messina",        "Messina",   "messina"),
    _t("0940011","Barcellona Pozzo di Gotto","Messina","barcellona"),
    _t("0940012","Patti",          "Messina",   "patti"),

    # — Catania
    _t("0950010","Catania",        "Catania",   "catania"),
    _t("0950011","Caltagirone",    "Catania",   "caltagirone"),
    _t("0950012","Enna",           "Catania",   "enna"),
    _t("0950013","Nicosia",        "Catania",   "nicosia"),
    _t("0960010","Ragusa",         "Catania",   "ragusa"),
    _t("0970010","Siracusa",       "Catania",   "siracusa"),
    _t("0960011","Modica",         "Catania",   "modica"),

    # — Cagliari
    _t("0980010","Cagliari",       "Cagliari",  "cagliari"),
    _t("0980011","Lanusei",        "Cagliari",  "lanusei"),
    _t("1000010","Nuoro",          "Cagliari",  "nuoro"),
    _t("0980012","Oristano",       "Cagliari",  "oristano"),
    _t("1010010","Sassari",        "Cagliari",  "sassari"),
    _t("1010011","Tempio Pausania","Cagliari",  "tempiopausania"),

    # — Bari (distretto)
    _t("1020010","Bari",           "Bari",      "bari"),
    _t("1020011","Trani",          "Bari",      "trani"),
    _t("1030010","Foggia",         "Bari",      "foggia"),
    _t("1020012","Taranto",        "Bari",      "taranto"),

    # — Lecce
    _t("1040010","Lecce",          "Lecce",     "lecce"),
    _t("1040011","Brindisi",       "Lecce",     "brindisi"),

    # ================================================================ CORTI D'APPELLO
    _ca("0530000","Torino",       "torino"),
    _ca("0540000","Genova",       "genova"),
    _ca("0580000","Milano",       "milano"),
    _ca("0600000","Brescia",      "brescia"),
    _ca("0620000","Venezia",      "venezia"),
    _ca("0660000","Trieste",      "trieste"),
    _ca("0680000","Trento",       "trento"),
    _ca("0700000","Bologna",      "bologna"),
    _ca("0710000","Firenze",      "firenze"),
    _ca("0730000","Perugia",      "perugia"),
    _ca("0750000","Ancona",       "ancona"),
    _ca("0760000","Roma",         "roma"),
    _ca("0800000","L'Aquila",     "laquila"),
    _ca("0815000","Campobasso",   "campobasso"),
    _ca("0820000","Napoli",       "napoli"),
    _ca("0870000","Potenza",      "potenza"),
    _ca("0890000","Catanzaro",    "catanzaro"),
    _ca("0920000","Palermo",      "palermo"),
    _ca("0940000","Messina",      "messina"),
    _ca("0950000","Catania",      "catania"),
    _ca("0980000","Cagliari",     "cagliari"),
    _ca("1020000","Bari",         "bari"),
    _ca("1040000","Lecce",        "lecce"),

    # ================================================================ CORTE DI CASSAZIONE
    {
        "codice": "9990000",
        "nome": "Corte Suprema di Cassazione",
        "distretto": "Roma",
        "pec": "scpd@cassazione.it",
        "tipo": "CORTE_CASSAZIONE",
    },
    # Procura Generale Cassazione
    {
        "codice": "9990001",
        "nome": "Procura Generale presso la Corte di Cassazione",
        "distretto": "Roma",
        "pec": "pg.cassazione@giustiziapec.it",
        "tipo": "PROCURA",
    },

    # ================================================================ PROCURE DELLA REPUBBLICA
    # (generate automaticamente dal registro tribunali — vedi _genera_procure)

    # ================================================================ TRIBUNALI PER I MINORENNI
    _tm("0530100","Torino",          "Torino",    "torino"),
    _tm("0540100","Genova",          "Genova",    "genova"),
    _tm("0580100","Milano",          "Milano",    "milano"),
    _tm("0600100","Brescia",         "Brescia",   "brescia"),
    _tm("0620100","Venezia",         "Venezia",   "venezia"),
    _tm("0660100","Trieste",         "Trieste",   "trieste"),
    _tm("0680100","Trento",          "Trento",    "trento"),
    _tm("0700100","Bologna",         "Bologna",   "bologna"),
    _tm("0710100","Firenze",         "Firenze",   "firenze"),
    _tm("0730100","Perugia",         "Perugia",   "perugia"),
    _tm("0750100","Ancona",          "Ancona",    "ancona"),
    _tm("0760100","Roma",            "Roma",      "roma"),
    _tm("0800100","L'Aquila",        "L'Aquila",  "laquila"),
    _tm("0815100","Campobasso",      "Campobasso","campobasso"),
    _tm("0820100","Napoli",          "Napoli",    "napoli"),
    _tm("0860100","Salerno",         "Napoli",    "salerno"),
    _tm("0870100","Potenza",         "Potenza",   "potenza"),
    _tm("0890100","Catanzaro",       "Catanzaro", "catanzaro"),
    _tm("0910100","Reggio Calabria", "Reggio Calabria", "reggiocalabria"),
    _tm("0920100","Palermo",         "Palermo",   "palermo"),
    _tm("0940100","Messina",         "Messina",   "messina"),
    _tm("0950100","Catania",         "Catania",   "catania"),
    _tm("0980100","Cagliari",        "Cagliari",  "cagliari"),
    _tm("1010100","Sassari",         "Cagliari",  "sassari"),
    _tm("1020100","Bari",            "Bari",      "bari"),
    _tm("1040100","Lecce",           "Lecce",     "lecce"),

    # ================================================================ TRIBUNALI DI SORVEGLIANZA
    _ts("0530200","Torino",          "Torino",    "torino"),
    _ts("0540200","Genova",          "Genova",    "genova"),
    _ts("0580200","Milano",          "Milano",    "milano"),
    _ts("0600200","Brescia",         "Brescia",   "brescia"),
    _ts("0620200","Venezia",         "Venezia",   "venezia"),
    _ts("0660200","Trieste",         "Trieste",   "trieste"),
    _ts("0680200","Trento",          "Trento",    "trento"),
    _ts("0700200","Bologna",         "Bologna",   "bologna"),
    _ts("0710200","Firenze",         "Firenze",   "firenze"),
    _ts("0730200","Perugia",         "Perugia",   "perugia"),
    _ts("0750200","Ancona",          "Ancona",    "ancona"),
    _ts("0760200","Roma",            "Roma",      "roma"),
    _ts("0800200","L'Aquila",        "L'Aquila",  "laquila"),
    _ts("0815200","Campobasso",      "Campobasso","campobasso"),
    _ts("0820200","Napoli",          "Napoli",    "napoli"),
    _ts("0860200","Salerno",         "Napoli",    "salerno"),
    _ts("0870200","Potenza",         "Potenza",   "potenza"),
    _ts("0890200","Catanzaro",       "Catanzaro", "catanzaro"),
    _ts("0910200","Reggio Calabria", "Reggio Calabria", "reggiocalabria"),
    _ts("0920200","Palermo",         "Palermo",   "palermo"),
    _ts("0940200","Messina",         "Messina",   "messina"),
    _ts("0950200","Catania",         "Catania",   "catania"),
    _ts("0980200","Cagliari",        "Cagliari",  "cagliari"),
    _ts("1010200","Sassari",         "Cagliari",  "sassari"),
    _ts("1020200","Bari",            "Bari",      "bari"),
    _ts("1040200","Lecce",           "Lecce",     "lecce"),

    # ================================================================ PROCURE GENERALI
    # (una per ogni Corte d'Appello — art. 105 ord. giudiziario)
    _pg("0530500","Torino",       "torino"),
    _pg("0540500","Genova",       "genova"),
    _pg("0580500","Milano",       "milano"),
    _pg("0600500","Brescia",      "brescia"),
    _pg("0620500","Venezia",      "venezia"),
    _pg("0660500","Trieste",      "trieste"),
    _pg("0680500","Trento",       "trento"),
    _pg("0700500","Bologna",      "bologna"),
    _pg("0710500","Firenze",      "firenze"),
    _pg("0730500","Perugia",      "perugia"),
    _pg("0750500","Ancona",       "ancona"),
    _pg("0760500","Roma",         "roma"),
    _pg("0800500","L'Aquila",     "laquila"),
    _pg("0815500","Campobasso",   "campobasso"),
    _pg("0820500","Napoli",       "napoli"),
    _pg("0870500","Potenza",      "potenza"),
    _pg("0890500","Catanzaro",    "catanzaro"),
    _pg("0920500","Palermo",      "palermo"),
    _pg("0940500","Messina",      "messina"),
    _pg("0950500","Catania",      "catania"),
    _pg("0980500","Cagliari",     "cagliari"),
    _pg("1020500","Bari",         "bari"),
    _pg("1040500","Lecce",        "lecce"),

    # ================================================================ CORTI D'ASSISE
    # (art. 5 c.p.p. — competenza per reati gravi; una per distretto principale)
    _assise("0530300","Torino",          "Torino",    "torino"),
    _assise("0530301","Alessandria",     "Torino",    "alessandria"),
    _assise("0530302","Asti",            "Torino",    "asti"),
    _assise("0530303","Cuneo",           "Torino",    "cuneo"),
    _assise("0530304","Novara",          "Torino",    "novara"),
    _assise("0530305","Vercelli",        "Torino",    "vercelli"),
    _assise("0540300","Genova",          "Genova",    "genova"),
    _assise("0540301","Imperia",         "Genova",    "imperia"),
    _assise("0540302","Savona",          "Genova",    "savona"),
    _assise("0580300","Milano",          "Milano",    "milano"),
    _assise("0580301","Bergamo",         "Milano",    "bergamo"),
    _assise("0580302","Brescia",         "Brescia",   "brescia"),
    _assise("0580303","Como",            "Milano",    "como"),
    _assise("0580304","Cremona",         "Brescia",   "cremona"),
    _assise("0580305","Mantova",         "Brescia",   "mantova"),
    _assise("0580306","Varese",          "Milano",    "varese"),
    _assise("0620300","Venezia",         "Venezia",   "venezia"),
    _assise("0620301","Padova",          "Venezia",   "padova"),
    _assise("0620302","Verona",          "Venezia",   "verona"),
    _assise("0620303","Vicenza",         "Venezia",   "vicenza"),
    _assise("0660300","Trieste",         "Trieste",   "trieste"),
    _assise("0660301","Udine",           "Trieste",   "udine"),
    _assise("0680300","Trento",          "Trento",    "trento"),
    _assise("0700300","Bologna",         "Bologna",   "bologna"),
    _assise("0700301","Modena",          "Bologna",   "modena"),
    _assise("0700302","Parma",           "Bologna",   "parma"),
    _assise("0700303","Ravenna",         "Bologna",   "ravenna"),
    _assise("0700304","Reggio Emilia",   "Bologna",   "reggioemilia"),
    _assise("0710300","Firenze",         "Firenze",   "firenze"),
    _assise("0710301","Arezzo",          "Firenze",   "arezzo"),
    _assise("0710302","Livorno",         "Firenze",   "livorno"),
    _assise("0710303","Siena",           "Firenze",   "siena"),
    _assise("0730300","Perugia",         "Perugia",   "perugia"),
    _assise("0740300","Terni",           "Perugia",   "terni"),
    _assise("0750300","Ancona",          "Ancona",    "ancona"),
    _assise("0760300","Roma",            "Roma",      "roma"),
    _assise("0760301","Frosinone",       "Roma",      "frosinone"),
    _assise("0760302","Latina",          "Roma",      "latina"),
    _assise("0760303","Viterbo",         "Roma",      "viterbo"),
    _assise("0800300","L'Aquila",        "L'Aquila",  "laquila"),
    _assise("0810300","Chieti",          "L'Aquila",  "chieti"),
    _assise("0810301","Pescara",         "L'Aquila",  "pescara"),
    _assise("0810302","Teramo",          "L'Aquila",  "teramo"),
    _assise("0815300","Campobasso",      "Campobasso","campobasso"),
    _assise("0820300","Napoli",          "Napoli",    "napoli"),
    _assise("0830300","Avellino",        "Napoli",    "avellino"),
    _assise("0840300","Benevento",       "Napoli",    "benevento"),
    _assise("0850300","Caserta",         "Napoli",    "caserta"),
    _assise("0860300","Salerno",         "Napoli",    "salerno"),
    _assise("0870300","Potenza",         "Potenza",   "potenza"),
    _assise("0880300","Matera",          "Potenza",   "matera"),
    _assise("0890300","Catanzaro",       "Catanzaro", "catanzaro"),
    _assise("0900300","Cosenza",         "Catanzaro", "cosenza"),
    _assise("0910300","Reggio Calabria", "Reggio Calabria", "reggiocalabria"),
    _assise("0920300","Palermo",         "Palermo",   "palermo"),
    _assise("0920301","Agrigento",       "Palermo",   "agrigento"),
    _assise("0920302","Trapani",         "Palermo",   "trapani"),
    _assise("0940300","Messina",         "Messina",   "messina"),
    _assise("0950300","Catania",         "Catania",   "catania"),
    _assise("0960300","Ragusa",          "Catania",   "ragusa"),
    _assise("0970300","Siracusa",        "Catania",   "siracusa"),
    _assise("0980300","Cagliari",        "Cagliari",  "cagliari"),
    _assise("1000300","Nuoro",           "Cagliari",  "nuoro"),
    _assise("1010300","Sassari",         "Cagliari",  "sassari"),
    _assise("1020300","Bari",            "Bari",      "bari"),
    _assise("1020301","Foggia",          "Bari",      "foggia"),
    _assise("1020302","Taranto",         "Bari",      "taranto"),
    _assise("1040300","Lecce",           "Lecce",     "lecce"),
    _assise("1040301","Brindisi",        "Lecce",     "brindisi"),

    # ================================================================ GIUDICI DI PACE
    # Capoluoghi di regione + principali province (d.lgs. 274/2000, l. 374/1991)
    # ── Nord-Ovest
    _gdp("0530400","Torino",          "Torino",    "torino"),
    _gdp("0530401","Aosta",           "Torino",    "aosta"),
    _gdp("0530402","Alessandria",     "Torino",    "alessandria"),
    _gdp("0530403","Asti",            "Torino",    "asti"),
    _gdp("0530404","Biella",          "Torino",    "biella"),
    _gdp("0530405","Cuneo",           "Torino",    "cuneo"),
    _gdp("0530406","Novara",          "Torino",    "novara"),
    _gdp("0530407","Verbania",        "Torino",    "verbania"),
    _gdp("0530408","Vercelli",        "Torino",    "vercelli"),
    _gdp("0530409","Moncalieri",      "Torino",    "moncalieri"),
    _gdp("0530410","Ivrea",           "Torino",    "ivrea"),
    _gdp("0530411","Acqui Terme",     "Torino",    "acquiterme"),
    _gdp("0530412","Alba",            "Torino",    "alba"),
    _gdp("0540400","Genova",          "Genova",    "genova"),
    _gdp("0540401","Imperia",         "Genova",    "imperia"),
    _gdp("0540402","La Spezia",       "Genova",    "laspezia"),
    _gdp("0540403","Sanremo",         "Genova",    "sanremo"),
    _gdp("0540404","Savona",          "Genova",    "savona"),
    _gdp("0540405","Chiavari",        "Genova",    "chiavari"),
    _gdp("0540406","Massa",           "Genova",    "massa"),
    # ── Nord-Est (Milano)
    _gdp("0580400","Milano",          "Milano",    "milano"),
    _gdp("0580401","Bergamo",         "Milano",    "bergamo"),
    _gdp("0580402","Brescia",         "Brescia",   "brescia"),
    _gdp("0580403","Busto Arsizio",   "Milano",    "bustoarsizio"),
    _gdp("0580404","Como",            "Milano",    "como"),
    _gdp("0580405","Cremona",         "Brescia",   "cremona"),
    _gdp("0580406","Lecco",           "Milano",    "lecco"),
    _gdp("0580407","Lodi",            "Milano",    "lodi"),
    _gdp("0580408","Mantova",         "Brescia",   "mantova"),
    _gdp("0580409","Monza",           "Milano",    "monza"),
    _gdp("0580410","Pavia",           "Milano",    "pavia"),
    _gdp("0580411","Sondrio",         "Milano",    "sondrio"),
    _gdp("0580412","Varese",          "Milano",    "varese"),
    _gdp("0580413","Vigevano",        "Milano",    "vigevano"),
    # ── Venezia / Trieste
    _gdp("0620400","Venezia",         "Venezia",   "venezia"),
    _gdp("0620401","Belluno",         "Venezia",   "belluno"),
    _gdp("0620402","Padova",          "Venezia",   "padova"),
    _gdp("0620403","Rovigo",          "Venezia",   "rovigo"),
    _gdp("0620404","Treviso",         "Venezia",   "treviso"),
    _gdp("0620405","Verona",          "Venezia",   "verona"),
    _gdp("0620406","Vicenza",         "Venezia",   "vicenza"),
    _gdp("0660400","Trieste",         "Trieste",   "trieste"),
    _gdp("0660401","Gorizia",         "Trieste",   "gorizia"),
    _gdp("0660402","Pordenone",       "Trieste",   "pordenone"),
    _gdp("0660403","Udine",           "Trieste",   "udine"),
    _gdp("0680400","Trento",          "Trento",    "trento"),
    _gdp("0680401","Rovereto",        "Trento",    "rovereto"),
    _gdp("0690400","Bolzano",         "Trento",    "bolzano"),
    # ── Bologna / Toscana / Umbria / Marche
    _gdp("0700400","Bologna",         "Bologna",   "bologna"),
    _gdp("0700401","Ferrara",         "Bologna",   "ferrara"),
    _gdp("0700402","Forlì",           "Bologna",   "forli"),
    _gdp("0700403","Modena",          "Bologna",   "modena"),
    _gdp("0700404","Parma",           "Bologna",   "parma"),
    _gdp("0700405","Piacenza",        "Bologna",   "piacenza"),
    _gdp("0700406","Ravenna",         "Bologna",   "ravenna"),
    _gdp("0700407","Reggio Emilia",   "Bologna",   "reggioemilia"),
    _gdp("0700408","Rimini",          "Bologna",   "rimini"),
    _gdp("0710400","Firenze",         "Firenze",   "firenze"),
    _gdp("0710401","Arezzo",          "Firenze",   "arezzo"),
    _gdp("0710402","Grosseto",        "Firenze",   "grosseto"),
    _gdp("0710403","Livorno",         "Firenze",   "livorno"),
    _gdp("0710404","Lucca",           "Firenze",   "lucca"),
    _gdp("0710405","Pisa",            "Firenze",   "pisa"),
    _gdp("0710406","Pistoia",         "Firenze",   "pistoia"),
    _gdp("0710407","Prato",           "Firenze",   "prato"),
    _gdp("0710408","Siena",           "Firenze",   "siena"),
    _gdp("0710409","Massa Carrara",   "Firenze",   "massacarrara"),
    _gdp("0730400","Perugia",         "Perugia",   "perugia"),
    _gdp("0730401","Orvieto",         "Perugia",   "orvieto"),
    _gdp("0730402","Spoleto",         "Perugia",   "spoleto"),
    _gdp("0740400","Terni",           "Perugia",   "terni"),
    _gdp("0750400","Ancona",          "Ancona",    "ancona"),
    _gdp("0750401","Ascoli Piceno",   "Ancona",    "ascolipiceno"),
    _gdp("0750402","Macerata",        "Ancona",    "macerata"),
    _gdp("0750403","Pesaro",          "Ancona",    "pesaro"),
    _gdp("0750404","Fermo",           "Ancona",    "fermo"),
    _gdp("0750405","Urbino",          "Ancona",    "urbino"),
    # ── Roma / Lazio / Abruzzo / Molise
    _gdp("0760400","Roma",            "Roma",      "roma"),
    _gdp("0760401","Civitavecchia",   "Roma",      "civitavecchia"),
    _gdp("0760402","Frosinone",       "Roma",      "frosinone"),
    _gdp("0760403","Latina",          "Roma",      "latina"),
    _gdp("0760404","Rieti",           "Roma",      "rieti"),
    _gdp("0760405","Viterbo",         "Roma",      "viterbo"),
    _gdp("0760406","Tivoli",          "Roma",      "tivoli"),
    _gdp("0760407","Velletri",        "Roma",      "velletri"),
    _gdp("0800400","L'Aquila",        "L'Aquila",  "laquila"),
    _gdp("0800401","Avezzano",        "L'Aquila",  "avezzano"),
    _gdp("0800402","Sulmona",         "L'Aquila",  "sulmona"),
    _gdp("0810400","Chieti",          "L'Aquila",  "chieti"),
    _gdp("0810401","Pescara",         "L'Aquila",  "pescara"),
    _gdp("0810402","Teramo",          "L'Aquila",  "teramo"),
    _gdp("0810403","Lanciano",        "L'Aquila",  "lanciano"),
    _gdp("0810404","Vasto",           "L'Aquila",  "vasto"),
    _gdp("0815400","Campobasso",      "Campobasso","campobasso"),
    _gdp("0815401","Isernia",         "Campobasso","isernia"),
    _gdp("0815402","Larino",          "Campobasso","larino"),
    # ── Napoli / Campania
    _gdp("0820400","Napoli",          "Napoli",    "napoli"),
    _gdp("0820401","Afragola",        "Napoli",    "afragola"),
    _gdp("0820402","Giugliano",       "Napoli",    "giugliano"),
    _gdp("0820403","Portici",         "Napoli",    "portici"),
    _gdp("0820404","Napoli Nord",     "Napoli",    "napolinord"),
    _gdp("0820405","Nola",            "Napoli",    "nola"),
    _gdp("0820406","Torre Annunziata","Napoli",    "torreannunziata"),
    _gdp("0830400","Avellino",        "Napoli",    "avellino"),
    _gdp("0830401","Ariano Irpino",   "Napoli",    "arianoirpino"),
    _gdp("0840400","Benevento",       "Napoli",    "benevento"),
    _gdp("0850400","Caserta",         "Napoli",    "caserta"),
    _gdp("0850401","Santa Maria Capua Vetere","Napoli","santamariacapuavetere"),
    _gdp("0860400","Salerno",         "Napoli",    "salerno"),
    _gdp("0860401","Nocera Inferiore","Napoli",    "nocerainferiore"),
    _gdp("0860402","Vallo della Lucania","Napoli", "vallodellalucania"),
    # ── Basilicata / Calabria
    _gdp("0870400","Potenza",         "Potenza",   "potenza"),
    _gdp("0870401","Lagonegro",       "Potenza",   "lagonegro"),
    _gdp("0870402","Melfi",           "Potenza",   "melfi"),
    _gdp("0880400","Matera",          "Potenza",   "matera"),
    _gdp("0890400","Catanzaro",       "Catanzaro", "catanzaro"),
    _gdp("0890401","Crotone",         "Catanzaro", "crotone"),
    _gdp("0890402","Vibo Valentia",   "Catanzaro", "vibovalentia"),
    _gdp("0890403","Lamezia Terme",   "Catanzaro", "lameziaterme"),
    _gdp("0900400","Cosenza",         "Catanzaro", "cosenza"),
    _gdp("0900401","Paola",           "Catanzaro", "paola"),
    _gdp("0900402","Rossano",         "Catanzaro", "rossano"),
    _gdp("0910400","Reggio Calabria", "Reggio Calabria", "reggiocalabria"),
    _gdp("0910401","Palmi",           "Reggio Calabria", "palmi"),
    # ── Sicilia
    _gdp("0920400","Palermo",         "Palermo",   "palermo"),
    _gdp("0920401","Agrigento",       "Palermo",   "agrigento"),
    _gdp("0920402","Trapani",         "Palermo",   "trapani"),
    _gdp("0920403","Sciacca",         "Palermo",   "sciacca"),
    _gdp("0920404","Termini Imerese", "Palermo",   "terminimerese"),
    _gdp("0930400","Caltanissetta",   "Palermo",   "caltanissetta"),
    _gdp("0930401","Marsala",         "Palermo",   "marsala"),
    _gdp("0940400","Messina",         "Messina",   "messina"),
    _gdp("0940401","Barcellona Pozzo di Gotto","Messina","barcellonapdg"),
    _gdp("0940402","Patti",           "Messina",   "patti"),
    _gdp("0950400","Catania",         "Catania",   "catania"),
    _gdp("0950401","Enna",            "Catania",   "enna"),
    _gdp("0950402","Caltagirone",     "Catania",   "caltagirone"),
    _gdp("0950403","Nicosia",         "Catania",   "nicosia"),
    _gdp("0960400","Ragusa",          "Catania",   "ragusa"),
    _gdp("0960401","Modica",          "Catania",   "modica"),
    _gdp("0970400","Siracusa",        "Catania",   "siracusa"),
    # ── Sardegna
    _gdp("0980400","Cagliari",        "Cagliari",  "cagliari"),
    _gdp("0980401","Oristano",        "Cagliari",  "oristano"),
    _gdp("0980402","Lanusei",         "Cagliari",  "lanusei"),
    _gdp("1000400","Nuoro",           "Cagliari",  "nuoro"),
    _gdp("1010400","Sassari",         "Sassari",   "sassari"),
    _gdp("1010401","Tempio Pausania", "Sassari",   "tempiopausania"),
    # ── Puglia
    _gdp("1020400","Bari",            "Bari",      "bari"),
    _gdp("1020401","Altamura",        "Bari",      "altamura"),
    _gdp("1020402","Molfetta",        "Bari",      "molfetta"),
    _gdp("1020403","Taranto",         "Bari",      "taranto"),
    _gdp("1020404","Trani",           "Bari",      "trani"),
    _gdp("1030400","Foggia",          "Bari",      "foggia"),
    _gdp("1040400","Lecce",           "Lecce",     "lecce"),
    _gdp("1040401","Brindisi",        "Lecce",     "brindisi"),

    # ================================================================ TAR — GIUSTIZIA AMMINISTRATIVA
    _tar("T010000","Piemonte",            "Piemonte",          "piemonte"),
    _tar("T010001","Piemonte - sez. II",  "Piemonte",          "piemonte-sez2"),
    _tar("T020000","Valle d'Aosta",       "Valle d'Aosta",     "vda"),
    _tar("T030000","Lombardia",           "Lombardia",         "lombardia"),
    _tar("T030001","Lombardia - Brescia", "Lombardia",         "lombardia-bs"),
    _tar("T040000","Liguria",             "Liguria",           "liguria"),
    _tar("T050000","Trentino-A.A.",       "Trentino-A.A.",     "trento"),
    _tar("T050001","Trentino-A.A. Bolzano","Trentino-A.A.",    "bolzano"),
    _tar("T060000","Veneto",              "Veneto",            "veneto"),
    _tar("T070000","Friuli-V.G.",         "Friuli-V.G.",       "trieste"),
    _tar("T080000","Emilia-Romagna",      "Emilia-Romagna",    "bologna"),
    _tar("T080001","Emilia-Romagna - Parma","Emilia-Romagna",  "parma"),
    _tar("T090000","Toscana",             "Toscana",           "firenze"),
    _tar("T100000","Umbria",              "Umbria",            "perugia"),
    _tar("T110000","Marche",              "Marche",            "ancona"),
    _tar("T120000","Lazio",               "Lazio",             "roma"),
    _tar("T120001","Lazio - sez. I bis",  "Lazio",             "roma-sez1bis"),
    _tar("T120002","Lazio - Latina",      "Lazio",             "latina"),
    _tar("T130000","Abruzzo",             "Abruzzo",           "laquila"),
    _tar("T130001","Abruzzo - Pescara",   "Abruzzo",           "pescara"),
    _tar("T140000","Molise",              "Molise",            "campobasso"),
    _tar("T150000","Campania",            "Campania",          "napoli"),
    _tar("T150001","Campania - Salerno",  "Campania",          "salerno"),
    _tar("T160000","Basilicata",          "Basilicata",        "potenza"),
    _tar("T170000","Calabria",            "Calabria",          "catanzaro"),
    _tar("T170001","Calabria - Reggio",   "Calabria",          "reggiocalabria"),
    _tar("T180000","Sicilia",             "Sicilia",           "palermo"),
    _tar("T180001","Sicilia - Catania",   "Sicilia",           "catania"),
    _tar("T190000","Sardegna",            "Sardegna",          "cagliari"),
    _tar("T200000","Puglia",              "Puglia",            "bari"),
    _tar("T200001","Puglia - Lecce",      "Puglia",            "lecce"),

    # ── CGARS — Consiglio di Giustizia Amministrativa per la Regione Siciliana
    _cgars("CGARS0000", "Consiglio di Giustizia Amministrativa per la Regione Siciliana",
           "Palermo", "cgars"),

    # ── Consiglio di Stato
    {
        "codice": "CDS000000",
        "nome":   "Consiglio di Stato",
        "distretto": "Roma",
        "pec":    "cds@pec.giustizia-amministrativa.it",
        "tipo":   "CDS",
    },

    # ================================================================ CGT — Corti di Giustizia Tributaria di Secondo Grado
    # (D.Lgs. 546/1992 art. 1 — ex Commissioni Tributarie Regionali → CGT con D.Lgs. 130/2022)
    _cgt("CGT010000", "Piemonte",         "Torino",      "piemonte"),
    _cgt("CGT020000", "Valle d'Aosta",    "Aosta",       "vda"),
    _cgt("CGT030000", "Lombardia",        "Milano",      "lombardia"),
    _cgt("CGT040000", "Trentino-A.A.",    "Trento",      "trento"),
    _cgt("CGT040001", "Bolzano",          "Bolzano",     "bolzano"),
    _cgt("CGT050000", "Veneto",           "Venezia",     "veneto"),
    _cgt("CGT060000", "Friuli-V.G.",      "Trieste",     "fvg"),
    _cgt("CGT070000", "Liguria",          "Genova",      "liguria"),
    _cgt("CGT080000", "Emilia-Romagna",   "Bologna",     "emilia-romagna"),
    _cgt("CGT090000", "Toscana",          "Firenze",     "toscana"),
    _cgt("CGT100000", "Umbria",           "Perugia",     "umbria"),
    _cgt("CGT110000", "Marche",           "Ancona",      "marche"),
    _cgt("CGT120000", "Lazio",            "Roma",        "lazio"),
    _cgt("CGT130000", "Abruzzo",          "L'Aquila",    "abruzzo"),
    _cgt("CGT140000", "Molise",           "Campobasso",  "molise"),
    _cgt("CGT150000", "Campania",         "Napoli",      "campania"),
    _cgt("CGT160000", "Puglia",           "Bari",        "puglia"),
    _cgt("CGT170000", "Basilicata",       "Potenza",     "basilicata"),
    _cgt("CGT180000", "Calabria",         "Catanzaro",   "calabria"),
    _cgt("CGT190000", "Sicilia",          "Palermo",     "sicilia"),
    _cgt("CGT200000", "Sardegna",         "Cagliari",    "sardegna"),

    # ================================================================ CPT — Corti di Giustizia Tributaria di Primo Grado
    # (D.Lgs. 546/1992 — ex Commissioni Tributarie Provinciali → CPT con D.Lgs. 130/2022)
    # ── Piemonte ──
    _cpt("CPT010000", "Torino",       "torino",     "Torino"),
    _cpt("CPT010001", "Alessandria",  "alessandria","Torino"),
    _cpt("CPT010002", "Asti",         "asti",       "Torino"),
    _cpt("CPT010003", "Biella",       "biella",     "Torino"),
    _cpt("CPT010004", "Cuneo",        "cuneo",      "Torino"),
    _cpt("CPT010005", "Novara",       "novara",     "Torino"),
    _cpt("CPT010006", "Verbania",     "verbania",   "Torino"),
    _cpt("CPT010007", "Vercelli",     "vercelli",   "Torino"),
    # ── Valle d'Aosta ──
    _cpt("CPT020000", "Aosta",        "aosta",      "Aosta"),
    # ── Lombardia ──
    _cpt("CPT030000", "Milano",       "milano",     "Milano"),
    _cpt("CPT030001", "Bergamo",      "bergamo",    "Milano"),
    _cpt("CPT030002", "Brescia",      "brescia",    "Milano"),
    _cpt("CPT030003", "Como",         "como",       "Milano"),
    _cpt("CPT030004", "Cremona",      "cremona",    "Milano"),
    _cpt("CPT030005", "Lecco",        "lecco",      "Milano"),
    _cpt("CPT030006", "Lodi",         "lodi",       "Milano"),
    _cpt("CPT030007", "Mantova",      "mantova",    "Milano"),
    _cpt("CPT030008", "Monza",        "monza",      "Milano"),
    _cpt("CPT030009", "Pavia",        "pavia",      "Milano"),
    _cpt("CPT030010", "Sondrio",      "sondrio",    "Milano"),
    _cpt("CPT030011", "Varese",       "varese",     "Milano"),
    # ── Trentino-A.A. ──
    _cpt("CPT040000", "Trento",       "trento",     "Trento"),
    _cpt("CPT040001", "Bolzano",      "bolzano",    "Bolzano"),
    # ── Veneto ──
    _cpt("CPT050000", "Venezia",      "venezia",    "Venezia"),
    _cpt("CPT050001", "Belluno",      "belluno",    "Venezia"),
    _cpt("CPT050002", "Padova",       "padova",     "Venezia"),
    _cpt("CPT050003", "Rovigo",       "rovigo",     "Venezia"),
    _cpt("CPT050004", "Treviso",      "treviso",    "Venezia"),
    _cpt("CPT050005", "Verona",       "verona",     "Venezia"),
    _cpt("CPT050006", "Vicenza",      "vicenza",    "Venezia"),
    # ── Friuli-V.G. ──
    _cpt("CPT060000", "Trieste",      "trieste",    "Trieste"),
    _cpt("CPT060001", "Gorizia",      "gorizia",    "Trieste"),
    _cpt("CPT060002", "Pordenone",    "pordenone",  "Trieste"),
    _cpt("CPT060003", "Udine",        "udine",      "Trieste"),
    # ── Liguria ──
    _cpt("CPT070000", "Genova",       "genova",     "Genova"),
    _cpt("CPT070001", "Imperia",      "imperia",    "Genova"),
    _cpt("CPT070002", "La Spezia",    "la-spezia",  "Genova"),
    _cpt("CPT070003", "Savona",       "savona",     "Genova"),
    # ── Emilia-Romagna ──
    _cpt("CPT080000", "Bologna",      "bologna",    "Bologna"),
    _cpt("CPT080001", "Ferrara",      "ferrara",    "Bologna"),
    _cpt("CPT080002", "Forlì",        "forli",      "Bologna"),
    _cpt("CPT080003", "Modena",       "modena",     "Bologna"),
    _cpt("CPT080004", "Parma",        "parma",      "Bologna"),
    _cpt("CPT080005", "Piacenza",     "piacenza",   "Bologna"),
    _cpt("CPT080006", "Ravenna",      "ravenna",    "Bologna"),
    _cpt("CPT080007", "Reggio Emilia","reggio-emilia","Bologna"),
    _cpt("CPT080008", "Rimini",       "rimini",     "Bologna"),
    # ── Toscana ──
    _cpt("CPT090000", "Firenze",      "firenze",    "Firenze"),
    _cpt("CPT090001", "Arezzo",       "arezzo",     "Firenze"),
    _cpt("CPT090002", "Grosseto",     "grosseto",   "Firenze"),
    _cpt("CPT090003", "Livorno",      "livorno",    "Firenze"),
    _cpt("CPT090004", "Lucca",        "lucca",      "Firenze"),
    _cpt("CPT090005", "Massa",        "massa",      "Firenze"),
    _cpt("CPT090006", "Pisa",         "pisa",       "Firenze"),
    _cpt("CPT090007", "Pistoia",      "pistoia",    "Firenze"),
    _cpt("CPT090008", "Prato",        "prato",      "Firenze"),
    _cpt("CPT090009", "Siena",        "siena",      "Firenze"),
    # ── Umbria ──
    _cpt("CPT100000", "Perugia",      "perugia",    "Perugia"),
    _cpt("CPT100001", "Terni",        "terni",      "Perugia"),
    # ── Marche ──
    _cpt("CPT110000", "Ancona",       "ancona",     "Ancona"),
    _cpt("CPT110001", "Ascoli Piceno","ascoli",     "Ancona"),
    _cpt("CPT110002", "Fermo",        "fermo",      "Ancona"),
    _cpt("CPT110003", "Macerata",     "macerata",   "Ancona"),
    _cpt("CPT110004", "Pesaro",       "pesaro",     "Ancona"),
    # ── Lazio ──
    _cpt("CPT120000", "Roma",         "roma",       "Roma"),
    _cpt("CPT120001", "Frosinone",    "frosinone",  "Roma"),
    _cpt("CPT120002", "Latina",       "latina",     "Roma"),
    _cpt("CPT120003", "Rieti",        "rieti",      "Roma"),
    _cpt("CPT120004", "Viterbo",      "viterbo",    "Roma"),
    # ── Abruzzo ──
    _cpt("CPT130000", "L'Aquila",     "laquila",    "L'Aquila"),
    _cpt("CPT130001", "Chieti",       "chieti",     "L'Aquila"),
    _cpt("CPT130002", "Pescara",      "pescara",    "L'Aquila"),
    _cpt("CPT130003", "Teramo",       "teramo",     "L'Aquila"),
    # ── Molise ──
    _cpt("CPT140000", "Campobasso",   "campobasso", "Campobasso"),
    _cpt("CPT140001", "Isernia",      "isernia",    "Campobasso"),
    # ── Campania ──
    _cpt("CPT150000", "Napoli",       "napoli",     "Napoli"),
    _cpt("CPT150001", "Avellino",     "avellino",   "Napoli"),
    _cpt("CPT150002", "Benevento",    "benevento",  "Napoli"),
    _cpt("CPT150003", "Caserta",      "caserta",    "Napoli"),
    _cpt("CPT150004", "Salerno",      "salerno",    "Napoli"),
    # ── Puglia ──
    _cpt("CPT160000", "Bari",         "bari",       "Bari"),
    _cpt("CPT160001", "BAT",          "bat",        "Bari"),
    _cpt("CPT160002", "Brindisi",     "brindisi",   "Bari"),
    _cpt("CPT160003", "Foggia",       "foggia",     "Bari"),
    _cpt("CPT160004", "Lecce",        "lecce",      "Bari"),
    _cpt("CPT160005", "Taranto",      "taranto",    "Bari"),
    # ── Basilicata ──
    _cpt("CPT170000", "Potenza",      "potenza",    "Potenza"),
    _cpt("CPT170001", "Matera",       "matera",     "Potenza"),
    # ── Calabria ──
    _cpt("CPT180000", "Catanzaro",    "catanzaro",  "Catanzaro"),
    _cpt("CPT180001", "Cosenza",      "cosenza",    "Catanzaro"),
    _cpt("CPT180002", "Crotone",      "crotone",    "Catanzaro"),
    _cpt("CPT180003", "Reggio Calabria","reggio-calabria","Catanzaro"),
    _cpt("CPT180004", "Vibo Valentia","vibo",       "Catanzaro"),
    # ── Sicilia ──
    _cpt("CPT190000", "Palermo",      "palermo",    "Palermo"),
    _cpt("CPT190001", "Agrigento",    "agrigento",  "Palermo"),
    _cpt("CPT190002", "Caltanissetta","caltanissetta","Palermo"),
    _cpt("CPT190003", "Catania",      "catania",    "Palermo"),
    _cpt("CPT190004", "Enna",         "enna",       "Palermo"),
    _cpt("CPT190005", "Messina",      "messina",    "Palermo"),
    _cpt("CPT190006", "Ragusa",       "ragusa",     "Palermo"),
    _cpt("CPT190007", "Siracusa",     "siracusa",   "Palermo"),
    _cpt("CPT190008", "Trapani",      "trapani",    "Palermo"),
    # ── Sardegna ──
    _cpt("CPT200000", "Cagliari",     "cagliari",   "Cagliari"),
    _cpt("CPT200001", "Nuoro",        "nuoro",      "Cagliari"),
    _cpt("CPT200002", "Oristano",     "oristano",   "Cagliari"),
    _cpt("CPT200003", "Sassari",      "sassari",    "Cagliari"),
    _cpt("CPT200004", "Sud Sardegna", "sudsardegna","Cagliari"),
]


def _genera_procure() -> list[dict]:
    """
    Genera automaticamente una Procura per ogni Tribunale del bundle.
    Slug estratto dalla PEC del tribunale: tribunale.{slug}@... → procura.{slug}@...
    Codice: ultima cifra del tipo cambia da '1' a '2' (pattern MinGiust).
    """
    procure = []
    # chiavi già presenti nel bundle (evita duplicati con Cassazione ecc.)
    nomi_procure_esistenti: set[str] = set()
    for u in _BUNDLE_RAW:
        if u["tipo"] == "PROCURA":
            nomi_procure_esistenti.add(u["nome"])

    for u in _BUNDLE_RAW:
        if u["tipo"] != "TRIBUNALE":
            continue
        slug = u["pec"].split("tribunale.")[1].split("@")[0]
        citta = u["nome"].replace("Tribunale di ", "")
        nome_procura = f"Procura della Repubblica di {citta}"
        if nome_procura in nomi_procure_esistenti:
            continue
        # Codice: cambia posizione 5 da '1' a '2'
        cod = u["codice"]
        proc_cod = cod[:5] + "2" + cod[6:] if len(cod) == 7 else cod
        procure.append({
            "codice":    proc_cod,
            "nome":      nome_procura,
            "distretto": u["distretto"],
            "pec":       f"procura.{slug}@giustiziapec.it",
            "tipo":      "PROCURA",
        })
    return procure


# Lista completa (bundle + procure auto-generate)
def _build_bundle_completo() -> list[dict]:
    base = list(_BUNDLE_RAW)
    base.extend(_genera_procure())
    return _applica_riferimenti_ministero(base)


# ================================================================ GestoreUfficiGiudiziari

class GestoreUfficiGiudiziari:
    """
    Gestore degli uffici giudiziari con cache JSON persistente e refresh automatico.

    Utilizzo:
        g = GestoreUfficiGiudiziari()
        uffici = g.carica()             # lista dict
        ok, msg = g.aggiorna()          # refresh da remoto
        info = g.stato()                # metadati cache
    """

    def __init__(self, cache_path: str = _CACHE_PATH):
        self.cache_path = Path(cache_path)
        self.ttl = timedelta(days=_TTL_GIORNI)
        self._mem: list[dict] | None = None   # cache in memoria

    # ---------------------------------------------------------------- lettura

    def carica(self) -> list[dict]:
        """Restituisce la lista degli uffici (da cache o bundle).

        Auto-upgrade: se la cache su disco ha meno uffici del bundle interno
        (es. dopo un aggiornamento del codice che aggiunge nuovi uffici), oppure
        se la cache è stata generata da una release precedente con un bundle hash
        diverso dal corrente, la cache viene automaticamente rigenerata dal bundle
        aggiornato.
        """
        if self._mem is not None:
            return self._mem
        da_file = self._da_file()
        bundle = _build_bundle_completo()
        meta = self._leggi_meta() if da_file is not None else {}
        bundle_hash = _uffici_hash(bundle)
        cache_non_allineata_al_bundle = (
            da_file is not None
            and meta.get("bundle_hash") != bundle_hash
        )
        cache_pst_non_allineata = (
            da_file is not None
            and _cache_pst_metadata_non_allineata(da_file, bundle)
        )
        if (
            da_file
            and len(da_file) >= len(bundle)
            and not cache_non_allineata_al_bundle
            and not cache_pst_non_allineata
        ):
            # La cache è completa o più aggiornata del bundle → usala
            self._mem = da_file
        else:
            # Cache assente o meno completa del bundle → rigenera
            if da_file is not None:
                if cache_non_allineata_al_bundle:
                    log.info(
                        "Auto-upgrade cache uffici: bundle_hash cache=%s bundle=%s sorgente=%s → rigenero",
                        meta.get("bundle_hash", "—"),
                        bundle_hash,
                        meta.get("sorgente", "—"),
                    )
                elif cache_pst_non_allineata:
                    log.info(
                        "Auto-upgrade cache uffici: metadati PST/JPW non allineati al bundle ministeriale -> rigenero"
                    )
                else:
                    log.info(
                        "Auto-upgrade cache uffici: %d (cache) < %d (bundle) → rigenero",
                        len(da_file), len(bundle),
                    )
            self._mem = bundle
            self._salva(bundle, sorgente="bundle")
        return self._mem

    def cerca(self, q: str, tipo: str = "", limit: int = 20) -> list[dict]:
        """Ricerca full-text + filtro tipo. Restituisce un numero limitato di risultati."""
        q = q.strip()
        if len(q) < 2:
            return []
        slug_q = _n(q)
        q_up   = q.upper()
        tipo_u = tipo.upper() if tipo else ""
        limit = max(1, min(int(limit or 20), 50))
        out: list[tuple[int, str, str, dict]] = []
        for u in self.carica():
            if tipo_u and u.get("tipo") != tipo_u:
                continue
            campi = (
                u.get("nome", ""),
                u.get("distretto", ""),
                u.get("descrizione_ministero", ""),
                u.get("comune_ministero", ""),
                u.get("tipo_ministero_descrizione", ""),
                u.get("regione_ministero", ""),
                u.get("provincia_ministero", ""),
                u.get("codice_ministero", ""),
            )
            if not any(
                slug_q in _n(str(val)) or q_up in str(val).upper()
                for val in campi
                if val
            ):
                continue
            nome = str(u.get("nome", ""))
            distretto = str(u.get("distretto", ""))
            descrizione = str(u.get("descrizione_ministero", ""))
            comune = str(u.get("comune_ministero", ""))
            tipo_desc = str(u.get("tipo_ministero_descrizione", ""))
            regione = str(u.get("regione_ministero", ""))
            provincia = str(u.get("provincia_ministero", ""))
            codice_ministero = str(u.get("codice_ministero", ""))

            nome_slug = _n(nome)
            distretto_slug = _n(distretto)
            descrizione_slug = _n(descrizione)
            comune_slug = _n(comune)
            tipo_desc_slug = _n(tipo_desc)
            regione_slug = _n(regione)
            provincia_slug = _n(provincia)

            score = 0
            if nome_slug == slug_q:
                score += 1000
            elif nome_slug.startswith(slug_q):
                score += 800
            elif slug_q in nome_slug:
                score += 500

            if distretto_slug == slug_q:
                score += 700
            elif distretto_slug.startswith(slug_q):
                score += 450
            elif slug_q in distretto_slug:
                score += 250

            if comune_slug == slug_q:
                score += 500
            elif comune_slug.startswith(slug_q):
                score += 300
            elif slug_q in comune_slug:
                score += 180

            if slug_q in descrizione_slug:
                score += 120
            if slug_q in tipo_desc_slug:
                score += 90
            if slug_q in regione_slug:
                score += 80
            if slug_q in provincia_slug:
                score += 70
            if codice_ministero and q_up == codice_ministero.upper():
                score += 600

            out.append((score, nome.lower(), distretto.lower(), u))

        out.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [row[3] for row in out[:limit]]

    def stato(self) -> dict:
        """Restituisce metadati sulla cache (usata nell'UI admin)."""
        from collections import Counter

        def _conta_per_tipo(uffici: list[dict]) -> dict:
            c = Counter(u.get("tipo", "?") for u in uffici)
            return dict(sorted(c.items()))

        if self.cache_path.exists():
            meta    = self._leggi_meta()
            uffici  = self._da_file() or []
            return {
                "sorgente":       meta.get("sorgente", "bundle"),
                "aggiornato_il":  meta.get("aggiornato_il", "—"),
                "n_uffici":       len(uffici),
                "per_tipo":       _conta_per_tipo(uffici),
                "cache_path":     str(self.cache_path),
                "ttl_giorni":     _TTL_GIORNI,
                "scaduta":        self._cache_scaduta(),
                "pst_resolver":   meta.get("pst_resolver") or valida_resolver_pst(uffici),
                "fonti_uffici":   fonti_uffici_giudiziari(),
                "policy_pec":     "PEC di deposito e PEC amministrative/protocollo restano distinte per uso e fonte.",
            }
        bundle = _build_bundle_completo()
        return {
            "sorgente":      "bundle",
            "aggiornato_il": "—",
            "n_uffici":      len(bundle),
            "per_tipo":      _conta_per_tipo(bundle),
            "cache_path":    str(self.cache_path),
            "ttl_giorni":    _TTL_GIORNI,
            "scaduta":       True,
            "fonti_uffici":  fonti_uffici_giudiziari(),
            "policy_pec":    "PEC di deposito e PEC amministrative/protocollo restano distinte per uso e fonte.",
        }

    # ---------------------------------------------------------------- aggiornamento

    def aggiorna(self, url: str = "") -> tuple[bool, str]:
        """
        Tenta di aggiornare la cache da sorgente ufficiale o dal bundle interno.

        Ordine di tentativo:
        1. url parametro compatibile, se coincide con l'endpoint PST ufficiale
        2. PCT_UFFICI_URL, solo se coincide con l'endpoint PST ufficiale
        3. PST REST pubblico MinGiust
        4. Ri-salva il bundle interno (sempre riuscito)
        """
        import requests as req

        # Ricarica esplicita dal bundle interno (richiesta dall'UI con url='bundle')
        if url == "bundle":
            bundle = _build_bundle_completo()
            self._salva(bundle, sorgente="bundle")
            self._mem = bundle
            return True, f"Bundle interno ricaricato: {len(bundle)} uffici"

        fonti = [
            ("parametro",   url),
            ("env",         _REMOTO_URL),
            ("pst_public",  _PST_UFFICI),
        ]
        for nome_fonte, endpoint in fonti:
            if not endpoint:
                continue
            endpoint_autorizzato = _endpoint_uffici_autorizzato(endpoint, nome_fonte)
            if not endpoint_autorizzato:
                log.warning(
                    "Aggiornamento uffici da %s ignorato: endpoint non autorizzato.",
                    nome_fonte,
                )
                continue
            try:
                log.info("Aggiornamento uffici da %s (%s)", nome_fonte, endpoint_autorizzato)
                resp = req.get(endpoint_autorizzato, timeout=_PST_TIMEOUT,
                               headers={"Accept": "application/json",
                                        "User-Agent": "PCT-Studio/2.0 (uffici-aggiornamento)"})
                if resp.ok:
                    data = resp.json()
                    uffici = self._normalizza_risposta(data)
                    if uffici:
                        sorgente = f"remoto:{nome_fonte}"
                        bundle = _build_bundle_completo()
                        if _cache_pst_metadata_non_allineata(uffici, bundle):
                            log.warning(
                                "Aggiornamento da %s privo di metadati PST completi: uso bundle ministeriale autoriparato.",
                                nome_fonte,
                            )
                            uffici = bundle
                            sorgente = f"{sorgente}:autoriparato_bundle"
                        self._salva(uffici, sorgente=sorgente)
                        self._mem = uffici
                        n = len(uffici)
                        log.info("Aggiornamento riuscito: %d uffici da %s", n, nome_fonte)
                        return True, f"Aggiornati {n} uffici da {nome_fonte} ({endpoint_autorizzato})"
            except Exception as exc:
                log.warning("Aggiornamento da %s fallito: %s", nome_fonte, exc)

        # Fallback: riscrivi il bundle interno aggiornato
        bundle = _build_bundle_completo()
        self._salva(bundle, sorgente="bundle")
        self._mem = bundle
        n = len(bundle)
        log.info("Aggiornamento dal bundle interno: %d uffici", n)
        return True, f"Aggiornati {n} uffici dal registro interno (sorgente remota non disponibile)"

    # ---------------------------------------------------------------- verifica variazioni

    def verifica_variazioni(self) -> dict:
        """
        Confronta il bundle interno con la sorgente remota (PST) e riporta le variazioni.

        Rileva:
        - PEC modificate (critico: depositi potrebbero non arrivare)
        - Uffici aggiunti nel remoto ma assenti nel bundle
        - Uffici presenti nel bundle ma assenti nel remoto

        Il report viene salvato in <cache_dir>/verifica_variazioni.json e restituito.
        Se la sorgente live non è raggiungibile, il report degrada sul registro interno
        versionato e mantiene separate le fonti PST/IPA senza modificare la cache.
        """
        import requests as req

        report_path = self.cache_path.parent / "verifica_variazioni.json"
        ts = datetime.now().isoformat(timespec="seconds")

        fonti = [
            ("env",        _REMOTO_URL),
            ("pst_public", _PST_UFFICI),
        ]

        remoti: list[dict] = []
        sorgente_usata = "—"
        errore: str | None = None

        for nome_fonte, endpoint in fonti:
            if not endpoint:
                continue
            endpoint_autorizzato = _endpoint_uffici_autorizzato(endpoint, nome_fonte)
            if not endpoint_autorizzato:
                log.warning(
                    "Verifica variazioni: sorgente %s ignorata per endpoint non autorizzato.",
                    nome_fonte,
                )
                errore = "endpoint_non_autorizzato"
                continue
            try:
                log.info("Verifica variazioni: tentativo da %s (%s)", nome_fonte, endpoint_autorizzato)
                resp = req.get(
                    endpoint_autorizzato, timeout=_PST_TIMEOUT,
                    headers={"Accept": "application/json",
                             "User-Agent": "PCT-Studio/2.0 (uffici-verifica)"},
                )
                if resp.ok:
                    remoti = self._normalizza_risposta(resp.json())
                    if remoti:
                        sorgente_usata = nome_fonte
                        log.info("Verifica: %d uffici remoti da %s", len(remoti), nome_fonte)
                        break
            except Exception as exc:
                log.warning("Verifica: sorgente %s non raggiungibile: %s", nome_fonte, exc)
                errore = "sorgente_non_raggiungibile"

        bundle = _build_bundle_completo()

        if not remoti:
            cache = list(self.carica())
            pec_modificate, aggiunti, rimossi = _calcola_variazioni_uffici(bundle, cache)
            n_variazioni = len(pec_modificate) + len(aggiunti) + len(rimossi)
            report: dict = {
                "verificato_il": ts,
                "sorgente": "registro_interno_versionato",
                "modalita": "verifica_locale_governata",
                "bundle_n": len(bundle),
                "remoto_n": len(cache),
                "pec_modificate": pec_modificate,
                "aggiunti": aggiunti,
                "rimossi": rimossi,
                "n_variazioni": n_variazioni,
                "ok": True,
                "errore": None,
                "avviso": (
                    "Le sorgenti live non hanno restituito dati utilizzabili; "
                    "verifica eseguita sul registro interno versionato."
                ),
                "messaggio": (
                    "Verifica completata sul registro interno versionato. "
                    "Le sorgenti live non sono disponibili ora; PST resta fonte primaria "
                    "per deposito e IPA fonte secondaria per protocollo/amministrazione."
                ),
                "fonti": fonti_uffici_giudiziari(errore),
                "policy_pec": "Non mischiare PEC di deposito telematico e PEC amministrative/protocollo.",
            }
            self._salva_report(report_path, report)
            return report

        pec_modificate, aggiunti, rimossi = _calcola_variazioni_uffici(bundle, remoti)

        n_variazioni = len(pec_modificate) + len(aggiunti) + len(rimossi)
        log.info(
            "Verifica completata: %d PEC modificate, %d aggiunti, %d rimossi",
            len(pec_modificate), len(aggiunti), len(rimossi),
        )

        report = {
            "verificato_il":  ts,
            "sorgente":       sorgente_usata,
            "bundle_n":       len(bundle),
            "remoto_n":       len(remoti),
            "pec_modificate": pec_modificate,
            "aggiunti":       aggiunti,
            "rimossi":        rimossi,
            "n_variazioni":   n_variazioni,
            "ok":             True,
            "errore":         None,
            "modalita":       "verifica_live",
            "messaggio":      f"Verifica completata su {sorgente_usata}: {n_variazioni} variazioni rilevate.",
            "fonti":          fonti_uffici_giudiziari(),
            "policy_pec":     "Non mischiare PEC di deposito telematico e PEC amministrative/protocollo.",
        }
        self._salva_report(report_path, report)
        return report

    def carica_report_variazioni(self) -> dict | None:
        """Restituisce l'ultimo report di verifica variazioni, o None se assente."""
        report_path = self.cache_path.parent / "verifica_variazioni.json"
        if not report_path.exists():
            return None
        try:
            return json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Lettura report variazioni fallita: %s", exc)
            return None

    # ---------------------------------------------------------------- privati

    def _salva_report(self, path: Path, report: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Salvataggio report variazioni fallito: %s", exc)

    def _da_file(self) -> list[dict] | None:
        if not self.cache_path.exists():
            return None
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return raw.get("uffici") if isinstance(raw, dict) else raw
        except Exception as exc:
            log.warning("Lettura cache uffici fallita: %s", exc)
            return None

    def _leggi_meta(self) -> dict:
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
        return {}

    def _cache_scaduta(self) -> bool:
        try:
            meta = self._leggi_meta()
            ts = meta.get("aggiornato_il")
            if not ts or ts == "—":
                return True
            dt = datetime.fromisoformat(ts)
            return datetime.now() - dt > self.ttl
        except Exception:
            return True

    def _salva(self, uffici: list[dict], sorgente: str = "bundle") -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            uffici = _applica_riferimenti_ministero(list(uffici))
            payload = {
                "sorgente":      sorgente,
                "aggiornato_il": datetime.now().isoformat(timespec="seconds"),
                "n_uffici":      len(uffici),
                "bundle_hash":   _uffici_hash(_build_bundle_completo()),
                "pst_resolver":  valida_resolver_pst(uffici),
                "uffici":        uffici,
            }
            self.cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Salvataggio cache uffici fallito: %s", exc)

    @staticmethod
    def _normalizza_risposta(data) -> list[dict]:
        """
        Normalizza la risposta JSON remota in formato interno.
        Supporta sia il formato PST sia il formato bundle.
        """
        # Formato bundle interno: {"uffici": [...]}
        if isinstance(data, dict) and "uffici" in data:
            return _applica_riferimenti_ministero(data["uffici"])
        # Lista diretta
        if isinstance(data, list):
            result = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                # Mappa campi PST → interno
                uff = {
                    "codice":    item.get("codice") or item.get("codiceUfficio", ""),
                    "nome":      item.get("nome") or item.get("denominazione", ""),
                    "distretto": item.get("distretto") or item.get("distrettoNome", ""),
                    "pec":       item.get("pec") or item.get("indirizzoElettronico", ""),
                    "tipo":      item.get("tipo") or item.get("tipoUfficio", "TRIBUNALE"),
                }
                if uff["nome"]:
                    result.append(uff)
            return _applica_riferimenti_ministero(result)
        return []


# ================================================================ helper pubblici PST / ministero

def risolvi_ufficio(
    codice_o_nome: str,
    *,
    tipo: str | None = None,
    cache_path: str = _CACHE_PATH,
) -> dict | None:
    """
    Risolve un ufficio dal codice IUSENTRA, dal codice ministeriale o dal nome.
    """
    chiave = (codice_o_nome or "").strip()
    if not chiave:
        return None

    uffici = get_gestore(cache_path).carica()
    tipo_norm = (tipo or "").strip().upper()

    def _ok_tipo(ufficio: dict) -> bool:
        return not tipo_norm or (ufficio.get("tipo") or "").upper() == tipo_norm

    for ufficio in uffici:
        if _ok_tipo(ufficio) and chiave == ufficio.get("codice"):
            return ufficio

    for ufficio in uffici:
        if _ok_tipo(ufficio) and chiave == ufficio.get("codice_ministero"):
            return ufficio

    if "@" in chiave:
        chiave_pec = chiave.casefold()
        for ufficio in uffici:
            if not _ok_tipo(ufficio):
                continue
            pec_values = (
                str(ufficio.get("pec") or "").strip().casefold(),
                str(ufficio.get("pec_ministero") or "").strip().casefold(),
            )
            if chiave_pec in pec_values:
                return ufficio

    chiave_norm = _n(chiave.replace("-", " "))
    for ufficio in uffici:
        if not _ok_tipo(ufficio):
            continue
        campi = (
            ufficio.get("nome", ""),
            ufficio.get("descrizione_ministero", ""),
            ufficio.get("comune_ministero", ""),
        )
        if any(_n(str(val).replace("-", " ")) == chiave_norm for val in campi if val):
            return ufficio

    for ufficio in uffici:
        if not _ok_tipo(ufficio):
            continue
        campi = (
            ufficio.get("nome", ""),
            ufficio.get("descrizione_ministero", ""),
            ufficio.get("comune_ministero", ""),
        )
        if any(chiave_norm in _n(str(val).replace("-", " ")) for val in campi if val):
            return ufficio

    return None


def risolvi_codice_ministero(
    codice_o_nome: str,
    *,
    tipo: str | None = None,
    cache_path: str = _CACHE_PATH,
) -> str:
    """
    Restituisce il codice ministeriale dell'ufficio quando disponibile,
    altrimenti mantiene il codice/nome originale.
    """
    ufficio = risolvi_ufficio(codice_o_nome, tipo=tipo, cache_path=cache_path)
    if not ufficio:
        return (codice_o_nome or "").strip()
    return (ufficio.get("codice_ministero") or ufficio.get("codice") or codice_o_nome).strip()


def risolvi_servizio_pst(
    codice_o_nome: str,
    *,
    preferito: str = "",
    tipo: str | None = None,
    cache_path: str = _CACHE_PATH,
) -> str:
    """
    Restituisce il servizio JPW più adatto per l'ufficio selezionato.
    """
    ufficio = risolvi_ufficio(codice_o_nome, tipo=tipo, cache_path=cache_path)
    if not ufficio:
        return ""

    servizi = [
        _normalizza_servizio_pst_name(s)
        for s in (ufficio.get("servizi_ministero") or [])
        if str(s).strip()
    ]
    jpw = [servizio for servizio in servizi if servizio.startswith("JPW_")]

    preferenze: list[str] = []
    if preferito:
        preferenze.append(_normalizza_servizio_pst_name(preferito))
    env_pref = _normalizza_servizio_pst_name(os.getenv("PCT_PST_SERVIZIO_DEFAULT", ""))
    if env_pref:
        preferenze.append(env_pref)
    servizio_ufficio = _normalizza_servizio_pst_name(ufficio.get("servizio_pst_predefinito") or "")
    if servizio_ufficio:
        preferenze.append(servizio_ufficio)
    preferenze.extend(_PST_SERVIZI_DEFAULT)

    if jpw:
        for candidato in preferenze:
            if candidato and candidato in jpw:
                return candidato
        return jpw[0]

    if ufficio.get("tipo") == "CORTE_CASSAZIONE":
        return "JPW_CASSCI"
    return next((servizio for servizio in preferenze if servizio), "")


def _normalizza_base_pst(base_url: str) -> tuple[str, bool]:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return "", False
    if base.startswith(_PST_LEGACY_BASE):
        return base, False
    if "/pda/pycons/" in base:
        parsed = urlparse(base)
        path_parts = [part for part in parsed.path.rstrip("/").split("/") if part]
        if path_parts:
            path_parts[-1] = _normalizza_servizio_pst_name(path_parts[-1])
            normalized_path = "/" + "/".join(path_parts)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}{normalized_path}", True
            return normalized_path, True
        return base, True
    parsed = urlparse(base)
    path = parsed.path.rstrip("/")
    if parsed.scheme and parsed.netloc and path not in ("", "/"):
        return base, True
    return base, False


def risolvi_base_pst(
    codice_o_nome: str,
    *,
    base_url: str = "",
    preferito: str = "",
    tipo: str | None = None,
    cache_path: str = _CACHE_PATH,
) -> str:
    """
    Costruisce il base URL PST per un ufficio usando i metadati GL/JPW del ministero.

    Supporta sia:
      - URL completi già configurati in `PCT_PST_BASE_URL`
      - root proxy (`https://ext.processotelematico.giustizia.it`)
      - fallback automatico al proxy `ext.processotelematico.giustizia.it`
    """
    candidate_base = base_url or os.getenv("PCT_PST_BASE_URL", "")
    normalized_base, is_full = _normalizza_base_pst(candidate_base)
    if is_full:
        return normalized_base

    ufficio = risolvi_ufficio(codice_o_nome, tipo=tipo, cache_path=cache_path)
    codice_gl = (ufficio or {}).get("codice_gl", "").strip()
    servizio = risolvi_servizio_pst(
        codice_o_nome,
        preferito=preferito,
        tipo=tipo,
        cache_path=cache_path,
    )

    if not codice_gl or not servizio:
        raise ValueError(
            "Impossibile determinare codice GL/servizio PST dell'ufficio selezionato. "
            "Verificare il registro uffici o configurare PCT_PST_BASE_URL completo."
        )

    root = normalized_base
    if not root or root.startswith(_PST_LEGACY_BASE):
        root = (os.getenv("PCT_PST_PROXY_ROOT", "") or _PST_PROXY_SH_URL).strip().rstrip("/")
    return f"{root}/pda/pycons/{codice_gl}/{servizio}"


def valida_resolver_pst(uffici: list[dict] | None = None) -> dict:
    """Controlla che tutti gli uffici JPW abbiano resolver PST completo."""
    rows = uffici if uffici is not None else _build_bundle_completo()
    problemi: list[dict] = []
    per_servizio: dict[str, int] = {}
    n_jpw = 0

    for ufficio in rows:
        servizi = sorted(_servizi_jpw(ufficio))
        if not servizi:
            continue
        n_jpw += 1
        codice = str(ufficio.get("codice") or "").strip()
        nome = str(ufficio.get("nome") or "").strip()
        codice_ministero = str(ufficio.get("codice_ministero") or "").strip()
        codice_gl = str(ufficio.get("codice_gl") or "").strip()
        preferito = _normalizza_servizio_pst_name(ufficio.get("servizio_pst_predefinito") or "")
        servizio = preferito if preferito in servizi else servizi[0]
        per_servizio[servizio] = per_servizio.get(servizio, 0) + 1

        issue: list[str] = []
        if not codice_ministero:
            issue.append("codice_ministero mancante")
        if not codice_gl:
            issue.append("codice_gl mancante")
        if not servizio:
            issue.append("servizio JPW mancante")
        if servizio and servizio not in _PST_QBUILDER_NAMESPACES:
            issue.append(f"namespace qbuilder non mappato per {servizio}")
        if issue:
            problemi.append(
                {
                    "codice": codice,
                    "nome": nome,
                    "servizio": servizio,
                    "problemi": issue,
                }
            )

    return {
        "ok": not problemi,
        "n_uffici_jpw": n_jpw,
        "per_servizio": dict(sorted(per_servizio.items())),
        "n_problemi": len(problemi),
        "problemi": problemi[:50],
    }


# ================================================================ singleton

_gestore: GestoreUfficiGiudiziari | None = None


def get_gestore(cache_path: str = _CACHE_PATH) -> GestoreUfficiGiudiziari:
    """Restituisce il singleton del gestore."""
    global _gestore
    if _gestore is None or str(_gestore.cache_path) != cache_path:
        _gestore = GestoreUfficiGiudiziari(cache_path)
    return _gestore
