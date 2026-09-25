"""Catalogo del Processo Tributario Telematico (PTT) come lo presenta il SIGIT.

Fonti ufficiali, consultate il 25/09/2026 e archiviate in
``docs/specs/ministero/fonti_ufficiali/2026-09-25/``:

- D.Lgs. 546/1992, artt. 16-bis, 18, 22 (costituzione entro 30 giorni), 12
  (valore della lite); D.M. 23/12/2013 n. 163; decreto direttoriale 4/8/2015
  (specifiche tecniche) modificato dai d.d. 28/11/2017 e 21/4/2023; obbligo del
  deposito telematico per i ricorsi notificati dal 1/7/2019 (art. 16 d.l.
  119/2018);
- «Istruzioni operative PTT» del DGT (maggio 2023): Appendice A (atti
  principali), B (tipologie di allegato), C (altri atti processuali);
- NIR cartacea della Corte di giustizia tributaria di primo grado (Tabella A,
  natura giuridica; Tabella B, atti impugnati; materie e tributi);
- notizia DGT 4/6/2026 «PTT: aggiornamenti tecnico-funzionali»: file fino a
  50 MB, deposito fino a 100 MB, 50 file, «procura-nomina del difensore» tra
  gli altri atti;
- elenco delle Corti per regione (dgt.mef.gov.it, pagina di ogni Corte con
  PEC e codice ufficio per l'F23): ``pct/data/ptt/sedi_cgt.json``.

Il SIGIT non offre servizi per i gestionali (Circolare 1/DF 2019, §6.2): il
deposito si fa dall'area riservata con SPID, CIE o CNS.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

PORTALE = "https://sigit.finanze.it/NIRWeb/login.jsp"
TELECONTENZIOSO = "https://sigit.finanze.it/Sigit/index.do"
REGISTRAZIONE = "https://www.dgt.mef.gov.it/gt/registrazione-ptt-sigit"
CONSULTAZIONE_PUBBLICA = "https://www.dgt.mef.gov.it/gt/servizio-consultazione-pubblica-contenziosi-tributari"
ASSISTENZA = "https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/"
NUMERO_VERDE = "800.051.052"
FONTE = "DGT - Istruzioni operative PTT (maggio 2023), NIR CGT, notizia DGT 4/6/2026"
_SEDI = Path(__file__).resolve().parents[1] / "data" / "ptt" / "sedi_cgt.json"

# Depositi del menu «Invio NIR – Ricorso – Altri Atti» (DGT, articolo DF-GiustiziaTributaria-3764).
DEPOSITI: tuple[dict[str, Any], ...] = (
    {"id": "ricorso", "nome": "Ricorso (primo grado)", "grado": "1", "principale": "RICORSO (primo grado)", "rg": False,
     "passi": ("Dati generali", "Ricorrenti", "Rappresentanti", "Difensori", "Domicilio eletto", "Parti resistenti",
               "Atti impugnati", "Documenti allegati", "Contributo unificato", "Validazione e trasmissione")},
    {"id": "appello", "nome": "Appello (secondo grado)", "grado": "2", "principale": "APPELLO (secondo grado)", "rg": False,
     "passi": ("Dati generali", "Appellanti", "Difensori", "Parti appellate", "Sentenza impugnata", "Documenti allegati",
               "Contributo unificato", "Validazione e trasmissione")},
    {"id": "controdeduzioni", "nome": "Controdeduzioni", "grado": "", "principale": "CONTRODEDUZIONI", "rg": True,
     "passi": ("Dati generali", "Parti", "Documenti allegati", "Validazione e trasmissione")},
    {"id": "altri-atti", "nome": "Altri atti processuali", "grado": "", "principale": "", "rg": True,
     "passi": ("Dati generali", "Documenti", "Validazione e trasmissione")},
    {"id": "nota-documenti", "nome": "Nota di deposito documenti", "grado": "", "principale": "NOTA DI DEPOSITO DOCUMENTI", "rg": True,
     "passi": ("Dati generali e motivazione", "Documenti", "Nota di deposito da firmare", "Validazione e trasmissione")},
)

# Appendice A: atti principali (ricorsi, appelli e altri procedimenti giurisdizionali).
ATTI_PRINCIPALI = (
    "APPELLO (secondo grado)", "ATTO INTERVENTO VOLONTARIO", "ATTO OPPOSIZIONE DI TERZO", "ISTANZA PER MISURE CONSERVATIVE",
    "ISTANZA SOSPENSIONE PRONUNCIA ART. 62 BIS", "ISTANZA SOSPENSIONE SENTENZA ART. 373 C.P.C.",
    "ISTANZA/RICORSO IN RIASSUNZIONE", "RECLAMO", "RICORSO (primo grado)", "RICORSO PER OTTEMPERANZA",
    "RICORSO PER REVOCAZIONE", "RICORSO PER RICUSAZIONE",
)

# Appendice C, più «PROCURA-NOMINA DEL DIFENSORE» (notizia DGT 4/6/2026).
ALTRI_ATTI = (
    "ALTRI ATTI", "COMUNICAZIONE VARIAZIONE DOM. ELETTO", "COMUNICAZIONE VARIAZIONE INDIRIZZO",
    "CONCILIAZIONE PROPOSTA DAL GIUDICE - ADESIONE", "CONCILIAZIONE PROPOSTA DAL GIUDICE - NON ADESIONE",
    "CONCILIAZIONE PROPOSTA DALLA PARTE - ADESIONE", "CONCILIAZIONE PROPOSTA DALLA PARTE - NON ADESIONE",
    "DEPOSITO PROVA TESTIMONIALE", "DISCUSSIONE PUBBLICA E PROPOSTA CONCILIAZIONE", "ISTANZA DI CORREZIONE",
    "ISTANZA DI DISCUSSIONE PUBBLICA", "ISTANZA DI FISSAZIONE UDIENZA", "ISTANZA DI RINVIO UDIENZA",
    "ISTANZA DI RIUNIFICAZIONE", "ISTANZA DI SOSPENSIONE ATTO", "ISTANZA DI SOSPENSIONE SENTENZA", "ISTANZA DI TRATTAZIONE",
    "MEMORIE", "PROCURA-NOMINA DEL DIFENSORE", "RICHIESTA SOSPENSIONE GIUDIZIO ART. 1 C. 197 L. 197/2022",
    "RICHIESTA DI INTERRUZIONE PROCESSO", "RICHIESTA PROVA TESTIMONIALE", "RICHIESTA DI SOSPENSIONE PROCESSO",
    "RICHIESTA ESTINZIONE GIUDIZIO", "RICHIESTA UDIENZA A DISTANZA", "RINUNCIA AL RICORSO/APPELLO",
)

# Appendice B: tipologie di allegato.
ALLEGATI = (
    "ACCETTAZIONE RINUNCIA", "ALTRI DOCUMENTI", "ATTESTAZIONE DEPOSITO ISTANZA ART. 369", "ATTI CATASTALI", "ATTO IMPUGNATO",
    "BILANCIO E SCRITTURE CONTABILI", "COMUNICAZIONE VARIAZIONE DOM. ELETTO", "COMUNICAZIONE VARIAZIONE INDIRIZZO",
    "CONCILIAZIONE PROPOSTA DAL GIUDICE - ADESIONE", "CONCILIAZIONE PROPOSTA DAL GIUDICE - NON ADESIONE",
    "CONCILIAZIONE PROPOSTA DALLA PARTE - ADESIONE", "CONCILIAZIONE PROPOSTA DALLA PARTE - NON ADESIONE", "CONTRATTI",
    "DECRETO LIQUIDAZIONE CTU", "DEFINIZIONI AGEVOLATE/CONDONO", "DELEGA (ENTI IMPOSITORI)", "DENUNCE/QUERELE",
    "DEPOSITO PROVA TESTIMONIALE", "DICHIARAZIONI FISCALI", "DINIEGO DEFINIZ. EX. ART. 6 DL 119/2018 E IST.TRATT.",
    "DISCUSSIONE PUBBLICA E PROPOSTA CONCILIAZIONE", "DOMANDA DEFINIZIONE AGEVOLATA ART.1, C. 186, L.197/2022", "FATTURE",
    "GIURISPRUDENZA", "INTERPELLO", "ISTANZA DEF. AGEVOL. ART. 6 DL 119/2018", "ISTANZA DI CORREZIONE",
    "ISTANZA DI DISCUSSIONE PUBBLICA", "ISTANZA DI FISSAZIONE UDIENZA", "ISTANZA DI RINVIO UDIENZA", "ISTANZA DI RIUNIFICAZIONE",
    "ISTANZA DI SOSPENSIONE ATTO", "ISTANZA DI TRATTAZIONE", "ISTANZE-COMUNICAZIONI PER UDIENZA A DISTANZA", "MEMORIE",
    "NOTA DI DEPOSITO DOCUMENTI", "ONERI DEDUCIBILI/DETRAIBILI", "PROCESSO VERBALE DI CONSTATAZIONE",
    "PROCURA-NOMINA DEL DIFENSORE", "RELATA DI NOTIFICA CARTACEA", "RELAZIONE CONSULENTE TECNICO",
    "RICEVUTA DI ACCETTAZIONE PEC", "RICEVUTA DI CONSEGNA PEC", "RICEVUTA DI PAGAMENTO CUT", "RICEVUTE PAGAMENTO",
    "RICHIESTA DI INTERRUZIONE PROCESSO", "RICHIESTA DI SOSPENSIONE PROCESSO", "RICHIESTA ESTINZIONE GIUDIZIO",
    "RICHIESTA UDIENZA A DISTANZA", "RINUNCIA AL RICORSO/APPELLO", "SENTENZA NOTIFICATA",
)

# NIR, Tabella A: natura giuridica del contribuente.
NATURA_GIURIDICA = (
    ("F01", "Persona fisica"), ("F02", "Impresa individuale/familiare"), ("F03", "Lavoratore autonomo/associazioni professionisti"),
    ("G04", "Consorzi"), ("G05", "Cooperative"), ("G06", "Enti non commerciali/ONLUS"), ("G07", "Fondazioni"),
    ("G08", "Società di capitali ed enti equiparati"), ("G09", "Società di persone ed enti equiparati"),
    ("G10", "Soggetti non residenti"), ("A11", "Altro"),
)

# NIR, Tabella B: denominazione degli atti impugnati.
ATTI_IMPUGNATI = (
    "ATTI RELATIVI AD OPERAZIONI CATASTALI", "AVVISO DI ACCERTAMENTO", "AVVISO DI INTIMAZIONE", "AVVISO DI LIQUIDAZIONE",
    "AVVISO DI MORA", "CARTELLA DI PAGAMENTO", "DINIEGO RIMBORSO", "DINIEGO/REVOCA AGEVOLAZIONI-RATEAZIONI",
    "FERMO AMMINISTRATIVO", "PREAVVISO DI FERMO AMMINISTRATIVO", "AVVISO DI ISCRIZIONE IPOTECARIA",
    "PROVVEDIMENTO DI IRROGAZIONE DELLE SANZIONI", "RIGETTO DEFINIZIONE AGEVOLATA DI RAPPORTI TRIBUTARI", "ALTRO",
)

MATERIE = ("Accertamento imposte", "Agevolazioni", "Condono", "Misure cautelari", "Rimborso", "Riscossione",
           "Violazioni e sanzioni", "Altro")

# Tributi della NIR cartacea (voci di primo livello, così come stampate nel modulo NIR-CGT1).
TRIBUTI = (
    "Bollo", "Catasto", "Concessioni governative", "COSAP", "Demanio", "Dogane", "Giochi e lotterie", "ICI", "ICIAP",
    "ILOR", "Imposta sulle assicurazioni", "Intrattenimenti", "INVIM", "Ipotecarie e catastali", "IRAP", "IRES (ex IRPEG)",
    "IRPEF", "IVA", "Pubblicità e pubbliche affissioni", "Radiodiffusioni", "Registro", "Successioni e donazioni",
    "Tabacchi e fiammiferi", "TARSU/TIA", "Tassa sui contratti di borsa", "TOSAP (comunale/provinciale)",
    "Tasse automobilistiche", "Diritto annuale CCIAA", "Contributo unificato", "Imposta di soggiorno",
    "Altri tributi erariali", "Altri tributi locali",
)

# Tipi di ente per le parti resistenti nella NIR web (DF-GiustiziaTributaria-3067).
TIPI_ENTE = ("Agenzie fiscali", "Enti locali", "Enti pubblici", "Amministrazioni centrali", "Organi di giustizia", "Altri enti")
PUBBLICA_UDIENZA = ("No (camera di consiglio)", "Sì, in presenza", "Sì, a distanza")
MODALITA_CUT = ("pagoPA", "F23", "Contrassegno", "Conto corrente postale", "Prenotazione a debito", "Patrocinio a spese dello Stato")
STATI_NIR = ("in preparazione", "trasmessa", "depositata", "acquisita", "depositata con anomalia", "acquisita con anomalia", "rigettata")


def _semplice(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


@lru_cache(maxsize=1)
def sedi() -> tuple[dict[str, Any], ...]:
    """Le Corti di giustizia tributaria (103 di primo grado, 36 di secondo grado con le sezioni staccate)."""
    righe = json.loads(_SEDI.read_text(encoding="utf-8"))
    esito = []
    for riga in righe:
        codice = riga["fonte"].rsplit("idpoi=", 1)[-1]
        nome = riga["denominazione"]
        if riga.get("sezione_staccata"):
            nome = f"Corte di Giustizia Tributaria di secondo grado - Sezione staccata di {riga['citta']}"
        esito.append({"codice": codice, "grado": riga["grado"], "nome": nome, "citta": riga["citta"],
                      "provincia": riga["provincia"], "regione": riga["regione"], "staccata": bool(riga.get("sezione_staccata")),
                      "codiceF23": riga.get("codice_ufficio_f23", ""), "pec": str(riga.get("pec") or "").lower(), "fonte": riga["fonte"]})
    return tuple(sorted(esito, key=lambda s: (s["grado"], s["regione"], s["citta"])))


def sede(codice: str) -> dict[str, Any] | None:
    return next((s for s in sedi() if s["codice"] == codice), None)


def sede_da_testo(testo: str, grado: str = "") -> str:
    """Codice della Corte nominata nel testo («CGT di primo grado di Bari», «Commissione tributaria provinciale di Bari»)."""
    semplice = _semplice(testo)
    if not semplice or not re.search(r"\b(tributari[ao]|cgt|ctp|ctr)\b", semplice):
        return ""
    secondo = bool(re.search(r"\b(secondo grado|regionale|ctr|cgt2|ii grado)\b", semplice))
    grado = grado or ("2" if secondo else "1")
    candidati = [s for s in sedi() if s["grado"] == grado]
    for s in sorted(candidati, key=lambda s: -len(s["citta"])):
        citta = _semplice(s["citta"]).replace("reggio di calabria", "reggio calabria").replace("reggio nell emilia", "reggio emilia")
        if re.search(rf"\b{re.escape(citta)}\b", semplice.replace("reggio di calabria", "reggio calabria").replace("reggio nell emilia", "reggio emilia")):
            if s["staccata"] and "staccata" not in semplice and grado == "2":
                continue
            return s["codice"]
    if grado == "2":
        for s in candidati:
            if not s["staccata"] and re.search(rf"\b{re.escape(_semplice(s['regione']))}\b", semplice):
                return s["codice"]
    return ""


# Province senza una Corte di primo grado propria (DGT, «Giurisdizione»): la competenza è della Corte indicata.
ACCORPATE = {"BT": "PBA", "FM": "PAP", "MB": "PMI"}


def sede_per_provincia(sigla: str) -> str:
    """Corte di primo grado della provincia dell'ente impositore (art. 4 D.Lgs. 546/1992)."""
    sigla = str(sigla or "").strip().upper()
    if sigla in ACCORPATE:
        return ACCORPATE[sigla]
    return next((s["codice"] for s in sedi() if s["grado"] == "1" and s["provincia"] == sigla), "")


def deposito(identificativo: str) -> dict[str, Any]:
    voce = next((d for d in DEPOSITI if d["id"] == identificativo), None)
    if voce is None:
        raise ValueError("Tipo di deposito non previsto dal PTT.")
    return voce


def catalogo() -> dict[str, Any]:
    return {
        "portale": PORTALE, "telecontenzioso": TELECONTENZIOSO, "registrazione": REGISTRAZIONE,
        "consultazione": CONSULTAZIONE_PUBBLICA, "assistenza": ASSISTENZA, "numeroVerde": NUMERO_VERDE, "fonte": FONTE,
        "sedi": list(sedi()), "depositi": [{**d, "passi": list(d["passi"])} for d in DEPOSITI],
        "attiPrincipali": list(ATTI_PRINCIPALI), "altriAtti": list(ALTRI_ATTI), "allegati": list(ALLEGATI),
        "naturaGiuridica": [{"codice": c, "descrizione": d} for c, d in NATURA_GIURIDICA],
        "attiImpugnati": list(ATTI_IMPUGNATI), "materie": list(MATERIE), "tributi": list(TRIBUTI), "tipiEnte": list(TIPI_ENTE),
        "pubblicaUdienza": list(PUBBLICA_UDIENZA), "modalitaCut": list(MODALITA_CUT), "statiNir": list(STATI_NIR),
    }


__all__ = ["ALLEGATI", "ALTRI_ATTI", "ATTI_IMPUGNATI", "ATTI_PRINCIPALI", "DEPOSITI", "MATERIE", "MODALITA_CUT",
           "NATURA_GIURIDICA", "PORTALE", "PUBBLICA_UDIENZA", "STATI_NIR", "TELECONTENZIOSO", "TIPI_ENTE", "TRIBUTI",
           "catalogo", "deposito", "sede", "sede_da_testo", "sede_per_provincia", "sedi"]
