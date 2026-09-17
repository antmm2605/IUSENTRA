"""L'archivio delle letture nella lettura del fascicolo: che cosa i motori hanno letto e collaudato.

Le udienze e i termini letti dai documenti e dalle PEC, le prove di notifica,
i numeri di ruolo, i fatti plausibili da confermare e lo stato della lettura
automatica. La lettura non rilegge nulla: riporta l'archivio.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_it, pulisci

ETICHETTE_CAMPO = {"udienza": "udienza", "termine": "termine", "costituzione": "costituzione", "decorrenza": "decorrenza", "notifica": "notifica", "accettazione": "accettazione", "consegna": "consegna", "comunicazione": "comunicazione", "provvedimento": "provvedimento", "data_atto": "data dell'atto", "deposito": "deposito"}


def _azione(voce: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pulisci(voce.get("id")),
        "prove": list(voce.get("prove") or []),
        "tipo": "udienza" if pulisci(voce.get("type")) == "udienza_documento" else "termine",
        "data": pulisci(voce.get("date")) or data_it(voce.get("dateIso")),
        "data_iso": pulisci(voce.get("dateIso")),
        "ora": pulisci(voce.get("time")),
        "verifica": pulisci(voce.get("verifica")),
        "verifica_etichetta": pulisci(voce.get("verificaLabel")),
        "documento_id": pulisci(voce.get("documentId")),
        "descrizione": pulisci(voce.get("description"))[:200],
        "scaduta": bool(voce.get("overdue")),
    }


def archivio(dati: dict[str, Any]) -> dict[str, Any]:
    riassunto = dict(dati.get("riassunto") or {})
    per_verifica = dict(riassunto.get("per_verifica") or {})
    azioni = [_azione(voce) for voce in list(dati.get("azioni") or [])]
    stato = dict(dati.get("stato") or {})
    return {
        "disponibile": bool(dati),
        "ricevute": list(dati.get("ricevute") or []),
        "totale": int(riassunto.get("totale") or 0),
        "verificati": int(per_verifica.get("verificata") or 0) + int(per_verifica.get("corretta") or 0),
        "plausibili": int(per_verifica.get("plausibile") or 0),
        "respinti": int(per_verifica.get("respinta") or 0),
        "udienze": [voce for voce in azioni if voce["tipo"] == "udienza"],
        "termini": [voce for voce in azioni if voce["tipo"] == "termine"],
        "prove_notifica": int(riassunto.get("prove_notifica") or 0),
        "notifiche_datate": int(riassunto.get("notifiche") or 0),
        "ruoli": [pulisci(voce.get("valore")) for voce in list(dati.get("ruoli") or [])],
        "eventi": [
            {
                "etichetta": pulisci(voce.get("etichetta")),
                "famiglia": pulisci(voce.get("famiglia")),
                "data": pulisci(voce.get("data")) or data_it(voce.get("data_iso")),
                "data_iso": pulisci(voce.get("data_iso")),
                "verifica": pulisci(voce.get("verifica")),
                "verifica_etichetta": pulisci(voce.get("verifica_etichetta")),
                "oggetto_id": pulisci(voce.get("oggetto_id")),
                "contesto": pulisci(voce.get("contesto"))[:200],
            }
            for voce in list(dati.get("eventi") or [])
        ],
        "da_confermare": [
            {"id": pulisci(voce.get("id")), "campo": ETICHETTE_CAMPO.get(pulisci(voce.get("campo")), pulisci(voce.get("campo"))), "etichetta": pulisci(voce.get("etichetta")), "valore": pulisci(voce.get("valore")), "letto": pulisci(voce.get("valore_letto")), "oggetto_id": pulisci(voce.get("oggetto_id"))}
            for voce in list(riassunto.get("da_confermare") or [])
        ],
        "per_motore": dict(riassunto.get("per_motore") or {}),
        "lettura_automatica": {
            "in_corso": bool(stato.get("in_corso")),
            "completa": bool(stato.get("completa")),
            "da_leggere": int(stato.get("da_leggere") or 0),
            "ultima_lettura": pulisci(stato.get("ultima_lettura_it")),
        },
        "collaudo": dict(dati.get("collaudo") or {}),
    }


def descrivi(archivio_letto: dict[str, Any]) -> str:
    if not archivio_letto.get("disponibile"):
        return ""
    pezzi = []
    if archivio_letto["verificati"]:
        pezzi.append(f"{archivio_letto['verificati']} dati verificati dal software")
    if archivio_letto["plausibili"]:
        pezzi.append(f"{archivio_letto['plausibili']} da confermare")
    if archivio_letto["udienze"]:
        pezzi.append(f"{len(archivio_letto['udienze'])} udienze lette")
    if archivio_letto["termini"]:
        pezzi.append(f"{len(archivio_letto['termini'])} termini letti")
    if archivio_letto["prove_notifica"]:
        pezzi.append(f"{archivio_letto['prove_notifica']} prove di notifica")
    if archivio_letto.get("eventi"):
        pezzi.append(f"{len(archivio_letto['eventi'])} eventi comunicati dalle PEC")
    return ", ".join(pezzi)


__all__ = ["archivio", "descrivi"]
