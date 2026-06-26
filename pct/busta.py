"""Preparazione ministeriale della busta di deposito PCT."""

import hashlib
import mimetypes
import re
from io import BytesIO
import tempfile
import uuid
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .path_security import UnsafeRuntimePath, resolve_runtime_path
from .atto_enc_validation import inspect_atto_enc_payload
from .pst_catalog import (
    PST_BUSTA_ENCRYPTION_ALGORITHM,
    PST_BUSTA_ENCRYPTION_FATAL_FROM,
    PST_BUSTA_ENCRYPTION_REQUIRED_FROM,
    PST_BUSTA_ENCRYPTION_UPDATE_URL,
    PST_DM44_SPECIFICHE_2024_DETAIL_URL,
    PST_DM44_SPECIFICHE_REVISION,
    PST_DM44_SPECIFICHE_URL,
    PST_FORMAL_ERROR_CODES,
    PST_MAX_BUSTA_BYTES,
    PST_MAX_BUSTA_MB,
)
from .pst_cifratura import (
    PSTCifraturaError,
    carica_certificato_cifratura,
    cifra_atto_msg_aes256,
    risolvi_certificato_cifratura_ufficio,
)

DATI_ATTO_FILENAME = "DatiAtto.xml"
DATI_ATTO_FIRMATO_FILENAME = "DatiAtto.xml.p7m"
INDICE_BUSTA_FILENAME = "IndiceBusta.xml"
INDICE_DOCUMENTI_FILENAME = "IndiceDocumentiDepositati.PDF"
ATTO_MSG_FILENAME = "Atto.msg"
ATTO_ENC_FILENAME = "Atto.enc"


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
    Prepara Atto.msg e Atto.enc per il deposito civile.

    Atto.msg contiene IndiceBusta.xml, DatiAtto.xml, atto principale,
    allegati e indice documenti. Atto.enc viene consegnato al Local Signer
    solo dopo avere verificato questo Atto.msg non cifrato.
    Atto.enc è il CMS PKCS#7 cifrato AES256 con il certificato pubblico PST
    dell'ufficio destinatario.
    """

    NAMESPACE = "http://www.giustizia.it/processo_telematico"

    def __init__(
        self,
        dati: DatiBusta,
        *,
        id_busta: str | None = None,
        timestamp: datetime | str | None = None,
    ):
        self.dati = dati
        self.id_busta = self._normalizza_id_busta(id_busta)
        self.timestamp = self._normalizza_timestamp(timestamp)
        self._last_transport_audit: dict | None = None
        self._last_atto_msg_path: str = ""
        self._last_atto_enc_path: str = ""

    @staticmethod
    def _normalizza_id_busta(value: str | None = None) -> str:
        raw = str(value or "").strip().upper()
        if raw:
            try:
                return str(uuid.UUID(raw)).upper()
            except (TypeError, ValueError):
                if re.fullmatch(r"[A-Z0-9_.-]{8,64}", raw):
                    return raw
        return str(uuid.uuid4()).upper()

    @staticmethod
    def _normalizza_timestamp(value: datetime | str | None = None) -> datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        raw = str(value or "").strip()
        if raw:
            try:
                return datetime.fromisoformat(raw).replace(tzinfo=None)
            except ValueError:
                pass
        return datetime.now()

    @staticmethod
    def _runtime_path(value: str | Path, *, must_be_file: bool = False) -> Path:
        try:
            path = resolve_runtime_path(value, extra_roots=(tempfile.gettempdir(), Path.cwd())).resolve()
        except (OSError, RuntimeError, ValueError, UnsafeRuntimePath) as exc:
            raise ValueError("Percorso busta non consentito.") from exc
        if must_be_file and not path.is_file():
            raise ValueError("Documento busta non disponibile.")
        return path

    @staticmethod
    def _hash_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest().upper()

    @staticmethod
    def _pdf_text(value: str, *, max_len: int = 110) -> str:
        text = " ".join(str(value or "").split())
        if len(text) > max_len:
            text = f"{text[: max_len - 3]}..."
        return text

    @staticmethod
    def _xml_id(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
        if not cleaned or not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = fallback
        return cleaned[:64]

    @staticmethod
    def _indice_busta_tipo_allegato(filename: str, tipo: str = "", descrizione: str = "") -> str:
        text = f"{filename} {tipo} {descrizione}".casefold()
        if "procura" in text:
            return "PL"
        if "iscrizione" in text and "ruolo" in text:
            return "IR"
        if "pagament" in text or "ricevuta" in text or "rt_" in text:
            return "RT"
        if filename.casefold().endswith(".eml") and ("notifica" in text or "posta certificata" in text):
            return "PA"
        if "avvenuta consegna" in text or "consegna" in text:
            return "RA"
        return "SM"

    def _crea_indice_busta_xml(self, *, dati_atto_filename: str = DATI_ATTO_FILENAME) -> bytes:
        """Genera l'IndiceBusta.xml ministeriale richiesto nel file Atto.msg."""
        root = etree.Element("IndiceBusta")
        atto_name = Path(self.dati.atto_principale).name
        etree.SubElement(
            root,
            "Atto",
            Nome=atto_name,
            ID=self._xml_id(f"ATTO_{self.id_busta[:8]}", "ATTO_1"),
        )

        allegati: list[tuple[str, str]] = [(dati_atto_filename, "DA")]
        for index, allegato in enumerate(self.dati.allegati, start=1):
            filename = Path(allegato.percorso).name
            tipo = self._indice_busta_tipo_allegato(filename, allegato.tipo, allegato.descrizione)
            allegati.append((filename, tipo))
        allegati.append((INDICE_DOCUMENTI_FILENAME, "SM"))

        used_ids: set[str] = set()
        for index, (filename, tipo) in enumerate(allegati, start=1):
            raw_id = self._xml_id(f"ALLEGATO_{index}_{Path(filename).stem}", f"ALLEGATO_{index}")
            candidate = raw_id
            suffix = 2
            while candidate in used_ids:
                candidate = self._xml_id(f"{raw_id}_{suffix}", f"ALLEGATO_{index}_{suffix}")
                suffix += 1
            used_ids.add(candidate)
            etree.SubElement(root, "Allegato", Nome=filename, ID=candidate, Tipo=tipo)

        payload = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            doctype='<!DOCTYPE IndiceBusta SYSTEM "IndiceBusta.dtd">',
        )
        return payload

    @staticmethod
    def _atto_msg_attachments(atto_msg: bytes) -> dict[str, bytes]:
        message = BytesParser(policy=policy.default).parsebytes(atto_msg)
        attachments: dict[str, bytes] = {}
        for part in message.iter_attachments():
            filename = Path(part.get_filename() or "").name
            if filename:
                attachments[filename] = part.get_payload(decode=True) or b""
        return attachments

    def _verifica_atto_msg_payloads(
        self,
        atto_msg: bytes,
        *,
        dati_atto_filename: str,
        require_dati_atto_firmato: bool = False,
    ) -> dict:
        """Controlla la busta MIME prima della cifratura ministeriale."""

        result = {
            "valida": False,
            "documenti": [],
            "errori": [],
            "indice_busta_atto_filename": "",
            "indice_busta_dati_atto_filename": "",
            "indice_busta_allegati": [],
        }
        attachments = self._atto_msg_attachments(atto_msg)
        required = {INDICE_BUSTA_FILENAME, dati_atto_filename, INDICE_DOCUMENTI_FILENAME}
        missing = sorted(name for name in required if name not in attachments)
        if missing:
            result["errori"].append("Atto.msg incompleto: mancano " + ", ".join(missing))
            return result

        main_name = Path(self.dati.atto_principale).name
        if main_name not in attachments:
            result["errori"].append(f"Atto principale {main_name} mancante in Atto.msg")
            return result
        for allegato in self.dati.allegati:
            name = Path(allegato.percorso).name
            if name not in attachments:
                result["errori"].append(f"Allegato {name} mancante in Atto.msg")
                return result

        if require_dati_atto_firmato and dati_atto_filename != DATI_ATTO_FIRMATO_FILENAME:
            result["errori"].append("DatiAtto.xml.p7m firmato obbligatorio per la busta reale")
            return result

        try:
            indice_root = etree.fromstring(attachments[INDICE_BUSTA_FILENAME])
        except Exception as exc:
            result["errori"].append(f"{INDICE_BUSTA_FILENAME} non leggibile: {exc}")
            return result
        atto_node = indice_root.find("Atto")
        if indice_root.tag != "IndiceBusta" or atto_node is None:
            result["errori"].append(f"{INDICE_BUSTA_FILENAME} non conforme al DTD ministeriale")
            return result
        atto_name = str(atto_node.get("Nome") or "").strip()
        result["indice_busta_atto_filename"] = atto_name
        if atto_name != main_name:
            result["errori"].append(
                f"{INDICE_BUSTA_FILENAME} non richiama l'atto principale {main_name}"
            )
            return result
        if atto_name not in attachments:
            result["errori"].append(f"{INDICE_BUSTA_FILENAME} richiama un atto assente: {atto_name}")
            return result

        allegati = indice_root.findall("Allegato")
        result["indice_busta_allegati"] = [
            {"nome": str(node.get("Nome") or ""), "tipo": str(node.get("Tipo") or "")}
            for node in allegati
        ]
        dati_nodes = [
            node
            for node in allegati
            if node.get("Tipo") == "DA"
            and str(node.get("Nome") or "").strip() in {DATI_ATTO_FILENAME, DATI_ATTO_FIRMATO_FILENAME}
        ]
        if len(dati_nodes) != 1:
            result["errori"].append(f"{INDICE_BUSTA_FILENAME} deve contenere un solo Allegato Tipo=DA")
            return result
        dati_nome = str(dati_nodes[0].get("Nome") or "").strip()
        result["indice_busta_dati_atto_filename"] = dati_nome
        if dati_nome != dati_atto_filename:
            result["errori"].append(
                f"{INDICE_BUSTA_FILENAME} richiama {dati_nome}, ma Atto.msg contiene {dati_atto_filename}"
            )
            return result
        for node in allegati:
            nome = str(node.get("Nome") or "").strip()
            tipo = str(node.get("Tipo") or "").strip()
            if not nome or not tipo:
                result["errori"].append(f"{INDICE_BUSTA_FILENAME} contiene allegato senza Nome o Tipo")
                return result
            if nome not in attachments:
                result["errori"].append(f"{INDICE_BUSTA_FILENAME} richiama un allegato assente: {nome}")
                return result

        result["documenti"] = [atto_name, *[row["nome"] for row in result["indice_busta_allegati"] if row["nome"]]]
        if INDICE_DOCUMENTI_FILENAME not in result["documenti"]:
            result["errori"].append(f"{INDICE_DOCUMENTI_FILENAME} non richiamato da {INDICE_BUSTA_FILENAME}")
            return result
        result["valida"] = True
        return result

    def crea_dati_atto_xml_per_firma(self) -> bytes:
        """Restituisce DatiAtto.xml non firmato da inviare al Local Signer."""
        indice_pdf = self._crea_indice_documenti_pdf()
        return self._crea_xml_dati_atto(indice_pdf)

    def _indice_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = [
            {
                "numero": "1",
                "ruolo": "Metadati tecnici",
                "nome": "DatiAtto.xml",
                "descrizione": "Dati strutturati del deposito",
            },
            {
                "numero": "2",
                "ruolo": "Atto principale",
                "nome": Path(self.dati.atto_principale).name,
                "descrizione": self.dati.tipo_atto or "Atto principale",
            },
        ]
        for index, allegato in enumerate(self.dati.allegati, start=3):
            rows.append(
                {
                    "numero": str(index),
                    "ruolo": allegato.tipo or "Allegato",
                    "nome": Path(allegato.percorso).name,
                    "descrizione": allegato.descrizione or "Documento allegato",
                }
            )
        rows.append(
            {
                "numero": str(len(rows) + 1),
                "ruolo": "Indice",
                "nome": INDICE_DOCUMENTI_FILENAME,
                "descrizione": "Indice generato dal software",
            }
        )
        return rows

    def _crea_indice_documenti_pdf(self) -> bytes:
        """Genera l'indice dei documenti depositati mostrati nel pacchetto."""
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)
        width, height = A4
        margin_x = 42
        y = height - 52

        pdf.setTitle("Indice documenti depositati")
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin_x, y, "Indice documenti depositati")
        y -= 18
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(margin_x, y, f"Id busta: {self.id_busta}")
        y -= 13
        pdf.drawString(margin_x, y, f"Generato il: {self.timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
        y -= 13
        pdf.drawString(margin_x, y, f"Tipo atto: {self._pdf_text(self.dati.tipo_atto, max_len=80)}")
        y -= 13
        if self.dati.numero_rg or self.dati.anno_rg:
            rg = "/".join(part for part in (str(self.dati.numero_rg or ""), str(self.dati.anno_rg or "")) if part)
            pdf.drawString(margin_x, y, f"Procedimento: RG {rg}")
            y -= 13
        pdf.drawString(margin_x, y, f"Codice oggetto: {self._pdf_text(self.dati.oggetto, max_len=80)}")
        y -= 22

        pdf.setFont("Helvetica-Bold", 8.2)
        pdf.drawString(margin_x, y, "N.")
        pdf.drawString(margin_x + 28, y, "Ruolo")
        pdf.drawString(margin_x + 122, y, "Nome file")
        pdf.drawString(margin_x + 372, y, "Descrizione")
        y -= 5
        pdf.line(margin_x, y, width - margin_x, y)
        y -= 13

        pdf.setFont("Helvetica", 7.7)
        for row in self._indice_rows():
            if y < 52:
                pdf.showPage()
                y = height - 52
                pdf.setFont("Helvetica", 7.7)
            pdf.drawString(margin_x, y, self._pdf_text(row["numero"], max_len=4))
            pdf.drawString(margin_x + 28, y, self._pdf_text(row["ruolo"], max_len=24))
            pdf.drawString(margin_x + 122, y, self._pdf_text(row["nome"], max_len=54))
            pdf.drawString(margin_x + 372, y, self._pdf_text(row["descrizione"], max_len=34))
            y -= 13

        y -= 8
        if y < 64:
            pdf.showPage()
            y = height - 52
        pdf.setFont("Helvetica-Oblique", 7.5)
        pdf.drawString(
            margin_x,
            y,
            "Indice generato automaticamente da IUSENTRA sulla selezione documenti confermata prima della busta.",
        )
        pdf.save()
        return buffer.getvalue()

    def crea_indice_documenti_pdf(self) -> bytes:
        """Restituisce il PDF dell'indice documenti per anteprima e controllo."""
        return self._crea_indice_documenti_pdf()

    def _crea_xml_dati_atto(self, indice_pdf_bytes: bytes | None = None) -> bytes:
        """Crea il file XML DatiAtto.xml con i metadati dell'atto."""
        if indice_pdf_bytes is None:
            indice_pdf_bytes = self._crea_indice_documenti_pdf()
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

        indice_el = etree.SubElement(docs, "Allegato")
        etree.SubElement(indice_el, "NomeFile").text = INDICE_DOCUMENTI_FILENAME
        etree.SubElement(indice_el, "Descrizione").text = "Indice documenti depositati"
        etree.SubElement(indice_el, "Tipo").text = "INDICE_DOCUMENTI"
        etree.SubElement(indice_el, "Hash").text = self._hash_bytes(indice_pdf_bytes)

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _hash_file(self, percorso: str) -> str:
        """Calcola l'hash SHA-256 di un file."""
        sha256 = hashlib.sha256()
        with open(percorso, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest().upper()

    @staticmethod
    def _mime_type(filename: str) -> tuple[str, str]:
        lower = filename.lower()
        if lower.endswith(".p7m"):
            return "application", "pkcs7-mime"
        guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, _, subtype = guessed.partition("/")
        return maintype or "application", subtype or "octet-stream"

    def _document_payloads(
        self,
        *,
        xml_content: bytes,
        indice_busta_xml: bytes,
        indice_pdf: bytes,
        dati_atto_firmato: bytes | None = None,
    ) -> list[tuple[str, bytes, str, str]]:
        dati_atto_filename = DATI_ATTO_FIRMATO_FILENAME if dati_atto_firmato else DATI_ATTO_FILENAME
        dati_atto_payload = dati_atto_firmato or xml_content
        dati_atto_mime = ("application", "pkcs7-mime") if dati_atto_firmato else ("application", "xml")
        payloads: list[tuple[str, bytes, str, str]] = [
            (INDICE_BUSTA_FILENAME, indice_busta_xml, "application", "xml"),
            (dati_atto_filename, dati_atto_payload, dati_atto_mime[0], dati_atto_mime[1]),
        ]

        ap_path = self._runtime_path(self.dati.atto_principale, must_be_file=True)
        ap_name = ap_path.name
        ap_main, ap_sub = self._mime_type(ap_name)
        payloads.append((ap_name, ap_path.read_bytes(), ap_main, ap_sub))

        for allegato in self.dati.allegati:
            all_path = self._runtime_path(allegato.percorso, must_be_file=True)
            all_name = all_path.name
            all_main, all_sub = self._mime_type(all_name)
            payloads.append((all_name, all_path.read_bytes(), all_main, all_sub))

        payloads.append((INDICE_DOCUMENTI_FILENAME, indice_pdf, "application", "pdf"))
        return payloads

    def _crea_atto_msg(
        self,
        *,
        xml_content: bytes,
        indice_busta_xml: bytes,
        indice_pdf: bytes,
        dati_atto_firmato: bytes | None = None,
    ) -> bytes:
        message = EmailMessage(policy=policy.SMTP)
        message["Subject"] = f"Atto deposito telematico {self.id_busta[:8]}"
        message["From"] = self.dati.cf_mittente or self.dati.operatore or "iusentra@localhost"
        message["To"] = self.dati.codice_ufficio
        message["Date"] = format_datetime(self.timestamp.astimezone())
        message["X-IUSENTRA-Busta-ID"] = self.id_busta
        message.set_content(
            "Busta telematica IUSENTRA. Il contenuto di questo messaggio viene cifrato in Atto.enc."
        )
        for filename, payload, maintype, subtype in self._document_payloads(
            xml_content=xml_content,
            indice_busta_xml=indice_busta_xml,
            indice_pdf=indice_pdf,
            dati_atto_firmato=dati_atto_firmato,
        ):
            message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
        return message.as_bytes(policy=policy.SMTP)

    def stima_dimensione_busta(self) -> int:
        """Stima la dimensione della busta simulata, includendo un overhead minimo."""
        indice_pdf = self._crea_indice_documenti_pdf()
        indice_busta_xml = self._crea_indice_busta_xml()
        totale = len(self._crea_xml_dati_atto(indice_pdf)) + len(indice_busta_xml) + len(indice_pdf) + 4096
        file_paths = [self.dati.atto_principale] + [a.percorso for a in self.dati.allegati]
        for percorso in file_paths:
            path = Path(percorso)
            if path.exists():
                totale += path.stat().st_size
        return totale

    def audit_conformita_pst(self) -> dict:
        """Restituisce un audit tecnico della busta rispetto alle specifiche PST."""
        issues: list[dict[str, str]] = []
        xml_ok = True
        indice_pdf = self._crea_indice_documenti_pdf()
        indice_documenti_generated = bool(indice_pdf)
        indice_busta_generated = False
        dati_atto_signed = bool((self._last_transport_audit or {}).get("dati_atto_signed"))
        try:
            root = etree.fromstring(self._crea_xml_dati_atto(indice_pdf))
            ns = {"p": self.NAMESPACE}
            if root.find(".//p:Documenti/p:Attoprincipale", ns) is None:
                xml_ok = False
            indice_node = root.find(
                f".//p:Documenti/p:Allegato[p:NomeFile='{INDICE_DOCUMENTI_FILENAME}']",
                ns,
            )
            if indice_node is None:
                indice_documenti_generated = False

            indice_root = etree.fromstring(
                self._crea_indice_busta_xml(
                    dati_atto_filename=DATI_ATTO_FIRMATO_FILENAME if dati_atto_signed else DATI_ATTO_FILENAME
                )
            )
            atto_node = indice_root.find("Atto")
            dati_node = next(
                (
                    node
                    for node in indice_root.findall("Allegato")
                    if node.get("Tipo") == "DA"
                    and node.get("Nome") in {DATI_ATTO_FILENAME, DATI_ATTO_FIRMATO_FILENAME}
                ),
                None,
            )
            indice_busta_generated = (
                indice_root.tag == "IndiceBusta"
                and atto_node is not None
                and bool(atto_node.get("Nome"))
                and dati_node is not None
            )
        except Exception as exc:
            xml_ok = False
            indice_documenti_generated = False
            indice_busta_generated = False
            issues.append(
                {
                    "code": "T002",
                    "level": "BLOCK",
                    "title": "DatiAtto.xml non generabile",
                    "detail": "Il payload XML tecnico non è stato generato correttamente.",
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Correggi i metadati della busta prima del deposito.",
                }
            )

        if not indice_busta_generated:
            issues.append(
                {
                    "code": "INDICE-BUSTA-MISSING",
                    "level": "BLOCK",
                    "title": "IndiceBusta.xml ministeriale non generato",
                    "detail": "Atto.msg deve contenere IndiceBusta.xml con atto principale e allegati.",
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Rigenera la busta includendo IndiceBusta.xml prima dell'invio reale.",
                }
            )

        if not dati_atto_signed:
            issues.append(
                {
                    "code": "DATI-ATTO-SIGNATURE-MISSING",
                    "level": "BLOCK",
                    "title": "DatiAtto.xml non firmato",
                    "detail": "DatiAtto.xml deve essere sottoscritto digitalmente e inserito in busta come DatiAtto.xml.p7m.",
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Firma DatiAtto.xml con Local Signer e riprendi la generazione di Atto.enc.",
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

        transport = dict(self._last_transport_audit or {})
        transport_indice_ok = transport.get("atto_msg_indice_busta_valid") is True or not transport
        real_transport = (
            transport.get("uses_real_encryption") is True
            and transport.get("atto_enc_cms_valid") is True
            and transport.get("busta_verifica_valida") is True
            and transport.get("atto_msg_indice_busta_valid") is True
        )
        if not transport_indice_ok:
            issues.append(
                {
                    "code": "INDICE-BUSTA-STRUCTURE",
                    "level": "BLOCK",
                    "title": "IndiceBusta.xml non coerente con Atto.msg",
                    "detail": "Atto.msg deve contenere IndiceBusta.xml che richiama esattamente atto, DatiAtto.xml.p7m e allegati presenti.",
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Rigenera la busta e ripeti la simulazione PEC prima dell'invio reale.",
                }
            )
        if not real_transport:
            issues.append(
                {
                    "code": "ATTO-ENC-MISSING",
                    "level": "BLOCK",
                    "title": "Atto.enc ministeriale non generato",
                    "detail": (
                        "La busta non dispone ancora di Atto.enc ottenuto dalla cifratura "
                        f"di Atto.msg con algoritmo {PST_BUSTA_ENCRYPTION_ALGORITHM}."
                    ),
                    "source": (
                        f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}; "
                        "comunicazione PST 23/12/2025"
                    ),
                    "suggested_action": "Genera di nuovo la busta dopo il recupero del certificato PST dell'ufficio.",
                }
            )

        t002_status = "ok" if xml_ok and indice_busta_generated and dati_atto_signed and transport_indice_ok else "warning"
        if not xml_ok or not indice_busta_generated or not transport_indice_ok:
            t002_status = "block"
        t003_status = "block" if size_bytes > PST_MAX_BUSTA_BYTES else "ok"

        blocks_direct_send = any(issue.get("level") == "BLOCK" for issue in issues)
        next_actions = []
        if not real_transport:
            next_actions = list(transport.get("guided_next_actions") or [])
            if not next_actions:
                next_actions = [
                    f"Genera Atto.msg e Atto.enc cifrato {PST_BUSTA_ENCRYPTION_ALGORITHM} con certificato PST dell'ufficio.",
                    "Ripeti il controllo busta e verifica destinatario PEC prima dell'invio.",
                ]
        if not dati_atto_signed:
            action = "Firma DatiAtto.xml con Local Signer: il deposito riprende solo dopo DatiAtto.xml.p7m."
            if action not in next_actions:
                next_actions.insert(0, action)

        return {
            "transport_mode": transport.get("transport_mode") or "atto_enc_non_generato",
            "expected_transport_mode": "atto_enc_da_atto_msg_cifrato_aes256",
            "uses_real_encryption": real_transport,
            "required_encryption_algorithm": PST_BUSTA_ENCRYPTION_ALGORITHM,
            "encryption_required_from": PST_BUSTA_ENCRYPTION_REQUIRED_FROM,
            "encryption_fatal_from": PST_BUSTA_ENCRYPTION_FATAL_FROM,
            "encryption_requirement_status": "conforme_aes256" if real_transport else "non_conforme_invio_reale",
            "blocks_direct_send": blocks_direct_send,
            "guided_completion_required": blocks_direct_send,
            "guided_next_actions": next_actions,
            "atto_msg_generated": bool(transport.get("atto_msg_generated")),
            "atto_msg_path": transport.get("atto_msg_path", ""),
            "atto_msg_sha256": transport.get("atto_msg_sha256", ""),
            "atto_enc_path": transport.get("atto_enc_path", ""),
            "atto_enc_sha256": transport.get("atto_enc_sha256", ""),
            "atto_enc_cms_valid": transport.get("atto_enc_cms_valid") is True,
            "busta_verifica_valida": transport.get("busta_verifica_valida") is True,
            "atto_msg_indice_busta_valid": transport.get("atto_msg_indice_busta_valid") is True,
            "certificate": transport.get("certificate"),
            "certificate_error_code": transport.get("certificate_error_code", ""),
            "certificate_error": transport.get("certificate_error", ""),
            "dati_atto_signed": dati_atto_signed,
            "dati_atto_filename": DATI_ATTO_FIRMATO_FILENAME if dati_atto_signed else DATI_ATTO_FILENAME,
            "indice_busta_generated": indice_busta_generated,
            "indice_busta_xml_generated": indice_busta_generated,
            "indice_busta_atto_filename": transport.get("indice_busta_atto_filename", ""),
            "indice_busta_dati_atto_filename": transport.get("indice_busta_dati_atto_filename", ""),
            "indice_busta_documenti": transport.get("indice_busta_documenti", []),
            "indice_busta_filename": INDICE_BUSTA_FILENAME,
            "indice_documenti_generated": indice_documenti_generated,
            "indice_documenti_filename": INDICE_DOCUMENTI_FILENAME,
            "size_bytes": size_bytes,
            "max_size_bytes": PST_MAX_BUSTA_BYTES,
            "max_size_mb": PST_MAX_BUSTA_MB,
            "formal_checks": {
                "T001": {
                    "status": "ok" if real_transport else "non_verificabile_offline",
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
                },
                {
                    "label": "Specifiche tecniche ex art. 34 D.M. 44/2011 - Provvedimento 7 agosto 2024",
                    "url": PST_DM44_SPECIFICHE_2024_DETAIL_URL,
                },
                {
                    "label": "Aggiornamento algoritmo cifratura busta telematica - AES256",
                    "url": PST_BUSTA_ENCRYPTION_UPDATE_URL,
                }
            ],
            "issues": issues,
        }

    def crea_busta(
        self,
        output_dir: str,
        *,
        dati_atto_firmato: bytes | None = None,
        require_dati_atto_firmato: bool = False,
    ) -> str:
        """
        Crea Atto.msg e Atto.enc e salva tutto nella directory specificata.

        Args:
            output_dir: Directory dove salvare la busta

        Returns:
            Percorso ad Atto.enc.
        """
        output_dir = self._runtime_path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        busta_dir = self._runtime_path(tempfile.mkdtemp(prefix="busta_", dir=str(output_dir)))

        if require_dati_atto_firmato and not dati_atto_firmato:
            raise ValueError("DatiAtto.xml deve essere firmato prima di generare Atto.enc.")
        if dati_atto_firmato:
            try:
                from pct.firma import busta_cades_valida
            except Exception as exc:
                raise ValueError("Verifica CAdES non disponibile per DatiAtto.xml.p7m.") from exc
            if not busta_cades_valida(dati_atto_firmato):
                raise ValueError("DatiAtto.xml.p7m non contiene una firma CAdES valida.")

        dati_atto_filename = DATI_ATTO_FIRMATO_FILENAME if dati_atto_firmato else DATI_ATTO_FILENAME
        indice_pdf = self._crea_indice_documenti_pdf()
        indice_busta_xml = self._crea_indice_busta_xml(dati_atto_filename=dati_atto_filename)
        xml_content = self._crea_xml_dati_atto(indice_pdf)
        atto_msg = self._crea_atto_msg(
            xml_content=xml_content,
            indice_busta_xml=indice_busta_xml,
            indice_pdf=indice_pdf,
            dati_atto_firmato=dati_atto_firmato,
        )

        atto_msg_path = busta_dir / ATTO_MSG_FILENAME
        atto_enc_path = busta_dir / ATTO_ENC_FILENAME
        atto_msg_path.write_bytes(atto_msg)
        atto_msg_sha256 = self._hash_bytes(atto_msg)
        indice_msg_check = self._verifica_atto_msg_payloads(
            atto_msg,
            dati_atto_filename=dati_atto_filename,
            require_dati_atto_firmato=require_dati_atto_firmato,
        )
        if not indice_msg_check["valida"]:
            raise ValueError("Busta ministeriale non conforme: " + "; ".join(indice_msg_check["errori"]))

        self._last_atto_msg_path = str(atto_msg_path)
        self._last_atto_enc_path = ""
        self._last_transport_audit = {
            "transport_mode": "atto_msg_generato_senza_atto_enc",
            "uses_real_encryption": False,
            "required_encryption_algorithm": PST_BUSTA_ENCRYPTION_ALGORITHM,
            "atto_msg_generated": True,
            "atto_msg_path": str(atto_msg_path),
            "atto_enc_path": "",
            "atto_msg_size": len(atto_msg),
            "atto_msg_sha256": atto_msg_sha256,
            "atto_msg_indice_busta_valid": True,
            "dati_atto_signed": bool(dati_atto_firmato),
            "dati_atto_filename": dati_atto_filename,
            "indice_busta_generated": True,
            "indice_busta_atto_filename": indice_msg_check.get("indice_busta_atto_filename", ""),
            "indice_busta_dati_atto_filename": indice_msg_check.get("indice_busta_dati_atto_filename", ""),
            "indice_busta_documenti": indice_msg_check.get("documenti", []),
            "indice_busta_filename": INDICE_BUSTA_FILENAME,
            "indice_documenti_filename": INDICE_DOCUMENTI_FILENAME,
            "certificate": None,
            "certificate_error": "",
            "guided_next_actions": [
                f"Recupera o collega il certificato pubblico PST .cer dell'ufficio {self.dati.codice_ufficio}.",
                f"Genera Atto.enc cifrato {PST_BUSTA_ENCRYPTION_ALGORITHM} da Atto.msg prima dell'invio reale.",
                "Ripeti la prova busta e presidia le ricevute dal fascicolo.",
            ],
        }

        try:
            cert_info = risolvi_certificato_cifratura_ufficio(self.dati.codice_ufficio)
            cert = carica_certificato_cifratura(cert_info.path)
            encrypted = cifra_atto_msg_aes256(atto_msg, cert)
            encrypted_audit = inspect_atto_enc_payload(encrypted)
            if encrypted_audit.get("valid") is not True:
                raise PSTCifraturaError("Atto.enc generato non è un CMS EnvelopedData ministeriale valido.")
        except PSTCifraturaError as exc:
            detail = str(exc)
            non_pubblicato = "Certificato di cifratura PST non trovato" in detail
            public_error = (
                (
                    f"Il PST non pubblica un certificato pubblico .cer di cifratura per l'ufficio "
                    f"{self.dati.codice_ufficio}. "
                    if non_pubblicato
                    else f"Certificato pubblico PST .cer non recuperabile per l'ufficio {self.dati.codice_ufficio}. "
                )
                + "Il pacchetto di controllo resta disponibile, ma Atto.enc ministeriale non e' ancora generato."
            )
            guided_next_actions = [
                (
                    f"Verifica sul PST ministeriale se l'ufficio {self.dati.codice_ufficio} pubblica un .cer "
                    "o se deve essere usato un diverso ufficio/canale ufficiale."
                    if non_pubblicato
                    else f"Recupera o collega il certificato pubblico PST .cer dell'ufficio {self.dati.codice_ufficio}."
                ),
                f"Genera Atto.enc cifrato {PST_BUSTA_ENCRYPTION_ALGORITHM} da Atto.msg prima dell'invio reale.",
                "Ripeti la prova busta e presidia le ricevute dal fascicolo.",
            ]
            self._last_transport_audit = {
                **(self._last_transport_audit or {}),
                "transport_mode": "atto_msg_generato_cifratura_pst_non_completata",
                "certificate_error_code": (
                    "certificato_cifratura_non_pubblicato"
                    if non_pubblicato
                    else "certificato_cifratura_non_recuperabile"
                ),
                "certificate_error": public_error,
                "certificate_error_detail": detail,
                "guided_next_actions": guided_next_actions,
            }
            raise

        atto_enc_path.write_bytes(encrypted)
        verifica = self.verifica_busta(str(atto_enc_path))
        if verifica.get("valida") is not True:
            raise PSTCifraturaError(
                "Atto.enc generato da una busta non conforme: "
                + "; ".join(str(item) for item in verifica.get("errori", []))
            )
        atto_enc_sha256 = self._hash_bytes(encrypted)

        self._last_atto_enc_path = str(atto_enc_path)
        self._last_transport_audit = {
            "transport_mode": "atto_enc_da_atto_msg_cifrato_aes256",
            "uses_real_encryption": True,
            "required_encryption_algorithm": PST_BUSTA_ENCRYPTION_ALGORITHM,
            "atto_msg_generated": True,
            "atto_msg_path": str(atto_msg_path),
            "atto_enc_path": str(atto_enc_path),
            "atto_msg_size": len(atto_msg),
            "atto_msg_sha256": atto_msg_sha256,
            "atto_enc_size": len(encrypted),
            "atto_enc_sha256": atto_enc_sha256,
            "atto_enc_cms_valid": True,
            "busta_verifica_valida": True,
            "atto_msg_indice_busta_valid": True,
            "content_encryption_algorithm": encrypted_audit.get("encryption_algorithm", ""),
            "content_encryption_algorithm_oid": encrypted_audit.get("encryption_algorithm_oid", ""),
            "cms_content_type": encrypted_audit.get("content_type", ""),
            "cms_recipients": encrypted_audit.get("recipients"),
            "dati_atto_signed": bool(dati_atto_firmato),
            "dati_atto_filename": dati_atto_filename,
            "indice_busta_generated": True,
            "indice_busta_atto_filename": indice_msg_check.get("indice_busta_atto_filename", ""),
            "indice_busta_dati_atto_filename": indice_msg_check.get("indice_busta_dati_atto_filename", ""),
            "indice_busta_documenti": indice_msg_check.get("documenti", []),
            "indice_busta_filename": INDICE_BUSTA_FILENAME,
            "indice_documenti_filename": INDICE_DOCUMENTI_FILENAME,
            "certificate": {
                "codice_ufficio": cert_info.codice_ufficio,
                "subject": cert_info.subject,
                "issuer": cert_info.issuer,
                "serial_number": cert_info.serial_number,
                "not_valid_after": cert_info.not_valid_after,
                "sha256": cert_info.sha256,
                "source_url": cert_info.source_url,
            },
        }

        return str(atto_enc_path)

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
            enc_path = self._runtime_path(busta_path, must_be_file=True)
            atto_msg_path = enc_path.with_name(ATTO_MSG_FILENAME)
            if not atto_msg_path.exists():
                risultato["errori"].append(f"{ATTO_MSG_FILENAME} mancante accanto ad {ATTO_ENC_FILENAME}")
                return risultato

            atto_msg_bytes = atto_msg_path.read_bytes()
            attachments = self._atto_msg_attachments(atto_msg_bytes)
            has_dati_atto_xml = DATI_ATTO_FILENAME in attachments
            has_dati_atto_signed = DATI_ATTO_FIRMATO_FILENAME in attachments
            dati_atto_filename = DATI_ATTO_FIRMATO_FILENAME if has_dati_atto_signed else DATI_ATTO_FILENAME
            indice_msg_check = self._verifica_atto_msg_payloads(
                atto_msg_bytes,
                dati_atto_filename=dati_atto_filename,
                require_dati_atto_firmato=has_dati_atto_signed,
            )
            if not indice_msg_check["valida"]:
                risultato["errori"].extend(indice_msg_check["errori"])
                return risultato
            risultato["documenti"] = list(indice_msg_check.get("documenti", []))

            if has_dati_atto_signed:
                try:
                    from pct.firma import busta_cades_valida
                    if not busta_cades_valida(attachments[DATI_ATTO_FIRMATO_FILENAME]):
                        risultato["errori"].append("DatiAtto.xml.p7m non contiene una firma CAdES valida")
                        return risultato
                except Exception as exc:
                    risultato["errori"].append(f"Verifica DatiAtto.xml.p7m non completata: {exc}")
                    return risultato

            if has_dati_atto_xml:
                xml_data = attachments[DATI_ATTO_FILENAME]
                root = etree.fromstring(xml_data)
                ns = {"p": self.NAMESPACE}

                id_el = root.find("p:IdBusta", ns)
                if id_el is not None:
                    risultato["id_busta"] = id_el.text

                for doc in root.findall(".//p:NomeFile", ns):
                    if doc.text and doc.text not in risultato["documenti"]:
                        risultato["documenti"].append(doc.text)

            risultato["valida"] = True
            risultato["audit_tecnico"] = self.audit_conformita_pst()
            risultato["atto_msg_sha256"] = self._hash_bytes(atto_msg_bytes)
            risultato["atto_enc_sha256"] = self._hash_bytes(enc_path.read_bytes())
            risultato["indice_busta_atto_filename"] = indice_msg_check.get("indice_busta_atto_filename", "")
            risultato["indice_busta_dati_atto_filename"] = indice_msg_check.get("indice_busta_dati_atto_filename", "")
        except Exception as e:
            risultato["errori"].append(str(e))

        return risultato
