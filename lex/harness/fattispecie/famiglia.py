"""Fattispecie di famiglia: separazione e divorzio giudiziale, mantenimento del figlio maggiorenne (artt. 473-bis ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P


def riconosci_separazione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if re.search(r"modific\w* (?:delle |le )?condizion|revision\w* (?:delle |le )?condizion|negoziazione assistita|ordine di protezione|"
                 r"ordini di protezione", t):
        return 0
    if re.search(r"separazion|divorzi", t) and not re.search(r"quando posso.{0,40}divorzi|dopo (?:quanto|la separazione)", t):
        return 3
    return 0


def analizza_separazione(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    divorzio = "divorzi" in t and "separazion" not in t
    a = Analisi("separazione_giudiziale", "famiglia", modello="FAM_002")
    luogo = f.residenza_convenuto or f.luogo_immobile
    m = re.search(r"(?:minore|figli\w*)[^.]{0,60}?(?:residente|vive|abita|convive)[^.]{0,30}?\b(?:a|in)\s+([A-Z][a-zà-ù]+)", f.testo)
    luogo_minore = m.group(1) if m else ""
    a.capito = [("Divorzio" if divorzio else "Separazione") + " giudiziale" + (" con figli minori" if f.ha("figli_minori") else "") + "."]
    a.rito = [Punto("Rito unificato per le persone, i minorenni e le famiglie: si applica a tutti i procedimenti relativi "
                    "allo stato delle persone, ai minorenni e alle famiglie.", [Rif("cpc:473bis", "stato delle persone, ai minorenni e alle famiglie")]),
              Punto("La domanda si propone con ricorso, che indica fra l'altro i fatti, le domande, i mezzi di prova e, "
                    "in presenza di figli minori, il piano genitoriale.", [Rif("cpc:473bis12", "si propone con ricorso")])]
    a.competenza = [Punto("Competenza per territorio: se ci sono figli minori, è competente il tribunale del luogo in cui il "
                          "minore ha la residenza abituale" + (f" (qui: {luogo_minore})" if luogo_minore else "") +
                          "; altrimenti valgono gli altri criteri dello stesso articolo (residenza del convenuto).",
                          [Rif("cpc:473bis11", "residenza abituale")])]
    a.giudice = P.ufficio("Tribunale", luogo_minore or luogo) if (luogo_minore or luogo) else "Tribunale"
    a.inquadramento = [
        Punto("La separazione giudiziale si chiede quando si verificano fatti tali da rendere intollerabile la "
              "prosecuzione della convivenza o recare grave pregiudizio all'educazione dei figli.",
              [Rif("cc:151", "intollerabile la prosecuzione della convivenza")]),
        Punto("Sui figli il giudice valuta prioritariamente l'affidamento a entrambi i genitori.",
              [Rif("cc:337ter", "affidati a entrambi i genitori")]),
        Punto("Nel ricorso di separazione si può proporre anche la domanda di divorzio, che diventa procedibile quando "
              "matura il termine di legge.", [Rif("cpc:473bis49", "possono proporre anche domanda di scioglimento")]),
    ]
    a.procedibilita = [Punto("Mediazione e negoziazione assistita non sono condizioni di procedibilità per la separazione "
                             "giudiziale: la materia non è fra quelle dell'art. 5, comma 1, d.lgs. 28/2010.",
                             [Rif("dlgs28:5", "diritti reali")])]
    a.conclusione = [Punto(f"Ricorso al {a.giudice} nelle forme degli artt. 473-bis ss. c.p.c.",
                           [Rif("cpc:473bis12", "si propone con ricorso"), Rif("cpc:473bis11", "residenza abituale")])]
    a.cosa_fare = ["Raccogliere estratto dell'atto di matrimonio, stato di famiglia, dichiarazioni dei redditi degli ultimi "
                   "tre anni e documentazione patrimoniale da allegare al ricorso.",
                   "Preparare il piano genitoriale se ci sono figli minori.",
                   "Valutare la domanda congiunta di divorzio nello stesso ricorso."]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso per separazione giudiziale (art. 473-bis.12 c.p.c.)", a.giudice, f,
            "separazione personale dei coniugi con provvedimenti sui figli e sugli aspetti economici",
            ["Fatti che rendono intollerabile la prosecuzione della convivenza (art. 151 c.c.): [da completare].",
             "Affidamento dei figli e collocamento (art. 337-ter c.c.): [da completare]; piano genitoriale allegato.",
             "Contributo al mantenimento e assegnazione della casa familiare: [da completare]."],
            "pronunciare la separazione personale dei coniugi; disporre l'affidamento condiviso dei figli minori con "
            "collocamento presso [da completare]; porre a carico di [da completare] un contributo al mantenimento di "
            "[da completare]; con vittoria di spese.",
            "atto di matrimonio, stato di famiglia, dichiarazioni dei redditi, piano genitoriale.", "artt. 473-bis ss. c.p.c.")
    return a


def riconosci_divorzio_tempi(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 3 if re.search(r"divorzi", t) and re.search(r"quando|dopo quanto|tempo|termine|mesi", t) else 0


def analizza_divorzio_tempi(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("divorzio_tempi", "famiglia")
    a.capito = ["Da quando si può chiedere il divorzio dopo la separazione."]
    a.conclusione = [Punto("Il divorzio si può chiedere quando la separazione si è protratta ininterrottamente per almeno "
                           "dodici mesi dalla comparizione dei coniugi davanti al giudice nella separazione giudiziale, e "
                           "per sei mesi nella separazione consensuale.",
                           [Rif("l898:3", "dodici mesi"), Rif("l898:3", "sei mesi")])]
    a.inquadramento = [Punto("La domanda di divorzio può essere proposta già nel ricorso di separazione: è procedibile "
                             "solo al decorso del termine.", [Rif("cpc:473bis49", "possono proporre anche domanda di scioglimento")])]
    return a


def riconosci_maggiorenne(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 3 if "maggiorenn" in t and re.search(r"mantenim|assegno", t) else 0


def analizza_maggiorenne(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("figlio_maggiorenne", "famiglia", modello="FAM_010")
    a.capito = ["Mantenimento del figlio maggiorenne non economicamente indipendente."]
    a.conclusione = [Punto("Il giudice può disporre in favore dei figli maggiorenni non indipendenti economicamente il "
                           "pagamento di un assegno periodico, versato direttamente all'avente diritto salvo diversa "
                           "determinazione.", [Rif("cc:337septies", "figli maggiorenni non indipendenti economicamente")])]
    a.rito = [Punto("Si procede con ricorso nel rito per le persone, i minorenni e le famiglie.",
                    [Rif("cpc:473bis", "stato delle persone, ai minorenni e alle famiglie"), Rif("cpc:473bis12", "si propone con ricorso")])]
    return a


# ------------------------------------------------------------------- revisione delle condizioni (art. 473-bis.29 c.p.c.)
def riconosci_modifica_condizioni(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if re.search(r"negoziazione assistita", t):
        return 0
    return 6 if re.search(r"(?:modific|revision|revoc|riduzion|ridurr|aument|rivede|rivision)\w* (?:delle |le |dell |l |dell assegno|del mantenimento|"
                          r"dell affidamento|del contributo)?(?:condizion|assegno|mantenimento|affidamento|contribut)", t) and re.search(
        r"separazion|divorzi|figli|assegno|mantenimento|ex (?:moglie|marito|coniuge)", t) else 0


def analizza_modifica_condizioni(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import forma

    a = Analisi("modifica_condizioni", "famiglia — revisione delle condizioni", forma=forma(c))
    a.capito = ["Richiesta di modificare le condizioni di separazione o divorzio (figli, assegni) per fatti sopravvenuti."]
    a.rimedio = ("ricorso per la revisione dei provvedimenti con le forme del rito unitario della famiglia, oppure accordo "
                 "con negoziazione assistita")
    a.conclusione = [
        Punto("Se sopravvengono giustificati motivi, le parti possono in ogni tempo chiedere la revisione dei provvedimenti a "
              "tutela dei minori e in materia di contributi economici, con le forme del procedimento in materia di famiglia.",
              [Rif("cpc:473bis29", "Qualora sopravvengano giustificati motivi"),
               Rif("cpc:473bis29", "la revisione dei provvedimenti a tutela dei minori e in materia di contributi economici")]),
        Punto("Se c'è accordo, la modifica delle condizioni di separazione o di divorzio si può fare anche con la negoziazione "
              "assistita da almeno un avvocato per parte.",
              [Rif("dl132:6", "di modifica delle condizioni di separazione o di divorzio")]),
    ]
    a.cosa_fare = ["Documentare il fatto nuovo (reddito, lavoro, esigenze dei figli, nuova convivenza) rispetto al provvedimento.",
                   "Allegare il provvedimento da modificare e le ultime dichiarazioni dei redditi."]
    a.dati_mancanti.append("provvedimento da modificare (data e giudice) e fatti sopravvenuti")
    return a


# ------------------------------------------------------------------- negoziazione assistita familiare (art. 6 d.l. 132/2014)
def riconosci_negoziazione_familiare(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 7 if re.search(r"negoziazione assistita", t) and re.search(r"separazion|divorzi|coniug|figli|mantenimento|affidamento|"
                                                                     r"alimenti|matrimonio", t) else 0


def analizza_negoziazione_familiare(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import forma

    t = piano(f.testo)
    a = Analisi("negoziazione_familiare", "famiglia — negoziazione assistita", forma=forma(c))
    figli = re.search(r"figli (?:minor|maggiorenn\w* (?:non autosufficient|incapac|portator))|con figli|minori", t)
    a.capito = ["Separazione, divorzio o modifica delle condizioni con accordo raggiunto in negoziazione assistita"
                + (", con figli minori o non autosufficienti." if figli else ".")]
    a.rimedio = "convenzione di negoziazione assistita da almeno un avvocato per parte e trasmissione dell'accordo al pubblico ministero"
    a.conclusione = [
        Punto("La convenzione di negoziazione assistita da almeno un avvocato per parte può essere conclusa fra coniugi per la "
              "separazione, il divorzio o la modifica delle condizioni.",
              [Rif("dl132:6", "da almeno un avvocato per parte puo' essere conclusa tra coniugi")]),
        Punto("Senza figli minori, maggiorenni incapaci, con handicap grave o non autosufficienti, l'accordo va al procuratore "
              "della Repubblica, che se non trova irregolarità rilascia il nullaosta.",
              [Rif("dl132:6", "comunica agli avvocati di tutte le parti il nullaosta")]),
        Punto("Con quei figli, l'accordo deve essere trasmesso entro dieci giorni al procuratore della Repubblica, che lo "
              "autorizza se risponde al loro interesse; altrimenti lo trasmette al presidente del tribunale, che fissa la "
              "comparizione delle parti.",
              [Rif("dl132:6", "deve essere trasmesso entro il termine di dieci giorni al procuratore della Repubblica"),
               Rif("dl132:6", "quando ritiene che l'accordo risponde all'interesse dei figli, lo autorizza")]),
        Punto("L'accordo si trasmette in via telematica a cura degli avvocati.",
              [Rif("dl132:6", "L'accordo e' trasmesso con modalita' telematiche")]),
    ]
    if figli:
        a.avvertenze.append("Con figli minori non basta il nullaosta: serve l'autorizzazione del pubblico ministero, che valuta "
                            "l'interesse dei figli.")
    return a


# ------------------------------------------------------------------- ordini di protezione (artt. 473-bis.69 ss. c.p.c.)
def riconosci_ordini_protezione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 7 if re.search(r"ordin\w* di protezione|allontanamento dalla casa familiare|abusi familiari|violenz\w* (?:domestic|in famiglia)|"
                          r"342[- ]bis|342[- ]ter", t) else 0


def analizza_ordini_protezione(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import forma

    a = Analisi("ordini_protezione", "famiglia — ordini di protezione", forma=forma(c))
    a.capito = ["Condotta del coniuge o del convivente che reca grave pregiudizio all'integrità o alla libertà dell'altro."]
    a.rimedio = "ricorso per ordine di protezione contro gli abusi familiari (artt. 473-bis.69 e 473-bis.70 c.p.c.)"
    a.conclusione = [
        Punto("Quando la condotta del coniuge o di altro convivente è causa di grave pregiudizio all'integrità fisica o morale "
              "o alla libertà dell'altro, il giudice, su istanza di parte, può adottare con decreto gli ordini di protezione, "
              "anche se la convivenza è cessata.",
              [Rif("cpc:473bis69", "e' causa di grave pregiudizio all'integrita' fisica o morale"),
               Rif("cpc:473bis69", "anche quando la convivenza e' cessata")]),
        Punto("La disciplina vigente è nel codice di procedura civile (artt. 473-bis.69 e seguenti), non più agli artt. 342-bis "
              "e 342-ter c.c.; se la condotta può pregiudicare i minori provvede, anche su istanza del pubblico ministero, il "
              "tribunale per i minorenni.",
              [Rif("cpc:473bis69", "dal tribunale per i minorenni")]),
        Punto("Con il decreto il giudice ordina la cessazione della condotta e l'allontanamento dalla casa familiare, e può "
              "vietare di avvicinarsi ai luoghi frequentati dal beneficiario.",
              [Rif("cpc:473bis70", "la cessazione della stessa condotta e dispone l'allontanamento dalla casa familiare"),
               Rif("cpc:473bis70", "di non avvicinarsi ai luoghi abitualmente frequentati dal beneficiario")]),
    ]
    return a
