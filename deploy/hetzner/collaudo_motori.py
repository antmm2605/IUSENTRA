"""Collaudo dei motori di lettura, eseguito DENTRO il container scheduler-worker.

Risponde, motore per motore, alle domande dell'avvocato con soli numeri: nessun nome, codice fiscale, oggetto
di PEC o testo esce dal server. Gli studi sono numerati (studio_1, studio_2…) nell'ordine del registro studi,
come in ``verifica_pec_fascicolo.py``. Le fasi si scelgono con la variabile ``FASE`` (anche più di una,
separate da virgola):

- ``INVENTARIO`` (sola lettura): oggetti vivi dei fascicoli (documenti, PEC collegate, allegati) contro il
  registro delle letture; per ogni lettore censito letti, da leggere, in errore, non leggibili, fermi da più
  di 24 ore; coda degli eventi, riga di sintesi, archivio dei fatti e consegne ai presìdi; casella PEC contro
  presidio PEC; coda OCR; ultime esecuzioni delle pianificazioni dei motori.
- ``GIRI``: per ogni pianificazione di ``GIRI_JOBS`` due esecuzioni manuali di fila (come «Esegui» della console
  «Pianificazioni»); il secondo giro deve leggere zero oggetti.
- ``INCREMENTALE`` (solo sul fascicolo di collaudo): aggiunge un documento di prova, lo sostituisce (nuova
  impronta), lo rimuove; deve essere riletto solo quel documento e aggiornata la riga di sintesi.
- ``ERRORI`` (solo sul fascicolo di collaudo): un PDF guasto accanto a uno buono; il guasto non blocca il buono,
  l'errore è scritto nel registro e nel pannello «Letture e verifiche»; sostituito, viene riletto.
- ``PULIZIA`` (solo sul fascicolo di collaudo): elimina i documenti di prova (nome ``collaudo_motori_…``).

Il fascicolo di collaudo si cerca con ``FASCICOLO`` (identificativo o suo prefisso, predefinito il fascicolo
FAS-28 ``474D4C13``) e si accetta solo se il titolo contiene «COLLAUDO» e non c'è un cliente collegato. Con
``CREA=1`` e nessun fascicolo di prova accettabile ne crea uno «COLLAUDO MOTORI – non cliente», senza
cliente, nello studio ``STUDIO`` (predefinito studio_1). Mai una scrittura su un fascicolo di un cliente.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T -e FASE=INVENTARIO scheduler-worker python - < deploy/hetzner/collaudo_motori.py

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (impronta e integrità dei documenti informatici letti).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

MARCATORE = "COLLAUDO_MOTORI_JSON:"
ETICHETTA_PROVA = "COLLAUDO MOTORI – non cliente"
PREFISSO_FILE = "collaudo_motori_"
FASCICOLO_PREDEFINITO = "474D4C13"
JOB_MOTORI = (
    "archivio_letture_automatico", "fascicoli_document_economic_presidio", "pec_audit_pipeline_workers",
    "mailbox_sync_runtime", "pec_fascicolo_documenti_recupero", "legal_notification_relata_presidio",
    "agenda_scadenziario_notifications", "letture_recupero_completo", "lex_sentenza_economia_auto",
    "local_ai_maintenance", "collaudo_lettore",
)
GIRI_PREDEFINITI = (
    "archivio_letture_automatico", "fascicoli_document_economic_presidio", "pec_audit_pipeline_workers",
    "mailbox_sync_runtime", "legal_notification_relata_presidio",
)
_ID = re.compile(r"\b[0-9A-Fa-f]{8,}\b|\b[\w.+-]+@[\w-]+\.[\w.]+\b|/[\w./-]+")
_ESCLUSI = {"tenants", "studi", "items", "details", "casi", "elenco", "fascicoli", "messaggi"}


# ---- utilità --------------------------------------------------------------------------------------------------

def _adesso() -> datetime:
    return datetime.now(timezone.utc)


def _iso(valore: datetime) -> str:
    return valore.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _breve(testo: Any) -> str:
    """Prima riga del messaggio, identificativi, indirizzi e percorsi mascherati: mai un dato del cliente."""
    riga = str(testo or "").strip().splitlines()[0] if str(testo or "").strip() else ""
    return _ID.sub("<ID>", riga)[:120]


def _numeri(valore: Any, prefisso: str = "", profondita: int = 0) -> dict[str, Any]:
    """Solo i numeri e i sì/no di un esito: le stringhe (che possono contenere dati) non escono."""
    out: dict[str, Any] = {}
    if isinstance(valore, dict):
        for chiave, voce in valore.items():
            nome = f"{prefisso}.{chiave}" if prefisso else str(chiave)
            if isinstance(voce, bool) or isinstance(voce, (int, float)):
                out[nome] = voce
            elif isinstance(voce, list):
                out[nome + "#"] = len(voce)
            elif isinstance(voce, dict) and str(chiave) not in _ESCLUSI and profondita < 3:
                out.update(_numeri(voce, nome, profondita + 1))
    return out


def _env_lista(nome: str, predefinito: tuple[str, ...] = ()) -> list[str]:
    grezzo = os.getenv(nome, "").strip()
    return [v.strip() for v in grezzo.split(",") if v.strip()] if grezzo else list(predefinito)


def _pdf(righe: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    y = 780
    for riga in righe:
        pagina.drawString(60, y, riga)
        y -= 22
    pagina.save()
    return buffer.getvalue()


def _pdf_prova(versione: str) -> bytes:
    # Nessuna data, nome o importo: il documento di prova non deve produrre udienze, termini o crediti.
    return _pdf([
        ETICHETTA_PROVA,
        "Documento tecnico di collaudo dei motori di lettura di IUSENTRA.",
        "Non e' un atto, non riguarda alcun cliente e verra' eliminato a fine collaudo.",
        f"Versione del documento di prova: {versione}.",
    ])


PDF_GUASTO = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nstream\n\x00\xff\x13 contenuto troncato"


# ---- contesto degli studi --------------------------------------------------------------------------------------

def _studi(app: Any) -> Iterator[tuple[str, Callable[[], None]]]:
    """(studio_n, funzione che prepara il contesto dello studio dentro una richiesta di prova).

    La funzione porta anche ``slug``: serve ai repository che lo usano come chiave, non esce mai nell'esito.
    """
    if app.config.get("MULTI_TENANT"):
        from pct.tenant import GestioneTenant
        from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for numero, studio in enumerate(_active_tenants(app), start=1):
            prepara = (lambda s=studio: _attach_tenant_context(manager, s))
            prepara.slug = str(getattr(studio, "slug", "") or "tenant")  # type: ignore[attr-defined]
            yield f"studio_{numero}", prepara
        return
    prepara = (lambda: None)
    prepara.slug = "default"  # type: ignore[attr-defined]
    yield "studio_1", prepara


def _percorsi(app: Any) -> Any:
    from flask import g

    return getattr(g, "data_paths", None) or app.config


def _fascicoli_vivi() -> list[Any]:
    from web.helpers import get_fascicoli

    return list(get_fascicoli().tutti(archiviati=True))


# ---- fascicolo di collaudo -------------------------------------------------------------------------------------

def _e_di_prova(fascicolo: Any) -> dict[str, Any]:
    titolo = str(getattr(fascicolo, "titolo", "") or "")
    di_prova = "COLLAUDO" in titolo.upper()
    senza_cliente = not str(getattr(fascicolo, "id_cliente", "") or "").strip() and not str(getattr(fascicolo, "nome_cliente", "") or "").strip()
    return {
        "id": str(getattr(fascicolo, "id", "") or ""),
        "titolo": titolo if di_prova else "(titolo non di collaudo: non riportato)",
        "titolo_di_prova": di_prova,
        "senza_cliente": senza_cliente,
        "accettabile": di_prova and senza_cliente,
        "documenti": len(list(getattr(fascicolo, "documenti", []) or [])),
        "documenti_di_prova": sum(1 for d in getattr(fascicolo, "documenti", []) or [] if str(getattr(d, "nome", "")).startswith(PREFISSO_FILE)),
        "nel_cestino_di_prova": sum(1 for d in getattr(fascicolo, "documenti_cestino", []) or [] if str(getattr(d, "nome", "")).startswith(PREFISSO_FILE)),
    }


def _cerca_fascicolo_prova(fascicoli: list[Any]) -> Any | None:
    cercato = os.getenv("FASCICOLO", FASCICOLO_PREDEFINITO).strip().upper()
    candidati = [f for f in fascicoli if cercato and str(getattr(f, "id", "")).upper().startswith(cercato)]
    candidati += [f for f in fascicoli if str(getattr(f, "titolo", "")).strip() == ETICHETTA_PROVA]
    for fascicolo in candidati:
        if _e_di_prova(fascicolo)["accettabile"]:
            return fascicolo
    return None


# ---- INVENTARIO --------------------------------------------------------------------------------------------------

def _durata(inizio: Any, fine: Any) -> int:
    try:
        return int((datetime.fromisoformat(str(fine).replace("Z", "+00:00")) - datetime.fromisoformat(str(inizio).replace("Z", "+00:00"))).total_seconds())
    except (TypeError, ValueError):
        return 0


def _righe(conn: Any, sql: str, parametri: tuple[Any, ...]) -> list[Any]:
    return list(conn.execute(sql, parametri).fetchall())


def _inventario_registro(app: Any, fascicoli: list[Any], adesso: datetime) -> dict[str, Any]:
    from pct.registro_letture.lettori import LETTORI, livello_lettore, tipi_lettore, versioni_compatibili_lettore
    try:
        from pct.registro_letture.lettori import su_richiesta_lettore
    except ImportError:  # versione senza lettori su richiesta
        def su_richiesta_lettore(_lettore: str) -> bool:
            return False
    from pct.registro_letture.modello import impronta_inventario, impronta_oggetto
    from web.services.registro_letture_runtime import inventario_fascicolo, registro_consultivo, registro_corrente, tenant_corrente

    soglia = _iso(adesso - timedelta(hours=24))
    with registro_consultivo():
        try:
            registro = registro_corrente(sola_lettura=True)
        except Exception as exc:
            return {"registro": {"aperto": False, "motivo": _breve(f"{type(exc).__name__}: {exc}")}}
        tenant = tenant_corrente()
        vivi: dict[str, list[Any]] = {}
        errori_inventario = 0
        for fascicolo in fascicoli:
            try:
                vivi[str(fascicolo.id)] = inventario_fascicolo(fascicolo, con_pec=True)
            except Exception:
                errori_inventario += 1
                vivi[str(fascicolo.id)] = []
        with registro.connection() as conn:
            oggetti = _righe(conn, "SELECT fascicolo_id, tipo, oggetto_id, sha256, sha256_archivio, dimensione, presente, censito_il, aggiornato_il "
                                   "FROM letture_oggetti WHERE tenant_id=?", (tenant,))
            letture = _righe(conn, "SELECT fascicolo_id, tipo, oggetto_id, sha256, lettore, versione_lettore, stato, letto_il, aggiornato_il "
                                   "FROM letture WHERE tenant_id=?", (tenant,))
            righe_fascicoli = _righe(conn, "SELECT fascicolo_id, lettore, impronta, stato, aggiornato_il FROM letture_fascicoli WHERE tenant_id=?", (tenant,))
            eventi = _righe(conn, "SELECT fascicolo_id, stato, attempts, available_at, last_error, last_error_code, lease_until, aggiornato_il "
                                  "FROM letture_eventi WHERE tenant_id=?", (tenant,))
            esiti = _righe(conn, "SELECT fascicolo_id, stato, error_code, iniziato_il, errore, concluso_il FROM letture_eventi_esiti WHERE tenant_id=? ORDER BY iniziato_il", (tenant,))
            sintesi = _righe(conn, "SELECT fascicolo_id, da_leggere, documenti_presenti, pec_collegate, allegati_pec, aggiornato_il "
                                   "FROM letture_sintesi_fascicolo WHERE tenant_id=?", (tenant,))
            anomalie = dict(_righe(conn, "SELECT stato, COUNT(*) FROM letture_anomalie WHERE tenant_id=? GROUP BY stato", (tenant,)))
            fatti = dict(_righe(conn, "SELECT verifica, COUNT(*) FROM letture_fatti WHERE tenant_id=? GROUP BY verifica", (tenant,)))
            consegne = _righe(conn, "SELECT presidio, stato, COUNT(*), SUM(CASE WHEN aggiornato_il < ? THEN 1 ELSE 0 END) "
                                    "FROM letture_consegne WHERE tenant_id=? GROUP BY presidio, stato", (soglia, tenant))

    registro_oggetti = {(r[0], r[1], r[2]): r for r in oggetti}
    per_lettura = {(r[0], r[1], r[2], r[3], r[4]): r for r in letture}
    vivi_chiavi: set[tuple[str, str, str]] = set()
    allineamento: dict[str, Counter] = defaultdict(Counter)
    for fid, elenco in vivi.items():
        for o in elenco:
            if not o.presente:
                continue
            vivi_chiavi.add((fid, o.tipo, o.oggetto_id))
            voce = allineamento[o.tipo]
            voce["vivi"] += 1
            reg = registro_oggetti.get((fid, o.tipo, o.oggetto_id))
            if reg is None or not int(reg[6] or 0):
                voce["vivi_non_censiti"] += 1
            elif o.impronta != impronta_oggetto({"sha256": reg[3], "sha256_archivio": reg[4], "dimensione": reg[5]}):
                voce["impronta_diversa"] += 1
    for (fid, tipo, oid), reg in registro_oggetti.items():
        if int(reg[6] or 0):
            allineamento[tipo]["censiti_presenti"] += 1
            if fid in vivi and (fid, tipo, oid) not in vivi_chiavi:
                allineamento[tipo]["censiti_ma_non_vivi"] += 1

    lettori: dict[str, Any] = {}
    for lettore in LETTORI:
        tipi = set(tipi_lettore(lettore))
        valide = set(versioni_compatibili_lettore(lettore))
        conto: Counter = Counter()
        ultima = ""
        if livello_lettore(lettore) == "fascicolo":
            riga_per_fascicolo = {r[0]: r for r in righe_fascicoli if r[1] == lettore}
            for fid, elenco in vivi.items():
                propri = [o for o in elenco if o.presente and o.tipo in tipi]
                if not propri:
                    continue
                conto["fascicoli_con_oggetti"] += 1
                conto["oggetti"] += len(propri)
                riga = riga_per_fascicolo.get(fid)
                if riga is None and su_richiesta_lettore(lettore):
                    conto["fascicoli_non_pertinenti"] += 1
                    continue
                if riga is None:
                    conto["fascicoli_mai_letti"] += 1
                    continue
                ultima = max(ultima, str(riga[4] or ""))
                if str(riga[3]) == "completa" and str(riga[2]) in {impronta_inventario(propri), impronta_inventario([o for o in elenco if o.presente])}:
                    conto["fascicoli_aggiornati"] += 1
                elif str(riga[3]) == "completa":
                    conto["fascicoli_impronta_superata"] += 1
                    conto["fermi_oltre_24h"] += int(str(riga[4] or "") < soglia)
                else:
                    conto[f"fascicoli_{riga[3]}"] += 1
            lettori[lettore] = {"livello": "fascicolo", **conto, "ultima": ultima}
            continue
        for fid, elenco in vivi.items():
            for o in elenco:
                if not o.presente or o.tipo not in tipi:
                    continue
                conto["oggetti"] += 1
                riga = per_lettura.get((fid, o.tipo, o.oggetto_id, o.impronta, lettore))
                if riga is None and su_richiesta_lettore(lettore):
                    conto["non_richiesti"] += 1
                    continue
                if riga is None:
                    conto["da_leggere"] += 1
                    reg = registro_oggetti.get((fid, o.tipo, o.oggetto_id))
                    if reg is None:
                        conto["da_leggere_non_censiti"] += 1
                    elif str(reg[8] or reg[7] or "") < soglia:
                        conto["fermi_oltre_24h"] += 1
                    continue
                stato = str(riga[6])
                conto[stato] += 1
                if stato == "letto":
                    ultima = max(ultima, str(riga[7] or ""))
                    if valide and str(riga[5]) not in valide:
                        conto["letti_versione_precedente"] += 1
                if stato == "in_corso" and str(riga[8] or "") < soglia:
                    conto["fermi_oltre_24h"] += 1
                if stato == "errore" and str(riga[8] or "") < soglia:
                    conto["errori_oltre_24h"] += 1
        conto["letture_ultime_24h"] = sum(1 for r in letture if r[4] == lettore and str(r[7] or "") >= soglia)
        lettori[lettore] = {"livello": "oggetto", **conto, "ultima": ultima}

    adesso_iso = _iso(adesso)
    stato_eventi = Counter(str(r[1]) for r in eventi)
    ultimo_esito: dict[str, str] = {}
    ripresi = 0
    errore_visto: set[str] = set()
    for fid, stato, _codice, _inizio, _errore, _fine in esiti:
        if stato in {"failed", "expired"}:
            errore_visto.add(fid)
        elif stato == "succeeded" and fid in errore_visto:
            ripresi += 1
            errore_visto.discard(fid)
        ultimo_esito[fid] = stato
    sintesi_ids = {r[0] for r in sintesi}
    return {
        "registro": {"aperto": True, "backend": getattr(registro, "backend_kind", "")},
        "fascicoli": len(fascicoli),
        "errori_inventario_vivo": errori_inventario,
        "inventario": {tipo: dict(c) for tipo, c in sorted(allineamento.items())},
        "lettori": lettori,
        "eventi": {
            "per_stato": dict(stato_eventi),
            "con_errore": sum(1 for r in eventi if str(r[4] or "")),
            "abbandonati_con_errore": sum(1 for r in eventi if str(r[1]) == "idle" and str(r[4] or "")),
            "codici_errore": dict(Counter(str(r[5]) for r in eventi if str(r[4] or ""))),
            "lease_scaduta": sum(1 for r in eventi if str(r[1]) == "running" and str(r[6] or "") and str(r[6]) < adesso_iso),
            "pending_oltre_24h": sum(1 for r in eventi if str(r[1]) == "pending" and str(r[7] or "") < soglia),
            "esiti_ultime_24h": dict(Counter(str(r[1]) for r in esiti if str(r[3] or "") >= soglia)),
            "fascicoli_ripresi_dopo_errore": ripresi,
            "fascicoli_ultimo_esito_errore": sum(1 for s in ultimo_esito.values() if s in {"failed", "expired"}),
            "fascicoli_ultimo_esito_errore_esistenti": sum(1 for f, s in ultimo_esito.items() if s in {"failed", "expired"} and f in vivi),
            "errori_24h_per_codice": dict(Counter(f"{r[1]}:{r[2]}" for r in esiti if str(r[1]) in {"failed", "expired"} and str(r[3] or "") >= soglia)),
            "errori_24h_motivi": dict(Counter(_breve(r[4]) for r in esiti if str(r[1]) in {"failed", "expired"} and str(r[3] or "") >= soglia).most_common(6)),
            "durata_s_riusciti_24h_max": max([_durata(r[3], r[5]) for r in esiti if str(r[1]) == "succeeded" and str(r[3] or "") >= soglia] or [0]),
            "fascicoli_distinti_in_errore_24h": len({r[0] for r in esiti if str(r[1]) in {"failed", "expired"} and str(r[3] or "") >= soglia}),
            "pending_con_tentativi": sum(1 for r in eventi if str(r[1]) == "pending" and int(r[2] or 0) > 0),
            "pending_in_attesa_di_riprova": sum(1 for r in eventi if str(r[1]) == "pending" and str(r[3] or "") > adesso_iso),
        },
        "sintesi": {
            "righe": len(sintesi),
            "fascicoli_senza_riga": sum(1 for f in fascicoli if str(f.id) not in sintesi_ids),
            "righe_con_da_leggere": sum(1 for r in sintesi if int(r[1] or 0) > 0),
            "oggetti_da_leggere_dichiarati": sum(int(r[1] or 0) for r in sintesi),
            "righe_non_aggiornate_24h_con_da_leggere": sum(1 for r in sintesi if int(r[1] or 0) > 0 and str(r[5] or "") < soglia),
        },
        "fascicoli_censiti_ma_inesistenti": len({k[0] for k, r in registro_oggetti.items() if int(r[6] or 0)} - set(vivi)),
        "anomalie": anomalie,
        "fatti": fatti,
        "consegne": {f"{r[0]}:{r[1]}": {"n": int(r[2]), "oltre_24h": int(r[3] or 0)} for r in consegne},
    }


def _inventario_pec(app: Any, adesso: datetime, slug: str) -> dict[str, Any]:
    soglia = _iso(adesso - timedelta(hours=24))
    out: dict[str, Any] = {}
    chiavi_casella: set[str] = set()
    try:
        from web.services.email_storage_runtime import create_email_mailbox

        percorso = _percorsi(app).get("EMAIL_CASELLA_DB")
        casella = create_email_mailbox(percorso, load_catalog=False, allow_initialize=False)
        repo = getattr(casella, "repository", None)
        if repo is not None:
            righe = repo.db.conn.execute(
                "SELECT folder, message_key FROM email_mailbox_records WHERE tenant_key=? AND mailbox_kind=?", (repo.tenant, repo.kind)).fetchall()
            out["casella"] = dict(Counter(str(r[0]) for r in righe))
            chiavi_casella = {str(r[1]) for r in righe if str(r[0]) == "INBOX"}
        else:
            elenco = casella.tutte()
            out["casella"] = dict(Counter(str(getattr(e, "cartella", "")) for e in elenco))
            chiavi_casella = {str(getattr(e, "id", "")) for e in elenco if str(getattr(e, "cartella", "")) == "INBOX"}
    except Exception as exc:
        out["casella"] = {"errore": _breve(type(exc).__name__)}
    try:
        from web.services.pec_pipeline_runtime import repository_for_current_request

        repo = repository_for_current_request()
        t = repo.tenant_id
        with repo.connect() as conn:
            def gruppi(sql: str, *parametri: Any) -> dict[str, int]:
                return {str(r[0]): int(r[1]) for r in conn.execute(sql, (t, *parametri)).fetchall()}

            esaminate = {str(r[0]) for r in conn.execute("SELECT DISTINCT email_id FROM pec_local_acquire_items WHERE tenant_id=?", (t,)).fetchall()}
            ultimi = gruppi(
                "SELECT i.status, COUNT(*) FROM pec_local_acquire_items i JOIN (SELECT email_id, MAX(updated_at) u FROM pec_local_acquire_items "
                "WHERE tenant_id=? GROUP BY email_id) x ON x.email_id=i.email_id AND x.u=i.updated_at GROUP BY i.status", )
            out["presidio"] = {
                "messaggi": int(conn.execute("SELECT COUNT(*) FROM pec_messages WHERE tenant_id=?", (t,)).fetchone()[0]),
                "per_stato": gruppi("SELECT status, COUNT(*) FROM pec_messages WHERE tenant_id=? GROUP BY status"),
                "collegati_a_fascicolo": int(conn.execute("SELECT COUNT(*) FROM pec_messages WHERE tenant_id=? AND linked_fascicolo_id<>''", (t,)).fetchone()[0]),
                "allegati_ultima_versione": int(conn.execute(
                    "SELECT COUNT(*) FROM pec_attachments a JOIN pec_messages m ON m.id=a.message_id WHERE m.tenant_id=? AND a.parsed_version_id="
                    "(SELECT v.id FROM pec_parsed_versions v WHERE v.message_id=a.message_id ORDER BY v.version DESC LIMIT 1)", (t,)).fetchone()[0]),
                "allegati_con_testo": int(conn.execute(
                    "SELECT COUNT(*) FROM pec_attachments a JOIN pec_messages m ON m.id=a.message_id WHERE m.tenant_id=? AND a.ocr_text<>'' AND a.parsed_version_id="
                    "(SELECT v.id FROM pec_parsed_versions v WHERE v.message_id=a.message_id ORDER BY v.version DESC LIMIT 1)", (t,)).fetchone()[0]),
                "messaggi_senza_lettura": int(conn.execute(
                    "SELECT COUNT(*) FROM pec_messages m WHERE m.tenant_id=? AND NOT EXISTS (SELECT 1 FROM pec_parsed_versions v WHERE v.message_id=m.id)", (t,)).fetchone()[0]),
                "acquisizione_ultimo_esito": ultimi,
                "lavori": gruppi("SELECT job_type || ':' || status, COUNT(*) FROM pec_jobs WHERE tenant_id=? GROUP BY 1"),
                "lavori_in_coda_oltre_24h": int(conn.execute(
                    "SELECT COUNT(*) FROM pec_jobs WHERE tenant_id=? AND status IN ('queued','running') AND created_at < ?", (t, soglia)).fetchone()[0]),
            }
        try:
            from web.services.pec_pipeline_runtime import _archive_fingerprint

            archivio = Path(str(_percorsi(app).get("EMAIL_CASELLA_DB") or ""))
            cursore = repo.latest_local_acquire_cursor(origin="auto") or {}
            out["acquisizione_cursore"] = {
                "file_casella_presente": archivio.is_file(),
                "backlog_completo": bool(cursore.get("backlog_complete")),
                "impronta_uguale_all_ultimo_giro": bool(cursore.get("archive_fingerprint")) and cursore.get("archive_fingerprint") == _archive_fingerprint(archivio),
                "impronta_da_catalogo_sql": str(_archive_fingerprint(archivio)).startswith("sql:"),
            }
        except Exception as exc:
            out["acquisizione_cursore"] = {"errore": _breve(type(exc).__name__)}
        if chiavi_casella:
            out["casella_inbox_mai_esaminate_dal_presidio"] = len(chiavi_casella - esaminate)
            out["esaminate_non_piu_in_casella"] = len(esaminate - chiavi_casella)
    except Exception as exc:
        out["presidio"] = {"errore": _breve(type(exc).__name__)}
    try:
        from web.services.pec_fascicolo_documenti_runtime import stato_per_studi

        voce = (stato_per_studi([(slug, dict(_percorsi(app)))]) or [{}])[0]
        voce.pop("studio", None)
        out["pec_fascicolo_documenti"] = {k: v for k, v in voce.items() if k != "ultimo_giro"} | {"ultimo_giro": _numeri(voce.get("ultimo_giro") or {})}
    except Exception as exc:
        out["pec_fascicolo_documenti"] = {"errore": _breve(type(exc).__name__)}
    return out


def _coda_ocr(app: Any, adesso: datetime) -> dict[str, Any]:
    import sqlite3

    soglia = (datetime.now() - timedelta(hours=24)).isoformat()  # la coda OCR scrive l'ora locale del container, senza fuso
    out: dict[str, Any] = {}
    percorsi = {str((Path(str(app.config.get("SEARCH_INDEX") or "./data/search/index.db")).parent / "ocr_jobs.db").resolve())}
    for numero, percorso in enumerate(sorted(percorsi), start=1):
        if not Path(percorso).is_file():
            out[f"coda_{numero}"] = {"presente": False}
            continue
        try:
            conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=10)
            out[f"coda_{numero}"] = {
                "per_stato": {str(r[0]): int(r[1]) for r in conn.execute("SELECT status, COUNT(*) FROM ocr_jobs GROUP BY status")},
                "aperti_oltre_24h": int(conn.execute(
                    "SELECT COUNT(*) FROM ocr_jobs WHERE status IN ('pending','processing') AND updated_at < ?", (soglia,)).fetchone()[0]),
                "con_errore": int(conn.execute("SELECT COUNT(*) FROM ocr_jobs WHERE last_error<>''").fetchone()[0]),
            }
            conn.close()
        except Exception as exc:
            out[f"coda_{numero}"] = {"errore": _breve(type(exc).__name__)}
    return out


def _pianificazioni(app: Any) -> dict[str, Any]:
    from pct.scheduler_registry import scheduler_registry_repository

    repo = scheduler_registry_repository(app.config)
    dal = _iso(_adesso() - timedelta(hours=48))
    out: dict[str, Any] = {}
    with repo.connect() as conn:  # sola lettura
        for job in JOB_MOTORI:
            ultima = conn.execute(
                "SELECT origin, status, started_at, duration_ms, result_json, error_message FROM scheduled_job_runs "
                "WHERE job_id=? AND status IN ('completed','failed') ORDER BY id DESC LIMIT 1", (job,)).fetchone()
            conteggi = {str(r[0]): int(r[1]) for r in conn.execute(
                "SELECT status, COUNT(*) FROM scheduled_job_runs WHERE job_id=? AND created_at>=? GROUP BY status", (job, dal))}
            voce: dict[str, Any] = {"ultime_48h": conteggi}
            if ultima:
                try:
                    risultato = json.loads(ultima[4] or "{}")
                except ValueError:
                    risultato = {}
                voce.update({"origine": ultima[0], "esito": ultima[1], "inizio": ultima[2], "durata_s": round(int(ultima[3] or 0) / 1000, 1),
                             "numeri": _numeri(risultato), "errore": _breve(ultima[5])})
            out[job] = voce
    return out


def fase_inventario(app: Any) -> dict[str, Any]:
    adesso = _adesso()
    studi: list[dict[str, Any]] = []
    prova: dict[str, Any] = {"trovato": False}
    for etichetta, prepara in _studi(app):
        with app.test_request_context(f"/__collaudo-motori/{etichetta}"):
            prepara()
            voce: dict[str, Any] = {"studio": etichetta}
            try:
                fascicoli = _fascicoli_vivi()
                voce.update(_inventario_registro(app, fascicoli, adesso))
                candidato = _cerca_fascicolo_prova(fascicoli)
                if candidato is not None and not prova["trovato"]:
                    prova = {"trovato": True, "studio": etichetta, **_e_di_prova(candidato)}
            except Exception as exc:
                voce["errore"] = _breve(f"{type(exc).__name__}: {exc}")
            voce["pec"] = _inventario_pec(app, adesso, getattr(prepara, "slug", "default"))
            studi.append(voce)
    try:
        diagnosi = _diagnosi_eventi(app)
    except Exception as exc:
        diagnosi = {"errore": _breve(f"{type(exc).__name__}: {exc}")}
    try:
        pianificazioni = _pianificazioni(app)
    except Exception as exc:  # registro delle pianificazioni non raggiungibile
        pianificazioni = {"errore": _breve(type(exc).__name__)}
    return {"istante": _iso(adesso), "studi": studi, "fascicolo_di_collaudo": prova,
            "coda_ocr": _coda_ocr(app, adesso), "pianificazioni": pianificazioni,
            "diagnosi_eventi_non_disponibile": diagnosi}


def _diagnosi_eventi(app: Any) -> dict[str, Any]:
    """Sola lettura: i fascicoli con ultimo esito «Fascicolo accodato non disponibile» si cercano nel contesto
    dello studio e nel contesto che il thread di lettura si costruisce (avvia_lettura_in_background)."""
    from flask import g

    from web.services.archivio_letture_runtime import _studi_della_coda
    from web.services.registro_letture_runtime import registro_per_percorsi

    out: dict[str, Any] = {}
    for numero, (slug, paths) in enumerate(_studi_della_coda(app), start=1):
        voce: dict[str, Any] = {}
        try:
            registro = registro_per_percorsi(paths, sola_lettura=True)
            with registro.connection() as conn:
                ids = [str(r[0]) for r in conn.execute(
                    "SELECT e.fascicolo_id FROM letture_eventi_esiti e WHERE e.tenant_id=? AND e.errore LIKE 'Fascicolo accodato%' "
                    "GROUP BY e.fascicolo_id ORDER BY MAX(e.iniziato_il) DESC LIMIT 8", (slug,))]
            voce["campione"] = len(ids)
            esiti: Counter = Counter()
            for fid in ids:
                with app.test_request_context("/__collaudo-motori/thread"):
                    g.data_paths = dict(paths or {})
                    g.tenant = None
                    g.tenant_context_slug = slug
                    g.tenant_context_required = False
                    g.tenant_context_missing = False
                    g.storage_runtime = None
                    if slug and app.config.get("MULTI_TENANT"):
                        from pct.tenant import GestioneTenant

                        g.tenant = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]).get(slug)
                    from web.helpers import _studio_db, get_fascicoli
                    from web.services.storage_runtime import get_request_storage_runtime

                    gestore = get_fascicoli()
                    profilo = get_request_storage_runtime(str(paths.get("FASCICOLI_DB") or ""))
                    trovato_thread = gestore.get(fid) is not None
                    esiti[f"thread:{'trovato' if trovato_thread else 'NON trovato'}"] += 1
                    esiti[f"thread_tenant:{'presente' if g.tenant is not None else 'assente'}"] += 1
                    esiti[f"thread_archivio:{getattr(profilo, 'effective_mode', '?')}:studio_db={'si' if _studio_db('FASCICOLI_DB') is not None else 'no'}"] += 1
                    esiti[f"thread_carico_completo:{len(gestore._fascicoli)}"] += 0
                    tutti = {str(f.id) for f in gestore.tutti(archiviati=True)}
                    esiti[f"thread_in_elenco_completo:{'si' if fid in tutti else 'no'}"] += 1
                    esiti[f"thread_fascicoli_in_elenco:{len(tutti)}"] += 0
            voce["esiti"] = {k: v for k, v in esiti.items()}
        except Exception as exc:
            voce["errore"] = _breve(f"{type(exc).__name__}: {exc}")
        out[f"studio_{numero}"] = voce
    return out


# ---- GIRI: due esecuzioni manuali di fila ------------------------------------------------------------------------

def _letture_scritte_dal(app: Any, dal: str) -> dict[str, int]:
    from web.services.registro_letture_runtime import registro_consultivo, registro_corrente, tenant_corrente

    totale: Counter = Counter()
    for etichetta, prepara in _studi(app):
        with app.test_request_context(f"/__collaudo-motori/{etichetta}"):
            prepara()
            try:
                with registro_consultivo():
                    registro = registro_corrente(sola_lettura=True)
                    with registro.connection() as conn:
                        for lettore, quante in conn.execute(
                                "SELECT lettore, COUNT(*) FROM letture WHERE tenant_id=? AND aggiornato_il>=? GROUP BY lettore", (tenant_corrente(), dal)):
                            totale[str(lettore)] += int(quante)
            except Exception:
                continue
    return dict(totale)


def _esegui_e_attendi(repo: Any, job: str, attesa_s: int) -> dict[str, Any]:
    inizio = _iso(_adesso())
    richiesta = repo.request_manual_run(job, requested_by="collaudo-motori", dedupe_open=True)
    run_id = str(richiesta.get("run_id") or "")
    limite = time.monotonic() + attesa_s
    riga = None
    while time.monotonic() < limite:
        with repo.connect() as conn:
            riga = conn.execute("SELECT status, started_at, finished_at, duration_ms, result_json, error_message FROM scheduled_job_runs "
                                "WHERE run_id=? ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
        if riga and str(riga[0]) in {"completed", "failed", "cancelled", "missed"}:
            break
        time.sleep(10)
    if not riga or str(riga[0]) not in {"completed", "failed", "cancelled", "missed"}:
        return {"run_id": run_id[:8], "esito": "non concluso entro l'attesa", "richiesta_il": inizio, "replica": bool(richiesta.get("replayed"))}
    try:
        risultato = json.loads(riga[4] or "{}")
    except ValueError:
        risultato = {}
    return {"run_id": run_id[:8], "esito": str(riga[0]), "inizio": str(riga[1]), "durata_s": round(int(riga[3] or 0) / 1000, 1),
            "numeri": _numeri(risultato), "errore": _breve(riga[5]), "replica": bool(richiesta.get("replayed"))}


def fase_giri(app: Any) -> dict[str, Any]:
    from pct.scheduler_registry import scheduler_registry_repository

    repo = scheduler_registry_repository(app.config)
    attesa = max(60, int(os.getenv("GIRO_ATTESA_S", "1500") or 1500))
    out: dict[str, Any] = {}
    for job in _env_lista("GIRI_JOBS", GIRI_PREDEFINITI):
        giri = []
        for numero in (1, 2):
            dal = _iso(_adesso())
            esito = _esegui_e_attendi(repo, job, attesa)
            esito["letture_scritte_nel_frattempo"] = _letture_scritte_dal(app, dal)
            giri.append({"giro": numero, **esito})
        out[job] = giri
    return {"giri": out}


# ---- operazioni sul fascicolo di collaudo -------------------------------------------------------------------------

class FascicoloDiProva:
    """Le sole scritture del collaudo: documenti di prova su un fascicolo di prova senza cliente."""

    def __init__(self, app: Any, fascicolo_id: str) -> None:
        from web.helpers import get_fascicoli
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        self.app = app
        self.id = fascicolo_id
        self.gf = get_fascicoli()
        self.registro = registro_corrente()
        self.tenant = tenant_corrente()
        controllo = _e_di_prova(self.gf.get(fascicolo_id))
        if not controllo["accettabile"]:
            raise RuntimeError("Il fascicolo indicato non è un fascicolo di prova senza cliente: nessuna scrittura.")

    def fascicolo(self) -> Any:
        return self.gf.get(self.id)

    def carica(self, nome: str, contenuto: bytes) -> Any:
        """Come il caricamento dell'avvocato: file cifrato, coda OCR, evento del registro."""
        from pct.fascicoli import TipoDocumento
        from web.services.document_crypto import encrypt_doc
        from web.services.ocr_runtime import build_ocr_runtime
        from web.services.registro_letture_runtime import documento_aggiornato

        assert nome.startswith(PREFISSO_FILE)
        documento = self.gf.aggiungi_documento(
            self.id, nome_file=nome, tipo=TipoDocumento.ALTRO, contenuto=encrypt_doc(contenuto), note=ETICHETTA_PROVA,
            caricato_da="collaudo-motori", hash_contenuto_sha256=hashlib.sha256(contenuto).hexdigest())
        self._accoda_ocr(documento, nome, build_ocr_runtime)
        documento_aggiornato(self.id, documento)
        return documento

    def sostituisci(self, documento_id: str, nome: str, contenuto: bytes) -> Any:
        from web.services.document_crypto import encrypt_doc
        from web.services.ocr_runtime import build_ocr_runtime
        from web.services.registro_letture_runtime import documento_aggiornato

        documento = self.gf.sostituisci_documento(self.id, documento_id, nome_file=nome, contenuto=encrypt_doc(contenuto),
                                                  caricato_da="collaudo-motori", hash_contenuto_sha256=hashlib.sha256(contenuto).hexdigest())
        self._accoda_ocr(documento, nome, build_ocr_runtime)
        documento_aggiornato(self.id, documento)
        return documento

    def rimuovi(self, documento_id: str) -> None:
        from web.services.registro_letture_runtime import documento_rimosso

        self.gf.rimuovi_documento(self.id, documento_id, eliminato_da="collaudo-motori")
        documento_rimosso(self.id, documento_id)

    def _accoda_ocr(self, documento: Any, nome: str, build_ocr_runtime: Any) -> None:
        try:
            build_ocr_runtime(search_index_path=self.app.config["SEARCH_INDEX"], auto_start_embedded=False).enqueue(
                percorso=str(self.gf.percorso_documento(self.id, documento.id)), hash_sha256=documento.hash_sha256, id_fasc=self.id,
                id_doc=documento.id, nome_doc=nome, tipo_doc=str(getattr(documento.tipo, "value", documento.tipo)),
                index_path=self.app.config["SEARCH_INDEX"])
        except Exception:
            pass  # la coda OCR non blocca il caricamento, come nell'app

    # -- fotografie del registro per il solo fascicolo di prova --

    def fotografia(self) -> dict[str, Any]:
        with self.registro.connection() as conn:
            letture = {(r[0], r[1], r[2], r[3]): (str(r[4]), str(r[5])) for r in conn.execute(
                "SELECT tipo, oggetto_id, sha256, lettore, stato, aggiornato_il FROM letture WHERE tenant_id=? AND fascicolo_id=?", (self.tenant, self.id))}
            fascicolo = {str(r[0]): (str(r[1]), str(r[2]), str(r[3])) for r in conn.execute(
                "SELECT lettore, impronta, stato, aggiornato_il FROM letture_fascicoli WHERE tenant_id=? AND fascicolo_id=?", (self.tenant, self.id))}
            sintesi = conn.execute("SELECT documenti_presenti, da_leggere, impronta_inventario, aggiornato_il FROM letture_sintesi_fascicolo "
                                   "WHERE tenant_id=? AND fascicolo_id=?", (self.tenant, self.id)).fetchone()
            presenti = int(conn.execute("SELECT COUNT(*) FROM letture_oggetti WHERE tenant_id=? AND fascicolo_id=? AND tipo='documento' AND presente=1",
                                        (self.tenant, self.id)).fetchone()[0])
        return {"letture": letture, "fascicolo": fascicolo, "presenti": presenti,
                "sintesi": {"documenti_presenti": int(sintesi[0]), "da_leggere": int(sintesi[1]), "impronta": str(sintesi[2])[:12], "aggiornato_il": str(sintesi[3])} if sintesi else None}

    def letture_oggetto(self, oggetto_id: str, sha256: str) -> dict[str, str]:
        with self.registro.connection() as conn:
            return {str(r[0]): str(r[1]) for r in conn.execute(
                "SELECT lettore, stato FROM letture WHERE tenant_id=? AND fascicolo_id=? AND tipo='documento' AND oggetto_id=? AND sha256=?",
                (self.tenant, self.id, oggetto_id, sha256))}

    def impronta_registro(self, oggetto_id: str) -> str:
        oggetto = self.registro.oggetto(self.tenant, self.id, "documento", oggetto_id)
        return oggetto.impronta if oggetto else ""

    def attendi(self, oggetti: list[str], *, attesa_s: int, lettori: tuple[str, ...] = ("motore_documenti",)) -> dict[str, Any]:
        """Aspetta che i motori abbiano un esito per gli oggetti; poi, se serve, un giro sincrono come lo scheduler."""
        limite = time.monotonic() + attesa_s
        inizio = time.monotonic()
        while True:
            mancano = [o for o in oggetti if any(l not in self.letture_oggetto(o, self.impronta_registro(o)) for l in lettori)]
            if not mancano or time.monotonic() >= limite:
                break
            time.sleep(15)
        esito: dict[str, Any] = {"secondi_di_attesa": round(time.monotonic() - inizio), "letti_entro_attesa": not mancano}
        if mancano:
            from web.services.archivio_letture_runtime import leggi_fascicolo

            giro = leggi_fascicolo(self.fascicolo(), registro=self.registro)
            esito["giro_sincrono_del_collaudo"] = {"documenti": _numeri(giro.get("documenti") or {}), "restano": giro.get("restano")}
        return esito

    def attendi_sintesi(self, *, attesa_s: int) -> dict[str, Any]:
        """Dopo una rimozione nessun motore legge: deve cambiare la riga di sintesi (documenti presenti)."""
        limite = time.monotonic() + attesa_s
        inizio = time.monotonic()
        while True:
            foto = self.fotografia()
            allineata = (foto["sintesi"] or {}).get("documenti_presenti") == foto["presenti"]
            if allineata or time.monotonic() >= limite:
                break
            time.sleep(15)
        esito: dict[str, Any] = {"secondi_di_attesa": round(time.monotonic() - inizio), "sintesi_allineata_entro_attesa": allineata}
        if not allineata:
            from web.services.archivio_letture_runtime import leggi_fascicolo

            giro = leggi_fascicolo(self.fascicolo(), registro=self.registro)
            esito["giro_sincrono_del_collaudo"] = {"documenti": _numeri(giro.get("documenti") or {}), "restano": giro.get("restano")}
        return esito

    def confronta(self, prima: dict[str, Any], dopo: dict[str, Any], oggetti_di_prova: set[str]) -> dict[str, Any]:
        """Che cosa è stato (ri)letto tra le due fotografie: solo gli oggetti di prova devono comparire."""
        nuovi_prova: Counter = Counter()
        altri: Counter = Counter()
        arretrato: Counter = Counter()
        for chiave, (stato, aggiornato) in dopo["letture"].items():
            precedente = prima["letture"].get(chiave)
            if precedente is not None and precedente[1] == aggiornato:
                continue
            if chiave[1] in oggetti_di_prova:
                nuovi_prova[f"{chiave[3]}:{stato}"] += 1
            elif precedente is None:  # prima lettura di un oggetto rimasto indietro: non è una rilettura
                arretrato[f"{chiave[3]}:{stato}"] += 1
            else:
                altri[f"{chiave[3]}:{stato}"] += 1
        livello_fascicolo = {l: "riesaminato" for l, v in dopo["fascicolo"].items() if prima["fascicolo"].get(l) != v}
        return {"letture_oggetti_di_prova": dict(nuovi_prova), "letture_altri_oggetti": dict(altri),
                "prime_letture_altri_oggetti": dict(arretrato),
                "altri_oggetti_riletti": sum(altri.values()), "lettori_di_fascicolo_riesaminati": livello_fascicolo,
                "sintesi_prima": prima["sintesi"], "sintesi_dopo": dopo["sintesi"],
                "sintesi_aggiornata": prima["sintesi"] != dopo["sintesi"],
                "sintesi_coerente_col_registro": (dopo["sintesi"] or {}).get("documenti_presenti") == dopo["presenti"],
                "documenti_presenti_registro": [prima["presenti"], dopo["presenti"]]}

    def pannello(self, oggetto_id: str) -> dict[str, Any]:
        """Che cosa mostra il pannello «Letture e verifiche» per l'oggetto (senza segnare la vista)."""
        from web.services.registro_letture_runtime import stato_letture_payload

        payload = stato_letture_payload(self.fascicolo(), registro=self.registro, segna_visto=False)
        voce = next((v for v in payload.get("per_oggetto") or [] if str(v.get("oggetto_id")) == oggetto_id), None)
        return {"oggetto_nel_pannello": voce is not None, "stati_nel_pannello": dict((voce or {}).get("letture") or {}),
                "tutto_letto": bool(payload.get("tutto_letto")), "degradato": len(payload.get("degradato") or []),
                "lettori": {v.get("lettore"): {"letti": v.get("letti"), "da_leggere": v.get("da_leggere"), "errori": v.get("errori")} for v in payload.get("lettori") or []}}

    def motivo(self, oggetto_id: str, sha256: str) -> dict[str, str]:
        with self.registro.connection() as conn:
            righe = conn.execute("SELECT lettore, stato, esito_json FROM letture WHERE tenant_id=? AND fascicolo_id=? AND oggetto_id=? AND sha256=? "
                                 "AND stato IN ('errore','non_leggibile')", (self.tenant, self.id, oggetto_id, sha256)).fetchall()
        out = {}
        for lettore, stato, esito in righe:
            try:
                motivo = str((json.loads(esito or "{}") or {}).get("motivo") or (json.loads(esito or "{}") or {}).get("errore") or "")
            except ValueError:
                motivo = ""
            out[str(lettore)] = f"{stato}: {_breve(motivo)}"
        return out


def _con_fascicolo_di_prova(app: Any, azione: Callable[[FascicoloDiProva], dict[str, Any]]) -> dict[str, Any]:
    scelto = os.getenv("STUDIO", "studio_1").strip() or "studio_1"
    for etichetta, prepara in _studi(app):
        with app.test_request_context(f"/__collaudo-motori/{etichetta}"):
            prepara()
            fascicoli = _fascicoli_vivi()
            fascicolo = _cerca_fascicolo_prova(fascicoli)
            if fascicolo is None and os.getenv("CREA", "").strip() == "1" and etichetta == scelto:
                from pct.fascicoli import TipoFascicolo
                from web.helpers import get_fascicoli

                fascicolo = get_fascicoli().nuovo(ETICHETTA_PROVA, TipoFascicolo.ALTRO, note=ETICHETTA_PROVA)
            if fascicolo is None:
                continue
            prova = FascicoloDiProva(app, str(fascicolo.id))
            return {"studio": etichetta, "fascicolo": _e_di_prova(prova.fascicolo()), **azione(prova)}
    return {"errore": "Nessun fascicolo di collaudo accettabile (titolo con «COLLAUDO», senza cliente). Rilanciare con CREA=1."}


def _incrementale(prova: FascicoloDiProva) -> dict[str, Any]:
    attesa = int(os.getenv("ATTESA_S", "360") or 360)
    passi: dict[str, Any] = {}
    prima = prova.fotografia()
    documento = prova.carica(f"{PREFISSO_FILE}incrementale.pdf", _pdf_prova("1"))
    passi["aggiunta"] = {"attesa": prova.attendi([documento.id], attesa_s=attesa)}
    dopo = prova.fotografia()
    passi["aggiunta"].update(prova.confronta(prima, dopo, {documento.id}))
    passi["aggiunta"]["letture_del_documento"] = prova.letture_oggetto(documento.id, prova.impronta_registro(documento.id))

    prima = dopo
    impronta_vecchia = prova.impronta_registro(documento.id)
    prova.sostituisci(documento.id, f"{PREFISSO_FILE}incrementale.pdf", _pdf_prova("2 (modificata)"))
    impronta_nuova = prova.impronta_registro(documento.id)
    passi["modifica"] = {"impronta_cambiata": bool(impronta_nuova) and impronta_nuova != impronta_vecchia,
                         "attesa": prova.attendi([documento.id], attesa_s=attesa)}
    dopo = prova.fotografia()
    passi["modifica"].update(prova.confronta(prima, dopo, {documento.id}))
    passi["modifica"]["letture_nuova_impronta"] = prova.letture_oggetto(documento.id, impronta_nuova)

    prima = dopo
    prova.rimuovi(documento.id)
    passi["rimozione"] = {"attesa": prova.attendi_sintesi(attesa_s=attesa)}
    dopo = prova.fotografia()
    passi["rimozione"].update(prova.confronta(prima, dopo, {documento.id}))
    passi["rimozione"]["nel_registro_ancora_presente"] = bool(prova.registro.oggetto(prova.tenant, prova.id, "documento", documento.id)
                                                              and prova.registro.oggetto(prova.tenant, prova.id, "documento", documento.id).presente)
    return {"incrementale": passi}


def _errori(prova: FascicoloDiProva) -> dict[str, Any]:
    attesa = int(os.getenv("ATTESA_S", "360") or 360)
    prima = prova.fotografia()
    guasto = prova.carica(f"{PREFISSO_FILE}guasto.pdf", PDF_GUASTO)
    buono = prova.carica(f"{PREFISSO_FILE}buono.pdf", _pdf_prova("buono"))
    attesa_1 = prova.attendi([guasto.id, buono.id], attesa_s=attesa)
    dopo = prova.fotografia()
    impronta_guasto = prova.impronta_registro(guasto.id)
    esito: dict[str, Any] = {
        "attesa": attesa_1,
        "guasto": {"letture": prova.letture_oggetto(guasto.id, impronta_guasto), "motivi": prova.motivo(guasto.id, impronta_guasto),
                   "pannello": prova.pannello(guasto.id)},
        "buono": {"letture": prova.letture_oggetto(buono.id, prova.impronta_registro(buono.id))},
        **prova.confronta(prima, dopo, {guasto.id, buono.id}),
    }
    prova.sostituisci(guasto.id, f"{PREFISSO_FILE}guasto.pdf", _pdf_prova("riparato"))
    impronta_riparata = prova.impronta_registro(guasto.id)
    esito["dopo_la_sostituzione"] = {"attesa": prova.attendi([guasto.id], attesa_s=attesa),
                                     "letture": prova.letture_oggetto(guasto.id, impronta_riparata), "pannello": prova.pannello(guasto.id)}
    return {"errori": esito}


def _pulizia(prova: FascicoloDiProva) -> dict[str, Any]:
    from web.services.registro_letture_runtime import documento_rimosso

    fascicolo = prova.fascicolo()
    spostati = eliminati = 0
    for documento in list(fascicolo.documenti or []):
        if str(documento.nome).startswith(PREFISSO_FILE):
            prova.rimuovi(documento.id)
            spostati += 1
    for documento in list(prova.fascicolo().documenti_cestino or []):
        if str(documento.nome).startswith(PREFISSO_FILE):
            prova.gf.elimina_documento_definitivamente(prova.id, documento.id)
            documento_rimosso(prova.id, documento.id)
            eliminati += 1
    return {"pulizia": {"spostati_nel_cestino": spostati, "eliminati_definitivamente": eliminati,
                        "restano_di_prova": _e_di_prova(prova.fascicolo())["documenti_di_prova"]}}


FASI: dict[str, Callable[[Any], dict[str, Any]]] = {
    "INVENTARIO": fase_inventario,
    "GIRI": fase_giri,
    "INCREMENTALE": lambda app: _con_fascicolo_di_prova(app, _incrementale),
    "ERRORI": lambda app: _con_fascicolo_di_prova(app, _errori),
    "PULIZIA": lambda app: _con_fascicolo_di_prova(app, _pulizia),
}


def esegui(app: Any, fasi: list[str]) -> dict[str, Any]:
    esito: dict[str, Any] = {"fasi": fasi}
    for fase in fasi:
        azione = FASI.get(fase.upper())
        if azione is None:
            esito[fase] = {"errore": "fase sconosciuta"}
            continue
        try:
            esito[fase.upper()] = azione(app)
        except Exception as exc:
            esito[fase.upper()] = {"errore": _breve(f"{type(exc).__name__}: {exc}")}
    return esito


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app

    app = create_scheduler_app()
    fasi = _env_lista("FASE", ("INVENTARIO",))
    with app.app_context():
        esito = esegui(app, fasi)
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
