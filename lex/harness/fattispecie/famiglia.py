"""Fattispecie di famiglia: separazione e divorzio giudiziale, mantenimento del figlio maggiorenne (artt. 473-bis ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi, Punto, Rif
from ..norme import piano


def riconosci_separazione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
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
    a.giudice = f"Tribunale di {luogo_minore or luogo}" if (luogo_minore or luogo) else "Tribunale"
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
