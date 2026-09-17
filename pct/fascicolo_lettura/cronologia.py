"""Che cosa è stato fatto, in ordine di tempo, con la prova di ogni fatto."""

from __future__ import annotations

from typing import Any
import re

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
    archivio_letto: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    eventi: list[Evento] = []
    archivio_disponibile = bool((archivio_letto or {}).get("disponibile"))
    depositi_ids = {str(d.get("id")) for d in depositi_letti}
    ricevute = list((archivio_letto or {}).get("ricevute") or [])
    receipt_ids = {str(p.get("receipt_message_id") or "").strip().strip("<>").casefold(): p for p in ricevute if p.get("deposito_id") in depositi_ids and p.get("receipt_message_id")}

    for voce in attivita:
        tipo = pulisci(voce.get("tipo")).upper()
        if tipo == "NOTIFICA":
            continue  # le notifiche entrano dalla loro lettura, con lo stato di perfezionamento
        titolo = pulisci(voce.get("titolo"))
        note = pulisci(voce.get("note"))
        mid = re.search(r"Message-ID:\s*<?([^<>\s]+@[^<>\s]+)>?", note, re.I)
        if mid and mid.group(1).casefold() in receipt_ids:
            continue
        if "prova deposito" in titolo.lower() or "prova senza invio" in titolo.lower():
            continue
        if pulisci(voce.get("id_deposito_pct")) in depositi_ids:
            continue
        if archivio_disponibile and "PEC_DOCUMENT_PRESIDIO:" in note:
            continue  # the same event is represented by current archive facts below
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
        if not documento.get("data_evento"):
            continue  # upload dates do not establish that a procedural event occurred
        if documento["sezione"] in {"provvedimenti", "comunicazioni", "notifiche"} or documento["natura"] == "atto_principale":
            eventi.append(Evento(
                data=documento["data_evento"],
                categoria={"provvedimenti": "provvedimento", "comunicazioni": "comunicazione", "notifiche": "prova di notifica"}.get(documento["sezione"], "atto"),
                titolo=documento["etichetta"],
                dettaglio=documento["nome"],
                esito="",
                fonte="documento catalogato",
                fonte_id=documento["id"],
            ))
    # Le udienze e i termini che i due motori hanno letto nei documenti sono fatti
    # come gli altri: prima restavano nell'archivio senza entrare in cronologia.
    for voce in list((archivio_letto or {}).get("udienze") or []) + list((archivio_letto or {}).get("termini") or []):
        giorno = pulisci(voce.get("data_iso"))[:10]
        if not giorno or voce.get("verifica") not in {"verificata", "corretta"}:
            continue
        eventi.append(Evento(
            data=giorno,
            categoria="udienza" if pulisci(voce.get("tipo")) == "udienza" else "termine",
            titolo=pulisci(voce.get("descrizione")) or pulisci(voce.get("tipo")) or "data letta dai documenti",
            dettaglio=f"letta dai documenti · {pulisci(voce.get('verifica_etichetta')) or pulisci(voce.get('verifica'))}",
            esito="data fissata dal provvedimento",
            fonte="archivio delle letture",
            fonte_id=pulisci(voce.get("documento_id")) or giorno,
        ))
    # Gli eventi processuali che le PEC comunicano (rinvio d'ufficio, fissazione,
    # deposito del provvedimento) sono fatti della causa: il motore PEC li legge
    # e li data, qui prendono il loro posto nel tempo.
    for voce in list((archivio_letto or {}).get("eventi") or []):
        giorno = pulisci(voce.get("data_iso"))[:10]
        if not giorno or voce.get("verifica") not in {"verificata", "corretta"}:
            continue
        eventi.append(Evento(
            data=giorno,
            categoria="comunicazione",
            titolo=pulisci(voce.get("etichetta")) or "evento comunicato dalla cancelleria",
            dettaglio=f"letto dalla PEC · {pulisci(voce.get('verifica_etichetta')) or pulisci(voce.get('verifica'))}",
            esito="",
            fonte="archivio delle letture",
            fonte_id=f"evento:{pulisci(voce.get('oggetto_id')) or giorno}:{pulisci(voce.get('etichetta'))}",
        ))
    giorno_oggi = data_da(oggi)
    eventi = [evento for evento in eventi if not giorno_oggi or not data_da(evento.data) or data_da(evento.data) <= giorno_oggi]

    giorni_udienza = {_chiave(evento.data) for evento in eventi if evento.categoria == "udienza"}
    eventi_pec = {str(v.get("oggetto_id") or "") for v in (archivio_letto or {}).get("eventi", [])}
    fonti_agenda: dict[str, list[dict[str, Any]]] = {}
    for appuntamento in appuntamenti:
        riferimento = re.search(r"PEC_RICEZIONE:([^\s]+)", str(appuntamento.get("descrizione") or ""))
        if riferimento and riferimento.group(1) in eventi_pec:
            fonti_agenda.setdefault(riferimento.group(1), []).append({
                "fonte": "agenda", "fonte_id": pulisci(appuntamento.get("id")),
                "dettaglio": "Registrazione della stessa PEC ricevuta",
                "esito": pulisci(appuntamento.get("stato")).lower(),
            })
            continue
        quando = data_da(appuntamento.get("data_ora"))
        if pulisci(appuntamento.get("stato")).upper() != "COMPLETATO":
            continue  # a scheduled or cancelled appointment is not completed work
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
    visti: set[tuple[str, str, str, str]] = set()
    unici: list[dict[str, Any]] = []
    for evento in eventi:
        chiave = (evento.fonte, evento.fonte_id or evento.titolo, evento.data, evento.categoria)
        if chiave in visti:
            continue
        visti.add(chiave)
        voce = evento.come_dizionario()
        voce["data_it"] = data_it(evento.data)
        unici.append(voce)
    raggruppati = _raggruppa(unici)
    for voce in raggruppati:
        fonte_id = str(voce.get("fonte_id") or "")
        if fonte_id.startswith("evento:"):
            oggetto_id = fonte_id.split(":", 2)[1]
            voce["fonti"].extend(fonti_agenda.get(oggetto_id, []))
    return raggruppati


__all__ = ["ESITI", "TIPI_ATTIVITA", "cronologia"]


def _titolo_base(titolo: str) -> str:
    testo = pulisci(titolo).casefold()
    testo = re.sub(r"^(?:pec: |posta certificata: |accettazione: |consegna: |esito controlli automatici |accettazione )+", "", testo)
    testo = re.sub(r"\s+(?:rg[: .]|\[).*", "", testo)
    return testo.rstrip(" .")


def _raggruppa(eventi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine identical facts across views, keeping every source reference."""
    gruppi: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for evento in eventi:
        categoria = str(evento.get("categoria") or "")
        titolo = pulisci(evento.get("titolo")).casefold()
        chiave = (str(evento.get("data") or ""), categoria, titolo, str(evento.get("fonte_id") or ""))
        corrente = gruppi.get(chiave)
        fonte = {k: evento.get(k, "") for k in ("fonte", "fonte_id", "dettaglio", "esito")}
        if corrente is None:
            gruppi[chiave] = {**evento, "fonti": [fonte]}
        elif fonte not in corrente["fonti"]:
            corrente["fonti"].append(fonte)
    return list(gruppi.values())
