"""Il quadro del fascicolo: cinque righe che dicono all'avvocato a che punto è la pratica.

Modulo puro: compone le righe da dati già calcolati altrove (stato della pratica, prossimi passaggi della Lettura,
scadenze e udienze future, conto economico con lo stato unico del contributo unificato, obblighi di notifica
degli atti, conteggi di documenti e PEC). Non legge documenti e non decide nulla di nuovo: se un dato manca, la
riga lo dice («da verificare») invece di indovinarlo.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

SEZIONI = {
    "prossimo_passo": ("Prossimo passo", "sezione-andamento"),
    "termini": ("Termini", "sezione-termini"),
    "economia": ("Economia", "sezione-economia"),
    "notifiche": ("Notifiche", "sezione-comunicazioni"),
    "documenti": ("Documenti", "sezione-documenti"),
}
_LIVELLO_URGENZA = {0: "urgente", 1: "attenzione", 2: "info", 3: "info"}
_PARCELLA = {"Da preparare": "proforma da preparare", "Proforma": "proforma preparata", "Fatturata": "parcella fatturata"}
_STATI_NOTIFICA = {"notificato": "notificato", "facoltativo": "notifica facoltativa", "da_verificare": "notifica da verificare"}


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


def riga_prossimo_passo(passi: list[Mapping[str, Any]] | None, *, ripiego: str = "") -> dict[str, str]:
    """Il primo dei prossimi passaggi della Lettura; senza Lettura pronta, il passo economico o una frase onesta."""
    if passi:
        passo = passi[0]
        entro = _testo(passo.get("entro"))
        testo = _testo(passo.get("azione")) + (f" (entro {entro})" if entro else "")
        try:
            urgenza = int(passo.get("urgenza"))
        except (TypeError, ValueError):
            urgenza = 2
        return riga("prossimo_passo", testo, "urgente" if passo.get("scaduto") else _LIVELLO_URGENZA.get(urgenza, "info"))
    if passi is not None:
        return riga("prossimo_passo", "Nessun adempimento aperto risulta dalla Lettura del fascicolo.", "ok")
    if ripiego:
        return riga("prossimo_passo", ripiego, "info")
    return riga("prossimo_passo", "Da verificare: la Lettura del fascicolo non è ancora pronta; si aggiorna in sfondo.", "info")


def riga_termini(termini: Iterable[Mapping[str, Any]], *, oggi: date) -> dict[str, str]:
    """La scadenza o l'udienza futura più vicina; scadenze passate e chiuse non entrano nel quadro."""
    futuri = sorted((g, t) for t in termini if (g := _giorno(t.get("data"))) and g >= oggi)
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
    if sentenza.get("importo"):
        parti.append(f"liquidate in sentenza {sentenza.get('importoLabel')}, {_testo(sentenza.get('stato')).lower()}")
    elif sentenza and _testo(sentenza.get("stato")) not in {"", "Nessuna sentenza con spese liquidate"}:
        parti.append(_testo(sentenza.get("stato")).lower())
    parcella = per_voce.get("parcella") or {}
    if parcella:
        stato_parcella = _testo(parcella.get("stato"))
        parti.append(_PARCELLA.get(stato_parcella, f"parcella: {stato_parcella.lower()}"))
        attenzione = attenzione or (stato_parcella == "Da preparare" and bool(sentenza.get("importo")))
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
            descrizione = f"da notificare entro il {scadenza.strftime('%d/%m/%Y')}" if scadenza else "da notificare"
            livello = "urgente" if scadenza and (scadenza - oggi).days <= 7 else "attenzione"
        else:
            descrizione = _STATI_NOTIFICA.get(stato, stato.replace("_", " ") or "da verificare")
            if stato == "da_verificare" and livello == "ok":
                livello = "attenzione"
        parti.append(f"{_testo(obbligo.get('atto'))}: {descrizione}")
    return riga("notifiche", " · ".join(parti), livello)


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
    parti.append(f"{collegate} PEC collegat{'a' if collegate == 1 else 'e'}")
    livello = "attenzione" if da_confermare or da_classificare else "ok"
    return riga("documenti", " · ".join(parti), livello)


__all__ = ["SEZIONI", "riga", "riga_documenti", "riga_economia", "riga_notifiche", "riga_prossimo_passo", "riga_termini"]
