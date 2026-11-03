"""Riconvalida dello storico: le PEC già lavorate si collegano con la regola di ruolo, cliente e ufficio.

Il linker applica ``pct/pec_collegamento_certo`` alle PEC che arrivano da ora; quelle già elaborate restano con
l'ultimo esito scritto (proposte, ruolo non sufficiente, identità incompleta, nessun candidato). Qui si
ripassano **a lotti**: per ogni PEC si verificano i tre controlli sull'archivio dei fascicoli caricato una sola
volta e, se un solo fascicolo li soddisfa, si richiama il linker (``link_fascicolo``), che scrive l'esito
certificato e porta allegati, .eml, eventi e scadenze come per ogni collegamento certo.

Idempotente: ogni verifica si annota con la versione letta della PEC e l'impronta dei dati dei fascicoli che
contano (ruolo, cliente, ufficio). Una PEC già verificata torna in coda solo se cambia la sua lettura o se cambia
un fascicolo (per esempio quando l'avvocato inserisce il numero di ruolo o il cliente).

Base normativa: art. 16 D.L. 179/2012; D.M. 44/2011 (vedi ``pct/pec_collegamento_certo``).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pct.pec_collegamento_certo import STATO_CERTO, cerca_collegamento_certo

#: Ultimi esiti del linker che la riconvalida riprende (le PEC senza collegamento certo).
ESITI_DA_RICONVALIDARE = ("proposte", "rg_non_sufficiente", "identita_incompleta", "nessun_candidato")
#: Cambia quando cambia la regola: tutte le verifiche precedenti tornano in coda.
# 2: forme ministeriali del numero di ruolo («COMUNICAZIONE n/aaaa/LAV», «RG: n - aaaa»);
# 3: etichette per esteso («Numero di Ruolo generale: n/aaaa»), registri con suffisso, «n. n/aaaa R.G.», «proc. n.».
VERSIONE_REGOLA = "3"
LIMITE_PREDEFINITO = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS pec_collegamento_certo_verifiche (
    tenant_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    parsed_version_id TEXT NOT NULL DEFAULT '',
    impronta_fascicoli TEXT NOT NULL DEFAULT '',
    esito TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, message_id)
);
"""

_ULTIMO_ESITO = ("(SELECT l.status FROM pec_fascicolo_links l WHERE l.message_id=m.id "
                 "ORDER BY l.created_at DESC, l.rowid DESC LIMIT 1)")
_ULTIMA_LETTURA = "(SELECT p.id FROM pec_parsed_versions p WHERE p.message_id=m.id ORDER BY p.version DESC LIMIT 1)"


def _coda(n_esiti: int) -> str:
    segnaposti = ",".join("?" for _ in range(n_esiti))
    return (f"FROM pec_messages m LEFT JOIN pec_collegamento_certo_verifiche v ON v.tenant_id=m.tenant_id AND v.message_id=m.id "
            f"WHERE m.tenant_id=? AND {_ULTIMO_ESITO} IN ({segnaposti}) "
            f"AND (v.message_id IS NULL OR v.impronta_fascicoli<>? OR v.parsed_version_id<>COALESCE({_ULTIMA_LETTURA}, ''))")


def impronta_fascicoli(fascicoli: list[Any]) -> str:
    """Impronta dei soli dati che decidono la regola: ruolo, cliente, ufficio."""
    righe = sorted(
        "|".join(str(getattr(f, campo, "") or "") for campo in ("id", "numero_rg", "anno_rg", "nome_cliente", "id_cliente",
                                                                 "tribunale", "codice_ufficio_portale"))
        for f in fascicoli
    )
    return hashlib.sha256("\n".join([VERSIONE_REGOLA, *righe]).encode("utf-8")).hexdigest()


def riconvalida_collegamenti(repo: Any, *, limite: int = LIMITE_PREDEFINITO, actor: str = "pec-collegamento-certo") -> dict[str, Any]:
    """Un lotto della riconvalida; restituisce solo conteggi (nessun dato del cliente)."""
    conteggi = {"esaminati": 0, "collegati": 0, "non_certi": 0, "errori": 0, "restano": 0}
    if not getattr(repo, "fascicoli_db_path", None):
        return {"ok": True, **conteggi}
    from pct.pec_fascicolo_documenti.flusso import _gestione_fascicoli

    fascicoli = list(_gestione_fascicoli(repo).tutti(archiviati=True))
    impronta = impronta_fascicoli(fascicoli)
    parametri = (repo.tenant_id, *ESITI_DA_RICONVALIDARE, impronta)
    with repo.connect() as conn:
        conn.executescript(SCHEMA)
        righe = conn.execute(
            f"SELECT m.id, COALESCE({_ULTIMA_LETTURA}, '') AS versione {_coda(len(ESITI_DA_RICONVALIDARE))} "
            "ORDER BY m.received_at ASC, m.id ASC LIMIT ?",
            (*parametri, max(1, int(limite))),
        ).fetchall()
    for riga in righe:
        message_id, versione = str(riga["id"]), str(riga["versione"] or "")
        conteggi["esaminati"] += 1
        try:
            with repo.connect() as conn:
                letta = repo.latest_parsed_row(conn, message_id)
            parsed = json.loads(letta["parsed_json"] or "{}") if letta else {}
            # Prima la verifica leggera; il linker, solo se un fascicolo soddisfa i tre controlli, rifà tutto
            # (codice fiscale letto dai documenti compreso) e decide lui.
            trovato = cerca_collegamento_certo(parsed, fascicoli) if parsed else {"motivo": "pec_non_letta"}
            esito = trovato["motivo"] + (f":{trovato['manca']}" if trovato.get("manca") else "")
            if parsed and esito == "ruolo_cliente_ufficio_coincidenti":
                esito = str(repo.link_fascicolo(message_id, actor=actor).get("status") or "")
            chiave = "collegati" if esito == STATO_CERTO else "non_certi"
        except Exception as exc:  # un messaggio guasto non ferma il lotto; si riprova quando cambiano lettura o fascicoli
            esito, chiave = f"errore:{type(exc).__name__}", "errori"
        conteggi[chiave] += 1
        with repo.connect() as conn:
            conn.execute(
                "INSERT INTO pec_collegamento_certo_verifiche (tenant_id, message_id, parsed_version_id, impronta_fascicoli, esito, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(tenant_id, message_id) DO UPDATE SET parsed_version_id=excluded.parsed_version_id, "
                "impronta_fascicoli=excluded.impronta_fascicoli, esito=excluded.esito, updated_at=excluded.updated_at",
                (repo.tenant_id, message_id, versione, impronta, esito,
                 datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")),
            )
    with repo.connect() as conn:
        conteggi["restano"] = int(conn.execute(f"SELECT COUNT(*) {_coda(len(ESITI_DA_RICONVALIDARE))}", parametri).fetchone()[0])
    return {"ok": conteggi["errori"] == 0, **conteggi}


__all__ = ["ESITI_DA_RICONVALIDARE", "LIMITE_PREDEFINITO", "impronta_fascicoli", "riconvalida_collegamenti"]
