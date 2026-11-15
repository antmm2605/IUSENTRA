"""Lo stato del contributo unificato di un fascicolo, con gli stessi dati per tutti i pannelli.

La regola è in ``pct.contributo_unificato_stato``; qui si raccolgono, senza leggere documenti, la voce economica
del fascicolo (quella proiettata dall'archivio delle letture, come nel presidio economico) e le voci del catalogo
documentale «contributo unificato / pagamento» ed «esenzione». Card della regia, finestra del controllo
economico, conto economico e quadro del fascicolo chiamano tutti ``stato_contributo_fascicolo`` o
``applica_stato_contributo``: per questo dicono la stessa cosa.

Base normativa: art. 13 e art. 9, comma 1-bis, D.P.R. 115/2002.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def href_documento(fascicolo_id: str, documento_id: str) -> str:
    return f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(documento_id, safe='')}/visualizza"


def documenti_contributo(fascicolo: Any) -> list[dict[str, Any]]:
    """Le voci del catalogo sul contributo unificato, solo per i documenti presenti nel fascicolo."""
    from pct.document_intelligence.certezza_lettura import lettura_certa
    from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id

    fid = _testo(getattr(fascicolo, "id", ""))
    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "") or getattr(d, "nome_file", ""))
            for d in getattr(fascicolo, "documenti", []) or []}
    try:
        voci = build_document_ai_repository().list_contributo_labels(document_ai_tenant_id(), fid)
    except Exception as exc:  # catalogo non pronto: lo stato resta deciso dalla voce economica
        logger.debug("Catalogo del contributo non disponibile per %s: %s", fid, exc)
        return []
    risultato = []
    for documento_id, etichetta, stato, affidabilita in voci:
        if documento_id not in nomi:
            continue  # allegati PEC: la fonte si apre dalla comunicazione
        # Riconosciuto con certezza dal contenuto vale come confermato: l'avvocato non deve riverificarlo.
        risultato.append({"etichetta": etichetta, "id": documento_id, "nome": nomi[documento_id] or etichetta,
                          "href": href_documento(fid, documento_id), "confermato": lettura_certa(stato, affidabilita)})
    return risultato


def _documento_della_voce(fascicolo: Any, voce: Mapping[str, Any]) -> str:
    documento_id = _testo(voce.get("documento_id") or voce.get("documentoId"))
    documenti = list(getattr(fascicolo, "documenti", []) or [])
    if documento_id and any(_testo(getattr(d, "id", "")) == documento_id for d in documenti):
        return documento_id
    nomi = {_testo(voce.get(campo)) for campo in ("documento_fonte", "documentoFonte", "documentoFonteRaw")} - {""}
    return next((_testo(getattr(d, "id", "")) for d in documenti if _testo(getattr(d, "nome", "")) in nomi), "")


_AUTOMATICI = ("import", "automatic", "automatico", "document ai", "lex", "scheduler", "iusentra", "archivio delle letture")


def decisione_dell_avvocato(voce: Mapping[str, Any]) -> bool:
    """Vero se la voce è stata registrata o cambiata da una persona dello studio, non da una lettura automatica.

    Diversamente dal presidio economico, «non previsto» senza importo qui conta: è proprio la decisione
    «contributo non dovuto» o «esente» presa dall'avvocato.
    """
    autori = [_testo(voce.get("updated_by") or voce.get("updatedBy"))]
    for riga in voce.get("history") or voce.get("storico") or []:
        if isinstance(riga, Mapping):
            autori.append(_testo(riga.get("by") or riga.get("updated_by")))
    return any(a and not any(m in a.casefold() for m in _AUTOMATICI) for a in autori)


def voce_contributo(fascicolo: Any, voce: Mapping[str, Any]) -> dict[str, Any]:
    """La voce economica pronta per la regola: documento fonte risolto e decisione dell'avvocato riconosciuta."""
    fid = _testo(getattr(fascicolo, "id", ""))
    documento_id = _documento_della_voce(fascicolo, voce)
    return {
        "status": _testo(voce.get("status") or voce.get("stato")).lower(),
        "importo": voce.get("importo"),
        "documento_fonte": _testo(voce.get("documento_fonte") or voce.get("documentoFonteRaw") or voce.get("documentoFonte")),
        "documento_id": documento_id,
        "href": href_documento(fid, documento_id) if documento_id else "",
        "richiedeConferma": bool(voce.get("richiedeConferma")),
        "importiLetti": list(voce.get("importiLetti") or []),
        "manuale": decisione_dell_avvocato(voce),
    }


def voce_corrente(fascicolo: Any) -> dict[str, Any]:
    """La voce «contributo_unificato» come la vede il presidio economico (archivio delle letture già proiettato)."""
    from web.services.react_fascicoli_bridge import _payment_source_for_kind, _payments_with_automatic_sources

    pagamenti = _payments_with_automatic_sources(fascicolo, getattr(fascicolo, "pagamenti", {}) or {}, enabled=False)
    return _payment_source_for_kind(pagamenti, "contributo_unificato")


@lru_cache(maxsize=1)
def _voci_pst() -> dict[str, tuple[str, str]]:
    """codice oggetto → (area, voce padre) dal catalogo ministeriale XSD versionato."""
    import pct

    percorso = Path(pct.__file__).resolve().parent / "data" / "cataloghi" / "codici_oggetto_pst.json"
    voci: dict[str, tuple[str, str]] = {}

    def _visita(nodo: Any) -> None:
        if isinstance(nodo, dict):
            if "codice" in nodo and "area" in nodo:
                voci.setdefault(str(nodo["codice"]), (str(nodo.get("area") or ""), str(nodo.get("descrizionePadre") or "")))
            for valore in nodo.values():
                _visita(valore)
        elif isinstance(nodo, list):
            for valore in nodo:
                _visita(valore)

    try:
        _visita(json.loads(percorso.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        logger.warning("Catalogo dei codici oggetto PST non leggibile: il contributo dovuto non si calcola.")
    return voci


def _data_documento(documento: Any) -> date | None:
    for campo in ("data_documento", "data_deposito_portale", "data_caricamento", "creato_il"):
        try:
            return date.fromisoformat(_testo(getattr(documento, campo, ""))[:10])
        except ValueError:
            continue
    return None


_DEPOSITO = ("deposito telematico",)
_ESENZIONE = re.compile(r"autocertific|dichiarazione\s+sostitutiva|esenzione", re.IGNORECASE)


def verifiche_contributo(fascicolo: Any, voce: Mapping[str, Any]) -> dict[str, Any]:
    """Confronto del versato con il dovuto (pct.contributo_dovuto) e autocertificazione depositata contro la soglia
    vigente al deposito (pct.esenzione_reddito_cu). Solo testi già salvati: nessuna lettura di file."""
    from pct.contributo_dovuto import categoria, confronta, contributo_dovuto
    from pct.esenzione_reddito_cu import CAMPO_ANNO_REDDITO, invito_rideposito, leggi_autocertificazione, verifica

    esito: dict[str, Any] = {}
    area, padre = _voci_pst().get(_testo(getattr(fascicolo, "codice_oggetto_pst", "")), ("", ""))
    cat = categoria(area=area, padre=padre, tipo_fascicolo=getattr(fascicolo, "tipo", ""))
    try:
        valore = float(getattr(fascicolo, "valore_causa", 0) or 0)
    except (TypeError, ValueError):
        valore = 0.0
    giudice_pace = "giudice di pace" in _testo(getattr(fascicolo, "tribunale", "")).casefold()
    letti = [v for v in [*(voce.get("importiLetti") or []), voce.get("importo")] if v not in (None, "")]
    if cat and letti:
        esito["confronto"] = confronta(letti, contributo_dovuto(cat, valore, giudice_pace=giudice_pace), cat=cat)
    esito["categoria"] = cat
    try:
        from web.services.archivio_letture_runtime import testi_indice_archivio

        testi = testi_indice_archivio(fascicolo)
    except Exception as exc:
        logger.debug("Testi non disponibili per il contributo di %s: %s", getattr(fascicolo, "id", ""), exc)
        return esito
    documenti = {_testo(getattr(d, "id", "")): d for d in getattr(fascicolo, "documenti", []) or []}
    depositi = {oid: d for oid, d in documenti.items() if any(t in _testo(getattr(d, "nome", "")).casefold() for t in _DEPOSITO)}
    verifiche = []
    inviti = []
    anni_archiviati: dict[str, set[int]] | None = None
    for oid, documento in documenti.items():
        testo = testi.get(oid, "")
        nome = _testo(getattr(documento, "nome", ""))
        if not testo or not (_ESENZIONE.search(nome) or _ESENZIONE.search(testo[:1500])):
            continue
        if invito_rideposito(testo):
            inviti.append({"id": oid, "nome": nome, "href": href_documento(_testo(fascicolo.id), oid)})
            continue
        letta = leggi_autocertificazione(testo)
        if letta["soglia"] is None:
            continue
        # Depositata: è la PEC del deposito, o il file è fra gli allegati di una PEC di deposito del fascicolo.
        if oid in depositi:
            data = _data_documento(documento)
        else:
            stelo = nome.rsplit(".", 1)[0].casefold()
            contenitore = next((d for did, d in depositi.items() if stelo and stelo in testi.get(did, "").casefold()), None)
            if contenitore is None:
                continue  # autocertificazione non depositata: non conta (art. 9, comma 1-bis)
            data = _data_documento(contenitore)
        anno = letta["anno"]
        if not letta["anni"]:
            if anni_archiviati is None:
                from web.services.archivio_letture_runtime import fatti_fascicolo
                anni_archiviati = {}
                for fatto in fatti_fascicolo(fascicolo, campo=CAMPO_ANNO_REDDITO, tipo="documento",
                                             verifiche=("verificata", "corretta"), canonico=False):
                    originale = documenti.get(fatto.oggetto_id)
                    if originale is None or not re.fullmatch(r"20[0-9]{2}", str(fatto.valore)):
                        continue
                    impronta = _testo(getattr(originale, "hash_contenuto_sha256", "") or getattr(originale, "hash_sha256", ""))
                    if impronta and fatto.sha256 == impronta:
                        anni_archiviati.setdefault(fatto.oggetto_id, set()).add(int(fatto.valore))
            anni = anni_archiviati.get(oid, set())
            anno = next(iter(anni)) if len(anni) == 1 else None
        verifiche.append({"documento_id": oid, **verifica(anno=anno, soglia=letta["soglia"], data_deposito=data)})
    esito["invitiRideposito"] = inviti
    certe = [v for v in verifiche if v.get("certa")]
    if certe or verifiche:
        esito["esenzioneVerificata"] = certe[0] if certe else verifiche[0]
    return esito


def stato_contributo_fascicolo(fascicolo: Any, voce: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from pct.contributo_unificato_stato import stato_contributo

    grezza = voce if voce is not None else voce_corrente(fascicolo)
    pronta = voce_contributo(fascicolo, grezza or {})
    try:
        pronta.update(verifiche_contributo(fascicolo, pronta))
    except Exception as exc:  # le verifiche sciolgono dubbi: senza, lo stato resta quello della voce
        logger.warning("Verifiche del contributo non eseguite per %s: %s", getattr(fascicolo, "id", ""), exc)
    return stato_contributo(pronta, documenti_contributo(fascicolo))


def applica_stato_contributo(items: dict[str, dict[str, Any]], fascicolo: Any, voce: Mapping[str, Any]) -> None:
    """Card e finestra del presidio economico: etichetta, tono e fonti dallo stato unico del contributo."""
    from pct.contributo_unificato_stato import solo_fonti_del_contributo

    item = items.get("contributo_unificato")
    if not isinstance(item, dict):
        return
    try:
        stato = stato_contributo_fascicolo(fascicolo, voce)
    except Exception as exc:  # il presidio resta consultabile con l'etichetta della voce
        logger.warning("Stato del contributo non calcolato per %s: %s", getattr(fascicolo, "id", ""), exc)
        return
    item["statoContributo"] = stato
    item["statusLabel"] = stato["etichetta"]
    item["tone"] = stato["tono"]
    # «Verifiche e fonti del contributo unificato»: solo ricevute, note che lo riportano e autocertificazioni.
    item["fontiVerifica"] = solo_fonti_del_contributo(item.get("fontiVerifica") or [])


__all__ = ["applica_stato_contributo", "documenti_contributo", "href_documento", "stato_contributo_fascicolo",
           "decisione_dell_avvocato", "voce_contributo", "voce_corrente"]
