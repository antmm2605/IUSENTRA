"""Viste delle conclusioni già preparate dal motore per la Lettura."""

import json
from typing import Any

from flask import has_request_context

from web.services.pannelli_pronti_runtime import pannello_del_profilo

_NOTIFICHE = frozenset({
    "notifica_sentenza", "notifica_ricorso_decreto_415", "notifica_decreto_ingiuntivo",
    "notifica_ordinata", "precetto", "esecuzione_pa",
})
_ECONOMIA = frozenset({"spese_liquidate", "contributo_unificato"})


def risultato_materializzato(fascicolo_id: str, pannello: str) -> dict[str, Any] | None:
    """Legge il risultato persistito per l'impronta e il profilo correnti."""
    corpo = pannello_del_profilo(fascicolo_id, pannello)
    try:
        payload = json.loads(corpo) if corpo else None
    except (UnicodeDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def lettura_materializzata(fascicolo_id: str) -> dict[str, Any] | None:
    risultato = risultato_materializzato(fascicolo_id, "lettura")
    if risultato is None and has_request_context():
        from web.blueprints.api_v1_react import lettura_preparata

        corpo = lettura_preparata(fascicolo_id)
        risultato = json.loads(corpo) if corpo else None
    lettura = (risultato or {}).get("lettura")
    return lettura if isinstance(lettura, dict) else None


def stato_contributo_da_lettura(lettura: dict[str, Any] | None) -> dict[str, Any] | None:
    stato = (((lettura or {}).get("ragionamento") or {}).get("economia") or {}).get("contributo_unificato")
    return stato if isinstance(stato, dict) and stato.get("codice") else None


def contesto_operativo_da_lettura(lettura: dict[str, Any] | None, fascicolo_id: str = "", *, fascicolo: Any = None) -> dict[str, Any]:
    """Le informazioni comuni di Quadro, Guida pratica e Redazione già lette."""
    contributo = stato_contributo_da_lettura(lettura)
    if contributo is None and fascicolo_id:
        # Le Letture già salvate possono avere solo la conclusione narrativa.
        conto = risultato_materializzato(fascicolo_id, "conto-economico") or {}
        contributo = next((riga.get("statoContributo") for riga in conto.get("righe") or []
                           if riga.get("voce") == "contributo_unificato"), None)
    valore = ((lettura or {}).get("intestazione") or {}).get("fonte_valore_causa") or {}
    if not valore and fascicolo_id:
        from web.services.valore_causa_archivio import valore_iscrizione_corrente

        valore = valore_iscrizione_corrente(fascicolo_id, fascicolo=fascicolo)
    if not lettura and not contributo and not valore:
        return {}
    fase = (lettura or {}).get("fase") or {}
    return {
        **({"udienza": fase.get("prossima_udienza") or ""} if lettura else {}),
        "valore_causa": valore,
        "contributo": contributo,
    }


def lettura_precedente(fascicolo_id: str) -> dict[str, Any] | None:
    """L'ultimo risultato dello stesso profilo, esplicitamente consultivo."""
    corpo = pannello_del_profilo(fascicolo_id, "lettura", precedente=True)
    try:
        lettura = (json.loads(corpo) or {}).get("lettura") if corpo else None
    except (UnicodeDecodeError, ValueError, AttributeError):
        return None
    return {**lettura, "aggiornamento_pendente": True} if isinstance(lettura, dict) else None


def lettura_consultiva(fascicolo_id: str) -> dict[str, Any] | None:
    """Preferisce l'esito corrente e conserva l'ultimo esito durante l'aggiornamento."""
    return lettura_materializzata(fascicolo_id) or lettura_precedente(fascicolo_id)


def aggiorna_stato_presidi(lettura: dict[str, Any], fascicolo_id: str) -> None:
    """Aggiorna soltanto l'indicatore di lavoro, che può scadere senza un nuovo esito."""
    verifiche = lettura.get("verifiche")
    if isinstance(verifiche, dict):
        from web.services.fascicolo_lettura_verifiche import leggi_registro

        try:
            verifiche["in_corso"] = bool(leggi_registro(fascicolo_id).get("in_corso"))
        except Exception:
            # In caso di lettura del registro non riuscita conserva l'indicatore noto.
            pass


def chiarisci_spese_da_sentenza(conto: dict[str, Any], lettura: dict[str, Any] | None) -> None:
    """Distingue una sentenza presente da un dispositivo economico non ancora provato."""
    if not conto.get("ok"):
        return
    quadro = (lettura or {}).get("ragionamento") or {}
    conclusioni = quadro.get("conclusioni") or []
    sentenze = {}
    for voce in conclusioni:
        if voce.get("codice") not in {"notifica_sentenza", "termine_impugnazione"}:
            continue
        fonte = voce.get("letto") or {}
        if fonte.get("documento_id") and fonte.get("documento"):
            sentenze[fonte["documento_id"]] = fonte["documento"]
    if not sentenze:
        return

    from urllib.parse import quote

    fid = quote(str(conto.get("fascicoloId") or ""), safe="")
    base = f"/fascicoli/{fid}/documenti/"
    distrazioni = {}
    for voce in (quadro.get("economia") or {}).get("liquidazioni") or ():
        if voce.get("distrazione_condizionata") and voce.get("richiesta_distrazione"):
            for oid in [voce.get("atto"), *(voce.get("copie") or [])]:
                if oid:
                    distrazioni[f"{base}{quote(oid, safe='')}/visualizza"] = voce["richiesta_distrazione"]
    for riga in conto.get("righe") or []:
        if riga.get("voce") == "sentenza" and riga.get("stato") == "Distratte in favore dell'avvocato":
            fonti = riga.get("fonti") or []
            richieste = {f["href"]: distrazioni[f["href"]] for f in fonti if f.get("href") in distrazioni}
            if richieste and len(richieste) == len(fonti) and len({r["id"] for r in richieste.values()}) == 1:
                prova = next(iter(richieste.values()))
                avviso = "La sentenza distrae le spese «ove richiesto»: verificare che negli atti ci sia la dichiarazione di antistatarietà."
                riga["dettaglio"] = riga.get("dettaglio", "").replace(
                    avviso, "La richiesta di distrazione con dichiarazione di antistatarietà è negli atti (art. 93 c.p.c.).")
                riga["fonti"] = [*fonti, {"label": prova["nome"], "norma": "Richiesta di distrazione · art. 93 c.p.c.",
                                          "href": f"{base}{quote(prova['id'], safe='')}/visualizza"}]
        if riga.get("voce") != "sentenza" or riga.get("stato") not in {
            "Nessuna sentenza con spese liquidate", "Liquidazione non confermata",
        }:
            continue
        riga.update(stato="Sentenza presente: spese da verificare", tono="warning",
                    dettaglio="La sentenza è nel fascicolo. Il dispositivo sulle spese non è ancora confermato: "
                             "consultarlo prima di predisporre una proforma o chiedere il pagamento.",
                    fonti=[{"label": nome, "norma": "Sentenza del fascicolo",
                            "href": f"/fascicoli/{fid}/documenti/{quote(str(oid), safe='')}/visualizza"}
                           for oid, nome in sentenze.items()])
        percorso = conto.get("percorso") or {}
        percorso["prossimoPasso"] = "Verificare il dispositivo sulle spese della sentenza."
        for passo in percorso.get("passi") or []:
            if (passo.get("azione") or {}).get("comando") == "genera_proforma":
                passo.pop("azione")
                passo["dettaglio"] = "Disponibile dopo la verifica della liquidazione."


def proietta_riscontri(lettura: dict[str, Any] | None, sezione: str) -> dict[str, Any]:
    quadro = (lettura or {}).get("ragionamento") or {}
    if not quadro.get("impronta"):
        return {"stato": "da_preparare"}
    conclusioni = quadro.get("conclusioni") or []
    if sezione == "notifiche":
        conclusioni = [v for v in conclusioni if v["codice"] in _NOTIFICHE]
    elif sezione == "economia":
        conclusioni = [v for v in conclusioni if v["codice"] in _ECONOMIA]
    elif sezione == "termini":
        conclusioni = [v for v in conclusioni if v.get("termine") or v["codice"] == "termine_impugnazione"]
    risultato = {
        "stato": "pronto", "versione": quadro["versione"], "impronta": quadro["impronta"],
        "conclusioni": conclusioni,
    }
    if (lettura or {}).get("aggiornamento_pendente"):
        risultato["aggiornamento_pendente"] = True
    if sezione == "regia":
        risultato["fase"] = quadro.get("fase") or {}
        risultato["dubbi"] = quadro.get("dubbi") or []
    return risultato


def documenti_notifica_storica(conclusioni: list[dict[str, Any]]) -> set[str]:
    return {
        voce["letto"]["documento_id"]
        for voce in conclusioni
        if voce.get("codice") == "notifica_sentenza"
        and voce.get("stato") == "non_dovuto"
        and (voce.get("letto") or {}).get("documento_id")
    }


def obbligo_di_notifica_storico(voce: dict[str, Any], documenti_storici: set[str]) -> bool:
    if voce.get("regola") != "sentenza_notifica_breve" or voce.get("stato") not in {"da_verificare", "facoltativo"}:
        return False
    documenti = set(voce.get("documenti") or ())
    documenti.add(voce.get("documentoId"))
    documenti.update(fonte.get("documentoId") for fonte in voce.get("fonti_documentali") or ())
    return bool(documenti_storici.intersection(documenti))


def stati_obblighi_da_lettura(obblighi: list[dict[str, Any]], lettura: dict[str, Any]) -> list[dict[str, Any]]:
    conclusioni = (lettura.get("ragionamento") or {}).get("conclusioni") or []
    storici = documenti_notifica_storica(conclusioni)
    stato = "riscontro_storico_precedente" if lettura.get("aggiornamento_pendente") else "riscontro_storico"
    from pct.fascicolo_quadro import allinea_al_modello

    marcati = [
        {**voce, "stato": stato} if obbligo_di_notifica_storico(voce, storici) else voce
        for voce in obblighi
    ]
    # Una sola verità per atto: dove il modello della causa conclude sulla notifica, vale il modello (2.490, coerenza).
    modello = (lettura.get("ragionamento") or {}).get("conclusioni")
    return allinea_al_modello(marcati, modello if isinstance(modello, list) and modello else None)


def proietta_obblighi_notifica(payload: dict[str, Any], riscontri: dict[str, Any]) -> dict[str, Any]:
    """Le notifiche superate restano nei riscontri, con la fonte della Lettura."""
    from pct.fascicolo_quadro import allinea_al_modello

    storici = documenti_notifica_storica(riscontri.get("conclusioni") or [])
    obblighi = [voce for voce in payload.get("obblighi") or [] if not obbligo_di_notifica_storico(voce, storici)]
    # Il pannello mostra per ogni atto lo stato del modello della causa, lo stesso del Quadro e dei prossimi passi.
    conclusioni = riscontri.get("conclusioni") if riscontri.get("stato") == "pronto" else None
    return {**payload, "riscontriProcessuali": riscontri, "obblighi": allinea_al_modello(obblighi, conclusioni, pannello=True)}


def riscontri_processuali(fascicolo_id: str, sezione: str) -> dict[str, Any]:
    if sezione == "notifiche":
        # Durante il ricalcolo il Quadro e la Lettura conservano l'ultimo
        # riscontro. Il pannello Notifiche applica lo stesso esito e lo espone
        # come precedente, senza riproporre la notifica del medesimo atto.
        return proietta_riscontri(lettura_consultiva(fascicolo_id), sezione)
    return proietta_riscontri(lettura_materializzata(fascicolo_id), sezione)


def riscontro_note_scritte(fascicolo_id: str, giorno: str, *, titolo: str, note: str = "") -> str:
    """Proietta il riscontro della Lettura sul termine dello stesso fascicolo e giorno."""
    from pct.note_127_ter.comunicazione import e_termine_note_127_ter
    from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, TITOLO_NOTE_127_TER

    if not fascicolo_id or not giorno:
        return ""
    if not (f":{CODICE_NOTE_127_TER}" in note or titolo.startswith(TITOLO_NOTE_127_TER)
            or e_termine_note_127_ter(titolo)):
        return ""
    conclusioni = riscontri_processuali(fascicolo_id, "termini").get("conclusioni") or []
    corrispondenti = [voce for voce in conclusioni if voce.get("codice") == "note_127ter"
                     and (voce.get("termine") or {}).get("scadenza_iso") == giorno]
    if len(corrispondenti) != 1:
        return ""
    voce = corrispondenti[0]
    if any(d.get("codice") in {"note_depositate_da_correlare", "note_in_attesa_cancelleria"} for d in voce.get("dubbi") or []):
        return str(voce.get("prova_o_motivo") or "")
    return ""
