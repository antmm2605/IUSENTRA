"""Gli obblighi di notifica del fascicolo, dai documenti catalogati e dall'archivio delle letture.

Raccoglie senza leggere nulla: le voci del catalogo documentale (quale atto è
ogni documento), le date e le parti dell'archivio delle letture, le prove di
notifica già lette. Le regole e le norme sono in `pct.obblighi_notifica`.

Un obbligo «da notificare» con una scadenza futura entra nello scadenziario
una volta sola (il riferimento resta nella nota), come proposta da confermare.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from pct.obblighi_notifica import STATO_DA_NOTIFICARE, DocumentoCatalogato, Parte, obblighi_del_fascicolo

logger = logging.getLogger(__name__)

MARCATORE = "OBBLIGO_NOTIFICA:"
_ETICHETTA_RICORSO_DI = "ricorso per decreto ingiuntivo"


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _dettaglio(fatto: Any, codice: str) -> str:
    return next((str(p.get("dettaglio") or "") for p in list(getattr(fatto, "prove", []) or []) if p.get("codice") == codice), "")


def _catalogo(fascicolo: Any) -> dict[str, str]:
    """document_id → voce del catalogo (proposte e conferme; mai le voci respinte)."""
    try:
        from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

        assegnazioni = build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), _testo(fascicolo.id))
    except Exception:
        logger.debug("Catalogo non disponibile per gli obblighi di notifica di %s", getattr(fascicolo, "id", ""), exc_info=True)
        return {}
    return {_testo(a.document_id): _testo(a.document_label) for a in assegnazioni if _testo(a.document_id) and _testo(a.document_label)}


def raccogli(fascicolo: Any, fatti: list[Any], etichette: dict[str, str]) -> tuple[list[DocumentoCatalogato], list[Parte], dict[str, Any]]:
    """Documenti, parti e contesto per il calcolo, dai soli dati già letti."""
    from pct.archivio_letture.parti_fascicolo import parti_lette

    oggi = date.today().isoformat()
    per_oggetto: dict[str, list[Any]] = {}
    for fatto in fatti:
        per_oggetto.setdefault(_testo(getattr(fatto, "oggetto_id", "")), []).append(fatto)
    precedenti = {oid for oid, elenco in per_oggetto.items() if any(f.campo == "natura_documentale" and f.valore == "precedente_giurisprudenziale" for f in elenco)}

    def _data(oid: str, *campi: str) -> str:
        for campo in campi:
            date_campo = sorted(_testo(f.valore)[:10] for f in per_oggetto.get(oid, []) if f.categoria == "data" and f.campo == campo)
            if date_campo:
                return date_campo[0]
        return ""

    def _nostro(oid: str) -> bool | None:
        lati = {_dettaglio(f, "lato") for f in per_oggetto.get(oid, []) if f.categoria == "parte" and f.campo == "assistito"}
        if "agisce" in lati:
            return True
        if "resiste" in lati:
            return False
        return None

    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "")) for d in list(getattr(fascicolo, "documenti", []) or [])}
    documenti: list[DocumentoCatalogato] = []
    ricorso_di_nostro = any(etichetta.casefold() == _ETICHETTA_RICORSO_DI and _nostro(oid) for oid, etichetta in etichette.items())
    for oid, etichetta in etichette.items():
        if oid in precedenti or oid not in nomi:
            continue
        nostro = _nostro(oid)
        if nostro is None and etichetta.casefold() == "decreto ingiuntivo" and ricorso_di_nostro:
            nostro = True
        udienze = tuple(sorted({_testo(f.valore)[:10] for f in per_oggetto.get(oid, []) if f.categoria == "data" and f.campo == "udienza"}))
        documenti.append(DocumentoCatalogato(id=oid, nome=nomi[oid], etichetta=etichetta, data=_data(oid, "provvedimento", "data_atto"), nostro=nostro, udienze=udienze))

    parti: list[Parte] = []
    for voce in parti_lette(fatti):
        ruolo = "controinteressato" if "controinteressat" in voce.posizione.casefold() else voce.ruolo
        parti.append(Parte(nome=voce.nome, ruolo=ruolo, difensore=voce.difensore, posizione=voce.posizione))
    if not any(p.ruolo in {"controparte", "controinteressato"} for p in parti) and _testo(getattr(fascicolo, "controparte", "")):
        parti.append(Parte(nome=_testo(fascicolo.controparte), ruolo="controparte", difensore=_testo(getattr(fascicolo, "avvocato_controparte", ""))))

    prove = []
    for oid, elenco in per_oggetto.items():
        if any(f.categoria == "prova_notifica" and f.campo in {"relata", "rdac"} for f in elenco) or etichette.get(oid, "").casefold() == "relata di notifica":
            prove.append({"documento_id": oid, "data": _data(oid, "notifica", "data_atto"), "atto": " ".join(_testo(f.contesto)[:200] for f in elenco if f.categoria == "prova_notifica")})
    contesto = {
        "udienze_future": sorted({_testo(f.valore)[:10] for f in fatti if f.categoria == "data" and f.campo == "udienza" and _testo(f.valore)[:10] >= oggi}),
        "date_sentenze": [d.data for d in documenti if d.etichetta.casefold() == "sentenza" and d.data],
        "data_provvedimento_impugnato": next((d.data for d in documenti if d.etichetta.casefold() == "provvedimento amministrativo" and d.data), ""),
        "prove_notifica": prove,
    }
    return documenti, parti, contesto


def obblighi_fascicolo(fascicolo: Any) -> list[dict[str, Any]]:
    from web.services.archivio_letture_runtime import fatti_fascicolo

    fatti = fatti_fascicolo(fascicolo)
    documenti, parti, contesto = raccogli(fascicolo, fatti, _catalogo(fascicolo))
    ufficio = _testo(getattr(fascicolo, "tribunale", "")) or _testo(getattr(fascicolo, "ufficio_giudiziario", ""))
    return [o.to_dict() for o in obblighi_del_fascicolo(documenti, parti, ufficio=ufficio, contesto=contesto)]


def allinea_scadenze(fascicolo: Any, obblighi: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Gli obblighi da notificare con scadenza futura diventano scadenze da confermare, una volta sola."""
    from pct.scadenziario import TipoTermine
    from web.helpers import get_scadenziario

    obblighi = obblighi if obblighi is not None else obblighi_fascicolo(fascicolo)
    gestore = get_scadenziario()
    fid = _testo(fascicolo.id)
    esistenti = " ".join(_testo(getattr(s, "note", "")) for s in gestore.tutte(id_fascicolo=fid, solo_aperte=False))
    conteggi = {"creati": 0, "esistenti": 0}
    oggi = date.today().isoformat()
    for obbligo in obblighi:
        if obbligo["stato"] != STATO_DA_NOTIFICARE or not obbligo["scadenza"] or obbligo["scadenza"] < oggi:
            continue
        marcatore = MARCATORE + obbligo["chiave"]
        if marcatore in esistenti:
            conteggi["esistenti"] += 1
            continue
        destinatari = "; ".join(f"{d['nome']} {d['presso']}" for d in obbligo["destinatari"]) or "controparte da individuare"
        nota = (f"Obbligo di notifica letto dal documento «{obbligo['documento']}». Destinatari: {destinatari}. "
                f"Termine: {obbligo['formula']}. Fonti: {', '.join(obbligo['fonti'])}. Da confermare.\n{marcatore}")
        gestore.nuova(
            titolo=f"Notificare {obbligo['atti']}"[:120],
            tipo=TipoTermine.TERMINE_PERENTORIO if obbligo["natura"] == "perentorio" else TipoTermine.ADEMPIMENTO,
            data_scadenza=obbligo["scadenza"], id_fascicolo=fid,
            descrizione=(obbligo["avvertenze"] or obbligo["formula"])[:300], note=nota,
            perentorio=obbligo["natura"] == "perentorio",
        )
        conteggi["creati"] += 1
    return conteggi


__all__ = ["MARCATORE", "allinea_scadenze", "obblighi_fascicolo", "raccogli"]
