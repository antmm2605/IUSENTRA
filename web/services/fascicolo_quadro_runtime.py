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

    from pct.fascicolo_lettura.termini_certi import codice_della_bozza

    termini = [{"data": _testo(s.data_scadenza)[:10], "titolo": _testo(s.titolo), "tipo": "scadenza",
                "stato": _testo(s.stato), "id": _testo(s.id),
                **({"codice_proposta": codice} if s.stato == StatoTermine.BOZZA and (codice := codice_della_bozza(
                    {"titolo": s.titolo, "note": s.note, "stato": "BOZZA"})) else {})}
               for s in get_scadenziario().tutte(id_fascicolo=fid, solo_aperte=False)
               if s.stato in {StatoTermine.APERTO, StatoTermine.BOZZA}]
    for attivita in getattr(fascicolo, "attivita", []) or []:
        if _testo(getattr(attivita, "esito", "")).upper() != "IN_ATTESA" or is_identity_expiry_observation(attivita):
            continue
        tipo = "udienza" if _testo(getattr(attivita, "tipo", "")).upper() == "UDIENZA" else "scadenza"
        termini.append({"data": _testo(getattr(attivita, "data", ""))[:10], "titolo": _testo(getattr(attivita, "titolo", "")), "tipo": tipo})
    return termini


def documenti_da_classificare(fascicolo: Any) -> int:
    """Documenti da verificare nel catalogo o non ancora catalogati (bozze dello studio escluse).

    Stesso calcolo del pannello «Catalogazione documentale» e della Lettura (``catalogo_conteggi_runtime``)."""
    from web.services.catalogo_conteggi_runtime import riepilogo_fascicolo

    riepilogo = riepilogo_fascicolo(fascicolo)
    return riepilogo["da_verificare"] + riepilogo["in_attesa"]


def _numero_documenti(fascicolo: Any) -> int:
    """I documenti del fascicolo: le bozze preparate dal software non si contano."""
    from web.services.catalogo_conteggi_runtime import documenti_del_fascicolo

    return len(documenti_del_fascicolo(fascicolo))


def conteggio_pec_fascicolo(fascicolo: Any, lettura: dict[str, Any] | None) -> dict[str, Any]:
    from pct.fascicolo_pec_conteggio import conteggio_pec
    from web.services.fascicolo_lettura_verifiche import leggi_registro

    if lettura and isinstance((lettura.get("pec") or {}).get("conteggio"), dict):
        pec = lettura["pec"]
        conteggio = dict(pec["conteggio"])
        if "collegate" in pec:
            conteggio["collegate"] = pec["collegate"]
        return conteggio
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
        riga_economia_materializzata(fid, lettura, fascicolo=fascicolo, oggi=oggi),
        riga_notifiche_da_lettura(sintesi, lettura, oggi),
        riga_documenti(_numero_documenti(fascicolo),
                       _sicuro(lambda: documenti_da_classificare(fascicolo), None, "catalogo"), pec),
    ]
    return {"ok": True, "stato": stato, "righe": righe, "termini_agenda": termini, "termini_agenda_versione": 2,
            "lettura_mancante": lettura is None,
            "lettura_precedente": bool((lettura or {}).get("aggiornamento_pendente")),
            "esito_dispositivo": esito_dispositivo_da_lettura(lettura),
            "testata": testata_da_lettura(lettura),
            "generato_il": datetime.now(ROME_TZ).replace(microsecond=0).isoformat()}


def testata_da_lettura(lettura: dict[str, Any] | None) -> dict[str, str] | None:
    """Controparte, difensore e valore come li legge il modello della causa negli atti (pct/ragionamento/parti)."""
    from pct.ragionamento.parti import etichetta_valore

    parti = ((lettura or {}).get("ragionamento") or {}).get("parti") or {}
    if not parti:
        return None
    valore = parti.get("valore") or {}
    return {"controparte": _testo(parti.get("controparte")), "difensore_controparte": _testo(parti.get("difensore_controparte")),
            "fonte_controparte": _testo(parti.get("fonte_controparte")), "valore": etichetta_valore(valore),
            "fonte_valore": _testo(valore.get("fonte")), "norma_valore": _testo(valore.get("norma"))}


def esito_dispositivo_da_lettura(lettura: dict[str, Any] | None) -> dict[str, str] | None:
    percorso = (lettura or {}).get("percorso") or {}
    if not percorso.get("esito"):
        return None
    return {campo: _testo(percorso.get(campo))
            for campo in ("esito", "per_il_cliente", "motivo_esito", "data", "documento_id", "sentenza", "brano_dispositivo")}


def riga_economia_materializzata(fascicolo_id: str, lettura: dict[str, Any] | None, *,
                                fascicolo: Any = None, oggi: date | None = None) -> dict[str, str] | None:
    """Il percorso economico completo (pct/quadro_economia): contributo dal modello della causa, compenso e incassi
    dalla Fatturazione, spese liquidate dal Conto economico; le stesse fonti del Conto economico, nessuna rilettura."""
    from pct.fascicolo_quadro import riga
    from pct.quadro_economia import percorso_economico
    from web.services.fascicolo_conto_economico_runtime import parcelle_del_fascicolo
    from web.services.riscontri_processuali_runtime import (
        chiarisci_spese_da_sentenza, risultato_materializzato, stato_contributo_da_lettura,
    )

    conto = _sicuro(lambda: risultato_materializzato(fascicolo_id, "conto-economico"), {}, "conto economico") or {}
    chiarisci_spese_da_sentenza(conto, lettura)
    righe_conto = list(conto.get("righe") or [])
    corrente = lettura or {}
    if not righe_conto and not corrente.get("aggiornamento_pendente"):
        percorso = corrente.get("percorso") or {}
        if percorso.get("documento_id") and (percorso.get("spese") or {}).get("regolazione") == "compensazione":
            righe_conto = [{"voce": "sentenza", "stato": "Spese compensate"}]
    presidio = next((r.get("statoContributo") for r in righe_conto if r.get("voce") == "contributo_unificato"), None)
    presidio = presidio or stato_contributo_da_lettura(lettura)
    if presidio is None and fascicolo is not None and lettura is None:
        from web.services.contributo_stato_runtime import stato_contributo_fascicolo

        presidio = _sicuro(lambda: stato_contributo_fascicolo(fascicolo), None, "stato del contributo")
    modello = corrente.get("ragionamento") or {}
    conclusioni = modello.get("conclusioni") if isinstance(modello.get("conclusioni"), list) else None
    if conclusioni is None and presidio is None and not righe_conto and fascicolo is None:
        return None
    parcelle = _sicuro(lambda: parcelle_del_fascicolo(fascicolo_id), None, "documenti economici")
    if fascicolo is None:
        from web.services.sentenza_economic_runtime import _fascicoli_repository_mirato

        fascicolo = _sicuro(lambda: _fascicoli_repository_mirato().get(fascicolo_id), None, "voci economiche del fascicolo")
    voci = dict(getattr(fascicolo, "pagamenti", {}) or {}) if fascicolo is not None else {}
    testo, livello = percorso_economico(
        conclusioni=conclusioni, atti=modello.get("atti") or [], righe_conto=righe_conto, parcelle=parcelle, voci=voci,
        presidio_contributo=presidio, oggi=oggi or datetime.now(ROME_TZ).date(), cliente=_natura_cliente(fascicolo))
    prossimo = _testo((conto.get("percorso") or {}).get("prossimoPasso"))
    if prossimo and livello != "ok":
        testo += f". {prossimo}"
    return riga("economia", testo, livello)


def _natura_cliente(fascicolo: Any) -> str:
    """Impresa, P.A. o consumatore dall'anagrafica del cliente del fascicolo (pct/quadro_economia.natura_cliente)."""
    from pct.quadro_economia import natura_cliente

    if fascicolo is None:
        return ""

    def leggi():
        from web.helpers import get_clienti

        id_cliente = _testo(getattr(fascicolo, "id_cliente", ""))
        return get_clienti().get(id_cliente) if id_cliente else None

    return natura_cliente(_sicuro(leggi, None, "anagrafica del cliente"), _testo(getattr(fascicolo, "nome_cliente", "")))


def prossimo_passo_da_lettura(lettura: dict[str, Any] | None) -> dict[str, str]:
    from pct.fascicolo_quadro import riga_prossimo_passo

    passi = (lettura or {}).get("prossimi_passi")
    motivo_stato = _testo(((lettura or {}).get("stato_passi") or {}).get("motivo"))
    return riga_prossimo_passo(passi if isinstance(passi, list) else None, motivo_stato=motivo_stato)


def riga_notifiche_da_lettura(sintesi: dict[str, Any] | None, lettura: dict[str, Any] | None,
                              oggi: date) -> dict[str, str]:
    from pct.fascicolo_quadro import obblighi_dal_modello, riga_notifiche
    from web.services.riscontri_processuali_runtime import proietta_riscontri, stati_obblighi_da_lettura

    if sintesi is None:
        # Il giro in sfondo non ha ancora salvato la sintesi: la riga si calcola dal modello della causa
        # già nella Lettura (conclusioni sulle notifiche dovute), mai rinviata.
        conclusioni = ((lettura or {}).get("ragionamento") or {}).get("conclusioni")
        obblighi_modello = obblighi_dal_modello(conclusioni if isinstance(conclusioni, list) else None)
        riscontri = proietta_riscontri(lettura, "notifiche")
        # I riscontri storici della Lettura attestano singoli adempimenti superati: senza obblighi aperti
        # nel modello non consentono di concludere che tutto il fascicolo sia in ordine.
        testi = {"notifica_sentenza": "Sentenza: riscontro storico del termine breve",
                 "notifica_ricorso_decreto_415": "Ordine di notifica del ricorso e del decreto: adempimento storico"}
        frasi = list(dict.fromkeys(
            testi[voce["codice"]] for voce in riscontri.get("conclusioni", [])
            if voce.get("codice") in testi and voce.get("stato") == "non_dovuto"
            and (voce.get("letto") or {}).get("documento_id")
        ))
        if obblighi_modello:
            riga = riga_notifiche(obblighi_modello, oggi=oggi)
            if frasi:
                riga["testo"] = riga["testo"].rstrip(".") + " · " + " · ".join(frasi) + "."
            return riga
        if frasi:
            riga = riga_notifiche(None, oggi=oggi)
            prefisso = "Ultima lettura salvata. " if riscontri.get("aggiornamento_pendente") else ""
            riga["testo"] = prefisso + " · ".join(frasi) + ". Apri Notifiche per fonti e altri obblighi."
            return riga
        return riga_notifiche(obblighi_modello, oggi=oggi)
    # Il riscontro storico non prova la consegna. Il quadro lo distingue da una
    # notifica ancora azionabile solo per la stessa sentenza e la stessa finalità.
    obblighi = list(sintesi.get("obblighi") or [])
    return riga_notifiche(stati_obblighi_da_lettura(obblighi, lettura or {}), oggi=oggi)


def riga_termini_da_lettura(agenda: list[dict[str, str]] | None, lettura: dict[str, Any] | None, oggi: date) -> dict[str, str]:
    from pct.fascicolo_quadro import riga_termini
    from web.services.riscontri_processuali_runtime import proietta_riscontri

    from pct.fascicolo_lettura.termini_certi import bozze_certe, bozze_della_controparte

    # Le bozze che il modello della causa ha letto nello stesso provvedimento del giudice sono certe: contano come termini,
    # non come «da verificare» (si confermano da sole nel ciclo in sfondo, web/services/termini_certi_runtime). I termini
    # della controparte letti nel provvedimento non sono né adempimenti dello studio né dubbi.
    bozze = [v for v in agenda or [] if v.get("stato") == "BOZZA"]
    conclusioni_modello = ((lettura or {}).get("ragionamento") or {}).get("conclusioni")
    certe = bozze_certe(bozze, conclusioni_modello)
    della_controparte = bozze_della_controparte(bozze, conclusioni_modello)
    termini = [voce for voce in (agenda or []) if voce.get("stato") != "BOZZA" or (voce.get("id") or voce.get("titolo")) in certe]
    bozze_future = [voce for voce in (agenda or [])
                    if voce.get("stato") == "BOZZA" and voce["data"] >= oggi.isoformat()
                    and (voce.get("id") or voce.get("titolo")) not in certe
                    and (voce.get("id") or voce.get("titolo")) not in della_controparte]
    riscontri = proietta_riscontri(lettura, "termini")
    conclusioni = riscontri.get("conclusioni") or []
    lettura_precedente = bool((lettura or {}).get("aggiornamento_pendente"))
    if lettura_precedente:
        conclusioni = [voce for voce in conclusioni if voce.get("codice") == "termine_impugnazione"
                       and (voce.get("termine") or {}).get("scaduto")]
    presenti = {(t["data"], _testo(t["titolo"]).casefold()) for t in termini}
    for voce in conclusioni:
        data = (voce.get("termine") or {}).get("scadenza_iso")
        titolo = voce.get("cosa") or ""
        chiave = data, _testo(titolo).casefold()
        if data and voce.get("stato") == "da_fare" and voce.get("onerato_codice") in {"noi", "tutte_le_parti"} and chiave not in presenti:
            termini.append({"data": data, "titolo": titolo, "tipo": "scadenza"})
            presenti.add(chiave)
    # Una scadenza sola per giorno e adempimento: la bozza certa e il termine già aperto dello stesso atto non sono due.
    from pct.fascicolo_lettura.prossimi_passi import _codice_scadenza

    unici, chiavi = [], set()
    for voce in termini:
        codice = voce.get("codice_proposta") or _codice_scadenza({"titolo": voce.get("titolo")}) or _testo(voce.get("titolo")).casefold()
        if (voce.get("data"), codice) not in chiavi:
            chiavi.add((voce.get("data"), codice))
            unici.append(voce)
    termini = unici
    riga_termine = riga_termini(termini, oggi=oggi)
    if agenda is not None and riga_termine["livello"] == "ok" and riscontri.get("stato") != "pronto":
        riga_termine["testo"] = "Nessuna scadenza o udienza futura registrata in agenda. I termini dagli atti sono da verificare."
        riga_termine["livello"] = "attenzione"
    impugnazioni = [voce for voce in conclusioni
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
        if lettura_precedente:
            pezzi[0] = "Ultima lettura salvata · " + pezzi[0]
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


__all__ = ["conteggio_pec_fascicolo", "documenti_da_classificare", "quadro_fascicolo", "testata_da_lettura", "termini_futuri"]
