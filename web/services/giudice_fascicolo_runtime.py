"""Consegna del dato del motore al campo SQL, senza letture nei percorsi GET."""
from __future__ import annotations

from pct.giudice_fascicolo_repository import GiudiceFascicoloRepository, nome_giudice_equivalente


def cronologia_concordante(fatti, candidato):
    """Ogni nome diverso deve appartenere a una catena esplicita di sostituzioni."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    current = nome_giudice_equivalente(candidato)
    names = {nome_giudice_equivalente(f.valore) for f in fatti}
    visited = {current}
    upper = None
    for _ in range(len(names)):
        predecessors = set()
        dates = set()
        for fact in fatti:
            if fact.verifica != "verificata" or nome_giudice_equivalente(fact.valore) != current:
                continue
            for proof in fact.prove:
                detail = proof.get("dettaglio")
                if proof.get("codice") != "sostituzione_giudice" or proof.get("esito") != "ok" or not isinstance(detail, dict):
                    continue
                try:
                    effective = date.fromisoformat(detail.get("decorrenza", ""))
                except (ValueError, TypeError):
                    continue
                if (effective > datetime.now(ZoneInfo("Europe/Rome")).date()
                        or (upper is not None and effective >= upper)
                        or nome_giudice_equivalente(detail.get("nuovo", "")) != current):
                    continue
                predecessors.add(nome_giudice_equivalente(detail.get("precedente", "")))
                dates.add(effective)
        if not predecessors:
            break
        if len(predecessors) != 1 or len(dates) != 1 or not next(iter(predecessors)):
            return False
        current = next(iter(predecessors))
        if current in visited:
            return False
        visited.add(current)
        upper = next(iter(dates))
    return names <= visited


def consegna_giudice(fascicolo, fatti):
    from web.helpers import _studio_db
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from pct.discordanze_letture_repository import RegistroDiscordanze

    values = {nome_giudice_equivalente(f.valore) for f in fatti if f.campo == "giudice"}
    sources = [{"fatto_id": f.id, "documento_id": f.oggetto_id, "sha256": f.sha256,
                "valore": f.valore, "passaggio": f.contesto, "prove": f.prove} for f in fatti]
    registro = registro_corrente()
    current_facts = registro.fatti(tenant_corrente(), fascicolo.id, categoria="metadato_fascicolo", campo="giudice", verifiche=("verificata", "corretta"))
    all_sources = [{"fatto_id": f.id, "documento_id": f.oggetto_id, "sha256": f.sha256,
                   "valore": f.valore, "passaggio": f.contesto, "prove": f.prove} for f in current_facts]
    if len(values) != 1 or not cronologia_concordante(current_facts, fatti[0].valore):
        result = {"stato": "discordante", "motivo": "Provvedimenti con magistrati differenti: verifica cronologia richiesta."}
    else:
        result = GiudiceFascicoloRepository(_studio_db("FASCICOLI_DB")).consegna(fascicolo.id, fatti[0].valore, sources)
    discordances = RegistroDiscordanze(registro)
    documents = {str(doc.id): doc for doc in fascicolo.documenti}
    evidence = all_sources or sources
    reason = result.get("motivo", "Il magistrato letto è diverso dal dato della scheda.")
    number, year = str(fascicolo.numero_rg or ""), str(fascicolo.anno_rg or "")
    discordances.riconcilia(tenant_corrente(), fascicolo.id, "giudice_da_fonte",
        [{"chiave": "giudice", "codice": "giudice_da_fonte", "campo": "giudice",
          "titolo": "Giudice da verificare", "fascicoloId": fascicolo.id,
          "fascicolo": fascicolo.titolo, "cliente": fascicolo.nome_cliente,
          "clienteId": fascicolo.id_cliente,
          "rg": f"{number}/{year}" if number and year else "da acquisire",
          "numeroFascicolo": str(getattr(fascicolo, "numero", "") or ""),
          "valoreAnagrafica": str(fascicolo.giudice or "").strip() or "Non indicato nella scheda",
          "valoriAtto": sorted({source["valore"] for source in evidence}),
          "fonti": [{"id": source["documento_id"], "sha256": source["sha256"],
                     "label": str(getattr(documents.get(source["documento_id"]), "nome", "")
                                  or source["documento_id"]),
                     "href": f'/fascicoli/{fascicolo.id}/documenti/{source["documento_id"]}/visualizza',
                     "valore": source["valore"], "citazione": source["passaggio"]}
                    for source in evidence],
          "nota": reason, "motivo": reason, "evidenze": evidence, "esito": result}]
        if result["stato"] == "discordante" else [])
    if result["stato"] == "consegnato":
        fascicolo.giudice = fatti[0].valore
    return [{"fatto_id": f.id, "stato": "consegnato" if result["stato"] in {"consegnato", "gia_presente"} else "non_pertinente",
             "riferimento": result.get("riferimento", ""), "motivo": "Già presente." if result["stato"] == "gia_presente" else result.get("motivo", "Discordanza registrata nella verifica documentale.") if result["stato"] == "discordante" else "Giudice memorizzato dalla fonte."} for f in fatti]
