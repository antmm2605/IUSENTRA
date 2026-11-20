"""Raccoglie ciò che il fascicolo mostra, per il guardiano della catena (sola lettura, nessun calcolo dei motori).

La Lettura e il Conto economico si prendono **salvati per l'impronta attuale** delle fonti (come le bozze dei passi):
se non lo sono, il fascicolo è «in aggiornamento» e i controlli che ne dipendono aspettano il giro successivo, invece
di confrontare dati superati. Scadenze, agenda, stato, quadro, bozze e impronte dei pannelli si leggono così come sono.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from pct.catena.guardiano import StatoFascicolo

logger = logging.getLogger(__name__)


def _t(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def _enum(valore: Any) -> str:
    return _t(getattr(valore, "value", valore))


def _sicuro(funzione, riserva):
    try:
        return funzione()
    except Exception as exc:  # una fonte illeggibile non ferma il controllo
        logger.debug("Fonte del guardiano non disponibile: %s", exc)
        return riserva


def _json(corpo: bytes | None) -> dict[str, Any] | None:
    try:
        dati = json.loads(corpo) if corpo else None
    except (UnicodeDecodeError, ValueError):
        return None
    return dati if isinstance(dati, dict) else None


def utenti_dello_studio() -> frozenset[str] | None:
    """Identificativi e nomi utente delle persone dello studio (None se non leggibili: ogni responsabile conta)."""
    try:
        from web.helpers import get_utenti

        return frozenset(v for u in get_utenti().tutti() for v in (_t(u.id), _t(u.username)) if v)
    except Exception as exc:
        logger.debug("Utenti dello studio non disponibili: %s", exc)
        return None


def responsabile_umano(responsabile: Any, utenti: frozenset[str] | None) -> bool:
    responsabile = _t(responsabile)
    return bool(responsabile) and (utenti is None or responsabile in utenti)


def scadenze(fascicolo_id: str, utenti: frozenset[str] | None = None) -> list[dict[str, Any]]:
    from web.helpers import get_scadenziario

    return [{"id": s.id, "titolo": s.titolo, "data": str(s.data_scadenza or "")[:10], "stato": _enum(s.stato),
             "note": s.note or "", "id_utente_responsabile": getattr(s, "id_utente_responsabile", "") or "",
             "responsabile_umano": responsabile_umano(getattr(s, "id_utente_responsabile", ""), utenti),
             "perentorio": bool(getattr(s, "perentorio", False))}
            for s in get_scadenziario().tutte(id_fascicolo=str(fascicolo_id), solo_aperte=False)]


def appuntamenti(fascicolo: Any) -> list[dict[str, Any]]:
    """Gli appuntamenti del fascicolo (collegamento esplicito o stesso R.G.), con la modalità dell'udienza."""
    from pct.agenda_eventi_equivalenti import _ruolo, evento_udienza, termine_note_127_ter
    from web.helpers import get_agenda

    fid = _t(getattr(fascicolo, "id", ""))
    numero, anno = _t(getattr(fascicolo, "numero_rg", "")), _t(getattr(fascicolo, "anno_rg", ""))
    ruolo = _ruolo(f"RG {numero}/{anno}") if numero and anno else ""
    risultato = []
    for a in get_agenda().tutti():
        if _t(getattr(a, "id_fascicolo", "")) != fid and not (ruolo and _ruolo(_t(getattr(a, "procedimento", ""))) == ruolo):
            continue
        note_127 = termine_note_127_ter(a)
        risultato.append({
            "id": a.id, "tipo": "UDIENZA" if evento_udienza(a) else _enum(a.tipo), "data": str(a.data_ora or "")[:10],
            "ora": str(a.data_ora or "")[11:16], "stato": _enum(a.stato), "note": a.note or "", "titolo": a.titolo,
            "modalita": "note_scritte" if note_127 or _t(getattr(a, "hearing_mode", "")) == "note_scritte"
            else _t(getattr(a, "hearing_mode", "")),
        })
    return risultato


def bozze(data_paths: dict[str, Any], fascicolo_id: str) -> list[dict[str, Any]]:
    from pct.bozze_passi.archivio import ArchivioBozze, percorso_archivio

    percorso = percorso_archivio(data_paths)
    if percorso is None or not percorso.exists():
        return []
    return [{"chiave": v.chiave, "stato": v.stato, "titolo": v.titolo, "passi": list(v.passi or [])}
            for v in ArchivioBozze(percorso).del_fascicolo(fascicolo_id)]


def pannelli_salvati(archivio: Any, fonti: Any, fascicolo_id: str) -> tuple[list[dict[str, Any]], str | None]:
    """Per ogni pannello salvato del fascicolo: impronta salvata, tentata e attesa; e l'impronta delle fonti."""
    from pct.pannelli_pronti import impronta as impronta_fonti
    from web.services.pannelli_pronti_catalogo import (
        PANNELLI, PANNELLI_SENZA_DATA_DI_CONSULTAZIONE, VERSIONE_PANNELLI, impronta_del_pannello,
    )

    componenti = impronta_fonti.componenti(fonti, fascicolo_id, generazione=archivio.generazione(fascicolo_id),
                                           versione=VERSIONE_PANNELLI)
    if componenti is None:
        return [], None
    per_giorno = impronta_fonti.impronta_componenti(componenti)
    senza_giorno = impronta_fonti.impronta_componenti(componenti, dipende_dal_giorno=False)
    nomi = {p.nome for p in PANNELLI}
    risultato, visti = [], set()
    for _chiave, nome, _percorso, _profilo, salvata, tentata in archivio.voci_del_fascicolo(fascicolo_id):
        if nome not in nomi or nome in visti:
            continue
        visti.add(nome)
        attuale = senza_giorno if nome in PANNELLI_SENZA_DATA_DI_CONSULTAZIONE else per_giorno
        risultato.append({"pannello": nome, "salvata": salvata or "", "tentata": tentata or "",
                          "attesa": impronta_del_pannello(nome, attuale)})
    return risultato, per_giorno


def salvato(archivio: Any, fascicolo_id: str, pannello: str, impronta_fonti_correnti: str | None) -> dict[str, Any] | None:
    from web.services.pannelli_pronti_catalogo import impronta_del_pannello

    if not impronta_fonti_correnti:
        return None
    return _json(archivio.ultimo_valido(fascicolo_id, pannello, impronta_del_pannello(pannello, impronta_fonti_correnti)))


def ultimo_salvato(archivio: Any, fascicolo_id: str, pannello: str) -> dict[str, Any] | None:
    """L'ultimo payload salvato del pannello, anche superato (solo per la misura in sola lettura)."""
    for chiave, nome, *_resto in archivio.voci_del_fascicolo(fascicolo_id):
        if nome == pannello:
            voce = archivio.voce(chiave)
            dati = _json(bytes(voce.corpo)) if voce is not None and voce.corpo else None
            if dati:
                return dati
    return None


def catalogo_dopo_letture(fascicolo_id: str) -> list[dict[str, Any]]:
    """Le voci del catalogo decise dall'avvocato (confermate o respinte) dopo l'ultimo ciclo delle letture."""
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    ciclo = registro_corrente().impronta_fascicolo(tenant_corrente(), fascicolo_id, "motore_documenti") or {}
    ultima = _t(ciclo.get("aggiornato_il"))
    if not ultima:
        return []
    repository = build_document_ai_service().repository
    return [{"documento": _t((a.metadata or {}).get("filename")) or a.document_id, "voce": a.document_label,
             "quando": a.updated_at}
            for a in repository.list_catalog_assignments(document_ai_tenant_id(), str(fascicolo_id))
            if _t(a.status) in {"confirmed", "rejected"} and _t(a.updated_at) > ultima]


def studio_con_avvocati() -> bool:
    from web.services.ragionamento_raccolta import _studio

    return bool((_studio() or {}).get("avvocati"))


def rilettura(fascicolo: Any, lettura: dict[str, Any] | None, oggi: date):
    """La rilettura del testo di un provvedimento del fascicolo (testi già indicizzati, nessuna lettura di file)."""
    testi: dict[str, str] = {}
    rito = (((lettura or {}).get("ragionamento") or {}).get("rito") or {}).get("codice")
    numero, anno = _t(getattr(fascicolo, "numero_rg", "")), _t(getattr(fascicolo, "anno_rg", ""))

    def rileggi(documento_id: str, codice: str) -> list[str] | None:
        from pct.catena.rilettura import date_dal_testo
        from web.services.archivio_letture_runtime import testi_indice_archivio

        if not testi:
            testi.update(testi_indice_archivio(fascicolo) or {})
        testo = testi.get(documento_id)
        if not testo:
            return None
        return date_dal_testo(testo, rg=f"{numero}/{anno}" if numero and anno else "", data_atto="", codice=codice,
                              rito_lavoro=rito == "lavoro", oggi=oggi)
    return rileggi


def credito_incassato(lettura: dict[str, Any] | None) -> bool | None:
    """Liquidazione della sentenza incassata e nessun saldo aperto (pct/fascicolo_lettura/economico.py)."""
    economico = (lettura or {}).get("economico") or {}
    if not economico.get("presente"):
        return None
    if economico.get("liquidato"):
        return economico.get("liquidazione_incasso") == "incassata" and not economico.get("saldo_aperto")
    return None


def stato_fascicolo(fascicolo: Any, data_paths: dict[str, Any], *, archivio: Any, fonti: Any, oggi: date,
                    lettura: dict[str, Any] | None = None, anche_superati: bool = False) -> tuple[StatoFascicolo, str | None]:
    """Lo stato mostrato dal fascicolo e l'impronta delle fonti (None: impronta non disponibile)."""
    fid = _t(getattr(fascicolo, "id", ""))
    pannelli, impronta = ([], None) if archivio is None or fonti is None else pannelli_salvati(archivio, fonti, fid)
    quadro = None
    if lettura is None and archivio is not None:
        dati = salvato(archivio, fid, "lettura", impronta) or (ultimo_salvato(archivio, fid, "lettura") if anche_superati else None)
        candidata = (dati or {}).get("lettura")
        lettura = candidata if isinstance(candidata, dict) and not candidata.get("aggiornamento_pendente") else None
    if archivio is not None:
        quadro = salvato(archivio, fid, "quadro", impronta) or (ultimo_salvato(archivio, fid, "quadro") if anche_superati else None)
    stato = StatoFascicolo(
        fascicolo_id=fid, oggi=oggi, lettura=lettura, scadenze=scadenze(fid, utenti_dello_studio()),
        appuntamenti=appuntamenti(fascicolo),
        stato_fascicolo=_enum(getattr(fascicolo, "stato", "")).upper(), credito_incassato=credito_incassato(lettura),
        quadro=quadro, bozze=bozze(data_paths, fid), pannelli=pannelli,
        catalogo_dopo_letture=_sicuro(lambda: catalogo_dopo_letture(fid), []),
        studio_con_avvocati=_sicuro(studio_con_avvocati, True), rileggi=rilettura(fascicolo, lettura, oggi),
    )
    return stato, impronta


__all__ = ["appuntamenti", "bozze", "pannelli_salvati", "scadenze", "stato_fascicolo"]
