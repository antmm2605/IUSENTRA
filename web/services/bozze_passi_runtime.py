"""Bozze dei passi preparate in sfondo e salvate nel fascicolo come «bozza da rivedere e firmare».

Il lavoro gira fuori dalla richiesta della pagina (calcolatore dei pannelli pronti e lavoro dello scheduler a
bassa priorità): legge la Lettura e il Conto economico già salvati per l'impronta attuale delle fonti
(``ArchivioPannelli.ultimo_valido``), compila le bozze di ``pct.bozze_passi.catalogo`` e le scrive come documenti
dell'editor. Una bozza si rigenera solo se l'avvocato non l'ha toccata; se l'ha salvata, la sua versione resta e
la bozza si segna «dati cambiati». Nulla si invia, si deposita o si notifica: la bozza è solo un documento.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import g, has_request_context

from pct.bozze_passi.archivio import (
    STATO_DATI_CAMBIATI,
    STATO_MODIFICATA,
    STATO_PRONTA,
    STATO_SUPERATA,
    ArchivioBozze,
    VoceBozza,
    adesso,
    percorso_archivio,
)
from pct.bozze_passi.modello import AVVISO_BOZZA, FONTE_BOZZA_PASSO, Bozza
from pct.fascicolo_lettura._testo import data_it

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")
AUTORE = "IUSENTRA (bozza preparata in automatico)"
STATI_ETICHETTE = {
    STATO_PRONTA: "Bozza pronta",
    STATO_MODIFICATA: "Bozza modificata dall'avvocato",
    STATO_DATI_CAMBIATI: "Bozza modificata dall'avvocato: i dati del fascicolo sono cambiati",
    STATO_SUPERATA: "Bozza non più legata a un passo aperto",
}
_RE_SEGNAPOSTO_HTML = re.compile(r"\[da completare: [^\]<]+\]")


def oggi_roma() -> date:
    return datetime.now(ROME_TZ).date()


def archivio_corrente(data_paths: dict[str, Any] | None = None) -> ArchivioBozze | None:
    percorsi = data_paths if data_paths is not None else (dict(getattr(g, "data_paths", {}) or {}) if has_request_context() else {})
    percorso = percorso_archivio(percorsi)
    return ArchivioBozze(percorso) if percorso else None


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def dati_studio() -> dict[str, str]:
    """Avvocato, codice fiscale, indirizzo, PEC e IBAN dalla scheda dello studio (Impostazioni)."""
    from flask import current_app

    from pct.config_studio import GestioneConfigStudio

    try:
        paths = getattr(g, "data_paths", {}) or {}
        percorso = next((_testo(paths.get(k) or current_app.config.get(k)) for k in ("CONFIG_STUDIO_DB", "STUDIO_CONFIG")
                         if _testo(paths.get(k) or current_app.config.get(k))), "./config/studio.json")
        config = GestioneConfigStudio(config_path=percorso).config
    except Exception as exc:  # la scheda mancante non blocca: i dati restano segnaposti
        logger.info("Scheda dello studio non disponibile per le bozze: %s", exc)
        return {}
    studio = config.studio
    citta = _testo(studio.city)
    completo = ", ".join(p for p in (_testo(studio.indirizzo), " ".join(x for x in (_testo(studio.cap), citta,
                                     f"({_testo(studio.province)})" if _testo(studio.province) else "") if x)) if p)
    return {"avvocato": _testo(studio.avvocato), "cf_avvocato": _testo(studio.codice_fiscale_avvocato or studio.cf),
            "indirizzo": _testo(studio.indirizzo), "cap": _testo(studio.cap), "citta": citta,
            "provincia": _testo(studio.province), "indirizzo_completo": completo,
            "pec": _testo(getattr(config.pec, "indirizzo", "")), "iban": _testo(studio.iban)}


def _cliente_cf(fascicolo: Any) -> str:
    from web.helpers import get_clienti

    try:
        cliente = get_clienti().get(_testo(getattr(fascicolo, "id_cliente", "")))
    except Exception:
        return ""
    return _testo(getattr(cliente, "codice_fiscale", "") or getattr(cliente, "partita_iva", "")) if cliente else ""


def impagina(testo: str) -> str:
    """Il testo della bozza nell'impaginazione dell'editor; i segnaposti evidenziati."""
    from web.services.passaggi_runtime import _impagina_bozza_note

    html = _impagina_bozza_note(testo)
    return _RE_SEGNAPOSTO_HTML.sub(lambda m: f"<mark>{m.group(0)}</mark>", html)


def _documento(fascicolo: Any, documento_id: str) -> Any:
    return next((d for d in getattr(fascicolo, "documenti", []) or [] if d.id == documento_id), None)


def _crea_documento(repository: Any, fascicolo_id: str, bozza: Bozza) -> tuple[str, str]:
    from pct.editor_ai.editor_renderer import create_editor_document
    from web.services.document_crypto import encrypt_doc

    creato = create_editor_document(
        fascicoli_repository=repository, fascicolo_id=fascicolo_id, title=bozza.titolo, html_content=impagina(bozza.testo),
        created_by=AUTORE, encrypt=encrypt_doc, fonte_documento=FONTE_BOZZA_PASSO, note=_nota(bozza),
        tags=["bozza", "bozza-passo", f"bozza-passo:{bozza.chiave}"], salvataggio_mirato=True,
    )
    documento = _documento(repository.get(fascicolo_id), creato["document_id"])
    return creato["document_id"], _testo(getattr(documento, "hash_contenuto_sha256", ""))


def _archivio_intero(repository: Any) -> None:
    """Sostituzione e cestino salvano l'archivio intero: in lettura puntuale si completa prima il caricamento
    (stessa salvaguardia del repository, «meglio lento che monco»), come nelle scritture dell'editor."""
    completa = getattr(repository, "_assicura_archivio_completo", None)
    if callable(completa):
        completa()


def _riscrivi_documento(repository: Any, fascicolo_id: str, documento: Any, bozza: Bozza) -> str:
    from pct.editor_ai.editor_renderer import sanitize_editor_html
    from web.services.document_crypto import encrypt_doc

    _archivio_intero(repository)
    grezzo = sanitize_editor_html(impagina(bozza.testo)).encode("utf-8")
    impronta = hashlib.sha256(grezzo).hexdigest()
    repository.sostituisci_documento(fascicolo_id, documento.id, nome_file=documento.nome, contenuto=encrypt_doc(grezzo),
                                     caricato_da=AUTORE, note=_nota(bozza), hash_contenuto_sha256=impronta)
    return impronta


def _nota(bozza: Bozza) -> str:
    mancano = len(bozza.segnaposti)
    return (f"{AVVISO_BOZZA}. Preparata dal software il {oggi_roma():%d/%m/%Y} con il modello «{bozza.modello_titolo}»"
            + (f"; {mancano} dati da completare" if mancano else "") + ". Non è stata inviata, depositata né notificata.")


def _toccata(documento: Any, voce: VoceBozza) -> bool:
    """L'avvocato l'ha salvata: il contenuto non è più quello scritto dal software."""
    return _testo(getattr(documento, "hash_contenuto_sha256", "")) != voce.impronta_contenuto


def prepara_bozze_fascicolo(fascicolo_id: str, *, lettura: dict[str, Any] | None, conto: dict[str, Any] | None = None,
                            archivio: ArchivioBozze, oggi: date | None = None) -> dict[str, int]:
    """Crea, aggiorna o segnala le bozze del fascicolo (contesto dello studio già impostato)."""
    from pct.bozze_passi.catalogo import bozze_del_fascicolo
    from pct.procedura_fasi.fonti import norme
    from web.helpers import get_fascicoli

    esiti = {"create": 0, "aggiornate": 0, "invariate": 0, "dati_cambiati": 0, "superate": 0}
    g.fascicoli_sql_puntuali = True
    repository = get_fascicoli()
    fascicolo = repository.get(fascicolo_id)
    if fascicolo is None or lettura is None:
        return esiti
    bozze = bozze_del_fascicolo(lettura, oggi=oggi or oggi_roma(), conto=conto, studio=dati_studio(),
                                cliente_cf=_cliente_cf(fascicolo))
    passi = list(lettura.get("prossimi_passi") or [])
    esistenti = {v.chiave: v for v in archivio.del_fascicolo(fascicolo_id)}
    for bozza in bozze:
        voce = esistenti.pop(bozza.chiave, None)
        documento = _documento(fascicolo, voce.documento_id) if voce else None
        comune = {"titolo": bozza.titolo, "modello": bozza.modello, "modello_titolo": bozza.modello_titolo,
                  "norma": norme(bozza.fonti), "passi": bozza.passi(passi)}
        if voce is None or documento is None:
            documento_id, impronta = _crea_documento(repository, fascicolo_id, bozza)
            ora = adesso()
            archivio.salva(VoceBozza(fascicolo_id=fascicolo_id, chiave=bozza.chiave, documento_id=documento_id, tipo=bozza.tipo,
                                     da_completare=list(bozza.segnaposti), impronta_testo=bozza.impronta,
                                     impronta_contenuto=impronta, impronta_fonti_attuali=bozza.impronta,
                                     stato=STATO_PRONTA, creata_il=ora, aggiornata_il=ora, **comune))
            fascicolo = repository.get(fascicolo_id)
            esiti["create"] += 1
            continue
        toccata = _toccata(documento, voce)
        if voce.impronta_testo == bozza.impronta:
            stato = STATO_PRONTA if not toccata else (STATO_DATI_CAMBIATI if voce.stato == STATO_DATI_CAMBIATI
                                                      and voce.impronta_fonti_attuali != bozza.impronta else STATO_MODIFICATA)
            voce.__dict__.update(comune, stato=stato, impronta_fonti_attuali=bozza.impronta)
            esiti["invariate"] += 1
        elif not toccata:
            voce.impronta_contenuto = _riscrivi_documento(repository, fascicolo_id, documento, bozza)
            voce.__dict__.update(comune, impronta_testo=bozza.impronta, impronta_fonti_attuali=bozza.impronta,
                                 da_completare=list(bozza.segnaposti), stato=STATO_PRONTA, aggiornata_il=adesso())
            fascicolo = repository.get(fascicolo_id)
            esiti["aggiornate"] += 1
        else:
            if voce.stato != STATO_DATI_CAMBIATI or voce.impronta_fonti_attuali != bozza.impronta:
                voce.dati_cambiati_il = adesso()
            voce.__dict__.update(comune, stato=STATO_DATI_CAMBIATI, impronta_fonti_attuali=bozza.impronta)
            esiti["dati_cambiati"] += 1
        archivio.salva(voce)
    for voce in esistenti.values():
        # Il passo non c'è più: la bozza mai toccata va nel cestino del fascicolo, quella dell'avvocato resta.
        documento = _documento(fascicolo, voce.documento_id)
        if documento is not None and not _toccata(documento, voce):
            _archivio_intero(repository)
            repository.rimuovi_documento(fascicolo_id, voce.documento_id, eliminato_da=AUTORE)
            archivio.elimina(fascicolo_id, voce.chiave)
        elif documento is None:
            archivio.elimina(fascicolo_id, voce.chiave)
        elif voce.stato != STATO_SUPERATA:
            voce.stato, voce.passi = STATO_SUPERATA, []
            archivio.salva(voce)
        esiti["superate"] += 1
    if esiti["create"] or esiti["aggiornate"] or esiti["superate"]:
        _segnala_documenti(fascicolo_id)
    return esiti


def _segnala_documenti(fascicolo_id: str) -> None:
    """I pannelli dei documenti mostrano le bozze nuove (le bozze restano fuori dalla Lettura)."""
    try:
        from web.services.pannelli_pronti_runtime import segnala_scrittura_fascicolo

        segnala_scrittura_fascicolo(fascicolo_id)
    except Exception as exc:
        logger.info("Pannelli non segnalati dopo le bozze di %s: %s", fascicolo_id, exc)


def _fonti_salvate(archivio_pannelli: Any, fonti: Any, fascicolo_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Lettura e Conto economico salvati per l'impronta attuale delle fonti (nessun calcolo qui)."""
    from pct.pannelli_pronti import impronta as impronta_fonti
    from web.services.pannelli_pronti_catalogo import VERSIONE_PANNELLI

    attuale = impronta_fonti.impronta(fonti, fascicolo_id, generazione=archivio_pannelli.generazione(fascicolo_id),
                                      versione=VERSIONE_PANNELLI)
    if attuale is None:
        return None, None

    def leggi(pannello: str) -> dict[str, Any] | None:
        corpo = archivio_pannelli.ultimo_valido(fascicolo_id, pannello, attuale)
        try:
            dati = json.loads(corpo) if corpo else None
        except (UnicodeDecodeError, ValueError):
            return None
        return dati if isinstance(dati, dict) else None

    lettura = (leggi("lettura") or {}).get("lettura")
    conto = leggi("conto-economico")
    if not isinstance(lettura, dict) or lettura.get("aggiornamento_pendente") or conto is None:
        # Senza il Conto economico della stessa impronta (spese distratte, regime IVA) si attende il prossimo giro:
        # una bozza non si riscrive con dati parziali.
        return None, None
    return lettura, conto


def giro(app, *, fascicoli: dict[str, set[str]] | None = None, ore: float = 72.0, limite: int = 40) -> dict[str, int]:
    """Un giro per studio: i fascicoli indicati, o quelli aperti di recente, con la Lettura salvata e attuale."""
    from web.services.pannelli_pronti_runtime import archivio_per_percorsi, fonti_per_percorsi
    from web.services.pannelli_pronti_sfondo import studi

    totale = {"fascicoli": 0, "create": 0, "aggiornate": 0, "invariate": 0, "dati_cambiati": 0, "superate": 0, "errori": 0}
    for owner, data_paths in studi(app):
        slug = str(getattr(owner, "slug", "") or "single-studio")
        if fascicoli is not None and slug not in fascicoli:
            continue
        archivio_pannelli, fonti, archivio = archivio_per_percorsi(data_paths), fonti_per_percorsi(data_paths), archivio_corrente(data_paths)
        if archivio_pannelli is None or fonti is None or archivio is None:
            continue
        elenco = sorted(fascicoli[slug]) if fascicoli is not None else archivio_pannelli.fascicoli_aperti_dal(ore)[:limite]
        for fascicolo_id in elenco:
            try:
                lettura, conto = _fonti_salvate(archivio_pannelli, fonti, fascicolo_id)
                if lettura is None:
                    continue
                with _contesto_studio(app, owner):
                    esiti = prepara_bozze_fascicolo(fascicolo_id, lettura=lettura, conto=conto, archivio=archivio)
                totale["fascicoli"] += 1
                for chiave, valore in esiti.items():
                    totale[chiave] += valore
            except Exception as exc:  # un fascicolo non blocca gli altri
                logger.warning("Bozze dei passi non preparate per %s: %s", fascicolo_id, exc)
                totale["errori"] += 1
    return totale


def _contesto_studio(app, owner):
    """Il contesto di richiesta dello studio, come nel ricalcolo dei pannelli pronti."""
    from contextlib import contextmanager

    from pct.tenant import GestioneTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context

    @contextmanager
    def contesto():
        with app.test_request_context("/__scheduler/bozze-passi"):
            if owner is not None:
                _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), owner)
            yield

    return contesto()


def payload_bozze(fascicolo_id: str) -> dict[str, Any]:
    """Le bozze del fascicolo e il loro stato, per il pannello dei prossimi passi (solo lettura del registro)."""
    from web.helpers import get_fascicoli

    archivio = archivio_corrente()
    voci = archivio.del_fascicolo(fascicolo_id) if archivio else []
    fascicolo = get_fascicoli().get(fascicolo_id) if voci else None
    bozze = []
    for voce in voci:
        documento = _documento(fascicolo, voce.documento_id) if fascicolo is not None else None
        if documento is None:
            continue
        stato = voce.stato
        if stato == STATO_PRONTA and _toccata(documento, voce):
            stato = STATO_MODIFICATA
        bozze.append({
            "chiave": voce.chiave, "tipo": voce.tipo, "titolo": voce.titolo, "modello": voce.modello,
            "modelloTitolo": voce.modello_titolo, "norma": voce.norma, "daCompletare": voce.da_completare,
            "passi": voce.passi, "stato": stato, "statoEtichetta": STATI_ETICHETTE.get(stato, stato),
            "documentoId": voce.documento_id,
            "apri": f"/fascicoli/{fascicolo_id}/documenti/{voce.documento_id}/editor",
            "preparataIl": data_it(voce.creata_il), "aggiornataIl": data_it(voce.aggiornata_il),
            "datiCambiatiIl": data_it(voce.dati_cambiati_il),
        })
    return {"ok": True, "fascicoloId": fascicolo_id, "bozze": bozze,
            "avviso": "Bozze preparate dal software con i dati certi del fascicolo: vanno riviste, completate e firmate. "
                      "Nessuna è stata inviata, depositata o notificata."}


__all__ = ["STATI_ETICHETTE", "archivio_corrente", "dati_studio", "giro", "impagina", "payload_bozze", "prepara_bozze_fascicolo"]
