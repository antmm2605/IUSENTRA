"""La scheda del deposito PTT: cosa scrivere, nell'ordine delle schede della NIR web del SIGIT.

Riceve il contesto già risolto (procedimento, parti, difensore, documenti
controllati, CUT, termini) e restituisce le sezioni come le mostra l'area
riservata del PTT (DGT, articoli DF-GiustiziaTributaria-3067, 3066, 3179 e
Istruzioni operative maggio 2023). Ogni riga dice se il dato c'è, manca o va
verificato; un dato assente resta «da indicare».
"""

from __future__ import annotations

from typing import Any

from . import catalogo

OK, MANCA, FACOLTATIVO, VERIFICA = "ok", "manca", "facoltativo", "verifica"


def _riga(etichetta: str, valore: Any, stato: str = "", nota: str = "", copia: bool = True) -> dict[str, Any]:
    testo = "" if valore in (None, False) else str(valore).strip()
    return {"etichetta": etichetta, "valore": testo or "da indicare", "stato": stato or (OK if testo else MANCA),
            "nota": nota, "copia": copia and bool(testo)}


def _euro(valore: Any) -> str:
    return f"€ {float(valore):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if valore not in (None, "") else ""


def _natura(codice: str) -> str:
    return next((f"{c} {d}" for c, d in catalogo.NATURA_GIURIDICA if c == codice), "")


def _dati_generali(ctx: dict[str, Any], tipo: dict[str, Any]) -> dict[str, Any]:
    proc = ctx["procedimento"]
    corte = catalogo.sede(proc.get("corte") or "")
    righe = [_riga("Corte di giustizia tributaria", corte["nome"] if corte else "", nota="Scegli la Corte competente: sede dell'ente impositore (art. 4)."),
             _riga("Tipologia di deposito", tipo["nome"], OK, copia=False)]
    if tipo["rg"]:
        righe.append(_riga("Numero di ruolo (RGR/RGA)", proc.get("rg"), nota="Numero, anno e sotto-numero; per le controdeduzioni anche il numero della ricevuta."))
    else:
        righe.append(_riga("Atto principale", proc.get("atto") or tipo["principale"], OK, "Appendice A delle istruzioni PTT."))
        righe.append(_riga("Trattazione in pubblica udienza", proc.get("pubblicaUdienza") or "No (camera di consiglio)", OK,
                           "Se richiesta a distanza la segreteria invia l'avviso con il collegamento (art. 34-bis)."))
        righe.append(_riga("Istanza di sospensione", "Sì" if proc.get("sospensione") else "No", OK))
    return {"titolo": "Dati generali", "righe": righe}


def _parti(ctx: dict[str, Any], tipo: dict[str, Any]) -> list[dict[str, Any]]:
    parti, avv = ctx["parti"], ctx.get("avvocato") or {}
    ricorrenti = [_riga("Ricorrente" if tipo["id"] != "appello" else "Appellante",
                        " · ".join(x for x in (p["denominazione"], p["codiceFiscale"], _natura(p.get("natura", ""))) if x),
                        VERIFICA if not p.get("natura") or not p["codiceFiscale"] else OK,
                        "Natura giuridica da scegliere nella Tabella A." if not p.get("natura") else (
                            "Senza codice fiscale il CUT aumenta della metà." if not p["codiceFiscale"] else ""))
                  for p in parti["ricorrenti"]] or [_riga("Ricorrente", "", MANCA)]
    difensore = [_riga("Difensore", " · ".join(x for x in (avv.get("nome"), avv.get("codiceFiscale")) if x),
                       nota="Ordine, numero di tessera e data della nomina come nel mandato."),
                 _riga("PEC del difensore", avv.get("pec"), nota="Senza PEC il CUT aumenta della metà (art. 13 c. 3-bis).")]
    resistenti = [_riga("Parte resistente", " · ".join(x for x in (p["denominazione"], p.get("tipoEnte")) if x),
                        OK if p.get("tipoEnte") else VERIFICA,
                        "" if p.get("tipoEnte") else "Scegli nel SIGIT tipo di ente, provincia, ente e ufficio.")
                  for p in parti["resistenti"]] or [_riga("Parte resistente", "", MANCA, "L'ente impositore o l'agente della riscossione.")]
    return [{"titolo": "Ricorrenti" if tipo["id"] != "appello" else "Appellanti", "righe": ricorrenti},
            {"titolo": "Difensori e domicilio", "righe": difensore},
            {"titolo": "Parti resistenti" if tipo["id"] != "appello" else "Parti appellate", "righe": resistenti}]


def _atti_impugnati(ctx: dict[str, Any]) -> dict[str, Any]:
    righe = []
    for numero, atto in enumerate(ctx["procedimento"].get("atti") or [], start=1):
        descrizione = " · ".join(x for x in (atto.get("tipo"), atto.get("numero"), atto.get("ufficio")) if x)
        righe.append(_riga(f"Atto impugnato {numero}", descrizione, nota="Tabella B della NIR: tipologia, numero e ufficio."))
        righe.append(_riga("Data di notifica dell'atto", atto.get("dataNotifica")))
        righe.append(_riga("Periodo d'imposta", atto.get("periodo"), "" if atto.get("periodo") else FACOLTATIVO))
        valore = "valore indeterminabile" if atto.get("indeterminabile") else _euro(atto.get("tributo") or atto.get("sanzioni"))
        righe.append(_riga("Valore della lite", valore, nota="Tributo al netto di interessi e sanzioni; solo sanzioni se in lite ci sono solo quelle (art. 12)."))
        righe.append(_riga("Materia e tributo", " · ".join(x for x in (atto.get("materia"), atto.get("tributo_tipo")) if x),
                           nota="Almeno una materia procedimentale e un tributo per ogni atto."))
    return {"titolo": "Atti impugnati", "righe": righe or [_riga("Atto impugnato", "", MANCA, "Avviso, cartella, diniego…: Tabella B.")]}


def _sentenza(ctx: dict[str, Any]) -> dict[str, Any]:
    sentenza = ctx["procedimento"].get("sentenza") or {}
    testo = " · ".join(x for x in (sentenza.get("corte"), sentenza.get("numero"), sentenza.get("anno"), sentenza.get("data")) if x)
    return {"titolo": "Sentenza impugnata", "righe": [_riga("Sentenza di primo grado", testo, nota="Corte, tipo, numero, sezione, anno e data.")]}


def _documenti(ctx: dict[str, Any]) -> dict[str, Any]:
    righe = []
    atto = [d for d in ctx["documenti"] if d["ruolo"] == "atto"]
    for doc in atto[:1]:
        righe.append(_riga("Atto principale firmato", doc["nome"], VERIFICA if doc["bloccante"] else OK,
                           "; ".join(e["messaggio"] for e in doc["esiti"]) or f"Firma {doc['firma'].upper()} rilevata."))
    if not atto:
        righe.append(_riga("Atto principale firmato", "", MANCA, "PDF/A nativo firmato CAdES o PAdES: si carica per primo."))
    for doc in [d for d in ctx["documenti"] if d["ruolo"] == "allegato"]:
        riga = _riga(doc.get("tipologia") or "Allegato", doc["nome"], VERIFICA if doc["bloccante"] else OK,
                     "; ".join(e["messaggio"] for e in doc["esiti"]) or "Firma facoltativa per gli allegati.")
        righe.append(riga)
    return {"titolo": "Documenti allegati", "righe": righe}


def _contributo(ctx: dict[str, Any]) -> dict[str, Any]:
    proc, cut = ctx["procedimento"], ctx.get("cut") or {}
    calcolato = bool(cut.get("righe")) or bool(proc.get("cutEsenzione"))
    righe = [_riga("CUT dovuto", _euro(cut.get("totale")) if calcolato else "", VERIFICA if cut.get("maggiorazione") else "",
                   cut.get("nota") or "Art. 13 c. 6-quater d.P.R. 115/2002: somma dei contributi di ogni atto.")]
    modalita = proc.get("cutEsenzione") or proc.get("cutModalita")
    righe.append(_riga("Modalità di pagamento", modalita, nota="pagoPA dal PTT, F23 (codice tributo 171T) o contrassegno."))
    if not proc.get("cutEsenzione"):
        corte = catalogo.sede(proc.get("corte") or "")
        if proc.get("cutModalita") == "F23" and corte:
            righe.append(_riga("Codice ufficio F23", corte.get("codiceF23"), OK, f"Codice tributo 171T; ufficio di {corte['citta']}."))
        righe.append(_riga("Estremi del versamento", " · ".join(x for x in (proc.get("cutEstremi"), proc.get("cutData")) if x),
                           FACOLTATIVO if proc.get("cutModalita") == "pagoPA" else "",
                           "Con pagoPA si paga dal link nella PEC con il numero di ruolo." if proc.get("cutModalita") == "pagoPA" else ""))
    return {"titolo": "Contributo unificato", "righe": righe}


def _invio(tipo: dict[str, Any]) -> dict[str, Any]:
    righe = [_riga("1. Valida la NIR", "Scarica la bozza, controllala e premi «Valida»: dopo non è più modificabile.", OK, copia=False),
             _riga("2. Trasmetti", "Ricevuta di avvenuta trasmissione a video e via PEC.", OK, copia=False),
             _riga("3. Esito dei controlli", "Entro 24 ore la PEC con l'esito e, per ricorso e appello, il numero RGR/RGA.", OK, copia=False),
             _riga("4. Registra in IUSENTRA", "Stato della NIR, ricevuta e numero di ruolo nella scheda «Depositi».", OK, copia=False)]
    if tipo["id"] == "nota-documenti":
        righe.insert(0, _riga("Nota di deposito", "Il SIGIT genera la nota in PDF/A: scaricala, firmala e ricaricala.", OK, copia=False))
    return {"titolo": "Validazione e trasmissione", "righe": righe}


def scheda(ctx: dict[str, Any], tipo_id: str) -> dict[str, Any]:
    tipo = catalogo.deposito(tipo_id)
    sezioni = [_dati_generali(ctx, tipo)]
    if tipo_id in {"ricorso", "appello"}:
        sezioni += _parti(ctx, tipo)
        sezioni.append(_atti_impugnati(ctx) if tipo_id == "ricorso" else _sentenza(ctx))
        sezioni += [_documenti(ctx), _contributo(ctx)]
    elif tipo_id == "controdeduzioni":
        sezioni += [_documenti(ctx)]
    elif tipo_id == "altri-atti":
        sezioni += [{"titolo": "Atti processuali", "righe": [_riga("Tipo di atto", ctx["procedimento"].get("atto"),
                    nota="Appendice C: memorie, istanze, conciliazione, rinuncia, procura-nomina del difensore…")]}, _documenti(ctx)]
    elif tipo_id == "nota-documenti":
        sezioni += [{"titolo": "Motivazione", "righe": [_riga("Motivazione del deposito", ctx["procedimento"].get("note"),
                    nota="Obbligatoria: solo documenti, nessun atto processuale.")]},
                    {"titolo": "Documenti", "righe": [r for r in _documenti(ctx)["righe"] if r["etichetta"] != "Atto principale firmato"]
                     or [_riga("Documento", "", MANCA)]}]
    sezioni.append(_invio(tipo))
    mancanti = [f"{s['titolo']}: {r['etichetta']}" for s in sezioni for r in s["righe"] if r["stato"] == MANCA]
    da_verificare = [f"{s['titolo']}: {r['etichetta']}" for s in sezioni for r in s["righe"] if r["stato"] == VERIFICA]
    return {"tipo": tipo_id, "nome": tipo["nome"], "link": catalogo.PORTALE, "sezioni": sezioni,
            "mancanti": mancanti, "daVerificare": da_verificare, "pronto": not mancanti and not da_verificare}


__all__ = ["FACOLTATIVO", "MANCA", "OK", "VERIFICA", "scheda"]
