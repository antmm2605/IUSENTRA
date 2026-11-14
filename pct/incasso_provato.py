"""«Pagato» solo con la prova dell'incasso o con la decisione dell'avvocato.

Un credito si estingue con l'adempimento (art. 1176 e art. 1188 c.c.: il pagamento fatto al creditore);
la prova dell'avvenuto pagamento spetta a chi lo afferma (art. 2697 c.c.). Per le spese distratte in
favore del difensore (art. 93 c.p.c.) il pagamento arriva all'avvocato, che ne emette fattura solo
all'incasso (art. 6, terzo comma, D.P.R. 633/1972). Quindi una voce economica è «pagata» solo se:

- l'incasso è registrato (ricevuta di pagamento della parcella, saldo nel registro degli incassi), oppure
- la lettura documentale ha trovato la prova del pagamento (``payment_proven``), oppure
- l'avvocato ha segnato il pagamento (autore umano del passaggio a «pagato»).

Uno stato «pagato» scritto da un automatismo senza nessuna di queste prove non è una decisione
dell'avvocato: si riconvalida a «da incassare», con il motivo nello storico (collaudo 10/11/2026, G-4:
«Pagato, 17/04/2026, Bonifico bancario» scritto dal «Lex AI backfill» con la data della sentenza).
Modulo puro: nessuna scrittura, restituisce la voce corretta.
"""

from __future__ import annotations

from typing import Any, Mapping

STATI_PAGATI = frozenset({"pagato", "parziale"})
STATO_DA_INCASSARE = "da_incassare"
AUTORE_RICONVALIDA = "IUSENTRA riconvalida incassi"
ORIGINE_RICONVALIDA = "riconvalida_incasso"
NORMA = "artt. 1188 e 2697 c.c.; art. 6, terzo comma, D.P.R. 633/1972"

# Autori che sono automatismi del software, non persone dello studio (stessa regola di
# web/services/contributo_stato_runtime.decisione_dell_avvocato).
_AUTOMATICI = ("import", "automatic", "automatico", "document ai", "lex", "scheduler", "iusentra", "archivio delle letture",
               "backfill", "presidio", "riallineamento")


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def autore_automatico(autore: Any) -> bool:
    autore = _testo(autore).casefold()
    return not autore or any(m in autore for m in _AUTOMATICI)


def _stato(voce: Mapping[str, Any]) -> str:
    stato = _testo(voce.get("status") or voce.get("stato")).lower()
    return "pagato" if not stato and voce.get("pagato") is True else stato


def pagato_deciso_dall_avvocato(voce: Mapping[str, Any]) -> bool:
    """Vero se il passaggio a «pagato» (o «parziale») l'ha fatto una persona dello studio."""
    storico = [r for r in (voce.get("history") or voce.get("storico") or []) if isinstance(r, Mapping)]
    passaggi = [r for r in storico if _testo(r.get("toStatus") or r.get("to_status")).lower() in STATI_PAGATI]
    if passaggi:
        return not autore_automatico(passaggi[-1].get("by") or passaggi[-1].get("updated_by"))
    return not autore_automatico(voce.get("updated_by") or voce.get("updatedBy"))


def pagamento_provato(voce: Mapping[str, Any], *, incasso_registrato: bool = False) -> bool:
    evidenza = voce.get("evidenza_dispositivo") if isinstance(voce.get("evidenza_dispositivo"), Mapping) else {}
    return bool(incasso_registrato or voce.get("payment_proven") is True or evidenza.get("payment_proven") is True
                or _testo(voce.get("incasso_id") or voce.get("receipt_id")))


def pagato_senza_prova(voce: Mapping[str, Any], *, incasso_registrato: bool = False) -> bool:
    """«Pagato» scritto da un automatismo, senza incasso registrato né prova letta."""
    return (_stato(voce) in STATI_PAGATI and not pagato_deciso_dall_avvocato(voce)
            and not pagamento_provato(voce, incasso_registrato=incasso_registrato))


def riconvalida_voce(voce: Mapping[str, Any], *, incasso_registrato: bool = False, adesso: str = "") -> dict[str, Any] | None:
    """La voce riportata a «da incassare», o None se non va toccata (decisione dell'avvocato o prova)."""
    if not pagato_senza_prova(voce, incasso_registrato=incasso_registrato):
        return None
    nuova = dict(voce)
    prima = _stato(voce)
    data_segnata = _testo(voce.get("data_pagamento"))[:10]
    nuova.update(status=STATO_DA_INCASSARE, pagato=False, data_pagamento="", metodo="", updated_at=adesso or voce.get("updated_at"),
                 updated_by=AUTORE_RICONVALIDA)
    motivo = ("Segnato come pagato da una lettura automatica" + (f" con la data {data_segnata}" if data_segnata else "")
              + " senza incasso registrato né prova di pagamento: da incassare (" + NORMA + ").")
    storico = list(voce.get("history") or voce.get("storico") or [])
    storico.append({"at": adesso, "by": AUTORE_RICONVALIDA, "fromStatus": prima, "toStatus": STATO_DA_INCASSARE,
                    "fromImporto": voce.get("importo"), "toImporto": voce.get("importo"), "fromDataPagamento": data_segnata,
                    "fromMetodo": _testo(voce.get("metodo")), "note": motivo, "origine": ORIGINE_RICONVALIDA})
    nuova["history"] = storico[-25:]
    nuova.pop("storico", None)
    nuova["note_riconvalida"] = motivo
    return nuova


def motivo_credito_aperto(economico_letto: Mapping[str, Any]) -> str:
    """Perché il fascicolo definito non è pronto per l'archivio: il credito liquidato non è incassato.

    ``economico_letto``: il quadro economico della Lettura (``pct.fascicolo_lettura.economico``). Il prossimo passo
    è chiedere il pagamento; contro un'amministrazione dello Stato o un ente pubblico non economico il precetto si
    notifica solo decorsi 120 giorni dalla notifica del titolo esecutivo (art. 14, comma 1, D.L. 669/1996), poi
    precetto e pignoramento nei termini degli artt. 480-482 c.p.c.
    """
    stato = _testo(economico_letto.get("liquidazione_incasso"))
    if stato not in {"non_incassata", "parziale"}:
        return ""
    importo = _testo(economico_letto.get("liquidato_it")) or "liquidato"
    quanto = "incassato solo in parte" if stato == "parziale" else "non ancora incassato"
    return (f"Credito di {importo} liquidato dal giudice {quanto}: prima di archiviare chiedere il pagamento alla parte "
            "condannata; contro una pubblica amministrazione il precetto si notifica decorsi 120 giorni dalla notifica "
            "del titolo (art. 14 D.L. 669/1996), poi l'esecuzione (artt. 480-482 c.p.c.).")


__all__ = ["AUTORE_RICONVALIDA", "motivo_credito_aperto", "NORMA", "ORIGINE_RICONVALIDA", "STATO_DA_INCASSARE", "autore_automatico",
           "pagamento_provato", "pagato_deciso_dall_avvocato", "pagato_senza_prova", "riconvalida_voce"]
