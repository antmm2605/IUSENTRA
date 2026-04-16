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
    # Tipo atto predefinito per il modal deposito (pre-compila la select)
    tipo_atto_default: str = ""
    # Note sul canale/redattore
    nota_canale: str = ""
    documenti: List[DocumentoRichiesto] = field(default_factory=list)
    checklist: List[ItemChecklist] = field(default_factory=list)
    note_generali: str = ""


CANALE_LABEL = {
    "PCT_TELEMATICO":     "Deposito telematico PCT",
    "PDP_PENALE":         "Portale Deposito Penale (PDP)",
    "PAT_AMMINISTRATIVO": "Portale Atti Amministrativi (PAT)",
    "PTT_TRIBUTARIO":     "Portale PTT / SIGIT (MEF)",
    "PEC":                "Deposito a mezzo PEC",
    "CARTACEO":           "Deposito cartaceo / cancelleria",
}

CANALE_ICON = {
    "PCT_TELEMATICO":     "bi-send-fill",
    "PDP_PENALE":         "bi-shield-fill",
    "PAT_AMMINISTRATIVO": "bi-building",
    "PTT_TRIBUTARIO":     "bi-receipt-cutoff",
    "PEC":                "bi-envelope-fill",
    "CARTACEO":           "bi-printer-fill",
}

CANALE_COL = {
    "PCT_TELEMATICO":     "primary",
    "PDP_PENALE":         "dark",
    "PAT_AMMINISTRATIVO": "info",
    "PTT_TRIBUTARIO":     "warning",
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
    tipo_atto_default="DECRETO_INGIUNTIVO",
    nota_canale=(
        "Il ricorso si deposita tramite redattore atti (Consolle Avvocato / FileSafe / Lextel) "
        "che genera e invia direttamente la busta telematica .enc al tribunale. "
        "PolisWeb/PST serve solo per consultare e scaricare i documenti del fascicolo. "
        "Verificare che l'ufficio destinatario sia abilitato al deposito telematico."
    ),
    documenti=[
        _doc(1,  "Ricorso_per_decreto_ingiuntivo",  "Ricorso principale firmato digitalmente (CAdES .p7m o PAdES)"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti con firma autenticata"),
        _doc(3,  "Indice_documenti",                "Indice numerato di tutti gli allegati"),
        _doc(4,  "Doc_01_Contratto",                "Contratto o titolo del credito (art. 634 c.p.c.)"),
        _doc(5,  "Doc_02_Fattura",                  "Fatture o estratto conto"),
        _doc(6,  "Doc_03_DDT",                      "DDT / bolla di consegna", obbl=False),
        _doc(7,  "Doc_04_Sollecito",                "Sollecito di pagamento", obbl=False),
        _doc(8,  "Doc_05_Diffida",                  "Diffida formale", obbl=False),
        _doc(9,  "Ricevuta_contributo_unificato",   "Ricevuta pagamento contributo unificato",
             note="Pagabile via PagoPA su portale Giustizia — verificare importo in base al valore della causa"),
        _doc(10, "Nota_calcolo_interessi",          "Nota di calcolo interessi moratori/anatocistici (D.Lgs. 231/2002)",
             obbl=False,
             note="Obbligatoria se si chiedono interessi moratori — includere tasso, base di calcolo, periodo"),
        _doc(11, "Certificato_CCIAA",              "Visura / Certificato CCIAA del debitore (se società)",
             obbl=False,
             note="Richiesto quando il debitore è una persona giuridica — verifica poteri di rappresentanza"),
        _doc(12, "Estratto_notarile_autentico",    "Estratto notarile autentico del titolo (art. 634 c.p.c.)",
             obbl=False,
             note="Necessario se il titolo del credito è un atto notarile (es. mutuo, compravendita)"),
        _doc(13, "Eventuali_altri_allegati",        "Altri documenti utili", obbl=False),
    ],
    checklist=[
        _chk("Ufficio destinatario abilitato al deposito telematico PCT (verifica sul PST)", critico=True),
        _chk("Redattore atti installato e aggiornato (Consolle Avvocato / FileSafe / Lextel)", critico=True),
        _chk("Firma digitale valida e non scaduta (CNS o token USB)", critico=True),
        _chk("Tutti i PDF nel formato PDF/A-1b (non protetti da password, testo selezionabile)", critico=True),
        _chk("Procura alle liti firmata e scansionata correttamente", critico=True),
        _chk("Contributo unificato pagato via PagoPA o F23 — ricevuta allegata", critico=True),
        _chk("Se debitore è società: visura CCIAA allegata (verifica poteri firma)", critico=True,
             note="Senza visura il DI può essere opposto per difetto di legittimazione"),
        _chk("Se richiesti interessi moratori: Nota calcolo interessi allegata (D.Lgs. 231/2002)",
             note="Indicare tasso BCE + 8 pp per crediti commerciali, tasso contrattuale per altri"),
        _chk("Nomi file senza caratteri speciali (no spazi, #, %, &, ', \", accenti)", critico=True),
        _chk("Peso totale della busta .enc < 30 MB", critico=True,
             note="Se supera, dividere in più depositi o comprimere i PDF"),
        _chk("Busta telematica .enc generata correttamente dal redattore atti", critico=True),
        _chk("Busta inviata dal redattore atti e ricevuta di accettazione PEC salvata", critico=True),
        _chk("Ricevuta PagoPA: allegare file .xml (o PDF con codice IUV/hash) — NON screenshot del bonifico",
             critico=True,
             note="Il sistema PCT verifica l'hash del pagamento — lo screenshot non ha valore probatorio"),
        _chk("Se procura su foglio separato: atto principale riporta impronta hash della procura o riferimento esplicito",
             note="Art. 83 c.p.c. e D.M. 44/2011: l'atto deve fare espresso riferimento alla procura separata"),
        _chk("Privacy/GDPR: estratti conto o documenti con dati di terzi non coinvolti → oscurare (omissis)",
             note="Oscurare nomi/codici fiscali di persone estranee alla causa prima della scansione"),
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
    tipo_atto_default="CITAZIONE",
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
        _doc(10, "Ricevuta_contributo_unificato",   "Ricevuta contributo unificato",
             note="Pagabile via PagoPA su portale Giustizia"),
        _doc(11, "Diritti_cancelleria",             "Ricevuta diritti di cancelleria", obbl=False),
    ],
    checklist=[
        _chk("Ufficio abilitato al deposito telematico PCT verificato sul PST", critico=True),
        _chk("Redattore atti installato e aggiornato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Atto introduttivo notificato entro i termini", critico=True),
        _chk("Tutti i PDF nel formato PDF/A-1b (non protetti, testo selezionabile)", critico=True),
        _chk("Attestazione di conformità per atti originariamente cartacei (art. 16-undecies D.L. 179/2012)",
             critico=True,
             note="Obbligatoria per: sentenze cartacee scansionate, atti autenticati su carta, procure notarili"),
        _chk("Nota di iscrizione a ruolo compilata correttamente nel redattore", critico=True),
        _chk("Prova notifica completa (relata + ricevute PEC) allegata alla busta", critico=True),
        _chk("Contributo unificato pagato via PagoPA e ricevuta allegata — file .xml o PDF con hash (non screenshot)",
             critico=True),
        _chk("REGINDE/INIPEC: PEC della controparte estratta SOLO da registro ufficiale (L. 53/94)",
             critico=True,
             note="REGINDE per avvocati (pst.giustizia.it), INIPEC per imprese (inipec.gov.it) — notifica a PEC da sito web = NULLA"),
        _chk("Allegare certificato di ricerca PEC (screenshot REGINDE/INIPEC con data e ora della ricerca)",
             note="È la prova che l'indirizzo PEC è tratto da registro pubblico — conservarlo nel fascicolo"),
        _chk("File .eml o .msg delle ricevute PEC allegati (non solo i PDF delle ricevute)",
             note="Il .eml è la prova originale firmata dal gestore PEC — il PDF è solo una conversione"),
        _chk("Se procura su foglio separato: atto introduce l'impronta hash della procura",
             note="Art. 83 c.p.c.: collegare formalmente l'atto alla procura separata"),
        _chk("Privacy/GDPR: documenti con dati di terzi non coinvolti → oscurare (omissis) prima del deposito"),
        _chk("Nomi file senza caratteri speciali (no spazi, #, %, &, ', \", accenti)", critico=True),
        _chk("Peso totale della busta .enc < 30 MB", critico=True),
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
    tipo_atto_default="COMPARSA",
    nota_canale=(
        "La comparsa si deposita tramite redattore atti (Consolle Avvocato / FileSafe / Lextel) "
        "che crea e invia la busta telematica al tribunale. "
        "Attenzione ai termini del rito ordinario post-Cartabia: la costituzione del convenuto "
        "deve avvenire almeno 70 giorni prima dell'udienza indicata nell'atto di citazione. "
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
        _chk("Comparsa depositata entro 70 gg prima dell'udienza nel rito ordinario post-Cartabia", critico=True),
        _chk("Procura alle liti del convenuto allegata nella busta", critico=True),
        _chk("Eccezioni processuali proposte a pena di decadenza", critico=True),
        _chk("Domande riconvenzionali dichiarate esplicitamente"),
        _chk("Sinteticità D.M. 110/2023 (cause < €500.000): comparsa entro 80.000 caratteri ≈ 40 pp (esclusi spazi). Se supera: Indice Ipertestuale + nota motivazione",
             note="D.M. 110/2023 art. 3 lett. a) — stessa soglia di citazione e memoria difensiva. Il mancato rispetto può comportare sanzioni sulle spese di lite (art. 46 disp. att. c.p.c.)"),
        _chk("Tutti i PDF nel formato PDF/A-1b", critico=True),
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
    tipo_atto_default="MEMORIA",
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
        _chk("Sinteticità D.M. 110/2023 (cause < €500.000): memorie ex art. 171-ter n.1/2 e difensive → 80.000 caratteri ≈ 40 pp; repliche e altri atti → 50.000 caratteri ≈ 26 pp (esclusi spazi)",
             critico=True,
             note="D.M. 110/2023 artt. 3 e 5 — se si supera: Indice Ipertestuale + nota sintetica di giustificazione nell'intestazione dell'atto. Senza, rischio sanzione spese"),
        _chk("Se memoria supera il limite: Indice Ipertestuale in apertura con link ai paragrafi + breve nota giustificativa",
             note="Art. 5 D.M. 110/2023: la nota di giustificazione va inserita dopo l'intestazione, prima del testo"),
        _chk("Tutti i PDF nel formato PDF/A-1b", critico=True),
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
    tipo_atto_default="APPELLO",
    nota_canale=(
        "L'appello civile si deposita tramite redattore atti presso la Corte d'Appello (se abilitata). "
        "Il redattore crea e invia la busta telematica direttamente. "
        "PolisWeb serve solo per consultare il fascicolo. Verificare l'abilitazione dell'ufficio sul PST."
    ),
    documenti=[
        _doc(1,  "Ricorso_in_appello",              "Atto di appello"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti per il grado di appello"),
        _doc(3,  "Sentenza_impugnata_copia_autentica", "Copia autentica della sentenza impugnata (art. 348 c.p.c.)",
             note="Deve essere copia autentica rilasciata dalla cancelleria — non basta la copia informale"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Relata_notifica_sentenza",        "Relata di notifica della sentenza (dies a quo)",
             obbl=False,
             note="Allegare se la sentenza è stata notificata — determina il termine breve di 30 gg"),
        _doc(6,  "Ricevuta_contributo_unificato",   "Contributo unificato appello",
             note="Pagabile via PagoPA — importo aumentato rispetto al primo grado"),
        _doc(7,  "Doc_01_nuovi",                    "Documenti nuovi ex art. 345 c.p.c.", obbl=False),
        _doc(8,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Ufficio (Corte d'Appello) abilitato al deposito telematico PCT verificato", critico=True),
        _chk("Firma digitale valida e non scaduta", critico=True),
        _chk("Termine rispettato: 30 gg da notifica sentenza oppure 6 mesi dal deposito", critico=True,
             note="Verificare se la sentenza è stata notificata — in tal caso vale il termine breve"),
        _chk("Corte d'Appello competente indicata correttamente", critico=True),
        _chk("Sentenza impugnata allegata in COPIA AUTENTICA (art. 348 c.p.c.) — non copia informale",
             critico=True,
             note="Richiedere copia autentica alla cancelleria del tribunale di primo grado"),
        _chk("Relata di notifica sentenza allegata (per verificare dies a quo del termine breve)",
             note="Se la sentenza è stata notificata, la relata è fondamentale per la verifica dei termini"),
        _chk("Tutti i PDF nel formato PDF/A-1b", critico=True),
        _chk("Motivi di appello specifici ex art. 342 c.p.c.", critico=True),
        _chk("Sinteticità D.M. 110/2023 (cause < €500.000): appello civile → 80.000 caratteri ≈ 40 pp. Se supera: Indice Ipertestuale + nota giustificazione nell'intestazione",
             note="D.M. 110/2023 art. 3 lett. a) — gli 'atti introduttivi dei giudizi di impugnazione' sono nella stessa soglia di citazione e comparsa. Alcune Corti d'Appello hanno protocolli locali più restrittivi"),
        _chk("REGINDE/INIPEC: se si notifica l'appello in proprio (L. 53/94), PEC controparte da registro ufficiale",
             critico=True,
             note="Per avvocati: REGINDE — per imprese: INIPEC — mai indirizzi PEC da siti web (notifica nulla)"),
        _chk("Ricevuta PagoPA: file .xml o PDF con hash — non screenshot", critico=True),
        _chk("Contributo unificato per appello pagato via PagoPA e allegato", critico=True),
        _chk("Procura alle liti specifica per il grado di appello"),
        _chk("Peso totale della busta .enc < 30 MB", critico=True),
        _chk("Nomi file senza caratteri speciali", critico=True),
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
    tipo_atto_default="OPPOSIZIONE",
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
    tipo_atto_default="ALTRO",
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
    tipo_atto_default="RICORSO",
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
    tipo_atto_default="RICORSO",
    nota_canale=(
        "⚠️ DAL 1° FEBBRAIO 2026: deposito ESCLUSIVAMENTE tramite Formweb (nuovo portale PAT) "
        "con firma PAdES sul 'RiepilogoDepositoFormweb' generato dal sistema — NON si usa CAdES .p7m. "
        "La PEC è rimasta solo modalità d'emergenza (sistemi down). "
        "Accesso: SPID / CIE / CNS su portale-avvocato.giustizia-amministrativa.it. "
        "Normativa: D.P.C.S. 9 maggio 2025 (GU n. 111/2025). Non si usa PCT né PolisWeb."
    ),
    documenti=[
        _doc(1,  "Ricorso_TAR",                     "Atto introduttivo del giudizio"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti"),
        _doc(3,  "Provvedimento_impugnato",         "Atto amministrativo impugnato"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Doc_01_Prova_interesse",          "Prova dell'interesse a ricorrere"),
        _doc(6,  "Doc_02",                          "Secondo documento", obbl=False),
        _doc(7,  "Ricevuta_contributo_unificato",   "Contributo unificato TAR",
             note="Importo diverso dal civile — verificare tabella aggiornata"),
        _doc(8,  "Ricevuta_CPA",                    "Contributo PAT / CPA", obbl=False),
        _doc(9,  "IFU_Istanza_Fissazione_Udienza",  "Istanza di Fissazione dell'Udienza (IFU)",
             obbl=False,
             note="ATTENZIONE: va depositata entro 1 anno dal ricorso (art. 71-bis c.p.a.) — senza IFU il ricorso viene dichiarato perento"),
        _doc(10, "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("DAL 1/2/2026 — Deposito tramite FORMWEB (non più PEC): accedere a portale-avvocato.giustizia-amministrativa.it",
             critico=True,
             note="La modalità PEC è rimasta solo per emergenza (sistemi down); l'upload diretto è stato abolito"),
        _chk("Firma PAdES (non CAdES) sul 'RiepilogoDepositoFormweb' generato dal sistema",
             critico=True,
             note="Formweb genera un PDF riepilogativo da firmare PAdES — il formato .p7m (CAdES) NON è ammesso su Formweb (D.P.C.S. 9/5/2025 art. 6-bis Allegato 2)"),
        _chk("Accesso SPID / CIE / CNS verificato prima della scadenza", critico=True),
        _chk("Termine di 60 gg dalla notifica/pubblicazione rispettato", critico=True),
        _chk("TAR territorialmente competente verificato", critico=True),
        _chk("Atto impugnato allegato integralmente", critico=True),
        _chk("Tutti i PDF nel formato PDF/A-1b (non protetti, testo selezionabile)", critico=True),
        _chk("Attestazione di conformità per atti originariamente cartacei (art. 16-undecies D.L. 179/2012)",
             critico=True,
             note="Obbligatoria per atti amministrativi cartacei scansionati"),
        _chk("Contributo unificato TAR pagato (importo diverso dal civile)", critico=True),
        _chk("Contributo PAT / CPA pagato se dovuto"),
        _chk("CRITICO — Istanza di Fissazione Udienza (IFU): depositarla entro 1 anno dal ricorso",
             critico=True,
             note="Art. 71-bis c.p.a.: senza IFU il ricorso è dichiarato perento — inserire subito scadenza in agenda"),
        _chk("Interesse a ricorrere chiaramente esposto"),
        _chk("Vizi di legittimità indicati (incompetenza, eccesso di potere, violazione di legge)"),
        _chk("Nomi file senza caratteri speciali", critico=True),
        _chk("Peso totale del deposito < 30 MB", critico=True),
        _chk("Deposito effettuato sul portale PAT e ricevuta salvata", critico=True),
        _chk("Sinteticità (C.P.A. art. 26 co. 1): ricorso TAR entro i limiti del protocollo del TAR adito. Se supera: Indice Ipertestuale",
             note="Diversi TAR hanno adottato protocolli propri — verificare sul sito del TAR competente. Conseguenza: condanna alle spese aggravata"),
        _chk("Scadenza IFU inserita immediatamente in agenda (1 anno dal deposito ricorso)", critico=True),
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
        _doc(6,  "Accordo_mediazione_firmato",      "Accordo di mediazione firmato digitalmente da tutte le parti",
             obbl=False,
             note="Al termine della mediazione positiva: firme CAdES/PAdES di tutte le parti e dei rispettivi avvocati — vale come titolo esecutivo (art. 12 D.Lgs. 28/2010)"),
        _doc(7,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Materia soggetta a mediazione obbligatoria verificata", critico=True),
        _chk("Organismo di mediazione accreditato al Ministero della Giustizia scelto"),
        _chk("Istanza compilata con tutti i dati delle parti"),
        _chk("Spese di avvio pagate se richieste"),
        _chk("Termine sospeso per mediazione annotato in agenda"),
        _chk("Se accordo raggiunto: firme digitali di TUTTE le parti e di TUTTI gli avvocati sull'accordo",
             critico=True,
             note="Art. 12 D.Lgs. 28/2010: l'accordo deve essere firmato dalle parti e dai loro avvocati — senza le firme degli avvocati non è titolo esecutivo"),
        _chk("Accordo di mediazione conforme a norme imperative, ordine pubblico e buon costume",
             critico=True,
             note="Il mediatore deve verificare la conformità — l'accordo nullo non vale come titolo esecutivo"),
        _chk("Accordo omologato dal tribunale se necessario per l'esecutività"),
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
    tipo_atto_default="APPELLO",
    nota_canale=(
        "DAL 1/1/2025: deposito obbligatorio tramite PDP per Procure e Tribunali (art. 111-bis c.p.p.). "
        "DAL 1/1/2026: obbligatorio anche per GdP, Trib. Minorenni, Trib. Sorveglianza, esecuzione. "
        "Proroga al 31/3/2026 per modalità alternative in alcune sedi (D.M. 30/12/2025 n. 206). "
        "Firma digitale: CAdES (.p7m). Non si usa il redattore atti civile né PolisWeb. "
        "Prerequisito: nomina difensore già accettata nel PDP (procedimento visibile nell'elenco)."
    ),
    documenti=[
        _doc(1,  "Atto_di_appello",                 "Motivi di appello firmati digitalmente (CAdES .p7m)"),
        _doc(2,  "Nomina_difensore",               "Nomina difensore / sostituzione difensore",
             obbl=False,
             note="Obbligatoria se difensore diverso da quello del primo grado o se non già nominato"),
        _doc(3,  "Procura_speciale",                "Procura speciale autenticata", obbl=False),
        _doc(4,  "Sentenza_impugnata",              "Sentenza di primo grado"),
        _doc(5,  "Indice_documenti",                "Indice allegati", obbl=False),
        _doc(6,  "Doc_01_nuove_prove",              "Nuove prove ex art. 603 c.p.p.", obbl=False),
        _doc(7,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta — PDP accetta solo CAdES, non PAdES",
             critico=True,
             note="Il Portale PDP Penale richiede CAdES (.p7m) — verificare che il redattore non produca PAdES"),
        _chk("Accesso al Portale PDP Penale funzionante (pdp_home in IUSENTRA)", critico=True),
        _chk("Termine di 15 gg dal deposito della motivazione rispettato", critico=True,
             note="Termine perentorio — verificare data deposito motivazione (non data lettura dispositivo)"),
        _chk("Corte d'Appello penale competente verificata", critico=True),
        _chk("Nomina difensore allegata se diverso da primo grado", critico=True),
        _chk("Motivi specifici ex art. 581 c.p.p. indicati", critico=True),
        _chk("Sentenza impugnata allegata"),
        _chk("Tutti i PDF nel formato PDF/A-1b", critico=True),
        _chk("Nomi file senza caratteri speciali", critico=True),
        _chk("Peso totale del deposito < 30 MB", critico=True),
        _chk("Deposito effettuato sul portale PDP e ricevuta salvata", critico=True),
        _chk("Istanza misure cautelari se necessaria"),
        _chk("Procura speciale autenticata se imputato non presente"),
    ],
)

RICORSO_TRIBUTARIO = TemplateAtto(
    id="ricorso_tributario",
    nome="Ricorso Tributario (CTP/CGT primo grado)",
    categoria="TRIBUTARIO",
    descrizione="Ricorso alla Corte di Giustizia Tributaria di primo grado (ex CTP).",
    nome_cartella="Ricorso_tributario_{parte}_{data}",
    canale="PTT_TRIBUTARIO",
    endpoint_deposito="sigit_home",
    tipo_atto_default="RICORSO",
    nota_canale=(
        "Il ricorso tributario si deposita tramite il Portale di Trasmissione Telematica (PTT) "
        "del MEF — sistema SIGIT — con firma digitale CAdES (.p7m). "
        "Normativa: D.Lgs. 546/1992, D.M. 163/2013 (processo tributario telematico). "
        "Non si usa PCT, PDP né PAT."
    ),
    documenti=[
        _doc(1,  "Ricorso_tributario",              "Ricorso introduttivo firmato CAdES (.p7m)"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti (se difensore abilitato)"),
        _doc(3,  "Atto_impugnato",                  "Avviso di accertamento / cartella / atto impugnato",
             note="Allegare copia integrale — il ricorso deve identificare il provvedimento con precisione"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Doc_01_Prova_pagamento",          "Prova pagamento tributo (se controversia su rimborso)", obbl=False),
        _doc(6,  "Doc_02_Perizia",                  "Perizia o relazione tecnica", obbl=False),
        _doc(7,  "Contributo_unificato",            "Ricevuta contributo unificato tributario",
             note="Verificare importo in base al valore della lite — tabella specifica per tributario"),
        _doc(8,  "NIR_Nota_iscrizione_a_ruolo_FIRMATA", "NIR firmata digitalmente (scaricata da portale MEF, poi firmata CAdES e ri-caricata)",
             note="WORKFLOW PTT: 1) carica dati ricorso sul PTT → 2) scarica NIR generata dal portale MEF → 3) firma NIR con CAdES (.p7m) → 4) ri-carica NIR firmata come ultimo documento — senza questo step il deposito non si chiude"),
        _doc(9,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Registrazione/accesso al portale SIGIT/PTT (ptt.mef.gov.it) verificata", critico=True),
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True,
             note="Il PTT accetta solo CAdES — verificare che il file abbia estensione .p7m"),
        _chk("Termine di 60 gg dalla notifica dell'atto impugnato rispettato", critico=True,
             note="Art. 21 D.Lgs. 546/1992 — termine perentorio, non prorogabile"),
        _chk("CGT primo grado territorialmente competente verificata", critico=True,
             note="Competenza legata alla sede dell'ente impositore, non al domicilio del contribuente"),
        _chk("Atto impugnato allegato integralmente (con tutti i fogli)", critico=True),
        _chk("Tutti i PDF nel formato PDF/A-1b (non protetti, testo selezionabile)", critico=True),
        _chk("Nomi file senza caratteri speciali (no spazi, #, %, &, accenti)", critico=True),
        _chk("Contributo unificato tributario pagato — importo specifico per tributario", critico=True),
        _chk("NIR: carica dati → scarica NIR dal portale MEF → firma CAdES (.p7m) → ri-carica NIR firmata",
             critico=True,
             note="Senza la NIR firmata e ri-caricata il deposito telematico tributario non si chiude — è un passaggio unico del PTT rispetto al civile"),
        _chk("Peso totale deposito < 30 MB", critico=True),
        _chk("Ricorso depositato sul PTT/SIGIT entro termine e ricevuta salvata", critico=True),
        _chk("Copia del ricorso notificata all'ente impositore (notifica preventiva o contestuale)",
             critico=True,
             note="Art. 16-bis D.Lgs. 546/1992 — la notifica all'ente impositore è condizione di procedibilità"),
        _chk("Istanza di sospensiva se accertamento è in scadenza di riscossione"),
        _chk("Eventuale istanza di reclamo/mediazione obbligatoria per liti < 50.000 €",
             note="Art. 17-bis D.Lgs. 546/1992: per liti fino a 50.000 € è obbligatorio il tentativo di mediazione preventiva"),
    ],
)

APPELLO_TRIBUTARIO = TemplateAtto(
    id="appello_tributario",
    nome="Appello Tributario (CGT secondo grado)",
    categoria="TRIBUTARIO",
    descrizione="Appello alla Corte di Giustizia Tributaria di secondo grado (ex CTR).",
    nome_cartella="Appello_tributario_{rg}_{parte}_{data}",
    canale="PTT_TRIBUTARIO",
    endpoint_deposito="sigit_home",
    tipo_atto_default="APPELLO",
    nota_canale=(
        "L'appello tributario si deposita tramite PTT/SIGIT (ptt.mef.gov.it) con firma CAdES (.p7m). "
        "Normativa: artt. 51-63 D.Lgs. 546/1992. "
        "Non si usa PCT, PDP né PAT."
    ),
    documenti=[
        _doc(1,  "Atto_di_appello_tributario",     "Appello firmato CAdES (.p7m)"),
        _doc(2,  "Procura_alle_liti",               "Procura alle liti per il grado di appello"),
        _doc(3,  "Sentenza_CGT_primo_grado",        "Sentenza CGT primo grado impugnata",
             note="Deve essere copia autentica — richiedere alla cancelleria della CGT"),
        _doc(4,  "Indice_documenti",                "Indice allegati"),
        _doc(5,  "Relata_notifica_sentenza",        "Relata di notifica sentenza (dies a quo)", obbl=False,
             note="Allegare se la sentenza è stata notificata — determina il termine breve di 60 gg"),
        _doc(6,  "Contributo_unificato_appello",   "Ricevuta contributo unificato per appello",
             note="Importo aumentato rispetto al primo grado"),
        _doc(7,  "NIR_appello_FIRMATA",            "NIR appello firmata digitalmente (scaricata da MEF, firmata CAdES, ri-caricata)",
             note="Come per il ricorso: 1) carica dati → 2) scarica NIR da portale MEF → 3) firma CAdES (.p7m) → 4) ri-carica NIR firmata"),
        _doc(8,  "Doc_01_nuovi",                   "Nuovi documenti (se ammissibili)", obbl=False),
        _doc(9,  "Eventuali_altri_allegati",        "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Accesso al portale SIGIT/PTT (ptt.mef.gov.it) verificato", critico=True),
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Termine di 60 gg da notifica sentenza (o 6 mesi da deposito) rispettato", critico=True,
             note="Art. 51 D.Lgs. 546/1992 — verificare se la sentenza è stata notificata"),
        _chk("CGT secondo grado (ex CTR) competente verificata", critico=True),
        _chk("Sentenza impugnata in copia autentica allegata", critico=True),
        _chk("Relata di notifica sentenza allegata per dies a quo"),
        _chk("Tutti i PDF nel formato PDF/A-1b", critico=True),
        _chk("Contributo unificato appello tributario pagato", critico=True),
        _chk("NIR appello: carica dati → scarica NIR dal portale MEF → firma CAdES (.p7m) → ri-carica NIR firmata",
             critico=True,
             note="Identico al ricorso di primo grado — senza NIR firmata il deposito non si chiude"),
        _chk("Nomi file senza caratteri speciali", critico=True),
        _chk("Peso totale deposito < 30 MB", critico=True),
        _chk("Appello depositato sul PTT/SIGIT entro termine e ricevuta salvata", critico=True),
        _chk("Copia dell'appello notificata all'ente impositore / controparte", critico=True),
        _chk("Motivi di appello specifici (non è ammissibile un richiamo generico al ricorso)",
             critico=True),
        _chk("Istanza di sospensiva provvisoria se necessaria"),
    ],
)

NOMINA_DIFENSORE = TemplateAtto(
    id="nomina_difensore",
    nome="Nomina Difensore (PDP Penale)",
    categoria="PENALE",
    descrizione="Nomina del difensore di fiducia ex art. 107 c.p.p. tramite PDP — primo deposito da fare per accedere al fascicolo.",
    nome_cartella="Nomina_difensore_{rg}_{parte}_{data}",
    canale="PDP_PENALE",
    endpoint_deposito="pdp_home",
    tipo_atto_default="NOMINA",
    nota_canale=(
        "DAL 14/1/2024: deposito obbligatorio tramite PDP (art. 3 co. 8 D.M. 217/2023). "
        "ATTENZIONE: la nomina è l'ATTO ABILITANTE — senza la sua accettazione non è possibile "
        "depositare alcun altro atto nel procedimento. In fase di indagini preliminari è obbligatorio "
        "allegare l'atto abilitante (certificato ex art. 335 c.p.p., avviso UNEP, decreto perquisizione, ecc.). "
        "Dopo l'avviso ex art. 408/411/415-bis c.p.p. l'atto abilitante non è più necessario."
    ),
    documenti=[
        _doc(1, "Nomina_difensore",        "Nomina del difensore di fiducia firmata CAdES (.p7m)"),
        _doc(2, "Atto_abilitante",         "Atto abilitante (certificato art. 335 / avviso UNEP / decreto perquisizione / verbale identificazione)",
             obbl=False,
             note="Obbligatorio SOLO se il procedimento è in fase di indagini preliminari prima di avviso ex artt. 408/411/415-bis c.p.p. — senza, il sistema non accetta la nomina"),
        _doc(3, "Procura_speciale",        "Procura speciale autenticata", obbl=False),
    ],
    checklist=[
        _chk("Accesso al PDP tramite PST (pst.giustizia.it) con CNS verificato", critico=True),
        _chk("Avvocato iscritto in ReGIndE (requisito per accedere al PDP)", critico=True),
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Numero procedimento (RGNR o RG) correttamente indicato", critico=True),
        _chk("Atto abilitante allegato se procedimento in fase di indagini preliminari (pre art. 415-bis)",
             critico=True,
             note="Senza atto abilitante il sistema rifiuta la nomina — richiedere certificato ex art. 335 c.p.p."),
        _chk("Dopo accettazione nomina: procedimento visibile nell'elenco PDP — solo allora si possono depositare altri atti",
             critico=True),
        _chk("Ricevuta di accettazione PDP salvata nel fascicolo", critico=True),
        _chk("Nomina depositata entro termini (es. prima di udienza, prima di notifiche)", critico=True),
    ],
)

RINUNCIA_REVOCA_MANDATO = TemplateAtto(
    id="rinuncia_revoca_mandato",
    nome="Rinuncia / Revoca Mandato Penale (PDP)",
    categoria="PENALE",
    descrizione="Rinuncia al mandato difensivo o revoca ex art. 107 c.p.p. tramite PDP.",
    nome_cartella="Rinuncia_revoca_{rg}_{parte}_{data}",
    canale="PDP_PENALE",
    endpoint_deposito="pdp_home",
    tipo_atto_default="ALTRO",
    nota_canale=(
        "DAL 14/1/2024: deposito obbligatorio tramite PDP (art. 3 co. 8 D.M. 217/2023). "
        "Prerequisito: nomina già accettata dal sistema (procedimento visibile nel PDP). "
        "La rinuncia non ha effetto immediato — il difensore rimane in carica fino alla "
        "nomina del sostituto o all'assegnazione del difensore d'ufficio."
    ),
    documenti=[
        _doc(1, "Atto_rinuncia_o_revoca",  "Atto di rinuncia/revoca firmato CAdES (.p7m)"),
        _doc(2, "Comunicazione_cliente",   "Comunicazione al cliente della rinuncia", obbl=False),
    ],
    checklist=[
        _chk("Accesso al PDP tramite PST verificato", critico=True),
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Nomina precedente già accettata (procedimento visibile nel PDP)", critico=True),
        _chk("Numero procedimento correttamente indicato", critico=True),
        _chk("Comunicazione della rinuncia all'assistito prima del deposito"),
        _chk("Ricevuta di accettazione PDP salvata nel fascicolo", critico=True),
        _chk("Verifica che udienza successiva abbia un difensore (rinuncia non ha effetto immediato)"),
    ],
)

OPPOSIZIONE_ARCHIVIAZIONE = TemplateAtto(
    id="opposizione_archiviazione",
    nome="Opposizione all'Archiviazione (PDP Penale)",
    categoria="PENALE",
    descrizione="Opposizione alla richiesta di archiviazione ex art. 410 c.p.p. tramite PDP.",
    nome_cartella="Opposizione_archiviazione_{rg}_{parte}_{data}",
    canale="PDP_PENALE",
    endpoint_deposito="pdp_home",
    tipo_atto_default="OPPOSIZIONE",
    nota_canale=(
        "DAL 14/1/2024: deposito obbligatorio tramite PDP. "
        "Prerequisito: nomina già accettata e avviso di archiviazione ex art. 408 c.p.p. ricevuto. "
        "Termine: 20 giorni dalla notifica dell'avviso ex art. 408 c.p.p. — termine perentorio."
    ),
    documenti=[
        _doc(1, "Opposizione_archiviazione",   "Atto di opposizione firmato CAdES (.p7m)",
             note="Deve contenere l'indicazione delle indagini richieste (art. 410 co. 1 c.p.p.) — senza, l'opposizione è inammissibile"),
        _doc(2, "Avviso_archiviazione",        "Copia avviso di archiviazione ex art. 408 c.p.p."),
        _doc(3, "Procura_speciale",            "Procura speciale della persona offesa", obbl=False),
        _doc(4, "Doc_01_Prove_nuove",          "Documenti/prove a supporto dell'opposizione", obbl=False),
    ],
    checklist=[
        _chk("Accesso al PDP tramite PST verificato", critico=True),
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Nomina precedente già accettata nel PDP", critico=True),
        _chk("Termine di 20 gg dalla notifica dell'avviso ex art. 408 c.p.p. rispettato", critico=True,
             note="Termine perentorio — verificare data notifica avviso"),
        _chk("Opposizione indica specificamente le indagini richieste (art. 410 co. 1 c.p.p.)",
             critico=True,
             note="Senza indicazione delle indagini, il GIP dichiara l'opposizione inammissibile"),
        _chk("Avviso di archiviazione allegato nella busta", critico=True),
        _chk("Ricevuta di accettazione PDP salvata nel fascicolo", critico=True),
        _chk("Udienza ex art. 410-bis c.p.p. richiesta se necessaria"),
    ],
)

DENUNCIA_QUERELA = TemplateAtto(
    id="denuncia_querela",
    nome="Denuncia / Querela (PDP Penale)",
    categoria="PENALE",
    descrizione="Deposito di denuncia (art. 333 c.p.p.) o querela (art. 336 c.p.p.) tramite PDP.",
    nome_cartella="Denuncia_querela_{data}",
    canale="PDP_PENALE",
    endpoint_deposito="pdp_home",
    tipo_atto_default="DENUNCIA",
    nota_canale=(
        "DAL 14/1/2024: deposito telematico obbligatorio tramite PDP per i difensori. "
        "L'accoglimento equivale al ricevimento e iscrizione nel ReGeWEB da parte della Procura. "
        "Nota: la querela è un diritto della persona offesa — il difensore la deposita in rappresentanza. "
        "Termine querela: 3 mesi dalla conoscenza del fatto per reati perseguibili a querela (art. 124 c.p.)."
    ),
    documenti=[
        _doc(1, "Denuncia_o_querela",          "Atto di denuncia/querela firmato CAdES (.p7m)"),
        _doc(2, "Procura_speciale",            "Procura speciale del denunciante/querelante",
             note="Obbligatoria se il difensore deposita per conto del cliente — deve contenere espresso potere"),
        _doc(3, "Doc_01_Prove",                "Documenti a supporto (contratti, screenshot, referti, ecc.)"),
        _doc(4, "Doc_02",                      "Ulteriori prove", obbl=False),
        _doc(5, "Eventuali_altri_allegati",    "Altri allegati", obbl=False),
    ],
    checklist=[
        _chk("Accesso al PDP tramite PST (pst.giustizia.it) verificato", critico=True),
        _chk("Firma digitale CAdES (.p7m) valida e non scaduta", critico=True),
        _chk("Per querela: termine di 3 mesi dalla conoscenza del fatto rispettato (art. 124 c.p.)",
             critico=True,
             note="Termine perentorio per reati perseguibili a querela — la querela tardiva è inefficace"),
        _chk("Procura speciale del querelante/denunciante allegata", critico=True,
             note="Obbligatoria se il difensore deposita in nome e per conto del cliente"),
        _chk("Ufficio di Procura competente per territorio verificato"),
        _chk("Fatto descritto con precisione (data, luogo, modalità, autore se noto)"),
        _chk("Prove documentali allegate nella busta"),
        _chk("Ricevuta di accettazione PDP salvata nel fascicolo", critico=True),
        _chk("Per querela: riserva di rimessione valutata"),
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
    NOMINA_DIFENSORE,
    RINUNCIA_REVOCA_MANDATO,
    OPPOSIZIONE_ARCHIVIAZIONE,
    DENUNCIA_QUERELA,
    RICORSO_TRIBUTARIO,
    APPELLO_TRIBUTARIO,
]

CATEGORIE = {
    "CIVILE":         "Civile",
    "ESECUTIVO":      "Esecutivo",
    "CAUTELARE":      "Cautelare",
    "PENALE":         "Penale",
    "AMMINISTRATIVO": "Amministrativo",
    "TRIBUTARIO":     "Tributario",
    "STRAGIUDIZIALE": "Stragiudiziale",
}

CAT_ICON = {
    "CIVILE":         "bi-balance-scale",
    "ESECUTIVO":      "bi-hammer",
    "CAUTELARE":      "bi-shield-exclamation",
    "PENALE":         "bi-shield-fill",
    "AMMINISTRATIVO": "bi-building",
    "TRIBUTARIO":     "bi-receipt-cutoff",
    "STRAGIUDIZIALE": "bi-handshake",
}

CAT_COL = {
    "CIVILE":         "primary",
    "ESECUTIVO":      "warning",
    "CAUTELARE":      "danger",
    "PENALE":         "dark",
    "AMMINISTRATIVO": "info",
    "TRIBUTARIO":     "warning",
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

