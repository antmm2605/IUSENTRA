"""Import nel fascicolo degli elenchi esportati dal PDP (procedimenti autorizzati, depositi, udienze).

Il PDP non espone un servizio per i gestionali: l'avvocato esporta l'elenco
con il tasto «Esporta» e lo carica qui. Si importano solo le righe che
appartengono a questo fascicolo (stesso numero/anno di registro); le altre
si contano e si ignorano. Le udienze future entrano in agenda.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app

from pct.penale_pdp import catalogo, stati
from pct.penale_pdp.export_pdp import leggi_export
from web.services import penale_pdp_contesto as contesto
from web.services.penale_pdp_depositi import dopo_cambio_stato

ROMA = ZoneInfo("Europe/Rome")


def _chiavi_fascicolo(fascicolo: Any, registri: list[dict[str, Any]]) -> set[tuple[str, str]]:
    chiavi = {(str(r["register_number"]).lstrip("0"), str(r["register_year"])) for r in registri}
    if fascicolo.numero_rg and fascicolo.anno_rg:
        chiavi.add((str(fascicolo.numero_rg).lstrip("0"), str(fascicolo.anno_rg)))
    return chiavi


def _della_pratica(riga: dict[str, Any], chiavi: set[tuple[str, str]]) -> bool:
    return any((p["numero"].lstrip("0"), p["anno"]) in chiavi for p in riga.get("protocolli") or [])


def _udienza_in_agenda(fascicolo: Any, udienza: dict[str, Any]) -> str:
    quando = udienza["quando"]
    if "T" not in quando:
        quando += "T09:00"
    inizio = datetime.fromisoformat(quando).replace(tzinfo=ROMA)
    if inizio < datetime.now(ROMA):
        return ""
    from pct.agenda import TipoAppuntamento

    agenda = current_app.extensions["core_runtime"]["get_agenda"]()
    luogo = " · ".join(filter(None, (udienza.get("luogo"), f"aula {udienza['aula']}" if udienza.get("aula") else "")))
    appuntamento = agenda.aggiungi(
        f"Udienza penale – {fascicolo.titolo}", TipoAppuntamento.UDIENZA, quando, luogo=luogo, allow_overlap=True,
        procedimento=f"{fascicolo.numero_rg}/{fascicolo.anno_rg}" if fascicolo.numero_rg else "",
        tribunale=fascicolo.tribunale, cliente=fascicolo.nome_cliente, id_cliente=fascicolo.id_cliente,
        note=f"Dallo storico udienze del PDP. {udienza.get('causale') or ''}".strip(),
    )
    return str(getattr(appuntamento, "id", "") or "")


def importa(fid: str, contenuto: bytes, *, anteprima: bool = True) -> dict[str, Any]:
    fascicolo = contesto.fascicolo_penale(fid)
    caso = contesto.caso(fid)
    arch = contesto.archivio()
    letto = leggi_export(contenuto)
    tipo, righe = letto["tipo"], letto["righe"]
    chiavi = _chiavi_fascicolo(fascicolo, arch.registri(caso["id"]))
    if tipo == "udienze":
        pertinenti, ignorate = righe, 0  # lo storico udienze si esporta dal singolo procedimento
    else:
        pertinenti = [r for r in righe if _della_pratica(r, chiavi)]
        ignorate = len(righe) - len(pertinenti)
    esito: dict[str, Any] = {"tipo": tipo, "totale": len(righe), "pertinenti": len(pertinenti), "ignorate": ignorate,
                             "anteprima": pertinenti[:20], "importati": 0, "aggiornati": 0, "inAgenda": 0}
    if anteprima or not pertinenti:
        return esito
    if tipo == "procedimenti":
        for riga in pertinenti:
            for protocollo in riga["protocolli"]:
                if protocollo["ufficio"]:
                    arch.salva_registro(caso["id"], office_code=protocollo["ufficio"], office_name=riga.get("ufficio") or "",
                                        register_type=protocollo["registro"] or "N", register_number=protocollo["numero"],
                                        register_year=protocollo["anno"], magistrate=riga.get("magistrato") or "",
                                        corrente=protocollo is riga["protocolli"][-1], source="export_pdp")
                    esito["importati"] += 1
        contesto.aggiorna_procedimento(fid, {"autorizzato": True, "fonte": "Elenco procedimenti autorizzati del PDP"})
    elif tipo == "depositi":
        for riga in pertinenti:
            identificativo = riga.get("identificativo") or ""
            protocollo = (riga.get("protocolli") or [{}])[0]
            voce = catalogo.per_nome(riga.get("tipoAtto") or "")
            campi = {"status": riga.get("stato") or "INVIATO", "sent_at": riga.get("dataInvio") or "",
                     "arrived_at": riga.get("dataArrivo") or ""}
            esistente = arch.per_identificativo(caso["id"], identificativo) if identificativo else None
            if esistente:
                aggiornato = arch.aggiorna_deposito(caso["id"], esistente["id"], **campi)
                esito["aggiornati"] += 1
                dopo_cambio_stato(fid, aggiornato)
                continue
            nuovo = arch.crea_deposito(
                caso["id"], source="export_pdp", act_name=voce.codice if voce else (riga.get("tipoAtto") or "Atto"),
                is_main_act=int(bool(voce and voce.principale)), office_code=protocollo.get("ufficio") or "",
                office_name=riga.get("ufficio") or "", register_label=riga.get("registroLetto") or "",
                subjects_json=[{"nome": riga.get("soggetti") or "", "ruolo": ""}], sending_id=identificativo, **campi,
            )
            dopo_cambio_stato(fid, nuovo)
            esito["importati"] += 1
    else:
        for riga in pertinenti:
            udienza, nuova = arch.registra_udienza(caso["id"], starts_at=riga["quando"], office_type=riga.get("tipoUfficio") or "",
                                                   room=riga.get("aula") or "", place=riga.get("luogo") or "", reason=riga.get("causale") or "")
            if not nuova:
                continue
            esito["importati"] += 1
            agenda_id = _udienza_in_agenda(fascicolo, riga)
            if agenda_id:
                arch.collega_agenda(udienza["id"], agenda_id)
                esito["inAgenda"] += 1
    esito["statiLetti"] = sorted({stati.etichetta(r.get("stato") or "") for r in pertinenti if r.get("stato")})
    return esito


__all__ = ["importa"]
