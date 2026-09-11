"""Cliente del fascicolo a cui appartiene una PEC processuale.

Base normativa e limite di ambito:

- D.M. 44/2011, art. 13 (ricevute del deposito telematico: accettazione,
  consegna, esito dei controlli automatici, intervento della cancelleria) e
  art. 16 (comunicazioni e biglietti di cancelleria via PEC), con le
  Specifiche tecniche DGSIA (rev. 04.01.24) che fissano i tracciati
  ``Comunicazione.xml`` / ``EsitoAtto.xml``: il procedimento e' identificato
  da ufficio giudiziario e numero di ruolo, non dal nominativo del cliente.
- Il cliente dello studio quindi non si legge dalla PEC: si ricava soltanto
  dall'anagrafica del fascicolo dello studio collegato a quel procedimento.
  Nessun nome viene dedotto dal testo del messaggio.
- GDPR 2016/679, art. 5.1.c (minimizzazione): verso l'interfaccia escono solo
  nominativo e tipo del cliente, mai codice fiscale, recapiti o documenti.

Regole di collegamento (fail-closed):

1. PEC gia' collegata dalla pipeline (``linked_fascicolo_id``): fascicolo
   ``collegato``.
2. Altrimenti si propone il primo candidato della riconciliazione solo se il
   numero di ruolo e' certificato dall'XML ministeriale, oppure se RG e ufficio
   coincidono entrambi: fascicolo ``da_confermare`` dall'avvocato.
3. In ogni altro caso nessun fascicolo e nessun cliente vengono proposti.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "MOTIVO_RG_CERTIFICATO",
    "cliente_payload",
    "fascicolo_payload",
    "resolve_pec_fascicolo_cliente",
    "select_pec_fascicolo",
]

MOTIVO_RG_CERTIFICATO = "RG certificato dall'XML ministeriale"
MOTIVO_RG_COINCIDENTE = "RG coincidente"
MOTIVO_UFFICIO = "ufficio compatibile"
_STATI_CHIUSI = {"DEFINITO", "ARCHIVIATO"}


def _text(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def _attr(obj: Any, *names: str) -> str:
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        cleaned = _text(value)
        if cleaned:
            return cleaned
    return ""


def _norm(value: Any) -> str:
    return re.sub(r"[\W_]+", " ", _text(value).casefold()).strip()


def select_pec_fascicolo(detail: dict[str, Any]) -> dict[str, Any]:
    """Sceglie il fascicolo della PEC applicando le regole fail-closed del modulo."""

    message = detail.get("message") if isinstance(detail.get("message"), dict) else {}
    linked_id = _text(message.get("linked_fascicolo_id"), 80)
    link = detail.get("fascicolo_link") if isinstance(detail.get("fascicolo_link"), dict) else {}
    candidates = [item for item in (link.get("candidates") or []) if isinstance(item, dict)]
    if linked_id:
        linked = next((item for item in candidates if _text(item.get("id"), 80) == linked_id), {})
        return {
            "fascicolo_id": linked_id,
            "stato": "collegato",
            "motivazioni": [str(reason) for reason in (linked.get("reasons") or []) if reason] or ["Fascicolo collegato alla PEC dalla pipeline."],
        }
    if candidates:
        best = candidates[0]
        reasons = [str(reason) for reason in (best.get("reasons") or []) if reason]
        certified = MOTIVO_RG_CERTIFICATO in reasons
        rg_and_office = MOTIVO_RG_COINCIDENTE in reasons and MOTIVO_UFFICIO in reasons
        best_id = _text(best.get("id"), 80)
        if best_id and (certified or rg_and_office):
            return {"fascicolo_id": best_id, "stato": "da_confermare", "motivazioni": reasons}
    return {"fascicolo_id": "", "stato": "non_collegato", "motivazioni": []}


def fascicolo_payload(fascicolo: Any) -> dict[str, Any]:
    fascicolo_id = _attr(fascicolo, "id")
    numero = _attr(fascicolo, "numero")
    titolo = _attr(fascicolo, "titolo")
    numero_rg = _attr(fascicolo, "numero_rg")
    anno_rg = _attr(fascicolo, "anno_rg")
    rg = f"{numero_rg}/{anno_rg}" if numero_rg and anno_rg and anno_rg != "0" and "/" not in numero_rg else numero_rg
    stato = _attr(fascicolo, "stato")
    return {
        "id": fascicolo_id,
        "numero": numero,
        "titolo": titolo,
        "label": " - ".join(part for part in (numero, titolo) if part) or fascicolo_id,
        "rg": rg,
        "ufficio": _attr(fascicolo, "tribunale"),
        "stato": stato,
        "aperto": stato.upper() not in _STATI_CHIUSI,
        "href": f"/fascicoli/{fascicolo_id}" if fascicolo_id else "/fascicoli",
    }


def cliente_payload(cliente: Any, *, fonte: str) -> dict[str, Any]:
    tipo = _attr(cliente, "tipo")
    giuridica = tipo.upper() == "PERSONA_GIURIDICA"
    nome = "" if giuridica else _attr(cliente, "nome")
    cognome = "" if giuridica else _attr(cliente, "cognome")
    ragione_sociale = _attr(cliente, "ragione_sociale")
    nome_completo = ragione_sociale if giuridica else " ".join(part for part in (nome, cognome) if part)
    return {
        "id": _attr(cliente, "id"),
        "tipo": tipo,
        "nome": nome,
        "cognome": cognome,
        "ragione_sociale": ragione_sociale if giuridica else "",
        "nome_completo": nome_completo or ragione_sociale,
        "fonte": fonte,
    }


def _cliente_da_nome_denormalizzato(nome_cliente: str, clienti: Any) -> Any | None:
    """Anagrafica con nominativo identico al nome riportato sul fascicolo, se unica."""

    target = _norm(nome_cliente)
    if not target or clienti is None:
        return None
    try:
        tutti = list(clienti.tutti())
    except Exception:
        return None
    matches = []
    for cliente in tutti:
        nome = _attr(cliente, "nome")
        cognome = _attr(cliente, "cognome")
        variants = {
            _norm(_attr(cliente, "ragione_sociale")),
            _norm(f"{nome} {cognome}"),
            _norm(f"{cognome} {nome}"),
        }
        if target in variants:
            matches.append(cliente)
    return matches[0] if len(matches) == 1 else None


def resolve_pec_fascicolo_cliente(detail: dict[str, Any], *, fascicoli: Any, clienti: Any | None) -> dict[str, Any]:
    """Restituisce fascicolo e cliente di una PEC per profilo processuale e salvataggio."""

    selection = select_pec_fascicolo(detail)
    base = {
        "ok": True,
        "stato": selection["stato"],
        "motivazioni": selection["motivazioni"],
        "fascicolo": {},
        "cliente": {},
    }
    fascicolo_id = selection["fascicolo_id"]
    if not fascicolo_id:
        base["messaggio"] = "PEC non ancora ricondotta a un fascicolo: indica il cliente per cercarlo."
        return base
    fascicolo = fascicoli.get(fascicolo_id) if fascicoli is not None else None
    if fascicolo is None:
        base.update(stato="non_collegato", motivazioni=[], messaggio="Il fascicolo collegato alla PEC non è più presente in archivio.")
        return base
    base["fascicolo"] = fascicolo_payload(fascicolo)

    cliente = None
    fonte = ""
    id_cliente = _attr(fascicolo, "id_cliente")
    if id_cliente and clienti is not None:
        try:
            cliente = clienti.get(id_cliente)
        except Exception:
            cliente = None
        fonte = "anagrafica_cliente"
    nome_cliente = _attr(fascicolo, "nome_cliente")
    if cliente is None and nome_cliente:
        cliente = _cliente_da_nome_denormalizzato(nome_cliente, clienti)
        fonte = "anagrafica_cliente" if cliente is not None else ""
    if cliente is not None:
        base["cliente"] = cliente_payload(cliente, fonte=fonte)
    elif nome_cliente:
        # Nome riportato sul fascicolo senza anagrafica univoca: si mostra com'e',
        # senza separare nome e cognome per non inventare la loro divisione.
        base["cliente"] = {
            "id": "",
            "tipo": "",
            "nome": "",
            "cognome": "",
            "ragione_sociale": "",
            "nome_completo": nome_cliente,
            "fonte": "nome_cliente_fascicolo",
        }
    if not base["cliente"]:
        base["messaggio"] = "Il fascicolo collegato non ha un cliente indicato in anagrafica."
    elif selection["stato"] == "collegato":
        base["messaggio"] = "Cliente letto dall'anagrafica del fascicolo collegato alla PEC."
    else:
        base["messaggio"] = "Fascicolo proposto per numero di ruolo e ufficio: conferma prima di salvare."
    return base
