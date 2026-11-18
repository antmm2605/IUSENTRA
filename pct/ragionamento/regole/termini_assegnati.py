"""I termini assegnati dal giudice, trasformati in conclusioni: chi, che cosa, come, perché, se è fatto, se siamo nei termini.

- note scritte (art. 127-ter c.p.c.): termine perentorio assegnato dal giudice; in mancanza di note il giudice
  assegna un nuovo termine o fissa udienza e, se nessuno deposita neppure allora, il processo si estingue;
  nel processo esecutivo già rinviato per mancata comparizione l'estinzione è immediata (art. 631, secondo
  comma, c.p.c.);
- termine della controparte (costituzione del convenuto, art. 416 c.p.c.): non è un nostro adempimento (G-6);
- termine che il provvedimento non riferisce a un adempimento preciso: dubbio dichiarato (G-7).
"""

from __future__ import annotations

import re
from datetime import date, time

from pct.ora_italiana import in_ora_italiana

from ..eventi import comunicazione_di
from ..modello import Atto, Conclusione, Dubbio, Fonte, TermineAssegnato
from ..notifiche import notifiche_di
from ..norme import norme
from ..testo import data_it, date_nel_testo, frasi, giorno, pulito, semplice
from .calcolo import a_ritroso, esito, in_avanti
from .contesto import Contesto, chi

_COME = {
    "note_127ter": ("deposito telematico PCT delle note nel fascicolo del ruolo {rg} (art. 196-quater disp. att. c.p.c.), "
                    "entro l'ora indicata dal giudice se c'è", "builtin-tmp-civ-012"),
    "notifica_ordinata": ("notifica a mezzo PEC all'indirizzo dei pubblici elenchi con relata (art. 3-bis L. 53/1994), "
                          "o tramite ufficiale giudiziario", "builtin-tmp-not-003"),
    "costituzione_convenuto": ("deposito telematico della memoria difensiva", "builtin-tmp-lav-002"),
    "deposito_ordinato": ("deposito telematico PCT nel fascicolo del ruolo {rg}", ""),
}
_NORME = {
    "note_127ter": ("cpc_127ter_testo", "dispatt_196quater"),
    "notifica_ordinata": ("l53_art3bis",),
    "costituzione_convenuto": ("cpc_416",),
    "deposito_ordinato": ("cc_2697",),
}


def _perche(codice: str, termine: TermineAssegnato) -> str:
    if codice == "note_127ter" and "cpc_181" in termine.norme:
        return ("la causa è già stata rinviata perché nessuna parte era comparsa: se nessuno deposita le note nel termine "
                "la causa è cancellata dal ruolo e il processo si estingue (art. 181, primo comma, e art. 127-ter c.p.c.)")
    if codice == "note_127ter" and "cpc_631" in termine.norme:
        return ("il processo esecutivo è già stato rinviato perché nessuna parte era presente: se nessuno deposita le note "
                "entro il termine, il giudice dichiara con ordinanza l'estinzione del processo esecutivo (art. 631, secondo "
                "comma, c.p.c.)")
    if codice == "note_127ter":
        return ("Il giorno di scadenza vale come udienza. Il giudice provvede entro trenta giorni dalla scadenza. "
                "Se nessuna parte deposita, il giudice assegna un nuovo termine o "
                "fissa udienza. Se nessuno deposita nel nuovo termine o compare all’udienza fissata, la causa è cancellata dal ruolo e il processo si "
                "estingue (art. 127-ter c.p.c.)")
    if codice == "notifica_ordinata":
        return "la notifica disposta dal giudice è il presupposto per procedere nei confronti del destinatario all'udienza fissata"
    if codice == "costituzione_convenuto":
        return "oltre il termine il convenuto decade dalle domande riconvenzionali, dalle eccezioni non rilevabili d'ufficio e dai mezzi di prova (art. 416 c.p.c.)"
    if codice == "deposito_ordinato":
        return "il giudice decide sulle prove in atti: senza il deposito nel termine la prova del fatto manca (art. 2697 c.c.)"
    return ""


def _fatto(ctx: Contesto, codice: str, testo: str, dal: str, al: str, ora: str) -> str:
    """La prova dell'adempimento già eseguito dopo il provvedimento ed entro la scadenza, o stringa vuota."""
    if codice == "notifica_ordinata":
        # La finestra temporale da sola non lega la PEC al destinatario e all'atto dell'ordine.
        return ""
    parole = {"note_127ter": {"note"}}.get(codice) or {p for p in re.findall(r"[a-z]{6,}", semplice(testo))} - {"depositare", "ulteriore"}
    try:
        ora_limite = time.fromisoformat(ora.replace(".", ":")) if ora else None
    except ValueError:
        return ""
    for deposito in ctx.depositi:
        if not deposito.prova_consegna or not deposito.documenti_ids:
            continue
        momento = in_ora_italiana(deposito.consegna)
        if momento is None or len(deposito.consegna) < 16 or momento.date() > ctx.oggi:
            continue
        giorno_consegna = momento.date().isoformat()
        if giorno_consegna < dal or (al and giorno_consegna > al):
            continue
        if ora_limite and giorno_consegna == al and momento.time() > ora_limite:
            continue
        if deposito.stato_registro in {"rifiutato_cancelleria", "errore_controlli", "rifiutato", "errore"}:
            continue
        documenti = [ctx.atto(oid) for oid in deposito.documenti_ids]
        corrisponde = any(a and a.appartenenza == "causa" and parole & set(re.findall(r"[a-z]+", semplice(a.nome + " " + a.etichetta)))
                          for a in documenti)
        if corrisponde:
            return f"Trasmissione confermata il {data_it(giorno_consegna)} alle {momento:%H:%M}, ricevuta {deposito.prova_consegna}"
    return ""


def _riscontro_notifica_congiunta(ctx: Contesto, decreto: Atto, ordine: TermineAssegnato) -> Dubbio | None:
    brano = semplice(ordine.fonte.brano)
    if "decreto" not in brano or not re.search(r"\b(?:ricorso|atto introduttivo)\b", brano):
        return None
    prove_decreto = {ctx.notifiche_storiche[oid] for oid in (decreto.id, *decreto.copie) if oid in ctx.notifiche_storiche}
    if len(prove_decreto) != 1:
        return None
    (prova,) = prove_decreto
    invio, data = prova
    notifica, pronuncia = giorno(data), giorno(decreto.data)
    if not notifica or not pronuncia or not pronuncia <= notifica <= ctx.oggi:
        return None
    ricorsi = [a for a in ctx.della_causa() if a.natura == "atto_principale" and a.dello_studio
               and any("ricorso" in semplice(testo) for testo in (a.etichetta, a.nome))]
    ricorsi_consegnati = {min((a.id, *a.copie)) for a in ricorsi
                          if any(ctx.notifiche_storiche.get(oid) == prova for oid in (a.id, *a.copie))}
    if len(ricorsi_consegnati) != 1:
        return None
    documento = ctx.atto(invio)
    return Dubbio(
        "validita_notifica_ordinata",
        f"Accettazione PEC del {data_it(data)}, con consegna documentata del ricorso e del decreto. "
        "Controlla la relata, il recapito nei pubblici elenchi alla data dell'invio e lo stato storico dei certificati.",
        "relata, recapito legale alla data dell'invio e stato storico dei certificati",
        Fonte(invio, documento.nome if documento else "Originale della notifica PEC", data=data),
    )


def _note_in_attesa(ctx: Contesto, dal: str, scadenza: date) -> list[str]:
    """Individua le buste nel fascicolo il cui titolo indica proprio la data assegnata."""
    giorno_atto = giorno(dal)
    if not giorno_atto:
        return []
    riferimenti = set()
    for deposito in ctx.depositi:
        if deposito.stato_registro not in {"consegnato", "controlli_superati", "warn_controlli"}:
            continue
        giorno_deposito = giorno(deposito.data)
        if not giorno_deposito or not giorno_atto <= giorno_deposito <= min(scadenza, ctx.oggi):
            continue
        nome = semplice(deposito.nome_atto)
        if not re.search(r"\bnote\b.{0,45}\b(?:udienza|trattazione|127 ter)\b", nome):
            continue
        if {d for _, _, d in date_nel_testo(nome)} != {scadenza}:
            continue
        riferimento = f"busta {deposito.busta}" if deposito.busta else f"deposito {deposito.fonte_id}"
        fase = {"consegnato": "consegnata al Ministero", "controlli_superati": "controlli automatici superati",
                "warn_controlli": "controlli automatici con avvisi"}[deposito.stato_registro]
        riferimenti.add(f"{riferimento} del {data_it(giorno_deposito)} ({fase})")
    return sorted(riferimenti)


def _scadenza(ctx: Contesto, termine: TermineAssegnato, codice: str) -> tuple[date | None, dict, list[Dubbio]]:
    dubbi: list[Dubbio] = []
    atto = ctx.atto(termine.fonte.oggetto_id)
    norma = (_NORME.get(codice) or ("cpc_155",))[0]
    if termine.formula.startswith("a_ritroso:"):
        _f, giorni, base = termine.formula.split(":")
        calcolo = a_ritroso(date.fromisoformat(base), int(giorni), rito=ctx.rito, oggi=ctx.oggi, perentorio=termine.perentorio,
                            evento="udienza fissata dal giudice", norma=norma)
        return giorno(calcolo.scadenza), {"termine": calcolo}, dubbi
    if termine.formula.startswith("da_"):
        _evento, giorni = termine.formula[3:].split(":")
        comunicazione = comunicazione_di(atto, ctx.comunicazioni) if atto else None
        base = giorno(comunicazione.data) if comunicazione else None
        if base is None:
            dubbio = Dubbio(
                "comunicazione_non_trovata",
                "Non risulta la data della comunicazione da cui decorre il termine.",
                "la PEC di cancelleria collegata al provvedimento con la data di consegna",
                termine.fonte,
            )
            return None, {}, [dubbio]
        calcolo = in_avanti(base, int(giorni), rito=ctx.rito, oggi=ctx.oggi, perentorio=termine.perentorio,
                            evento=f"comunicazione del provvedimento del {data_it(atto.data)}", norma=norma)
        return giorno(calcolo.scadenza), {"termine": calcolo}, dubbi
    scadenza = giorno(termine.scadenza)
    computo = "data fissata dal giudice nel provvedimento" + (f", entro le ore {termine.ora}" if termine.ora else "")
    calcolo = esito(scadenza, oggi=ctx.oggi, perentorio=termine.perentorio, decorrenza=atto.data if atto else "",
                    evento="provvedimento del giudice", computo=computo, rito=ctx.rito)
    return scadenza, {"termine": calcolo}, dubbi


_PAROLE_VUOTE = {"depositare", "deposito", "ulteriore", "ulteriori", "parte", "ricorrente", "resistente", "proprio",
                 "risulti", "nelle", "quali", "della", "delle", "degli", "nella"}
_SOGGETTO = {"attiva": r"(?:parte\s+)?(?:ricorrente|attric\w*|attore|creditric\w*|istante|opponente)",
             "passiva": r"(?:parte\s+)?(?:resistente|convenut\w*|debitric\w*|opposta)"}


def _parole(testo: str) -> set[str]:
    return {p for p in re.findall(r"[a-z]{5,}", semplice(testo))} - _PAROLE_VUOTE


def _stesso_adempimento(a: TermineAssegnato, b: TermineAssegnato, codice: str) -> bool:
    """Lo stesso adempimento assegnato da due provvedimenti: stesse note scritte, o deposito con le stesse parole."""
    if codice == "note_127ter":
        return True
    pa, pb = _parole(a.adempimento), _parole(b.adempimento)
    return bool(pa and pb) and len(pa & pb) / min(len(pa), len(pb)) >= 0.6


def _attestato_dal_giudice(ctx: Contesto, codice: str, dal: str, al: str, fonte_id: str) -> str:
    """Il provvedimento successivo del giudice dà atto dell'adempimento: «la parte ricorrente con le note del 21.10.2026 …
    ha depositato …». È una fonte certa (il giudice attesta ciò che è nel fascicolo d'ufficio): l'adempimento è fatto,
    qualunque giudizio il giudice dia poi sul suo contenuto. Solo la parte del cliente, solo date nel termine."""
    soggetto = _SOGGETTO.get(ctx.posizione)
    inizio, fine = giorno(dal), giorno(al)
    if not soggetto or not inizio or not fine:
        return ""
    for atto in ctx.della_causa():
        if atto.autore != "giudice" or atto.id == fonte_id or not atto.testo or not atto.data or atto.data <= dal:
            continue
        for _p, frase in frasi(atto.testo):
            s = semplice(frase)
            trovato = re.search(soggetto + r"[^.;]{0,60}?(?:con\s+(?:le\s+)?note|ha\s+depositat|ha\s+prodott|depositav)", s)
            if not trovato:
                continue
            if codice == "note_127ter" and "note" not in s:
                continue
            for _i, _f, data in date_nel_testo(frase):
                if inizio <= data <= fine:
                    return (f"Il giudice dà atto del deposito della parte del {data_it(data)} nel provvedimento «{atto.nome}» "
                            f"del {data_it(atto.data)}: «{pulito(frase)[trovato.start():][:220]}»")
    return ""


def _superato(ctx: Contesto, termine: TermineAssegnato, codice: str, scadenza: date | None) -> TermineAssegnato | None:
    """Il termine poi riassegnato da un provvedimento successivo per lo stesso adempimento (artt. 153-154 c.p.c.)."""
    atto = ctx.atto(termine.fonte.oggetto_id)
    if not atto or not atto.data:
        return None
    for altro in ctx.termini:
        if altro is termine or altro.fonte.oggetto_id == termine.fonte.oggetto_id:
            continue
        successivo = ctx.atto(altro.fonte.oggetto_id)
        if not successivo or not successivo.data or successivo.data <= atto.data:
            continue
        if codice == "note_127ter" and scadenza and successivo.data < scadenza.isoformat():
            continue  # le note di un'altra udienza: superano le precedenti solo se il giudice ha provveduto dopo
        codice_altro = _codice_di(altro)
        if codice_altro == codice and _stesso_adempimento(termine, altro, codice):
            return altro
    return None


def _codice_di(termine: TermineAssegnato) -> str:
    return next((k for k in _COME if termine.adempimento.startswith({"note_127ter": "Depositare le note",
                 "notifica_ordinata": "Notificare", "costituzione_convenuto": "Costituirsi", "deposito_ordinato": "Depositare"}[k])), "")


def conclusioni_termini(ctx: Contesto) -> list[Conclusione]:
    esito_: list[Conclusione] = []
    for termine in ctx.termini:
        codice = _codice_di(termine)
        onerato = chi(termine.onerato, ctx.posizione)
        if onerato == "terzo":
            continue
        scadenza, calcolo, dubbi = _scadenza(ctx, termine, codice)
        conseguenza = _perche(codice, termine)
        if calcolato := calcolo.get("termine"):
            calcolato.conseguenze = conseguenza
            calcolato.ora_assegnata = termine.ora
        come, template = _COME.get(codice, ("", ""))
        if not codice:
            dubbi.append(Dubbio("adempimento_generico", "Il provvedimento assegna un termine senza che la lettura riconosca "
                                "l'adempimento preciso: leggere il brano citato.", "l'adempimento scritto nel provvedimento", termine.fonte))
        if onerato == "ignoto":
            dubbi.append(Dubbio("parte_onerata_ignota", "Non si sa quale parte sia onerata del termine.",
                                "la posizione del cliente (attore o convenuto) o la parte nominata nel provvedimento", termine.fonte))
        atto = ctx.atto(termine.fonte.oggetto_id)
        prova = _fatto(ctx, codice, termine.adempimento, atto.data if atto else "", scadenza.isoformat() if scadenza else "", termine.ora)
        if not prova and onerato in {"noi", "tutte_le_parti"} and codice in {"note_127ter", "deposito_ordinato"} and atto and scadenza:
            prova = _attestato_dal_giudice(ctx, codice, atto.data, scadenza.isoformat(), atto.id)
        # Solo i depositi e le note si riassegnano (artt. 127-ter e 421 c.p.c.); gli ordini di notifica di provvedimenti
        # diversi restano distinti, ciascuno con il suo destinatario.
        riassegnato = (None if prova or onerato == "controparte" or codice not in {"note_127ter", "deposito_ordinato", ""}
                       else _superato(ctx, termine, codice, scadenza))
        if onerato == "controparte":
            stato, motivo = "non_dovuto", f"termine della controparte ({termine.adempimento.lower()}): non è un nostro adempimento"
        elif prova:
            stato, motivo = "fatto", prova
        elif riassegnato is not None:
            # Lo stesso adempimento è stato riassegnato da un provvedimento successivo: vale il nuovo termine
            # (un solo adempimento nel modello, non due passi quasi uguali).
            successivo = ctx.atto(riassegnato.fonte.oggetto_id)
            stato = "non_dovuto"
            motivo = (f"Termine superato dal provvedimento «{successivo.nome if successivo else riassegnato.fonte.nome}» del "
                      f"{data_it(successivo.data if successivo else riassegnato.fonte.data)}, che assegna di nuovo lo stesso "
                      f"adempimento: vale il nuovo termine")
            dubbi = []
        else:
            stato = "dubbio" if onerato == "ignoto" or (dubbi and not scadenza) else "da_fare"
            motivo = "Nelle fonti esaminate non risulta una prova dell'adempimento."
            if codice == "note_127ter" and atto and scadenza:
                cand = [d for d in ctx.depositi if d.accettato and d.fonte_id and atto.data
                        and atto.data <= d.data <= scadenza.isoformat() and giorno(d.data) <= ctx.oggi
                        and re.search(r"\bnote\b.{0,45}\b(?:udienza|trattazione|127 ter)\b", semplice(d.nome_atto))]
                pendenti = _note_in_attesa(ctx, atto.data, scadenza)
                if pendenti and not cand:
                    stato = "dubbio"
                    riferimenti = ", ".join(pendenti)
                    motivo = (f"Per le note del {data_it(scadenza)} risulta {riferimenti}. "
                              "Verificare l’esito finale della cancelleria e la corrispondenza delle note depositate.")
                    dubbi.append(Dubbio("note_in_attesa_cancelleria", motivo,
                                        "l’esito finale della cancelleria e il testo delle note riferito a questa udienza",
                                        termine.fonte))
                if cand:
                    stato = "dubbio"
                    riferimenti = ", ".join(f"{data_it(d.data)} (deposito {d.fonte_id})" for d in cand)
                    motivo = f"La cancelleria ha accettato note scritte il {riferimenti}. Verificare se riguardano questa udienza."
                    dubbi.append(Dubbio("note_depositate_da_correlare", motivo,
                                        "il testo delle note depositate o il relativo evento di cancelleria che le riferisce a questa udienza",
                                        termine.fonte))
            if codice == "notifica_ordinata" and atto:
                riscontro = _riscontro_notifica_congiunta(ctx, atto, termine) if onerato == "noi" else None
                if riscontro:
                    stato, motivo = "dubbio", riscontro.testo
                    dubbi.append(riscontro)
                elif notifiche_di(atto.id, ctx.notifiche, ctx.atti):
                    stato = "dubbio"
                    motivo = ("Risultano tracce della notifica del provvedimento. "
                              "Collegare la ricevuta di consegna all'ordine, agli atti richiesti e al destinatario.")
                    dubbi.append(Dubbio("notifica_ordinata_da_correlare", motivo,
                                        "la consegna originale con gli atti e il destinatario indicati nell'ordine", termine.fonte))
            if scadenza and scadenza < ctx.oggi:
                dubbi.append(Dubbio("adempimento_non_provato", f"Il termine è scaduto il {data_it(scadenza)} e nel fascicolo non c'è "
                                    "la prova dell'adempimento.", "la ricevuta del deposito o della notifica, se eseguiti", termine.fonte))
        if stato in {"fatto", "non_dovuto"}:
            # chi ha già adempiuto (o non deve) non ha dubbi sul computo: restano solo quelli sull'adempimento
            dubbi = [d for d in dubbi if d.codice not in {"comunicazione_non_trovata", "decorrenza_ignota", "adempimento_non_provato"}]
        riferimenti = _NORME.get(codice, ()) + tuple(termine.norme)
        if codice == "notifica_ordinata" and ctx.rito.codice == "lavoro":
            brano = semplice(termine.fonte.brano)
            if "decreto" in brano and ("ricorso" in brano or "atto introduttivo" in brano):
                riferimenti += ("cpc_415_notifica",)
                if ctx.rito.contro_pa:
                    riferimenti += ("rd1611_art11",)
        esito_.append(Conclusione(
            codice=codice or "termine_assegnato", cosa=termine.adempimento or "Adempimento assegnato dal giudice (vedi brano)",
            letto=termine.fonte, norme=norme(*dict.fromkeys(riferimenti)),
            come=come.format(rg=ctx.rg), perche=conseguenza, stato=stato, prova_o_motivo=motivo,
            termine=calcolo.get("termine"), template=template, onerato=onerato, dubbi=dubbi,
        ))
    return esito_


__all__ = ["conclusioni_termini"]
