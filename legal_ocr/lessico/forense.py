"""Il lessico degli atti: le parole che un avvocato scrive ogni giorno.

Il lettore ottico sbaglia soprattutto sulle parole che non si aspetta. Negli
atti giudiziari il vocabolario è ristretto e ricorrente: istituti, formule,
soggetti del processo, riti. Dichiararlo qui permette al correttore di
riportare «cornparsa» a «comparsa», «istan2a» a «istanza», «perentorìo» a
«perentorio», senza inventare nulla: una parola si corregge solo se la forma
corretta è in questo elenco (o nel vocabolario italiano) ed è l'unica
possibile.

Le parole vengono dal linguaggio dei codici e delle leggi che il gestionale
già cita: c.p.c. e disp. att., c.p.p., c.c., D.M. 44/2011 e specifiche DGSIA
per il telematico, L. 53/1994 per le notifiche, D.P.R. 115/2002 per le spese,
D.M. 55/2014 per i compensi.
"""

from __future__ import annotations

# Atti, istituti e soggetti del processo.
PROCESSO = (
    "atto", "atti", "citazione", "ricorso", "ricorrente", "resistente", "attore", "attrice", "convenuto", "convenuta",
    "comparsa", "costituzione", "risposta", "memoria", "memorie", "istanza", "istanze", "domanda", "domande",
    "eccezione", "eccezioni", "conclusioni", "conclusionale", "replica", "repliche", "note", "nota", "verbale", "verbali",
    "udienza", "udienze", "comparizione", "trattazione", "discussione", "rinvio", "rinviata", "rinviato",
    "giudice", "giudizio", "giudiziario", "giudiziaria", "tribunale", "corte", "appello", "cassazione", "sezione", "sezioni",
    "presidente", "collegio", "cancelleria", "cancelliere", "procura", "procuratore", "difensore", "difensori", "avvocato",
    "parte", "parti", "terzo", "terzi", "interveniente", "intervento", "litisconsorte", "contumace", "contumacia",
    "sentenza", "sentenze", "ordinanza", "ordinanze", "decreto", "decreti", "provvedimento", "provvedimenti",
    "ingiuntivo", "ingiunzione", "precetto", "pignoramento", "esecuzione", "esecutivo", "espropriazione", "opposizione",
    "reclamo", "impugnazione", "gravame", "revocazione", "sequestro", "cautelare", "inibitoria", "sospensione",
    "mediazione", "mediatore", "negoziazione", "conciliazione", "arbitrato", "transazione",
    "termine", "termini", "perentorio", "perentoria", "ordinatorio", "decadenza", "prescrizione", "sospensione", "interruzione",
    "notifica", "notificazione", "notificato", "notificata", "relata", "relazione", "ufficiale", "ufficiario",
    "deposito", "depositato", "depositata", "telematico", "telematica", "busta", "ricevuta", "ricevute", "accettazione",
    "consegna", "attestazione", "conformità", "asseverazione", "firma", "firmato", "firmata", "digitale",
    "fascicolo", "fascicoli", "documento", "documenti", "allegato", "allegati", "produzione", "produzioni", "indice",
    "prova", "prove", "testimone", "testimoni", "testimonianza", "consulenza", "consulente", "perizia", "perito",
    "istruttoria", "istruttorie", "ammissione", "capitolo", "capitoli", "interrogatorio", "confessione", "giuramento",
    "spese", "compenso", "compensi", "onorario", "liquidazione", "liquidate", "rimborso", "forfettarie", "accessori",
    "contributo", "unificato", "marca", "bollo", "esenzione", "patrocinio", "gratuito",
    "risarcimento", "danno", "danni", "responsabilità", "colpa", "dolo", "inadempimento", "adempimento", "obbligazione",
    "contratto", "contratti", "clausola", "clausole", "nullità", "annullamento", "risoluzione", "rescissione", "recesso",
    "credito", "crediti", "creditore", "debitore", "debito", "interessi", "mora", "rivalutazione", "capitale",
    "proprietà", "possesso", "usucapione", "servitù", "condominio", "condomino", "locazione", "conduttore", "locatore",
    "successione", "erede", "eredi", "legato", "testamento", "donazione", "separazione", "divorzio", "affidamento",
    "mantenimento", "assegno", "coniuge", "figli", "minore", "minori", "tutela", "curatore", "amministratore", "sostegno",
    "lavoro", "lavoratore", "datore", "licenziamento", "dimissioni", "retribuzione", "contributi", "previdenza",
    "societa", "società", "socio", "soci", "amministratori", "assemblea", "delibera", "fallimento", "liquidazione",
    "concorsuale", "curatela", "insinuazione", "passivo", "concordato", "sovraindebitamento",
    "penale", "imputato", "indagato", "persona", "offesa", "querela", "denuncia", "pubblico", "ministero", "procura",
    "indagini", "preliminari", "archiviazione", "rinvio", "giudizio", "dibattimento", "assoluzione", "condanna", "pena",
    "amministrativo", "ricorso", "annullamento", "provvedimento", "silenzio", "accesso", "appalto", "aggiudicazione",
    "tributario", "accertamento", "cartella", "avviso", "riscossione", "sgravio", "rimborso",
)

# Formule e locuzioni che compaiono nelle intestazioni e nelle conclusioni.
FORMULE = (
    "voglia", "piaccia", "chiede", "chiedono", "conclude", "concludono", "insta", "istano", "rassegna", "rassegnano",
    "premesso", "premessa", "considerato", "rilevato", "ritenuto", "atteso", "visto", "visti", "vista", "viste",
    "letto", "letti", "letta", "lette", "sentite", "udito", "uditi", "esaminati", "accertato", "verificato",
    "dichiara", "dichiarare", "accertare", "accogliere", "respingere", "rigettare", "condannare", "revocare",
    "disporre", "dispone", "ordina", "ordinare", "autorizza", "autorizzare", "ingiunge", "assegna", "fissa", "rimette",
    "conferma", "riforma", "annulla", "cassa", "rinvia", "provvede", "delibera", "liquida", "compensa",
    "salvis", "iuribus", "ogni", "riserva", "riservata", "impregiudicata", "occorrendo", "subordine", "principalità",
    "sensi", "effetti", "quanto", "sopra", "seguito", "quali", "cui", "nonché", "altresì", "pertanto", "conseguentemente",
    "espressamente", "integralmente", "specificamente", "tempestivamente", "ritualmente", "regolarmente", "validamente",
    "vittoria", "rifusione", "refusione", "distrazione", "antistatario",
)

# Le forme tipiche delle intestazioni e delle formule solenni: si scrivono così.
FRASI = (
    ("per questi motivi", "PER QUESTI MOTIVI"),
    ("p.q.m.", "P.Q.M."),
    ("in fatto e in diritto", "IN FATTO E IN DIRITTO"),
    ("in nome del popolo italiano", "IN NOME DEL POPOLO ITALIANO"),
    ("repubblica italiana", "REPUBBLICA ITALIANA"),
    ("con vittoria di spese e competenze", "con vittoria di spese e competenze"),
    ("salvis iuribus", "salvis iuribus"),
    ("con ogni riserva", "con ogni riserva"),
    ("ai sensi e per gli effetti", "ai sensi e per gli effetti"),
    ("in via preliminare", "in via preliminare"),
    ("in via principale", "in via principale"),
    ("in via subordinata", "in via subordinata"),
    ("in via istruttoria", "in via istruttoria"),
    ("si chiede", "si chiede"),
    ("voglia l'ill.mo tribunale", "Voglia l'Ill.mo Tribunale"),
    ("rassegnando le seguenti conclusioni", "rassegnando le seguenti conclusioni"),
)

LESSICO: frozenset[str] = frozenset(parola.casefold() for parola in (*PROCESSO, *FORMULE))

__all__ = ["FORMULE", "FRASI", "LESSICO", "PROCESSO"]
