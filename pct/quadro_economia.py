"""La riga «Economia» del quadro: il percorso economico completo del fascicolo, dalla stessa verità del Conto economico.

In quest'ordine, con le date in gg/mm/aaaa:

1. **contributo unificato** — la conclusione del modello della causa (`pct/ragionamento/regole/economia.py`), la stessa
   dei prossimi passi: versato con importo e data della ricevuta, oppure esente o non dovuto con la norma, oppure il
   dubbio come il modello lo scrive (un solo controllore per dato);
2. **compenso dello studio** — dai documenti della Fatturazione e dagli incassi registrati (`parcelle_del_fascicolo`,
   lo stesso elenco del Conto economico): proforma (numero, data, importo), fattura (numero e data: la fattura si
   emette al pagamento, art. 6, terzo comma, e art. 21 D.P.R. 633/1972), incasso (importo e data) oppure «non ancora
   incassato» con i giorni trascorsi dalla proforma. Un incasso senza prova non c'è (`pct/incasso_provato.py`):
   conta solo l'incasso registrato;
3. **spese liquidate dal giudice** — la riga del Conto economico (il provvedimento reale: sentenza, decreto
   ingiuntivo, ordinanza) o, senza Conto, la conclusione del modello; se la controparte le ha pagate (solo con prova
   d'incasso) e se sono distratte in favore dell'avvocato (art. 93 c.p.c.).

Livello: «ok» (In ordine) solo se tutto è incassato o non c'è nulla da incassare; un credito aperto è «info» (Da
sapere) e diventa «attenzione» oltre i trenta giorni dalla proforma. Il termine legale di trenta giorni dal ricevimento
della fattura o di una richiesta di pagamento equivalente (art. 4, comma 2, lett. a), D.Lgs. 231/2002) vale solo per le
transazioni commerciali, cioè con un cliente impresa, professionista o pubblica amministrazione (art. 2, comma 1, lett.
a) e c)): solo allora si cita la norma; con un cliente consumatore (o di natura non nota) i trenta giorni sono un
promemoria di sollecito dello studio, senza norma. Un contributo in dubbio è sempre «attenzione».
Modulo puro: riceve i dati già calcolati, non legge e non scrive nulla.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable, Mapping

GIORNI_PAGAMENTO = 30
NORMA_PAGAMENTO = "art. 4, comma 2, lett. a), D.Lgs. 231/2002"
# Chi è il cliente ai fini del D.Lgs. 231/2002: «impresa» (anche professionista), «pa», «consumatore», «» se non noto.
CLIENTI_COMMERCIALI = frozenset({"impresa", "pa"})
NORMA_FATTURA = "art. 6, terzo comma, e art. 21 D.P.R. 633/1972"
_EURO = re.compile(r"€\s*([0-9][0-9.]*,[0-9]{2})")


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _iso(valore: Any) -> str:
    testo = _testo(valore)[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", testo):
        return testo
    trovato = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", testo)
    return f"{trovato[3]}-{int(trovato[2]):02d}-{int(trovato[1]):02d}" if trovato else ""


def _data_it(valore: Any) -> str:
    iso = _iso(valore)
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else ""


def _euro(importo: Any) -> str:
    try:
        valore = float(importo)
    except (TypeError, ValueError):
        return ""
    return "€ " + f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _giorni(da: str, oggi: date) -> int | None:
    try:
        return (oggi - date.fromisoformat(_iso(da))).days
    except ValueError:
        return None


def contributo(conclusione: Mapping[str, Any] | None, voce: Mapping[str, Any] | None = None,
               presidio: Mapping[str, Any] | None = None) -> tuple[str, bool]:
    """(testo, dubbio): il contributo unificato come lo conclude il modello; senza modello, lo stato del presidio."""
    voce = voce or {}
    if conclusione:
        stato = _testo(conclusione.get("stato"))
        cosa = _testo(conclusione.get("cosa"))
        norme = [_testo(n.get("norma")) for n in conclusione.get("norme") or [] if n.get("norma")]
        if stato == "fatto":
            importo = _EURO.search(cosa) or _EURO.search(_testo(conclusione.get("prova_o_motivo")))
            data = _data_it(voce.get("data_pagamento")) if _testo(voce.get("status")) == "pagato" else ""
            return ("versato" + (f" € {importo.group(1)}" if importo else "") + (f" (ricevuta del {data})" if data else ""), False)
        if stato == "non_dovuto":
            return ("non dovuto" + (f" ({norme[0]})" if norme else ""), False)
        testo = re.sub(r"^contributo unificato:?\s*", "", cosa, flags=re.I)
        return (testo[:1].lower() + testo[1:] if testo else "da verificare", True)
    if presidio:
        importo = _testo(presidio.get("importoLabel"))
        norma = _testo(presidio.get("norma"))
        testo = _testo(presidio.get("etichetta")) + (f" {importo}" if importo else "")
        if norma and presidio.get("categoria") == "esente":
            testo += f" ({norma})"
        return testo, presidio.get("tono") == "warning"
    return "da verificare", True


def natura_cliente(cliente: Any, nome: str = "") -> str:
    """«impresa» (persona giuridica o titolare di partita IVA: imprenditore o professionista, art. 2, comma 1, lett. c),
    D.Lgs. 231/2002), «pa», «consumatore» (persona fisica senza partita IVA) o «» se l'anagrafica non lo dice."""
    from pct.ragionamento.rito import contro_pa

    if contro_pa(nome, getattr(cliente, "nome", "") if cliente is not None else ""):
        return "pa"
    if cliente is None:
        return ""
    if _testo(getattr(cliente, "partita_iva", "")) or _testo(getattr(cliente, "tipo", "")).upper().endswith("PERSONA_GIURIDICA"):
        return "impresa"
    return "consumatore" if _testo(getattr(cliente, "tipo", "")).upper().endswith("PERSONA_FISICA") else ""


def compenso(parcelle: Iterable[Mapping[str, Any]] | None, *, oggi: date, cliente: str = "") -> tuple[str, str]:
    """(testo, livello) del compenso dello studio: proforma, fattura, incasso."""
    from pct.proforma_unica import attive_non_superate

    if parcelle is None:
        return "compenso: apri la Fatturazione per proforma, fattura e incassi", "info"
    attive = [p for p in attive_non_superate(list(parcelle)) if _testo(p.get("stato")).upper() != "ANNULLATA"]
    if not attive:
        return "compenso: proforma da preparare", "info"
    parti, livello = [], "ok"
    for documento in attive:
        fattura = _testo(documento.get("operativo")).upper() == "FATTURA"
        numero, data = _testo(documento.get("numero")), _data_it(documento.get("data"))
        totale = _euro(documento.get("netto_a_pagare") if documento.get("netto_a_pagare") is not None else documento.get("totale"))
        testo = (f"{'fattura' if fattura else 'proforma'} n. {numero}" + (f" del {data}" if data else "")
                 + (f", {totale}" if totale else ""))
        try:
            incassato = float(documento.get("incassato") or 0)
            dovuto = float(documento.get("netto_a_pagare") if documento.get("netto_a_pagare") is not None else documento.get("totale") or 0)
        except (TypeError, ValueError):
            incassato, dovuto = 0.0, 0.0
        pagato_il = _data_it(documento.get("data_pagamento"))
        if incassato > 0 and (not dovuto or incassato + 0.005 >= dovuto):
            testo += f": incassati {_euro(incassato)}" + (f" il {pagato_il}" if pagato_il else "")
            if not fattura:
                testo += f", fattura da emettere ({NORMA_FATTURA})"
                livello = "attenzione"
        else:
            giorni = _giorni(documento.get("data"), oggi)
            testo += (f": incassati {_euro(incassato)}" + (f" il {pagato_il}" if pagato_il else "") + f", restano {_euro(dovuto - incassato)}"
                      if incassato > 0 else ": non ancora incassato")
            if giorni is not None and giorni >= 0:
                testo += f", da {giorni} giorn{'o' if giorni == 1 else 'i'} dalla {'fattura' if fattura else 'proforma'}"
            scaduto = giorni is not None and giorni > GIORNI_PAGAMENTO
            if scaduto:
                testo += (f" (oltre i {GIORNI_PAGAMENTO} giorni dalla richiesta di pagamento, {NORMA_PAGAMENTO})"
                          if cliente in CLIENTI_COMMERCIALI else
                          f" (oltre i {GIORNI_PAGAMENTO} giorni: promemoria dello studio per il sollecito)")
            livello = "attenzione" if scaduto or livello == "attenzione" else "info"
        parti.append(testo)
    return "compenso: " + "; ".join(parti), livello


def _provvedimento(etichetta: str) -> str:
    """«Importo liquidato in sentenza» → «in sentenza»; «Spese liquidate nel decreto ingiuntivo» → «nel decreto ingiuntivo»."""
    semplice = _testo(etichetta)
    trovato = re.search(r"liquidat[eo]\s+((?:in|nel|nella|nell['’]|dal|dalla)\s*.+)$", semplice, re.I)
    return trovato.group(1).lower() if trovato else ("dal giudice" if not semplice else semplice.lower())


def spese_liquidate(riga_conto: Mapping[str, Any] | None, *, conclusione: Mapping[str, Any] | None = None,
                    atti: Mapping[str, Mapping[str, Any]] | None = None, liquidazione: Mapping[str, Any] | None = None
                    ) -> tuple[str, str]:
    """(testo, livello) delle spese liquidate dal giudice; testo vuoto se non ce ne sono."""
    from pct.incasso_provato import pagato_senza_prova

    riga = riga_conto or {}
    stato = _testo(riga.get("stato"))
    if stato == "Spese compensate":
        return "spese di lite compensate (art. 92 c.p.c.)", "ok"
    importo, dove, distratte = riga.get("importoLabel") if riga.get("importo") else "", "", stato.startswith("Distratte")
    if importo:
        dove = _provvedimento(_testo(riga.get("etichetta")))
    elif conclusione and _testo(conclusione.get("codice")) == "spese_liquidate":
        cosa = _testo(conclusione.get("cosa"))
        trovato = _EURO.search(cosa)
        importo = f"€ {trovato.group(1)}" if trovato else ""
        letto = conclusione.get("letto") or {}
        atto = (atti or {}).get(_testo(letto.get("documento_id"))) or {}
        etichetta = _testo(atto.get("etichetta")).lower()
        dove = ("nel decreto ingiuntivo" if "decreto ingiuntivo" in etichetta else "in sentenza" if "sentenza" in etichetta
                else f"nel provvedimento «{_testo(letto.get('documento'))}»" if letto.get("documento") else "dal giudice")
        if letto.get("data"):
            dove += f" del {_testo(letto.get('data'))}"
    if not importo:
        return "", "ok"
    testo = f"spese liquidate {dove} {importo}"
    if distratte:
        testo += ", distratte in favore dell'avvocato (art. 93 c.p.c.)"
    voce = liquidazione or {}
    if _testo(voce.get("status")) == "pagato" and not pagato_senza_prova(voce):
        quando = _data_it(voce.get("data_pagamento"))
        return testo + ": pagate dalla controparte" + (f" il {quando}" if quando else ""), "ok"
    return testo + ": non ancora pagate dalla controparte", "info"


_ORDINE = {"ok": 0, "info": 1, "attenzione": 2}


def percorso_economico(*, conclusioni: Iterable[Mapping[str, Any]] | None, atti: Iterable[Mapping[str, Any]] | None,
                       righe_conto: Iterable[Mapping[str, Any]], parcelle: Iterable[Mapping[str, Any]] | None,
                       voci: Mapping[str, Mapping[str, Any]] | None, presidio_contributo: Mapping[str, Any] | None,
                       oggi: date, cliente: str = "") -> tuple[str, str]:
    """(testo, livello) della riga Economia."""
    conclusioni = list(conclusioni or [])
    per_voce = {_testo(r.get("voce")): r for r in righe_conto}
    voci = voci or {}
    conclusione_cu = next((c for c in conclusioni if _testo(c.get("codice")) == "contributo_unificato"), None)
    testo_cu, dubbio = contributo(conclusione_cu, voci.get("contributo_unificato"), presidio_contributo)
    testo_compenso, livello_compenso = compenso(parcelle, oggi=oggi, cliente=cliente)
    testo_spese, livello_spese = spese_liquidate(
        per_voce.get("sentenza"), conclusione=next((c for c in conclusioni if _testo(c.get("codice")) == "spese_liquidate"), None),
        atti={_testo(a.get("id")): a for a in atti or []}, liquidazione=voci.get("liquidazione_giudice"))
    parti = [f"Contributo unificato: {testo_cu}", testo_compenso, testo_spese]
    livelli = ["attenzione" if dubbio else "ok", livello_compenso, livello_spese]
    return " · ".join(p for p in parti if p), max(livelli, key=_ORDINE.get)


__all__ = ["CLIENTI_COMMERCIALI", "GIORNI_PAGAMENTO", "NORMA_PAGAMENTO", "compenso", "natura_cliente", "contributo", "percorso_economico", "spese_liquidate"]
