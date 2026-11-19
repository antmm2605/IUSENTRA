"""I testi delle bozze, compilati solo con dati certi.

Ogni testo segue la norma che regola l'atto e niente di più: le istanze, le conclusioni, gli importi non letti e
le scelte difensive restano segnaposti «[da completare: …]». Norme verificate sul testo vigente dell'archivio
Normattiva del software (18/11/2026): art. 127-ter c.p.c.; art. 3-bis, commi 4, 5 e 6, L. 53/1994; art. 11
R.D. 1611/1933; artt. 474, 480 e 654 c.p.c.; art. 14, commi 1 e 1-bis, D.L. 669/1996; art. 2, comma 2, D.M. 55/2014 (rimborso forfettario).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from pct.fascicolo_lettura._testo import data_it, pulisci

from .contesto import Contesto, euro, percentuale, provvedimento
from .modello import manca

OGGETTO_PEC_L53 = "notificazione ai sensi della legge n. 53 del 1994"


def _unisci(righe: list[str]) -> str:
    return "\n\n".join(r for r in righe if r is not None and r != "")


def note_127_ter(ctx: Contesto, voce: dict[str, Any], *, udienza: str) -> str:
    """Note scritte in sostituzione dell'udienza: sole istanze e conclusioni (art. 127-ter, primo comma, c.p.c.)."""
    termine = voce.get("termine") or {}
    scadenza = data_it(termine.get("scadenza"))
    ora = pulisci(termine.get("ora_assegnata"))
    entro = f"{scadenza} entro le ore {ora}" if ora else scadenza
    sostituita = f"l'udienza del {udienza}" if udienza else f"l'udienza {manca('data dell’udienza sostituita')}"
    righe = ctx.intestazione_ufficio()
    if udienza:
        righe.append(f"*Udienza del {udienza} sostituita dal deposito di note scritte*")
    righe += [
        "## Note scritte ex art. 127-ter c.p.c.",
        *ctx.parti(),
        "Il sottoscritto difensore,",
        (f"visto il {provvedimento(voce)}, con cui il Giudice ha disposto che {sostituita} sia sostituita dal deposito "
        f"di note scritte nel termine perentorio del {entro};"),
        "deposita le presenti note, contenenti le sole istanze e conclusioni (art. 127-ter, primo comma, c.p.c.).",
        "### Istanze",
        manca("eventuali istanze; se non ve ne sono, eliminare la sezione"),
        "### Conclusioni",
        manca("conclusioni, come nell'atto introduttivo e negli scritti successivi"),
        *ctx.firma(),
    ]
    return _unisci(righe)


def nota_di_deposito(ctx: Contesto, voce: dict[str, Any]) -> str:
    """Nota di deposito dei documenti richiesti dal giudice, con il richiamo al provvedimento e al termine."""
    termine = voce.get("termine") or {}
    scadenza = data_it(termine.get("scadenza"))
    oggetto = pulisci(voce.get("cosa"))
    oggetto = oggetto[:1].lower() + oggetto[1:] if oggetto else manca("oggetto del deposito richiesto")
    righe = ctx.intestazione_ufficio() + [
        "## Nota di deposito",
        *ctx.parti(),
        "Il sottoscritto difensore,",
        f"in esecuzione del {provvedimento(voce)}, con cui il Giudice ha assegnato a "
        f"{'parte ' + ctx.ruoli[0] if ctx.ruoli[0] else 'questa parte'} termine"
        + (f" fino al {scadenza}" if scadenza else "") + f" per {oggetto},",
        "deposita i seguenti documenti:",
        f"1. {manca('primo documento depositato')}",
        f"2. {manca('eventuali ulteriori documenti, o eliminare la riga')}",
    ]
    if termine.get("scaduto") and scadenza:
        righe.append(manca(f"il termine del {scadenza} è scaduto ({pulisci(termine.get('natura')) or 'natura da verificare'}): "
                           "valutare se indicare le ragioni del deposito successivo, o eliminare la riga"))
    righe += ["Con osservanza.", *ctx.firma()]
    return _unisci(righe)


def _destinatario_pa(ctx: Contesto) -> str:
    amministrazione = ctx.controparte if ctx.controparte and not ctx.controparte_e_avvocatura else ""
    if not amministrazione:
        accenno = ctx.controparte_nel_titolo
        amministrazione = manca("amministrazione convenuta" + (f" (nel titolo del fascicolo: «{accenno}»)" if accenno else ""))
    return f"{amministrazione}, in persona del legale rappresentante pro tempore, presso l'{ctx.avvocatura}" if ctx.avvocatura else amministrazione


def relata_notifica(ctx: Contesto, voce: dict[str, Any], *, documenti: list[dict[str, str]]) -> str:
    """Relata di notificazione ex art. 3-bis L. 53/1994 (motore canonico di pct.notifiche_legali) e testo della PEC."""
    from pct.notifiche_legali import render_control_document, render_relata, select_relata_template

    numero, _, anno = ctx.rg.partition("/")
    studio = ctx.studio
    pa = ctx.pubblica_amministrazione
    payload = {
        "avvocato_nome": ctx.avvocato.removeprefix("Avv. ").strip() or manca("nome del difensore"),
        "avvocato_cf": pulisci(studio.get("cf_avvocato")) or manca("codice fiscale dell'avvocato notificante"),
        "mittente_pec": pulisci(studio.get("pec")) or manca("PEC del notificante risultante da pubblici elenchi"),
        "studio_indirizzo": pulisci(studio.get("indirizzo")) or manca("indirizzo dello studio"),
        "studio_cap": pulisci(studio.get("cap")), "studio_citta": pulisci(studio.get("citta")),
        "studio_provincia": pulisci(studio.get("provincia")),
        "assistito_nome": ctx.cliente or manca("parte assistita"),
        "assistito_cf": ctx.cliente_cf or manca("codice fiscale della parte che ha conferito la procura"),
        "procedimento_pendente": bool(ctx.rg), "ufficio_giudiziario": ctx.ufficio, "sezione": ctx.sezione,
        "numero_rg": numero, "anno_rg": anno, "giudice": ctx.giudice,
        "destinatari": [{
            "tipo": "pa" if pa else "controparte",
            "nome": _destinatario_pa(ctx) if pa else ctx.controparte_o_manca,
            "pec": manca("indirizzo PEC del destinatario tratto dal pubblico elenco"),
            "fonte_pec": "registro_ppaa" if pa else "altro_pubblico_elenco",
        }],
        "documenti": documenti,
    }
    modello = select_relata_template(payload)
    relata = render_relata(payload, template=modello)
    relata = re.sub(r"\[dato mancante: ([^\]]+)\]", lambda m: manca(m.group(1)), relata)
    corpo = render_control_document("corpo_pec_standard", payload, template=modello)
    righe = [
        "# Relata di notificazione",
        manca("esportare la relata in PDF come documento separato e firmarla digitalmente prima dell'invio "
              "(art. 3-bis, comma 5, L. 53/1994); poi eliminare questa riga"),
        *[r for r in relata.strip().split("\n\n")],
        "## Testo del messaggio PEC",
        f"**Oggetto:** {OGGETTO_PEC_L53}",
        corpo,
    ]
    return _unisci(righe)


def _accessori(compenso: Decimal, *, iva: str) -> tuple[list[str], Decimal]:
    """Rimborso forfettario 15% (art. 2, comma 2, D.M. 55/2014) e contributo integrativo C.P.A. del 4% sul compenso e sul rimborso."""
    forfettario = percentuale(compenso, "15")
    cpa = percentuale(compenso + forfettario, "4")
    righe = [f"compenso liquidato: {euro(compenso)}", f"rimborso forfettario delle spese generali (15%): {euro(forfettario)}",
             f"C.P.A. (4%): {euro(cpa)}"]
    totale = compenso + forfettario + cpa
    if iva == "forfetario":
        righe.append("I.V.A.: non dovuta (regime forfetario dello studio)")
    else:
        righe.append(manca("I.V.A. sul compenso, se dovuta, secondo il regime fiscale"))
    return righe, totale


def richiesta_pagamento_pa(ctx: Contesto, credito: dict[str, Any]) -> str:
    """Richiesta di pagamento alla P.A. delle spese liquidate e distratte, prima del precetto (art. 14 D.L. 669/1996)."""
    compenso: Decimal = credito["importo"]
    righe_importo, totale = _accessori(compenso, iva=credito.get("iva", ""))
    distratte = credito.get("distratte")
    beneficiario = ("in favore del sottoscritto difensore, dichiaratosi antistatario (art. 93 c.p.c.)" if distratte
                    else manca("beneficiario delle spese: parte assistita o difensore antistatario"))
    studio = ctx.studio
    righe = [
        f"**{ctx.avvocato_o_manca}**",
        pulisci(studio.get("indirizzo_completo")) or manca("indirizzo dello studio"),
        f"PEC: {pulisci(studio.get('pec')) or manca('PEC dello studio')}",
        f"Spett.le **{_destinatario_pa(ctx).split(', in persona')[0]}**",
        manca("ufficio dell'amministrazione competente al pagamento e suo indirizzo PEC dal Registro PP.AA."),
        f"e, per conoscenza, {ctx.avvocatura}" if ctx.avvocatura else "",
        (f"**Oggetto:** {ctx.ufficio_o_manca}, R.G. n. {ctx.rg_o_manca}, {credito['fonte']} — {ctx.cliente or manca('parte assistita')} "
        "— richiesta di pagamento delle spese di lite liquidate"),
        f"Il sottoscritto {ctx.avvocato_o_manca}, difensore di {ctx.cliente or manca('parte assistita')} nel giudizio indicato in oggetto,",
        "premesso che",
        (f"- con la {credito['fonte'].lower() if credito['fonte'] else manca('sentenza')} {manca('numero della sentenza')} "
        f"il {ctx.ufficio_o_manca} ha condannato l'amministrazione al pagamento delle spese di lite, liquidate in {euro(compenso)} "
        f"per compenso, oltre accessori di legge, {beneficiario};"),
        f"- il titolo esecutivo è stato notificato il {manca('data della notificazione del titolo esecutivo')};",
        "chiede",
        f"il pagamento della somma di {euro(totale)}, così determinata:",
        *[f"- {r}" for r in righe_importo],
        f"mediante bonifico sul conto {pulisci(studio.get('iban')) or manca('IBAN')} intestato a {ctx.avvocato_o_manca if distratte else manca('beneficiario')}.",
        ("Si ricorda che le amministrazioni completano le procedure per il pagamento entro centoventi giorni dalla "
        "notificazione del titolo esecutivo, decorsi i quali il creditore può procedere alla notifica del precetto e "
        "all'esecuzione forzata (art. 14, comma 1, D.L. 669/1996, convertito dalla L. 30/1997)."),
        "Distinti saluti.",
        *ctx.firma(),
    ]
    return _unisci(righe)


def precetto(ctx: Contesto, titolo: dict[str, Any]) -> str:
    """Atto di precetto (artt. 474 e 480 c.p.c.; art. 654 c.p.c. sul decreto ingiuntivo esecutivo).

    ``titolo``: descrizione (str), voci (list[str]) e totale (Decimal|None), menzione_654 (str), pa (bool).
    """
    pa = bool(titolo.get("pa"))
    istante = f"**{ctx.cliente or manca('parte istante')}**" + (f" (C.F. {ctx.cliente_cf})" if ctx.cliente_cf else f" ({manca('codice fiscale della parte istante')})")
    if titolo.get("distratte"):
        istante = f"**{ctx.avvocato_o_manca}**, difensore antistatario di {ctx.cliente or manca('parte assistita')} (art. 93 c.p.c.)"
    debitore = _destinatario_pa(ctx).split(", presso")[0] if pa else (ctx.controparte_o_manca + (f" (C.F. {titolo['cf_debitore']})" if titolo.get("cf_debitore") else f" ({manca('codice fiscale del debitore')})"))
    righe = [
        "# Atto di precetto",
        "*(artt. 474 e 480 c.p.c.)*",
        f"Su istanza {'del sottoscritto ' if titolo.get('distratte') else 'di '}{istante}" + ("" if titolo.get("distratte") else f", rappresentata e difesa da {ctx.avvocato_o_manca}"),
        f"in forza {titolo['descrizione']}, titolo esecutivo (art. 474 c.p.c.)" + (f"; {titolo['menzione_654']}" if titolo.get("menzione_654") else "")
        + f", notificato il {manca('data della notificazione del titolo esecutivo')},",
        "## Intima e fa precetto",
        f"a **{debitore}**, " + (manca("sede dell'amministrazione presso cui notificare il precetto") if pa
                                  else manca("residenza, sede o domicilio del debitore")) + ",",
        "di pagare entro dieci giorni dalla notificazione del presente atto le seguenti somme:",
        *[f"- {voce}" for voce in titolo.get("voci") or []],
        f"- competenze e spese del presente atto: {manca('importo secondo il D.M. 55/2014')}",
        f"per un totale di {euro(titolo['totale']) + ' oltre ' if titolo.get('totale') else ''}{manca('totale complessivo con interessi e competenze')},",
        "con l'avvertimento che, in mancanza, si procederà a esecuzione forzata (art. 480, primo comma, c.p.c.).",
        ("Avverte il debitore che può, con l'ausilio di un organismo di composizione della crisi o di un professionista "
        "nominato dal giudice, porre rimedio alla situazione di sovraindebitamento concludendo con i creditori un accordo "
        "di composizione della crisi o proponendo agli stessi un piano del consumatore (art. 480, secondo comma, c.p.c.)."),
        f"Giudice competente per l'esecuzione: {manca('giudice del luogo dell’esecuzione (art. 480, terzo comma, c.p.c.)')}.",
    ]
    if pa:
        righe.append(manca("il precetto si notifica solo decorsi centoventi giorni dalla notificazione del titolo "
                           "(art. 14, comma 1, D.L. 669/1996): indicare la data da cui è possibile, poi eliminare la riga"))
    righe += [*ctx.firma()]
    return _unisci(righe)


__all__ = ["OGGETTO_PEC_L53", "nota_di_deposito", "note_127_ter", "precetto",
           "relata_notifica", "richiesta_pagamento_pa"]
