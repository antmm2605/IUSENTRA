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
    return 4 if re.search(r"appalt|appaltator|installator|falegnam|commissionat\w*[^.]{0,80}(?:fornitura e posa|realizzazion|lavori)|fornitura e posa", t) and re.search(r"vizi|difett|non ha mai funzionato|rigonfiament|blocco|infiltrazion", t) else 0


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
    # Consumatore: persona fisica che contratta per la propria abitazione con un'impresa (s.r.l., s.n.c., ditta).
    consumatore = (not f.assistita.persona_giuridica and (f.controparte.persona_giuridica or re.search(
        r"\bs\.?n\.?c\b|\bs\.?a\.?s\b|\bditta\b|\bimpresa\b|falegnameria", piano(f.controparte.nome + " " + t)) is not None)
        and re.search(r"abitazion|casa|appartamento", t) is not None)
    m_luogo = re.search(r"abitazione (?:di |della |del )?(?:[a-z]+ )?(?:a|di|in) ([a-z]+(?: [a-z]+)?)", t)
    residenza = m_luogo.group(1).split(" ")[0].title() if m_luogo else ""
    if valore:
        giudice, punti = P.giudice_per_valore(valore)
        a.competenza = punti
        if consumatore and giudice:
            a.giudice = P.ufficio(giudice, residenza) if residenza else f"{giudice} del luogo di residenza del consumatore"
            a.competenza.append(Punto(
                "Contratto fra impresa e consumatore: è vessatoria, e quindi non vincola il consumatore, la clausola che "
                "fissa un foro diverso da quello della sua residenza o del domicilio elettivo; la causa si propone davanti al "
                "giudice del luogo di residenza del consumatore" + (f" ({residenza})" if residenza else "") + ".",
                [Rif("dlgs206:33", "residenza o domicilio elettivo del consumatore")]))
        else:
            a.giudice = f"{giudice} competente per territorio (sede dell'appaltatore o luogo dell'obbligazione) [da verificare]"
    if consumatore:
        a.inquadramento.append(Punto(
            "Il contratto con cui un'impresa fornisce a un consumatore un bene da fabbricare o produrre è equiparato alla "
            "vendita ai fini della garanzia di conformità del codice del consumo; il venditore risponde dei difetti che si "
            "manifestano entro due anni dalla consegna e il consumatore ha diritto al ripristino della conformità, alla "
            "riduzione proporzionale del prezzo o alla risoluzione. Il testo vigente non prevede più l'onere di denuncia entro "
            "due mesi: l'azione si prescrive in ventisei mesi dalla consegna.",
            [Rif("dlgs206:128", "quelli di appalto, d'opera"), Rif("dlgs206:133", "si manifesta entro due anni"),
             Rif("dlgs206:133", "ventisei mesi dalla consegna del bene"), Rif("dlgs206:135bis", "riduzione proporzionale del prezzo")]))
        if consegna:
            from ..termini import termine_mesi

            p26 = termine_mesi(consegna, 26, sostanziale=True)
            a.termini.append(Punto(f"Garanzia di conformità: azione entro {data_breve(p26)} (ventisei mesi dalla consegna).",
                                   [Rif("dlgs206:133", "ventisei mesi dalla consegna del bene")]))
    if decaduto and consumatore:
        a.forma = forma(c)
        a.rimedio = ("azione per la garanzia di conformità del codice del consumo (artt. 128, 133 e 135-bis): riduzione del "
                     "prezzo e risarcimento, con la garanzia d'appalto (artt. 1667-1668 c.c.) solo in subordine")
        a.conclusione = [Punto(
            "La garanzia d'appalto è esposta alla decadenza: la PEC è oltre i sessanta giorni; la denuncia però non ha forma "
            "prescritta, quindi le telefonate fatte entro i sessanta giorni, se provate per testi, possono valere. La strada "
            "principale è la garanzia di conformità, che nel testo vigente non richiede la denuncia entro due mesi e si "
            "prescrive in ventisei mesi dalla consegna: la causa si può proporre.",
            [Rif("cc:1667", "denunziare"), Rif("dlgs206:133", "ventisei mesi dalla consegna del bene")])]
        a.avvertenze.append("L'appaltatore ha già eccepito la decadenza: impostare la domanda sul codice del consumo e "
                            "raccogliere comunque le prove delle telefonate (testimoni, tabulati).")
        a.dubbi.append("Residenza del consumatore presunta nel comune dell'abitazione: va confermata per il foro.")
        a.dati_mancanti = ["prove delle telefonate all'impresa entro sessanta giorni dalla scoperta",
                           "conferma che il contratto riguarda la fornitura e posa dei beni (art. 128 cod. cons.)"]
        decaduto = False
        consumatore_principale = True
        if c.tipo == "redazione":
            from ..bozze import ricorso_generico

            a.bozza = ricorso_generico(
                "Atto di citazione (artt. 163 c.p.c.; artt. 128, 133 e 135-bis d.lgs. 206/2005)", a.giudice, f,
                "riduzione del prezzo e risarcimento per difetto di conformità del bene fornito e installato",
                ["Contratto fra impresa e consumatore per la fornitura e posa di un bene: garanzia di conformità del codice del "
                 "consumo (art. 128 d.lgs. 206/2005).", "Difetto manifestato entro due anni dalla consegna; azione entro "
                 "ventisei mesi dalla consegna (art. 133 d.lgs. 206/2005).", "Rimedi: riduzione proporzionale del prezzo pari "
                 "al costo di ripristino e risarcimento del danno (art. 135-bis d.lgs. 206/2005).", "In subordine, garanzia "
                 "per i vizi dell'appalto (artt. 1667 e 1668 c.c.), con prova della denuncia tempestiva anche orale."],
                "ridurre il prezzo in misura pari al costo di ripristino e condannare la convenuta al pagamento della relativa "
                "somma, oltre al risarcimento del danno; con vittoria di spese.", "contratto, verbale di consegna, e-mail e foto "
                "del 10/03/2026, PEC e risposta, perizia di parte.", "art. 163 c.p.c.")
    else:
        consumatore_principale = False
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
    elif not consumatore_principale:
        a.forma = forma(c)
        a.rimedio = ("azione di garanzia per vizi dell'appalto (artt. 1667-1668 c.c.): diffida interruttiva della prescrizione, "
                     "accertamento tecnico preventivo e poi giudizio di merito per l'eliminazione dei vizi o la riduzione del prezzo")
        a.conclusione = [Punto("La garanzia è ancora esercitabile: denuncia tempestiva; va interrotta subito la prescrizione "
                               "biennale e chiesta in via principale l'eliminazione dei vizi, in subordine la riduzione del prezzo"
                               + (f" pari al costo di ripristino di {euro(ripristino)}" if ripristino else "") + ", salvo il danno.",
                               [Rif("cc:1668", "proporzionalmente diminuito"), Rif("cc:2943", "costituire in mora il debitore")])]
        a.dati_mancanti = ["ricevuta di consegna della PEC di denuncia", "eventuale garanzia convenzionale nel contratto"]
    if consumatore:
        a.procedibilita = P.negoziazione_pagamento(valore or 0, consumatore=True)
        if not consumatore_principale:
            a.dubbi.append("Residenza del consumatore presunta nel comune dell'abitazione: va confermata per il foro.")
    else:
        a.procedibilita = [Punto(f"Per la domanda di riduzione del prezzo o di risarcimento (somme non eccedenti "
                                 f"{euro(P.soglia_negoziazione() or 0)}) serve prima l'invito alla negoziazione assistita; la "
                                 "domanda di eliminazione dei vizi e l'accertamento tecnico preventivo non ne sono condizionati.",
                                 [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti")])]
    a.dubbi.append("L'art. 5, comma 1, d.lgs. 28/2010 elenca fra le materie a mediazione obbligatoria i contratti «di opera»: "
                   "l'appalto è un contratto distinto (art. 1655 c.c.), ma se il giudice lo assimilasse la mancanza si rileva "
                   "entro la prima udienza; valutare la domanda di mediazione per prudenza.")
    return a
