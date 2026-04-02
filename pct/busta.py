"""
Creazione della busta telematica (.enc) per il deposito PCT.
La busta è un archivio cifrato conforme alle specifiche del Ministero della Giustizia.
"""

import os
import zipfile
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from lxml import etree

from .pst_catalog import (
    PST_DM44_SPECIFICHE_REVISION,
    PST_DM44_SPECIFICHE_URL,
    PST_FORMAL_ERROR_CODES,
    PST_MAX_BUSTA_BYTES,
    PST_MAX_BUSTA_MB,
)


@dataclass
class Allegato:
    """Rappresenta un allegato nella busta telematica."""

    percorso: str
    descrizione: str
    tipo: str = "ALLEGATO"  # ATTO_PRINCIPALE | ALLEGATO | PROCURA


@dataclass
class DatiBusta:
    """Dati strutturati per la creazione della busta telematica."""

    codice_ufficio: str
    codice_registro: str
    oggetto: str
    tipo_atto: str
    atto_principale: str
    allegati: List[Allegato] = field(default_factory=list)
    numero_rg: Optional[str] = None
    anno_rg: Optional[int] = None
    operatore: str = ""
    cf_mittente: str = ""


class BustaTelematica:
    """
    Genera la busta telematica (.enc) per il deposito civile telematico.

    La busta è strutturata come:
    - DatiAtto.xml       (metadati dell'atto)
    - atto_principale.pdf.p7m  (atto firmato digitalmente)
    - allegato_N.pdf.p7m       (allegati firmati)
    - indice.enc               (indice cifrato)
    """

    NAMESPACE = "http://www.giustizia.it/processo_telematico"

    def __init__(self, dati: DatiBusta):
        self.dati = dati
        self.id_busta = str(uuid.uuid4()).upper()
        self.timestamp = datetime.now()

    def _crea_xml_dati_atto(self) -> bytes:
        """Crea il file XML DatiAtto.xml con i metadati dell'atto."""
        root = etree.Element(
            "DatiAtto",
            xmlns=self.NAMESPACE,
            attrib={"versione": "1.0"},
        )

        # Identificativo busta
        etree.SubElement(root, "IdBusta").text = self.id_busta

        # Dati ufficio
        ufficio = etree.SubElement(root, "UfficioGiudiziario")
        etree.SubElement(ufficio, "CodiceUfficio").text = self.dati.codice_ufficio
        etree.SubElement(ufficio, "CodiceRegistro").text = self.dati.codice_registro

        # Riferimento procedimento — emesso solo se entrambi numero_rg e anno_rg sono
        # valorizzati; anno_rg=0/None produrrebbe <AnnoRG/> malformato (D.M. 44/2011)
        if self.dati.numero_rg and self.dati.anno_rg:
            proc = etree.SubElement(root, "RiferimentoProcedimento")
            etree.SubElement(proc, "NumeroRG").text = self.dati.numero_rg
            etree.SubElement(proc, "AnnoRG").text = str(self.dati.anno_rg)

        # Dati atto
        atto = etree.SubElement(root, "Atto")
        etree.SubElement(atto, "TipoAtto").text = self.dati.tipo_atto
        etree.SubElement(atto, "Oggetto").text = self.dati.oggetto
        etree.SubElement(atto, "DataDeposito").text = self.timestamp.strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

        # Mittente
        mittente = etree.SubElement(root, "Mittente")
        etree.SubElement(mittente, "CodiceFiscale").text = self.dati.cf_mittente
        etree.SubElement(mittente, "Nominativo").text = self.dati.operatore

        # Elenco documenti
        docs = etree.SubElement(root, "Documenti")
        ap = etree.SubElement(docs, "Attoprincipale")   # spec PST D.M. 44/2011
        etree.SubElement(ap, "NomeFile").text = Path(self.dati.atto_principale).name
        etree.SubElement(ap, "Hash").text = self._hash_file(self.dati.atto_principale)

        for i, allegato in enumerate(self.dati.allegati, 1):
            all_el = etree.SubElement(docs, "Allegato")
            etree.SubElement(all_el, "NomeFile").text = Path(allegato.percorso).name
            etree.SubElement(all_el, "Descrizione").text = allegato.descrizione
            etree.SubElement(all_el, "Tipo").text = allegato.tipo
            etree.SubElement(all_el, "Hash").text = self._hash_file(allegato.percorso)

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _hash_file(self, percorso: str) -> str:
        """Calcola l'hash SHA-256 di un file."""
        sha256 = hashlib.sha256()
        with open(percorso, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest().upper()

    def stima_dimensione_busta(self) -> int:
        """Stima la dimensione della busta simulata, includendo un overhead minimo."""
        totale = len(self._crea_xml_dati_atto()) + 4096
        file_paths = [self.dati.atto_principale] + [a.percorso for a in self.dati.allegati]
        for percorso in file_paths:
            path = Path(percorso)
            if path.exists():
                totale += path.stat().st_size
        return totale

    def audit_conformita_pst(self) -> dict:
        """
        Restituisce un audit tecnico della busta rispetto alle specifiche PST.

        L'audit distingue tra quanto e verificabile offline e quanto richiede
        ancora un adapter ministeriale completo lato Atto.msg / Atto.enc.
        """
        issues: list[dict[str, str]] = []
        xml_ok = True
        try:
            root = etree.fromstring(self._crea_xml_dati_atto())
            ns = {"p": self.NAMESPACE}
            if root.find(".//p:Documenti/p:Attoprincipale", ns) is None:
                xml_ok = False
        except Exception as exc:
            xml_ok = False
            issues.append(
                {
                    "code": "T002",
                    "level": "BLOCK",
                    "title": "DatiAtto.xml non generabile",
                    "detail": f"Il payload XML tecnico non e stato generato correttamente: {exc}",
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Correggi i metadati della busta prima del deposito.",
                }
            )

        size_bytes = self.stima_dimensione_busta()
        if size_bytes > PST_MAX_BUSTA_BYTES:
            issues.append(
                {
                    "code": "T003",
                    "level": "BLOCK",
                    "title": "Busta oltre il limite ministeriale",
                    "detail": (
                        f"La busta stimata pesa circa {round(size_bytes / (1024 * 1024), 2)} MB "
                        f"e supera il limite PST di {PST_MAX_BUSTA_MB} MB."
                    ),
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Riduci scansioni e allegati o suddividi il deposito.",
                }
            )

        issues.append(
            {
                "code": "SIM-ENC",
                "level": "WARNING",
                "title": "Trasporto ministeriale simulato",
                "detail": (
                    "Il file .enc locale e ottenuto rinominando uno ZIP strutturale. "
                    "Le specifiche PST prevedono invece Atto.enc ottenuto dalla cifratura di Atto.msg."
                ),
                "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                "suggested_action": (
                    "Tratta questa busta come simulazione tecnica locale finche non viene "
                    "implementato il trasporto ministeriale completo."
                ),
            }
        )

        t002_status = "warning"
        if not xml_ok:
            t002_status = "block"
        t003_status = "block" if size_bytes > PST_MAX_BUSTA_BYTES else "ok"

        return {
            "transport_mode": "simulazione_zip_rinominato",
            "expected_transport_mode": "atto_enc_da_atto_msg_cifrato_3des",
            "uses_real_encryption": False,
            "atto_msg_generated": False,
            "indice_busta_generated": False,
            "size_bytes": size_bytes,
            "max_size_bytes": PST_MAX_BUSTA_BYTES,
            "max_size_mb": PST_MAX_BUSTA_MB,
            "formal_checks": {
                "T001": {
                    "status": "non_verificabile_offline",
                    "message": PST_FORMAL_ERROR_CODES["T001"],
                },
                "T002": {
                    "status": t002_status,
                    "message": PST_FORMAL_ERROR_CODES["T002"],
                },
                "T003": {
                    "status": t003_status,
                    "message": PST_FORMAL_ERROR_CODES["T003"],
                },
            },
            "sources": [
                {
                    "label": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "url": PST_DM44_SPECIFICHE_URL,
                }
            ],
            "issues": issues,
        }

    def crea_busta(self, output_dir: str) -> str:
        """
        Crea la busta telematica e la salva nella directory specificata.

        Args:
            output_dir: Directory dove salvare la busta

        Returns:
            Percorso al file busta (.zip che verrà poi cifrato in .enc)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        nome_busta = f"busta_{self.id_busta[:8]}.zip"
        zip_path = output_dir / nome_busta

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Aggiungi DatiAtto.xml
            xml_content = self._crea_xml_dati_atto()
            zf.writestr("DatiAtto.xml", xml_content)

            # Aggiungi atto principale
            ap_path = Path(self.dati.atto_principale)
            zf.write(ap_path, ap_path.name)

            # Aggiungi allegati
            for allegato in self.dati.allegati:
                all_path = Path(allegato.percorso)
                zf.write(all_path, all_path.name)

        # Il file .enc è la busta cifrata (qui simuliamo con il .zip)
        enc_path = str(zip_path).replace(".zip", ".enc")
        os.rename(zip_path, enc_path)

        return enc_path

    def verifica_busta(self, busta_path: str) -> dict:
        """
        Verifica l'integrità di una busta telematica.

        Args:
            busta_path: Percorso alla busta .enc

        Returns:
            Dizionario con risultato della verifica
        """
        risultato = {
            "valida": False,
            "id_busta": None,
            "documenti": [],
            "errori": [],
            "audit_tecnico": {},
        }

        try:
            with zipfile.ZipFile(busta_path, "r") as zf:
                nomi = zf.namelist()
                if "DatiAtto.xml" not in nomi:
                    risultato["errori"].append("DatiAtto.xml mancante nella busta")
                    return risultato

                xml_data = zf.read("DatiAtto.xml")
                root = etree.fromstring(xml_data)
                ns = {"p": self.NAMESPACE}

                id_el = root.find("p:IdBusta", ns)
                if id_el is not None:
                    risultato["id_busta"] = id_el.text

                for doc in root.findall(".//p:NomeFile", ns):
                    risultato["documenti"].append(doc.text)

                risultato["valida"] = True
                risultato["audit_tecnico"] = self.audit_conformita_pst()
        except Exception as e:
            risultato["errori"].append(str(e))

        return risultato
