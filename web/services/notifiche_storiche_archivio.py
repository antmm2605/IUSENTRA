"""Riconcilia gli originali PEC importati durante la lettura in sfondo."""

from __future__ import annotations

import hashlib
import logging
import subprocess
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException

from pct.pec_ricevute_archivio import (
    riscontra_invio_storico,
    riscontri_da_ricevute_storiche,
    tipo_eml_storico,
    verifica_ricevuta_storica,
)
from pct.registro_letture.fatti_repository import Fatto

_CAMPO = "riscontro_notifica_pec_storica"
logger = logging.getLogger(__name__)


def registra_riscontri_notifiche(fascicolo, registro, tenant: str) -> int:
    from web.services.archivio_letture_runtime import _bytes_documento, _formato_documento

    fascicolo_id = str(fascicolo.id)
    documenti = {str(d.id): d for d in fascicolo.documenti if _formato_documento(d) == ".eml"}
    if not documenti:
        return 0
    invii, ricevute, impronte = {}, [], {}
    impronte_ricevute, impronte_invii = set(), set()
    for oid, documento in sorted(documenti.items()):
        raw = _bytes_documento(fascicolo_id, documento)
        try:
            tipo = tipo_eml_storico(raw)
            if not tipo:
                continue
            impronta = hashlib.sha256(raw).hexdigest()
            if tipo == "ricevuta":
                # Una copia dello stesso EML non rende ambigua la consegna.
                if impronta in impronte_ricevute:
                    continue
                ricevute.append((oid, verifica_ricevuta_storica(raw)))
                impronte_ricevute.add(impronta)
            elif tipo == "invio":
                if impronta in impronte_invii:
                    continue
                invii[oid] = raw
                impronte_invii.add(impronta)
        except (ValueError, ParseError, DefusedXmlException, OSError, subprocess.TimeoutExpired) as exc:
            logger.debug("Riscontro ricevuta storica indisponibile (%s)", type(exc).__name__)
            continue
        impronte[oid] = impronta

    scritti = 0
    precedenti = {f.oggetto_id: f for f in registro.fatti(tenant, fascicolo_id, campo=_CAMPO, verifiche=None)}
    riscontri, accettazioni = {}, set()
    for oid, raw in invii.items():
        prova = riscontra_invio_storico(raw, ricevute)
        if prova and prova["accettazione_id"] not in accettazioni:
            riscontri[oid] = prova
            accettazioni.add(prova["accettazione_id"])
    riscontri.update({oid: prova for oid, prova in riscontri_da_ricevute_storiche(ricevute).items() if oid not in accettazioni})
    for oid in (precedenti.keys() | riscontri.keys()) & documenti.keys():
        oggetto = registro.oggetto(tenant, fascicolo_id, "documento", oid)
        if oggetto is None:
            continue
        prova = riscontri.get(oid)
        fatti = []
        if prova:
            ids = [oid, prova["accettazione_id"], *(r["documento_id"] for r in prova["consegne"])]
            prova["impronte_eml"] = {ref: impronte[ref] for ref in ids}
            fatti.append(Fatto(
                categoria="metadato_fascicolo", campo=_CAMPO, valore=impronte[oid],
                etichetta="Riscontro documentale della notifica PEC",
                origine="ricevute_pec_originali", verifica="plausibile", prove=[prova],
            ))
        precedente = precedenti.get(oid)
        if precedente and fatti and precedente.sha256 == oggetto.impronta and precedente.prove == fatti[0].prove:
            continue
        if precedente is None and not fatti:
            continue
        esito = registro.registra_fatti(tenant, fascicolo_id, oggetto, "pec", fatti, versione="notifiche_storiche_v2")
        scritti += esito["nuovi"] + esito["aggiornati"] + esito["rimossi"]
    return scritti
