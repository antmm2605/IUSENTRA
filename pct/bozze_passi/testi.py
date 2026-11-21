"""I testi delle bozze, compilati solo con dati certi.

Ogni testo segue la norma che regola l'atto e niente di più: le istanze, le conclusioni, gli importi non letti e
le scelte difensive restano segnaposti «[da completare: …]». Norme verificate sul testo vigente dell'archivio
Normattiva del software (18/11/2026): art. 127-ter c.p.c.; art. 3-bis, commi 4, 5 e 6, L. 53/1994; art. 11
R.D. 1611/1933; artt. 26-bis, 474, 480 (terzo comma: elezione di domicilio) e 654 c.p.c.; art. 14, commi 1 e 1-bis,
D.L. 669/1996; art. 2, comma 2, D.M. 55/2014 (rimborso forfettario); art. 11 L. 576/1980 (contributo integrativo).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from pct.fascicolo_lettura._testo import data_it, pulisci

from .contesto import Contesto, euro, percentuale, provvedimento
from .amministrazioni import denominazione, preposizione_articolata, rappresentante
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
    else:
        amministrazione = denominazione(amministrazione)
    # Denominazione ufficiale e rappresentante (pct.bozze_passi.amministrazioni): «Ministero …, in persona del Ministro
    # pro tempore», domiciliato presso l'Avvocatura dello Stato (art. 11 R.D. 1611/1933).
    return f"{amministrazione}, {rappresentante(amministrazione)}, presso l'{ctx.avvocatura}" if ctx.avvocatura else amministrazione


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


def _accessori(compenso: Decimal, *, iva: str, forfettario: bool) -> tuple[list[str], Decimal | None]:
    """Gli accessori del compenso liquidato, scritti solo se certi; il totale solo se tutti certi (altrimenti None).

    - Rimborso forfettario delle spese generali nella misura del 15% (art. 2, comma 2, D.M. 55/2014) solo se il
      provvedimento lo liquida («oltre rimborso forfettario», «spese generali»): altrimenti un segnaposto.
    - Contributo integrativo C.P.A. del 4% sul compenso e sul rimborso (art. 11 L. 576/1980).
    - I.V.A. esclusa solo se il regime forfetario (RF19) o dei minimi (RF02) risulta dalla scheda dello studio.
    """
    righe = [f"compenso liquidato: {euro(compenso)}"]
    if forfettario:
        rimborso = percentuale(compenso, "15")
        cpa = percentuale(compenso + rimborso, "4")
        righe += [f"rimborso forfettario delle spese generali (15%): {euro(rimborso)}", f"C.P.A. (4%): {euro(cpa)}"]
        totale: Decimal | None = compenso + rimborso + cpa
    else:
        righe += [f"rimborso forfettario delle spese generali: {manca('se e in che misura lo liquida il provvedimento (art. 2, comma 2, D.M. 55/2014)')}",
                  f"C.P.A. (4%): {manca('importo sul compenso e sull’eventuale rimborso forfettario')}"]
        totale = None
    if iva == "forfetario":
        righe.append("I.V.A.: non dovuta (regime forfetario dello studio)")
    else:
        righe.append(manca("I.V.A. sul compenso, se dovuta, secondo il regime fiscale"))
    return righe, totale


def notifica_del_titolo(titolo: dict[str, Any]) -> str:
    """«20/04/2026 all'amministrazione (…) e all'Avvocatura …» se la notificazione del titolo è provata, altrimenti il
    segnaposto. I destinatari sono quelli delle ricevute di consegna verificate (relata, art. 3-bis L. 53/1994)."""
    data = pulisci(titolo.get("notificato_il"))
    if not data:
        return manca("data della notificazione del titolo esecutivo")
    elenco = titolo.get("destinatari_titolo") or []
    amministrazione = [d for d in elenco if d.get("ruolo") == "amministrazione"]
    avvocatura = [d for d in elenco if d.get("ruolo") == "avvocatura_stato"]
    parti = []
    if amministrazione:
        parti.append("all'amministrazione (" + "; ".join(_ufficio(d) for d in amministrazione) + ")")
    if avvocatura:
        parti.append(("e all'" if parti else "alla sola ") + "Avvocatura dello Stato (" + "; ".join(_ufficio(d) for d in avvocatura) + ")")
    return f"{data} " + " ".join(parti) if parti else data


def _ufficio(destinatario: dict[str, str]) -> str:
    voce = destinatario.get("denominazione") or destinatario.get("pec") or ""
    if destinatario.get("sede"):
        voce += f", {destinatario['sede']}"
    return voce + (f", PEC {destinatario['pec']}" if destinatario.get("pec") else "")


def uffici_del_titolo(titolo: dict[str, Any]) -> str:
    """Gli uffici dell'amministrazione a cui è stato consegnato il titolo: proposta per precetto e richiesta."""
    amministrazione = [d for d in titolo.get("destinatari_titolo") or [] if d.get("ruolo") == "amministrazione"]
    return "; ".join(_ufficio(d) for d in amministrazione)


def elezione_domicilio(ctx: Contesto, titolo: dict[str, Any]) -> str:
    """Il recapito della parte istante richiesto dall'art. 480, terzo comma, c.p.c. (testo vigente dopo il D.Lgs. 164/2024).

    La norma vigente consente, in alternativa alla dichiarazione di residenza o all'elezione di domicilio nel comune
    sede del giudice dell'esecuzione, l'indicazione dell'indirizzo di posta elettronica certificata risultante da
    pubblici elenchi: per l'avvocato è la PEC dello studio (iscritta nel ReGIndE e in INI-PEC), quindi si scrive da sé.
    Senza PEC il domicilio è lo studio solo se il comune dell'esecuzione è certo (``titolo["comune_esecuzione"]``) e
    coincide con la sede dello studio; altrimenti resta un segnaposto. In mancanza le opposizioni si propongono davanti
    al giudice del luogo della notificazione del precetto (art. 480, terzo comma, c.p.c.).
    """
    studio = ctx.studio
    pec = pulisci(studio.get("pec"))
    if pec:
        return (f"Indica, quale proprio recapito, l'indirizzo di posta elettronica certificata risultante dai pubblici elenchi "
                f"{pec} (art. 480, terzo comma, c.p.c.).")
    comune = pulisci(titolo.get("comune_esecuzione"))
    if comune and comune.lower() == pulisci(studio.get("citta")).lower() and pulisci(studio.get("indirizzo_completo")):
        indirizzo = f"presso lo studio del difensore in {pulisci(studio.get('indirizzo_completo'))}"
    else:
        indirizzo = "in " + manca("indirizzo nel comune sede del giudice dell’esecuzione"
                          + (f" ({comune})" if comune else (" (crediti verso la P.A.: luogo del terzo debitore, art. 26-bis, "
                                                            "primo comma, c.p.c.)" if titolo.get("pa") else "")))
    return f"Elegge domicilio {indirizzo} (art. 480, terzo comma, c.p.c.)."


def giudice_dell_esecuzione(titolo: dict[str, Any]) -> str:
    """L'indicazione del giudice competente per l'esecuzione (art. 480, terzo comma, c.p.c. vigente).

    Dipende dal pignoramento che l'avvocato sceglie: per i crediti verso una pubblica amministrazione è il giudice del
    luogo in cui ha sede il terzo debitore (art. 26-bis, primo comma, c.p.c.), altrimenti quello del luogo del debitore o
    dei beni (artt. 26 e 26-bis, secondo comma, c.p.c.). La Lettura non lo sa: è un dato che resta da completare."""
    comune = pulisci(titolo.get("giudice_esecuzione"))
    if comune:
        return f"Indica quale giudice competente per l'esecuzione il {comune} (art. 480, terzo comma, c.p.c.)."
    criterio = ("Tribunale del luogo in cui ha sede il terzo debitore, art. 26-bis, primo comma, c.p.c." if titolo.get("pa")
                else "Tribunale competente secondo il pignoramento scelto, artt. 26 e 26-bis c.p.c.")
    return f"Indica quale giudice competente per l'esecuzione il {manca(criterio)} (art. 480, terzo comma, c.p.c.)."


def richiesta_pagamento_pa(ctx: Contesto, credito: dict[str, Any]) -> str:
    """Richiesta di pagamento alla P.A. delle spese liquidate e distratte, prima del precetto (art. 14 D.L. 669/1996)."""
    compenso: Decimal = credito["importo"]
    righe_importo, totale = _accessori(compenso, iva=credito.get("iva", ""), forfettario=bool(credito.get("forfettario")))
    distratte = credito.get("distratte")
    beneficiario = ("in favore del sottoscritto difensore, dichiaratosi antistatario (art. 93 c.p.c.)" if distratte
                    else manca("beneficiario delle spese: parte assistita o difensore antistatario"))
    studio = ctx.studio
    righe = [
        f"**{ctx.avvocato_o_manca}**",
        pulisci(studio.get("indirizzo_completo")) or manca("indirizzo dello studio"),
        f"PEC: {pulisci(studio.get('pec')) or manca('PEC dello studio')}",
        f"Spett.le **{_destinatario_pa(ctx).split(', in persona')[0]}**",
        (f"presso gli uffici a cui è stato notificato il titolo: {uffici_del_titolo(credito)}" if uffici_del_titolo(credito)
         else manca("ufficio dell'amministrazione competente al pagamento e suo indirizzo PEC dal Registro PP.AA.")),
        f"e, per conoscenza, {ctx.avvocatura}" if ctx.avvocatura else "",
        (f"**Oggetto:** {ctx.ufficio_o_manca}, R.G. n. {ctx.rg_o_manca}, {credito['fonte']} — {ctx.cliente or manca('parte assistita')} "
        "— richiesta di pagamento delle spese di lite liquidate"),
        f"Il sottoscritto {ctx.avvocato_o_manca}, difensore di {ctx.cliente or manca('parte assistita')} nel giudizio indicato in oggetto,",
        "premesso che",
        (f"- con la {credito['fonte'].lower() if credito['fonte'] else manca('sentenza')} {manca('numero della sentenza')} "
        f"il {ctx.ufficio_o_manca} ha condannato l'amministrazione al pagamento delle spese di lite, liquidate in {euro(compenso)} "
        f"per compenso, oltre accessori di legge, {beneficiario};"),
        f"- il titolo esecutivo è stato notificato il {notifica_del_titolo(credito)};",
        "chiede",
        (f"il pagamento della somma di {euro(totale)}, così determinata:" if totale is not None else
         f"il pagamento della somma di {euro(compenso)} per compenso, oltre accessori, così determinata:"),
        *[f"- {r}" for r in righe_importo],
        f"mediante bonifico sul conto {pulisci(studio.get('iban')) or manca('IBAN')} intestato a {ctx.avvocato_o_manca if distratte else manca('beneficiario')}.",
        # Regime forfetario: la fattura sconta il bollo di € 2,00 (art. 13 Tariffa all. A D.P.R. 642/1972), che nei
        # rapporti con lo Stato resta a carico dell'altra parte (art. 8 D.P.R. 642/1972): non si chiede all'amministrazione.
        ("L'imposta di bollo sulla fattura resta a carico dello scrivente (art. 8 D.P.R. 642/1972) e non è compresa "
         "nella somma richiesta." if distratte and credito.get("iva") == "forfetario" and ctx.avvocatura else ""),
        ("Si ricorda che le amministrazioni completano le procedure per il pagamento entro centoventi giorni dalla "
        "notificazione del titolo esecutivo, decorsi i quali il creditore può procedere alla notifica del precetto e "
        "all'esecuzione forzata (art. 14, comma 1, D.L. 669/1996, convertito dalla L. 30/1997)."),
        "Distinti saluti.",
        *ctx.firma(),
    ]
    return _unisci(righe)


def _al_destinatario(nome: str, *, pa: bool) -> str:
    """«al **Ministero …**, », «all'**Agenzia …**, » per le amministrazioni; «a **Mario Rossi**, » per le persone."""
    preposizione = preposizione_articolata(nome) if pa else "a"
    return f"{preposizione}{'' if preposizione.endswith("'") else ' '}**{nome}**, "


def _righe_competenze(competenze: dict[str, Any] | None) -> list[str]:
    """Le competenze del precetto: la proposta dal tariffario (modificabile nel testo) o il segnaposto."""
    if not competenze:
        return [f"- competenze e spese del presente atto: {manca('importo secondo il D.M. 55/2014')}"]
    righe = [f"- compenso (D.M. 55/2014, Tabella 6 «Atto di precetto», valore medio dello scaglione «{competenze['scaglione']}», "
             f"nei valori del D.M. 147/2022): {euro(competenze['compenso'])}"]
    righe += [f"- {riga}" for riga in competenze["righe"][1:]]
    if competenze.get("totale") is not None:
        righe.append(f"totale competenze del presente atto: {euro(competenze['totale'])}")
    return righe


def _totale_precetto(totale: Decimal | None, competenze: dict[str, Any] | None, *, pa: bool) -> str:
    if pa and totale and competenze and competenze.get("totale") is not None:
        return (f"per un totale di {euro(totale + competenze['totale'])}, oltre gli interessi legali dalla sentenza al saldo "
                "e le successive occorrende,")
    if pa and totale:
        return (f"per un totale di {euro(totale)}, oltre le competenze e spese del presente atto, gli interessi legali dalla "
                "sentenza al saldo e le successive occorrende,")
    return f"per un totale di {euro(totale) + ' oltre ' if totale else ''}{manca('totale complessivo con interessi e competenze')},"


def precetto(ctx: Contesto, titolo: dict[str, Any]) -> str:
    """Atto di precetto (artt. 474, 475 e 480 c.p.c.; art. 654 c.p.c. sul decreto ingiuntivo esecutivo; contro la
    P.A. art. 14 D.L. 669/1996 e art. 11 R.D. 1611/1933).

    ``titolo``: descrizione (str), voci (list[str]) e totale (Decimal|None), menzione_654 (str), pa (bool), distratte
    (bool), notificato_il e centoventi_giorni (gg/mm/aaaa, se la notifica del titolo è provata).
    Testi vigenti dall'archivio Normattiva del software: art. 475 c.p.c. (dal 28/02/2023 il titolo vale in copia
    attestata conforme, senza formula esecutiva: D.Lgs. 149/2022) e art. 480 c.p.c. (terzo comma come modificato dal
    D.Lgs. 164/2024: giudice dell'esecuzione e PEC da pubblici elenchi).
    """
    pa = bool(titolo.get("pa"))
    distratte = bool(titolo.get("distratte"))
    studio = ctx.studio
    if distratte:
        cf = pulisci(studio.get("cf_avvocato"))
        istante = (f"**{ctx.avvocato_o_manca}**" + (f" (C.F. {cf})" if cf else f" ({manca('codice fiscale del difensore')})")
                   + f", in proprio quale difensore antistatario di {ctx.cliente or manca('parte assistita')} (art. 93 c.p.c.)")
    else:
        istante = f"**{ctx.cliente or manca('parte istante')}**" + (f" (C.F. {ctx.cliente_cf})" if ctx.cliente_cf else f" ({manca('codice fiscale della parte istante')})")
    amministrazione = _destinatario_pa(ctx).split(", presso")[0] if pa else ""
    debitore = amministrazione if pa else (ctx.controparte_o_manca + (f" (C.F. {titolo['cf_debitore']})" if titolo.get("cf_debitore") else f" ({manca('codice fiscale del debitore')})"))
    if pa:
        # Il precetto è atto stragiudiziale: non rientra negli atti che l'art. 11 R.D. 1611/1933 fa notificare presso
        # l'Avvocatura dello Stato (la cui rappresentanza e domiciliazione riguardano l'attività giudiziale). Si notifica
        # alla parte personalmente (art. 480, ultimo comma, c.p.c.), cioè direttamente all'amministrazione destinataria
        # (art. 144, secondo comma, c.p.c.); notificato presso l'Avvocatura è inefficace e non interrompe la prescrizione
        # (Cass. civ., sez. V, 19 dicembre 2003, n. 19512). L'ufficio e la PEC del Registro PP.AA. restano da indicare.
        uffici = uffici_del_titolo(titolo)
        recapito = ("da notificarsi direttamente all'amministrazione (artt. 480, ultimo comma, e 144, secondo comma, c.p.c.; "
                    "Cass. civ., sez. V, 19 dicembre 2003, n. 19512), presso "
                    + (f"gli uffici a cui è stato notificato il titolo: {uffici}" if uffici else
                       manca("ufficio dell'amministrazione debitrice e suo indirizzo PEC dal Registro PP.AA. (non l'Avvocatura dello Stato)")))
    else:
        recapito = manca("residenza, sede o domicilio del debitore")
    # Dal 28/02/2023 il provvedimento vale come titolo in copia attestata conforme, senza formula esecutiva (art. 475 c.p.c.).
    copia = " rilasciato in copia attestata conforme all'originale (art. 475 c.p.c.)"
    totale = titolo.get("totale")
    righe = [
        "# Atto di precetto",
        "*(artt. 474, 475 e 480 c.p.c." + ("; art. 14 D.L. 669/1996)*" if pa else ")*"),
        f"Su istanza {'del sottoscritto ' if distratte else 'di '}{istante}" + ("" if distratte else f", rappresentata e difesa da {ctx.avvocato_o_manca}"),
        f"in forza {titolo['descrizione']}, titolo esecutivo (art. 474 c.p.c.){copia}" + (f"; {titolo['menzione_654']}" if titolo.get("menzione_654") else "")
        + f", notificato il {notifica_del_titolo(titolo)},",
        # Art. 14, comma 1, D.L. 669/1996: prima dei centoventi giorni dalla notifica del titolo il precetto è vietato.
        (f"decorso il termine di centoventi giorni dalla notificazione del titolo, scaduto il {titolo['centoventi_giorni']}, "
         "senza che l'amministrazione abbia provveduto al pagamento (art. 14, comma 1, D.L. 669/1996),"
         if pa and titolo.get("centoventi_giorni") else ""),
        "## Intima e fa precetto",
        # «al Ministero …», «all'Agenzia …», «alla Regione …» per le amministrazioni; «a Mario Rossi» per le persone.
        _al_destinatario(debitore, pa=pa) + recapito + ",",
        "di pagare entro dieci giorni dalla notificazione del presente atto le seguenti somme:",
        "*a) spese di lite liquidate nel titolo, con gli accessori di legge:*" if titolo.get("competenze") else "",
        *[f"- {voce}" for voce in titolo.get("voci") or []],
        (f"totale spese di lite liquidate: {euro(totale)}" if titolo.get("competenze") and totale else ""),
        ("*b) competenze del presente atto (proposta calcolata dal tariffario, modificabile entro i limiti dell'art. 4 "
         "D.M. 55/2014):*" if titolo.get("competenze") else ""),
        *_righe_competenze(titolo.get("competenze")),
        # Spese di lite liquidate contro la P.A.: il totale degli importi certi (con le competenze proposte), poi gli
        # interessi legali dalla sentenza al saldo e le successive occorrende. Negli altri titoli il totale resta da completare.
        _totale_precetto(totale, titolo.get("competenze"), pa=pa),
        "con l'avvertimento che, in mancanza, si procederà a esecuzione forzata (art. 480, primo comma, c.p.c.).",
        ("Avverte il debitore che può, con l'ausilio di un organismo di composizione della crisi o di un professionista "
        "nominato dal giudice, porre rimedio alla situazione di sovraindebitamento concludendo con i creditori un accordo "
        "di composizione della crisi o proponendo agli stessi un piano del consumatore (art. 480, secondo comma, c.p.c.)."),
        giudice_dell_esecuzione(titolo),
        elezione_domicilio(ctx, titolo),
    ]
    if pa and titolo.get("rischio_120"):
        righe.append(manca("ATTENZIONE: " + titolo["rischio_120"] + " Poi eliminare la riga"))
    elif pa and not titolo.get("centoventi_giorni"):
        righe.append(manca("il precetto si notifica solo decorsi centoventi giorni dalla notificazione del titolo "
                           "(art. 14, comma 1, D.L. 669/1996): indicare la data da cui è possibile, poi eliminare la riga"))
    righe += [*ctx.firma()]
    return _unisci(righe)


__all__ = ["OGGETTO_PEC_L53", "elezione_domicilio", "giudice_dell_esecuzione", "nota_di_deposito", "note_127_ter", "precetto",
           "relata_notifica", "richiesta_pagamento_pa"]
