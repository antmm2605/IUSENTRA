"""Il quadro del fascicolo (``GET /api/v1/ui/fascicoli/<id>/quadro``): raccolta dei dati già materializzati.

Fonti, tutte già calcolate e mai riletture di documenti (regola «Registro delle letture»):
- stato della pratica: il record del fascicolo (``pct/fascicolo_stato_pratica.py``), lo stesso della Lettura;
- prossimo passo: la Lettura già salvata per il profilo corrente;
- termini: scadenziario (scadenze aperte del fascicolo) e udienze in attesa del fascicolo, solo future;
- economia: il conto economico, con lo stato unico del contributo unificato;
- notifiche: la sintesi degli obblighi di notifica salvata dal giro in sfondo (``obblighi_notifica_sintesi``);
- documenti e PEC: documenti del fascicolo, voci del catalogo, PEC collegate e collegamenti da confermare.
Ogni fonte che manca diventa una frase onesta («da verificare»): il quadro non risponde mai con un errore 500.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _sicuro(funzione: Callable[[], Any], ripiego: Any, cosa: str) -> Any:
    try:
        return funzione()
    except Exception as exc:  # una fonte assente non ferma il quadro
        logger.warning("Quadro del fascicolo: %s non disponibile (%s)", cosa, exc)
        return ripiego


def termini_futuri(fascicolo: Any) -> list[dict[str, str]]:
    from pct.fascicolo_document_presidio import is_identity_expiry_observation
    from web.helpers import get_scadenziario

    fid = _testo(getattr(fascicolo, "id", ""))
    from pct.scadenziario import StatoTermine

    termini = [{"data": _testo(s.data_scadenza)[:10], "titolo": _testo(s.titolo), "tipo": "scadenza",
                "stato": _testo(s.stato)}
               for s in get_scadenziario().tutte(id_fascicolo=fid, solo_aperte=False)
               if s.stato in {StatoTermine.APERTO, StatoTermine.BOZZA}]
    for attivita in getattr(fascicolo, "attivita", []) or []:
        if _testo(getattr(attivita, "esito", "")).upper() != "IN_ATTESA" or is_identity_expiry_observation(attivita):
            continue
        tipo = "udienza" if _testo(getattr(attivita, "tipo", "")).upper() == "UDIENZA" else "scadenza"
        termini.append({"data": _testo(getattr(attivita, "data", ""))[:10], "titolo": _testo(getattr(attivita, "titolo", "")), "tipo": tipo})
    return termini


def documenti_da_classificare(fascicolo: Any) -> int:
    """Documenti senza voce di catalogo attiva o con la voce da rivedere."""
    from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id

    fid = _testo(getattr(fascicolo, "id", ""))
    stati = build_document_ai_repository().catalog_status_by_document(document_ai_tenant_id(), fid)
    return sum(1 for d in getattr(fascicolo, "documenti", []) or []
               if stati.get(_testo(getattr(d, "id", "")), "review_required") == "review_required")


def conteggio_pec_fascicolo(fascicolo: Any, lettura: dict[str, Any] | None) -> dict[str, Any]:
    from pct.fascicolo_pec_conteggio import conteggio_pec
    from web.services.fascicolo_lettura_verifiche import leggi_registro

    if lettura and isinstance((lettura.get("pec") or {}).get("conteggio"), dict):
        return dict(lettura["pec"]["conteggio"])
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    fid = _testo(getattr(fascicolo, "id", ""))
    collegate = sum(1 for o in registro_corrente().oggetti(tenant_corrente(), fid) if getattr(o, "tipo", "") == "pec" and getattr(o, "presente", True))
    pec_letto = (lettura or {}).get("pec") or {"totale": collegate, "da_controllare": []}
    return conteggio_pec(pec_letto, leggi_registro(fid))


def quadro_fascicolo(fascicolo: Any) -> dict[str, Any]:
    from pct.fascicolo_quadro import riga_documenti
    from pct.fascicolo_stato_pratica import stato_pratica_da_fascicolo
    from web.services.obblighi_notifica_sintesi import leggi as sintesi_obblighi
    from web.services.riscontri_processuali_runtime import lettura_consultiva

    fid = _testo(getattr(fascicolo, "id", ""))
    oggi = datetime.now(ROME_TZ).date()
    stato = _sicuro(lambda: stato_pratica_da_fascicolo(fascicolo),
                    {"codice": "in_corso", "etichetta": "Stato da verificare", "dettaglio": ""}, "stato della pratica")
    lettura = _sicuro(lambda: lettura_consultiva(fid), None, "Lettura salvata")
    sintesi = _sicuro(lambda: sintesi_obblighi(fid), None, "obblighi di notifica")
    pec = _sicuro(lambda: conteggio_pec_fascicolo(fascicolo, lettura), {"collegate": 0, "da_confermare": 0}, "conteggio PEC")
    termini = _sicuro(lambda: termini_futuri(fascicolo), [], "termini")
    righe = [
        prossimo_passo_da_lettura(lettura),
        riga_termini_da_lettura(termini, lettura, oggi),
        riga_economia_materializzata(fid, lettura, fascicolo=fascicolo),
        riga_notifiche_da_lettura(sintesi, lettura, oggi),
        riga_documenti(len(getattr(fascicolo, "documenti", []) or []),
                       _sicuro(lambda: documenti_da_classificare(fascicolo), None, "catalogo"), pec),
    ]
    return {"ok": True, "stato": stato, "righe": righe, "termini_agenda": termini, "termini_agenda_versione": 2,
            "lettura_mancante": lettura is None,
            "lettura_precedente": bool((lettura or {}).get("aggiornamento_pendente")),
            "esito_dispositivo": esito_dispositivo_da_lettura(lettura),
            "generato_il": datetime.now(ROME_TZ).replace(microsecond=0).isoformat()}


def esito_dispositivo_da_lettura(lettura: dict[str, Any] | None) -> dict[str, str] | None:
    percorso = (lettura or {}).get("percorso") or {}
    if not percorso.get("esito"):
        return None
    return {campo: _testo(percorso.get(campo))
            for campo in ("esito", "per_il_cliente", "motivo_esito", "data", "documento_id", "sentenza")}


def riga_economia_materializzata(fascicolo_id: str, lettura: dict[str, Any] | None, *,
                                fascicolo: Any = None) -> dict[str, str] | None:
    from pct.fascicolo_quadro import riga_economia
    from web.services.riscontri_processuali_runtime import chiarisci_spese_da_sentenza, risultato_materializzato

    conto = _sicuro(lambda: risultato_materializzato(fascicolo_id, "conto-economico"), {}, "conto economico") or {}
    chiarisci_spese_da_sentenza(conto, lettura)
    righe_conto = list(conto.get("righe") or [])
    contributo = next((r.get("statoContributo") for r in righe_conto if r.get("voce") == "contributo_unificato"), None)
    prossimo_economico = _testo((conto.get("percorso") or {}).get("prossimoPasso"))
    if not conto:
        if fascicolo is None:
            return None
        if lettura is not None:
            # I riscontri sono già nella Lettura. Il conto espone il dettaglio
            # economico quando è disponibile per questo profilo.
            return {**riga_economia(None, []),
                    "testo": "Apri il Conto economico per consultare importi, stato delle spese e fonti.",
                    "livello": "info"}
        from web.services.contributo_stato_runtime import stato_contributo_fascicolo

        contributo = _sicuro(lambda: stato_contributo_fascicolo(fascicolo), None, "stato del contributo")
        riga = riga_economia(contributo, [])
        riga["testo"] += ". Apri il Conto economico per consultare importi, stato delle spese e fonti."
        return riga
    return riga_economia(contributo, righe_conto, prossimo_economico)


def prossimo_passo_da_lettura(lettura: dict[str, Any] | None) -> dict[str, str]:
    from pct.fascicolo_quadro import riga_prossimo_passo

    passi = (lettura or {}).get("prossimi_passi")
    motivo_stato = _testo(((lettura or {}).get("stato_passi") or {}).get("motivo"))
    return riga_prossimo_passo(passi if isinstance(passi, list) else None, motivo_stato=motivo_stato)


def riga_notifiche_da_lettura(sintesi: dict[str, Any] | None, lettura: dict[str, Any] | None,
                              oggi: date) -> dict[str, str]:
    from pct.fascicolo_quadro import riga_notifiche
    from web.services.riscontri_processuali_runtime import documenti_notifica_storica, obbligo_di_notifica_storico

    if sintesi is None:
        return riga_notifiche(None, oggi=oggi)
    # Il riscontro storico non prova la consegna. Il quadro lo distingue da una
    # notifica ancora azionabile solo per la stessa sentenza e la stessa finalità.
    lettura = lettura or {}
    obblighi = list(sintesi.get("obblighi") or [])
    esiti = (lettura.get("ragionamento") or {}).get("conclusioni") or []
    storici = documenti_notifica_storica(esiti)
    stato = "riscontro_storico_precedente" if lettura.get("aggiornamento_pendente") else "riscontro_storico"
    return riga_notifiche([
        {**voce, "stato": stato} if obbligo_di_notifica_storico(voce, storici) else voce
        for voce in obblighi
    ], oggi=oggi)


def riga_termini_da_lettura(agenda: list[dict[str, str]] | None, lettura: dict[str, Any] | None, oggi: date) -> dict[str, str]:
    from pct.fascicolo_quadro import riga_termini
    from web.services.riscontri_processuali_runtime import proietta_riscontri

    termini = [voce for voce in (agenda or []) if voce.get("stato") != "BOZZA"]
    bozze_future = [voce for voce in (agenda or [])
                    if voce.get("stato") == "BOZZA" and voce["data"] >= oggi.isoformat()]
    riscontri = proietta_riscontri(lettura, "termini")
    presenti = {(t["data"], _testo(t["titolo"]).casefold()) for t in termini}
    for voce in riscontri.get("conclusioni") or []:
        data = (voce.get("termine") or {}).get("scadenza_iso")
        titolo = voce.get("cosa") or ""
        chiave = data, _testo(titolo).casefold()
        if data and voce.get("stato") == "da_fare" and voce.get("onerato_codice") in {"noi", "tutte_le_parti"} and chiave not in presenti:
            termini.append({"data": data, "titolo": titolo, "tipo": "scadenza"})
            presenti.add(chiave)
    riga_termine = riga_termini(termini, oggi=oggi)
    if agenda is not None and riga_termine["livello"] == "ok" and riscontri.get("stato") != "pronto":
        riga_termine["testo"] = "Nessuna scadenza o udienza futura registrata in agenda. I termini dagli atti sono da verificare."
        riga_termine["livello"] = "attenzione"
    impugnazioni = [voce for voce in riscontri.get("conclusioni") or []
                    if voce.get("codice") == "termine_impugnazione" and (voce.get("termine") or {}).get("scadenza")]
    futuri = [voce for voce in impugnazioni if not voce["termine"].get("scaduto")]
    mostrati = futuri or (impugnazioni if riga_termine["livello"] == "ok" else [])
    if mostrati:
        sintesi_impugnazioni = []
        for voce in mostrati:
            termine = voce["termine"]
            norma = " · ".join(n["norma"] for n in voce.get("norme") or [] if n.get("norma"))
            stato_termine = "decorso" if termine.get("scaduto") else "per chi intende impugnare"
            sintesi_impugnazioni.append(f"{voce['cosa']}: {termine['scadenza']} ({stato_termine})"
                                        + (f" · {norma}" if norma else ""))
        pezzi = list(dict.fromkeys(sintesi_impugnazioni))
        if riga_termine["livello"] == "ok":
            riga_termine["testo"] = "Nessuna scadenza o udienza futura registrata in agenda." if agenda is not None else ""
            riga_termine["livello"] = "info"
        riga_termine["testo"] = " ".join(filter(None, (riga_termine["testo"], " / ".join(pezzi))))
    if bozze_future:
        numero = len(bozze_future)
        riga_termine["testo"] = riga_termine["testo"].replace(
            "registrata in agenda", "confermata in agenda"
        ).replace("aperta nel fascicolo", "confermata in agenda")
        sezione_bozze = "1 scadenza da verificare in agenda" if numero == 1 else f"{numero} scadenze da verificare in agenda"
        riga_termine["testo"] += f" {sezione_bozze}."
        if riga_termine["livello"] in {"ok", "info"}:
            riga_termine["livello"] = "attenzione"
    if agenda is None:
        avviso = "Agenda in aggiornamento."
        riga_termine["testo"] = (
            avviso if riga_termine["livello"] == "ok" else f"{riga_termine['testo']} {avviso}"
        )
        if riga_termine["livello"] == "ok":
            riga_termine["livello"] = "info"
    return riga_termine


__all__ = ["conteggio_pec_fascicolo", "documenti_da_classificare", "quadro_fascicolo", "termini_futuri"]
