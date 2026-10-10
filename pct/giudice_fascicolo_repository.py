"""Consegna SQL del giudice: confronto concorrente, audit e nessun cambio di stato."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def _sostituzione_dimostrata(previous, value, sources):
    valid = []
    for source in sources:
        proofs = source.get("prove", [])
        identity = any(p.get("codice") == "identita_congiunta_provvedimento"
                       and p.get("esito") == "ok"
                       and isinstance(p.get("dettaglio"), dict)
                       and p["dettaglio"].get("complete_match") is True for p in proofs)
        if not identity or not source.get("documento_id") or len(source.get("sha256", "")) != 64:
            continue
        for proof in proofs:
            if proof.get("codice") != "sostituzione_giudice" or proof.get("esito") != "ok":
                continue
            detail = proof.get("dettaglio", {})
            if not isinstance(detail, dict):
                continue
            try:
                effective = date.fromisoformat(detail.get("decorrenza", ""))
            except (ValueError, TypeError):
                continue
            if (str(detail.get("precedente", "")).casefold() == previous.casefold()
                    and str(detail.get("nuovo", "")).casefold() == value.casefold()
                    and detail.get("passaggio")
                    and effective <= datetime.now(ZoneInfo("Europe/Rome")).date()):
                valid.append(detail)
    return valid


class GiudiceFascicoloRepository:
    def __init__(self, backend):
        self.backend = backend

    def consegna(self, fid, valore, evidenze):
        if not fid or not valore or not evidenze:
            raise ValueError("Fascicolo, giudice e prove obbligatori.")
        writer = getattr(self.backend, "_conn_per_scrittura", None)
        conn = writer() if callable(writer) else self.backend.conn
        raw = getattr(self.backend, "raw_conn", None)
        transaction = raw if raw is not None else conn
        try:
            row = conn.execute("SELECT giudice,dati_json FROM fascicoli WHERE id=?", (fid,)).fetchone()
            if row is None:
                raise ValueError("Fascicolo non trovato.")
            previous = str(row["giudice"] or "").strip()
            payload = json.loads(row["dati_json"] or "{}")
            embedded = str(payload.get("giudice") or "").strip()
            if previous != embedded:
                raise ValueError("Giudice SQL discordante dal dato della scheda: verifica richiesta.")
            if previous and previous.casefold() != valore.casefold():
                replacements = _sostituzione_dimostrata(previous, valore, evidenze)
                last = conn.execute(
                    "SELECT dettagli FROM audit_log WHERE risorsa_tipo='fascicolo' AND risorsa_id=? "
                    "AND azione='fascicolo.giudice_da_fonte' AND esito='SUCCESSO' ORDER BY timestamp DESC LIMIT 1",
                    (fid,),
                ).fetchone()
                automatic = json.loads(last["dettagli"]) if last else {}
                # Una decisione manuale successiva rimane in verifica, anche
                # quando la fonte esplicita una sostituzione.
                if not replacements or automatic.get("giudice", "").casefold() != previous.casefold():
                    transaction.rollback()
                    return {"stato": "discordante", "precedente": previous, "letto": valore,
                            "motivo": "Sostituzione e decorrenza non dimostrate, oppure dato manuale da preservare."}
                old_dates = [d["decorrenza"] for source in automatic.get("evidenze", [])
                             for proof in source.get("prove", [])
                             if proof.get("codice") == "sostituzione_giudice"
                             and isinstance((d := proof.get("dettaglio")), dict) and d.get("decorrenza")]
                if old_dates and min(d["decorrenza"] for d in replacements) <= max(old_dates):
                    transaction.rollback()
                    return {"stato": "discordante", "motivo": "La fonte non dimostra una sostituzione successiva all'ultima applicata."}
            if previous.casefold() == valore.casefold():
                transaction.rollback()
                return {"stato": "gia_presente", "riferimento": fid}
            stamp = datetime.now(timezone.utc).isoformat()
            payload["giudice"] = valore
            payload["modificato_il"] = stamp
            payload["giudice_fonte"] = {"versione": "2026.10.10.v1", "evidenze": evidenze}
            saved = conn.execute(
                "UPDATE fascicoli SET giudice=?,dati_json=?,modificato_il=? WHERE id=? AND COALESCE(giudice,'')=? AND dati_json=? RETURNING id",
                (valore, json.dumps(payload, ensure_ascii=False), stamp, fid, row["giudice"] or "", row["dati_json"]),
            ).fetchone()
            if saved is None:
                raise ValueError("Il fascicolo è cambiato durante la consegna: nessun dato sovrascritto.")
            conn.execute(
                "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, stamp, "archivio_letture", "Motore documenti", "fascicolo.giudice_da_fonte", "fascicolo", fid,
                 json.dumps({"giudice": valore, "precedente": previous, "evidenze": evidenze}, ensure_ascii=False), "", "SUCCESSO"),
            )
            transaction.commit()
            return {"stato": "consegnato", "riferimento": fid}
        except Exception:
            transaction.rollback()
            raise
