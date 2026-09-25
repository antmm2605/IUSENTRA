"""Pagina «PDP Penale» e card del Centro telematico: i procedimenti penali dello studio.

Il PDP non ha servizi per i gestionali (è una maschera web per l'avvocato
autenticato con CNS/CIE): la pagina non «importa pratiche» né verifica
connessioni, ma elenca i fascicoli penali con lo stato dei depositi
preparati in IUSENTRA e la prossima azione, e rimanda alla sezione
«Deposito penale» di ciascun fascicolo. Calendario degli obblighi: art.
111-bis c.p.p. e D.M. 217/2023 come modificato (vedi ``calendario``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app

from pct.fascicoli import StatoFascicolo, TipoFascicolo
from pct.penale_pdp import calendario, catalogo, stati
from pct.penale_pdp.riepilogo import AZIONI, DA_RIFARE, IN_ATTESA, IN_PREPARAZIONE, prossima_azione, riepilogo
from web.services import penale_pdp_contesto as contesto

ROMA = ZoneInfo("Europe/Rome")


def _protocollo(registro: dict[str, Any] | None) -> str:
    if not registro:
        return ""
    sigla = str(registro["office_code"] or "").split("-")[0]
    return f"{sigla}: {registro['register_type']}{registro['register_year']}/{registro['register_number']}"


def _fascicoli_penali() -> list[Any]:
    try:
        tutti = current_app.extensions["core_runtime"]["get_fascicoli"]().tutti()
    except Exception:
        current_app.logger.warning("Fascicoli non leggibili per la pagina PDP", exc_info=True)
        return []
    return [f for f in tutti if getattr(f, "tipo", None) == TipoFascicolo.PENALE and getattr(f, "stato", None) != StatoFascicolo.ARCHIVIATO]


def _riepilogo_casi(oggi: str) -> dict[str, dict[str, Any]]:
    try:
        return riepilogo(contesto.repository().conn, oggi)
    except Exception:
        current_app.logger.warning("Riepilogo depositi penali non disponibile", exc_info=True)
        return {}


def _riga(fascicolo: Any, voce: dict[str, Any] | None, oggi: date) -> dict[str, Any]:
    voce = voce or {"registro": None, "conteggi": {}, "ultimo": None, "prossimaUdienza": "", "autorizzato": False,
                    "ufficio": contesto.ufficio_da_nome(getattr(fascicolo, "tribunale", ""))}
    codice, testo, _ = voce.get("azione") or prossima_azione(voce)
    ufficio = (voce.get("registro") or {}).get("office_code") or voce.get("ufficio") or ""
    ultimo = voce.get("ultimo")
    voce_atto = catalogo.voce(ultimo["act_name"]) if ultimo else None
    return {
        "id": fascicolo.id,
        "titolo": fascicolo.titolo,
        "cliente": getattr(fascicolo, "nome_cliente", "") or "",
        "tribunale": getattr(fascicolo, "tribunale", "") or "",
        "href": f"/fascicoli/{fascicolo.id}#penale-pdp",
        "accessoAttiHref": f"/fascicoli/{fascicolo.id}?pdp=accesso#penale-pdp",
        "protocollo": _protocollo(voce.get("registro")),
        "ufficio": ufficio,
        "ufficioEtichetta": catalogo.etichetta_ufficio(ufficio) if ufficio else "",
        "autorizzato": bool(voce.get("autorizzato")),
        "canale": calendario.canale(ufficio, oggi) if ufficio else None,
        "conteggi": voce.get("conteggi") or {},
        "ultimo": {
            "atto": voce_atto.nome if voce_atto else ultimo["act_name"], "stato": ultimo["status"],
            "statoEtichetta": stati.etichetta(ultimo["status"]), "statoTono": stati.TONI.get(ultimo["status"], "neutral"),
            "identificativo": ultimo["sending_id"], "dataInvio": ultimo["sent_at"], "motivazione": ultimo["rejection_reason"],
        } if ultimo else None,
        "prossimaUdienza": voce.get("prossimaUdienza") or "",
        "azione": {"codice": codice, "testo": testo, "tono": AZIONI[codice][1]},
    }


def _calendario(oggi: date) -> list[dict[str, Any]]:
    per_data: dict[date, list[str]] = {}
    for dal, descrizione in calendario.OBBLIGO.values():
        if descrizione not in per_data.setdefault(dal, []):
            per_data[dal].append(descrizione)
    for descrizione, dal in calendario.ALTRI:
        per_data.setdefault(dal, []).append(descrizione)
    return [{"dal": dal.isoformat(), "uffici": uffici, "inVigore": oggi >= dal} for dal, uffici in sorted(per_data.items())]


def panoramica() -> dict[str, Any]:
    adesso = datetime.now(ROMA)
    oggi = adesso.date()
    casi = _riepilogo_casi(adesso.strftime("%Y-%m-%dT%H:%M"))
    righe = [_riga(f, casi.get(f.id), oggi) for f in _fascicoli_penali()]
    righe.sort(key=lambda r: (AZIONI[r["azione"]["codice"]][2], r["prossimaUdienza"] or "9999", r["titolo"].casefold()))

    def somma(insieme: frozenset[str]) -> int:
        return sum(n for r in righe for s, n in r["conteggi"].items() if s in insieme)

    return {
        "ok": True,
        "generatoIl": adesso.isoformat(timespec="seconds"),
        "totali": {
            "procedimenti": len(righe),
            "nonAutorizzati": sum(1 for r in righe if not r["autorizzato"]),
            "inPreparazione": somma(IN_PREPARAZIONE),
            "inAttesaEsito": somma(IN_ATTESA),
            "daRifare": sum(1 for r in righe if r["azione"]["codice"] == "RIFARE"),
            "accolti": somma(frozenset({"ACCOLTO"})),
            "rigettati": somma(DA_RIFARE),
            "udienze": sum(1 for r in righe if r["prossimaUdienza"]),
        },
        "procedimenti": righe,
        "calendario": _calendario(oggi),
        "fonteCalendario": calendario.FONTE,
        "link": {"pdp": contesto.LINK_PDP, "avvisi": contesto.LINK_AVVISI},
    }


def per_centro_telematico() -> dict[str, Any]:
    """I numeri della card «PDP Penale» nel Centro Servizi Telematici."""
    dati = panoramica()
    totali = dati["totali"]
    return {
        "procedimenti": totali["procedimenti"],
        "inAttesaEsito": totali["inAttesaEsito"],
        "daFare": totali["daRifare"] + sum(1 for r in dati["procedimenti"] if r["azione"]["codice"] in {"INVIARE", "COMPLETARE"}),
        "accolti": totali["accolti"],
    }


__all__ = ["panoramica", "per_centro_telematico"]
