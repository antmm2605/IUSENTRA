"""La scheda Formweb: cosa scrivere, nell'ordine del portale, per ogni deposito.

Riceve un contesto già risolto (fascicolo, procedimento PAT, avvocato, parti con
il ruolo PAT, documenti controllati con le regole del Formweb) e restituisce le
sezioni come le mostra il Portale dell'Avvocato: passi iniziali della bozza,
poi le schede del deposito, infine firma e invio del riepilogo. Ogni riga dice
se il dato c'è, se manca o se è facoltativo; niente viene inventato: un dato
assente resta «da indicare». Fonti in ``catalogo``.
"""

from __future__ import annotations

from typing import Any

from . import catalogo
from .regole import LIMITE_DESCRIZIONE, LIMITE_OGGETTO

OK, MANCA, FACOLTATIVO, VERIFICA = "ok", "manca", "facoltativo", "verifica"


def _riga(etichetta: str, valore: Any, stato: str = "", nota: str = "", copia: bool = True) -> dict[str, Any]:
    testo = "" if valore in (None, False) else str(valore).strip()
    return {"etichetta": etichetta, "valore": testo or "da indicare", "stato": stato or (OK if testo else MANCA),
            "nota": nota, "copia": copia and bool(testo)}


def _parte_testo(parte: dict[str, Any]) -> str:
    nome = parte.get("denominazione") or " ".join(x for x in (parte.get("cognome"), parte.get("nome")) if x)
    return " · ".join(x for x in (nome, parte.get("codiceFiscale"), parte.get("pec")) if x)


def _per_ruolo(parti: list[dict[str, Any]], ruolo: str) -> list[dict[str, Any]]:
    return [p for p in parti if p.get("ruolo") == ruolo]


def _sede(ctx: dict[str, Any]) -> tuple[str, str]:
    codice = ctx["procedimento"].get("sede") or ""
    etichetta = next((e for c, e in catalogo.SEDI.values() if c == codice), "")
    return codice, etichetta


def _documenti(ctx: dict[str, Any], ruolo: str) -> list[dict[str, Any]]:
    return [d for d in ctx["documenti"] if d.get("ruolo") == ruolo]


def _riga_file(etichetta: str, doc: dict[str, Any] | None, obbligatorio: bool = True) -> dict[str, Any]:
    if doc is None:
        return _riga(etichetta, "", MANCA if obbligatorio else FACOLTATIVO, copia=False)
    stato = VERIFICA if doc.get("bloccante") else OK
    nota = "; ".join(e["messaggio"] for e in doc.get("esiti", [])) or "Nome e formato accettati dal Formweb."
    return _riga(etichetta, doc.get("nomeProposto") or doc.get("nome"), stato, nota)


def _proposta(ctx: dict[str, Any], campo: str) -> dict[str, Any] | None:
    """Il dato letto dai documenti del fascicolo, se il procedimento non lo ha ancora."""
    voce = (ctx.get("letti") or {}).get(campo)
    return voce if voce and voce.get("valore") else None


def _nota_letto(voce: dict[str, Any]) -> str:
    if voce.get("fonte"):
        return f"Letto dal {voce['fonte']}: conferma nel Procedimento."
    fonti = ", ".join(f"«{nome}»" for nome in voce.get("documenti") or []) or "i documenti del fascicolo"
    altri = f" Nei documenti compaiono anche: {', '.join(voce['altri'])}." if voce.get("altri") else ""
    return f"Letto da {fonti} (archivio delle letture): conferma nel Procedimento.{altri}"


def passi_iniziali(ctx: dict[str, Any], tipo: dict[str, Any]) -> dict[str, Any]:
    codice, etichetta = _sede(ctx)
    sede_letta = None if codice else _proposta(ctx, "sede")
    if sede_letta:
        codice = sede_letta["valore"]
        etichetta = next((e for c, e in catalogo.SEDI.values() if c == codice), "")
    proc, avv = ctx["procedimento"], ctx.get("avvocato") or {}
    ufficio = str((ctx.get("fascicolo") or {}).get("ufficio") or "").strip()
    righe = [_riga("Depositante", avv.get("nome"), OK if avv.get("nome") else VERIFICA,
                   "Il portale lo compila dal ReGIndE con la PEC dei registri di giustizia.", copia=False)]
    if tipo["id"] != "richieste-segreteria":
        cassazionista = catalogo.ambito(codice) in {"CDS", "CGARS"}
        righe.append(_riga("Cassazionista", "Sì" if proc.get("cassazionista") else ("Da spuntare" if cassazionista else "No"),
                           VERIFICA if cassazionista and not proc.get("cassazionista") else OK,
                           "Solo per Consiglio di Stato e CGARS (art. 76 d.P.R. 445/2000).", copia=False))
    righe.append(_riga("Autorità giurisdizionale", catalogo.ambito(codice), VERIFICA if sede_letta else "",
                       "Dalla sede: TAR, Consiglio di Stato o CGARS." if codice else "Si ricava dalla sede: indica l'ufficio nel fascicolo."))
    righe.append(_riga("Sede", etichetta, VERIFICA if sede_letta else "",
                       _nota_letto(sede_letta) if sede_letta else (
                           f"Dall'ufficio del fascicolo «{ufficio}»: scegli questa scrittura nel Formweb." if codice and ufficio
                           else "Scegli la sede con questa scrittura." if codice
                           else f"«{ufficio}» non indica la sede: scrivi città o regione del TAR nell'ufficio del fascicolo." if ufficio
                           else "Indica l'ufficio (es. «TAR Calabria - Reggio Calabria») nel fascicolo o nel Procedimento.")))
    if tipo["nrg"]:
        nrg_letto = None if proc.get("nrg") else _proposta(ctx, "nrg")
        righe.append(_riga("NRG", nrg_letto["valore"] if nrg_letto else proc.get("nrg"), VERIFICA if nrg_letto else "",
                           _nota_letto(nrg_letto) if nrg_letto else "Numero di registro generale, es. 202600123."))
    if tipo["id"] == "ricorso":
        primo = next(iter(_per_ruolo(ctx["parti"], "ricorrente")), None)
        righe.append(_riga("Ricorrente (primo)", _parte_testo(primo) if primo else "",
                           nota="Gli altri si aggiungono nella scheda Parti, anche con il foglio Excel."))
        righe.append(_riga("Sono presenti istanze ante causam?", "Sì" if proc.get("anteCausam") else "No"))
        righe.append(_riga("Tipologia", catalogo.descrizione(
            "tipoRicorsoCds" if catalogo.ambito(codice) in {"CDS", "CGARS"} else "tipoRicorsoTar", proc.get("tipoRicorso") or "")))
        righe.append(_riga("Finanziamento PNRR art. 12-bis d.l. 68/2022", "Sì" if proc.get("pnrr") else "No"))
        oggetto = proc.get("oggetto") or ctx["fascicolo"].get("oggetto") or ""
        righe.append(_riga("Oggetto", oggetto, VERIFICA if len(oggetto) > LIMITE_OGGETTO else "",
                           "Riportare l'oggetto della domanda come da epigrafe (max 16.000 caratteri)."))
    return {"titolo": "Creazione della bozza", "righe": righe}


def _scheda_parti(ctx: dict[str, Any]) -> dict[str, Any]:
    righe = []
    for ruolo, titolo in (("ricorrente", "Ricorrenti"), ("resistente", "Resistenti"), ("controinteressato", "Controinteressati")):
        parti = _per_ruolo(ctx["parti"], ruolo)
        valore = "; ".join(_parte_testo(p) for p in parti)
        stato = OK if parti else (FACOLTATIVO if ruolo == "controinteressato" else MANCA)
        nota = f"{len(parti)} parti: usa «Carica Excel» con il foglio preparato da IUSENTRA." if len(parti) > 1 else (
            "Se non ci sono, spunta «Il controinteressato è non indicato/non conosciuto»." if ruolo == "controinteressato" else "")
        righe.append({**_riga(titolo, valore, stato, nota), "excel": ruolo if parti else ""})
    return {"titolo": "Parti", "righe": righe}


def _scheda_atti(ctx: dict[str, Any], principale: str) -> dict[str, Any]:
    proc = ctx["procedimento"]
    atto = next(iter(_documenti(ctx, "atto")), None)
    procura = next(iter(_documenti(ctx, "procura")), None)
    righe = [_riga_file(principale, atto),
             _riga_file("Procura alle liti", procura, obbligatorio=False) if procura else
             _riga("Procura alle liti", "Procura a margine dell'atto introduttivo?", VERIFICA,
                   "Carica la procura o spunta «Procura a margine» nella finestra della procura.", copia=False)]
    if principale == "Ricorso":
        impugnato = proc.get("attoImpugnato") or {}
        testo = " · ".join(str(impugnato.get(k) or "") for k in ("organo", "tipo", "numero", "anno") if impugnato.get(k))
        righe.append(_riga("Atto impugnato", testo, nota="Denominazione organo, tipologia, anno e numero; "
                           "oppure «Atto impugnato: non indicato/non conosciuto»."))
    for doc in _documenti(ctx, "allegato"):
        riga = _riga_file("Documento allegato", doc)
        riga["descrizione"] = (doc.get("descrizione") or doc.get("nome") or "")[:LIMITE_DESCRIZIONE]
        righe.append(riga)
    return {"titolo": "Ricorso, procura e allegati" if principale == "Ricorso" else "Atto, procura e documenti", "righe": righe}


def _scheda_notifiche(ctx: dict[str, Any]) -> dict[str, Any]:
    relate = _documenti(ctx, "notifica")
    righe = []
    for parte in _per_ruolo(ctx["parti"], "resistente") + _per_ruolo(ctx["parti"], "controinteressato"):
        righe.append(_riga("Parte notificata", _parte_testo(parte), nota="Data invio, data ricezione e modalità dalla ricevuta."))
    righe += [_riga_file("Copia informatica di relata e atto notificato", d) for d in relate] or [
        _riga("Copia informatica di relata e atto notificato", "", MANCA, "Carica l'atto notificato con la relata e le ricevute.")]
    return {"titolo": "Notifiche", "righe": righe}


def _scheda_contributo(ctx: dict[str, Any]) -> dict[str, Any]:
    proc, cu = ctx["procedimento"], ctx.get("contributo") or {}
    tipologia = proc.get("cuTipologia") or ""
    righe = [_riga("Tipologia", tipologia, nota=" / ".join(catalogo.CONTRIBUTO))]
    if tipologia == "Esente":
        righe.append(_riga("Tipo esenzione", proc.get("esenzione")))
    if tipologia in {"", "Non esente"}:
        righe.append(_riga("Importo dovuto", f"€ {cu['importo']:.2f}".replace(".", ",") if cu.get("importo") else "",
                           VERIFICA if cu.get("importo") else MANCA, cu.get("nota", "")))
        righe.append(_riga("Estremi del versamento", cu.get("versamento"),
                           nota="Data, modalità, estremi, codice tributo e copia informatica della ricevuta."))
    return {"titolo": "Contributo unificato", "righe": righe}


def _scheda_istanze(ctx: dict[str, Any]) -> dict[str, Any]:
    scelte = [i for i in ctx["procedimento"].get("istanze") or [] if i in catalogo.ISTANZE_SEGNALABILI]
    return {"titolo": "Segnala istanze/domande",
            "righe": [_riga("Istanze e domande", "; ".join(scelte) or "Nessuna istanza", OK,
                            "Spunta le stesse voci nel portale.")]}


def _invio() -> dict[str, Any]:
    return {"titolo": "Riepilogo, firma e invio", "righe": [
        _riga("1. Genera riepilogo", "Il portale crea il PDF del deposito con l'impronta di ogni file.", OK, copia=False),
        _riga("2. Verifica in IUSENTRA", "Carica il riepilogo nella scheda «Verifica riepilogo».", OK, copia=False),
        _riga("3. Firma", "Firma digitale PAdES del riepilogo.", OK, copia=False),
        _riga("4. Invia deposito", "Carica il riepilogo firmato e conferma: l'invio lo fa solo l'avvocato.", OK, copia=False),
    ]}


def scheda(ctx: dict[str, Any], tipo_id: str) -> dict[str, Any]:
    tipo = catalogo.deposito(tipo_id)
    sezioni = [passi_iniziali(ctx, tipo)]
    if tipo_id == "ricorso":
        sezioni += [_scheda_parti(ctx), _scheda_atti(ctx, "Ricorso"), _scheda_istanze(ctx), _scheda_notifiche(ctx),
                    _scheda_contributo(ctx)]
    elif tipo_id in {"atto-successivo", "istanze-giudice"}:
        sezioni += [_scheda_atti(ctx, "Istanza" if tipo_id == "istanze-giudice" else "Atto")]
        if tipo_id == "atto-successivo":
            sezioni += [_scheda_notifiche(ctx), _scheda_contributo(ctx)]
    elif tipo_id == "documento-successivo":
        sezioni += [{"titolo": "Documenti", "righe": [_riga_file("Documento", d) for d in _documenti(ctx, "allegato")]
                     or [_riga("Documento", "", MANCA)]}]
    elif tipo_id == "succ-notifiche":
        sezioni += [_scheda_notifiche(ctx)]
    elif tipo_id in {"succ-contr-unificato", "rimborso"}:
        sezioni += [_scheda_contributo(ctx)]
    elif tipo_id == "richieste-segreteria":
        sezioni += [{"titolo": "Richiesta", "righe": [_riga("Tipo di richiesta", "", MANCA,
                     "Attestazioni, copie, certificazioni: scegli la voce dal portale.", copia=False)]}]
    sezioni.append(_invio())
    mancanti = [f"{s['titolo']}: {r['etichetta']}" for s in sezioni for r in s["righe"] if r["stato"] == MANCA]
    da_verificare = [f"{s['titolo']}: {r['etichetta']}" for s in sezioni for r in s["righe"] if r["stato"] == VERIFICA]
    return {"tipo": tipo_id, "nome": tipo["nome"], "link": catalogo.link_deposito(tipo_id), "sezioni": sezioni,
            "mancanti": mancanti, "daVerificare": da_verificare, "pronto": not mancanti and not da_verificare}


__all__ = ["FACOLTATIVO", "MANCA", "OK", "VERIFICA", "passi_iniziali", "scheda"]
