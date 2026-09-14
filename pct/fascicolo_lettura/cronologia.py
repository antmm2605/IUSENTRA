"""Che cosa è stato fatto, in ordine di tempo, con la prova di ogni fatto."""

from __future__ import annotations

from typing import Any

from ._testo import data_da, data_it, dataora_it, elenco, pulisci
from .modello import Evento

TIPI_ATTIVITA = {
    "UDIENZA": "udienza",
    "DEPOSITO_ATTI": "deposito",
    "ISCRIZIONE_A_RUOLO": "iscrizione a ruolo",
    "NOTIFICA": "notifica",
    "CONSULTAZIONE": "consultazione",
    "TERMINE_SCADENZA": "termine",
    "ACCESSO_ATTI": "accesso agli atti",
    "MEDIAZIONE": "mediazione",
    "CTU": "CTU",
    "SENTENZA_EMESSA": "sentenza",
    "PROVVEDIMENTO": "provvedimento",
    "COMUNICAZIONE_CANCELLERIA": "comunicazione di cancelleria",
    "APPELLO": "appello",
    "ESECUZIONE": "esecuzione",
    "ACCORDO": "accordo",
    "RINVIO": "rinvio",
    "ALTRO": "attività",
}
ESITI = {
    "FAVOREVOLE": "esito favorevole",
    "PARZIALE": "esito parziale",
    "SFAVOREVOLE": "esito sfavorevole",
    "RINVIATO": "rinviata",
    "ANNULLATO": "annullata",
    "IN_ATTESA": "in attesa di esito",
    "NON_APPLICABILE": "",
}


_ACQUISIZIONI_TECNICHE = ("acquisizione file ufficiali", "download ufficiale completo", "acquisiti localmente da polisweb", "acquisizione guidata da polisweb")


def _acquisizione_tecnica(voce: dict[str, Any]) -> bool:
    """Sincronizzazioni e download dal portale: eventi tecnici, non fatti della causa."""
    tipo = pulisci(voce.get("tipo")).upper()
    testo = f"{pulisci(voce.get('titolo'))} {pulisci(voce.get('descrizione'))}".lower()
    return tipo in {"CONSULTAZIONE", "SINCRONIZZAZIONE", "IMPORTAZIONE"} and any(marker in testo for marker in _ACQUISIZIONI_TECNICHE)


def _chiave(data: str) -> str:
    giorno = data_da(data)
    return giorno.isoformat() if giorno else "0000-00-00"


def cronologia(
    attivita: list[dict[str, Any]],
    depositi_letti: list[dict[str, Any]],
    notifiche_lette: list[dict[str, Any]],
    documenti_letti: list[dict[str, Any]],
    appuntamenti: list[dict[str, Any]],
    oggi: Any,
) -> list[dict[str, Any]]:
    eventi: list[Evento] = []
    for voce in attivita:
        tipo = pulisci(voce.get("tipo")).upper()
        if tipo == "NOTIFICA":
            continue  # le notifiche entrano dalla loro lettura, con lo stato di perfezionamento
        if _acquisizione_tecnica(voce):
            continue
        esito = ESITI.get(pulisci(voce.get("esito")).upper(), "")
        eventi.append(Evento(
            data=pulisci(voce.get("data"))[:10],
            categoria=TIPI_ATTIVITA.get(tipo, "attività"),
            titolo=pulisci(voce.get("titolo")) or TIPI_ATTIVITA.get(tipo, "attività"),
            dettaglio=pulisci(voce.get("descrizione"))[:160],
            esito=esito,
            fonte="attività processuale",
            fonte_id=pulisci(voce.get("id")),
        ))
    for deposito in depositi_letti:
        if deposito.get("importato"):
            continue  # gli atti del fascicolo d'ufficio sono già nelle attività importate
        eventi.append(Evento(
            data=_chiave(deposito["data"]) if deposito["data"] else "",
            categoria="deposito",
            titolo=f"Deposito telematico: {deposito['atto']}",
            dettaglio=deposito["attesa"] if not deposito["perfezionato"] else "",
            esito=deposito["fase"],
            fonte="deposito PCT",
            fonte_id=deposito["id"],
        ))
    for notifica in notifiche_lette:
        eventi.append(Evento(
            data=_chiave(notifica["data"]) if notifica["data"] else "",
            categoria="notifica",
            titolo=f"Notifica: {notifica['atto']}" + (f" a {elenco(notifica['destinatari'])}" if notifica["destinatari"] else ""),
            dettaglio=notifica.get("prossima_azione", "") if notifica["aperta"] else "",
            esito=notifica["stato_etichetta"],
            fonte="presidio notifiche" if notifica["origine"] == "presidio" else "attività processuale",
            fonte_id=notifica["id"],
        ))
    for documento in documenti_letti:
        if documento["sezione"] in {"provvedimenti", "comunicazioni", "notifiche"} or documento["natura"] == "atto_principale":
            eventi.append(Evento(
                data=documento["data"],
                categoria={"provvedimenti": "provvedimento", "comunicazioni": "comunicazione", "notifiche": "prova di notifica"}.get(documento["sezione"], "atto"),
                titolo=documento["etichetta"],
                dettaglio=documento["nome"],
                esito="",
                fonte="documento catalogato",
                fonte_id=documento["id"],
            ))
    giorno_oggi = data_da(oggi)
    giorni_udienza = {_chiave(evento.data) for evento in eventi if evento.categoria == "udienza"}
    for appuntamento in appuntamenti:
        quando = data_da(appuntamento.get("data_ora"))
        if not quando or (giorno_oggi and quando > giorno_oggi):
            continue
        # L'udienza registrata come attivita' processuale e' gia' in cronologia:
        # l'appuntamento in agenda dello stesso giorno non e' un secondo fatto.
        if quando.isoformat() in giorni_udienza and "udienz" in pulisci(appuntamento.get("titolo")).lower():
            continue
        eventi.append(Evento(
            data=quando.isoformat(),
            categoria="agenda",
            titolo=pulisci(appuntamento.get("titolo")) or "impegno in agenda",
            dettaglio=dataora_it(appuntamento.get("data_ora")),
            esito=pulisci(appuntamento.get("stato")).lower(),
            fonte="agenda",
            fonte_id=pulisci(appuntamento.get("id")),
        ))
    # Ordine cronologico; i fatti senza data restano in coda, dichiarati tali.
    eventi.sort(key=lambda evento: (_chiave(evento.data) == "0000-00-00", _chiave(evento.data)))
    visti: set[tuple[str, str]] = set()
    unici: list[dict[str, Any]] = []
    for evento in eventi:
        chiave = (evento.fonte, evento.fonte_id or evento.titolo)
        if chiave in visti:
            continue
        visti.add(chiave)
        voce = evento.come_dizionario()
        voce["data_it"] = data_it(evento.data)
        unici.append(voce)
    return unici


__all__ = ["ESITI", "TIPI_ATTIVITA", "cronologia"]
