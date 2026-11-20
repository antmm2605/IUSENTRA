"""Il quadro del fascicolo: cinque righe che dicono all'avvocato a che punto è la pratica.

Modulo puro: compone le righe da dati già calcolati altrove (stato della pratica, prossimi passaggi della Lettura,
scadenze e udienze future, conto economico con lo stato unico del contributo unificato, obblighi di notifica
degli atti, conteggi di documenti e PEC). Non legge documenti e non decide nulla di nuovo: se un dato manca, la
riga lo dice («da verificare») invece di indovinarlo.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

SEZIONI = {
    "prossimo_passo": ("Prossimo passo", "sezione-andamento"),
    "termini": ("Termini", "sezione-termini"),
    "economia": ("Economia", "sezione-economia"),
    "notifiche": ("Notifiche", "sezione-comunicazioni"),
    "documenti": ("Documenti", "sezione-documenti"),
}
_LIVELLO_URGENZA = {0: "urgente", 1: "attenzione", 2: "info", 3: "info"}
_PARCELLA = {"Da preparare": "proforma da preparare", "Proforma": "proforma preparata", "Fatturata": "parcella fatturata"}
_STATI_NOTIFICA = {
    "notificato": "notificato",
    "scopo_raggiunto": "la controparte si è costituita: notifica a buon fine (art. 156, terzo comma, c.p.c.)",
    "facoltativo": "notifica facoltativa",
    "da_verificare": "notifica da verificare",
    "riscontro_storico": "riscontro storico della notifica ai fini del termine breve",
    "riscontro_storico_precedente": "ultimo riscontro storico del termine breve, aggiornamento automatico in corso",
}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def _data_it(iso: str) -> str:
    iso = _testo(iso)[:10]
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso) == 10 and iso[4] == "-" else ""


def _giorno(iso: str) -> date | None:
    try:
        return date.fromisoformat(_testo(iso)[:10])
    except ValueError:
        return None


def riga(tema: str, testo: str, livello: str) -> dict[str, str]:
    titolo, sezione = SEZIONI[tema]
    return {"tema": tema, "titolo": titolo, "testo": testo, "livello": livello, "sezione": sezione}


# Termini la cui inosservanza estingue il processo o fa decadere la parte: artt. 181, 307, 309 e 631 c.p.c. (mancata
# comparizione e inattività delle parti, anche nell'esecuzione), art. 127-ter c.p.c. (note scritte in sostituzione
# dell'udienza: il mancato deposito equivale alla mancata comparizione, quindi agli artt. 181 e 309 c.p.c.).
_RE_TERMINE_GRAVE = re.compile(
    r"\b(?:estinzion\w*|estint\w*|decadenz\w*|decad\w*|perentori\w*|127[- ]?ter|"
    r"art(?:t)?\.?\s*(?:\d+\s*(?:,|e)\s*)*(?:181|307|309|631)(?!\d|[- ]?(?:bis|ter|quater)))\b",
    re.IGNORECASE,
)


def termine_grave(passo: Mapping[str, Any]) -> bool:
    """Il passo ha un termine perentorio o richiama estinzione o decadenza (artt. 181, 307, 309, 631, 127-ter c.p.c.)."""
    if _testo(passo.get("natura")).lower() == "perentorio":
        return True
    testo = " ".join(_testo(passo.get(campo)) for campo in ("azione", "motivo", "norma", "prova"))
    return bool(_RE_TERMINE_GRAVE.search(testo))


def _data_entro(entro: str) -> date | None:
    entro = _testo(entro)
    if len(entro) == 10 and entro[2] == "/" and entro[5] == "/":
        try:
            return date(int(entro[6:]), int(entro[3:5]), int(entro[:2]))
        except ValueError:
            return None
    return _giorno(entro)


def livello_del_passo(passo: Mapping[str, Any], *, oggi: date | None = None) -> str:
    """Il livello del prossimo passo nel quadro, con la regola giuridica e non solo l'urgenza del passo.

    - un termine scaduto senza prova dell'adempimento è «urgente»;
    - un termine perentorio, o un passo che cita estinzione o decadenza, è almeno «attenzione», e «urgente» se
      scade entro 7 giorni;
    - gli altri passi seguono l'urgenza assegnata dalla Lettura.
    """
    try:
        urgenza = int(passo.get("urgenza"))
    except (TypeError, ValueError):
        urgenza = 2
    livello = _LIVELLO_URGENZA.get(urgenza, "info")
    if passo.get("scaduto"):
        return "urgente"
    if not termine_grave(passo):
        return livello
    giorno = _data_entro(_testo(passo.get("entro")))
    oggi = oggi or datetime.now(ZoneInfo("Europe/Rome")).date()
    if giorno is not None and (giorno - oggi).days <= 7:
        return "urgente"  # anche un termine già passato ma non segnato «scaduto»: si verifica subito
    return "urgente" if livello == "urgente" else "attenzione"


def riga_prossimo_passo(passi: list[Mapping[str, Any]] | None, *, ripiego: str = "",
                       motivo_stato: str = "", oggi: date | None = None) -> dict[str, str]:
    """Il primo dei prossimi passaggi della Lettura; senza Lettura pronta, il passo economico o una frase onesta."""
    if passi:
        passo = passi[0]
        entro = _testo(passo.get("entro"))
        testo = _testo(passo.get("azione")) + (f" ({'scaduto il' if passo.get('scaduto') else 'entro il'} {entro})" if entro else "")
        norma = _testo(passo.get("norma"))
        if norma:
            testo += f" · {norma}"
        return riga("prossimo_passo", testo, livello_del_passo(passo, oggi=oggi))
    if passi is not None:
        if motivo_stato:
            return riga("prossimo_passo", motivo_stato, "info")
        return riga("prossimo_passo", "Nessun adempimento aperto risulta dalla Lettura del fascicolo.", "ok")
    if ripiego:
        return riga("prossimo_passo", ripiego, "info")
    return riga("prossimo_passo", "Da verificare: la Lettura del fascicolo non è ancora pronta; si aggiorna in sfondo.", "info")


def riga_termini(termini: Iterable[Mapping[str, Any]], *, oggi: date) -> dict[str, str]:
    """La scadenza o l'udienza futura più vicina; scadenze passate e chiuse non entrano nel quadro."""
    futuri = sorted(((g, t) for t in termini if (g := _giorno(t.get("data"))) and g >= oggi),
                    key=lambda voce: (voce[0], _testo(voce[1].get("titolo"))))
    if not futuri:
        return riga("termini", "Nessuna scadenza o udienza futura aperta nel fascicolo.", "ok")
    giorno, primo = futuri[0]
    tipo = "Udienza" if _testo(primo.get("tipo")) == "udienza" else "Scadenza"
    titolo = _testo(primo.get("titolo"))
    testo = f"{tipo} del {giorno.strftime('%d/%m/%Y')}" + (f": {titolo}" if titolo else "")
    if len(futuri) > 1:
        testo += f" · altri {len(futuri) - 1} termini aperti"
    distanza = (giorno - oggi).days
    return riga("termini", testo, "urgente" if distanza <= 7 else "attenzione" if distanza <= 30 else "info")


def riga_economia(contributo: Mapping[str, Any] | None, righe_conto: Iterable[Mapping[str, Any]],
                  prossimo_economico: str = "") -> dict[str, str]:
    """Contributo unificato (stato unico), importo liquidato in sentenza e documento economico, dal conto economico."""
    per_voce = {_testo(r.get("voce")): r for r in righe_conto}
    parti: list[str] = []
    attenzione = False
    if contributo:
        norma = _testo(contributo.get("norma"))
        importo = _testo(contributo.get("importoLabel"))
        parti.append(f"Contributo unificato: {contributo.get('etichetta')}" + (f" {importo}" if importo else "")
                     + (f" ({norma})" if norma and contributo.get("categoria") == "esente" else ""))
        attenzione = attenzione or contributo.get("tono") == "warning"
    else:
        parti.append("Contributo unificato: da verificare")
        attenzione = True
    sentenza = per_voce.get("sentenza") or {}
    spese_da_verificare = sentenza.get("tono") == "warning" and not sentenza.get("importo")
    attenzione = attenzione or spese_da_verificare
    if sentenza.get("importo"):
        parti.append(f"liquidate in sentenza {sentenza.get('importoLabel')}, {_testo(sentenza.get('stato')).lower()}")
    elif sentenza and _testo(sentenza.get("stato")) not in {"", "Nessuna sentenza con spese liquidate"}:
        parti.append(_testo(sentenza.get("stato")).lower())
    parcella = per_voce.get("parcella") or {}
    stato_parcella = _testo(parcella.get("stato"))
    spese_compensate = sentenza.get("stato") == "Spese compensate"
    if stato_parcella and not ((spese_da_verificare or spese_compensate) and stato_parcella == "Da preparare"):
        attenzione = attenzione or (stato_parcella == "Da preparare" and bool(sentenza.get("importo")))
        if not (stato_parcella == "Da preparare" and prossimo_economico and attenzione):
            parti.append(_PARCELLA.get(stato_parcella, f"parcella: {stato_parcella.lower()}"))
    testo = " · ".join(p for p in parti if p)
    if prossimo_economico and attenzione:
        testo += f". {prossimo_economico}"
    return riga("economia", testo, "attenzione" if attenzione else "ok")


def riga_notifiche(obblighi: list[Mapping[str, Any]] | None, *, oggi: date) -> dict[str, str]:
    """Gli obblighi di notifica degli atti già calcolati: «Ricorso: notificato · Sentenza: notifica facoltativa»."""
    if obblighi is None:
        return riga("notifiche", "Obblighi di notifica da calcolare: si aggiornano alla prossima lettura del fascicolo.", "info")
    if not obblighi:
        return riga("notifiche", "Nessun obbligo di notifica risulta dagli atti catalogati.", "ok")
    parti: list[str] = []
    livello = "ok"
    for obbligo in obblighi:
        stato = _testo(obbligo.get("stato"))
        if stato == "da_notificare":
            scadenza = _giorno(obbligo.get("scadenza"))
            ordinatorio_decorso = bool(scadenza and scadenza < oggi and obbligo.get("natura") == "ordinatorio")
            if ordinatorio_decorso:
                descrizione = f"Termine ordinatorio decorso il {scadenza:%d/%m/%Y}. Verificare invio e ricevute PEC."
                if obbligo.get("termine_da_verificare"):
                    descrizione += " Termine a difesa da verificare."
            elif scadenza and scadenza < oggi:
                descrizione = f"Data indicata {scadenza:%d/%m/%Y} già trascorsa. Verificare invio e ricevute PEC."
            else:
                descrizione = f"da notificare entro il {scadenza:%d/%m/%Y}" if scadenza else "da notificare"
            if scadenza and (scadenza - oggi).days <= 7 and not ordinatorio_decorso:
                livello = "urgente"
            elif livello != "urgente":
                livello = "attenzione"
        else:
            descrizione = _STATI_NOTIFICA.get(stato, stato.replace("_", " ") or "da verificare")
            if stato == "da_verificare" and livello in {"ok", "info"}:
                livello = "attenzione"
            elif stato == "riscontro_storico_precedente" and livello == "ok":
                livello = "info"
        parti.append(f"{_testo(obbligo.get('atto'))}: {descrizione}")
    return riga("notifiche", " · ".join(parti), livello)


# Le conclusioni del modello della causa sulle notifiche dovute (pct/ragionamento): l'atto che si notifica.
_ATTI_NOTIFICA_MODELLO = {
    "notifica_ricorso_decreto_415": "Ricorso e decreto di fissazione dell'udienza (art. 415 c.p.c.)",
    "notifica_decreto_ingiuntivo": "Ricorso e decreto ingiuntivo (art. 644 c.p.c.)",
    "notifica_ordinata": "Notifica ordinata dal giudice",
    "notifica_sentenza": "Sentenza",
    "esecuzione_pa": "Titolo esecutivo alla pubblica amministrazione (art. 14 D.L. 669/1996)",
}


def obblighi_dal_modello(conclusioni: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Gli obblighi di notifica come li conclude il modello della causa, nella forma della sintesi del quadro.

    Fatto (con la prova) → notificato; da fare → da notificare entro la scadenza calcolata; dubbio → da verificare;
    la notifica della sentenza senza termine è una scelta difensiva (facoltativa). None se il modello non c'è.
    """
    if conclusioni is None:
        return None
    obblighi: list[dict[str, Any]] = []
    for voce in conclusioni:
        codice = _testo(voce.get("codice"))
        atto = _ATTI_NOTIFICA_MODELLO.get(codice)
        stato = _testo(voce.get("stato"))
        if not atto or stato == "non_dovuto" or voce.get("onerato_codice") in {"controparte", "terzo"}:
            continue
        termine = voce.get("termine") or {}
        if stato == "fatto":
            obblighi.append({"atto": atto, "stato": _stato_fatto(voce)})
        elif stato == "da_fare" and codice == "notifica_sentenza" and not termine:
            obblighi.append({"atto": atto, "stato": "facoltativo"})
        elif stato == "da_fare":
            obblighi.append({"atto": atto, "stato": "da_notificare", "scadenza": _testo(termine.get("scadenza_iso")),
                             **({"natura": "ordinatorio"} if termine.get("natura") == "ordinatorio" else {})})
        else:
            obblighi.append({"atto": atto, "stato": "da_verificare"})
    return obblighi


def _stato_fatto(conclusione: Mapping[str, Any]) -> str:
    """«Notificato», o «scopo raggiunto» quando la prova è la costituzione della controparte (art. 156 c.p.c.)."""
    sanata = any("art. 156" in _testo(n.get("norma")) for n in conclusione.get("norme") or [] if isinstance(n, Mapping))
    return "scopo_raggiunto" if sanata or "si è costituita" in _testo(conclusione.get("prova_o_motivo")) else "notificato"


def codice_modello(conclusione: Mapping[str, Any]) -> str:
    """Il codice del modello, con l'ordine di notifica del giudice ricondotto all'atto che riguarda."""
    codice = _testo(conclusione.get("codice"))
    if codice == "notifica_ordinata":
        cosa = _testo(conclusione.get("cosa")).casefold()
        if "decreto ingiuntivo" in cosa:
            return "notifica_decreto_ingiuntivo"
        if "ricorso" in cosa and "decreto" in cosa:
            return "notifica_ricorso_decreto_415"
    return codice


_CODICE_DI_REGOLA = {"lavoro_415": "notifica_ricorso_decreto_415", "decreto_ingiuntivo_644": "notifica_decreto_ingiuntivo",
                     "sentenza_notifica_breve": "notifica_sentenza"}


def codice_obbligo(obbligo: Mapping[str, Any]) -> str:
    """A quale conclusione del modello corrisponde un obbligo del calcolo per atto (pct/obblighi_notifica_atto)."""
    regola = _testo(obbligo.get("regola"))
    if regola in _CODICE_DI_REGOLA:
        return _CODICE_DI_REGOLA[regola]
    atto = _testo(obbligo.get("atto") or obbligo.get("etichetta")).casefold()
    if "decreto ingiuntivo" in atto:
        return "notifica_decreto_ingiuntivo"
    if "415" in atto or "fissazione" in atto:
        return "notifica_ricorso_decreto_415"
    if atto.startswith("sentenza"):
        return "notifica_sentenza"
    return ""


def allinea_al_modello(obblighi: Iterable[Mapping[str, Any]], conclusioni: Iterable[Mapping[str, Any]] | None, *,
                       pannello: bool = False) -> list[dict[str, Any]]:
    """Una sola verità per atto: dove il modello della causa conclude sulla notifica, vale la sua conclusione.

    Il calcolo per atto (`pct/obblighi_notifica_atto`) resta la fonte degli atti che il modello non tratta; per gli
    altri lo stato è quello del modello (fatto, da fare, dubbio; «non dovuto» toglie la voce), con il suo motivo. I
    riscontri storici già marcati restano: coincidono con il «non dovuto» del modello. Senza modello nulla cambia.
    """
    obblighi = [dict(o) for o in obblighi]
    if conclusioni is None:
        return obblighi
    nostre = [c for c in conclusioni if _testo(c.get("codice")) in _ATTI_NOTIFICA_MODELLO
              and c.get("onerato_codice") not in {"controparte", "terzo"}]
    per_codice: dict[str, list[Mapping[str, Any]]] = {}
    for conclusione in nostre:
        per_codice.setdefault(codice_modello(conclusione), []).append(conclusione)
    usati: set[str] = set()
    esito: list[dict[str, Any]] = []
    for obbligo in obblighi:
        codice = codice_obbligo(obbligo)
        if not codice or codice not in per_codice or _testo(obbligo.get("stato")).startswith("riscontro_storico"):
            esito.append(obbligo)
            continue
        candidate = per_codice[codice]
        if codice == "notifica_sentenza":
            # La notifica della sentenza è per documento: vale la conclusione sulla stessa sentenza (o sua copia).
            documenti = {_testo(obbligo.get("documentoId")), *map(_testo, obbligo.get("documenti") or ()),
                         *(_testo(f.get("documentoId")) for f in obbligo.get("fonti_documentali") or () if isinstance(f, Mapping))} - {""}
            candidate = [c for c in candidate if _testo((c.get("letto") or {}).get("documento_id")) in documenti]
            if not candidate:
                esito.append(obbligo)
                continue
        usati.add(codice)
        aperte = [c for c in candidate if _testo(c.get("stato")) != "non_dovuto"]
        if not aperte:
            continue
        for voce in obblighi_dal_modello(aperte) or []:
            if pannello and voce["stato"] == "scopo_raggiunto":
                voce["stato"] = "notificato"
            esito.append({**obbligo, **voce, "atto": _testo(obbligo.get("atto")) or voce["atto"],
                          "motivo_modello": _testo(aperte[0].get("prova_o_motivo"))})
            break
    if not pannello:
        # Un ordine di notifica del giudice che il modello non ha ricondotto a un atto può essere la stessa voce che il
        # calcolo per atto descrive con un'altra etichetta: si aggiunge solo se il calcolo non ha voci senza codice.
        senza_codice = any(not codice_obbligo(o) for o in obblighi)
        esito += obblighi_dal_modello([c for codice, voci in per_codice.items() if codice not in usati
                                       and not (senza_codice and codice == "notifica_ordinata") for c in voci]) or []
    return esito


def riga_documenti(totale: int, da_classificare: int | None, pec: Mapping[str, Any]) -> dict[str, str]:
    parti = [f"{totale} document{'o' if totale == 1 else 'i'}"]
    if da_classificare is None:
        parti.append("classificazione da verificare")
    elif da_classificare:
        parti.append(f"{da_classificare} da classificare")
    else:
        parti.append("tutti classificati")
    da_confermare = int(pec.get("da_confermare") or 0)
    if da_confermare:
        parti.append(f"{da_confermare} PEC da confermare")
    collegate = int(pec.get("collegate") or 0)
    if collegate:
        parti.append(f"{collegate} PEC collegat{'a' if collegate == 1 else 'e'} dalla casella")
    livello = "attenzione" if da_confermare or da_classificare else "ok"
    return riga("documenti", " · ".join(parti), livello)


__all__ = ["SEZIONI", "allinea_al_modello", "codice_modello", "codice_obbligo", "livello_del_passo", "obblighi_dal_modello", "riga", "riga_documenti", "riga_economia", "riga_notifiche", "riga_prossimo_passo", "riga_termini", "termine_grave"]
