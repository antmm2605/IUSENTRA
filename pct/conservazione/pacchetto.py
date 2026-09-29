"""Pacchetto di versamento (PdV) per il conservatore.

Linee guida AgID sulla formazione, gestione e conservazione dei documenti informatici (§ 4):
il produttore trasmette al sistema di conservazione pacchetti di versamento con i documenti e i
loro metadati; il conservatore li verifica, emette il rapporto di versamento e forma i pacchetti
di archiviazione con l'indice UNI 11386 (SInCRO). IUSENTRA non è un conservatore: prepara il PdV
e ne tiene traccia, la conservazione a norma la svolge il conservatore scelto dallo studio
(art. 44 CAD).

Struttura dello ZIP (deterministica, stesso contenuto → stessa impronta):
- ``documenti/<n>_<nome>``: i file originali, come acquisiti o firmati;
- ``metadati/<n>.xml``: metadati Allegato 5 del documento;
- ``IndicePdV.xml``: produttore, fascicolo, elenco dei documenti con impronta SHA-256;
- ``impronte.sha256``: impronte di tutti i file del pacchetto;
- ``LEGGIMI.txt``: cosa contiene e come verificarlo.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

NAMESPACE = "urn:iusentra:conservazione:pdv:1"
_DATA_FISSA = (2020, 1, 1, 0, 0, 0)


def _nome_sicuro(nome: str) -> str:
    pulito = re.sub(r"[^A-Za-z0-9._-]+", "_", str(nome or "documento")).strip("._") or "documento"
    return pulito[:120]


def _elemento(padre: ET.Element, nome: str, valore: Any) -> None:
    if isinstance(valore, dict):
        figlio = ET.SubElement(padre, nome)
        for chiave, sotto in valore.items():
            _elemento(figlio, chiave, sotto)
    elif isinstance(valore, list):
        if nome == "Soggetti":
            contenitore = ET.SubElement(padre, nome)
            for voce in valore:
                _elemento(contenitore, "Soggetto", voce)
        else:
            for voce in valore:
                _elemento(padre, nome, voce)
    else:
        ET.SubElement(padre, nome).text = "" if valore is None else str(valore)


def xml_metadati(metadati: dict[str, Any]) -> bytes:
    radice = ET.Element("DocumentoInformatico", {"xmlns": NAMESPACE})
    for chiave, valore in metadati.items():
        _elemento(radice, chiave, valore)
    ET.indent(radice)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(radice, encoding="utf-8")


def _scrivi(archivio: zipfile.ZipFile, percorso: str, dati: bytes) -> None:
    info = zipfile.ZipInfo(percorso, date_time=_DATA_FISSA)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archivio.writestr(info, dati)


def crea_pdv(*, identificativo: str, creato_il: str, produttore: dict[str, str], fascicolo: dict[str, str],
             voci: list[tuple[dict[str, Any], str, bytes]]) -> tuple[bytes, list[dict[str, str]]]:
    """Crea lo ZIP del PdV. ``voci``: (metadati Allegato 5, nome del file, contenuto)."""

    if not voci:
        raise ValueError("Scegli almeno un documento da versare.")
    file_pacchetto: list[tuple[str, bytes]] = []
    elenco: list[dict[str, str]] = []
    indice = ET.Element("IndicePdV", {"xmlns": NAMESPACE, "versione": "1"})
    ET.SubElement(indice, "Identificativo").text = identificativo
    ET.SubElement(indice, "DataCreazione").text = creato_il
    _elemento(indice, "Produttore", produttore)
    _elemento(indice, "Aggregazione", {"TipoAggregazione": "Fascicolo", **fascicolo})
    documenti = ET.SubElement(indice, "Documenti")
    for numero, (metadati, nome, contenuto) in enumerate(voci, start=1):
        percorso_doc = f"documenti/{numero:04d}_{_nome_sicuro(nome)}"
        percorso_meta = f"metadati/{numero:04d}.xml"
        file_pacchetto += [(percorso_doc, contenuto), (percorso_meta, xml_metadati(metadati))]
        impronta = metadati["IdDoc"]["ImprontaCrittograficaDelDocumento"]["Impronta"]
        voce = ET.SubElement(documenti, "Documento", {"progressivo": str(numero)})
        ET.SubElement(voce, "Identificativo").text = metadati["IdDoc"]["Identificativo"]
        ET.SubElement(voce, "NomeDelDocumento").text = metadati["NomeDelDocumento"]
        ET.SubElement(voce, "File").text = percorso_doc
        ET.SubElement(voce, "Metadati").text = percorso_meta
        ET.SubElement(voce, "Impronta", {"algoritmo": "SHA-256"}).text = impronta
        elenco.append({"id": metadati["IdDoc"]["Identificativo"], "nome": metadati["NomeDelDocumento"], "impronta": impronta,
                       "file": percorso_doc})
    ET.indent(indice)
    file_pacchetto.insert(0, ("IndicePdV.xml", b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(indice, encoding="utf-8")))
    impronte = "".join(f"{hashlib.sha256(dati).hexdigest()}  {percorso}\n" for percorso, dati in file_pacchetto)
    leggimi = (
        f"Pacchetto di versamento {identificativo} del {creato_il[:10]}\n"
        f"Produttore: {produttore.get('Denominazione', '')}\nFascicolo: {fascicolo.get('Oggetto', '')}\n\n"
        "Contiene i documenti del fascicolo e, per ciascuno, i metadati del documento informatico previsti "
        "dall'Allegato 5 alle Linee guida AgID sulla formazione, gestione e conservazione dei documenti informatici.\n"
        "Il file impronte.sha256 elenca l'impronta SHA-256 di ogni file: si verifica con «sha256sum -c impronte.sha256».\n"
        "Il pacchetto va consegnato al conservatore, che lo verifica, emette il rapporto di versamento e forma il "
        "pacchetto di archiviazione (indice UNI 11386 SInCRO). IUSENTRA non svolge la conservazione a norma.\n"
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archivio:
        for percorso, dati in file_pacchetto:
            _scrivi(archivio, percorso, dati)
        _scrivi(archivio, "impronte.sha256", impronte.encode("utf-8"))
        _scrivi(archivio, "LEGGIMI.txt", leggimi)
    return buffer.getvalue(), elenco


__all__ = ["NAMESPACE", "crea_pdv", "xml_metadati"]
