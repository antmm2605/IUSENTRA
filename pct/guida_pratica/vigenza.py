"""Scelta delle norme della Guida pratica in base alla data dell'atto da compiere.

Una voce di ``normativa`` o di ``termini_processuali`` può dichiarare la propria vigenza con ``vigente_dal`` e/o
``vigente_fino_al`` (date ISO); una voce abrogata porta ``abrogata_da`` con l'atto abrogante. Alla data di riferimento restano solo le voci in vigore quel giorno; le altre si
spostano in ``vigenza_applicata`` con il motivo. Base: art. 11 disp. prel. c.c. (la legge non dispone che per
l'avvenire) e le norme di decorrenza delle singole leggi, dichiarate nella scheda (es. art. 131 D.Lgs. 175/2024).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")
SEZIONI_CON_VIGENZA = ("normativa", "termini_processuali")


def _data(valore: Any) -> date | None:
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    testo = str(valore or "").strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    return None


def _italiana(giorno: date) -> str:
    return giorno.strftime("%d/%m/%Y")


def data_di_riferimento(fascicolo: dict[str, Any] | None, oggi: date | None = None) -> tuple[date, str]:
    """La data dell'atto da compiere indicata nel fascicolo, altrimenti oggi (Europe/Rome)."""
    fascicolo = fascicolo or {}
    for chiave, motivo in (("data_atto_da_compiere", "data dell'atto da compiere indicata nel fascicolo"),
                           ("dataAttoDaCompiere", "data dell'atto da compiere indicata nel fascicolo")):
        giorno = _data(fascicolo.get(chiave))
        if giorno:
            return giorno, motivo
    return (oggi or datetime.now(ROME_TZ).date()), "data di oggi"


def in_vigore(voce: dict[str, Any], giorno: date) -> bool:
    dal = _data(voce.get("vigente_dal"))
    fino = _data(voce.get("vigente_fino_al"))
    if voce.get("abrogata_da") and fino is None:
        return False  # abrogata senza data certa: vale solo per i procedimenti anteriori, non per gli atti di oggi
    return (dal is None or giorno >= dal) and (fino is None or giorno <= fino)


def applica_vigenza(guida: dict[str, Any], fascicolo: dict[str, Any] | None = None, *, oggi: date | None = None) -> dict[str, Any]:
    """Tiene nella guida solo norme e termini in vigore alla data di riferimento e spiega la scelta."""
    voci_con_vigenza = [voce for sezione in SEZIONI_CON_VIGENZA for voce in guida.get(sezione) or []
                        if isinstance(voce, dict) and (voce.get("vigente_dal") or voce.get("vigente_fino_al") or voce.get("abrogata_da"))]
    if not voci_con_vigenza:
        return guida
    giorno, criterio = data_di_riferimento(fascicolo, oggi)
    escluse: list[dict[str, Any]] = []
    for sezione in SEZIONI_CON_VIGENZA:
        voci = guida.get(sezione)
        if not isinstance(voci, list):
            continue
        tenute = []
        for voce in voci:
            if not isinstance(voce, dict) or in_vigore(voce, giorno):
                tenute.append(voce)
            else:
                escluse.append({"sezione": sezione, "voce": voce})
        guida[sezione] = tenute
    inizi = [_data(e["voce"].get("vigente_dal")) for e in escluse]
    future = sorted({inizio for inizio in inizi if inizio is not None and inizio > giorno})
    messaggio = f"Norme e termini scelti per la {criterio}: {_italiana(giorno)}."
    if future:
        cambio = future[0]
        cambiano = [e for e in escluse if _data(e["voce"].get("vigente_dal")) == cambio]
        nuove = sorted({str(e["voce"].get("fonte")) for e in cambiano if e["sezione"] == "normativa" and e["voce"].get("fonte")})
        nuove = nuove or sorted({str(e["voce"].get("norma")) for e in cambiano if e["voce"].get("norma")})
        messaggio += f" Dal {_italiana(cambio)} cambia la disciplina" + (f" ({', '.join(nuove)})" if nuove else "") + ": per un atto da compiere da quella data la guida mostrerà le nuove norme."
    abrogate = [e["voce"] for e in escluse if e["voce"].get("abrogata_da")]
    if abrogate:
        elenco = "; ".join(f"art. {v.get('articolo')} {v.get('fonte')} (abrogato da {v.get('abrogata_da')})" for v in abrogate[:6])
        messaggio += f" Non mostrate perché abrogate: {elenco}" + (" e altre" if len(abrogate) > 6 else "") + "; valgono solo per i procedimenti anteriori all'abrogazione."
    guida["vigenza_applicata"] = {"data": giorno.isoformat(), "criterio": criterio, "messaggio": messaggio, "escluse": escluse,
                                  "prossimo_cambio": future[0].isoformat() if future else ""}
    avvertenze = [a for a in guida.get("avvertenze_redazionali") or [] if a != messaggio]
    guida["avvertenze_redazionali"] = [messaggio, *avvertenze]
    return guida

