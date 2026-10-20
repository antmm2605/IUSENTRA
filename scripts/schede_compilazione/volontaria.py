"""Schede di volontaria giurisdizione e successioni (VGS).

Base normativa: artt. 404-432 c.c. (amministrazione di sostegno, interdizione, inabilitazione); artt. 343-389 c.c.
(tutela e autorizzazioni); artt. 459-535 c.c. (accettazione, rinuncia, eredità giacente); artt. 712-720-bis, 737-742,
747-750, 769-782 c.p.c. Sospensione feriale esclusa per amministrazione di sostegno, interdizione e inabilitazione
(art. 92 ord. giud.); i termini dell’accettazione e dell’inventario sono sostanziali e non si sospendono.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, SENZA_FERIALE, T, assistito, avvocato, calcolo, data_luogo, difensore, documento,
                                                lex, procura)
from scripts.schede_compilazione.costruisci import scheda

RECLAMO = [(CPC, "739", "reclamo entro dieci giorni"), (CPC, "720bis", "reclamo dei decreti in materia di amministrazione di sostegno: verificare il giudice del reclamo nel testo vigente")]


def _base(ric="Ricorrente"):
    return [difensore(), procura("la procura serve se si sta in giudizio con difensore; per l’amministrazione di sostegno il ricorso può essere depositato anche senza"),
            data_luogo(), assistito(ric)]


def _beneficiario(etichetta="Beneficiario, interdicendo o minore"):
    return avvocato("beneficiario", etichetta, "Anagrafica, residenza o dimora abituale, condizioni di salute e di vita",
                    norma=[(CC, "404", "beneficiario"), (CC, "407", "contenuto del ricorso")])


def _familiari():
    return avvocato("familiari", "Coniuge, parenti entro il quarto grado e affini entro il secondo",
                    "Chi sono e dove risiedono (vanno indicati e sentiti)?", norma=[(CC, "407", "persone da indicare"), (CPC, "712", "contenuto del ricorso")])


def _certificazione():
    return documento("certificato", "Certificazione medica", "certificato medico o relazione dei servizi", ["certificato", "relazione", "medico"],
                     se_manca="chiedere la documentazione sanitaria")


SCHEDE = [
    scheda("VGS_001", "Ricorso per amministrazione di sostegno e istanze di modifica", ["VGS_001", "VGS_002"],
           [(CC, "404", "amministrazione di sostegno"), (CC, "405", "decreto entro sessanta giorni"), (CC, "406", "legittimazione"),
            (CC, "407", "procedimento"), (CC, "408", "scelta dell’amministratore"), (CC, "409", "capacità del beneficiario"),
            (CC, "413", "revoca e modifica"), *RECLAMO, *SENZA_FERIALE],
           _base() + [_beneficiario(), _familiari(), _certificazione(),
                      avvocato("atti", "Atti per cui serve l’assistenza o la rappresentanza", "Quali atti l’amministratore deve compiere in nome o con il beneficiario?",
                               norma=[(CC, "405", "oggetto dell’incarico"), (CC, "409", "atti che il beneficiario conserva")]),
                      avvocato("amministratore", "Amministratore proposto", "Chi si propone e perché (preferenza del beneficiario, coniuge, parenti)?",
                               norma=[(CC, "408", "criteri di scelta")]),
                      avvocato("modifica", "Modifica richiesta", "Se è una modifica: quale decreto e quali circostanze nuove?", obbligatorio=False,
                               norma=[(CC, "413", "revoca o modifica")]),
                      calcolo("ufficio", "Giudice competente", "giudice tutelare del luogo di residenza o domicilio del beneficiario", norma=[(CC, "404", "competenza")])],
           [("Ricorso", "condizioni del beneficiario, atti, amministratore proposto, familiari")],
           ["beneficiario non indicato", "nessuna documentazione sanitaria o sociale"]),

    scheda("VGS_003", "Rendiconto dell’amministratore, del tutore o del curatore", ["VGS_003"],
           [(CC, "380", "rendiconto annuale"), (CC, "385", "conto finale"), (CC, "411", "norme applicabili all’amministrazione di sostegno")],
           _base("Amministratore o tutore") + [_beneficiario(),
                      documento("movimenti", "Estratti conto e giustificativi del periodo", "estratti conto, ricevute, fatture", ["estratto", "ricevuta", "fattura"],
                                se_manca="senza giustificativi il rendiconto non si chiude"),
                      lex("prospetto", "Prospetto entrate e uscite", "riepilogare entrate, uscite e saldo dai documenti caricati, senza stime")],
           [("Rendiconto", "periodo, entrate, uscite, saldo e atti compiuti")], ["periodo non indicato"]),

    scheda("VGS_004", "Ricorso per interdizione o inabilitazione", ["VGS_004", "VGS_005"],
           [(CC, "414", "interdizione"), (CC, "415", "inabilitazione"), (CC, "417", "legittimazione"), (CC, "418", "poteri del giudice e amministrazione di sostegno"),
            (CPC, "712", "forma della domanda"), (CPC, "713", "comparizione"), (CPC, "714", "esame dell’interdicendo"), *SENZA_FERIALE],
           _base() + [_beneficiario("Interdicendo o inabilitando"), _familiari(), _certificazione(),
                      avvocato("residualita", "Perché non basta l’amministrazione di sostegno", "Per quali ragioni la tutela meno invasiva non è adeguata?",
                               norma=[(CC, "418", "trasmissione al giudice tutelare"), (CC, "404", "misura preferibile")]),
                      calcolo("ufficio", "Tribunale competente", "tribunale del luogo di residenza o domicilio dell’interdicendo, con il pubblico ministero",
                              norma=[(CPC, "712", "competenza")])],
           [("Ricorso", "infermità abituale, incapacità, ragioni della misura, parenti")],
           ["non sono indicate le ragioni per cui l’amministrazione di sostegno non basta"]),

    scheda("VGS_006", "Ricorso per nomina del tutore o del curatore", ["VGS_006", "VGS_007"],
           [(CC, "343", "apertura della tutela"), (CC, "346", "nomina del tutore"), (CC, "348", "scelta del tutore"), (CC, "392", "curatore dell’emancipato"),
            (CC, "424", "tutela dell’interdetto e curatela dell’inabilitato")],
           _base() + [_beneficiario("Minore, interdetto o inabilitato"),
                      documento("titolo", "Provvedimento o evento che apre la tutela", "sentenza di interdizione, certificato di morte dei genitori",
                                ["sentenza", "morte", "decesso"], se_manca="indicare perché la tutela o la curatela si apre"),
                      avvocato("tutore", "Persona proposta", "Chi si propone e con quali requisiti?", norma=[(CC, "348", "criteri di scelta")])],
           [("Ricorso", "presupposti e persona proposta")], ["presupposti non documentati"]),

    scheda("VGS_008", "Ricorso al giudice tutelare per autorizzazioni (riscossione, vendita, divisione)", ["VGS_008", "VGS_009", "VGS_010", "VGS_019"],
           [(CC, "320", "atti dei genitori"), (CC, "374", "autorizzazioni del giudice tutelare"), (CC, "375", "autorizzazioni, oggi del giudice tutelare dopo il D.Lgs. 149/2022"),
            (CC, "411", "amministrazione di sostegno"), (CPC, "732", "alienazione di beni di minori e incapaci"), (CPC, "733", "vendita all’incanto"), (CPC, "734", "reimpiego"),
            *RECLAMO],
           _base("Genitore, tutore o amministratore") + [_beneficiario(),
                      avvocato("atto", "Atto da autorizzare", "Riscossione, vendita, divisione, transazione: quale atto, con quale valore?",
                               norma=[(CC, "374", "atti soggetti ad autorizzazione"), (CC, "375", "atti che richiedono il tribunale")]),
                      avvocato("utilita", "Utilità evidente e reimpiego", "Perché l’atto è necessario o utile e come si reimpiegano le somme?",
                               norma=[(CC, "320", "necessità o utilità evidente")]),
                      documento("stima", "Perizia di stima o progetto di divisione", "perizia, progetto divisionale", ["perizia", "stima", "divisione"], obbligatorio=False)],
           [("Ricorso", "atto, utilità evidente, valore e reimpiego; ricordare l’alternativa dell’autorizzazione notarile prevista dall’art. 21 D.Lgs. 149/2022")], ["utilità o reimpiego non indicati"]),

    scheda("VGS_011", "Accettazione con beneficio di inventario, autorizzazioni e inventario", ["VGS_011", "VGS_014", "VGS_016"],
           [(CC, "471", "accettazione per minori e interdetti solo col beneficio"), (CC, "472", "emancipati e inabilitati"), (CC, "484", "forma dell’accettazione beneficiata"),
            (CC, "485", "chiamato nel possesso dei beni: inventario entro tre mesi"), (CC, "487", "chiamato non nel possesso"),
            (CC, "488", "termini dopo l’inventario"), (CPC, "769", "inventario"), (CPC, "775", "processo verbale di inventario")],
           _base("Chiamato all’eredità o suo rappresentante") + [
               avvocato("defunto", "Defunto e apertura della successione", "Chi è il defunto, data e luogo di morte?", norma=[(CC, "456", "apertura della successione")]),
               avvocato("possesso", "Possesso dei beni ereditari", "Il chiamato è nel possesso di beni ereditari?",
                        norma=[(CC, "485", "tre mesi dall’apertura o dalla notizia"), (CC, "487", "chiamato non possessore")]),
               calcolo("inventario", "Termine per l’inventario del chiamato nel possesso", termine=T("evento", mesi=3, feriale=False),
                       regola="tre mesi dall’apertura della successione o dalla notizia della devoluzione, prorogabili; termine sostanziale, senza sospensione feriale",
                       norma=[(CC, "485", "tre mesi")]),
               calcolo("deliberare", "Termine per accettare o rinunciare dopo l’inventario", termine=T("evento", 40, feriale=False),
                       regola="40 giorni dal compimento dell’inventario (evento = chiusura dell’inventario), altrimenti erede puro e semplice; termine sostanziale",
                       norma=[(CC, "485", "quaranta giorni")]),
               avvocato("incapace", "Minore o incapace chiamato", "Il chiamato è minore, interdetto o beneficiario? Serve l’autorizzazione?",
                        obbligatorio=False, norma=[(CC, "471", "beneficio obbligatorio"), (CC, "320", "autorizzazione")])],
           [("Atto", "dichiarazione davanti al notaio o al cancelliere, inventario, autorizzazione se necessaria")],
           ["data di apertura o di notizia non indicata", "chiamato nel possesso oltre tre mesi senza inventario: segnalare che si considera erede puro e semplice"]),

    scheda("VGS_012", "Rinuncia all’eredità e relativa autorizzazione", ["VGS_012", "VGS_015"],
           [(CC, "519", "forma della rinuncia"), (CC, "520", "rinuncia nulla se condizionata"), (CC, "521", "effetti"), (CC, "525", "revoca della rinuncia"),
            (CC, "320", "autorizzazione per il minore"), (CC, "374", "autorizzazione per il tutelato")],
           _base("Chiamato all’eredità o suo rappresentante") + [
               avvocato("defunto", "Defunto e apertura della successione", "Chi è il defunto, data e luogo di morte?", norma=[(CC, "456", "apertura")]),
               avvocato("atti", "Atti già compiuti sui beni ereditari", "Il chiamato ha già compiuto atti che importano accettazione o possiede beni da oltre tre mesi?",
                        norma=[(CC, "476", "accettazione tacita"), (CC, "485", "possessore che non fa l’inventario")],
                        se_manca="segnalare il rischio di accettazione già avvenuta"),
               avvocato("incapace", "Minore o incapace", "Se il rinunciante è minore o incapace: autorizzazione del giudice e utilità della rinuncia",
                        obbligatorio=False, norma=[(CC, "320", "autorizzazione")])],
           [("Atto", "dichiarazione di rinuncia davanti al notaio o al cancelliere, istanza di autorizzazione se necessaria")],
           ["accettazione già avvenuta: la rinuncia non è più possibile"]),

    scheda("VGS_013", "Ricorso per la nomina del curatore dell’eredità giacente", ["VGS_013"],
           [(CC, "528", "nomina del curatore"), (CC, "529", "obblighi del curatore"), (CPC, "781", "procedimento")],
           _base("Interessato") + [
               avvocato("defunto", "Defunto e apertura della successione", "Chi è il defunto, data e luogo di morte?", norma=[(CC, "456", "apertura")]),
               avvocato("giacenza", "Presupposti della giacenza", "Nessun chiamato ha accettato e nessuno è nel possesso dei beni? Quale interesse ha il ricorrente?",
                        norma=[(CC, "528", "presupposti")])],
           [("Ricorso", "presupposti, interesse, beni noti")], ["chiamato nel possesso dei beni: non c’è giacenza"]),

    scheda("VGS_017", "Ricorso per rettificazione di atti di stato civile o questioni sul nome", ["VGS_017", "VGS_018"],
           [(CC, "453", "annotazioni solo per legge o ordine del giudice"), (CC, "6", "diritto al nome"), (CC, "7", "tutela del nome"), (CPC, "737", "forma camerale")],
           _base() + [documento("atto", "Atto di stato civile da rettificare", "estratto o copia integrale dell’atto", ["atto", "estratto", "nascita"],
                                se_manca="chiedere l’atto da rettificare"),
                      avvocato("errore", "Errore o domanda", "Qual è l’errore o il cambiamento chiesto, con quali prove?"),
                      lex("competenza", "Autorità competente", "segnalare (artt. 95-96 e 89 D.P.R. 396/2000, da verificare) che il cambio volontario di nome o cognome si chiede al prefetto, mentre la rettifica degli errori al tribunale; la disciplina dello stato civile non è nella base normativa e va verificata")],
           [("Ricorso", "atto, errore, prova e correzione richiesta")], ["cambio volontario di nome o cognome: domanda al prefetto, non al tribunale"]),
]
