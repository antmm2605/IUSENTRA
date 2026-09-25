"""Registri, soggetti, depositi e udienze del procedimento penale (tabelle di ``schema.py``).

Usa la stessa connessione di ``PDPPenaleWorkflowRepository`` e registra ogni
cambio di stato di un deposito anche fra gli eventi del caso, perché la
storia del deposito resti ricostruibile (art. 7 provv. DGSIA 11/07/2023).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Iterable

from . import stati

_MUTABILI_DEPOSITO = frozenset({
    "act_name", "is_main_act", "office_code", "office_name", "register_label", "subjects_json", "files_json",
    "data_json", "checks_json", "status", "sending_id", "sent_at", "arrived_at", "rejection_reason",
    "receipt_document_id", "outcome_document_id", "receipt_check_json",
})
_JSON = ("subjects_json", "files_json", "data_json", "checks_json", "receipt_check_json")


def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _id(prefisso: str) -> str:
    return f"{prefisso}_{uuid.uuid4().hex[:16]}"


def _riga(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    dati = {k: row[k] for k in row.keys()}
    for chiave in _JSON:
        if chiave in dati:
            try:
                dati[chiave] = json.loads(dati[chiave] or "null")
            except (TypeError, ValueError):
                dati[chiave] = None
    return dati


class ArchivioPenale:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    # ---- registri -------------------------------------------------------
    def registri(self, caso_id: str) -> list[dict[str, Any]]:
        righe = self.conn.execute(
            "SELECT * FROM criminal_case_registers WHERE criminal_case_id = ? ORDER BY is_current DESC, created_at", (caso_id,)
        ).fetchall()
        return [_riga(r) for r in righe]

    def salva_registro(self, caso_id: str, *, office_code: str, office_name: str = "", register_type: str = "",
                       register_number: str = "", register_year: str = "", magistrate: str = "",
                       corrente: bool = False, source: str = "manuale") -> dict[str, Any]:
        esistente = self.conn.execute(
            "SELECT id FROM criminal_case_registers WHERE criminal_case_id = ? AND office_code = ? AND register_number = ? AND register_year = ?",
            (caso_id, office_code, register_number, str(register_year)),
        ).fetchone()
        if corrente:
            self.conn.execute("UPDATE criminal_case_registers SET is_current = 0 WHERE criminal_case_id = ?", (caso_id,))
        if esistente:
            self.conn.execute(
                "UPDATE criminal_case_registers SET office_name = COALESCE(NULLIF(?, ''), office_name), "
                "register_type = COALESCE(NULLIF(?, ''), register_type), magistrate = COALESCE(NULLIF(?, ''), magistrate), "
                "is_current = CASE WHEN ? THEN 1 ELSE is_current END WHERE id = ?",
                (office_name, register_type, magistrate, int(corrente), esistente["id"]),
            )
            identificativo = esistente["id"]
        else:
            identificativo = _id("creg")
            self.conn.execute(
                "INSERT INTO criminal_case_registers (id, criminal_case_id, office_code, office_name, register_type, register_number, "
                "register_year, magistrate, is_current, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (identificativo, caso_id, office_code, office_name, register_type, register_number, str(register_year),
                 magistrate, int(corrente), source, _adesso()),
            )
        self.conn.commit()
        return _riga(self.conn.execute("SELECT * FROM criminal_case_registers WHERE id = ?", (identificativo,)).fetchone())

    def elimina_registro(self, caso_id: str, registro_id: str) -> None:
        self.conn.execute("DELETE FROM criminal_case_registers WHERE id = ? AND criminal_case_id = ?", (registro_id, caso_id))
        self.conn.commit()

    # ---- soggetti -------------------------------------------------------
    def soggetti(self, caso_id: str) -> list[dict[str, Any]]:
        righe = self.conn.execute(
            "SELECT * FROM criminal_case_subjects WHERE criminal_case_id = ? ORDER BY created_at", (caso_id,)
        ).fetchall()
        return [_riga(r) for r in righe]

    def salva_soggetto(self, caso_id: str, *, full_name: str, role_code: str, tax_code: str = "",
                       subject_kind: str = "fisica", birth_date: str = "", source: str = "manuale") -> dict[str, Any]:
        nome = " ".join(str(full_name or "").split())
        if not nome:
            raise ValueError("Indica il nome del soggetto rappresentato.")
        self.conn.execute(
            "INSERT INTO criminal_case_subjects (id, criminal_case_id, full_name, role_code, tax_code, subject_kind, birth_date, source, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(criminal_case_id, full_name, role_code) DO UPDATE SET "
            "tax_code = COALESCE(NULLIF(excluded.tax_code, ''), tax_code), birth_date = COALESCE(NULLIF(excluded.birth_date, ''), birth_date)",
            (_id("csubj"), caso_id, nome, role_code.upper(), tax_code.upper(), subject_kind, birth_date, source, _adesso()),
        )
        self.conn.commit()
        return _riga(self.conn.execute(
            "SELECT * FROM criminal_case_subjects WHERE criminal_case_id = ? AND full_name = ? AND role_code = ?",
            (caso_id, nome, role_code.upper()),
        ).fetchone())

    def elimina_soggetto(self, caso_id: str, soggetto_id: str) -> None:
        self.conn.execute("DELETE FROM criminal_case_subjects WHERE id = ? AND criminal_case_id = ?", (soggetto_id, caso_id))
        self.conn.commit()

    # ---- depositi -------------------------------------------------------
    def depositi(self, caso_id: str) -> list[dict[str, Any]]:
        righe = self.conn.execute(
            "SELECT * FROM criminal_deposits WHERE criminal_case_id = ? ORDER BY COALESCE(NULLIF(sent_at, ''), created_at) DESC", (caso_id,)
        ).fetchall()
        return [_riga(r) for r in righe]

    def deposito(self, caso_id: str, deposito_id: str) -> dict[str, Any]:
        riga = _riga(self.conn.execute(
            "SELECT * FROM criminal_deposits WHERE id = ? AND criminal_case_id = ?", (deposito_id, caso_id)
        ).fetchone())
        if riga is None:
            raise KeyError("Deposito non trovato.")
        return riga

    def crea_deposito(self, caso_id: str, *, creato_da: str = "", source: str = "iusentra", **campi: Any) -> dict[str, Any]:
        dati = {k: v for k, v in campi.items() if k in _MUTABILI_DEPOSITO}
        identificativo = _id("cdep")
        adesso = _adesso()
        valori = {"id": identificativo, "criminal_case_id": caso_id, "created_by": creato_da, "source": source,
                  "created_at": adesso, "updated_at": adesso, **dati}
        for chiave in _JSON:
            if chiave in valori and not isinstance(valori[chiave], str):
                valori[chiave] = json.dumps(valori[chiave], ensure_ascii=False)
        colonne = ", ".join(valori)
        self.conn.execute(f"INSERT INTO criminal_deposits ({colonne}) VALUES ({', '.join('?' for _ in valori)})", tuple(valori.values()))
        self.conn.commit()
        return self.deposito(caso_id, identificativo)

    def aggiorna_deposito(self, caso_id: str, deposito_id: str, **campi: Any) -> dict[str, Any]:
        prima = self.deposito(caso_id, deposito_id)
        dati = {k: v for k, v in campi.items() if k in _MUTABILI_DEPOSITO}
        for chiave in _JSON:
            if chiave in dati and not isinstance(dati[chiave], str):
                dati[chiave] = json.dumps(dati[chiave], ensure_ascii=False)
        if not dati:
            return prima
        dati["updated_at"] = _adesso()
        assegnazioni = ", ".join(f"{k} = ?" for k in dati)
        self.conn.execute(f"UPDATE criminal_deposits SET {assegnazioni} WHERE id = ? AND criminal_case_id = ?",
                          (*dati.values(), deposito_id, caso_id))
        nuovo = campi.get("status")
        if nuovo and nuovo != prima.get("status"):
            self._evento_stato(caso_id, prima, str(nuovo))
        self.conn.commit()
        return self.deposito(caso_id, deposito_id)

    def per_identificativo(self, caso_id: str, identificativo: str) -> dict[str, Any] | None:
        return _riga(self.conn.execute(
            "SELECT * FROM criminal_deposits WHERE criminal_case_id = ? AND sending_id = ?", (caso_id, identificativo)
        ).fetchone())

    def elimina_deposito(self, caso_id: str, deposito_id: str) -> None:
        deposito = self.deposito(caso_id, deposito_id)
        if deposito["status"] not in {"BOZZA", "PRONTO"}:
            raise ValueError("Un deposito già inviato al PDP non si elimina: resta nello storico.")
        self.conn.execute("DELETE FROM criminal_deposits WHERE id = ?", (deposito_id,))
        self.conn.commit()

    def _evento_stato(self, caso_id: str, deposito: dict[str, Any], nuovo: str) -> None:
        try:
            self.conn.execute(
                "INSERT INTO criminal_case_events (id, criminal_case_id, event_type, event_source, event_status, title, description, payload_json) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (_id("cevt"), caso_id, "deposito_pdp", "ministry" if nuovo not in {"BOZZA", "PRONTO"} else "user", nuovo,
                 f"{deposito.get('act_name', 'Deposito')}: {stati.etichetta(nuovo)}",
                 f"Da «{stati.etichetta(deposito.get('status', ''))}» a «{stati.etichetta(nuovo)}».",
                 json.dumps({"deposito_id": deposito.get("id"), "identificativo": deposito.get("sending_id", "")}, ensure_ascii=False)),
            )
        except sqlite3.Error:
            pass

    # ---- udienze --------------------------------------------------------
    def udienze(self, caso_id: str) -> list[dict[str, Any]]:
        righe = self.conn.execute("SELECT * FROM criminal_hearings WHERE criminal_case_id = ? ORDER BY starts_at", (caso_id,)).fetchall()
        return [_riga(r) for r in righe]

    def registra_udienza(self, caso_id: str, *, starts_at: str, office_type: str = "", room: str = "", place: str = "",
                         reason: str = "") -> tuple[dict[str, Any], bool]:
        esistente = self.conn.execute(
            "SELECT * FROM criminal_hearings WHERE criminal_case_id = ? AND starts_at = ? AND office_type = ?",
            (caso_id, starts_at, office_type),
        ).fetchone()
        if esistente:
            return _riga(esistente), False
        identificativo = _id("chear")
        self.conn.execute(
            "INSERT INTO criminal_hearings (id, criminal_case_id, starts_at, office_type, room, place, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (identificativo, caso_id, starts_at, office_type, room, place, reason, _adesso()),
        )
        self.conn.commit()
        return _riga(self.conn.execute("SELECT * FROM criminal_hearings WHERE id = ?", (identificativo,)).fetchone()), True

    def collega_agenda(self, udienza_id: str, agenda_id: str) -> None:
        self.conn.execute("UPDATE criminal_hearings SET agenda_id = ? WHERE id = ?", (agenda_id, udienza_id))
        self.conn.commit()


def iniziali(nome: str) -> str:
    """Le iniziali come le mostra il PDP (es. «M.R.»)."""
    parti = [p for p in str(nome or "").replace(".", " ").split() if p]
    return ".".join(p[0].upper() for p in parti) + ("." if parti else "")


def ruoli_di(soggetti: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({str(s.get("role_code") or s.get("ruolo") or "").upper() for s in soggetti} - {""})


__all__ = ["ArchivioPenale", "iniziali", "ruoli_di"]
