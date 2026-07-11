"""Tool Lex per interrogare dati di fascicolo.

Espone: metadati, attività processuali (udienze, depositi, comunicazioni
di cancelleria, provvedimenti, istanze), documenti, depositi telematici.
"""

from __future__ import annotations

from typing import Any

from .base import BaseLexTool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _enum_val(obj: Any) -> str:
    return getattr(obj, "value", "") if obj is not None else ""


def _get_store():
    try:
        from web.helpers import get_fascicoli
        return get_fascicoli()
    except Exception:
        return None


# ──────────────────────────────────────────────
# Serializzatori
# ──────────────────────────────────────────────

def _meta_fascicolo(f: Any) -> dict[str, Any]:
    return {
        "id": getattr(f, "id", ""),
        "numero": getattr(f, "numero", ""),
        "titolo": getattr(f, "titolo", ""),
        "cliente": getattr(f, "nome_cliente", ""),
        "controparte": getattr(f, "controparte", ""),
        "oggetto": getattr(f, "oggetto", ""),
        "tribunale": getattr(f, "tribunale", ""),
        "rg": getattr(f, "rg", "") or getattr(f, "numero_rg", ""),
        "anno_rg": getattr(f, "anno_rg", ""),
        "giudice": getattr(f, "giudice", ""),
        "sezione": getattr(f, "sezione", ""),
        "avvocato_referente": getattr(f, "avvocato_referente", ""),
        "avvocato_dominus": getattr(f, "avvocato_dominus", ""),
        "valore_causa": getattr(f, "valore_causa", ""),
        "stato": _enum_val(getattr(f, "stato", None)),
        "tipo": _enum_val(getattr(f, "tipo", None)),
        "data_apertura": getattr(f, "data_apertura", ""),
        "data_prossima_udienza": getattr(f, "data_prossima_udienza", ""),
        "data_chiusura": getattr(f, "data_chiusura", ""),
        "source": getattr(f, "source", ""),
        "documenti_count": len(list(getattr(f, "documenti", []) or [])),
        "attivita_count": len(list(getattr(f, "attivita", []) or [])),
        "depositi_pct_count": len(list(getattr(f, "depositi_pct", []) or [])),
    }


def _ser_attivita(a: Any) -> dict[str, Any]:
    return {
        "id": getattr(a, "id", ""),
        "tipo": _enum_val(getattr(a, "tipo", None)),
        "data": getattr(a, "data", ""),
        "titolo": getattr(a, "titolo", ""),
        "descrizione": getattr(a, "descrizione", ""),
        "esito": _enum_val(getattr(a, "esito", None)),
        "luogo": getattr(a, "luogo", ""),
        "note": getattr(a, "note", ""),
        "avvocato": getattr(a, "avvocato", ""),
        "email_mittente": getattr(a, "email_mittente", ""),
        "email_oggetto": getattr(a, "email_oggetto", ""),
        "email_testo": (getattr(a, "email_testo", "") or "")[:800],
        "id_deposito_pct": getattr(a, "id_deposito_pct", ""),
        "id_documento": getattr(a, "id_documento", ""),
    }


def _ser_documento(d: Any) -> dict[str, Any]:
    return {
        "id": getattr(d, "id", ""),
        "nome": getattr(d, "nome", ""),
        "tipo": _enum_val(getattr(d, "tipo", None)),
        "firmato_digitalmente": bool(getattr(d, "firmato_digitalmente", False)),
        "data_documento": getattr(d, "data_documento", ""),
        "data_caricamento": getattr(d, "data_caricamento", ""),
        "id_deposito_pct": getattr(d, "id_deposito_pct", ""),
        "note": getattr(d, "note", ""),
    }


def _ser_deposito(e: Any) -> dict[str, Any]:
    stato = getattr(e, "stato", None)
    return {
        "id": getattr(e, "id", ""),
        "id_deposito": getattr(e, "id_deposito", ""),
        "tipo_atto": getattr(e, "tipo_atto", ""),
        "stato": str(stato) if stato is not None else "",
        "data_invio": getattr(e, "data_invio", "") or getattr(e, "timestamp", ""),
        "data_accettazione_pec": getattr(e, "data_accettazione_pec", ""),
        "data_esito": getattr(e, "data_esito", ""),
        "messaggio": getattr(e, "messaggio", ""),
        "pec_destinatario": getattr(e, "pec_destinatario", ""),
        "esito_controlli": getattr(e, "esito_controlli", ""),
        "esito_cancelleria": getattr(e, "esito_cancelleria", ""),
        "canale": getattr(e, "canale", "") or getattr(e, "portale", ""),
    }


def _filter_attivita(attivita: list[Any], tipi: set[str], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for a in attivita:
        if tipi and _enum_val(getattr(a, "tipo", None)) not in tipi:
            continue
        rows.append(_ser_attivita(a))
        if len(rows) >= limit:
            break
    return rows


def _filter_documenti(documenti: list[Any], tipi: set[str], portale_only: bool, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in documenti:
        tipo = _enum_val(getattr(d, "tipo", None))
        if tipi and tipo not in tipi:
            continue
        if portale_only and not _clean(getattr(d, "id_deposito_pct", "")):
            continue
        rows.append(_ser_documento(d))
        if len(rows) >= limit:
            break
    return rows


# ──────────────────────────────────────────────
# Tool principale
# ──────────────────────────────────────────────

class FascicoloTool(BaseLexTool):
    tool_name = "fascicolo"

    def run(self, **kwargs) -> dict[str, Any]:
        """Interroga dati di un fascicolo.

        Parametri:
        - fascicolo_id / pratica_id: ID fascicolo (obbligatorio salvo q)
        - q / query: ricerca testuale nella lista fascicoli
        - limit: max fascicoli in lista (default 10); il risultato lista
          riporta returned_count/total_matching/truncated/coverage_complete
        - include_archiviati: includi fascicoli archiviati (default False)
        - stato: filtra per stato fascicolo (es. "APERTO")
        - avvocato: filtra per referente o dominus (match parziale)
        - sezione: quale sezione restituire:
            "meta"        → solo metadati
            "attivita"    → tutte le attività processuali
            "udienze"     → solo udienze
            "cancelleria" → comunicazioni di cancelleria e provvedimenti
            "istanze"     → depositi atti, iscrizioni a ruolo, appelli
            "depositi"    → depositi telematici (EsitoDepositoPCT)
            "documenti"   → lista documenti fascicolo
            "doc_portale" → documenti dal portale telematico (con id_deposito_pct)
            "full"        → tutto (default)
        - limit_attivita: max attività (default 20)
        - limit_documenti: max documenti (default 15)
        - limit_depositi: max depositi (default 10)
        """
        store = _get_store()
        if store is None:
            return {"error": "store_unavailable", "items": []}

        fascicolo_id = _clean(kwargs.get("fascicolo_id") or kwargs.get("pratica_id") or kwargs.get("id"))
        sezione = _clean(kwargs.get("sezione") or "full").lower()
        lim_att = max(int(kwargs.get("limit_attivita") or 20), 1)
        lim_doc = max(int(kwargs.get("limit_documenti") or 15), 1)
        lim_dep = max(int(kwargs.get("limit_depositi") or 10), 1)

        # ── Ricerca lista fascicoli ──
        if not fascicolo_id:
            query = _clean(kwargs.get("q") or kwargs.get("query")).lower()
            limit = max(int(kwargs.get("limit") or 10), 1)
            include_archiviati = bool(kwargs.get("include_archiviati"))
            stato_filtro = _clean(kwargs.get("stato")).upper()
            avvocato_filtro = _clean(kwargs.get("avvocato")).lower()
            try:
                tutti = list(store.tutti(archiviati=include_archiviati))
            except TypeError:
                try:
                    tutti = list(store.tutti())
                except Exception:
                    tutti = []
            except Exception:
                try:
                    tutti = list(store.lista())
                except Exception:
                    tutti = []
            matching: list[dict[str, Any]] = []
            for f in tutti:
                if stato_filtro and _enum_val(getattr(f, "stato", None)).upper() != stato_filtro:
                    continue
                if avvocato_filtro:
                    referenti = " ".join(
                        str(getattr(f, attr, "") or "")
                        for attr in ("avvocato_referente", "avvocato_dominus")
                    ).lower()
                    if avvocato_filtro not in referenti:
                        continue
                if query:
                    hay = " ".join(
                        str(getattr(f, attr, "") or "")
                        for attr in ("numero", "titolo", "nome_cliente", "controparte", "oggetto")
                    ).lower()
                    if query not in hay:
                        continue
                matching.append(_meta_fascicolo(f))
            items = matching[:limit]
            truncated = len(matching) > len(items)
            return {
                "items": items,
                "total": len(items),
                "returned_count": len(items),
                "total_matching": len(matching),
                "truncated": truncated,
                "coverage_complete": not truncated,
                "query": query,
            }

        # ── Fascicolo specifico ──
        try:
            f = store.get(fascicolo_id)
        except Exception:
            f = None
        if not f:
            return {"found": False, "id": fascicolo_id, "items": []}

        attivita_raw: list[Any] = list(getattr(f, "attivita", []) or [])
        attivita_raw.sort(key=lambda a: getattr(a, "data", "") or "", reverse=True)
        documenti_raw: list[Any] = list(getattr(f, "documenti", []) or [])
        depositi_raw: list[Any] = list(getattr(f, "depositi_pct", []) or [])

        out: dict[str, Any] = {"found": True, "id": fascicolo_id}

        # Metadati sempre presenti
        if sezione in ("meta", "full"):
            out["meta"] = _meta_fascicolo(f)

        # Tutte le attività
        if sezione in ("attivita", "full"):
            out["attivita"] = _filter_attivita(attivita_raw, set(), lim_att)

        # Solo udienze
        if sezione in ("udienze", "full"):
            out["udienze"] = _filter_attivita(
                attivita_raw,
                {"UDIENZA", "RINVIO"},
                lim_att,
            )

        # Comunicazioni cancelleria + provvedimenti
        if sezione in ("cancelleria", "full"):
            out["cancelleria"] = _filter_attivita(
                attivita_raw,
                {"COMUNICAZIONE_CANCELLERIA", "PROVVEDIMENTO", "SENTENZA_EMESSA", "NOTIFICA"},
                lim_att,
            )

        # Istanze: depositi, iscrizioni, appelli
        if sezione in ("istanze", "full"):
            out["istanze"] = _filter_attivita(
                attivita_raw,
                {"DEPOSITO_ATTI", "ISCRIZIONE_A_RUOLO", "APPELLO", "TERMINE_SCADENZA"},
                lim_att,
            )

        # Depositi telematici PCT/PDP/PAT
        if sezione in ("depositi", "full"):
            out["depositi_telematici"] = [
                _ser_deposito(e) for e in depositi_raw[:lim_dep]
            ]

        # Tutti i documenti del fascicolo
        if sezione in ("documenti", "full"):
            out["documenti"] = _filter_documenti(documenti_raw, set(), False, lim_doc)

        # Solo documenti da portale telematico
        if sezione in ("doc_portale", "full"):
            out["documenti_portale"] = _filter_documenti(documenti_raw, set(), True, lim_doc)

        # Note fascicolo
        if sezione == "full":
            out["note"] = getattr(f, "note", "") or ""
            out["avanzamento"] = [
                {
                    "data": getattr(av, "data", ""),
                    "titolo": getattr(av, "titolo", ""),
                    "descrizione": getattr(av, "descrizione", ""),
                }
                for av in list(getattr(f, "avanzamento", []) or [])[:10]
            ]

        out["items"] = [out.get("meta") or _meta_fascicolo(f)]
        return out
