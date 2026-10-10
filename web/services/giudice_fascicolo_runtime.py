"""Consegna del dato del motore al campo SQL, senza letture nei percorsi GET."""
from __future__ import annotations

from pct.giudice_fascicolo_repository import GiudiceFascicoloRepository


def cronologia_concordante(fatti, candidato):
    """Ogni nome diverso deve appartenere a una catena esplicita di sostituzioni."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    current = candidato.strip().casefold()
    names = {f.valore.strip().casefold() for f in fatti}
    visited = {current}
    upper = None
    for _ in range(len(names)):
        predecessors = set()
        dates = set()
        for fact in fatti:
            if fact.verifica != "verificata" or fact.valore.strip().casefold() != current:
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
                        or str(detail.get("nuovo", "")).strip().casefold() != current):
                    continue
                predecessors.add(str(detail.get("precedente", "")).strip().casefold())
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

    values = {f.valore.strip().casefold() for f in fatti if f.campo == "giudice"}
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
    discordances.riconcilia(tenant_corrente(), fascicolo.id, "giudice_da_fonte",
        [{"chiave": "giudice", "campo": "giudice", "motivo": result.get("motivo", "Il magistrato letto è diverso dal dato della scheda."),
          "evidenze": all_sources or sources, "esito": result}] if result["stato"] == "discordante" else [])
    if result["stato"] == "consegnato":
        fascicolo.giudice = fatti[0].valore
    return [{"fatto_id": f.id, "stato": "consegnato" if result["stato"] in {"consegnato", "gia_presente"} else "non_pertinente",
             "riferimento": result.get("riferimento", ""), "motivo": "Già presente." if result["stato"] == "gia_presente" else result.get("motivo", "Discordanza registrata nella verifica documentale.") if result["stato"] == "discordante" else "Giudice memorizzato dalla fonte."} for f in fatti]
