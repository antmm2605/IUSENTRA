"""Quali passi del fascicolo richiedono un atto, con quale template e con quali dati.

Ogni voce del catalogo parte da una conclusione del modello della causa (``pct/ragionamento``, come la espone la
Lettura) o da un presidio della Lettura (credito liquidato non incassato), dichiara il template del catalogo
Template atti e le norme, e compila il testo solo con i dati certi. Una bozza nasce solo quando l'adempimento è
dello studio e ancora da fare; il passo della Lettura a cui si aggancia è riconosciuto dall'azione e dalla data.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pct.fascicolo_lettura._testo import data_da, data_it, pulisci

from . import testi
from .contesto import Contesto, contesto_della_lettura, euro, importo, udienza_sostituita
from .modello import AggancioPasso, Bozza

# tipo → (template del catalogo, titolo del template, norme del registro pct/procedura_fasi/fonti.py)
MODELLI: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "note_127ter": ("builtin-tmp-civ-012", "Note d'udienza", ("cpc_127ter", "dispatt_196quater")),
    "notifica_ricorso_decreto": ("builtin-tmp-not-003", "Relata di notifica PEC", ("l53_art3bis", "cpc_415", "rd1611_art11")),
    "notifica_ordinata": ("builtin-tmp-not-003", "Relata di notifica PEC", ("l53_art3bis",)),
    "nota_deposito": ("CIV_ORD_015", "Nota di deposito documenti", ("dispatt_196quater", "cpc_421")),
    "richiesta_pagamento_pa": ("STR_020", "Lettera pre-precetto", ("dl669_art14", "cpc_474")),
    "precetto_pa": ("ESE_003", "Precetto su sentenza", ("cpc_474", "cpc_480", "dl669_art14")),
    "precetto_decreto_ingiuntivo": ("MON_018", "Precetto su decreto ingiuntivo esecutivo", ("cpc_474", "cpc_480", "cpc_654")),
}

_ONERATI_STUDIO = {"noi", "tutte_le_parti"}


def _crea(tipo: str, riferimento: str, titolo: str, testo: str, agganci: tuple[AggancioPasso, ...], **dati: Any) -> Bozza:
    modello, modello_titolo, fonti = MODELLI[tipo]
    return Bozza(chiave=f"{tipo}:{riferimento}", tipo=tipo, titolo=titolo, modello=modello, modello_titolo=modello_titolo,
                 fonti=fonti, testo=testo, agganci=agganci, dati=dati)


def _da_fare(voce: dict[str, Any]) -> bool:
    return voce.get("stato") == "da_fare" and voce.get("onerato_codice") in _ONERATI_STUDIO


def _scadenza(voce: dict[str, Any]) -> date | None:
    return data_da((voce.get("termine") or {}).get("scadenza_iso") or (voce.get("termine") or {}).get("scadenza"))


def _note(lettura: dict[str, Any], ctx: Contesto, conclusioni: list[dict[str, Any]], oggi: date) -> list[Bozza]:
    bozze = []
    for voce in conclusioni:
        giorno = _scadenza(voce)
        if voce.get("codice") != "note_127ter" or not _da_fare(voce) or not giorno or giorno < oggi:
            continue
        udienza = udienza_sostituita(lettura, str((voce.get("letto") or {}).get("documento_id") or ""))
        bozze.append(_crea("note_127ter", giorno.isoformat(), f"Note scritte ex art. 127-ter c.p.c. — termine {data_it(giorno)}",
                           testi.note_127_ter(ctx, voce, udienza=udienza),
                           (AggancioPasso((r"\bnote\b",), (data_it(giorno),)),), termine=data_it(giorno), udienza=udienza,
                           provvedimento=(voce.get("letto") or {}).get("documento", "")))
    return bozze


def _documento(lettura: dict[str, Any], ruolo: str) -> dict[str, Any]:
    return ((lettura.get("documenti") or {}).get(ruolo) or {})


def _notifiche(lettura: dict[str, Any], ctx: Contesto, conclusioni: list[dict[str, Any]], oggi: date) -> list[Bozza]:
    bozze = []
    for voce in conclusioni:
        codice = voce.get("codice")
        if codice not in {"notifica_ricorso_decreto_415", "notifica_ordinata"} or not _da_fare(voce):
            continue
        letto = voce.get("letto") or {}
        giorno = _scadenza(voce)
        provvedimento_nome = pulisci(letto.get("documento"))
        if codice == "notifica_ordinata" and (not giorno or giorno < oggi):
            continue  # termine del giudice già decorso: la notifica non si prepara in bozza, va valutata
        if codice == "notifica_ricorso_decreto_415":
            # Il termine utile dipende dall'udienza (art. 415, quinto comma): la data la dà il passo del presidio.
            ricorso = _documento(lettura, "atto_introduttivo")
            udienze = [u.get("data") for u in (lettura.get("ragionamento") or {}).get("udienze") or []
                       if u.get("documento_id") == letto.get("documento_id") and u.get("data")]
            documenti = [
                {"nome_file": pulisci(ricorso.get("nome")) or "ricorso.pdf", "descrizione": "Ricorso",
                 "origine": "firmato_digitalmente" if ricorso.get("firmato") else "nativo_digitale"},
                {"nome_file": provvedimento_nome or "decreto.pdf",
                 "descrizione": "Decreto di fissazione dell'udienza" + (f" del {udienze[0]}" if len(set(udienze)) == 1 else ""),
                 "provvedimento_tipo": "Decreto", "data_documento": data_da(letto.get("data")).isoformat() if data_da(letto.get("data")) else "",
                 "origine": "copia_fascicolo_informatico"},
            ]
            bozze.append(_crea("notifica_ricorso_decreto", str(letto.get("documento_id") or "atto"),
                               "Notifica PEC ex art. 3-bis L. 53/1994 di ricorso e decreto — relata e testo della PEC",
                               testi.relata_notifica(ctx, voce, documenti=documenti),
                               (AggancioPasso((r"notific", r"ricorso|decreto|ordinata dal giudice")),),
                               destinatario=ctx.avvocatura or ctx.controparte, documenti=[d["nome_file"] for d in documenti]))
        else:
            documenti = [{"nome_file": provvedimento_nome or "provvedimento.pdf", "descrizione": "Provvedimento del giudice",
                          "data_documento": data_da(letto.get("data")).isoformat() if data_da(letto.get("data")) else "",
                          "origine": "copia_fascicolo_informatico"}]
            bozze.append(_crea("notifica_ordinata", f"{letto.get('documento_id') or 'atto'}:{giorno.isoformat()}",
                               f"Notifica PEC del provvedimento entro il {data_it(giorno)} — relata e testo della PEC",
                               testi.relata_notifica(ctx, voce, documenti=documenti),
                               (AggancioPasso((r"notific",), (data_it(giorno),)),), documenti=[d["nome_file"] for d in documenti]))
    return bozze


def _depositi(lettura: dict[str, Any], ctx: Contesto, conclusioni: list[dict[str, Any]], oggi: date) -> list[Bozza]:
    gruppi: dict[str, list[dict[str, Any]]] = {}
    for voce in conclusioni:
        if voce.get("codice") == "deposito_ordinato" and _da_fare(voce) and _scadenza(voce):
            famiglia = " ".join(re.findall(r"\w+", pulisci(voce.get("cosa")).lower())[:3])
            gruppi.setdefault(famiglia, []).append(voce)
    bozze = []
    for voci in gruppi.values():
        # Lo stesso deposito chiesto più volte (nuovo termine assegnato): vale l'ultimo provvedimento.
        ultima = max(voci, key=lambda v: _scadenza(v) or date.min)
        giorno = _scadenza(ultima)
        entro = tuple(data_it(_scadenza(v)) for v in voci)
        bozze.append(_crea("nota_deposito", f"{(ultima.get('letto') or {}).get('documento_id') or 'atto'}:{giorno.isoformat()}",
                           f"Nota di deposito — {pulisci(ultima.get('cosa'))[:80]}", testi.nota_di_deposito(ctx, ultima),
                           (AggancioPasso((r"^Depositare",), entro),), termine=data_it(giorno),
                           provvedimento=(ultima.get("letto") or {}).get("documento", "")))
    return bozze


def _riga_conto(conto: dict[str, Any] | None, voce: str) -> dict[str, Any]:
    return next((r for r in (conto or {}).get("righe") or [] if r.get("voce") == voce), {})


def _regime_iva(ctx: Contesto) -> str:
    """«forfetario» solo se il regime forfetario (RF19) o dei minimi (RF02) risulta dalla scheda dello studio."""
    return "forfetario" if pulisci(ctx.studio.get("regime_fiscale")).upper() in {"RF19", "RF02"} else ""


# Il provvedimento liquida il rimborso delle spese generali (art. 2, comma 2, D.M. 55/2014) solo se lo dice.
# Il brano salvato nella Lettura può essere troncato («oltre rimborso forfettar»): basta la radice della parola.
_RE_FORFETTARIO = re.compile(r"rimborso\s+(?:delle\s+)?(?:spese\s+)?(?:generali\s+)?forfet+ar|spese\s+generali|spese\s+forfet+ar",
                             re.IGNORECASE)


def _forfettario_liquidato(*testi_letti: Any) -> bool:
    return any(_RE_FORFETTARIO.search(pulisci(t)) for t in testi_letti)


def _notifica_titolo_provata(conclusioni: list[dict[str, Any]]) -> dict[str, str]:
    """Data della notificazione del titolo e fine dei 120 giorni, se il modello della causa li ha provati.

    Il modello (pct/ragionamento/regole/sentenza.py) produce «esecuzione_pa» con il termine dei centoventi giorni
    decorrente dalla notifica del titolo solo quando la notifica è provata; con il dubbio («dubbio») non c'è data.
    """
    for voce in conclusioni:
        if voce.get("codice") != "esecuzione_pa" or voce.get("stato") == "dubbio":
            continue
        termine = voce.get("termine") or {}
        notificato, scadenza = data_da(termine.get("decorrenza")), data_da(termine.get("scadenza_iso") or termine.get("scadenza"))
        if notificato and scadenza:
            return {"notificato_il": data_it(notificato), "centoventi_giorni": data_it(scadenza),
                    "precetto_dal": data_it(scadenza + timedelta(days=1))}
    return {}


def _credito_pa(lettura: dict[str, Any], ctx: Contesto, conclusioni: list[dict[str, Any]], oggi: date, conto: dict[str, Any] | None) -> list[Bozza]:
    economico = lettura.get("economico") or {}
    liquidazione = economico.get("liquidazione") or {}
    if not ctx.pubblica_amministrazione or liquidazione.get("stato") != "da_incassare" or liquidazione.get("pagato"):
        return []
    try:
        compenso = Decimal(str(liquidazione.get("importo"))).quantize(Decimal("0.01"))
    except (ArithmeticError, ValueError):
        return []
    if compenso <= 0:
        return []
    distratte = "distratt" in pulisci(_riga_conto(conto, "sentenza").get("stato")).lower()
    fonte = pulisci(liquidazione.get("fonte")) or "Sentenza"
    spese = next((v for v in conclusioni if v.get("codice") == "spese_liquidate"), {})
    forfettario = _forfettario_liquidato(liquidazione.get("nota"), (spese.get("letto") or {}).get("brano"), spese.get("cosa"))
    notifica = _notifica_titolo_provata(conclusioni)
    credito = {"importo": compenso, "fonte": fonte, "distratte": distratte, "iva": _regime_iva(ctx),
               "forfettario": forfettario, **notifica}
    voci, totale = testi._accessori(compenso, iva=credito["iva"], forfettario=forfettario)
    agganci = (AggancioPasso((r"riscuot|incass|pagamento",)),)
    riferimento = re.sub(r"\W+", "-", fonte.lower()).strip("-")
    articolo = "della " if fonte.lower().startswith("sentenza") else "del provvedimento: "
    descrizione = f"{articolo}{fonte[:1].lower() + fonte[1:]} del {ctx.ufficio_o_manca} (R.G. n. {ctx.rg_o_manca})"
    return [
        _crea("richiesta_pagamento_pa", riferimento, f"Richiesta di pagamento alla P.A. delle spese liquidate ({euro(compenso)} oltre accessori)",
              testi.richiesta_pagamento_pa(ctx, credito), agganci, importo=euro(compenso), distratte=distratte),
        _crea("precetto_pa", riferimento, "Atto di precetto contro la P.A. (dopo 120 giorni dalla notifica del titolo)",
              testi.precetto(ctx, {"descrizione": descrizione, "pa": True, "distratte": distratte, "totale": totale,
                                   "voci": voci, **notifica}), agganci, importo=euro(compenso), **notifica),
    ]


def _cf_nel_testo(testo: str, nome: str) -> str:
    """Il codice fiscale scritto accanto al nome della parte nel provvedimento («NOME (CF …)»)."""
    parole = {p for p in re.findall(r"\w+", nome.lower()) if len(p) > 2}
    for corrispondenza in re.finditer(r"([A-Z0-9&.' ]{3,}?)\s*\(C\.?F\.?\s*([0-9A-Z]{11,16})\)", testo):
        letti = {p for p in re.findall(r"\w+", corrispondenza.group(1).lower()) if len(p) > 2}
        if parole and letti and len(parole & letti) >= min(2, len(parole)):
            return corrispondenza.group(2)
    return ""


def _precetto_decreto(lettura: dict[str, Any], ctx: Contesto, conclusioni: list[dict[str, Any]], oggi: date, conto: dict[str, Any] | None) -> list[Bozza]:
    voce = next((v for v in conclusioni if v.get("codice") == "precetto" and _da_fare(v)), None)
    if voce is None or ctx.pubblica_amministrazione:
        return []
    brano = pulisci((voce.get("letto") or {}).get("brano"))
    numero_di = re.search(r"decreto ingiuntivo n\.?\s*(\d+\s*/\s*\d{4})", brano, re.IGNORECASE)
    esecutorieta = re.search(r"esecutoriet\w*'?\s*n\.?\s*cronol\.?\s*(\d+\s*/\s*\d{4})\s+del\s+(\d{2}/\d{2}/\d{4})", brano, re.IGNORECASE)
    if not numero_di:
        return []
    descrizione = f"del decreto ingiuntivo n. {numero_di.group(1).replace(' ', '')} del {ctx.ufficio_o_manca} (R.G. n. {ctx.rg_o_manca})"
    menzione = (f"dichiarato esecutivo con decreto n. cronol. {esecutorieta.group(1).replace(' ', '')} del {esecutorieta.group(2)} "
                "(art. 654, secondo comma, c.p.c.)") if esecutorieta else "dichiarato esecutivo con " + testi.manca("estremi del decreto di esecutorietà (art. 654, secondo comma, c.p.c.)")
    voci: list[str] = []
    totale = Decimal(0)
    spese = next((v for v in conclusioni if v.get("codice") == "spese_liquidate"), None)
    if spese:
        dispositivo = pulisci((spese.get("letto") or {}).get("brano"))
        capitale = re.search(r"somma (?:complessiva )?di\s*€\s*([\d.,]+?)[.,]?\s+(oltre [^.;)]*?)(?=\.\s|\s\d\)|;|$)", dispositivo, re.IGNORECASE)
        if capitale and (somma := importo(capitale.group(1))) is not None:
            voci.append(f"sorte capitale: {euro(somma)}")
            voci.append(f"{capitale.group(2)}: {testi.manca('calcolo degli interessi con tasso e decorrenza')}")
            totale += somma
        liquidate = re.search(r"€\s*([\d.,]+) di compensi e €\s*([\d.,]+) di spese", pulisci(spese.get("cosa")))
        if liquidate and (compenso := importo(liquidate.group(1))) is not None and (esborsi := importo(liquidate.group(2))) is not None:
            forfettario = _forfettario_liquidato(dispositivo, spese.get("cosa"))
            righe, accessori = testi._accessori(compenso, iva=_regime_iva(ctx), forfettario=forfettario)
            voci.append(f"spese del procedimento monitorio, esborsi: {euro(esborsi)}")
            voci.extend(f"spese del procedimento monitorio, {riga}" for riga in righe)
            totale += esborsi + (accessori if accessori is not None else compenso)
    if not voci:
        voci.append(testi.manca("somme ingiunte, interessi e spese liquidate nel decreto"))
    cf_debitore = _cf_nel_testo(brano, ctx.controparte)
    ctx_istante = ctx if ctx.cliente_cf else Contesto(**{**ctx.__dict__, "cliente_cf": _cf_nel_testo(brano, ctx.cliente)})
    return [_crea("precetto_decreto_ingiuntivo", numero_di.group(1).replace(" ", "").replace("/", "-"),
                  f"Atto di precetto sul decreto ingiuntivo n. {numero_di.group(1).replace(' ', '')}",
                  testi.precetto(ctx_istante, {"descrizione": descrizione, "menzione_654": menzione, "voci": voci,
                                               "totale": totale or None, "cf_debitore": cf_debitore}),
                  (AggancioPasso((r"precetto",)),), titolo_esecutivo=descrizione)]


# Il contributo unificato «da chiarire» non ha bozza: è un dubbio da sciogliere, non un adempimento certo
# (collaudo 18/11/2026, D960FA3E: procedimento del giudice tutelare esente, art. 10 D.P.R. 115/2002).
_PRODUTTORI: tuple[Callable[..., list[Bozza]], ...] = (_note, _notifiche, _depositi)


def bozze_del_fascicolo(lettura: dict[str, Any] | None, *, oggi: date, conto: dict[str, Any] | None = None,
                        studio: dict[str, Any] | None = None, cliente_cf: str = "") -> list[Bozza]:
    """Le bozze dei passi che richiedono un atto, dalla Lettura già calcolata (mai una lettura di documenti)."""
    if not lettura or not (lettura.get("ragionamento") or {}).get("impronta"):
        return []
    intestazione = lettura.get("intestazione") or {}
    if pulisci(intestazione.get("stato_codice")).upper() in {"CHIUSO", "ARCHIVIATO"}:
        return []
    ctx = contesto_della_lettura(lettura, studio=studio, cliente_cf=cliente_cf)
    conclusioni = list((lettura.get("ragionamento") or {}).get("conclusioni") or [])
    bozze: list[Bozza] = []
    attivi = (lettura.get("stato_passi") or {}).get("attivi") is not False
    if attivi:
        for produttore in _PRODUTTORI:
            bozze.extend(produttore(lettura, ctx, conclusioni, oggi))
        bozze.extend(_precetto_decreto(lettura, ctx, conclusioni, oggi, conto))
    # Il credito liquidato non incassato tiene aperto il fascicolo anche quando non ha altri passi (pct.incasso_provato).
    bozze.extend(_credito_pa(lettura, ctx, conclusioni, oggi, conto))
    visti: set[str] = set()
    return [b for b in bozze if not (b.chiave in visti or visti.add(b.chiave))]


__all__ = ["MODELLI", "bozze_del_fascicolo"]
