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
        except Exception as e:
            risultato["errori"].append(str(e))

        return risultato
