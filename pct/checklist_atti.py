"""
Checklist e struttura cartelle per la preparazione degli atti processuali.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentoRichiesto:
    numero: int
    nome_file: str
    descrizione: str
    obbligatorio: bool = True
    note: str = ""


@dataclass
class ItemChecklist:
    testo: str
    critico: bool = False
    note: str = ""


@dataclass
class TemplateAtto:
    id: str
    nome: str
    categoria: str
    descrizione: str
    nome_cartella: str
    # Canale di deposito: PCT_TELEMATICO | PDP_PENALE | PAT_AMMINISTRATIVO | PEC | CARTACEO
    canale: str = "PCT_TELEMATICO"
    # URL Flask endpoint per il deposito telematico (se applicabile)
    endpoint_deposito: str = ""
    # Note sul canale/redattore
    nota_canale: str = ""
    documenti: List[DocumentoRichiesto] = field(default_factory=list)
    checklist: List[ItemChecklist] = field(default_factory=list)
    note_generali: str = ""


CANALE_LABEL = {
    "PCT_TELEMATICO": "Deposito telematico PCT",
    "PDP_PENALE":     "Portale Deposito Penale (PDP)",
    "PAT_AMMINISTRATIVO": "Portale Atti Amministrativi (PAT)",
    "PEC":            "Deposito a mezzo PEC",
    "CARTACEO":       "Deposito cartaceo / cancelleria",
}

CANALE_ICON = {
    "PCT_TELEMATICO":     "bi-send-fill",
    "PDP_PENALE":         "bi-shield-fill",
    "PAT_AMMINISTRATIVO": "bi-building",
    "PEC":                "bi-envelope-fill",
    "CARTACEO":           "bi-printer-fill",
}

CANALE_COL = {
    "PCT_TELEMATICO":     "primary",
    "PDP_PENALE":         "dark",
    "PAT_AMMINISTRATIVO": "info",
    "PEC":                "success",
    "CARTACEO":           "secondary",
}


def _doc(n: int, nome: str, desc: str, obbl: bool = True, note: str = "") -> DocumentoRichiesto:
    return DocumentoRichiesto(numero=n, nome_file=f"{n:02d}_{nome}", descrizione=desc,
                               obbligatorio=obbl, note=note)


def _chk(testo: str, critico: bool = False, note: str = "") -> ItemChecklist:
    return ItemChecklist(testo=testo, critico=critico, note=note)


# ---------------------------------------------------------------------------
DECRETO_INGIUNTIVO = TemplateAtto(
    id="decreto_ingiuntivo",
    nome="Decreto Ingiuntivo",
    categoria="CIVILE",
    descrizione="Ricorso per decreto ingiuntivo ex artt. 633 ss. c.p.c.",
    nome_cartella="Decreto_ingiuntivo_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "Il ricorso si deposita tramite redattore atti (Consolle Avvocato / FileSafe / Lextel) "
        "che genera e invia direttamente la busta telematica .enc al tribunale. "
        "PolisWeb/PST serve solo per consultare e scaricare i documenti del fascicolo. "
        "Verificare che l'ufficio destinatario sia abilitato al deposito telematico."
    ),
    documenti=[
        _doc(1,  "Ricorso_per_decreto_ingiuntivo",  "Ricorso principale firmato"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti con firma autenticata"),
        _doc(3,  "Indice_documenti",                "Indice numerato di tutti gli allegati"),
        _doc(4,  "Doc_01_Contratto",                "Contratto o titolo del credito"),
        _doc(5,  "Doc_02_Fattura",                  "Fatture o estratto conto"),
        _doc(6,  "Doc_03_DDT",                      "DDT / bolla di consegna", obbl=False),
        _doc(7,  "Doc_04_Sollecito",                "Sollecito di pagamento", obbl=False),
        _doc(8,  "Doc_05_Diffida",                  "Diffida formale", obbl=False),
        _doc(9,  "Ricevuta_contributo_unificato",   "Ricevuta pagamento contributo unificato",
             note="Verificare importo in base al valore della causa"),
        _doc(10, "Eventuali_altri_allegati",        "Altri documenti utili", obbl=False),
    ],
    checklist=[
        _chk("Ufficio destinatario abilitato al deposito telematico PCT (verifica sul PST)", critico=True),
        _chk("Redattore atti installato e aggiornato (Consolle Avvocato / FileSafe / Lextel)", critico=True),
        _chk("Firma digitale valida e non scaduta (CNS o token USB)", critico=True),
        _chk("Ricorso in PDF/A leggibile e non protetto da password", critico=True),
        _chk("Procura alle liti firmata e scansionata correttamente", critico=True),
        _chk("Contributo unificato pagato (telematicamente o F23) e ricevuta allegata", critico=True),
        _chk("Busta telematica .enc generata correttamente dal redattore atti", critico=True),
        _chk("Busta inviata dal redattore atti e ricevuta di accettazione PEC salvata", critico=True),
        _chk("Valore della causa indicato correttamente nel ricorso"),
        _chk("Documenti allegati nel redattore con tipo corretto (principale / allegato)"),
        _chk("Tutti i PDF si aprono correttamente"),
    ],
)

ISCRIZIONE_A_RUOLO = TemplateAtto(
    id="iscrizione_a_ruolo",
    nome="Iscrizione a Ruolo — Atto di Citazione",
    categoria="CIVILE",
    descrizione="Iscrizione a ruolo dopo notifica dell'atto di citazione.",
    nome_cartella="Iscrizione_ruolo_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "L'iscrizione a ruolo avviene tramite deposito telematico PCT. "
        "Usare il redattore atti per creare e inviare la busta con la nota di iscrizione e gli allegati. "
        "La prova notifica deve essere allegata alla busta. "
        "PolisWeb serve solo per consultare il fascicolo dopo l'accettazione."
    ),
    documenti=[
        _doc(1,  "Atto_introduttivo",               "Citazione o ricorso introduttivo"),
        _doc(2,  "Nota_iscrizione_a_ruolo",         "Nota di iscrizione a ruolo"),
        _doc(3,  "Procura_alle_liti",               "Procura alle liti"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Prova_notifica",                  "Relata di notifica o ricevuta UNEP"),
        _doc(6,  "Ricevuta_accettazione_PEC",       "Ricevuta di accettazione PEC"),
        _doc(7,  "Ricevuta_consegna_PEC",           "Ricevuta di avvenuta consegna PEC"),
        _doc(8,  "Doc_01",                          "Primo documento allegato", obbl=False),
        _doc(9,  "Doc_02",                          "Secondo documento allegato", obbl=False),
        _doc(10, "Ricevuta_contributo_unificato",   "Ricevuta contributo unificato"),
        _doc(11, "Diritti_cancelleria",             "Ricevuta diritti di cancelleria", obbl=False),
    ],
    checklist=[
        _chk("Ufficio abilitato al deposito telematico PCT verificato sul PST", critico=True),
        _chk("Redattore atti installato e aggiornato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Atto introduttivo notificato entro i termini", critico=True),
        _chk("Nota di iscrizione a ruolo compilata correttamente nel redattore", critico=True),
        _chk("Prova notifica completa (relata + ricevute PEC) allegata alla busta", critico=True),
        _chk("Contributo unificato pagato e ricevuta allegata alla busta", critico=True),
        _chk("Busta telematica .enc generata e inviata dal redattore atti", critico=True),
        _chk("Ricevuta di accettazione PEC salvata nel fascicolo"),
        _chk("Numero RG corretto sulla nota di iscrizione"),
        _chk("Tutti i PDF leggibili e non protetti"),
    ],
)

COMPARSA_RISPOSTA = TemplateAtto(
    id="comparsa_risposta",
    nome="Comparsa di Costituzione e Risposta",
    categoria="CIVILE",
    descrizione="Costituzione in giudizio del convenuto.",
    nome_cartella="Comparsa_risposta_{rg}_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "La comparsa si deposita tramite redattore atti (Consolle Avvocato / FileSafe / Lextel) "
        "che crea e invia la busta telematica al tribunale. "
        "Attenzione ai termini: deve essere depositata almeno 20 giorni prima dell'udienza. "
        "PolisWeb serve solo per consultare il fascicolo."
    ),
    documenti=[
        _doc(1,  "Comparsa_costituzione_risposta",  "Comparsa firmata dall'avvocato"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti del convenuto"),
        _doc(3,  "Indice_documenti",                "Indice allegati difensivi"),
        _doc(4,  "Doc_01",                          "Primo documento difensivo", obbl=False),
        _doc(5,  "Doc_02",                          "Secondo documento difensivo", obbl=False),
        _doc(6,  "Doc_03",                          "Terzo documento difensivo", obbl=False),
        _doc(7,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Ufficio abilitato al deposito telematico PCT verificato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Comparsa depositata entro 20 gg prima dell'udienza", critico=True),
        _chk("Procura alle liti del convenuto allegata nella busta", critico=True),
        _chk("Eccezioni processuali proposte a pena di decadenza", critico=True),
        _chk("Domande riconvenzionali dichiarate esplicitamente"),
        _chk("Busta telematica .enc generata e inviata dal redattore atti", critico=True),
        _chk("Ricevuta di accettazione PEC salvata nel fascicolo"),
        _chk("Numero RG e sezione indicati correttamente"),
    ],
)

MEMORIA_DIFENSIVA = TemplateAtto(
    id="memoria_difensiva",
    nome="Memoria / Deposito Atti",
    categoria="CIVILE",
    descrizione="Deposito di memoria difensiva o istruttoria con allegati.",
    nome_cartella="Memoria_{rg}_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "Le memorie si depositano tramite redattore atti (Consolle Avvocato / FileSafe / Lextel) "
        "che crea e invia la busta telematica. "
        "Verificare il tipo di memoria (art. 171-ter n.1/2/3 o altro) e il termine perentorio. "
        "PolisWeb serve solo per consultare il fascicolo."
    ),
    documenti=[
        _doc(1,  "Memoria",                         "Memoria difensiva o istruttoria"),
        _doc(2,  "Indice_allegati",                 "Indice degli allegati"),
        _doc(3,  "Allegato_01",                     "Primo allegato", obbl=False),
        _doc(4,  "Allegato_02",                     "Secondo allegato", obbl=False),
        _doc(5,  "Allegato_03",                     "Terzo allegato", obbl=False),
        _doc(6,  "Allegato_04",                     "Quarto allegato", obbl=False),
    ],
    checklist=[
        _chk("Ufficio abilitato al deposito telematico PCT verificato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Termine perentorio rispettato", critico=True),
        _chk("Tipo di memoria corretto (art. 171-ter n.1 / n.2 / n.3)", critico=True),
        _chk("Numero RG e sezione corretti nell'intestazione"),
        _chk("Allegati caricati nel redattore con tipo 'allegato'", critico=True),
        _chk("Busta telematica .enc generata e inviata dal redattore atti", critico=True),
        _chk("Ricevuta di accettazione PEC salvata nel fascicolo"),
    ],
)

RICORSO_APPELLO = TemplateAtto(
    id="ricorso_appello",
    nome="Ricorso in Appello Civile",
    categoria="CIVILE",
    descrizione="Ricorso in appello avverso sentenza di primo grado.",
    nome_cartella="Appello_{rg}_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "L'appello civile si deposita tramite redattore atti presso la Corte d'Appello (se abilitata). "
        "Il redattore crea e invia la busta telematica direttamente. "
        "PolisWeb serve solo per consultare il fascicolo. Verificare l'abilitazione dell'ufficio sul PST."
    ),
    documenti=[
        _doc(1,  "Ricorso_in_appello",              "Atto di appello"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti per il grado di appello"),
        _doc(3,  "Sentenza_impugnata",              "Sentenza di primo grado"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Prova_notifica_sentenza",         "Notifica della sentenza (dies a quo)", obbl=False),
        _doc(6,  "Ricevuta_contributo_unificato",   "Contributo unificato appello"),
        _doc(7,  "Doc_01_nuovi",                    "Documenti nuovi ex art. 345 c.p.c.", obbl=False),
        _doc(8,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Ufficio (Corte d'Appello) abilitato al deposito telematico PCT verificato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Termine rispettato (30 gg da notifica sentenza, 6 mesi da deposito)", critico=True),
        _chk("Corte d'Appello competente indicata correttamente", critico=True),
        _chk("Sentenza impugnata allegata integralmente", critico=True),
        _chk("Motivi di appello specifici ex art. 342 c.p.c.", critico=True),
        _chk("Contributo unificato per appello pagato e allegato", critico=True),
        _chk("Procura alle liti specifica per il grado di appello"),
        _chk("Busta telematica .enc generata e inviata dal redattore atti", critico=True),
        _chk("Istanza di sospensiva se urgente"),
        _chk("Ricevuta di accettazione PEC salvata nel fascicolo"),
    ],
)

OPPOSIZIONE_DI = TemplateAtto(
    id="opposizione_decreto_ingiuntivo",
    nome="Opposizione a Decreto Ingiuntivo",
    categoria="CIVILE",
    descrizione="Atto di opposizione ex art. 645 c.p.c.",
    nome_cartella="Opposizione_DI_{rg}_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "L'opposizione si introduce con citazione notificata; "
        "l'iscrizione a ruolo avviene poi tramite redattore atti (busta telematica PCT). "
        "PolisWeb serve solo per consultare il fascicolo."
    ),
    documenti=[
        _doc(1,  "Atto_di_opposizione",             "Citazione in opposizione"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti dell'opponente"),
        _doc(3,  "Copia_decreto_ingiuntivo",        "Decreto ingiuntivo opposto"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Doc_01",                          "Primo documento difensivo", obbl=False),
        _doc(6,  "Doc_02",                          "Secondo documento difensivo", obbl=False),
        _doc(7,  "Ricevuta_contributo_unificato",   "Contributo unificato se dovuto", obbl=False),
    ],
    checklist=[
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Opposizione proposta entro 40 gg dalla notifica del DI", critico=True),
        _chk("Decreto ingiuntivo integralmente allegato nella busta", critico=True),
        _chk("Istanza di sospensiva dell'esecutorietà se necessaria", critico=True),
        _chk("Tribunale competente verificato (art. 645 c.p.c.)"),
        _chk("Procura alle liti presente"),
        _chk("Busta telematica .enc generata e inviata dal redattore atti", critico=True),
        _chk("Ricevuta di accettazione PEC salvata nel fascicolo"),
    ],
)

ATTO_PRECETTO = TemplateAtto(
    id="atto_precetto",
    nome="Atto di Precetto",
    categoria="ESECUTIVO",
    descrizione="Precetto ex art. 480 c.p.c. precedente all'esecuzione forzata.",
    nome_cartella="Precetto_{parte}_{data}",
    canale="CARTACEO",
    nota_canale=(
        "Il precetto non si deposita in tribunale: va notificato al debitore "
        "tramite ufficiale giudiziario (UNEP) o, se consentito, a mezzo PEC. "
        "Non è richiesto redattore atti né deposito telematico PCT."
    ),
    documenti=[
        _doc(1,  "Atto_di_precetto",                "Precetto con intimazione di pagamento"),
        _doc(2,  "Titolo_esecutivo",                "Sentenza / DI / altro titolo"),
        _doc(3,  "Formula_esecutiva",               "Copia con formula esecutiva", obbl=False),
        _doc(4,  "Procura_alle_liti",               "Procura alle liti"),
        _doc(5,  "Eventuali_altri_documenti",       "Altri documenti", obbl=False),
    ],
    checklist=[
        _chk("Titolo esecutivo valido e non prescritto", critico=True),
        _chk("Formula esecutiva apposta (per sentenze)", critico=True),
        _chk("Importo credito + interessi + spese calcolato correttamente", critico=True),
        _chk("Termine di 10 gg per adempiere indicato"),
        _chk("Elezione di domicilio indicata"),
        _chk("Precetto notificato correttamente prima di procedere all'esecuzione"),
        _chk("Tutti i PDF leggibili"),
    ],
)

PIGNORAMENTO = TemplateAtto(
    id="pignoramento",
    nome="Atto di Pignoramento",
    categoria="ESECUTIVO",
    descrizione="Pignoramento mobiliare, immobiliare o presso terzi.",
    nome_cartella="Pignoramento_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "Il pignoramento immobiliare e presso terzi si iscrive a ruolo tramite redattore atti (PCT). "
        "Il pignoramento mobiliare avviene tramite ufficiale giudiziario (UNEP); "
        "l'iscrizione a ruolo successiva avviene anch'essa con il redattore atti. "
        "PolisWeb serve solo per consultare il fascicolo esecutivo."
    ),
    documenti=[
        _doc(1,  "Atto_di_pignoramento",            "Atto di pignoramento"),
        _doc(2,  "Titolo_esecutivo",                "Titolo esecutivo"),
        _doc(3,  "Copia_precetto_notificato",       "Precetto notificato con relata"),
        _doc(4,  "Procura_alle_liti",               "Procura alle liti"),
        _doc(5,  "Nota_iscrizione_a_ruolo",         "Nota di iscrizione ruolo esecutivo", obbl=False),
        _doc(6,  "Ricevuta_contributo_unificato",   "Contributo unificato esecuzione", obbl=False),
        _doc(7,  "Eventuali_altri_documenti",       "Altri documenti", obbl=False),
    ],
    checklist=[
        _chk("Precetto notificato da almeno 10 gg (salvo urgenza)", critico=True),
        _chk("Titolo esecutivo valido allegato", critico=True),
        _chk("Tipo pignoramento corretto (mobiliare / immobiliare / P.T.)", critico=True),
        _chk("Per P.T.: terzo pignorato correttamente identificato"),
        _chk("Per immobiliare: estremi catastali corretti", critico=True),
        _chk("Contributo unificato per esecuzione pagato"),
        _chk("Iscrizione a ruolo eseguita entro 30 gg dal pignoramento"),
        _chk("Tutti i PDF leggibili"),
    ],
)

RICORSO_CAUTELARE = TemplateAtto(
    id="ricorso_cautelare",
    nome="Ricorso Cautelare / Sequestro",
    categoria="CAUTELARE",
    descrizione="Ricorso per sequestro conservativo, giudiziario o provvedimento d'urgenza.",
    nome_cartella="Cautelare_{parte}_{data}",
    canale="PCT_TELEMATICO",
    endpoint_deposito="polisWeb_home",
    nota_canale=(
        "Il ricorso cautelare si deposita tramite redattore atti (PCT): "
        "il redattore crea e invia la busta telematica direttamente al tribunale. "
        "Se urgente (inaudita altera parte), verificare con la cancelleria le modalità "
        "per il deposito urgente fuori orario. PolisWeb serve solo per consultare il fascicolo."
    ),
    documenti=[
        _doc(1,  "Ricorso_cautelare",               "Ricorso ex art. 700 c.p.c. o per sequestro"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti"),
        _doc(3,  "Indice_documenti",                "Indice allegati"),
        _doc(4,  "Doc_01_Prova_periculum",          "Prove del periculum in mora"),
        _doc(5,  "Doc_02_Prova_fumus",              "Prove del fumus boni iuris"),
        _doc(6,  "Doc_03",                          "Ulteriori prove", obbl=False),
        _doc(7,  "Ricevuta_contributo_unificato",   "Contributo unificato", obbl=False),
        _doc(8,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Ufficio abilitato al deposito telematico PCT verificato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Periculum in mora concretamente argomentato e documentato", critico=True),
        _chk("Fumus boni iuris documentato", critico=True),
        _chk("Busta telematica .enc generata e inviata dal redattore atti", critico=True),
        _chk("Ricevuta di accettazione PEC salvata nel fascicolo"),
        _chk("Competenza del giudice verificata"),
        _chk("Istanza inaudita altera parte se urgente (verifica modalità ufficio)"),
        _chk("Cauzione eventuale valutata"),
    ],
)

RICORSO_TAR = TemplateAtto(
    id="ricorso_tar",
    nome="Ricorso al TAR",
    categoria="AMMINISTRATIVO",
    descrizione="Ricorso al Tribunale Amministrativo Regionale.",
    nome_cartella="Ricorso_TAR_{parte}_{data}",
    canale="PAT_AMMINISTRATIVO",
    endpoint_deposito="pat_home",
    nota_canale=(
        "Il ricorso TAR si deposita tramite il Portale Atti Amministrativi (PAT) "
        "con firma digitale CAdES (.p7m). Non si usa il redattore atti civile né PolisWeb."
    ),
    documenti=[
        _doc(1,  "Ricorso_TAR",                     "Atto introduttivo del giudizio"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti"),
        _doc(3,  "Provvedimento_impugnato",         "Atto amministrativo impugnato"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Doc_01_Prova_interesse",          "Prova dell'interesse a ricorrere"),
        _doc(6,  "Doc_02",                          "Secondo documento", obbl=False),
        _doc(7,  "Ricevuta_contributo_unificato",   "Contributo unificato TAR"),
        _doc(8,  "Ricevuta_CPA",                    "Contributo PAT / CPA", obbl=False),
        _doc(9,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Accesso al Portale PAT funzionante (pat_home in HACS)", critico=True),
        _chk("Termine di 60 gg dalla notifica/pubblicazione rispettato", critico=True),
        _chk("TAR territorialmente competente verificato", critico=True),
        _chk("Atto impugnato allegato integralmente", critico=True),
        _chk("Contributo unificato TAR pagato (importo diverso dal civile)", critico=True),
        _chk("Contributo PAT / CPA pagato se dovuto"),
        _chk("Interesse a ricorrere chiaramente esposto"),
        _chk("Vizi di legittimità indicati (incompetenza, eccesso di potere, violazione di legge)"),
        _chk("Deposito effettuato sul portale PAT e ricevuta salvata", critico=True),
        _chk("Istanza sospensiva se urgente"),
    ],
)

MEDIAZIONE = TemplateAtto(
    id="mediazione",
    nome="Mediazione / Conciliazione",
    categoria="STRAGIUDIZIALE",
    descrizione="Istanza di mediazione obbligatoria o facoltativa.",
    nome_cartella="Mediazione_{parte}_{data}",
    canale="CARTACEO",
    nota_canale=(
        "L'istanza di mediazione si deposita direttamente presso l'organismo di mediazione "
        "(di persona, via email o PEC secondo le regole dell'organismo). "
        "Non si usa PCT, PDP né PAT."
    ),
    documenti=[
        _doc(1,  "Istanza_mediazione",              "Istanza di mediazione all'organismo"),
        _doc(2,  "Procura_alla_mediazione",         "Procura speciale per la mediazione", obbl=False),
        _doc(3,  "Doc_01_Contratto",                "Contratto o documento base della controversia"),
        _doc(4,  "Doc_02",                          "Secondo documento", obbl=False),
        _doc(5,  "Ricevuta_pagamento_spese",        "Ricevuta pagamento spese di avvio", obbl=False),
        _doc(6,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Materia soggetta a mediazione obbligatoria verificata", critico=True),
        _chk("Organismo di mediazione accreditato scelto"),
        _chk("Istanza compilata con tutti i dati delle parti"),
        _chk("Spese di avvio pagate se richieste"),
        _chk("Termine sospeso per mediazione annotato in agenda"),
        _chk("Tutti i PDF leggibili"),
    ],
)

APPELLO_PENALE = TemplateAtto(
    id="appello_penale",
    nome="Appello Penale",
    categoria="PENALE",
    descrizione="Atto di appello avverso sentenza penale di primo grado.",
    nome_cartella="Appello_penale_{rg}_{parte}_{data}",
    canale="PDP_PENALE",
    endpoint_deposito="pdp_home",
    nota_canale=(
        "L'appello penale si deposita tramite il Portale Deposito Atti Penali (PDP) "
        "con firma digitale CAdES (.p7m). Non si usa il redattore atti civile né PolisWeb."
    ),
    documenti=[
        _doc(1,  "Atto_di_appello",                 "Motivi di appello"),
        _doc(2,  "Procura_speciale",                "Procura speciale autenticata", obbl=False),
        _doc(3,  "Sentenza_impugnata",              "Sentenza di primo grado"),
        _doc(4,  "Indice_documenti",                "Indice allegati", obbl=False),
        _doc(5,  "Doc_01_nuove_prove",              "Nuove prove ex art. 603 c.p.p.", obbl=False),
        _doc(6,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Accesso al Portale PDP Penale funzionante (pdp_home in HACS)", critico=True),
        _chk("Termine di 15 gg dal deposito motivazione rispettato", critico=True),
        _chk("Corte d'Appello penale competente verificata", critico=True),
        _chk("Motivi specifici ex art. 581 c.p.p. indicati", critico=True),
        _chk("Sentenza impugnata allegata"),
        _chk("Deposito effettuato sul portale PDP e ricevuta salvata", critico=True),
        _chk("Istanza misure cautelari se necessaria"),
        _chk("Procura speciale autenticata se imputato non presente"),
    ],
)

# ---------------------------------------------------------------------------
TUTTI_I_TEMPLATE: List[TemplateAtto] = [
    DECRETO_INGIUNTIVO,
    ISCRIZIONE_A_RUOLO,
    COMPARSA_RISPOSTA,
    MEMORIA_DIFENSIVA,
    RICORSO_APPELLO,
    OPPOSIZIONE_DI,
    ATTO_PRECETTO,
    PIGNORAMENTO,
    RICORSO_CAUTELARE,
    RICORSO_TAR,
    MEDIAZIONE,
    APPELLO_PENALE,
]

CATEGORIE = {
    "CIVILE":         "Civile",
    "ESECUTIVO":      "Esecutivo",
    "CAUTELARE":      "Cautelare",
    "PENALE":         "Penale",
    "AMMINISTRATIVO": "Amministrativo",
    "STRAGIUDIZIALE": "Stragiudiziale",
}

CAT_ICON = {
    "CIVILE":         "bi-balance-scale",
    "ESECUTIVO":      "bi-hammer",
    "CAUTELARE":      "bi-shield-exclamation",
    "PENALE":         "bi-shield-fill",
    "AMMINISTRATIVO": "bi-building",
    "STRAGIUDIZIALE": "bi-handshake",
}

CAT_COL = {
    "CIVILE":         "primary",
    "ESECUTIVO":      "warning",
    "CAUTELARE":      "danger",
    "PENALE":         "dark",
    "AMMINISTRATIVO": "info",
    "STRAGIUDIZIALE": "success",
}


def get_template(id_template: str) -> Optional[TemplateAtto]:
    return next((t for t in TUTTI_I_TEMPLATE if t.id == id_template), None)


def nome_cartella_compilato(template: TemplateAtto, parte: str = "",
                             rg: str = "", data: str = "") -> str:
    import re
    from datetime import date as _date
    d = data or _date.today().isoformat()
    parte_safe = re.sub(r"[^\w]", "_", parte).strip("_") if parte else "Controparte"
    rg_safe    = re.sub(r"[^\w]", "_", rg).strip("_")    if rg    else "RG"
    return (template.nome_cartella
            .replace("{parte}", parte_safe)
            .replace("{rg}", rg_safe)
            .replace("{data}", d))
