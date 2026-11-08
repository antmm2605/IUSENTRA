"""Registrazione automatica dalla sentenza nei casi certi, e il suo annullamento.

Il lettore «proposta_definizione» (sentenza_proposte_runtime) chiama
`registra_se_certa` in sfondo, sui testi già salvati (documenti del fascicolo e
allegati delle PEC collegate), quando la sentenza del procedimento decide la
causa nel grado e l'identità del procedimento coincide. Il software:

- porta il fascicolo a «definito» con la data della sentenza (art. 132 c.p.c.;
  art. 88 c.p.a.), con la voce in cronologia che cita sentenza e fonte; spese
  compensate o soccombenza del cliente non lo impediscono (art. 92 c.p.c.);
- se il credito delle spese è certo (`pct.sentenza_automatica.valuta_certezza`)
  lo conferma con autore «automatico dalla sentenza», impronta SHA-256 della
  fonte e norma (art. 91 o art. 93 c.p.c.): da quel momento vale per il
  presidio economico e per la parcella (D.M. 55/2014). Un credito incerto resta
  da confermare, con il motivo.

L'avvocato vede la registrazione e può annullarla: lo stato precedente torna,
il credito torna da confermare e l'automatismo non si ripete su quella fonte.
Nessuna lettura di file in una richiesta.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pct.ora_italiana import ROME_TZ
from pct.sentenza_automatica import AUTORE, STATO_DOPPIONE, VERSIONE, valuta_certezza
from pct.sentenza_conclusiva import valuta_sentenza

logger = logging.getLogger(__name__)

LETTORE = "proposta_definizione"


def _testo(valore: Any) -> str:
    return str(getattr(valore, "value", valore) or "").strip()


def _adesso() -> str:
    return datetime.now(ROME_TZ).isoformat(timespec="seconds")


def _economia() -> tuple[Any, str] | None:
    from web.services.sentenza_economic_runtime import _flag_on, _repo, _tenant_id

    if not _flag_on():
        return None
    tenant = _tenant_id()
    return (_repo(), tenant) if tenant else None


def estremi_sentenza(estremi: dict[str, Any]) -> str:
    numero = _testo(estremi.get("numero"))
    anno = _testo(estremi.get("anno"))
    return f" n. {numero}{'/' + anno if anno else ''}" if numero else ""


def _definisci(fascicolo_id: str, *, estremi: dict[str, Any], nome: str, sha: str, grado: str) -> dict[str, Any]:
    """Fascicolo a «definito» con la data della sentenza; mai da archiviato, sospeso o già definito."""
    from pct.fascicoli import StatoFascicolo
    from pct.stato_fascicolo import Prova, ammessa
    from web.helpers import get_fascicoli

    gestore = get_fascicoli()
    corrente = gestore.get(fascicolo_id)
    if corrente is None:
        return {"definito": False}
    stato = _testo(getattr(corrente, "stato", "")).upper()
    norma = "art. 88 c.p.a." if grado == "amministrativo" else "art. 132 c.p.c."
    data = _testo(estremi.get("data"))
    prova = Prova(StatoFascicolo.DEFINITO, f"Definito automaticamente dalla sentenza{estremi_sentenza(estremi)}",
                  f"documento «{nome}», SHA-256 {sha}; {norma}", data=data)
    if stato in {"DEFINITO", "ARCHIVIATO", "SOSPESO"} or not ammessa(getattr(corrente, "stato", ""), prova):
        return {"definito": False, "stato_precedente": stato}
    chiusura_precedente = _testo(getattr(corrente, "data_chiusura", ""))
    if data and not chiusura_precedente:
        corrente.data_chiusura = data
    try:
        gestore.cambia_stato(fascicolo_id, StatoFascicolo.DEFINITO,
                             note=prova.nota() + " La definizione non attesta il passaggio in giudicato.", avvocato=AUTORE)
    except Exception:
        corrente.data_chiusura = chiusura_precedente
        raise
    return {"definito": True, "stato_precedente": stato, "data_chiusura_precedente": chiusura_precedente,
            "data_definizione": _testo(getattr(corrente, "data_chiusura", "")) or data, "norma_definizione": norma}


def correggi_data_definizione(fascicolo_id: str, *, automatica: dict[str, Any], estremi: dict[str, Any]) -> dict[str, Any] | None:
    """La data della definizione automatica segue la data della sentenza letta con la regola corrente.

    Solo se il fascicolo è ancora definito e la data di chiusura è quella scritta dalla registrazione automatica:
    una data scelta dall'avvocato non si tocca mai (06/11/2026: data citata in motivazione presa per la pronuncia).
    """
    from web.helpers import get_fascicoli

    nuova, vecchia = _testo(estremi.get("data")), _testo(automatica.get("data_definizione"))
    if not nuova or not vecchia or nuova == vecchia or automatica.get("annullata") or not automatica.get("definito"):
        return None
    gestore = get_fascicoli()
    corrente = gestore.get(fascicolo_id)
    if corrente is None or _testo(getattr(corrente, "stato", "")).upper() != "DEFINITO":
        return None
    if _testo(getattr(corrente, "data_chiusura", "")) != vecchia:
        return None
    gestore.aggiorna(fascicolo_id, data_chiusura=nuova)
    return {**automatica, "data_definizione": nuova, "data_corretta": {"prima": vecchia, "dopo": nuova}}


def _credito_certo(*, fascicolo: Any, oggetto: Any, testo: str, esito: dict[str, Any]) -> dict[str, Any]:
    """Il credito delle spese, registrato solo se certo; `motivi` dice perché no. Non tocca lo stato del fascicolo."""
    try:
        economia = _economia()
    except Exception:
        economia = None
    if economia is None:
        return {"confermati": [], "motivi": ["Controllo economico delle sentenze non attivo."]}
    repo, tenant = economia
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    sha = _testo(getattr(oggetto, "impronta", "")).lower()
    audits = [a for a in repo.list_sentenza_audits(tenant, fascicolo_id=fascicolo_id)
              if _testo(a.get("document_hash_sha256")).lower() == sha]
    sorgenti = {_testo(a.get("id")) for a in audits}
    eventi = [e for e in repo.list_economic_events(tenant, fascicolo_id=fascicolo_id)
              if e.get("source_type") == "sentenza_economic_audit" and _testo(e.get("source_id")) in sorgenti]
    if not audits and esito.get("importo") is None:
        # Spese compensate o non liquidate (art. 92 c.p.c.): nessun credito da registrare.
        return {"confermati": [], "motivi": []}
    certezza = valuta_certezza(dispositivo=valuta_sentenza(testo)["dispositivo"], importo_dispositivo=esito.get("importo"),
                               fascicolo=fascicolo, audits=audits, eventi=eventi)
    if not certezza["certo"]:
        return {"confermati": [], "motivi": certezza["motivi"]}
    evento = certezza["evento"]
    estremi = esito.get("estremi") or {}
    traccia = {"kind": "registrazione_automatica", "autore": AUTORE, "regola": VERSIONE, "sha256": sha,
               "documento_id": _testo(getattr(oggetto, "oggetto_id", "")), "norma": certezza["norma"],
               "sentenza": estremi_sentenza(estremi).strip(), "citazione": _testo(esito.get("capo_spese"))[:400]}
    confermati = []
    if _testo(evento.get("status")) == "to_review":
        if not repo.aggiorna_evento_se(tenant, _testo(evento.get("id")), da_stato="to_review", da_revisore="",
                                       a_stato="confirmed", revisore=AUTORE, nota=traccia):
            return {"confermati": [], "motivi": ["Credito deciso nel frattempo dall'avvocato."]}
        confermati.append(_testo(evento.get("id")))
    for doppione in certezza["gruppo"][1:]:
        if _testo(doppione.get("status")) == "to_review":
            repo.aggiorna_evento_se(tenant, _testo(doppione.get("id")), da_stato="to_review", a_stato=STATO_DOPPIONE,
                                    revisore="riconvalida:doppione", nota={"kind": "doppione", "credito": _testo(evento.get("id"))})
    if confermati:
        repo.record_decision(tenant_id=tenant, actor_id=AUTORE, kind="credito_automatico_da_sentenza",
                             subject_ref=confermati[0], decision="confirmed",
                             rationale=f"{certezza['etichetta']} ({certezza['norma']}) letto con certezza nella sentenza{traccia['sentenza'] and ' ' + traccia['sentenza']}",
                             evidence={**traccia, "importo": certezza["importo"], "fascicolo_id": fascicolo_id})
    credito = {"evento": _testo(evento.get("id")), "tipo": certezza["tipo"], "etichetta": certezza["etichetta"],
               "norma": certezza["norma"], "importo": certezza["importo"]} if confermati else {}
    return {"confermati": confermati, "motivi": [], **credito}


def registra_se_certa(*, fascicolo: Any, oggetto: Any, testo: str, esito: dict[str, Any]) -> dict[str, Any]:
    """`registrata` vero se definizione o credito sono stati registrati; altrimenti `motivi` dice perché no.

    Le due registrazioni hanno ciascuna la propria certezza (decisione dell'avvocato del 03/11/2026:
    «questo processo doveva essere automatico»):

    - la definizione, quando la sentenza decide la causa nel grado e l'identità del procedimento
      coincide (R.G., ufficio, parte, codice fiscale): è la verifica già superata dal chiamante
      (`esito["proposta"]`, art. 132 c.p.c.; art. 88 c.p.a.). Spese compensate o condanna del
      cliente non la impediscono: la causa è decisa lo stesso (art. 92 c.p.c.);
    - il credito delle spese, solo con importo e beneficiario certi (`pct.sentenza_automatica`,
      artt. 91 e 93 c.p.c.); altrimenti resta da confermare, con il motivo.
    """
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    sha = _testo(getattr(oggetto, "impronta", "")).lower()
    estremi = esito.get("estremi") or {}
    nome = _testo(getattr(oggetto, "nome", "")) or "sentenza"
    credito = _credito_certo(fascicolo=fascicolo, oggetto=oggetto, testo=testo, esito=esito)
    try:
        definizione = _definisci(fascicolo_id, estremi=estremi, nome=nome, sha=sha, grado=_testo(esito.get("grado")))
    except Exception:
        logger.exception("Definizione automatica non registrata per %s", fascicolo_id)
        definizione = {"definito": False}
    motivi = list(credito.get("motivi") or [])
    if not credito["confermati"] and not definizione.get("definito"):
        stato = _testo(definizione.get("stato_precedente"))
        if stato == "SOSPESO":
            motivi.insert(0, "Fascicolo sospeso: la definizione resta una decisione dell'avvocato.")
        return {"registrata": False, "motivi": motivi or ["Credito e stato del fascicolo già decisi: nulla da registrare."]}
    return {"registrata": True, "il": _adesso(), "da": AUTORE, "regola": VERSIONE, "evento": credito.get("evento", ""),
            "eventi": credito["confermati"], "tipo": credito.get("tipo", ""), "etichetta": credito.get("etichetta", ""),
            "norma": credito.get("norma", ""), "importo": credito.get("importo"),
            # Il credito non certo resta da confermare: il motivo accompagna la registrazione della definizione.
            "credito_non_automatico": motivi, **definizione}


def annulla_automatica(fascicolo: Any, proposta_id: str, *, utente: str = "") -> dict[str, Any]:
    """Ripristina lo stato precedente: fascicolo come prima, credito di nuovo da confermare, nessun nuovo automatismo."""
    from pct.fascicoli import StatoFascicolo
    from web.helpers import get_fascicoli
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from web.services.sentenza_proposte_runtime import _dopo_decisione, _parcelle_per_evento

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    oggetto_id, _, impronta = _testo(proposta_id).rpartition(":")
    registro, tenant = registro_corrente(), tenant_corrente()
    lettura = next((r for r in registro.letture(tenant, fascicolo_id, lettore=LETTORE)
                    if r.oggetto_id == oggetto_id and r.sha256 == impronta and r.stato == "letto"), None)
    automatica = dict((lettura.esito or {}).get("automatica") or {}) if lettura else {}
    if not automatica.get("registrata") or automatica.get("annullata"):
        raise ValueError("Registrazione automatica non trovata o già annullata.")
    oggetto = registro.oggetto(tenant, fascicolo_id, getattr(lettura, "tipo", "") or "documento", oggetto_id)
    if oggetto is None or oggetto.impronta != impronta:
        raise ValueError("Il documento della sentenza è cambiato: annullamento da fare dalla sezione economica.")
    parcelle = _parcelle_per_evento(fascicolo_id)
    generata = next((parcelle[e] for e in automatica.get("eventi") or [] if e in parcelle), "")
    if generata:
        raise ValueError(f"Dal credito è già stata generata la parcella {generata}: annullala prima in Fatturazione.")
    ora = _adesso()
    economia = _economia()
    if economia is not None:
        repo, tenant_economia = economia
        for evento_id in automatica.get("eventi") or []:
            repo.aggiorna_evento_se(tenant_economia, evento_id, da_stato="confirmed", da_revisore=AUTORE, a_stato="to_review",
                                    revisore="", nota={"kind": "annullamento_automatico", "da": utente, "il": ora})
    ripristinato = False
    if automatica.get("definito"):
        gestore = get_fascicoli()
        corrente = gestore.get(fascicolo_id)
        if corrente is not None and _testo(getattr(corrente, "stato", "")).upper() == "DEFINITO":
            precedente = _testo(automatica.get("stato_precedente")) or "IN_CORSO"
            corrente.data_chiusura = _testo(automatica.get("data_chiusura_precedente"))
            gestore.cambia_stato(fascicolo_id, StatoFascicolo(precedente), avvocato=utente or "avvocato",
                                 note=f"Definizione automatica dalla sentenza{estremi_sentenza(lettura.esito.get('estremi') or {})} "
                                      f"annullata dall'avvocato: ripristinato lo stato precedente. Fonte «{oggetto.nome}», SHA-256 {impronta}.")
            ripristinato = True
    esito = {k: v for k, v in (lettura.esito or {}).items() if k != "decisione"}
    esito["automatica"] = {**automatica, "annullata": {"da": utente, "il": ora, "stato_ripristinato": ripristinato}}
    registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=lettura.versione_lettore, esito=esito)
    decisione = {"esito": "annullata", "da": utente, "il": ora}
    _dopo_decisione(fascicolo_id, registro, decisione, impronta,
                    rationale="Annullamento dell'avvocato della registrazione automatica dalla sentenza")
    return {"proposta": proposta_id, **decisione}


def registrazioni_automatiche(fascicolo: Any, registro: Any, tenant: str, parcelle: dict[str, str]) -> list[dict[str, Any]]:
    """Le registrazioni automatiche in vigore, con la fonte da visualizzare e il passaggio letto."""
    from web.services.sentenza_proposte_runtime import _euro, con_passo, href_fonte

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    presenti = {(o.oggetto_id, o.impronta): o for o in registro.oggetti(tenant, fascicolo_id)
                if o.presente and o.tipo in {"documento", "allegato_pec"}}
    voci = []
    for lettura in registro.letture(tenant, fascicolo_id, lettore=LETTORE):
        esito = lettura.esito or {}
        automatica = esito.get("automatica") or {}
        if lettura.stato != "letto" or not automatica.get("registrata") or automatica.get("annullata"):
            continue
        oggetto = presenti.get((lettura.oggetto_id, lettura.sha256))
        estremi = esito.get("estremi") or {}
        evento = _testo(automatica.get("evento"))
        citazione = _testo(esito.get("capo_spese")) or _testo(esito.get("dispositivo"))
        voci.append({
            "id": f"{lettura.oggetto_id}:{lettura.sha256}", "documentoId": lettura.oggetto_id,
            "documento": _testo(getattr(oggetto, "nome", "")) or "Sentenza",
            "href": con_passo(href_fonte(fascicolo_id, oggetto), citazione),
            "numero": _testo(estremi.get("numero")), "anno": _testo(estremi.get("anno")), "data": _testo(estremi.get("data")),
            "citazione": citazione,
            "etichetta": (f"{_testo(automatica.get('etichetta'))} ({_testo(automatica.get('norma'))})"
                          if _testo(automatica.get("etichetta")) else ""),
            "importoLabel": _euro(automatica.get("importo")) if automatica.get("importo") is not None else "",
            "eventId": evento, "parcella": parcelle.get(evento, ""),
            "definito": bool(automatica.get("definito")), "dataDefinizione": _testo(automatica.get("data_definizione")),
            "normaDefinizione": _testo(automatica.get("norma_definizione")) or "art. 132 c.p.c.",
            "registrataIl": _testo(automatica.get("il")),
        })
    return voci


__all__ = ["annulla_automatica", "estremi_sentenza", "registra_se_certa", "registrazioni_automatiche"]
