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
            obblighi.append({"atto": atto, "stato": "notificato"})
        elif stato == "da_fare" and codice == "notifica_sentenza" and not termine:
            obblighi.append({"atto": atto, "stato": "facoltativo"})
        elif stato == "da_fare":
            obblighi.append({"atto": atto, "stato": "da_notificare", "scadenza": _testo(termine.get("scadenza_iso")),
                             **({"natura": "ordinatorio"} if termine.get("natura") == "ordinatorio" else {})})
        else:
            obblighi.append({"atto": atto, "stato": "da_verificare"})
    return obblighi


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


__all__ = ["SEZIONI", "livello_del_passo", "obblighi_dal_modello", "riga", "riga_documenti", "riga_economia", "riga_notifiche", "riga_prossimo_passo", "riga_termini", "termine_grave"]
