"""
pct/redazione_normativa.py - Registro riferimenti normativi per la Redazione Atti.

Base normativa del modulo: ogni voce e' un articolo puntuale di fonte ufficiale
(c.c., c.p.c., c.p., c.p.p., c.p.a., leggi speciali) collegato ai modelli del
compilatore (pct/compilatore_atti.py). Il registro distingue ambito processuale
e sostanziale, motiva ogni suggerimento e consente allo studio di integrare,
modificare o disattivare riferimenti senza toccare il codice (override JSON).

Principio delle fonti certe (CLAUDE.md): nessun articolo viene inventato; i
seed riportano estremi normativi consolidati con URL Normattiva e ogni voce e'
modificabile dall'avvocato prima dell'uso nell'atto.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REGISTRO_VERSIONE = "2026.06.12.redazione-normativa.v1"

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"

FONTI_UFFICIALI: dict[str, dict[str, str]] = {
    "c.c.": {"label": "Codice civile (R.D. 16 marzo 1942, n. 262)", "url": _NORMATTIVA + "regio.decreto:1942-03-16;262"},
    "c.p.c.": {"label": "Codice di procedura civile (R.D. 28 ottobre 1940, n. 1443)", "url": _NORMATTIVA + "regio.decreto:1940-10-28;1443"},
    "c.p.": {"label": "Codice penale (R.D. 19 ottobre 1930, n. 1398)", "url": _NORMATTIVA + "regio.decreto:1930-10-19;1398"},
    "c.p.p.": {"label": "Codice di procedura penale (D.P.R. 22 settembre 1988, n. 447)", "url": _NORMATTIVA + "decreto.del.presidente.della.repubblica:1988-09-22;447"},
    "c.p.a.": {"label": "Codice del processo amministrativo (D.Lgs. 2 luglio 2010, n. 104)", "url": _NORMATTIVA + "decreto.legislativo:2010-07-02;104"},
    "d.lgs. 28/2010": {"label": "Mediazione civile e commerciale (D.Lgs. 4 marzo 2010, n. 28)", "url": _NORMATTIVA + "decreto.legislativo:2010-03-04;28"},
    "d.l. 132/2014": {"label": "Negoziazione assistita (D.L. 12 settembre 2014, n. 132)", "url": _NORMATTIVA + "decreto.legge:2014-09-12;132"},
    "d.lgs. 546/1992": {"label": "Processo tributario (D.Lgs. 31 dicembre 1992, n. 546)", "url": _NORMATTIVA + "decreto.legislativo:1992-12-31;546"},
    "d.lgs. 150/2011": {"label": "Riduzione e semplificazione dei riti (D.Lgs. 1 settembre 2011, n. 150)", "url": _NORMATTIVA + "decreto.legislativo:2011-09-01;150"},
    "l. 300/1970": {"label": "Statuto dei lavoratori (L. 20 maggio 1970, n. 300)", "url": _NORMATTIVA + "legge:1970-05-20;300"},
    "l. 604/1966": {"label": "Licenziamenti individuali (L. 15 luglio 1966, n. 604)", "url": _NORMATTIVA + "legge:1966-07-15;604"},
    "d.lgs. 23/2015": {"label": "Contratto a tutele crescenti (D.Lgs. 4 marzo 2015, n. 23)", "url": _NORMATTIVA + "decreto.legislativo:2015-03-04;23"},
    "l. 898/1970": {"label": "Disciplina dei casi di scioglimento del matrimonio (L. 1 dicembre 1970, n. 898)", "url": _NORMATTIVA + "legge:1970-12-01;898"},
    "l. 392/1978": {"label": "Locazione di immobili urbani (L. 27 luglio 1978, n. 392)", "url": _NORMATTIVA + "legge:1978-07-27;392"},
    "d.p.r. 115/2002": {"label": "T.U. spese di giustizia (D.P.R. 30 maggio 2002, n. 115)", "url": _NORMATTIVA + "decreto.del.presidente.della.repubblica:2002-05-30;115"},
    "l. 247/2012": {"label": "Ordinamento della professione forense (L. 31 dicembre 2012, n. 247)", "url": _NORMATTIVA + "legge:2012-12-31;247"},
}

# Etichette delle condizioni contestuali rilevabili dal fascicolo.
CONDIZIONI_LABELS: dict[str, str] = {
    "mediazione": "mediazione presente o richiesta nel fascicolo",
    "negoziazione": "negoziazione assistita presente nel fascicolo",
    "contratto": "controversia contrattuale",
    "preliminare": "contratto preliminare presente nel fascicolo",
    "caparra": "caparra confirmatoria indicata nel fascicolo",
    "clausola_risolutiva": "clausola risolutiva espressa indicata nel fascicolo",
    "diffida": "diffida ad adempiere inviata o richiamata",
    "termine_essenziale": "termine essenziale richiamato nel fascicolo",
    "sinistro": "responsabilita' da fatto illecito o sinistro",
    "sinistro_stradale": "sinistro stradale indicato nel fascicolo",
    "condominio": "controversia condominiale",
    "locazione": "rapporto di locazione",
    "usucapione": "domanda di usucapione",
    "possesso": "tutela possessoria",
    "successioni": "materia successoria",
    "tutele_crescenti": "rapporto di lavoro a tutele crescenti",
    "immobile": "bene immobile coinvolto nella controversia",
}


@dataclass(slots=True)
class RiferimentoNormativo:
    """Articolo di legge collegato a uno o piu' modelli del compilatore."""

    id: str
    fonte: str                      # es. "c.p.c.", "c.c.", "d.lgs. 28/2010"
    articolo: str                   # es. "163", "163-bis"
    rubrica: str                    # rubrica ufficiale o descrizione sintetica
    ambito: str                     # "processuale" | "sostanziale"
    motivo: str                     # perche' viene suggerito
    modelli: List[str] = field(default_factory=list)   # codici modello o prefissi "CIV_*"
    materie: List[str] = field(default_factory=list)   # aree compilatore (CIVILE, LAVORO, ...)
    condizione: str = ""            # chiave CONDIZIONI_LABELS: suggerito solo se attiva
    comma: str = ""
    url_fonte: str = ""
    valid_from: str = ""
    valid_to: str = ""
    note: str = ""
    editable_by_lawyer: bool = True
    attivo: bool = True
    origine: str = "base"           # "base" (seed) | "studio" (personalizzato)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        fonte_info = FONTI_UFFICIALI.get(self.fonte, {})
        data["fonte_label"] = fonte_info.get("label", self.fonte)
        if not data.get("url_fonte"):
            data["url_fonte"] = fonte_info.get("url", "")
        data["riferimento"] = self.riferimento_breve()
        return data

    def riferimento_breve(self) -> str:
        comma = f", comma {self.comma}" if self.comma else ""
        return f"art. {self.articolo}{comma} {self.fonte}"


def _rif(
    rif_id: str,
    fonte: str,
    articolo: str,
    rubrica: str,
    ambito: str,
    motivo: str,
    modelli: Iterable[str],
    *,
    materie: Iterable[str] = (),
    condizione: str = "",
    comma: str = "",
    note: str = "",
) -> RiferimentoNormativo:
    return RiferimentoNormativo(
        id=rif_id,
        fonte=fonte,
        articolo=articolo,
        rubrica=rubrica,
        ambito=ambito,
        motivo=motivo,
        modelli=list(modelli),
        materie=list(materie),
        condizione=condizione,
        comma=comma,
        note=note,
        url_fonte=FONTI_UFFICIALI.get(fonte, {}).get("url", ""),
    )


_CITAZIONE = ("CIV_CIT_001",)
_INTRO_CIVILI = ("CIV_CIT_001", "CIV_LAVRIC_001", "CIV_SFRINT_001", "CIV_CONVSFR_001", "CIV_RDI_001", "SOC_RIC_001")

RIFERIMENTI_BASE: list[RiferimentoNormativo] = [
    # ----- Citazione e giudizio ordinario di cognizione (processuali) -----
    _rif("cpc_163", "c.p.c.", "163", "Contenuto della citazione", "processuale",
         "Requisiti formali dell'atto introduttivo del giudizio ordinario.", _CITAZIONE),
    _rif("cpc_163bis", "c.p.c.", "163-bis", "Termini per comparire", "processuale",
         "Termine minimo a comparire (120 giorni liberi in Italia) tra notifica e udienza.", _CITAZIONE),
    _rif("cpc_164", "c.p.c.", "164", "Nullita' della citazione", "processuale",
         "Verifica preventiva dei vizi della vocatio in ius e della editio actionis.", _CITAZIONE),
    _rif("cpc_166", "c.p.c.", "166", "Costituzione del convenuto", "processuale",
         "Termine di costituzione del convenuto: almeno 70 giorni prima dell'udienza.", ("CIV_CIT_001", "CIV_COM_001")),
    _rif("cpc_167", "c.p.c.", "167", "Comparsa di risposta", "processuale",
         "Contenuto della comparsa e decadenze per domande riconvenzionali ed eccezioni.", ("CIV_CIT_001", "CIV_COM_001")),
    _rif("cpc_168bis", "c.p.c.", "168-bis", "Designazione del giudice istruttore", "processuale",
         "Designazione del giudice e possibile differimento della prima udienza.", _CITAZIONE),
    _rif("cpc_171ter", "c.p.c.", "171-ter", "Memorie integrative", "processuale",
         "Termini delle memorie integrative nel rito ordinario riformato.", ("CIV_CIT_001", "CIV_COM_001", "CIV_MEM_001")),
    _rif("cpc_38", "c.p.c.", "38", "Incompetenza", "processuale",
         "Rilievo dell'incompetenza: da eccepire a pena di decadenza nella comparsa di risposta.", ("CIV_CIT_001", "CIV_COM_001"),
         note="Inserire solo se la competenza e' controversa."),
    _rif("cpc_86", "c.p.c.", "86", "Difesa personale della parte", "processuale",
         "Casi in cui la parte puo' stare in giudizio senza difensore.", _CITAZIONE,
         note="Pertinente solo nei casi eccezionali di difesa personale."),
    _rif("dpr115_13", "d.p.r. 115/2002", "13", "Importi del contributo unificato", "processuale",
         "Determinazione del contributo unificato in base al valore della causa.", _INTRO_CIVILI + ("AMM_RIC_001", "TRIB_RIC_001", "FAM_SEPG_001", "FAM_DIVG_001", "LAV_RIC_001", "LAV_IMPLIC_001")),
    _rif("dpr115_14", "d.p.r. 115/2002", "14", "Obbligo di pagamento e dichiarazione di valore", "processuale",
         "Dichiarazione del valore della causa nelle conclusioni dell'atto introduttivo.", _INTRO_CIVILI),
    # ----- Condizioni di procedibilita' -----
    _rif("dlgs28_5", "d.lgs. 28/2010", "5", "Condizione di procedibilita' e materie", "processuale",
         "Mediazione obbligatoria come condizione di procedibilita' nelle materie elencate.", ("CIV_CIT_001", "CIV_SFRINT_001", "CIV_CONVSFR_001", "CIV_RDI_001"),
         condizione="mediazione"),
    _rif("dlgs28_12bis", "d.lgs. 28/2010", "12-bis", "Conseguenze processuali della mancata partecipazione", "processuale",
         "Argomenti di prova e conseguenze per la parte che non partecipa alla mediazione.", _CITAZIONE,
         condizione="mediazione"),
    _rif("dl132_3", "d.l. 132/2014", "3", "Improcedibilita' e negoziazione assistita", "processuale",
         "Negoziazione assistita come condizione di procedibilita' (risarcimento da circolazione, pagamenti fino a 50.000 euro).", _CITAZIONE,
         condizione="negoziazione"),
    # ----- Comparsa conclusionale, repliche, appello -----
    _rif("cpc_189", "c.p.c.", "189", "Rimessione al collegio", "processuale",
         "Precisazione delle conclusioni e rimessione della causa in decisione.", ("CIV_CONCL_001",)),
    _rif("cpc_190", "c.p.c.", "190", "Comparse conclusionali e memorie", "processuale",
         "Termini di deposito di comparse conclusionali e memorie di replica.", ("CIV_CONCL_001", "CIV_REPL_001")),
    _rif("cpc_342", "c.p.c.", "342", "Forma dell'appello", "processuale",
         "Motivi specifici di appello a pena di inammissibilita'.", ("CIV_APP_001", "FAM_REC_001")),
    _rif("cpc_343", "c.p.c.", "343", "Appello incidentale", "processuale",
         "Modalita' e termini dell'appello incidentale.", ("CIV_APP_001",)),
    _rif("cpc_348", "c.p.c.", "348", "Improcedibilita' dell'appello", "processuale",
         "Conseguenze della mancata costituzione dell'appellante.", ("CIV_APP_001",)),
    # ----- Monitorio e opposizione -----
    _rif("cpc_633", "c.p.c.", "633", "Condizioni di ammissibilita'", "processuale",
         "Presupposti del decreto ingiuntivo: credito certo, liquido ed esigibile fondato su prova scritta.", ("CIV_RDI_001",)),
    _rif("cpc_634", "c.p.c.", "634", "Prova scritta", "processuale",
         "Documenti idonei come prova scritta ai fini monitori.", ("CIV_RDI_001",)),
    _rif("cpc_641", "c.p.c.", "641", "Accoglimento della domanda", "processuale",
         "Contenuto del decreto e termine per l'opposizione.", ("CIV_RDI_001",)),
    _rif("cpc_642", "c.p.c.", "642", "Esecuzione provvisoria", "processuale",
         "Provvisoria esecutorieta' del decreto ingiuntivo.", ("CIV_RDI_001",)),
    _rif("cpc_645", "c.p.c.", "645", "Opposizione", "processuale",
         "Forma e termini dell'opposizione a decreto ingiuntivo.", ("CIV_OPPDI_001",)),
    _rif("cpc_648", "c.p.c.", "648", "Esecuzione provvisoria in pendenza di opposizione", "processuale",
         "Concessione della provvisoria esecutorieta' in corso di opposizione.", ("CIV_OPPDI_001",)),
    _rif("cpc_649", "c.p.c.", "649", "Sospensione dell'esecuzione provvisoria", "processuale",
         "Sospensione dell'esecutorieta' del decreto opposto.", ("CIV_OPPDI_001",)),
    # ----- Esecuzione forzata -----
    _rif("cpc_479", "c.p.c.", "479", "Notificazione del titolo esecutivo e del precetto", "processuale",
         "Notifica del titolo e del precetto prima dell'esecuzione.", ("CIV_PREC_001",)),
    _rif("cpc_480", "c.p.c.", "480", "Forma del precetto", "processuale",
         "Contenuto obbligatorio del precetto e avvertimenti al debitore.", ("CIV_PREC_001",)),
    _rif("cpc_492", "c.p.c.", "492", "Forma del pignoramento", "processuale",
         "Ingiunzione al debitore e avvertimenti nel pignoramento.", ("CIV_PPT_001", "CIV_PIGBASE_001")),
    _rif("cpc_543", "c.p.c.", "543", "Forma del pignoramento presso terzi", "processuale",
         "Contenuto dell'atto di pignoramento presso terzi e citazione del terzo.", ("CIV_PPT_001",)),
    _rif("cpc_547", "c.p.c.", "547", "Dichiarazione del terzo", "processuale",
         "Obblighi dichiarativi del terzo pignorato.", ("CIV_PPT_001",)),
    _rif("cpc_615", "c.p.c.", "615", "Opposizione all'esecuzione", "processuale",
         "Contestazione del diritto della parte istante a procedere ad esecuzione forzata.", ("CIV_OPESE_001",)),
    _rif("cpc_617", "c.p.c.", "617", "Opposizione agli atti esecutivi", "processuale",
         "Vizi formali degli atti del processo esecutivo: termine perentorio di 20 giorni.", ("CIV_OPATTESE_001",)),
    _rif("cpc_624", "c.p.c.", "624", "Sospensione per opposizione all'esecuzione", "processuale",
         "Sospensione dell'esecuzione su istanza di parte in presenza di gravi motivi.", ("CIV_OPESE_001", "CIV_OPATTESE_001")),
    # ----- Cautelari -----
    _rif("cpc_669bis", "c.p.c.", "669-bis", "Forma della domanda cautelare", "processuale",
         "Proposizione del ricorso cautelare.", ("CIV_RCAUT_001", "CIV_ICAUT_001")),
    _rif("cpc_669sexies", "c.p.c.", "669-sexies", "Procedimento cautelare", "processuale",
         "Trattazione e provvedimenti del giudice della cautela.", ("CIV_RCAUT_001",)),
    _rif("cpc_700", "c.p.c.", "700", "Provvedimenti d'urgenza", "processuale",
         "Tutela d'urgenza atipica in presenza di pregiudizio imminente e irreparabile.", ("CIV_RCAUT_001", "CIV_ICAUT_001")),
    # ----- Locazioni e sfratto -----
    _rif("cpc_657", "c.p.c.", "657", "Licenza e sfratto per finita locazione", "processuale",
         "Intimazione di licenza o sfratto alla scadenza del contratto.", ("CIV_SFRINT_001", "CIV_CONVSFR_001")),
    _rif("cpc_658", "c.p.c.", "658", "Sfratto per morosita'", "processuale",
         "Intimazione di sfratto per mancato pagamento dei canoni.", ("CIV_SFRINT_001", "CIV_CONVSFR_001")),
    _rif("cpc_660", "c.p.c.", "660", "Forma dell'intimazione", "processuale",
         "Forma della citazione per la convalida e termini di comparizione.", ("CIV_SFRINT_001", "CIV_CONVSFR_001")),
    _rif("cpc_663", "c.p.c.", "663", "Mancata comparizione o mancata opposizione dell'intimato", "processuale",
         "Convalida dello sfratto in assenza di opposizione.", ("CIV_CONVSFR_001",)),
    _rif("cpc_665", "c.p.c.", "665", "Opposizione dell'intimato", "processuale",
         "Mutamento del rito in caso di opposizione dell'intimato.", ("CIV_CONVSFR_001",)),
    _rif("l392_5", "l. 392/1978", "5", "Inadempimento del conduttore", "sostanziale",
         "Gravita' dell'inadempimento per morosita' nel pagamento dei canoni.", ("CIV_SFRINT_001", "CIV_CONVSFR_001"),
         condizione="locazione"),
    _rif("l392_55", "l. 392/1978", "55", "Termine per il pagamento dei canoni scaduti", "sostanziale",
         "Sanatoria della morosita' in sede di convalida (termine di grazia).", ("CIV_SFRINT_001", "CIV_CONVSFR_001"),
         condizione="locazione"),
    # ----- Lavoro e previdenza -----
    _rif("cpc_409", "c.p.c.", "409", "Controversie individuali di lavoro", "processuale",
         "Ambito di applicazione del rito del lavoro.", ("LAV_RIC_001", "LAV_IMPLIC_001", "CIV_LAVRIC_001")),
    _rif("cpc_414", "c.p.c.", "414", "Forma della domanda", "processuale",
         "Contenuto del ricorso introduttivo nel rito del lavoro.", ("LAV_RIC_001", "LAV_IMPLIC_001", "LAV_PREV_001", "CIV_LAVRIC_001")),
    _rif("cpc_415", "c.p.c.", "415", "Decreto di fissazione dell'udienza", "processuale",
         "Deposito del ricorso, decreto e notifica al convenuto.", ("LAV_RIC_001", "LAV_IMPLIC_001")),
    _rif("cpc_416", "c.p.c.", "416", "Costituzione del convenuto", "processuale",
         "Memoria difensiva nel rito del lavoro e decadenze.", ("LAV_MEM_001", "CIV_LAVMEM_001")),
    _rif("cpc_433", "c.p.c.", "433", "Giudice d'appello", "processuale",
         "Appello nel rito del lavoro.", ("LAV_APP_001", "LAV_APPPREV_001")),
    _rif("cpc_434", "c.p.c.", "434", "Deposito del ricorso in appello", "processuale",
         "Forma e motivi dell'appello nel rito del lavoro.", ("LAV_APP_001", "LAV_APPPREV_001")),
    _rif("l604_2", "l. 604/1966", "2", "Comunicazione e motivazione del licenziamento", "sostanziale",
         "Forma scritta e motivazione del licenziamento individuale.", ("LAV_IMPLIC_001",)),
    _rif("l604_6", "l. 604/1966", "6", "Impugnazione del licenziamento", "sostanziale",
         "Termini di decadenza: impugnazione stragiudiziale entro 60 giorni e deposito entro 180.", ("LAV_IMPLIC_001",)),
    _rif("l300_18", "l. 300/1970", "18", "Tutela del lavoratore in caso di licenziamento illegittimo", "sostanziale",
         "Regime di tutela reintegratoria o indennitaria per i rapporti anteriori al 7 marzo 2015.", ("LAV_IMPLIC_001",)),
    _rif("dlgs23_3", "d.lgs. 23/2015", "3", "Licenziamento per giustificato motivo e giusta causa", "sostanziale",
         "Tutele crescenti per i lavoratori assunti dal 7 marzo 2015.", ("LAV_IMPLIC_001",),
         condizione="tutele_crescenti"),
    # ----- Famiglia e persone -----
    _rif("cpc_473bis12", "c.p.c.", "473-bis.12", "Forma della domanda", "processuale",
         "Contenuto del ricorso nel procedimento unitario per le persone, i minorenni e le famiglie.", ("FAM_SEPG_001", "FAM_DIVG_001", "FAM_AFF_001", "FAM_MOD_001")),
    _rif("cpc_473bis51", "c.p.c.", "473-bis.51", "Procedimento su domanda congiunta", "processuale",
         "Rito su domanda congiunta per separazione e divorzio consensuali.", ("FAM_SEPC_001", "FAM_DIVC_001")),
    _rif("cc_151", "c.c.", "151", "Separazione giudiziale", "sostanziale",
         "Presupposti della separazione giudiziale e addebito.", ("FAM_SEPG_001",)),
    _rif("cc_158", "c.c.", "158", "Separazione consensuale", "sostanziale",
         "Omologazione degli accordi di separazione consensuale.", ("FAM_SEPC_001",)),
    _rif("l898_3", "l. 898/1970", "3", "Casi di scioglimento del matrimonio", "sostanziale",
         "Presupposti per la domanda di divorzio.", ("FAM_DIVC_001", "FAM_DIVG_001")),
    _rif("l898_4", "l. 898/1970", "4", "Procedimento di divorzio", "processuale",
         "Domanda e procedimento per lo scioglimento del matrimonio.", ("FAM_DIVG_001",)),
    _rif("l898_9", "l. 898/1970", "9", "Revisione delle condizioni di divorzio", "sostanziale",
         "Modifica delle condizioni economiche e di affidamento.", ("FAM_MOD_001",)),
    _rif("cc_337ter", "c.c.", "337-ter", "Provvedimenti riguardo ai figli", "sostanziale",
         "Affidamento condiviso e mantenimento dei figli.", ("FAM_AFF_001", "FAM_SEPG_001", "FAM_DIVG_001", "FAM_SEPC_001", "FAM_DIVC_001")),
    _rif("cc_404", "c.c.", "404", "Amministrazione di sostegno", "sostanziale",
         "Presupposti per la nomina dell'amministratore di sostegno.", ("FAM_ADS_001", "FAM_MADS_001")),
    _rif("cc_405", "c.c.", "405", "Decreto di nomina dell'amministratore di sostegno", "sostanziale",
         "Contenuto del decreto di nomina e poteri.", ("FAM_ADS_001",)),
    _rif("cc_406", "c.c.", "406", "Soggetti legittimati a proporre il ricorso", "processuale",
         "Legittimazione alla proposizione del ricorso per amministrazione di sostegno.", ("FAM_ADS_001",)),
    _rif("cpc_720bis", "c.p.c.", "720-bis", "Procedimenti in materia di amministrazione di sostegno", "processuale",
         "Norme applicabili al procedimento davanti al giudice tutelare.", ("FAM_ADS_001", "FAM_MADS_001")),
    # ----- Penale -----
    _rif("cpp_96", "c.p.p.", "96", "Difensore di fiducia", "processuale",
         "Nomina del difensore di fiducia: forma e numero massimo.", ("PEN_NOM_001",)),
    _rif("cpp_121", "c.p.p.", "121", "Memorie e richieste delle parti", "processuale",
         "Facolta' di presentare memorie e richieste scritte al giudice.", ("PEN_MEM_001", "PEN_IST_001")),
    _rif("cp_120", "c.p.", "120", "Diritto di querela", "sostanziale",
         "Titolarita' del diritto di querela della persona offesa.", ("PEN_SEGNBASE_001",)),
    _rif("cp_124", "c.p.", "124", "Termine per proporre la querela", "sostanziale",
         "Termine di tre mesi dalla notizia del fatto.", ("PEN_SEGNBASE_001",)),
    _rif("cpp_336", "c.p.p.", "336", "Querela", "processuale",
         "Forma della querela e presentazione all'autorita'.", ("PEN_SEGNBASE_001",)),
    _rif("cpp_76", "c.p.p.", "76", "Costituzione di parte civile", "processuale",
         "Legittimazione e modalita' della costituzione di parte civile.", ("PEN_PARTECIVBASE_001",)),
    _rif("cpp_78", "c.p.p.", "78", "Formalita' della costituzione di parte civile", "processuale",
         "Requisiti a pena di inammissibilita' della dichiarazione di costituzione.", ("PEN_PARTECIVBASE_001",)),
    _rif("cpp_468", "c.p.p.", "468", "Citazione di testimoni, periti e consulenti", "processuale",
         "Deposito della lista testi almeno 7 giorni prima del dibattimento.", ("PEN_LISTATESTI_001",)),
    _rif("cpp_461", "c.p.p.", "461", "Opposizione al decreto penale", "processuale",
         "Termini e contenuto dell'opposizione a decreto penale di condanna.", ("PEN_OPPDP_001",)),
    _rif("cpp_581", "c.p.p.", "581", "Forma dell'impugnazione", "processuale",
         "Requisiti dell'atto di impugnazione penale a pena di inammissibilita'.", ("PEN_IMP_001",)),
    _rif("cpp_593", "c.p.p.", "593", "Casi di appello", "processuale",
         "Provvedimenti appellabili e limiti.", ("PEN_IMP_001",)),
    _rif("cpp_263", "c.p.p.", "263", "Procedimento per la restituzione delle cose sequestrate", "processuale",
         "Richiesta di restituzione dei beni in sequestro.", ("PEN_DISSEQ_001",)),
    # ----- Amministrativo -----
    _rif("cpa_29", "c.p.a.", "29", "Azione di annullamento", "processuale",
         "Azione di annullamento per violazione di legge, incompetenza ed eccesso di potere: termine di 60 giorni.", ("AMM_RIC_001",)),
    _rif("cpa_40", "c.p.a.", "40", "Contenuto del ricorso", "processuale",
         "Elementi che il ricorso al giudice amministrativo deve contenere.", ("AMM_RIC_001", "AMM_MOTAGG_001")),
    _rif("cpa_41", "c.p.a.", "41", "Notificazione del ricorso e suoi destinatari", "processuale",
         "Notifica all'amministrazione resistente e ad almeno un controinteressato.", ("AMM_RIC_001",)),
    _rif("cpa_43", "c.p.a.", "43", "Motivi aggiunti", "processuale",
         "Proposizione di motivi aggiunti avverso atti connessi.", ("AMM_MOTAGG_001",)),
    _rif("cpa_55", "c.p.a.", "55", "Misure cautelari collegiali", "processuale",
         "Domanda cautelare in corso di causa davanti al giudice amministrativo.", ("AMM_ICAUT_001", "AMM_RIC_001")),
    _rif("cpa_100", "c.p.a.", "100", "Appello avverso le sentenze dei T.A.R.", "processuale",
         "Appellabilita' delle sentenze dei tribunali amministrativi regionali.", ("AMM_APPCDS_001",)),
    _rif("cpa_101", "c.p.a.", "101", "Contenuto del ricorso in appello", "processuale",
         "Specifiche censure contro i capi della sentenza gravata.", ("AMM_APPCDS_001",)),
    # ----- Tributario -----
    _rif("dlgs546_18", "d.lgs. 546/1992", "18", "Il ricorso", "processuale",
         "Contenuto del ricorso tributario a pena di inammissibilita'.", ("TRIB_RIC_001",)),
    _rif("dlgs546_19", "d.lgs. 546/1992", "19", "Atti impugnabili e oggetto del ricorso", "processuale",
         "Elenco degli atti autonomamente impugnabili.", ("TRIB_RIC_001",)),
    _rif("dlgs546_21", "d.lgs. 546/1992", "21", "Termine per la proposizione del ricorso", "processuale",
         "Termine di 60 giorni dalla notificazione dell'atto impugnato.", ("TRIB_RIC_001",)),
    _rif("dlgs546_22", "d.lgs. 546/1992", "22", "Costituzione in giudizio del ricorrente", "processuale",
         "Deposito telematico del ricorso entro 30 giorni.", ("TRIB_RIC_001",)),
    _rif("dlgs546_47", "d.lgs. 546/1992", "47", "Sospensione dell'atto impugnato", "processuale",
         "Istanza di sospensione dell'esecuzione dell'atto tributario.", ("TRIB_SOSP_001",)),
    _rif("dlgs546_52", "d.lgs. 546/1992", "52", "Giudice competente e provvedimenti sull'esecuzione provvisoria in appello", "processuale",
         "Appello alla Corte di giustizia tributaria di secondo grado.", ("TRIB_APP_001",)),
    _rif("dlgs546_53", "d.lgs. 546/1992", "53", "Forma dell'appello", "processuale",
         "Motivi specifici dell'impugnazione tributaria.", ("TRIB_APP_001", "TRIB_CONTROAPP_001")),
    # ----- Stragiudiziale: mora, diffida, transazione, incarico -----
    _rif("cc_1219", "c.c.", "1219", "Costituzione in mora", "sostanziale",
         "Intimazione o richiesta scritta di adempimento al debitore.", ("STR_DIFF_001", "STR_MM_001", "STR_RDP_001", "STR_SOLL_001")),
    _rif("cc_1224", "c.c.", "1224", "Danni nelle obbligazioni pecuniarie", "sostanziale",
         "Interessi moratori dal giorno della mora.", ("STR_MM_001", "STR_RDP_001", "CIV_PREC_001")),
    _rif("cc_1218", "c.c.", "1218", "Responsabilita' del debitore", "sostanziale",
         "Inadempimento delle obbligazioni e risarcimento del danno.", ("STR_DIFF_001", "STR_MM_001", "STR_RDP_001", "CIV_CIT_001"),
         condizione="contratto"),
    _rif("cc_2697", "c.c.", "2697", "Onere della prova", "sostanziale",
         "Ripartizione dell'onere probatorio tra creditore e debitore.", ("STR_RDP_001", "CIV_RDI_001", "CIV_CIT_001")),
    _rif("cc_1965", "c.c.", "1965", "Nozione di transazione", "sostanziale",
         "Definizione e funzione del contratto di transazione.", ("STR_ATR_001", "STR_PTR_001")),
    _rif("cc_1967", "c.c.", "1967", "Prova della transazione", "sostanziale",
         "Forma scritta ad probationem della transazione.", ("STR_ATR_001",)),
    _rif("cc_2230", "c.c.", "2230", "Prestazione d'opera intellettuale", "sostanziale",
         "Disciplina del contratto d'opera intellettuale.", ("STR_INC_001", "STR_PREV_001")),
    _rif("l247_13", "l. 247/2012", "13", "Conferimento dell'incarico e compenso", "sostanziale",
         "Pattuizione del compenso e preventivo di massima obbligatorio.", ("STR_INC_001", "STR_PREV_001")),
    # ----- Sostanziali: contratti e risoluzione (citazione / diffide) -----
    _rif("cc_1453", "c.c.", "1453", "Risolubilita' del contratto per inadempimento", "sostanziale",
         "Domanda di risoluzione o adempimento con risarcimento del danno.", ("CIV_CIT_001", "STR_DIFF_001"),
         condizione="contratto"),
    _rif("cc_1454", "c.c.", "1454", "Diffida ad adempiere", "sostanziale",
         "Assegnazione di congruo termine con effetto risolutivo automatico.", ("CIV_CIT_001", "STR_DIFF_001"),
         condizione="diffida"),
    _rif("cc_1455", "c.c.", "1455", "Importanza dell'inadempimento", "sostanziale",
         "Gravita' dell'inadempimento ai fini della risoluzione.", ("CIV_CIT_001",),
         condizione="contratto"),
    _rif("cc_1456", "c.c.", "1456", "Clausola risolutiva espressa", "sostanziale",
         "Risoluzione di diritto per violazione della clausola pattuita.", ("CIV_CIT_001", "STR_DIFF_001"),
         condizione="clausola_risolutiva"),
    _rif("cc_1457", "c.c.", "1457", "Termine essenziale per una delle parti", "sostanziale",
         "Risoluzione di diritto alla scadenza del termine essenziale.", ("CIV_CIT_001",),
         condizione="termine_essenziale"),
    _rif("cc_1458", "c.c.", "1458", "Effetti della risoluzione", "sostanziale",
         "Retroattivita' della risoluzione tra le parti e obblighi restitutori.", ("CIV_CIT_001",),
         condizione="contratto"),
    _rif("cc_1385", "c.c.", "1385", "Caparra confirmatoria", "sostanziale",
         "Recesso con ritenzione della caparra o restituzione del doppio.", ("CIV_CIT_001", "STR_DIFF_001"),
         condizione="caparra"),
    _rif("cc_2932", "c.c.", "2932", "Esecuzione specifica dell'obbligo di concludere un contratto", "sostanziale",
         "Sentenza costitutiva che produce gli effetti del contratto non concluso.", ("CIV_CIT_001",),
         condizione="preliminare"),
    _rif("cc_1223", "c.c.", "1223", "Risarcimento del danno", "sostanziale",
         "Danno emergente e lucro cessante come conseguenza immediata e diretta.", ("CIV_CIT_001", "STR_DIFF_001"),
         condizione="contratto"),
    _rif("cc_1225", "c.c.", "1225", "Prevedibilita' del danno", "sostanziale",
         "Limite del danno prevedibile al tempo dell'obbligazione.", ("CIV_CIT_001",),
         condizione="contratto"),
    _rif("cc_1226", "c.c.", "1226", "Valutazione equitativa del danno", "sostanziale",
         "Liquidazione equitativa quando il danno non puo' essere provato nell'ammontare.", ("CIV_CIT_001",),
         condizione="contratto"),
    _rif("cc_1227", "c.c.", "1227", "Concorso del fatto colposo del creditore", "sostanziale",
         "Riduzione del risarcimento per concorso del danneggiato.", ("CIV_CIT_001",),
         condizione="contratto"),
    # ----- Sostanziali: responsabilita' extracontrattuale -----
    _rif("cc_2043", "c.c.", "2043", "Risarcimento per fatto illecito", "sostanziale",
         "Responsabilita' aquiliana: obbligo di risarcire il danno ingiusto.", ("CIV_CIT_001", "STR_DIFF_001"),
         condizione="sinistro"),
    _rif("cc_2054", "c.c.", "2054", "Circolazione di veicoli", "sostanziale",
         "Responsabilita' del conducente e presunzione di pari responsabilita'.", ("CIV_CIT_001",),
         condizione="sinistro_stradale"),
    _rif("cc_2059", "c.c.", "2059", "Danni non patrimoniali", "sostanziale",
         "Risarcibilita' del danno non patrimoniale nei casi previsti dalla legge.", ("CIV_CIT_001",),
         condizione="sinistro"),
    _rif("cc_2697_resp", "c.c.", "2697", "Onere della prova", "sostanziale",
         "Prova del fatto illecito, del danno e del nesso causale.", (),
         condizione="sinistro", note="Duplicato contestuale per area responsabilita'."),
    # ----- Sostanziali: condominio, diritti reali, possesso, successioni -----
    _rif("cc_1137", "c.c.", "1137", "Impugnazione delle deliberazioni dell'assemblea", "sostanziale",
         "Annullamento delle delibere condominiali: termine di 30 giorni.", ("CIV_CIT_001",),
         condizione="condominio"),
    _rif("cc_63disp", "c.c.", "63 disp. att.", "Riscossione dei contributi condominiali", "sostanziale",
         "Decreto ingiuntivo immediatamente esecutivo per oneri condominiali.", ("CIV_RDI_001",),
         condizione="condominio"),
    _rif("cc_1158", "c.c.", "1158", "Usucapione dei beni immobili e dei diritti reali immobiliari", "sostanziale",
         "Acquisto della proprieta' per possesso continuato ventennale.", ("CIV_CIT_001",),
         condizione="usucapione"),
    _rif("cc_948", "c.c.", "948", "Azione di rivendicazione", "sostanziale",
         "Rivendica della proprieta' contro chi possiede o detiene.", ("CIV_CIT_001",),
         condizione="immobile"),
    _rif("cc_1168", "c.c.", "1168", "Azione di reintegrazione", "sostanziale",
         "Reintegrazione nel possesso entro l'anno dallo spoglio.", ("CIV_RCAUT_001", "CIV_CIT_001"),
         condizione="possesso"),
    _rif("cc_713", "c.c.", "713", "Facolta' di domandare la divisione", "sostanziale",
         "Scioglimento della comunione ereditaria.", ("CIV_CIT_001",),
         condizione="successioni"),
    _rif("cc_533", "c.c.", "533", "Petizione di eredita'", "sostanziale",
         "Riconoscimento della qualita' di erede e restituzione dei beni.", ("CIV_CIT_001",),
         condizione="successioni"),
]


# ---------------------------------------------------------------------------
# Persistenza override di studio (upsert JSON, nessuna distruzione dei seed)
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()
_DEFAULT_DB = "./template_atti/riferimenti_normativi.json"


def _db_file(db_path: Optional[str]) -> Path:
    return Path(db_path or _DEFAULT_DB)


def _carica_override(db_path: Optional[str]) -> dict[str, Any]:
    path = _db_file(db_path)
    if not path.exists():
        return {"versione": 1, "personalizzati": [], "disattivati": [], "modificati": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"versione": 1, "personalizzati": [], "disattivati": [], "modificati": {}}
    if not isinstance(data, dict):
        return {"versione": 1, "personalizzati": [], "disattivati": [], "modificati": {}}
    data.setdefault("personalizzati", [])
    data.setdefault("disattivati", [])
    data.setdefault("modificati", {})
    return data


def _salva_override(data: dict[str, Any], db_path: Optional[str]) -> None:
    path = _db_file(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _riferimento_da_dict(data: dict[str, Any], *, origine: str = "studio") -> RiferimentoNormativo:
    campi_lista = {"modelli", "materie"}
    kwargs: dict[str, Any] = {}
    for nome in RiferimentoNormativo.__dataclass_fields__:
        if nome in data:
            valore = data[nome]
            if nome in campi_lista and not isinstance(valore, list):
                valore = [str(item).strip() for item in str(valore or "").split(",") if str(item).strip()]
            kwargs[nome] = valore
    kwargs.setdefault("id", f"studio_{uuid.uuid4().hex[:10]}")
    kwargs.setdefault("fonte", "")
    kwargs.setdefault("articolo", "")
    kwargs.setdefault("rubrica", "")
    kwargs.setdefault("ambito", "sostanziale")
    kwargs.setdefault("motivo", "Riferimento inserito dallo studio.")
    kwargs["origine"] = origine
    if kwargs.get("ambito") not in {"processuale", "sostanziale"}:
        kwargs["ambito"] = "sostanziale"
    return RiferimentoNormativo(**kwargs)


def tutti_riferimenti(*, db_path: Optional[str] = None, includi_disattivati: bool = False) -> list[RiferimentoNormativo]:
    """Seed di base + personalizzazioni dello studio (upsert non distruttivo)."""
    with _LOCK:
        override = _carica_override(db_path)
    disattivati = set(override.get("disattivati") or [])
    modificati = override.get("modificati") or {}
    risultato: list[RiferimentoNormativo] = []
    for base in RIFERIMENTI_BASE:
        rif = base
        patch = modificati.get(base.id)
        if isinstance(patch, dict) and patch:
            merged = base.to_dict()
            merged.update({k: v for k, v in patch.items() if k in RiferimentoNormativo.__dataclass_fields__})
            rif = _riferimento_da_dict(merged, origine="base")
        if rif.id in disattivati:
            if not includi_disattivati:
                continue
            rif = _riferimento_da_dict({**rif.to_dict(), "attivo": False}, origine=rif.origine)
        risultato.append(rif)
    for raw in override.get("personalizzati") or []:
        if not isinstance(raw, dict):
            continue
        rif = _riferimento_da_dict(raw, origine="studio")
        if rif.id in disattivati and not includi_disattivati:
            continue
        risultato.append(rif)
    return risultato


def salva_riferimento(dati: dict[str, Any], *, db_path: Optional[str] = None) -> RiferimentoNormativo:
    """Upsert di un riferimento: i seed vengono patchati, i nuovi salvati come 'studio'."""
    if not isinstance(dati, dict):
        raise ValueError("Dati riferimento non validi.")
    fonte = str(dati.get("fonte") or "").strip()
    articolo = str(dati.get("articolo") or "").strip()
    if not fonte or not articolo:
        raise ValueError("Fonte e articolo sono obbligatori per un riferimento normativo.")
    rif_id = str(dati.get("id") or "").strip()
    base_ids = {item.id for item in RIFERIMENTI_BASE}
    with _LOCK:
        override = _carica_override(db_path)
        if rif_id and rif_id in base_ids:
            patch = {k: v for k, v in dati.items() if k in RiferimentoNormativo.__dataclass_fields__ and k != "id"}
            override.setdefault("modificati", {})[rif_id] = patch
            if rif_id in (override.get("disattivati") or []):
                override["disattivati"] = [item for item in override["disattivati"] if item != rif_id]
            _salva_override(override, db_path)
            base = next(item for item in RIFERIMENTI_BASE if item.id == rif_id)
            merged = base.to_dict()
            merged.update(patch)
            return _riferimento_da_dict(merged, origine="base")
        rif = _riferimento_da_dict(dati, origine="studio")
        personalizzati = [item for item in (override.get("personalizzati") or []) if isinstance(item, dict)]
        personalizzati = [item for item in personalizzati if str(item.get("id") or "") != rif.id]
        salvabile = asdict(rif)
        personalizzati.append(salvabile)
        override["personalizzati"] = personalizzati
        if rif.id in (override.get("disattivati") or []):
            override["disattivati"] = [item for item in override["disattivati"] if item != rif.id]
        _salva_override(override, db_path)
    return rif


def disattiva_riferimento(rif_id: str, *, db_path: Optional[str] = None) -> bool:
    rif_id = str(rif_id or "").strip()
    if not rif_id:
        return False
    with _LOCK:
        override = _carica_override(db_path)
        disattivati = set(override.get("disattivati") or [])
        if rif_id in disattivati:
            return True
        disattivati.add(rif_id)
        override["disattivati"] = sorted(disattivati)
        _salva_override(override, db_path)
    return True


def riattiva_riferimento(rif_id: str, *, db_path: Optional[str] = None) -> bool:
    rif_id = str(rif_id or "").strip()
    if not rif_id:
        return False
    with _LOCK:
        override = _carica_override(db_path)
        disattivati = [item for item in (override.get("disattivati") or []) if item != rif_id]
        override["disattivati"] = disattivati
        _salva_override(override, db_path)
    return True


# ---------------------------------------------------------------------------
# Selezione per modello + condizioni contestuali del fascicolo
# ---------------------------------------------------------------------------

def _match_modello(rif: RiferimentoNormativo, model_code: str) -> bool:
    code = str(model_code or "").strip().upper()
    if not code:
        return False
    for pattern in rif.modelli:
        chiave = str(pattern or "").strip().upper()
        if not chiave:
            continue
        if chiave.endswith("*"):
            if code.startswith(chiave[:-1]):
                return True
        elif chiave == code:
            return True
    return False


def riferimenti_per_modello(
    model_code: str,
    *,
    materia: str = "",
    condizioni: Optional[Dict[str, bool]] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Riferimenti suggeriti per un modello, filtrati per condizioni del fascicolo.

    I riferimenti condizionali entrano solo se la condizione risulta attiva nel
    fascicolo (es. caparra, mediazione): nulla viene inserito se non pertinente.
    """
    condizioni = {str(k): bool(v) for k, v in (condizioni or {}).items()}
    base_code = str(model_code or "").strip().upper()
    alias_base = ""
    try:
        from pct.compilatore_atti import MODEL_INDEX

        modello = MODEL_INDEX.get(base_code) or {}
        alias_base = str(modello.get("alias_of") or "").strip().upper()
    except Exception:
        modello = {}
    processuali: list[dict[str, Any]] = []
    sostanziali: list[dict[str, Any]] = []
    visti: set[str] = set()
    for rif in tutti_riferimenti(db_path=db_path):
        if not rif.attivo:
            continue
        if not (_match_modello(rif, base_code) or (alias_base and _match_modello(rif, alias_base))):
            continue
        if rif.materie and materia and str(materia).strip().upper() not in {m.upper() for m in rif.materie}:
            continue
        motivo = rif.motivo
        if rif.condizione:
            if not condizioni.get(rif.condizione):
                continue
            etichetta = CONDIZIONI_LABELS.get(rif.condizione, rif.condizione)
            motivo = f"{rif.motivo} Rilevato nel fascicolo: {etichetta}."
        chiave = f"{rif.fonte}|{rif.articolo}|{rif.comma}|{rif.ambito}"
        if chiave in visti:
            continue
        visti.add(chiave)
        riga = rif.to_dict()
        riga["motivo_contestuale"] = motivo
        if rif.ambito == "processuale":
            processuali.append(riga)
        else:
            sostanziali.append(riga)
    return {
        "modello": base_code,
        "versione": REGISTRO_VERSIONE,
        "processuali": processuali,
        "sostanziali": sostanziali,
        "totale": len(processuali) + len(sostanziali),
    }


def testo_diritto_da_riferimenti(riferimenti: dict[str, Any]) -> str:
    """Traccia IN DIRITTO leggibile dai riferimenti selezionati (modificabile dall'avvocato)."""
    righe: list[str] = []
    sostanziali = riferimenti.get("sostanziali") or []
    processuali = riferimenti.get("processuali") or []
    if sostanziali:
        righe.append("Quanto al merito:")
        for rif in sostanziali:
            riferimento = rif.get("riferimento") or f"art. {rif.get('articolo')} {rif.get('fonte')}"
            rubrica = str(rif.get("rubrica") or "").strip()
            righe.append(f"- {riferimento} ({rubrica}): {rif.get('motivo_contestuale') or rif.get('motivo') or ''}".rstrip(": "))
    if processuali:
        if righe:
            righe.append("")
        righe.append("Quanto al rito:")
        for rif in processuali:
            riferimento = rif.get("riferimento") or f"art. {rif.get('articolo')} {rif.get('fonte')}"
            rubrica = str(rif.get("rubrica") or "").strip()
            righe.append(f"- {riferimento} ({rubrica}): {rif.get('motivo_contestuale') or rif.get('motivo') or ''}".rstrip(": "))
    return "\n".join(righe).strip()


def riepilogo_registro(*, db_path: Optional[str] = None) -> dict[str, Any]:
    riferimenti = tutti_riferimenti(db_path=db_path, includi_disattivati=True)
    return {
        "versione": REGISTRO_VERSIONE,
        "totale": len(riferimenti),
        "attivi": sum(1 for rif in riferimenti if rif.attivo),
        "processuali": sum(1 for rif in riferimenti if rif.ambito == "processuale"),
        "sostanziali": sum(1 for rif in riferimenti if rif.ambito == "sostanziale"),
        "personalizzati": sum(1 for rif in riferimenti if rif.origine == "studio"),
        "fonti": sorted({rif.fonte for rif in riferimenti if rif.fonte}),
    }
