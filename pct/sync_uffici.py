"""
pct/sync_uffici.py — Sincronizzazione automatica uffici giudiziari da fonti ufficiali.

Eseguito ogni giorno alle 03:30 dallo scheduler (pct/scheduler.py).
Integra e aggiorna il bundle interno attingendo da quattro fonti ufficiali:

  1. giustizia-amministrativa.it  → TAR, Consiglio di Stato, CGARS
  2. giustizia.it / PST            → Tribunali, Corti d'Appello, Procure
  3. giustiziatributaria.gov.it   → CPT, CGT (Corti di Giustizia Tributaria)
  4. indicepa.gov.it (IPA API)    → PEC aggiornate per tutti gli uffici

Strategia di merge:
  - Il bundle interno è il "ground truth" iniziale.
  - Le fonti remote arricchiscono/correggono la cache.
  - Variazioni critiche (PEC cambiate) vengono loggate come WARNING.
  - Se una fonte fallisce, si usa il dato precedente (degradazione controllata).

Configurazione tramite env vars:
  PCT_SYNC_TIMEOUT         — timeout HTTP per singola richiesta (default 15s)
  PCT_SYNC_IPA_ENABLED     — abilita enrichment PEC da IPA (default "1")
  PCT_SYNC_GA_ENABLED      — abilita sync da giustizia-amministrativa.it (default "1")
  PCT_SYNC_GT_ENABLED      — abilita sync da giustiziatributaria.gov.it (default "1")
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger("pct.sync_uffici")

# ---------------------------------------------------------------- configurazione

_TIMEOUT       = int(os.getenv("PCT_SYNC_TIMEOUT", "15"))
_IPA_ENABLED   = os.getenv("PCT_SYNC_IPA_ENABLED", "1") not in ("0", "false", "no")
_GA_ENABLED    = os.getenv("PCT_SYNC_GA_ENABLED", "1") not in ("0", "false", "no")
_GT_ENABLED    = os.getenv("PCT_SYNC_GT_ENABLED", "1") not in ("0", "false", "no")

# Endpoint ufficiali
_GA_SEDI_URL   = "https://www.giustizia-amministrativa.it/web/guest/sedi-dei-tar"
_GA_API_URL    = "https://www.giustizia-amministrativa.it/web/guest/-/servizi-tar"
_GT_SEDI_URL   = "https://www.giustiziatributaria.gov.it/sezioni/corti-tributarie"
_PST_URL       = "https://pst.giustizia.it/PST/resources/rest/ricercaUfficiGiudiziari"
_IPA_API_URL   = "https://indicepa.gov.it/ipa-dati/api/v1/enti"

# Parole chiave IPA per categoria uffici giudiziari
_IPA_CODICI_CATEGORIA = ["GIUSTIZIA", "AM_GIUSTIZIA"]

# ---------------------------------------------------------------- helpers

def _slug(s: str) -> str:
    """Normalizza stringa per confronto: minuscolo, no accenti, no punteggiatura."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def _get(url: str, params: Optional[dict] = None, **kw) -> Any:
    """HTTP GET con timeout configurabile. Lancia eccezione se fallisce."""
    try:
        import requests
        resp = requests.get(
            url,
            params=params,
            timeout=_TIMEOUT,
            headers={"User-Agent": "IUSENTRA-StudioLegale/2.41 (uffici-sync; +https://github.com/hacs)"},
            **kw,
        )
        resp.raise_for_status()
        return resp
    except Exception as exc:
        raise ConnectionError(f"GET {url}: {exc}") from exc


# ================================================================ Fonte 1: PST (MinGiust)

def sync_da_pst() -> List[Dict]:
    """
    Recupera uffici ordinari (Tribunali, Corti d'Appello, Procure) dal PST MinGiust.
    Endpoint REST pubblico — restituisce JSON con lista uffici.
    Restituisce lista di dict nel formato bundle interno oppure [] se il servizio non risponde.
    """
    try:
        resp = _get(_PST_URL)
        data = resp.json()
        from pct.uffici_giudiziari import GestoreUfficiGiudiziari
        uffici = GestoreUfficiGiudiziari._normalizza_risposta(data)
        log.info("[sync_pst] %d uffici da PST MinGiust", len(uffici))
        return uffici
    except Exception as exc:
        log.warning("[sync_pst] Fallito: %s", exc)
        return []


# ================================================================ Fonte 2: Giustizia Amministrativa

def sync_da_giustizia_amm() -> List[Dict]:
    """
    Recupera TAR, Consiglio di Stato e CGARS dal sito giustizia-amministrativa.it.

    Il sito pubblica le sedi in una pagina HTML strutturata. Effettua scraping
    leggero della lista sedi cercando i pattern 'TAR', 'Consiglio di Stato', 'CGARS'.
    In caso di errore o cambio struttura HTML, restituisce [].
    """
    if not _GA_ENABLED:
        return []
    try:
        resp = _get(_GA_SEDI_URL)
        html = resp.text
        uffici = _parse_ga_html(html)
        log.info("[sync_ga] %d uffici da giustizia-amministrativa.it", len(uffici))
        return uffici
    except Exception as exc:
        log.warning("[sync_ga] Fallito (HTML scraping): %s", exc)
        return []


def _parse_ga_html(html: str) -> List[Dict]:
    """
    Estrae sedi TAR/CDS/CGARS dall'HTML di giustizia-amministrativa.it.
    Pattern atteso: elementi con testo contenente 'TAR', 'Consiglio di Stato', 'CGARS'
    e un indirizzo email PEC (pattern @pec.giustizia-amministrativa.it).
    """
    from html.parser import HTMLParser

    class _SediParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.uffici: List[Dict] = []
            self._buf = ""
            self._capture = False

        def handle_starttag(self, tag, attrs):
            if tag in ("td", "li", "div", "p", "h3", "h4"):
                self._capture = True
                self._buf = ""

        def handle_endtag(self, tag):
            if tag in ("td", "li", "div", "p", "h3", "h4"):
                self._processa(self._buf.strip())
                self._capture = False
                self._buf = ""

        def handle_data(self, data):
            if self._capture:
                self._buf += data

        def _processa(self, testo: str):
            if not testo:
                return
            tipo = None
            if re.search(r"\bCGARS\b", testo, re.I):
                tipo = "CGARS"
            elif re.search(r"\bConsiglio\s+di\s+Stato\b", testo, re.I):
                tipo = "CDS"
            elif re.search(r"\bTAR\b", testo, re.I):
                tipo = "TAR"
            if not tipo:
                return
            # Cerca PEC nel testo
            pec_match = re.search(r"[\w.\-]+@pec\.giustizia-amministrativa\.it", testo, re.I)
            pec = pec_match.group(0).lower() if pec_match else ""
            nome = re.sub(r"\s+", " ", testo.split("\n")[0].strip())[:80]
            if nome and (tipo != "TAR" or "TAR" in nome.upper()):
                self.uffici.append({
                    "nome": nome,
                    "tipo": tipo,
                    "pec":  pec,
                    "distretto": _estrai_distretto_ga(nome),
                    "codice": "",  # non assegnato — sarà matched per nome
                })

    parser = _SediParser()
    parser.feed(html)

    # Deduplicazione per nome
    visti: set = set()
    result = []
    for u in parser.uffici:
        k = _slug(u["nome"])
        if k not in visti:
            visti.add(k)
            result.append(u)
    return result


def _estrai_distretto_ga(nome: str) -> str:
    """Estrae il distretto (regione/città) dal nome di un ufficio GA."""
    # TAR Lombardia - Brescia → "Lombardia"
    m = re.search(r"TAR\s+([\w\s\-']+?)(?:\s+-\s+|$)", nome, re.I)
    if m:
        return m.group(1).strip()
    if "Consiglio di Stato" in nome:
        return "Roma"
    if "CGARS" in nome:
        return "Palermo"
    return ""


# ================================================================ Fonte 3: Giustizia Tributaria

def sync_da_giustizia_tributaria() -> List[Dict]:
    """
    Recupera CPT/CGT dal portale giustiziatributaria.gov.it (MEF).

    Il portale pubblica l'elenco delle corti in una pagina HTML strutturata.
    Cerca pattern 'Corte di Giustizia Tributaria di Primo/Secondo Grado'.
    Restituisce [] in caso di errore o cambio struttura.
    """
    if not _GT_ENABLED:
        return []
    try:
        resp = _get(_GT_SEDI_URL)
        html = resp.text
        uffici = _parse_gt_html(html)
        log.info("[sync_gt] %d uffici da giustiziatributaria.gov.it", len(uffici))
        return uffici
    except Exception as exc:
        log.warning("[sync_gt] Fallito (HTML scraping): %s", exc)
        return []


def _parse_gt_html(html: str) -> List[Dict]:
    """
    Estrae CPT/CGT dall'HTML di giustiziatributaria.gov.it.
    Pattern: testi contenenti 'Corte di Giustizia Tributaria di Primo/Secondo Grado di {città}'.
    """
    uffici = []
    # Cerca istanze del pattern nel testo HTML grezzo (più robusto dello scraping DOM)
    pattern = re.compile(
        r"Corte\s+di\s+Giustizia\s+Tributaria\s+di\s+(Primo|Secondo)\s+Grado\s+di\s+([\w\s']+?)(?=<|,|\.|\n|&)",
        re.I,
    )
    visti: set = set()
    for m in pattern.finditer(html):
        grado = m.group(1).capitalize()   # "Primo" o "Secondo"
        citta = m.group(2).strip().title()
        tipo  = "CPT" if grado == "Primo" else "CGT"
        nome  = f"{'CPT' if tipo == 'CPT' else 'CGT'} {citta}"
        k     = _slug(nome)
        if k in visti:
            continue
        visti.add(k)
        uffici.append({
            "nome":      nome,
            "tipo":      tipo,
            "distretto": citta,
            "pec":       f"{tipo.lower()}.{_slug(citta)}@pec.mef.gov.it",
            "codice":    "",  # matched per nome
        })

    log.debug("[sync_gt] Trovate %d corti tributarie nell'HTML", len(uffici))
    return uffici


# ================================================================ Fonte 4: IPA (PEC)

def arricchisci_pec_da_ipa(uffici: List[Dict]) -> tuple[List[Dict], int]:
    """
    Aggiorna gli indirizzi PEC degli uffici interrogando l'IPA (Indice PA).

    L'IPA REST API restituisce gli enti pubblici con i relativi indirizzi PEC.
    Cerca corrispondenze per nome (full-text fuzzy) e aggiorna il campo 'pec'
    se l'IPA restituisce un indirizzo diverso da quello nel bundle.

    Restituisce (lista_aggiornata, n_pec_aggiornate).
    Documeentazione API IPA: https://indicepa.gov.it/ipa-dati/opendata/
    """
    if not _IPA_ENABLED:
        return uffici, 0

    aggiornati = 0
    # Recupera enti di tipo giustizia dall'IPA (paginato)
    ipa_enti: Dict[str, str] = {}  # slug_nome → pec

    for categoria in _IPA_CODICI_CATEGORIA:
        page = 0
        while True:
            try:
                resp = _get(
                    _IPA_API_URL,
                    params={
                        "codiceCategoria": categoria,
                        "page": page,
                        "size": 100,
                    },
                )
                data = resp.json()
                # Struttura IPA: {"data": [{"denominazione": "...", "pecPrimaria": "...", ...}]}
                items = data.get("data") or data.get("items") or (data if isinstance(data, list) else [])
                if not items:
                    break
                for ente in items:
                    nome_ente = ente.get("denominazione") or ente.get("nome") or ""
                    pec_ente  = (
                        ente.get("pecPrimaria") or
                        ente.get("pec") or
                        ente.get("indPec") or ""
                    ).strip().lower()
                    if nome_ente and pec_ente:
                        ipa_enti[_slug(nome_ente)] = pec_ente
                page += 1
                if len(items) < 100:
                    break
            except Exception as exc:
                log.warning("[sync_ipa] Pagina %d categoria %s fallita: %s", page, categoria, exc)
                break

    if not ipa_enti:
        log.warning("[sync_ipa] Nessun ente IPA recuperato.")
        return uffici, 0

    log.info("[sync_ipa] %d enti IPA caricati", len(ipa_enti))

    # Match: cerca ogni ufficio nell'indice IPA per slug nome
    for u in uffici:
        slug_u = _slug(u.get("nome", ""))
        if slug_u in ipa_enti:
            nuova_pec = ipa_enti[slug_u]
            vecchia_pec = (u.get("pec") or "").strip().lower()
            if nuova_pec and nuova_pec != vecchia_pec:
                log.warning(
                    "[sync_ipa] PEC aggiornata %s: %s → %s",
                    u.get("nome"), vecchia_pec or "(vuota)", nuova_pec,
                )
                u["pec"] = nuova_pec
                aggiornati += 1

    return uffici, aggiornati


# ================================================================ Merge e sync completo

def _merge_uffici(base: List[Dict], aggiornamenti: List[Dict]) -> tuple[List[Dict], int, int]:
    """
    Fonde due liste di uffici.

    Strategia:
    - Matching primario per codice (se presente e non vuoto).
    - Matching secondario per slug del nome.
    - Se trovata corrispondenza: aggiorna pec (se diversa e non vuota).
    - Se non trovata corrispondenza: aggiunge come nuovo ufficio.

    Restituisce (lista_merged, n_aggiornati, n_aggiunti).
    """
    base_per_cod:  Dict[str, Dict] = {u["codice"]: u for u in base if u.get("codice")}
    base_per_nome: Dict[str, Dict] = {_slug(u["nome"]): u for u in base}

    n_aggiornati = 0
    n_aggiunti   = 0

    for agg in aggiornamenti:
        codice = (agg.get("codice") or "").strip()
        nome   = (agg.get("nome") or "").strip()
        pec    = (agg.get("pec") or "").strip().lower()
        tipo   = agg.get("tipo", "")

        # Cerca corrispondenza
        esistente = None
        if codice and codice in base_per_cod:
            esistente = base_per_cod[codice]
        elif nome:
            slug_n = _slug(nome)
            if slug_n in base_per_nome:
                esistente = base_per_nome[slug_n]

        if esistente:
            # Aggiorna PEC se cambiata
            pec_base = (esistente.get("pec") or "").strip().lower()
            if pec and pec != pec_base:
                log.info(
                    "[merge] PEC aggiornata %s: %s → %s",
                    esistente.get("nome"), pec_base or "(vuota)", pec,
                )
                esistente["pec"] = pec
                n_aggiornati += 1
        else:
            # Nuovo ufficio
            if nome and tipo:
                nuovo = {
                    "codice":    codice or f"_sync_{_slug(nome)}",
                    "nome":      nome,
                    "distretto": agg.get("distretto", ""),
                    "pec":       pec,
                    "tipo":      tipo,
                }
                base.append(nuovo)
                base_per_cod[nuovo["codice"]] = nuovo
                base_per_nome[_slug(nome)] = nuovo
                log.info("[merge] Nuovo ufficio aggiunto: %s (%s)", nome, tipo)
                n_aggiunti += 1

    return base, n_aggiornati, n_aggiunti


def esegui_sync_completo(
    cache_path: str,
    forza: bool = False,
) -> Dict:
    """
    Esegue la sincronizzazione completa degli uffici giudiziari da tutte le fonti.

    1. Carica il bundle corrente (da cache o bundle interno).
    2. Recupera aggiornamenti da PST MinGiust (Tribunali/Corti/Procure).
    3. Recupera aggiornamenti da giustizia-amministrativa.it (TAR/CDS/CGARS).
    4. Recupera aggiornamenti da giustiziatributaria.gov.it (CPT/CGT).
    5. Arricchisce PEC dall'IPA.
    6. Salva la cache aggiornata.

    Restituisce un dict con il report di sync.
    """
    from pct.uffici_giudiziari import get_gestore

    ts = datetime.now().isoformat(timespec="seconds")
    report: Dict = {
        "sync_il":       ts,
        "fonti":         {},
        "n_pec_aggiornate": 0,
        "n_nuovi":       0,
        "n_totale_pre":  0,
        "n_totale_post": 0,
        "ok":            True,
        "errore":        None,
    }

    try:
        gestore = get_gestore(cache_path)
        uffici  = list(gestore.carica())   # copia modificabile
        report["n_totale_pre"] = len(uffici)

        # ---- PST ----
        pst_uffici = sync_da_pst()
        if pst_uffici:
            uffici, n_agg, n_new = _merge_uffici(uffici, pst_uffici)
            report["fonti"]["pst"] = {"ok": True, "n_remoti": len(pst_uffici),
                                       "n_aggiornati": n_agg, "n_nuovi": n_new}
            report["n_pec_aggiornate"] += n_agg
            report["n_nuovi"] += n_new
        else:
            report["fonti"]["pst"] = {"ok": False, "motivo": "sorgente non disponibile"}

        # ---- Giustizia Amministrativa ----
        ga_uffici = sync_da_giustizia_amm()
        if ga_uffici:
            uffici, n_agg, n_new = _merge_uffici(uffici, ga_uffici)
            report["fonti"]["giustizia_amm"] = {"ok": True, "n_remoti": len(ga_uffici),
                                                  "n_aggiornati": n_agg, "n_nuovi": n_new}
            report["n_pec_aggiornate"] += n_agg
            report["n_nuovi"] += n_new
        else:
            report["fonti"]["giustizia_amm"] = {"ok": False, "motivo": "sorgente non disponibile"}

        # ---- Giustizia Tributaria ----
        gt_uffici = sync_da_giustizia_tributaria()
        if gt_uffici:
            uffici, n_agg, n_new = _merge_uffici(uffici, gt_uffici)
            report["fonti"]["giustizia_tributaria"] = {"ok": True, "n_remoti": len(gt_uffici),
                                                        "n_aggiornati": n_agg, "n_nuovi": n_new}
            report["n_pec_aggiornate"] += n_agg
            report["n_nuovi"] += n_new
        else:
            report["fonti"]["giustizia_tributaria"] = {"ok": False, "motivo": "sorgente non disponibile"}

        # ---- IPA (arricchimento PEC) ----
        uffici, n_ipa = arricchisci_pec_da_ipa(uffici)
        report["fonti"]["ipa"] = {"ok": True, "n_pec_aggiornate": n_ipa}
        report["n_pec_aggiornate"] += n_ipa

        # ---- Salva ----
        report["n_totale_post"] = len(uffici)
        gestore._salva(uffici, sorgente="sync_multi")
        gestore._mem = uffici   # invalida cache in memoria

        log.info(
            "[sync] Completato: %d uffici totali, %d PEC aggiornate, %d nuovi",
            len(uffici), report["n_pec_aggiornate"], report["n_nuovi"],
        )

    except Exception as exc:
        log.error("[sync] Sync fallito: %s", exc, exc_info=True)
        report["ok"]    = False
        report["errore"] = str(exc)

    # Salva report accanto alla cache
    try:
        from pathlib import Path
        rp = Path(cache_path).parent / "sync_report.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("[sync] Salvataggio report fallito: %s", exc)

    return report


def carica_ultimo_report(cache_path: str) -> Optional[Dict]:
    """Restituisce l'ultimo report di sync, o None se non disponibile."""
    from pathlib import Path
    rp = Path(cache_path).parent / "sync_report.json"
    if not rp.exists():
        return None
    try:
        return json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        return None
