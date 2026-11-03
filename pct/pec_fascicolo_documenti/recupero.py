"""Recupero delle PEC già collegate e stato verificabile del flusso PEC → documenti del fascicolo.

Il recupero lavora a lotti limitati (``limite`` messaggi per giro, dai più vecchi) e riprende da solo: la
coda è «PEC collegate senza esito nel registro del flusso, o con esito superato». Un messaggio in attesa di
conferma torna in coda solo quando il linker scrive un esito nuovo; un errore si riprova al massimo tre volte.
Nessuna scansione dei fascicoli e nessuna rilettura: gli allegati si leggono dal MIME del presidio solo per i
messaggi in coda.
"""

from __future__ import annotations

from typing import Any

from pct.pec_collegamento_certo_riconvalida import riconvalida_collegamenti
from pct.pec_fascicolo_documenti import registro as reg
from pct.pec_fascicolo_documenti.classificazione import VERSIONE
from pct.pec_fascicolo_documenti.flusso import Eventi, _schema, processa_messaggio

# «completato» con regole di classificazione precedenti: si rivede una volta (per esempio le comunicazioni di
# cancelleria scartate come ricevute di deposito perché portavano IndiceBusta.xml).
_CODA = (
    "FROM pec_messages m LEFT JOIN pec_fascicolo_documenti_messaggi s ON s.tenant_id=m.tenant_id AND s.message_id=m.id "
    "WHERE m.tenant_id=? AND m.linked_fascicolo_id<>'' AND (s.message_id IS NULL OR s.fascicolo_id<>m.linked_fascicolo_id "
    f"OR (s.stato='errore' AND s.tentativi<{reg.MASSIMO_TENTATIVI}) "
    f"OR (s.stato='completato' AND s.versione_regole<>'{VERSIONE}') "
    "OR (s.stato='in_attesa_conferma' AND (SELECT MAX(l.created_at) FROM pec_fascicolo_links l WHERE l.message_id=m.id) > s.updated_at))"
)


def recupera_storico(repo: Any, *, limite: int = 50, actor: str = "pec-fascicolo-recupero", eventi: Eventi | None = None) -> dict[str, Any]:
    """Un lotto del recupero storico; restituisce i conteggi del giro e quanti messaggi restano in coda.

    Prima un lotto della riconvalida dei collegamenti (``pct/pec_collegamento_certo_riconvalida``): le PEC
    rimaste proposte che oggi hanno ruolo, cliente e ufficio coincidenti con un solo fascicolo si collegano
    e portano i loro documenti nel fascicolo senza intervento.
    """
    _schema(repo)
    iniziato = reg.adesso()
    try:
        riconvalida = riconvalida_collegamenti(repo, actor=actor)
    except Exception as exc:  # la riconvalida non ferma il recupero dei messaggi già collegati
        riconvalida = {"ok": False, "errore": type(exc).__name__}
    with repo.connect() as conn:
        ids = [riga[0] for riga in conn.execute(
            f"SELECT m.id {_CODA} ORDER BY m.received_at ASC, m.id ASC LIMIT ?", (repo.tenant_id, max(1, int(limite))),
        ).fetchall()]
    conteggi = {"esaminati": 0, "completati": 0, "gia_elaborati": 0, "in_attesa_conferma": 0, "salvati": 0,
                "eml_salvati": 0, "gia_presenti": 0, "scartati": 0, "errori": 0}
    for message_id in ids:
        esito = processa_messaggio(repo, message_id, actor=actor, eventi=eventi)
        conteggi["esaminati"] += 1
        stato = str(esito.get("stato") or "")
        chiave = {"completato": "completati", "gia_elaborato": "gia_elaborati", "in_attesa_conferma": "in_attesa_conferma"}.get(stato)
        if chiave:
            conteggi[chiave] += 1
        if not esito.get("ok"):
            conteggi["errori"] += 1
        for voce in ("salvati", "eml_salvati", "gia_presenti", "scartati"):
            conteggi[voce] += int(esito.get(voce) or 0)
    with repo.connect() as conn:
        conteggi["restano"] = int(conn.execute(f"SELECT COUNT(*) {_CODA}", (repo.tenant_id,)).fetchone()[0])
        reg.registra_giro(conn, repo.tenant_id, "recupero", iniziato, conteggi)
    return {"ok": conteggi["errori"] == 0, **conteggi, "riconvalida": riconvalida}


def stato_flusso(repo: Any) -> dict[str, Any]:
    """Solo conteggi, mai dati del cliente: PEC collegate, documenti ed .eml salvati, scarti per motivo, errori, ultimo giro."""
    _schema(repo)
    tenant = repo.tenant_id
    with repo.connect() as conn:
        def uno(sql: str, *parametri: Any) -> int:
            return int(conn.execute(sql, (tenant, *parametri)).fetchone()[0] or 0)

        per_stato = {riga[0]: int(riga[1]) for riga in conn.execute(
            "SELECT stato, COUNT(*) FROM pec_fascicolo_documenti_messaggi WHERE tenant_id=? GROUP BY stato", (tenant,))}
        scarti = {riga[0]: int(riga[1]) for riga in conn.execute(
            "SELECT motivo, COUNT(*) FROM pec_fascicolo_documenti WHERE tenant_id=? AND esito IN ('scartato', 'gia_presente') "
            "GROUP BY motivo ORDER BY motivo", (tenant,))}
        ultimo_salvataggio = conn.execute(
            "SELECT MAX(created_at) FROM pec_fascicolo_documenti WHERE tenant_id=? AND esito='salvato'", (tenant,)).fetchone()[0]
        return {
            "pec_collegate": uno("SELECT COUNT(*) FROM pec_messages WHERE tenant_id=? AND linked_fascicolo_id<>''"),
            "messaggi_completati": per_stato.get("completato", 0),
            "in_attesa_conferma": per_stato.get("in_attesa_conferma", 0),
            # Per esito del linker («automatico», «proposte»…): quante PEC aspettano la conferma e perché.
            "in_attesa_per_collegamento": {riga[0]: int(riga[1]) for riga in conn.execute(
                "SELECT motivo, COUNT(*) FROM pec_fascicolo_documenti_messaggi WHERE tenant_id=? AND stato='in_attesa_conferma' "
                "GROUP BY motivo ORDER BY motivo", (tenant,))},
            "errori": per_stato.get("errore", 0),
            "errori_definitivi": uno("SELECT COUNT(*) FROM pec_fascicolo_documenti_messaggi WHERE tenant_id=? AND stato='errore' AND tentativi>=?",
                                     reg.MASSIMO_TENTATIVI),
            "da_elaborare": uno(f"SELECT COUNT(*) {_CODA}"),
            "documenti_salvati": uno("SELECT COUNT(*) FROM pec_fascicolo_documenti WHERE tenant_id=? AND ruolo='allegato' AND esito='salvato'"),
            "eml_salvati": uno("SELECT COUNT(*) FROM pec_fascicolo_documenti WHERE tenant_id=? AND ruolo='eml' AND esito='salvato'"),
            "gia_presenti": uno("SELECT COUNT(*) FROM pec_fascicolo_documenti WHERE tenant_id=? AND esito='gia_presente'"),
            "scartati_per_motivo": {motivo or "gia_nel_fascicolo": n for motivo, n in scarti.items()},
            "ultimo_salvataggio": ultimo_salvataggio or "",
            "ultimo_giro": reg.ultimo_giro(conn, tenant),
        }


__all__ = ["recupera_storico", "stato_flusso"]
