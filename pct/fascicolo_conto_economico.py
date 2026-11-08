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
NORMA_FORFETTARIO = "art. 2, comma 2, D.M. 55/2014"
NORMA_PAGAMENTO = "art. 6, terzo comma, D.P.R. 633/1972"
NORMA_TERMINE_FATTURA = "art. 21, comma 4, D.P.R. 633/1972"
NORMA_ANTICIPAZIONI = "art. 15, primo comma, n. 3, D.P.R. 633/1972"
NORMA_CU = "art. 13 D.P.R. 115/2002"
NORMA_ESENZIONE_CU = "art. 9, comma 1-bis, D.P.R. 115/2002"
NORMA_ANTICIPAZIONE_FORFETTARIA = "art. 30 D.P.R. 115/2002"
GIORNI_EMISSIONE_FATTURA = 12

_ETICHETTA_ESENZIONE = "contributo unificato / esenzione"
_ETICHETTA_VERSAMENTO = "contributo unificato / pagamento"


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
        return _riga("sentenza", "Importo liquidato in sentenza", importo=None, stato="Spese compensate", tono="neutral",
                     norma=NORMA_COMPENSAZIONE, fonti=fonti,
                     dettaglio=f"{della} compensa le spese: ciascuna parte sostiene le proprie, nulla da chiedere alla controparte.")
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


def riga_sentenza(crediti: list[Mapping[str, Any]], sentenze: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
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
    # Lo stesso importo letto da più documenti (la sentenza e la sua copia arrivata via PEC) è un credito solo:
    # non si somma, si mostrano le fonti e si chiede di verificarlo.
    gruppi: dict[float, list[Mapping[str, Any]]] = {}
    for credito in scelti:
        gruppi.setdefault(round(float(credito.get("importo") or 0), 2), []).append(credito)
    totale = round(sum(gruppi), 2) or None
    fonti = [f for c in scelti for f in c.get("fonti") or []]
    avvisi = []
    if any(len(g) > 1 for g in gruppi.values()):
        avvisi.append("Stesso importo in più documenti: contato una volta, verificare che sia la stessa sentenza.")
    if len(gruppi) > 1:
        avvisi.append("Importi diversi in più sentenze del fascicolo: verificare quale è definitiva prima di chiedere il pagamento.")
    if any(c.get("accessori") for c in scelti):
        avvisi.append(f"Oltre all'importo liquidato spettano gli accessori: rimborso forfettario del 15% ({NORMA_FORFETTARIO}), "
                      "contributo previdenziale e IVA, da indicare nella proforma.")
    if distratte and any(c.get("distrazione_condizionata") for c in distratte):
        avvisi.append("La sentenza distrae le spese «ove richiesto»: verificare che negli atti ci sia la dichiarazione di antistatarietà.")
    if distratte:
        return _riga("sentenza", "Importo liquidato in sentenza", importo=totale, stato="Distratte in favore dell'avvocato",
                     tono="primary", norma=NORMA_DISTRAZIONE, fonti=fonti,
                     dettaglio=" ".join(["Le paga la controparte direttamente al difensore antistatario."] + avvisi))
    return _riga("sentenza", "Importo liquidato in sentenza", importo=totale, stato="Spese liquidate al cliente",
                 tono="primary" if not avvisi else "warning", fonti=fonti,
                 dettaglio=" ".join(["Le paga la controparte al cliente."] + avvisi))


def _avviso_importo_contributo(voce: Mapping[str, Any]) -> str:
    """Perché l'importo del contributo non si può dare per certo: più importi letti o lettura da confermare.

    Nelle ricevute dei depositi compare spesso anche l'anticipazione forfettaria di € 27 (art. 30 D.P.R. 115/2002),
    che non è contributo unificato: indicarla come tale falserebbe il conto e le anticipazioni da recuperare.
    """
    letti = sorted({n for n in (_numero(v) for v in voce.get("importiLetti") or []) if n})
    if len(letti) > 1:
        testo = f"Importi letti nelle ricevute: {', '.join(_euro(n) for n in letti)}"
        if 27.0 in letti:
            testo += f"; {_euro(27.0)} è l'anticipazione forfettaria ({NORMA_ANTICIPAZIONE_FORFETTARIA}), non il contributo unificato"
        return testo + ": confermare sulla ricevuta l'importo del contributo."
    if voce.get("richiedeConferma"):
        return "Lettura della ricevuta da confermare: aprirla e verificare importo, data e procedimento."
    return ""


def riga_contributo(voce: Mapping[str, Any], documenti: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Contributo unificato: versato (ricevuta), esente (autocertificazione) o da verificare.

    Prevale ciò che l'avvocato ha confermato nel catalogo; una ricevuta solo proposta non vince su un'autocertificazione
    (una PEC di deposito classificata come «versamento» non prova il pagamento).
    """
    esenzioni = [d for d in documenti if _ETICHETTA_ESENZIONE in str(d.get("etichetta") or "").lower()]
    versamenti = [d for d in documenti if _ETICHETTA_VERSAMENTO in str(d.get("etichetta") or "").lower()]
    nome_voce = str(voce.get("documento_fonte") or "")
    if not esenzioni and any(p in nome_voce.lower() for p in ("autocertificazione", "esenzione")):
        esenzioni = [{"nome": nome_voce, "href": str(voce.get("href") or ""), "confermato": False}]
    if esenzioni and not any(d.get("confermato") for d in versamenti):
        versamenti = []
    importo = _numero(voce.get("importo"))
    if versamenti:
        fonti = [_fonte(d["nome"], d.get("href", ""), "ricevuta di versamento") for d in versamenti]
        da_confermare = _avviso_importo_contributo(voce)
        if da_confermare or not any(d.get("confermato") for d in versamenti):
            return _riga("contributo_unificato", "Contributo unificato", importo=None if da_confermare else importo,
                         stato="Versato, da confermare", tono="warning", norma=NORMA_CU, fonti=fonti,
                         dettaglio=da_confermare or "Ricevuta proposta dal catalogo e non ancora confermata: aprirla e "
                                                    "confermare importo e procedimento.")
        return _riga("contributo_unificato", "Contributo unificato", importo=importo, stato="Versato", tono="success",
                     norma=NORMA_CU, fonti=fonti, dettaglio="" if importo else "Importo da riportare dalla ricevuta.")
    if esenzioni:
        confermata = any(d.get("confermato") for d in esenzioni)
        return _riga("contributo_unificato", "Contributo unificato", importo=None,
                     stato="Esente" if confermata else "Esente, da confermare", tono="success" if confermata else "warning",
                     norma=NORMA_ESENZIONE_CU,
                     fonti=[_fonte(d["nome"], d.get("href", ""), "autocertificazione del reddito") for d in esenzioni],
                     dettaglio="Esenzione per reddito con autocertificazione depositata." if confermata else
                     "Aprire l'autocertificazione e confermarla (anno di reddito, soglia): il documento non è ancora confermato.")
    return _riga("contributo_unificato", "Contributo unificato", importo=importo, stato="Da verificare", tono="warning",
                 norma=NORMA_CU, dettaglio="Manca la ricevuta del versamento o l'autocertificazione di esenzione.")


def _documento(parcella: Mapping[str, Any]) -> str:
    return "fattura" if str(parcella.get("operativo") or "").upper() == "FATTURA" else "proforma"


def righe_parcella(parcelle: list[Mapping[str, Any]], voce_spese: Mapping[str, Any], voce_fondo: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Parcella, spese ed esborsi, anticipazioni: dai documenti economici del fascicolo."""
    attive = [p for p in parcelle if str(p.get("stato") or "").upper() != "ANNULLATA"]
    righe = []
    onorari = round(sum(float(p.get("onorari") or 0) for p in attive), 2) or None
    righe.append(_riga("parcella", "Parcella dell'avvocato", importo=onorari or _numero((attive[:1] or [{}])[0].get("totale")),
                       stato="Da preparare" if not attive else ("Fatturata" if any(_documento(p) == "fattura" for p in attive) else "Proforma"),
                       tono="warning" if not attive else "primary",
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
             dichiarato: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Sentenza → proforma → pagamento → fattura di pari importo → conferma, con il prossimo passo."""
    oggi = oggi or date.today()
    attive = [p for p in parcelle if str(p.get("stato") or "").upper() != "ANNULLATA"]
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
                                 + (" dalla lettura automatica" if segnato.get("automatico") else "") + ": non registrato negli incassi")
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
    elif incassato <= 0 and (dichiarato or {}).get("data"):
        prossimo = ("Il controllo economico segna un pagamento non registrato negli incassi: registrare l'incasso reale "
                    "(data e importo dell'accredito) prima di emettere la fattura.")
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
                    oggi: date | None = None, sentenze: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    righe = [riga_sentenza(crediti, sentenze), riga_contributo(voci.get("contributo_unificato") or {}, documenti_contributo)]
    righe += righe_parcella(parcelle, voci.get("spese_esborsi") or {}, voci.get("fondo_spese") or {})
    liquidazione = voci.get("liquidazione_giudice") or {}
    dichiarato = None
    if str(liquidazione.get("status") or "") == "pagato" and liquidazione.get("data_pagamento"):
        dichiarato = {"data": str(liquidazione["data_pagamento"])[:10],
                      "automatico": str(liquidazione.get("origine") or "").startswith("lex_ai")}
    risultato_percorso = percorso(parcelle, crediti, oggi=oggi, dichiarato=dichiarato)
    if sentenze and not crediti:
        risultato_percorso["passi"][0].update(fatto=True, dettaglio=righe[0]["stato"])
    return {"righe": righe, "percorso": risultato_percorso}


__all__ = ["conto_economico", "percorso", "riga_contributo", "riga_sentenza", "righe_parcella"]
