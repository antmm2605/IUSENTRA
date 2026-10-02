"""Verificatore condiviso: atti catalogati, date documentate, regole e prove.

Consulta l'archivio delle letture; non rilegge PDF, non esegue OCR e non invia PEC.
La data proposta non sostituisce l'esame del rito, dei destinatari e del calendario.
"""

from web.services.obblighi_notifica_runtime import obblighi_fascicolo


def verifica_fascicolo(fascicolo) -> dict:
    obblighi = obblighi_fascicolo(fascicolo)
    from flask import g
    user = g.get("utente_corrente")
    for item in obblighi:
        from pct.notifiche_conoscenza import fonte_regola
        item["fonti_verificate"] = fonte_regola(item["regola"])
        item["termine_confermato"] = False
        item["verifiche"] = [
            "Controlla rito, regime applicabile e data di decorrenza nel documento.",
            "Verifica tutti i destinatari, eventuale notifica all'estero e indirizzi nei pubblici elenchi.",
            "Controlla sospensione feriale, festività e termini assegnati dal giudice prima della conferma.",
        ]
        if item["scadenza"]:
            item["verifiche"].insert(0, "Data proposta dalla regola: conferma nel calcolatore dei termini con il profilo del procedimento.")
        if item["stato"] == "notificato":
            item["verifiche"] = ["Prova riferita espressamente all'atto e a tutti i destinatari."]
        item["source_href"] = f"/fascicoli/{fascicolo.id}/documenti/{item['documentoId']}/visualizza"
    return {"ok": True, "fascicolo_id": str(fascicolo.id), "obblighi": obblighi,
            "puo_verificare": bool(user and user.ha_permesso("fascicoli.scrivi")),
            "documenti": [{"id": str(d.id), "nome": str(d.nome)} for d in fascicolo.documenti],
            "message": "Verifica basata sui documenti catalogati e sulle letture registrate del fascicolo."
                if obblighi else "Non risultano obblighi riconosciuti nei documenti catalogati. Questo non certifica l'assenza di notifiche: esamina l'atto e il provvedimento."}
