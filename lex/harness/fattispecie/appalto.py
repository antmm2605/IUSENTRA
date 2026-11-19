"""Appalto: garanzia per vizi dell'opera (artt. 1667-1669 c.c.), denuncia, decadenza e prescrizione."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine_anni, termine_giorni
from .strumenti import date_in, forma, frase, importi_in


def riconosci_vizi_appalto(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 4 if re.search(r"appalt|appaltator|installator|falegnam", t) and re.search(r"vizi|difett|non ha mai funzionato|rigonfiament|blocco", t) else 0


def analizza_vizi_appalto(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("vizi_appalto", "civile — appalto", modello="CIV_ORD_001")
    consegna = (date_in(frase(f, r"consegna|collaudo e consegna|posa della")) or [None])[0]
    scoperta = (date_in(frase(f, r"scopre|prima accensione|blocco|rigonfiament|scopert")) or [None])[0]
    x_den = frase(f, r"(?:denuncia|prima contestazione scritta|contesta)(?:(?!\d{1,2}/\d{1,2}/\d{4}).){0,90}(?:pec|raccomandat)|pec del \d")
    denuncia = (date_in(x_den) or [None])[0]
    corrispettivo = (importi_in(frase(f, r"corrispettivo")) or [None])[0]
    ripristino = (importi_in(frase(f, r"costo d\w* (?:ripristino|sostituzione)|stima il costo")) or [None])[-1]
    a.capito = [f"Appalto fra {f.assistita.nome or '[committente]'} e {f.controparte.nome or '[appaltatore]'}"
                + (f", corrispettivo {euro(corrispettivo)}" if corrispettivo else "") + f"; consegna {data_it(consegna)}, "
                f"vizi scoperti il {data_it(scoperta)}, prima denuncia scritta il {data_it(denuncia)}"
                + (f"; costo di ripristino stimato {euro(ripristino)}" if ripristino else "") + "."]
    a.inquadramento = [
        Punto("L'appaltatore risponde delle difformità e dei vizi dell'opera; la consegna senza riserve non lo libera per i "
              "vizi non riconoscibili. Il committente deve denunciare i vizi entro sessanta giorni dalla scoperta, a pena di "
              "decadenza; la denuncia non è necessaria se l'appaltatore ha riconosciuto i vizi o li ha occultati. L'azione si "
              "prescrive in due anni dalla consegna dell'opera.",
              [Rif("cc:1667", "sessanta giorni dalla scoperta"), Rif("cc:1667", "riconosciuto"), Rif("cc:1667", "due anni dal giorno della consegna")]),
        Punto("Il committente può chiedere che i vizi siano eliminati a spese dell'appaltatore o che il prezzo sia diminuito "
              "proporzionalmente, salvo il risarcimento del danno in caso di colpa; la risoluzione solo se i vizi rendono "
              "l'opera del tutto inadatta alla sua destinazione.", [Rif("cc:1668", "proporzionalmente diminuito"),
                                                                   Rif("cc:1668", "del tutto inadatta")]),
        Punto("Chi fa valere un diritto in giudizio deve provarne i fatti costitutivi: la tempestività della denuncia o il "
              "riconoscimento dei vizi sono a carico del committente.", [Rif("cc:2697", "deve provare i fatti")]),
    ]
    if re.search(r"1669|decennal", t):
        a.inquadramento.append(Punto(
            "La responsabilità dell'art. 1669 c.c. (dieci anni) riguarda edifici o altre cose immobili destinate per loro natura "
            "a lunga durata: non si applica a un arredo o a un impianto come questo, che resta nella garanzia dell'art. 1667 c.c.",
            [Rif("cc:1669", "cose immobili destinate per loro natura a lunga durata")]))
        a.avvertenze.append("La garanzia decennale indicata nella richiesta non è applicabile: non c'è margine per «prendersela "
                            "comoda», vale la prescrizione biennale.")
    decaduto = False
    if scoperta:
        lim = termine_giorni(scoperta, 60, sostanziale=True)
        decaduto = bool(denuncia and denuncia > lim) and not re.search(r"riconosciut\w* (?:i )?vizi", t.replace("ne riconoscimenti", ""))
        a.termini.append(Punto(f"Denuncia dei vizi: sessanta giorni dalla scoperta del {data_it(scoperta)}, scadenza "
                               f"{data_breve(lim)} (decadenza sostanziale, senza sospensione feriale); denuncia scritta del "
                               f"{data_it(denuncia)}: " + ("TARDIVA." if decaduto else "tempestiva."),
                               [Rif("cc:1667", "sessanta giorni dalla scoperta")]))
    if consegna:
        pres = termine_anni(consegna, 2)
        a.termini.append(Punto(f"Prescrizione dell'azione: due anni dalla consegna del {data_it(consegna)}, scadenza "
                               f"{data_breve(pres)}; la interrompe ogni atto che costituisce in mora l'appaltatore.",
                               [Rif("cc:1667", "due anni dal giorno della consegna"), Rif("cc:2943", "costituire in mora il debitore")]))
    valore = ripristino or corrispettivo
    if valore:
        giudice, punti = P.giudice_per_valore(valore)
        a.competenza = punti
        a.giudice = f"{giudice} competente per territorio (sede dell'appaltatore o luogo dell'obbligazione) [da verificare]"
    if decaduto:
        a.forma = "parere (consulenza)"
        a.rimedio = ("parere scritto al cliente sul rischio di decadenza, prima di qualsiasi citazione; azione per riduzione "
                     "del prezzo e danni solo se emerge la prova del riconoscimento dei vizi da parte dell'appaltatore")
        a.conclusione = [Punto("La citazione richiesta oggi è inadatta: la denuncia è tardiva e l'appaltatore ha già eccepito la "
                               "decadenza; senza prova del riconoscimento dei vizi la domanda sarebbe respinta.",
                               [Rif("cc:1667", "sessanta giorni dalla scoperta"), Rif("cc:2697", "deve provare i fatti")])]
        a.avvertenze.append("Raccogliere subito ogni prova del riconoscimento dei vizi (testimoni delle telefonate, messaggi, "
                            "interventi in garanzia); far sottoscrivere al cliente l'informativa sul rischio di soccombenza.")
        a.dati_mancanti = ["prove del riconoscimento dei vizi da parte dell'impresa", "sede dell'impresa (competenza territoriale)"]
    else:
        a.forma = forma(c)
        a.rimedio = ("azione di garanzia per vizi dell'appalto (artt. 1667-1668 c.c.): diffida interruttiva della prescrizione, "
                     "accertamento tecnico preventivo e poi giudizio di merito per l'eliminazione dei vizi o la riduzione del prezzo")
        a.conclusione = [Punto("La garanzia è ancora esercitabile: denuncia tempestiva; va interrotta subito la prescrizione "
                               "biennale e chiesta in via principale l'eliminazione dei vizi, in subordine la riduzione del prezzo"
                               + (f" pari al costo di ripristino di {euro(ripristino)}" if ripristino else "") + ", salvo il danno.",
                               [Rif("cc:1668", "proporzionalmente diminuito"), Rif("cc:2943", "costituire in mora il debitore")])]
        a.dati_mancanti = ["ricevuta di consegna della PEC di denuncia", "eventuale garanzia convenzionale nel contratto"]
    a.procedibilita = [Punto("Per la domanda di riduzione del prezzo o di risarcimento (somme non eccedenti 50.000 euro) serve "
                             "prima l'invito alla negoziazione assistita; la domanda di eliminazione dei vizi e l'accertamento "
                             "tecnico preventivo non ne sono condizionati.",
                             [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti")])]
    a.dubbi.append("L'art. 5, comma 1, d.lgs. 28/2010 elenca fra le materie a mediazione obbligatoria i contratti «di opera»: "
                   "l'appalto è un contratto distinto (art. 1655 c.c.), ma se il giudice lo assimilasse la mancanza si rileva "
                   "entro la prima udienza; valutare la domanda di mediazione per prudenza.")
    return a
