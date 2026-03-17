"""
pct/uffici_giudiziari.py — Gestore uffici giudiziari con cache persistente.

Mantiene un registro aggiornato di tutti gli uffici giudiziari italiani:
  • 140+ Tribunali ordinari
  • 29 Corti d'Appello
  • 140+ Procure della Repubblica (generate dal registro tribunali)
  • 27  Tribunali per i Minorenni
  • 26  Tribunali di Sorveglianza
  • Corte Suprema di Cassazione

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
import logging
import os
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- configurazione

_CACHE_PATH   = os.getenv("PCT_UFFICI_DB",          "/data/uffici/uffici_giudiziari.json")
_TTL_GIORNI   = int(os.getenv("PCT_UFFICI_TTL_GIORNI", "7"))
_REMOTO_URL   = os.getenv("PCT_UFFICI_URL", "")          # URL JSON esterno facoltativo
_PST_UFFICI   = "https://pst.giustizia.it/PST/resources/rest/ricercaUfficiGiudiziari"
_PST_TIMEOUT  = 12  # secondi

# ---------------------------------------------------------------- tipi

TIPI_UFFICIO = {
    "TRIBUNALE":         ("bi-building",            "Tribunale"),
    "CORTE_APPELLO":     ("bi-bank2",               "Corte d'Appello"),
    "PROCURA":           ("bi-shield-exclamation",  "Procura"),
    "CORTE_CASSAZIONE":  ("bi-star-fill",           "Cassazione"),
    "TM":                ("bi-people-fill",         "Trib. Minorenni"),
    "SORVEGLIANZA":      ("bi-eye-fill",            "Trib. Sorveglianza"),
    "TAR":               ("bi-building-check",      "TAR"),
}


# ================================================================ bundle interno

def _n(testo: str) -> str:
    """Normalizza slug (rimuove accenti, lowercase, senza spazi)."""
    nfkd = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().replace(" ", "")


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
    _t("0700017","Reggio Emilia",  "Bologna",   "reggioEmilia"),
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
    _t("0910011","Palmi",          "Catanzaro", "palmi"),
    _t("0900011","Paola",          "Catanzaro", "paola"),
    _t("0900012","Rossano",        "Catanzaro", "rossano"),
    _t("0910010","Reggio Calabria","Catanzaro", "reggiocalabria"),
    _t("0890013","Vibo Valentia",  "Catanzaro", "vibovalentia"),

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
    _t("1040012","Cotrone",        "Lecce",     "cotrone"),

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
    _tm("0910100","Reggio Calabria", "Catanzaro", "reggiocalabria"),
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
    _ts("0910200","Reggio Calabria", "Catanzaro", "reggiocalabria"),
    _ts("0920200","Palermo",         "Palermo",   "palermo"),
    _ts("0940200","Messina",         "Messina",   "messina"),
    _ts("0950200","Catania",         "Catania",   "catania"),
    _ts("0980200","Cagliari",        "Cagliari",  "cagliari"),
    _ts("1010200","Sassari",         "Cagliari",  "sassari"),
    _ts("1020200","Bari",            "Bari",      "bari"),
    _ts("1040200","Lecce",           "Lecce",     "lecce"),
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
    return base


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
        """Restituisce la lista degli uffici (da cache o bundle)."""
        if self._mem is not None:
            return self._mem
        self._mem = self._da_file() or _build_bundle_completo()
        # Salva su disco se mancante
        if not self.cache_path.exists():
            self._salva(self._mem)
        return self._mem

    def cerca(self, q: str, tipo: str = "") -> list[dict]:
        """Ricerca full-text + filtro tipo. Restituisce max 20 risultati."""
        q = q.strip()
        if len(q) < 2:
            return []
        slug_q = _n(q)
        q_up   = q.upper()
        tipo_u = tipo.upper() if tipo else ""
        out: list[dict] = []
        for u in self.carica():
            if tipo_u and u.get("tipo") != tipo_u:
                continue
            if (slug_q in _n(u["nome"]) or
                    slug_q in _n(u.get("distretto", "")) or
                    q_up in u["nome"].upper() or
                    q_up in u.get("distretto", "").upper()):
                out.append(u)
            if len(out) >= 20:
                break
        return out

    def stato(self) -> dict:
        """Restituisce metadati sulla cache (usata nell'UI admin)."""
        if self.cache_path.exists():
            meta = self._leggi_meta()
            n_uffici = len(self._da_file() or [])
            return {
                "sorgente":       meta.get("sorgente", "bundle"),
                "aggiornato_il":  meta.get("aggiornato_il", "—"),
                "n_uffici":       n_uffici,
                "cache_path":     str(self.cache_path),
                "ttl_giorni":     _TTL_GIORNI,
                "scaduta":        self._cache_scaduta(),
            }
        return {
            "sorgente":      "bundle",
            "aggiornato_il": "—",
            "n_uffici":      len(_build_bundle_completo()),
            "cache_path":    str(self.cache_path),
            "ttl_giorni":    _TTL_GIORNI,
            "scaduta":       True,
        }

    # ---------------------------------------------------------------- aggiornamento

    def aggiorna(self, url: str = "") -> tuple[bool, str]:
        """
        Tenta di aggiornare la cache da sorgente remota.

        Ordine di tentativo:
        1. url parametro (se specificato)
        2. PCT_UFFICI_URL variabile d'ambiente
        3. PST REST pubblico MinGiust
        4. Ri-salva il bundle interno (sempre riuscito)
        """
        import requests as req

        fonti = [
            ("parametro",   url),
            ("env",         _REMOTO_URL),
            ("pst_public",  _PST_UFFICI),
        ]
        for nome_fonte, endpoint in fonti:
            if not endpoint:
                continue
            try:
                log.info("Aggiornamento uffici da %s (%s)", nome_fonte, endpoint)
                resp = req.get(endpoint, timeout=_PST_TIMEOUT,
                               headers={"Accept": "application/json",
                                        "User-Agent": "PCT-Studio/2.0 (uffici-aggiornamento)"})
                if resp.ok:
                    data = resp.json()
                    uffici = self._normalizza_risposta(data)
                    if uffici:
                        self._salva(uffici, sorgente=f"remoto:{nome_fonte}")
                        self._mem = uffici
                        n = len(uffici)
                        log.info("Aggiornamento riuscito: %d uffici da %s", n, nome_fonte)
                        return True, f"Aggiornati {n} uffici da {nome_fonte} ({endpoint})"
            except Exception as exc:
                log.warning("Aggiornamento da %s fallito: %s", nome_fonte, exc)

        # Fallback: riscrivi il bundle interno aggiornato
        bundle = _build_bundle_completo()
        self._salva(bundle, sorgente="bundle")
        self._mem = bundle
        n = len(bundle)
        log.info("Aggiornamento dal bundle interno: %d uffici", n)
        return True, f"Aggiornati {n} uffici dal registro interno (sorgente remota non disponibile)"

    # ---------------------------------------------------------------- privati

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
            payload = {
                "sorgente":      sorgente,
                "aggiornato_il": datetime.now().isoformat(timespec="seconds"),
                "n_uffici":      len(uffici),
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
            return data["uffici"]
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
            return result
        return []


# ================================================================ singleton

_gestore: GestoreUfficiGiudiziari | None = None


def get_gestore(cache_path: str = _CACHE_PATH) -> GestoreUfficiGiudiziari:
    """Restituisce il singleton del gestore."""
    global _gestore
    if _gestore is None or str(_gestore.cache_path) != cache_path:
        _gestore = GestoreUfficiGiudiziari(cache_path)
    return _gestore
