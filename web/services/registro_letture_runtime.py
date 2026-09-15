"""Il registro delle letture dentro l'applicazione: percorsi, inventario, eventi, stato.

Qui il registro incontra Flask: il percorso tenant-aware del database, lo
studio corrente, l'inventario del fascicolo (documenti e PEC collegate), gli
eventi che lo aggiornano (documento caricato, sostituito, rimosso; PEC
collegata) e il payload che la Lettura del fascicolo mostra all'avvocato.
I lettori chiamano queste funzioni; la logica resta in `pct.registro_letture`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

from flask import current_app, g, has_app_context, has_request_context

from pct.registro_letture import LETTORI, Oggetto, RegistroLetture, etichetta_lettore
from pct.registro_letture.inventario import oggetti_da_fascicolo, oggetti_da_pec, oggetto_da_documento
from pct.registro_letture.verifica import verifica_date_lette, verifica_lettura
from pct.registro_letture.verifica_date import interpreta_data, orizzonte_fascicolo
from web.services.lettura_cache import invalida_lettura

logger = logging.getLogger(__name__)
CHIAVE_PERCORSO = "REGISTRO_LETTURE_DB"


def percorso_registro(paths: Mapping[str, Any] | None = None) -> str:
    """Il database del registro dello studio: da `data_paths`, altrimenti accanto ai fascicoli."""
    mappa = dict(paths or {})
    if not mappa and has_app_context():
        mappa = dict(getattr(g, "data_paths", {}) or {})
        if not mappa:
            mappa = {CHIAVE_PERCORSO: current_app.config.get(CHIAVE_PERCORSO, ""), "FASCICOLI_DB": current_app.config.get("FASCICOLI_DB", "")}
    esplicito = str(mappa.get(CHIAVE_PERCORSO) or "").strip()
    if esplicito:
        return esplicito
    fascicoli = str(mappa.get("FASCICOLI_DB") or "./data/fascicoli/fascicoli.json").strip()
    return str(Path(fascicoli).resolve().parent.parent / "intelligence" / "registro_letture.db")


def _dsn_postgres(paths: Mapping[str, Any] | None = None) -> str:
    try:
        from pct.postgres_runtime_support import resolve_runtime_postgres_dsn

        return resolve_runtime_postgres_dsn(env_url_keys=("IUSENTRA_REGISTRO_LETTURE_DSN",))
    except Exception:
        return ""


def registro_per_percorsi(paths: Mapping[str, Any] | None = None) -> RegistroLetture:
    return RegistroLetture(percorso_registro(paths), postgres_dsn=_dsn_postgres(paths))


def registro_corrente() -> RegistroLetture:
    return registro_per_percorsi(None)


def tenant_corrente() -> str:
    """Lo stesso identificativo di studio usato dall'indice documentale."""
    try:
        from web.services.document_intelligence_runtime import document_ai_tenant_id

        return document_ai_tenant_id()
    except Exception:
        return "single-studio"


def utente_corrente_id() -> str:
    utente = g.get("utente_corrente") if has_request_context() else None
    return str(getattr(utente, "id", "") or getattr(utente, "username", "") or "").strip()


def cifratura_attiva() -> bool:
    try:
        from pct.document_crypto import doc_key

        return bool(doc_key())
    except Exception:
        return False


# ---- inventario ---------------------------------------------------------------

def _righe_pec_collegate(fascicolo_id: str) -> list[dict[str, Any]]:
    """I messaggi PEC collegati al fascicolo con i loro allegati, dal presidio audit-grade."""
    try:
        from web.services.pec_pipeline_runtime import repository_for_current_request

        repository = repository_for_current_request()
        tenant = str(getattr(repository, "tenant_id", "default") or "default")
        righe: list[dict[str, Any]] = []
        with repository.connect() as conn:
            messaggi = conn.execute(
                "SELECT id, mime_sha256, mime_size, received_at, metadata_json FROM pec_messages WHERE tenant_id=? AND linked_fascicolo_id=? ORDER BY received_at DESC",
                (tenant, fascicolo_id),
            ).fetchall()
            for messaggio in messaggi:
                riga = dict(messaggio)
                allegati = conn.execute(
                    "SELECT id, attachment_index, filename, sha256, size_bytes, ocr_text FROM pec_attachments WHERE message_id=? AND parsed_version_id=("
                    "SELECT id FROM pec_parsed_versions WHERE message_id=? ORDER BY version DESC LIMIT 1) ORDER BY attachment_index",
                    (riga["id"], riga["id"]),
                ).fetchall()
                riga["allegati"] = [dict(allegato) for allegato in allegati]
                righe.append(riga)
        return righe
    except Exception:
        # Presidio non inizializzato o casella assente: l'inventario resta ai documenti.
        return []


def inventario_fascicolo(fascicolo: Any, *, con_pec: bool = True) -> list[Oggetto]:
    oggetti = oggetti_da_fascicolo(fascicolo, cifratura_attiva=cifratura_attiva())
    if con_pec:
        oggetti.extend(oggetti_da_pec(_righe_pec_collegate(str(getattr(fascicolo, "id", "") or "")), fascicolo))
    return oggetti


def aggiorna_inventario(fascicolo: Any, *, registro: RegistroLetture | None = None, con_pec: bool = True) -> dict[str, int]:
    """Allinea il registro all'inventario corrente del fascicolo; restituisce i conteggi."""
    fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
    if not fascicolo_id:
        return {}
    registro = registro or registro_corrente()
    oggetti = inventario_fascicolo(fascicolo, con_pec=con_pec)
    tipi = ("documento", "pec", "allegato_pec") if con_pec else ("documento",)
    return registro.registra_inventario(tenant_corrente(), fascicolo_id, oggetti, tipi=tipi)


def _fascicolo(fascicolo_id: str) -> Any:
    try:
        from web.helpers import get_fascicoli

        return get_fascicoli().get(str(fascicolo_id or "").strip())
    except Exception:
        return None


# ---- eventi -------------------------------------------------------------------

def documento_aggiornato(fascicolo_id: str, documento: Any = None) -> None:
    """Un documento è stato caricato o sostituito: inventario allineato e lettura invalidata."""
    fascicolo_id = str(fascicolo_id or "").strip()
    if not fascicolo_id:
        return
    try:
        fascicolo = _fascicolo(fascicolo_id)
        registro = registro_corrente()
        if fascicolo is not None:
            aggiorna_inventario(fascicolo, registro=registro, con_pec=False)
        elif documento is not None:
            oggetto = oggetto_da_documento(documento, {}, cifratura_attiva=cifratura_attiva())
            if oggetto is not None:
                registro.registra_inventario(tenant_corrente(), fascicolo_id, [oggetto], tipi=())
    except Exception as exc:  # il registro non deve mai bloccare il caricamento
        logger.warning("Registro letture non aggiornato per il fascicolo %s: %s", fascicolo_id, exc)
    invalida_lettura(fascicolo_id)
    _lettura_dopo_evento(fascicolo_id)


def _lettura_dopo_evento(fascicolo_id: str) -> None:
    """I motori dell'archivio leggono l'oggetto nuovo in un thread: mai nella richiesta."""
    try:
        from web.services.archivio_letture_runtime import lettura_dopo_evento

        lettura_dopo_evento(fascicolo_id)
    except Exception as exc:
        logger.debug("Lettura in sfondo non avviata per %s: %s", fascicolo_id, exc)


def documento_rimosso(fascicolo_id: str, documento_id: str) -> None:
    fascicolo_id = str(fascicolo_id or "").strip()
    if not fascicolo_id:
        return
    try:
        registro_corrente().rimuovi_oggetto(tenant_corrente(), fascicolo_id, "documento", str(documento_id or ""))
    except Exception as exc:
        logger.warning("Registro letture: rimozione non registrata per %s/%s: %s", fascicolo_id, documento_id, exc)
    invalida_lettura(fascicolo_id)


def pec_collegata(fascicolo_id: str) -> None:
    fascicolo_id = str(fascicolo_id or "").strip()
    if not fascicolo_id:
        return
    try:
        fascicolo = _fascicolo(fascicolo_id)
        if fascicolo is not None:
            aggiorna_inventario(fascicolo, con_pec=True)
    except Exception as exc:
        logger.warning("Registro letture: PEC collegata non registrata per %s: %s", fascicolo_id, exc)
    invalida_lettura(fascicolo_id)
    _lettura_dopo_evento(fascicolo_id)


# ---- impronte del contenuto per l'indice documentale ----------------------------

class ImpronteContenuto:
    """Risolve l'impronta in chiaro di un documento senza decifrarlo, se il registro la conosce."""

    def __init__(self, registro: RegistroLetture, tenant_id: str, fascicolo_id: str) -> None:
        self._registro = registro
        self._tenant = tenant_id
        self._fascicolo = fascicolo_id
        self._cache: dict[str, str] = {}

    def nota(self, documento: Any) -> str:
        archivio = str(getattr(documento, "hash_sha256", "") or "").strip().lower()
        if not archivio:
            return ""
        if archivio in self._cache:
            return self._cache[archivio]
        try:
            sha = self._registro.impronta_contenuto(self._tenant, "documento", archivio)
        except Exception:
            sha = ""
        self._cache[archivio] = sha
        return sha

    def impara(self, documento: Any, sha256: str, dimensione: int = 0) -> None:
        archivio = str(getattr(documento, "hash_sha256", "") or "").strip().lower()
        sha = str(sha256 or "").strip().lower()
        if not archivio or not sha:
            return
        self._cache[archivio] = sha
        try:
            self._registro.registra_impronta_contenuto(
                self._tenant, self._fascicolo, "documento", str(getattr(documento, "id", "") or ""),
                sha256=sha, sha256_archivio=archivio, dimensione=dimensione,
            )
        except Exception as exc:
            logger.debug("Impronta contenuto non registrata: %s", exc)


def impronte_contenuto(fascicolo_id: str, *, registro: RegistroLetture | None = None) -> ImpronteContenuto | None:
    try:
        return ImpronteContenuto(registro or registro_corrente(), tenant_corrente(), str(fascicolo_id or ""))
    except Exception:
        return None


# ---- letture e anomalie ------------------------------------------------------------

def registra_lettura(fascicolo: Any, oggetto: Oggetto, lettore: str, *, esito: dict[str, Any] | None = None, stato: str = "letto", durata_ms: int = 0, verifica: bool = True, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Registra una lettura e, se richiesto, verifica i dati letti registrando le anomalie."""
    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = str(getattr(fascicolo, "id", "") or fascicolo or "").strip()
    lettura = registro.segna_letto(tenant, fascicolo_id, oggetto, lettore, stato=stato, esito=esito, durata_ms=durata_ms)
    anomalie: list[Any] = []
    if verifica and esito and stato == "letto":
        contesto = orizzonte_fascicolo(fascicolo if not isinstance(fascicolo, str) else {})
        trovate = verifica_lettura(esito, contesto)
        if trovate:
            anomalie = registro.registra_anomalie(tenant, fascicolo_id, oggetto, lettore, trovate)
    return {"lettura": lettura.to_dict(), "anomalie": [a.to_dict() for a in anomalie]}


def _sincronizza_presidio_pec(fascicolo: Any, registro: RegistroLetture, tenant: str, righe: list[dict[str, Any]]) -> None:
    """Gli allegati PEC con testo letto dal presidio audit-grade risultano letti anche nel registro."""
    fascicolo_id = str(getattr(fascicolo, "id", "") or "")
    letti: list[Oggetto] = []
    for riga in righe:
        for allegato in list(riga.get("allegati") or []):
            if not str(allegato.get("ocr_text") or "").strip():
                continue
            oggetto = registro.oggetto(tenant, fascicolo_id, "allegato_pec", str(allegato.get("id") or ""))
            if oggetto is not None:
                letti.append(oggetto)
    if letti:
        da_segnare = registro.da_leggere(tenant, fascicolo_id, "presidio_pec", oggetti=letti)
        if da_segnare:
            registro.segna_letti(tenant, fascicolo_id, da_segnare, "presidio_pec", esito={"fonte": "presidio PEC audit-grade"})


def _verifica_date_pec(fascicolo: Any, registro: RegistroLetture, tenant: str) -> None:
    """Le udienze e i termini letti dalle PEC del fascicolo: una data prima della PEC o fuori orizzonte è un'anomalia."""
    try:
        from web.services.fascicolo_pec_presidio import messaggi_pec_per_fascicolo

        messaggi = messaggi_pec_per_fascicolo(fascicolo)
    except Exception:
        return
    fascicolo_id = str(getattr(fascicolo, "id", "") or "")
    contesto = orizzonte_fascicolo(fascicolo)
    for messaggio in messaggi:
        ricevuta = str(messaggio.get("received_at") or "")[:10]
        voci = []
        for udienza in list(messaggio.get("udienze") or []):
            data = str(udienza.get("hearing_date") or "")[:10]
            if data:
                voci.append({"valore": data, "campo": "udienza", "contesto": f"udienza comunicata con la PEC del {ricevuta}", "confronto": "", "etichetta_confronto": ""})
        for termine in list(messaggio.get("termini") or []):
            data = str(termine.get("dies_a_quo_date") or "")[:10]
            if data:
                voci.append({"valore": data, "campo": "termine", "contesto": f"decorrenza del termine {termine.get('deadline_type') or ''} dalla PEC del {ricevuta}".strip()})
        if not voci:
            continue
        contesto_pec = dict(contesto)
        data_pec = interpreta_data(ricevuta)
        if data_pec is not None:
            # Un'udienza o una decorrenza comunicate da una PEC non possono precederla.
            contesto_pec["data_minima"] = max(filter(None, [contesto.get("data_minima"), data_pec]))
        anomalie = verifica_date_lette(voci, contesto_pec)
        if not anomalie:
            continue
        oggetto = registro.oggetto(tenant, fascicolo_id, "pec", str(messaggio.get("id") or ""))
        if oggetto is None:
            continue
        for anomalia in anomalie:
            if anomalia["codice"] == "prima_del_fascicolo":
                anomalia["motivo"] = f"La data {anomalia['valore_letto']} precede la PEC che la comunica ({ricevuta}): probabile lettura errata."
                anomalia["codice"] = "prima_della_pec"
        registro.registra_anomalie(tenant, fascicolo_id, oggetto, "presidio_pec", anomalie)


def _oggetto_etichetta(voce: dict[str, Any]) -> str:
    tipo = str(voce.get("tipo") or "")
    nome = str(voce.get("nome") or "")
    if tipo == "pec":
        return f"PEC «{nome}»" if nome else "PEC"
    if tipo == "allegato_pec":
        return f"allegato PEC «{nome}»" if nome else "allegato PEC"
    return nome or "documento"


def stato_letture_payload(fascicolo: Any, *, registro: RegistroLetture | None = None, segna_visto: bool = True) -> dict[str, Any]:
    """Il pannello «Letture» del fascicolo: per lettore, per oggetto, novità dall'ultima apertura, anomalie."""
    from pct.formatting import format_datetime_it

    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
    # Ogni passo accessorio è isolato: un presidio che inciampa su un fascicolo
    # reale non deve far sparire l'intero registro dal pannello, come è successo
    # in produzione il 15/09/2026. Ciò che non riesce si dichiara, non si nasconde.
    degradato: list[dict[str, str]] = []

    def passo(nome: str, azione: Any, valore_di_riserva: Any = None) -> Any:
        try:
            return azione()
        except Exception as exc:
            logger.exception("Registro letture del fascicolo %s: passo «%s» non riuscito", fascicolo_id, nome)
            degradato.append({"passo": nome, "motivo": f"{type(exc).__name__}: {exc}"[:300]})
            return valore_di_riserva

    # L'inventario si allinea qui (documenti e PEC collegate): è la vista dell'avvocato.
    righe_pec = passo("PEC collegate", lambda: _righe_pec_collegate(fascicolo_id), []) or []
    oggetti = passo(
        "inventario del fascicolo",
        lambda: oggetti_da_fascicolo(fascicolo, cifratura_attiva=cifratura_attiva()) + oggetti_da_pec(righe_pec, fascicolo),
        [],
    ) or []
    if oggetti:
        passo("registrazione dell'inventario", lambda: registro.registra_inventario(tenant, fascicolo_id, oggetti))
    passo("allineamento del presidio PEC", lambda: _sincronizza_presidio_pec(fascicolo, registro, tenant, righe_pec))
    passo("verifica delle date lette dalle PEC", lambda: _verifica_date_pec(fascicolo, registro, tenant))
    stato = registro.stato_fascicolo(tenant, fascicolo_id)
    utente = utente_corrente_id()
    novita = (
        passo("novità dall'ultima apertura", lambda: registro.novita_e_segna_visto(tenant, fascicolo_id, utente, segna=segna_visto and bool(utente)))
        if utente else None
    ) or {"prima_vista": True, "visto_il": "", "nuovi": [], "cambiati": [], "rimossi": []}
    anomalie = passo("anomalie aperte", lambda: [a.to_dict() for a in registro.anomalie(tenant, fascicolo_id, stato="aperta")], []) or []
    nomi = {(str(v.get("tipo")), str(v.get("oggetto_id"))): _oggetto_etichetta(v) for v in stato.per_oggetto}
    for anomalia in anomalie:
        anomalia["oggetto"] = nomi.get((anomalia["tipo"], anomalia["oggetto_id"]), anomalia["oggetto_id"])
        anomalia["lettore_etichetta"] = etichetta_lettore(anomalia["lettore"])
        anomalia["creata_il_it"] = format_datetime_it(anomalia.get("creata_il"))
    lettori = []
    for voce in stato.lettori:
        dati = voce.to_dict()
        dati["ultima_lettura_it"] = format_datetime_it(voce.ultima_lettura) if voce.ultima_lettura else ""
        lettori.append(dati)
    def _archivio() -> dict[str, Any]:
        from web.services.archivio_letture_runtime import stato_archivio_payload

        return stato_archivio_payload(fascicolo, registro=registro)

    archivio = passo("archivio delle letture", _archivio, {}) or {}
    return {
        "impronta": stato.impronta,
        "oggetti": stato.oggetti,
        "tutto_letto": stato.tutto_letto,
        "degradato": degradato,
        "lettori": lettori,
        "archivio": archivio,
        "per_oggetto": [{**v, "etichetta": _oggetto_etichetta(v)} for v in stato.per_oggetto],
        "novita": {
            "prima_vista": bool(novita.get("prima_vista")),
            "visto_il": str(novita.get("visto_il") or ""),
            "visto_il_it": format_datetime_it(novita.get("visto_il")) if novita.get("visto_il") else "",
            "nuovi": [{**v, "etichetta": _oggetto_etichetta(v)} for v in novita.get("nuovi") or []],
            "cambiati": [{**v, "etichetta": _oggetto_etichetta(v)} for v in novita.get("cambiati") or []],
            "rimossi": list(novita.get("rimossi") or []),
        },
        "anomalie": anomalie,
        "anomalie_aperte": len(anomalie),
        "lettori_censiti": [{"id": chiave, **valori} for chiave, valori in LETTORI.items()],
    }


def risolvi_anomalia(anomalia_id: str, *, esito: str, valore: str = "", registro: RegistroLetture | None = None) -> dict[str, Any]:
    registro = registro or registro_corrente()
    anomalia = registro.risolvi_anomalia(tenant_corrente(), anomalia_id, esito=esito, utente_id=utente_corrente_id(), valore=valore)
    return anomalia.to_dict()


def leggi_i_nuovi(fascicolo: Any, *, registro: RegistroLetture | None = None) -> dict[str, Any]:
    """Legge solo ciò che manca: indice documentale sui documenti nuovi o cambiati, OCR sui testi non estratti.

    L'indice documentale salta da solo i documenti già pronti (impronta uguale);
    la coda OCR rifiuta i documenti già letti. Qui si chiede loro di guardare il
    fascicolo, non di rileggerlo.
    """
    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
    aggiorna_inventario(fascicolo, registro=registro, con_pec=True)
    esito: dict[str, Any] = {"indice": {}, "ocr_accodati": 0, "da_leggere_prima": 0}
    esito["da_leggere_prima"] = len(registro.da_leggere(tenant, fascicolo_id, "indice_documentale", tipi=("documento",)))
    try:
        from web.services.document_intelligence_runtime import build_lex_indexing_summary_payload

        riepilogo = build_lex_indexing_summary_payload(fascicolo_id, process=True, retry_errors=True, apply_automations=False, forza=True)
        esito["avvisi"] = [str(v)[:160] for v in list(riepilogo.get("warnings") or [])[:5]]
        esito["indice"] = {chiave: riepilogo.get(chiave) for chiave in ("total_documents", "ready", "queued", "indexing", "errors", "stale", "not_indexed") if chiave in riepilogo}
    except Exception as exc:
        esito["indice"] = {"errore": str(exc)[:160]}
    try:
        from web.helpers import get_fascicoli

        ocr_runtime = current_app.extensions.get("ocr_runtime") if has_app_context() else None
        gestore = get_fascicoli()
        if ocr_runtime is not None:
            for oggetto in registro.da_leggere(tenant, fascicolo_id, "ocr", tipi=("documento",)):
                documento = next((d for d in list(getattr(fascicolo, "documenti", []) or []) if str(getattr(d, "id", "")) == oggetto.oggetto_id), None)
                if documento is None:
                    continue
                ocr_runtime.enqueue(
                    percorso=str(gestore.percorso_documento(fascicolo_id, documento.id)),
                    hash_sha256=str(getattr(documento, "hash_sha256", "") or ""),
                    id_fasc=fascicolo_id,
                    id_doc=documento.id,
                    nome_doc=str(getattr(documento, "nome", "") or ""),
                    tipo_doc=str(getattr(getattr(documento, "tipo", None), "value", getattr(documento, "tipo", "")) or ""),
                    index_path=str(current_app.config.get("SEARCH_INDEX", "")),
                )
                esito["ocr_accodati"] += 1
    except Exception as exc:
        esito["ocr"] = {"errore": str(exc)[:160]}
    try:
        from web.services.archivio_letture_runtime import leggi_fascicolo

        esito["archivio"] = leggi_fascicolo(fascicolo, forza=True, registro=registro)
    except Exception as exc:
        esito["archivio"] = {"errore": str(exc)[:160]}
    stato = registro.stato_fascicolo(tenant, fascicolo_id, lettori=("indice_documentale", "ocr", "motore_documenti", "motore_pec"))
    restano = sum(voce.da_leggere for voce in stato.lettori)
    esito["restano"] = restano
    esito["messaggio"] = (
        "Tutti i documenti sono letti." if not restano and stato.oggetti
        else f"{restano} letture ancora in corso o in coda." if restano
        else "Nessun documento da leggere."
    )
    return esito


def oggetti_da_leggere(fascicolo: Any, lettore: str, *, tipi: Iterable[str] | None = None, registro: RegistroLetture | None = None) -> list[Oggetto]:
    """Gli oggetti del fascicolo che il lettore deve ancora leggere (inventario allineato prima)."""
    registro = registro or registro_corrente()
    fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
    aggiorna_inventario(fascicolo, registro=registro, con_pec="pec" in set(tipi or ()) or "allegato_pec" in set(tipi or ()))
    return registro.da_leggere(tenant_corrente(), fascicolo_id, lettore, tipi=tipi)


__all__ = [
    "CHIAVE_PERCORSO", "ImpronteContenuto", "aggiorna_inventario", "cifratura_attiva", "documento_aggiornato",
    "documento_rimosso", "impronte_contenuto", "inventario_fascicolo", "leggi_i_nuovi", "oggetti_da_leggere", "pec_collegata",
    "percorso_registro", "registra_lettura", "registro_corrente", "registro_per_percorsi", "risolvi_anomalia",
    "stato_letture_payload", "tenant_corrente", "utente_corrente_id",
]
