"""Scheda di lavorazione di un impegno d'agenda (GET /api/v1/ui/agenda/lavorazione).

Raccoglie in un'unica risposta ciò che il software ha già preparato per l'impegno: che cosa è arrivato (PEC e prove),
i termini in bozza da confermare o scartare, il collegamento dell'udienza da remoto, la notifica presidiata e il
prossimo passo. Sola lettura: le conferme passano dalle route esistenti dello scadenziario, con i loro permessi.
Le regole sono in ``pct/agenda_lavorazione.py``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from pct.agenda_lavorazione import (
    collegamento_remoto,
    e_bozza,
    fascicolo_dell_impegno,
    notifica_collegata,
    proposte_collegate,
    prossimo_passo,
    riferimenti_pec,
    voce_proposta,
)
from pct.agenda_linguaggio import nome_proprio, parole_del_registro, riga_contesto
from web.services.pec_source_links import pec_source_href

_RIGHE_ARRIVO = ("Evento:", "Descrizione evento:", "Termine proposto:", "Decorrenza letta:")


_RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?\b", re.I)
_ROMA = ZoneInfo("Europe/Rome")


def _data_italiana(trovato: re.Match[str]) -> str:
    """«2026-11-02T09:30:00» → «02/11/2026 ore 09:30», sempre nell'ora di Roma; mezzanotte senza ora."""
    anno, mese, giorno, ora, minuti, fuso = trovato.groups()
    if ora is None:
        return f"{giorno}/{mese}/{anno}"
    try:
        istante = datetime(int(anno), int(mese), int(giorno), int(ora), int(minuti))
    except ValueError:
        return trovato.group(0)
    if fuso:
        offset = 0 if fuso.upper() == "Z" else (1 if fuso[0] == "+" else -1) * (int(fuso[1:3]) * 60 + int(fuso[-2:]))
        istante = istante.replace(tzinfo=timezone(timedelta(minutes=offset))).astimezone(_ROMA)
    giorno_it = f"{istante:%d/%m/%Y}"
    return giorno_it if (istante.hour, istante.minute) == (0, 0) else f"{giorno_it} ore {istante:%H:%M}"


def date_italiane(testo: str) -> str:
    convertito = _RE_ISO.sub(_data_italiana, str(testo or ""))
    # «il 10/12/2026 00:00» del registro: la mezzanotte non è un orario dell'atto.
    return re.sub(r"\b(\d{2}/\d{2}/\d{4})(?:\s+(?:ore\s+)?00[:.]00)\b", r"\1", convertito)


def _frase(testo: str) -> str:
    """Il testo del registro in carattere normale, con l'iniziale maiuscola."""
    frase = parole_del_registro(testo)
    return frase[:1].upper() + frase[1:]


def _arrivo(note: str) -> str:
    righe = []
    for riga in str(note or "").splitlines():
        riga = riga.strip()
        for etichetta in _RIGHE_ARRIVO:
            if riga.startswith(etichetta):
                valore = date_italiane(riga.removeprefix(etichetta).strip().rstrip("."))
                righe.append(("Decorrenza: " + valore if etichetta == "Decorrenza letta:" else _frase(date_italiane(valore))) + ".")
    testo = " ".join(dict.fromkeys(r for r in righe if len(r) > 1))
    return date_italiane(re.sub(r"\s+", " ", testo))[:600]


def _prova_pec(pec_audit_db: str, tenant_id: str, pec_id: str) -> dict[str, Any]:
    """Come è conservata la PEC d'origine: collegamento, allegati letti, impronta del messaggio originale."""
    if not pec_id or not pec_audit_db or not Path(pec_audit_db).exists():
        return {}
    try:
        from pct.pec_pipeline import PecAuditRepository

        dettaglio: dict[str, Any] = PecAuditRepository(pec_audit_db, tenant_id=tenant_id).get_message_detail(pec_id) or {}
    except Exception:
        return {}
    messaggio: dict[str, Any] = dettaglio.get("message") if isinstance(dettaglio.get("message"), dict) else {}
    allegati = [a for a in dettaglio.get("attachments") or [] if isinstance(a, dict)]
    letti = [a for a in allegati if float(a.get("ocr_coverage") or 0) > 0 and a.get("classification") not in ("firma",)]
    impronta = str(messaggio.get("mime_sha256") or "")
    parti = ["PEC collegata al fascicolo" if messaggio.get("linked_fascicolo_id") else "PEC non ancora collegata al fascicolo"]
    if allegati:
        parti.append(f"{len(letti)} allegati letti su {len(allegati)}")
    if impronta:
        parti.append(f"messaggio originale conservato, impronta SHA-256 {impronta[:12]}…")
    collegamento = dettaglio.get("fascicolo_link") if isinstance(dettaglio.get("fascicolo_link"), dict) else {}
    candidati = [c for c in collegamento.get("candidates") or [] if isinstance(c, dict) and c.get("id")]
    rapporto = dettaglio.get("validation_report") if isinstance(dettaglio.get("validation_report"), dict) else {}
    profilo = rapporto.get("procedural_profile") if isinstance(rapporto.get("procedural_profile"), dict) else {}
    return {
        "profilo": {"cliente": str(profilo.get("cliente") or ""), "ufficio": str(profilo.get("ufficio") or ""),
                    "rg": str(profilo.get("numero_rg") or ""), "giudice": str(profilo.get("giudice") or ""),
                    "controparte": str(profilo.get("convenuto_principale") or "")},
        "candidati": [(str(c.get("id")), float(c.get("score") or 0)) for c in candidati[:3]],
        "pecId": pec_id,
        "pecHref": pec_source_href(pec_id, ""),
        "mimeHref": f"/api/pec/messages/{pec_id}/mime",
        "collegata": bool(messaggio.get("linked_fascicolo_id")),
        "prova": " · ".join(parti),
    }


def _fascicolo_da_proporre(impegno_fascicolo: str, suggerito: str, candidati: list[tuple[str, float]]) -> tuple[str, str]:
    """(id, motivo) del fascicolo da proporre per collegare la PEC; mai indovinato quando i candidati si equivalgono."""
    if impegno_fascicolo:
        return impegno_fascicolo, "indicato sull'impegno"
    if suggerito:
        return suggerito, "trovato con il numero di ruolo dell'impegno"
    if candidati and candidati[0][1] >= 0.9 and (len(candidati) == 1 or candidati[1][1] < candidati[0][1] - 0.2):
        return candidati[0][0], "candidato del presidio PEC con RG e ufficio coincidenti"
    return "", ""


def _riga(note: str, etichetta: str) -> str:
    trovato = re.search(rf"^{re.escape(etichetta)}:\s*(.+)$", str(note or ""), re.M)
    return trovato.group(1).strip() if trovato else ""


def _parole(testo: str) -> set[str]:
    return {p for p in re.findall(r"[a-zà-ý']{3,}", str(testo or "").lower())}


def _rg_anno(valore: str) -> tuple[str, str]:
    trovato = re.search(r"(\d{1,7})\s*/\s*(\d{4})", str(valore or ""))
    return (trovato.group(1).lstrip("0"), trovato.group(2)) if trovato else ("", "")


def _stesso_ufficio(ufficio_pec: str, tribunale: str) -> bool:
    generiche = {"tribunale", "ordinario", "corte", "ufficio", "giudice", "pace", "sezione", "lavoro", "civile"}
    luogo = _parole(ufficio_pec) - generiche
    return bool(luogo) and luogo <= _parole(tribunale)


def _fascicolo_per_rg(fascicoli: Any, rg: str, ufficio: str) -> Any:
    """Il fascicolo con lo stesso numero di ruolo e anno presso lo stesso ufficio: identificazione certa, se unica."""
    numero, anno = _rg_anno(rg)
    if not numero or fascicoli is None:
        return None
    try:
        elenco = list(fascicoli.tutti(archiviati=True))
    except TypeError:
        elenco = list(fascicoli.tutti())
    except Exception:
        return None
    uguali = [f for f in elenco
              if _rg_anno(f"{getattr(f, 'numero_rg', '')}/{getattr(f, 'anno_rg', '')}") == (numero, anno)
              and (not ufficio or _stesso_ufficio(ufficio, str(getattr(f, "tribunale", "") or "")))]
    return uguali[0] if len(uguali) == 1 else None


def _fascicoli_del_cliente(fascicoli: Any, cliente: str, ufficio: str) -> list[Any]:
    """Fascicoli aperti dello stesso cliente (tutte le parole del nome), prima quelli dello stesso ufficio e senza RG."""
    nome = _parole(cliente)
    if len(nome) < 2 or fascicoli is None:
        return []
    try:
        elenco = list(fascicoli.tutti(archiviati=False))
    except TypeError:
        elenco = list(fascicoli.tutti())
    except Exception:
        return []
    stessi = [f for f in elenco if nome <= _parole(getattr(f, "nome_cliente", ""))
              and str(getattr(getattr(f, "stato", ""), "value", getattr(f, "stato", "")) or "").upper() not in {"DEFINITO", "ARCHIVIATO"}]
    def ordine(f: Any) -> tuple[int, int]:
        stesso_ufficio = _stesso_ufficio(ufficio, str(getattr(f, "tribunale", "") or ""))
        return (0 if stesso_ufficio else 1, 0 if not str(getattr(f, "numero_rg", "") or "").strip() else 1)

    return sorted(stessi, key=ordine)


def _descrivi_fascicolo(fascicoli: Any, fascicolo_id: str) -> str:
    try:
        fascicolo = fascicoli.get(fascicolo_id) if fascicoli is not None else None
    except Exception:
        fascicolo = None
    if fascicolo is None:
        return ""
    return riga_contesto(client=str(getattr(fascicolo, "nome_cliente", "") or ""), numero_fascicolo=str(getattr(fascicolo, "numero", "") or ""),
                         rg=str(getattr(fascicolo, "rg_completo", "") or ""), ufficio=str(getattr(fascicolo, "tribunale", "") or ""))


def _impegno(event_id: str, agenda: Any, scadenziario: Any) -> tuple[Any, str]:
    """(oggetto, genere) dall'id dell'evento d'agenda: «scadenza-<id>» per lo scadenziario, altrimenti appuntamento."""
    if event_id.startswith("scadenza-"):
        return scadenziario.get(event_id.removeprefix("scadenza-")), "scadenza"
    return agenda.get(event_id), "appuntamento"


def build_agenda_lavorazione_payload(
    event_id: str,
    *,
    agenda_loader: Callable[[], Any],
    scadenziario_loader: Callable[[], Any],
    pec_audit_db: str = "",
    tenant_id: str = "default",
    fascicoli_loader: Callable[[], Any] | None = None,
    fascicolo_suggerito: str = "",
) -> dict[str, Any]:
    event_id = str(event_id or "").strip()
    if not event_id:
        return {"ok": False, "message": "Impegno non indicato."}
    agenda, scadenziario = agenda_loader(), scadenziario_loader()
    impegno, genere = _impegno(event_id, agenda, scadenziario)
    if impegno is None:
        return {"ok": False, "message": "Impegno non trovato: potrebbe essere stato spostato o eliminato."}
    note = str(getattr(impegno, "note", "") or "")
    descrizione = str(getattr(impegno, "descrizione", "") or "")
    scadenze = list(scadenziario.tutte(solo_aperte=False))
    proposte = proposte_collegate(scadenze, impegno, id_impegno=event_id if genere == "appuntamento" else "")
    pec = sorted(riferimenti_pec(impegno))
    prova = _prova_pec(pec_audit_db, tenant_id, pec[0]) if pec else {}
    fascicolo = fascicolo_dell_impegno(impegno)
    notifica = notifica_collegata(note, descrizione)
    collega_pec: dict[str, Any] = {}
    if prova and not prova.get("collegata"):
        archivio = fascicoli_loader() if fascicoli_loader else None
        proposto, motivo = _fascicolo_da_proporre(fascicolo, str(fascicolo_suggerito or "").strip(), prova.get("candidati") or [])
        # Fonte: il profilo processuale letto da Comunicazione.xml (cliente, ufficio, RG e anno); le note come riserva.
        profilo = prova.get("profilo") or {}
        cliente = profilo.get("cliente") or _riga(note, "Cliente")
        ufficio = profilo.get("ufficio") or _riga(note, "Ufficio")
        rg = profilo.get("rg") or _riga(note, "RG")
        per_rg = None if proposto else _fascicolo_per_rg(archivio, rg, ufficio)
        if per_rg is not None:
            proposto, motivo = str(getattr(per_rg, "id", "") or ""), "stesso numero di ruolo, anno e ufficio della comunicazione"
        alternative = [] if proposto else _fascicoli_del_cliente(archivio, cliente, ufficio)
        if len(alternative) == 1:
            proposto = str(getattr(alternative[0], "id", "") or "")
            senza_rg = not str(getattr(alternative[0], "numero_rg", "") or "").strip()
            stesso = _stesso_ufficio(ufficio, str(getattr(alternative[0], "tribunale", "") or ""))
            motivo = ("unico fascicolo aperto dello stesso cliente" + (" presso lo stesso ufficio" if stesso else "")
                      + (", ancora senza RG" if senza_rg else ""))
            alternative = []
        descrizione_fascicolo = _descrivi_fascicolo(archivio, proposto) if proposto else ""
        numero, anno = _rg_anno(rg)
        titolo = " c. ".join(nome_proprio(x) for x in (cliente, str(profilo.get("controparte") or "")) if x)
        nuovo = {"titolo": titolo, "numero_rg": numero, "anno_rg": anno, "tribunale": nome_proprio(ufficio) if ufficio.isupper() else ufficio,
                 "giudice": nome_proprio(str(profilo.get("giudice") or "")), "source_pec": str(prova.get("pecId") or "")}
        collega_pec = {
            "nuovoFascicoloHref": "/fascicoli/nuovo?" + urlencode({k: v for k, v in nuovo.items() if v}),
            "cliente": nome_proprio(cliente) if cliente.isupper() else cliente,
            "rg": rg,
            "alternative": [{"id": str(getattr(f, "id", "") or ""), "fascicolo": _descrivi_fascicolo(archivio, str(getattr(f, "id", "") or ""))}
                            for f in alternative[:4]],
            "fascicoloId": proposto if descrizione_fascicolo else "",
            "fascicolo": descrizione_fascicolo,
            "motivo": motivo if descrizione_fascicolo else "",
            "azione": f"/api/pec/messages/{quote(str(prova.get('pecId') or ''), safe='')}/salva-fascicolo",
            "scegliHref": str(prova.get("pecHref") or ""),
        }
    prova.pop("candidati", None)
    prova.pop("profilo", None)
    return {
        "ok": True,
        "id": event_id,
        "genere": genere,
        "arrivo": _arrivo(note) or _arrivo(descrizione) or (date_italiane(descrizione[:400]) if genere == "appuntamento" else ""),
        "prova": prova,
        "proposte": [voce_proposta(s) for s in proposte],
        "propostaPropria": genere == "scadenza" and e_bozza(impegno),
        "collegamento": collegamento_remoto(impegno),
        "collegaPec": collega_pec,
        "notificaHref": f"/notifiche-legali?notifica={quote(notifica, safe='')}" if notifica else "",
        "fascicoloHref": f"/fascicoli/{quote(fascicolo, safe='')}" if fascicolo else "",
        "prossimo": date_italiane(prossimo_passo(note, descrizione)),
    }


__all__ = ["build_agenda_lavorazione_payload"]
