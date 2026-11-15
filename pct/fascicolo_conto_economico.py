"""Conto economico del fascicolo: le voci con la loro fonte e il percorso dalla sentenza all'incasso fatturato.

Il percorso segue le norme vigenti:
- la sentenza liquida le spese e, se il difensore lo chiede, le distrae in suo favore (art. 93 c.p.c.);
- per l'avvocato la prestazione si considera effettuata all'atto del pagamento del corrispettivo (art. 6, terzo
  comma, D.P.R. 633/1972): prima si invia l'avviso di parcella (proforma), la fattura si emette quando arriva il
  pagamento, per l'importo ricevuto, entro dodici giorni (art. 21, comma 4, D.P.R. 633/1972);
- le somme anticipate in nome e per conto del cliente restano fuori dalla base imponibile se documentate
  (art. 15, primo comma, n. 3, D.P.R. 633/1972);
- il contributo unificato si versa (art. 13 D.P.R. 115/2002) salvo esenzione per reddito nelle cause di lavoro,
  previdenza e pubblico impiego, con autocertificazione (art. 9, comma 1-bis, D.P.R. 115/2002).

Modulo puro: riceve i dati già letti (voci del fascicolo, crediti da sentenza con le fonti, documenti del contributo
dal catalogo, documenti economici e incassi registrati) e non scrive nulla. La conferma dell'avvocato resta un
gesto esplicito: qui si dice soltanto a che punto è il percorso e qual è il prossimo passo.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Mapping

NORMA_DISTRAZIONE = "art. 93 c.p.c."
NORMA_CONDANNA = "art. 91 c.p.c."
NORMA_COMPENSAZIONE = "art. 92 c.p.c."
NORMA_SPESE_AMMINISTRATIVE = "art. 26 c.p.a."
NORMA_FORFETTARIO = "art. 2, comma 2, D.M. 55/2014"
NORMA_PAGAMENTO = "art. 6, terzo comma, D.P.R. 633/1972"
NORMA_TERMINE_FATTURA = "art. 21, comma 4, D.P.R. 633/1972"
NORMA_ANTICIPAZIONI = "art. 15, primo comma, n. 3, D.P.R. 633/1972"
NORMA_CU = "art. 13 D.P.R. 115/2002"
NORMA_ESENZIONE_CU = "art. 9, comma 1-bis, D.P.R. 115/2002"
NORMA_ESECUZIONE_PA = "art. 14, comma 1, D.L. 669/1996"
GIORNI_EMISSIONE_FATTURA = 12



def _euro(valore: float | None) -> str:
    if valore is None:
        return ""
    testo = f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"€ {testo}"


def _data_it(iso: str) -> str:
    iso = str(iso or "")[:10]
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso) == 10 else ""


def _numero(valore: Any) -> float | None:
    try:
        numero = round(float(valore), 2)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def _fonte(etichetta: str, href: str = "", norma: str = "") -> dict[str, str]:
    return {"label": etichetta, "href": href, "norma": norma}


def _riga(voce: str, etichetta: str, *, importo: float | None, stato: str, tono: str, dettaglio: str = "",
          fonti: Iterable[Mapping[str, str]] = (), norma: str = "") -> dict[str, Any]:
    return {"voce": voce, "etichetta": etichetta, "importo": importo, "importoLabel": _euro(importo), "stato": stato,
            "tono": tono, "dettaglio": dettaglio, "fonti": [dict(f) for f in fonti if f.get("label")], "norma": norma}


def _riga_senza_credito(sentenze: list[Mapping[str, Any]]) -> dict[str, Any]:
    """La sentenza della causa c'è ma non dà un credito: spese compensate, a carico del cliente o importo da leggere."""
    fonti = [f for s in sentenze for f in s.get("fonti") or []]
    data = next((_data_it(s.get("data")) for s in sentenze if s.get("data")), "")
    della = f"La sentenza{' del ' + data if data else ''}"
    regolazioni = {str(s.get("regolazione") or "") for s in sentenze}
    if regolazioni <= {"compensazione"}:
        return _riga("sentenza", "Spese di lite in sentenza", importo=None, stato="Spese compensate", tono="neutral",
                     norma=NORMA_COMPENSAZIONE, fonti=fonti,
                     dettaglio=f"{della} compensa le spese. Ciascuna parte sostiene le proprie spese di lite.")
    if "compensazione_parziale" in regolazioni:
        return _riga("sentenza", "Importo liquidato in sentenza", importo=None, stato="Spese compensate in parte", tono="warning",
                     norma=NORMA_COMPENSAZIONE, fonti=fonti,
                     dettaglio=f"{della} compensa le spese solo in parte: leggere il dispositivo per la quota liquidata e chi la paga.")
    a_carico = [s for s in sentenze if s.get("regolazione") == "condanna" and s.get("a_favore_del_cliente") is False]
    if a_carico:
        return _riga("sentenza", "Importo liquidato in sentenza", importo=_numero(a_carico[0].get("importo")),
                     stato="Spese a carico del cliente", tono="danger", norma=NORMA_CONDANNA, fonti=fonti,
                     dettaglio=f"{della} condanna il cliente alle spese: non è un credito dello studio; informare il cliente "
                               "e valutare l'impugnazione.")
    return _riga("sentenza", "Importo liquidato in sentenza", importo=None, stato="Importo da leggere sul dispositivo", tono="warning",
                 norma=NORMA_CONDANNA, fonti=fonti,
                 dettaglio=f"{della} regola le spese ma l'importo o il beneficiario non sono stati letti con certezza: aprire il dispositivo.")


def riga_sentenza(crediti: list[Mapping[str, Any]], sentenze: list[Mapping[str, Any]] | None = None,
                  *, regime: str = "") -> dict[str, Any]:
    """Spese liquidate dalla sentenza della causa: a favore del cliente o distratte in favore dell'avvocato.

    ``sentenze``: le regolazioni delle spese lette dal dispositivo (``pct/archivio_letture/spese_sentenza.py``); se la
    sentenza c'è ma non dà un credito, la riga dice perché invece di attendere una sentenza già arrivata.
    """
    if not crediti and sentenze:
        return _riga_senza_credito(list(sentenze))
    if not crediti:
        return _riga("sentenza", "Importo liquidato in sentenza", importo=None, stato="Nessuna sentenza con spese liquidate",
                     tono="neutral", dettaglio="Quando arriva la sentenza della causa, l'importo e la fonte compaiono qui.")
    distratte = [c for c in crediti if c.get("distrazione")]
    scelti = distratte or list(crediti)
    # Il decreto ingiuntivo (e gli altri provvedimenti fuori sentenza) liquida le spese anche lui (art. 641 c.p.c.).
    nature = {str(c.get("provvedimento") or "sentenza") for c in scelti}
    etichetta = "Importo liquidato in sentenza" if nature == {"sentenza"} else (
        f"Spese liquidate nel {next(iter(nature))}" if len(nature) == 1 else "Spese liquidate dal giudice")
    esborsi = round(sum(float(c.get("esborsi") or 0) for c in scelti), 2)
    # Lo stesso importo letto da più documenti (la sentenza e la sua copia arrivata via PEC) è un credito solo:
    # non si somma, si mostrano le fonti e si chiede di verificarlo.
    gruppi: dict[float, list[Mapping[str, Any]]] = {}
    for credito in scelti:
        importo = _numero(credito.get("importo"))
        if importo is not None:
            gruppi.setdefault(importo, []).append(credito)
    totale = round(sum(gruppi), 2) or None
    fonti = [f for c in scelti for f in c.get("fonti") or []]
    avvisi = []
    if any(len(gruppo) > 1 and (
        not all(c.get("identita_atto") for c in gruppo)
        or len({c["identita_atto"] for c in gruppo}) > 1
    ) for gruppo in gruppi.values()):
        avvisi.append("Stesso importo in più documenti: contato una volta, verificare che sia la stessa sentenza.")
    if any(_numero(c.get("importo")) is None for c in scelti):
        avvisi.append("Una fonte indica spese a credito senza riportare un importo leggibile.")
    if len(gruppi) > 1:
        avvisi.append("Importi diversi in più sentenze del fascicolo: verificare quale è definitiva prima di chiedere il pagamento.")
    if any(c.get("accessori") for c in scelti):
        # Nel regime forfetario o dei minimi l'IVA non si applica (art. 1, comma 58, L. 190/2014; art. 27 D.L. 98/2011).
        iva = ("senza IVA per il regime forfetario dello studio" if str(regime).upper() in {"RF19", "RF02"}
               else "IVA")
        avvisi.append(f"Oltre all'importo liquidato spettano gli accessori: rimborso forfettario del 15% ({NORMA_FORFETTARIO}), "
                      f"contributo previdenziale e {iva}, da indicare nella proforma." if iva == "IVA" else
                      f"Oltre all'importo liquidato spettano gli accessori: rimborso forfettario del 15% ({NORMA_FORFETTARIO}) "
                      f"e contributo previdenziale ({iva}), da indicare nella proforma.")
    if distratte and any(c.get("distrazione_condizionata") for c in distratte):
        avvisi.append("La sentenza distrae le spese «ove richiesto»: verificare che negli atti ci sia la dichiarazione di antistatarietà.")
    if esborsi:
        avvisi.append(f"Oltre ai compensi sono liquidati {_euro(esborsi)} di esborsi non imponibili ({NORMA_ANTICIPAZIONI}).")
    if distratte:
        return _riga("sentenza", etichetta, importo=totale, stato="Distratte in favore dell'avvocato",
                     tono="primary", norma=NORMA_DISTRAZIONE, fonti=fonti,
                     dettaglio=" ".join(["Le paga la controparte direttamente al difensore antistatario."] + avvisi))
    return _riga("sentenza", etichetta, importo=totale, stato="Spese liquidate al cliente",
                 tono="primary" if not avvisi else "warning", norma=NORMA_CONDANNA, fonti=fonti,
                 dettaglio=" ".join(["Le paga la controparte al cliente."] + avvisi))


def riga_contributo(voce: Mapping[str, Any], documenti: list[Mapping[str, Any]],
                    stato: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Contributo unificato: lo stato unico di ``pct.contributo_unificato_stato`` (lo stesso di card, finestra e quadro).

    ``stato``: lo stato già calcolato dal chiamante; se manca si calcola qui da voce e documenti del catalogo.
    """
    from pct.contributo_unificato_stato import stato_contributo

    stato = dict(stato) if stato else stato_contributo(voce, documenti)
    ruolo = str(stato.get("ruoloFonti") or "")
    riga = _riga("contributo_unificato", "Contributo unificato", importo=stato.get("importo"), stato=stato["etichetta"],
                 tono=stato["tono"], norma=stato.get("norma") or "", dettaglio=stato.get("dettaglio") or "",
                 fonti=[_fonte(f.get("nome") or "", f.get("href") or "", ruolo) for f in stato.get("fonti") or []])
    riga["statoContributo"] = stato
    return riga


def _documento(parcella: Mapping[str, Any]) -> str:
    return "fattura" if str(parcella.get("operativo") or "").upper() == "FATTURA" else "proforma"


def righe_parcella(parcelle: list[Mapping[str, Any]], voce_spese: Mapping[str, Any], voce_fondo: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Parcella, spese ed esborsi, anticipazioni: dai documenti economici del fascicolo.

    Una bozza automatica dichiarata superata (``pct.proforma_unica``) non entra nei totali: lo stesso compenso
    non si chiede due volte; la riga la indica con la proposta di annullarla.
    """
    from pct.proforma_unica import attive_non_superate

    attive = attive_non_superate(parcelle)
    superate = [p for p in parcelle if p.get("superata") and str(p.get("stato") or "").upper() != "ANNULLATA"]
    righe = []
    onorari = round(sum(float(p.get("onorari") or 0) for p in attive), 2) or None
    avviso = " ".join(f"La proforma {p.get('numero')} è superata dalla {(p.get('superata') or {}).get('da_numero') or 'proforma valida'}: "
                      "stesso compenso, non sommata; proposta all'avvocato di annullarla." for p in superate)
    righe.append(_riga("parcella", "Parcella dell'avvocato", importo=onorari or _numero((attive[:1] or [{}])[0].get("totale")),
                       stato="Da preparare" if not attive else ("Fatturata" if any(_documento(p) == "fattura" for p in attive) else "Proforma"),
                       tono="warning" if not attive or superate else "primary", dettaglio=avviso,
                       fonti=[_fonte(f"{'Fattura' if _documento(p) == 'fattura' else 'Proforma'} {p.get('numero') or ''}".strip(),
                                     f"/fatturazione?id_documento={p.get('id')}") for p in attive]))
    spese = round(sum(float(p.get("spese") or 0) for p in attive), 2) or _numero(voce_spese.get("importo"))
    fonte_spese = str(voce_spese.get("documento_fonte") or "")
    # Un documento indicato come fonte senza importo non è «nessuna spesa»: l'importo va riportato dal documento.
    stato_spese = "Documentate" if spese else ("Importo da riportare" if fonte_spese else "Nessuna spesa registrata")
    righe.append(_riga("spese_esborsi", "Spese ed esborsi", importo=spese, stato=stato_spese,
                       tono="primary" if spese else ("warning" if fonte_spese else "neutral"),
                       dettaglio="" if spese or not fonte_spese else "Il documento indicato come fonte non ha un importo registrato: riportare le spese documentate.",
                       fonti=[_fonte(fonte_spese, str(voce_spese.get("href") or ""))]))
    anticipi = round(sum(float(p.get("anticipazioni") or 0) for p in attive), 2) or None
    fondo = _numero(voce_fondo.get("importo"))
    fonti_anticipi = [_fonte(f"Voci di anticipazione nella {_documento(p)} {p.get('numero') or ''}".strip(),
                             f"/fatturazione?id_documento={p.get('id')}") for p in attive if float(p.get("anticipazioni") or 0) > 0]
    if fondo:
        fonti_anticipi.append(_fonte(str(voce_fondo.get("documento_fonte") or "Fondo spese ricevuto dal cliente"),
                                     str(voce_fondo.get("href") or "")))
    righe.append(_riga("anticipazioni", "Anticipazioni", importo=anticipi or fondo,
                       stato="Con fonte" if fonti_anticipi else "Nessuna anticipazione registrata",
                       tono="primary" if fonti_anticipi else "neutral", norma=NORMA_ANTICIPAZIONI, fonti=fonti_anticipi,
                       dettaglio=("Fondo spese ricevuto dal cliente: " + _euro(fondo)) if fondo else
                       "Le somme pagate in nome e per conto del cliente (es. contributo unificato) vanno documentate."))
    return righe


def percorso(parcelle: list[Mapping[str, Any]], crediti: list[Mapping[str, Any]], *, oggi: date | None = None,
             dichiarato: Mapping[str, Any] | None = None, esecuzione: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Sentenza → proforma → pagamento → fattura di pari importo → conferma, con il prossimo passo.

    ``esecuzione``: i 120 giorni dell'art. 14 D.L. 669/1996 dalla notifica della sentenza a una pubblica
    amministrazione (``pct.sentenza_notificata``). Credito non incassato e termine decorso: il prossimo passo è la
    richiesta di pagamento o il precetto (artt. 479-480 c.p.c.); prima del termine il precetto non si notifica.
    """
    from pct.proforma_unica import attive_non_superate

    oggi = oggi or date.today()
    attive = attive_non_superate(parcelle)
    incassato = round(sum(float(p.get("incassato") or 0) for p in attive), 2)
    pagamenti = sorted(str(p.get("data_pagamento") or "")[:10] for p in attive if p.get("data_pagamento"))
    fatture = [p for p in attive if _documento(p) == "fattura"]
    fatturato = round(sum(float(p.get("totale") or 0) for p in fatture), 2)
    passi = [
        {"codice": "sentenza", "etichetta": "Sentenza", "fatto": bool(crediti)},
        {"codice": "proforma", "etichetta": "Proforma", "fatto": bool(attive)},
        {"codice": "pagamento", "etichetta": "Pagamento ricevuto", "fatto": incassato > 0,
         "dettaglio": f"{_euro(incassato)} il {_data_it(pagamenti[-1])}" if incassato > 0 and pagamenti else (_euro(incassato) if incassato > 0 else "")},
        {"codice": "fattura", "etichetta": "Fattura elettronica", "fatto": bool(fatture),
         "dettaglio": ", ".join(f"n. {p.get('numero')} {_euro(_numero(p.get('totale')))}" + (f" · SdI {p.get('sdi_stato')}" if p.get("sdi_stato") else "") for p in fatture)},
        {"codice": "conferma", "etichetta": "Confermato dall'avvocato",
         "fatto": bool(fatture) and incassato > 0 and abs(fatturato - incassato) < 0.01 and all(str(p.get("stato") or "").upper() == "PAGATA" for p in fatture)},
    ]
    segnato = dichiarato or {}
    if incassato <= 0 and segnato.get("data"):
        passi[2]["dettaglio"] = (f"Segnato come pagato il {_data_it(segnato['data'])}"
                                 + (" dalla lettura automatica" if segnato.get("automatico") else "")
                                 + (" senza prova d'incasso: credito da incassare" if segnato.get("senza_prova")
                                    else ": non registrato negli incassi"))
    # Ogni passo da fare porta al punto del software dove l'avvocato lo compie: nessuna operazione fiscale parte da qui.
    documento = f"/fatturazione?id_documento={attive[-1].get('id')}" if attive else ""
    azioni = {
        "proforma": {"label": "Prepara la proforma", "comando": "genera_proforma"} if not attive else {"label": "Apri la proforma", "href": documento},
        "pagamento": {"label": "Registra l'incasso", "href": documento} if attive else {},
        "fattura": {"label": "Emetti la fattura elettronica", "href": documento} if attive and incassato > 0 else {},
        "conferma": {"label": "Conferma il pagamento", "href": documento} if fatture else {},
    }
    for passo in passi:
        azione = azioni.get(passo["codice"]) or {}
        if azione and not passo["fatto"]:
            passo["azione"] = azione
    if not attive:
        prossimo = ("Preparare la proforma (avviso di parcella) da inviare: la fattura si emette solo al pagamento "
                    f"({NORMA_PAGAMENTO})." if crediti else "Nessun documento economico: preparare la proforma quando la pratica lo richiede.")
    elif incassato <= 0 and (dichiarato or {}).get("data") and not (dichiarato or {}).get("senza_prova"):
        prossimo = ("Il controllo economico segna un pagamento non registrato negli incassi: registrare l'incasso reale "
                    "(data e importo dell'accredito) prima di emettere la fattura.")
    elif incassato <= 0 and crediti and (esecuzione or {}).get("deadline"):
        fine = date.fromisoformat(str(esecuzione["deadline"])[:10])
        if fine < oggi:
            prossimo = (f"Credito non incassato: i 120 giorni dalla notifica della sentenza all'amministrazione sono decorsi il "
                        f"{fine.strftime('%d/%m/%Y')} ({NORMA_ESECUZIONE_PA}): inviare la richiesta di pagamento o notificare il "
                        "precetto (artt. 479-480 c.p.c.). La fattura si emette solo all'incasso.")
        else:
            prossimo = (f"Proforma pronta: inviarla all'amministrazione. Il precetto si potrà notificare solo dopo il "
                        f"{fine.strftime('%d/%m/%Y')} ({NORMA_ESECUZIONE_PA}).")
    elif incassato <= 0:
        prossimo = "Proforma pronta: inviarla e attendere il pagamento. La fattura non si emette prima dell'incasso."
    elif not fatture:
        scadenza = date.fromisoformat(pagamenti[-1]) + timedelta(days=GIORNI_EMISSIONE_FATTURA) if pagamenti else None
        prossimo = (f"Pagamento ricevuto ({_euro(incassato)}): emettere la fattura elettronica dello stesso importo"
                    + (f" entro il {scadenza.strftime('%d/%m/%Y')}" if scadenza else "") + f" ({NORMA_TERMINE_FATTURA}).")
        if scadenza and scadenza < oggi:
            prossimo = "Termine scaduto: " + prossimo
    elif abs(fatturato - incassato) >= 0.01:
        prossimo = f"La fattura ({_euro(fatturato)}) non coincide con l'incasso ({_euro(incassato)}): verificare prima di confermare."
    elif not passi[-1]["fatto"]:
        prossimo = "Fattura emessa e pari all'incasso: l'avvocato conferma il pagamento nel documento economico."
    else:
        prossimo = "Percorso concluso: pagamento ricevuto, fatturato per lo stesso importo e confermato."
    return {"passi": passi, "prossimoPasso": prossimo, "incassato": incassato, "fatturato": fatturato}


def conto_economico(*, voci: Mapping[str, Mapping[str, Any]], crediti: list[Mapping[str, Any]],
                    documenti_contributo: list[Mapping[str, Any]], parcelle: list[Mapping[str, Any]],
                    oggi: date | None = None, sentenze: list[Mapping[str, Any]] | None = None,
                    regime: str = "", stato_contributo: Mapping[str, Any] | None = None,
                    esecuzione: Mapping[str, Any] | None = None, amministrativo: bool = False) -> dict[str, Any]:
    spese = riga_sentenza(crediti, sentenze, regime=regime)
    if amministrativo and spese.get("norma"):
        spese["norma"] = f"{NORMA_SPESE_AMMINISTRATIVE} in relazione all’{spese['norma']}"
    righe = [spese,
             riga_contributo(voci.get("contributo_unificato") or {}, documenti_contributo, stato_contributo)]
    righe += righe_parcella(parcelle, voci.get("spese_esborsi") or {}, voci.get("fondo_spese") or {})
    liquidazione = voci.get("liquidazione_giudice") or {}
    from pct.incasso_provato import pagato_senza_prova

    dichiarato = None
    if str(liquidazione.get("status") or "") == "pagato" and liquidazione.get("data_pagamento"):
        # «Pagato» scritto da un automatismo senza prova d'incasso non è un pagamento: il credito resta da incassare.
        dichiarato = {"data": str(liquidazione["data_pagamento"])[:10],
                      "automatico": str(liquidazione.get("origine") or "").startswith("lex_ai") or pagato_senza_prova(liquidazione),
                      "senza_prova": pagato_senza_prova(liquidazione)}
    risultato_percorso = percorso(parcelle, crediti, oggi=oggi, dichiarato=dichiarato, esecuzione=esecuzione)
    if sentenze and not crediti:
        risultato_percorso["passi"][0].update(fatto=True, dettaglio=righe[0]["stato"])
        if all(s.get("regolazione") == "compensazione" for s in sentenze):
            for passo in risultato_percorso["passi"]:
                if (passo.get("azione") or {}).get("comando") == "genera_proforma":
                    passo.pop("azione")
                    passo["dettaglio"] = "Eventuali compensi verso il cliente secondo l'incarico."
                    risultato_percorso["prossimoPasso"] = (
                        f"Spese di lite compensate ({spese['norma']}). "
                        "Consultare il conferimento per gli eventuali compensi verso il cliente."
                    )
    return {"righe": righe, "percorso": risultato_percorso}


__all__ = ["conto_economico", "percorso", "riga_contributo", "riga_sentenza", "righe_parcella"]
