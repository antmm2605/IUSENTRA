"""Lettore «Norme citate negli atti»: in sfondo, sui testi già salvati, mai riaprendo i file.

Lo chiama il ciclo delle letture del fascicolo (`archivio_letture_runtime.leggi_fascicolo`)
accanto agli altri lettori a valle: legge solo i documenti nuovi o cambiati secondo il
registro, poi riscrive il riepilogo del fascicolo che la pagina «Notizie utili» consulta
in una sola lettura (`atti_per_fascicolo`). Nessuna lettura durante una richiesta.
"""

from __future__ import annotations

import logging
from typing import Any

from pct.notiziario.norme_fascicolo import LETTORE, VERSIONE, atti_dai_riepiloghi, esito_documento, riepilogo_fascicolo

logger = logging.getLogger(__name__)

LIMITE_PER_GIRO = 300


def _testo(valore: Any) -> str:
    return str(getattr(valore, "value", valore) or "").strip()


def aggiorna_norme_citate(fascicolo: Any, registro: Any, tenant: str, *, limite: int = LIMITE_PER_GIRO) -> dict[str, int]:
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    report = {"letti": 0, "senza_testo": 0, "in_attesa_testo": 0}
    if not fascicolo_id:
        return report
    pendenti = registro.da_leggere(tenant, fascicolo_id, LETTORE, versione=VERSIONE, tipi=("documento",))
    if not pendenti and registro.impronta_fascicolo(tenant, fascicolo_id, LETTORE):
        return report  # fascicolo fermo: nulla da leggere, riepilogo già scritto
    if pendenti:
        from web.services.archivio_letture_runtime import testi_indice_archivio

        testi = testi_indice_archivio(fascicolo)
        chiusi_dal_motore = {
            (r.oggetto_id, r.sha256) for r in registro.letture(tenant, fascicolo_id, lettore="motore_documenti")
            if r.stato in {"letto", "non_leggibile"}
        }
        ocr_in_attesa = {(o.oggetto_id, o.impronta) for o in registro.da_leggere(tenant, fascicolo_id, "ocr", tipi=("documento",))}
        for oggetto in pendenti[:max(1, int(limite))]:
            testo = testi.get(oggetto.oggetto_id, "")
            if testo.lstrip().startswith("PCTENC"):
                testo = ""  # testo cifrato: non è una lettura
            if not testo.strip():
                chiave = (oggetto.oggetto_id, oggetto.impronta)
                if chiave in chiusi_dal_motore and chiave not in ocr_in_attesa:
                    registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=VERSIONE, stato="non_leggibile",
                                         esito={"motivo": "Testo del documento non disponibile."})
                    report["senza_testo"] += 1
                else:
                    report["in_attesa_testo"] += 1
                continue
            try:
                registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE, versione=VERSIONE, esito=esito_documento(testo))
                report["letti"] += 1
            except Exception as exc:  # es. impronta SHA-256 assente: la lettura non si conferma, si riprova
                report["in_attesa_testo"] += 1
                logger.debug("Norme citate non registrate per %s/%s: %s", fascicolo_id, oggetto.oggetto_id, exc)
    documenti = {o.oggetto_id: o for o in registro.oggetti(tenant, fascicolo_id) if o.tipo == "documento"}
    letture = [
        (documenti[lettura.oggetto_id].nome, dict(lettura.esito or {}))
        for lettura in registro.letture(tenant, fascicolo_id, lettore=LETTORE)
        if lettura.stato == "letto" and lettura.oggetto_id in documenti
        and lettura.sha256 == documenti[lettura.oggetto_id].impronta
    ]
    restano = report["in_attesa_testo"] + max(0, len(pendenti) - max(1, int(limite)))
    registro.segna_fascicolo(
        tenant, fascicolo_id, LETTORE, impronta=VERSIONE, oggetti_totali=len(documenti),
        oggetti_letti=len(letture), stato="completa" if restano == 0 else "parziale", versione=VERSIONE,
        esito=riepilogo_fascicolo(letture),
    )
    return report


def atti_per_fascicolo(registro: Any, tenant: str) -> dict[str, list[dict[str, Any]]]:
    """Gli atti citati nei documenti di ogni fascicolo dello studio, in una sola lettura del registro."""
    try:
        return atti_dai_riepiloghi(registro.righe_fascicoli(tenant, lettore=LETTORE))
    except Exception as exc:  # senza registro la pagina resta leggibile, senza questo collegamento
        logger.warning("Norme citate dei fascicoli non disponibili: %s", exc)
        return {}


__all__ = ["aggiorna_norme_citate", "atti_per_fascicolo"]
