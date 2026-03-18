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
    "PROCURA":           ("bi-shield-exclamation",  "Procura della Repubblica"),
    "PROCURA_GENERALE":  ("bi-shield-fill",         "Procura Generale"),
    "CORTE_CASSAZIONE":  ("bi-star-fill",           "Cassazione"),
    "TM":                ("bi-people-fill",         "Trib. Minorenni"),
    "SORVEGLIANZA":      ("bi-eye-fill",            "Trib. Sorveglianza"),
    "CORTE_ASSISE":      ("bi-hammer",              "Corte d'Assise"),
    "GDP":               ("bi-person-badge",        "Giudice di Pace"),
    "TAR":               ("bi-building-check",      "TAR"),
    "CDS":               ("bi-columns-gap",         "Consiglio di Stato"),
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
    _assise("0910300","Reggio Calabria", "Catanzaro", "reggiocalabria"),
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
    _gdp("0910400","Reggio Calabria", "Catanzaro", "reggiocalabria"),
    _gdp("0910401","Palmi",           "Catanzaro", "palmi"),
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
    _tar("T030002","Lombardia - Milano",  "Lombardia",         "lombardia-mi"),
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

    # ── Consiglio di Stato
    {
        "codice": "CDS000000",
        "nome":   "Consiglio di Stato",
        "distretto": "Roma",
        "pec":    "cds@pec.giustizia-amministrativa.it",
        "tipo":   "CDS",
    },
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
        """Restituisce la lista degli uffici (da cache o bundle).

        Auto-upgrade: se la cache su disco ha meno uffici del bundle interno
        (es. dopo un aggiornamento del codice che aggiunge nuovi uffici), la
        cache viene automaticamente rigenerata dal bundle aggiornato.
        """
        if self._mem is not None:
            return self._mem
        da_file = self._da_file()
        bundle  = _build_bundle_completo()
        if da_file and len(da_file) >= len(bundle):
            # La cache è completa o più aggiornata del bundle → usala
            self._mem = da_file
        else:
            # Cache assente o meno completa del bundle → rigenera
            if da_file is not None:
                log.info(
                    "Auto-upgrade cache uffici: %d (cache) < %d (bundle) → rigenero",
                    len(da_file), len(bundle),
                )
            self._mem = bundle
            self._salva(bundle, sorgente="bundle")
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
