"""La Lettura come vista del modello del ragionamento: conclusioni, prossimi passi, contraddizioni e dubbi.

Il modello (`pct/ragionamento`) decide; qui si mette in forma: date in gg/mm/aaaa, norme con URL, una riga per
conclusione con cosa si è letto, cosa fare, come, perché, stato e se siamo nei termini. I passi giuridici
(termini, note scritte, notifiche dovute, dopo la sentenza, monitorio, spese liquidate, contributo) vengono solo
da qui: i vecchi calcoli paralleli della Lettura non li ripetono.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ._testo import data_it
from .modello import Passo

HREF = {
    "note_127ter": "#udienze", "deposito_ordinato": "#udienze", "termine_assegnato": "#udienze",
    "notifica_ordinata": "#comunicazioni-notifica", "notifica_ricorso_decreto_415": "#comunicazioni-notifica",
    "notifica_sentenza": "#comunicazioni-notifica", "notifica_decreto_ingiuntivo": "#comunicazioni-notifica",
    "esecuzione_pa": "#comunicazioni-notifica",
    "spese_liquidate": "#economia", "contributo_unificato": "#economia",
}
STATI = {"fatto": "già fatto", "da_fare": "da fare", "non_dovuto": "non dovuto", "dubbio": "da chiarire"}
ONERATI = {"noi": "lo studio", "tutte_le_parti": "tutte le parti (anche lo studio)", "controparte": "la controparte",
           "ignoto": "parte non determinata", "terzo": "un terzo"}


def _termine(termine: dict[str, Any] | None) -> dict[str, Any] | None:
    if not termine:
        return None
    residui = termine.get("giorni_residui")
    if termine.get("natura") and termine.get("scaduto"):
        situazione = "data raggiunta"
    elif termine.get("scaduto"):
        situazione = f"scaduto da {abs(residui)} giorni" if residui is not None else "scaduto"
    elif residui is not None:
        situazione = "scade oggi" if residui == 0 else f"mancano {residui} giorni"
    else:
        situazione = "scadenza non calcolabile"
    return {
        "scadenza_iso": termine.get("scadenza") or "",
        "ora_assegnata": termine.get("ora_assegnata") or "",
        "scadenza": data_it(termine.get("scadenza")), "decorrenza": data_it(termine.get("decorrenza")),
        "evento_decorrenza": termine.get("evento_decorrenza") or "", "computo": termine.get("computo") or "",
        "sospensione_feriale": termine.get("sospensione_feriale") or "",
        "natura": termine.get("natura") or {True: "perentorio", False: "ordinatorio"}.get(termine.get("perentorio"), "non qualificato"),
        "giorni_residui": residui, "scaduto": bool(termine.get("scaduto")), "situazione": situazione,
        "conseguenze": termine.get("conseguenze") or "", "rimedi": termine.get("rimedi") or "",
    }


def _notifica_facoltativa(voce: dict[str, Any]) -> bool:
    return (voce["codice"] == "notifica_sentenza" and voce["stato"] == "da_fare"
            and not voce.get("termine") and not voce.get("dubbi"))


def _azione(voce: dict[str, Any]) -> str:
    if _notifica_facoltativa(voce):
        return "Valutare se notificare la sentenza per far decorrere il termine breve"
    return voce["cosa"]


def _conclusione(voce: dict[str, Any]) -> dict[str, Any]:
    letto = voce.get("letto") or {}
    termine = _termine(voce.get("termine"))
    stato_etichetta = STATI.get(voce["stato"], voce["stato"])
    perche = voce["perche"]
    if _notifica_facoltativa(voce):
        stato_etichetta = "Scelta difensiva"
    if voce["codice"] == "notifica_sentenza" and voce["stato"] == "non_dovuto":
        stato_etichetta = "Riscontro storico"
    if voce["codice"] == "termine_impugnazione" and termine and voce["stato"] == "non_dovuto":
        stato_etichetta = "Termine decorso" if termine["scaduto"] else "Termine per chi intende impugnare"
        perche = "La scadenza indica il limite per impugnare. Prima di attestare il giudicato, verificare a registro le impugnazioni."
        termine["conseguenze"] = "Il decorso del termine senza impugnazione rileva ai fini del giudicato (art. 324 c.p.c.)."
    return {
        "codice": voce["codice"], "cosa": _azione(voce), "come": voce["come"], "perche": perche,
        "stato": voce["stato"], "stato_etichetta": stato_etichetta, "prova_o_motivo": voce.get("prova_o_motivo") or "",
        "onerato_codice": voce.get("onerato") or "",
        "onerato": ONERATI.get(voce.get("onerato") or "", voce.get("onerato") or ""),
        "letto": {"documento_id": letto.get("oggetto_id", ""), "documento": letto.get("nome", ""), "brano": letto.get("brano", ""),
                  "tipo": letto.get("tipo", ""),
                  "data": data_it(letto.get("data"))},
        "norme": [{"norma": n.get("norma"), "titolo": n.get("titolo"), "url": n.get("url"), "estratto": n.get("estratto"),
                   "verifica": n.get("verifica")} for n in voce.get("norme") or []],
        "termine": termine, "template": voce.get("template") or "",
        "motivo_senza_termine": voce.get("motivo_senza_termine") or "", "guida": voce.get("guida") or "",
        "dubbi": [{"codice": d.get("codice", ""), "testo": d["testo"], "manca": d["manca"]} for d in voce.get("dubbi") or []],
    }


def vista(causa: dict[str, Any]) -> dict[str, Any]:
    """La sezione «ragionamento» della Lettura."""
    if not causa:
        return {}
    conclusioni = [_conclusione(c) for c in causa.get("conclusioni") or []]
    ordine = {"da_fare": 0, "dubbio": 1, "fatto": 2, "non_dovuto": 3}
    conclusioni.sort(key=lambda c: (ordine.get(c["stato"], 9), (c["termine"] or {}).get("giorni_residui") is None,
                                    (c["termine"] or {}).get("giorni_residui") or 0))
    rito = causa.get("rito") or {}
    return {
        "versione": causa.get("versione", ""), "impronta": causa.get("impronta", ""),
        "rito": {"codice": rito.get("codice"), "etichetta": rito.get("etichetta"), "fonte": rito.get("fonte")},
        "posizione": {"attiva": "il cliente agisce (attore, ricorrente, creditore)", "passiva": "il cliente resiste (convenuto, resistente)",
                      "ignota": "posizione del cliente non determinata"}.get(causa.get("ruolo_cliente") or "", ""),
        "fase": causa.get("fase") or {},
        "percorso": causa.get("percorso") or [],
        "stile_ricorsi": causa.get("stile_ricorsi") or [],
        "udienze": [{"data": data_it(u["data"]), "ora": u.get("ora") or "",
                     "modalita": {"note_scritte": "sostituita da note scritte (art. 127-ter c.p.c.)", "remota": "da remoto (art. 127-bis c.p.c.)",
                                  "presenza": "in presenza"}.get(u.get("modalita"), u.get("modalita")),
                     "documento": (u.get("fonte") or {}).get("nome", ""),
                     "documento_id": (u.get("fonte") or {}).get("oggetto_id", "")} for u in causa.get("udienze") or []],
        "economia": {"contributo_unificato": (causa.get("economia") or {}).get("contributo_unificato")},
        "conclusioni": conclusioni,
        "contraddizioni": [{"controllo": x["controllo"], "descrizione": x["descrizione"], "sciolta": x["sciolta"], "come": x["come"]}
                           for x in causa.get("contraddizioni") or []],
        "dubbi": [{"codice": d.get("codice", ""), "testo": d["testo"], "manca": d["manca"], "fonte": d.get("fonte")}
                  for d in causa.get("dubbi") or []],
    }


_PASSI_TRATTAZIONE = frozenset({"note_127ter", "costituzione_convenuto", "costituzione_attore"})


def passi(causa: dict[str, Any], *, trattazione_conclusa: bool = False, provvedimenti_consegnati: frozenset[str] = frozenset()) -> list[Passo]:
    """I prossimi passi giuridici: esclude gli adempimenti di trattazione dopo il provvedimento conclusivo."""

    esito: list[Passo] = []
    for voce in causa.get("conclusioni") or []:
        if voce["stato"] not in {"da_fare", "dubbio"} or voce.get("onerato") in {"controparte", "terzo"}:
            continue
        if (voce["codice"] == "notifica_ordinata"
                and (voce.get("letto") or {}).get("oggetto_id") in provvedimenti_consegnati):
            continue  # Il presidio espone il riscontro della stessa notifica, con le fonti PEC.
        if trattazione_conclusa and voce["codice"] in _PASSI_TRATTAZIONE:
            # La conclusione resta consultabile nei Riscontri, come dato storico da verificare.
            continue
        termine = voce.get("termine") or {}
        residui = termine.get("giorni_residui")
        pubblicazione_incerta = any(d.get("codice") == "pubblicazione_da_verificare" for d in voce.get("dubbi") or [])
        ravvicinato = residui is not None and residui <= 15
        urgenza = 0 if termine.get("scaduto") else 1 if ravvicinato or pubblicazione_incerta else 2
        motivo = voce["perche"] + (f" — {voce['come']}" if voce.get("come") else "")
        if voce["stato"] == "dubbio":
            motivo = "; ".join(d["testo"] for d in voce.get("dubbi") or []) or motivo
        azione = _azione(voce)
        href = HREF.get(voce["codice"], "#udienze")
        prova_pec = next((d.get("fonte") for d in voce.get("dubbi") or []
                          if d.get("codice") == "validita_notifica_ordinata"), None)
        if any(d.get("codice") == "note_in_attesa_cancelleria" for d in voce.get("dubbi") or []):
            azione = "Verificare l’esito finale del deposito delle note scritte"
        elif prova_pec:
            azione = "Controllare la validità della notifica PEC già consegnata"
            fid, oid = str(causa.get("fascicolo_id") or ""), str(prova_pec.get("oggetto_id") or "")
            if fid and oid:
                href = f"/fascicoli/{quote(fid, safe='')}/documenti/{quote(oid, safe='')}/visualizza"
        elif any(d.get("codice") == "notifica_ordinata_da_correlare" for d in voce.get("dubbi") or []):
            azione = "Verificare la prova della notifica ordinata dal giudice"
        elif any(d.get("codice") == "note_depositate_da_correlare" for d in voce.get("dubbi") or []):
            azione = "Verificare se le note già depositate riguardano questa udienza"
        elif voce.get("onerato") == "ignoto":
            azione = "Verificare se il termine riguarda il cliente: " + azione
        esito.append(Passo(
            urgenza, azione, motivo, data_it(termine.get("scadenza")), "ragionamento sul fascicolo",
            tuple(n["id"] for n in voce.get("norme") or [] if n.get("id")), href,
        ))
    prossima = next((u for u in sorted(causa.get("udienze") or [], key=lambda u: u["data"]) if u["data"] >= (causa.get("oggi") or "")), None)
    if prossima and prossima.get("modalita") != "note_scritte":
        esito.append(Passo(2, f"Preparare l'udienza del {data_it(prossima['data'])}" + (f" ore {prossima['ora']}" if prossima.get("ora") else "")
                           + (" (in presenza)" if prossima.get("modalita") == "presenza" else " (da remoto)"),
                           f"fissata con «{(prossima.get('fonte') or {}).get('nome', '')}»", data_it(prossima["data"]),
                           "ragionamento sul fascicolo", (), "#udienze"))
    return esito


__all__ = ["passi", "vista"]
