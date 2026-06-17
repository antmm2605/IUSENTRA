"""Preparazione ministeriale della busta di deposito PCT."""

import hashlib
import mimetypes
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

    Atto.msg contiene DatiAtto.xml, atto principale, allegati e indice.
    Atto.enc è il CMS PKCS#7 cifrato AES256 con il certificato pubblico PST
    dell'ufficio destinatario.
    """

    NAMESPACE = "http://www.giustizia.it/processo_telematico"

    def __init__(self, dati: DatiBusta):
        self.dati = dati
        self.id_busta = str(uuid.uuid4()).upper()
        self.timestamp = datetime.now()
        self._last_transport_audit: dict | None = None
        self._last_atto_msg_path: str = ""
        self._last_atto_enc_path: str = ""

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
        pdf = canvas.Canvas(buffer, pagesize=A4)
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
        indice_pdf: bytes,
    ) -> list[tuple[str, bytes, str, str]]:
        payloads: list[tuple[str, bytes, str, str]] = [
            ("DatiAtto.xml", xml_content, "application", "xml")
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

    def _crea_atto_msg(self, *, xml_content: bytes, indice_pdf: bytes) -> bytes:
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
            indice_pdf=indice_pdf,
        ):
            message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
        return message.as_bytes(policy=policy.SMTP)

    def stima_dimensione_busta(self) -> int:
        """Stima la dimensione della busta simulata, includendo un overhead minimo."""
        indice_pdf = self._crea_indice_documenti_pdf()
        totale = len(self._crea_xml_dati_atto(indice_pdf)) + len(indice_pdf) + 4096
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
        indice_generated = bool(indice_pdf)
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
                indice_generated = False
        except Exception as exc:
            xml_ok = False
            indice_generated = False
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
        real_transport = transport.get("uses_real_encryption") is True
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

        t002_status = "warning"
        if not xml_ok:
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
            "atto_enc_path": transport.get("atto_enc_path", ""),
            "certificate": transport.get("certificate"),
            "certificate_error": transport.get("certificate_error", ""),
            "indice_busta_generated": indice_generated,
            "indice_busta_filename": INDICE_DOCUMENTI_FILENAME,
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

    def crea_busta(self, output_dir: str) -> str:
        """
        Crea Atto.msg e Atto.enc e salva tutto nella directory specificata.

        Args:
            output_dir: Directory dove salvare la busta

        Returns:
            Percorso ad Atto.enc.
        """
        output_dir = self._runtime_path(output_dir)
        busta_dir = output_dir / f"busta_{self.id_busta[:8]}"
        # lgtm[py/path-injection] Directory risolta con resolve_runtime_path prima della creazione.
        busta_dir.mkdir(parents=True, exist_ok=True)

        indice_pdf = self._crea_indice_documenti_pdf()
        xml_content = self._crea_xml_dati_atto(indice_pdf)
        atto_msg = self._crea_atto_msg(xml_content=xml_content, indice_pdf=indice_pdf)

        atto_msg_path = busta_dir / ATTO_MSG_FILENAME
        atto_enc_path = busta_dir / ATTO_ENC_FILENAME
        atto_msg_path.write_bytes(atto_msg)

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
        except PSTCifraturaError as exc:
            public_error = (
                f"Certificato pubblico PST .cer non recuperabile per l'ufficio {self.dati.codice_ufficio}. "
                "Il pacchetto di controllo resta disponibile, ma Atto.enc ministeriale non e' ancora generato."
            )
            self._last_transport_audit = {
                **(self._last_transport_audit or {}),
                "transport_mode": "atto_msg_generato_cifratura_pst_non_completata",
                "certificate_error": public_error,
                "certificate_error_detail": str(exc),
                "guided_next_actions": [
                    f"Recupera o collega il certificato pubblico PST .cer dell'ufficio {self.dati.codice_ufficio}.",
                    f"Genera Atto.enc cifrato {PST_BUSTA_ENCRYPTION_ALGORITHM} da Atto.msg prima dell'invio reale.",
                    "Ripeti la prova busta e presidia le ricevute dal fascicolo.",
                ],
            }
            raise

        atto_enc_path.write_bytes(encrypted)

        self._last_atto_enc_path = str(atto_enc_path)
        self._last_transport_audit = {
            "transport_mode": "atto_enc_da_atto_msg_cifrato_aes256",
            "uses_real_encryption": True,
            "required_encryption_algorithm": PST_BUSTA_ENCRYPTION_ALGORITHM,
            "atto_msg_generated": True,
            "atto_msg_path": str(atto_msg_path),
            "atto_enc_path": str(atto_enc_path),
            "atto_msg_size": len(atto_msg),
            "atto_enc_size": len(encrypted),
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

            message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
            attachments: dict[str, bytes] = {}
            for part in message.iter_attachments():
                filename = part.get_filename() or ""
                if filename:
                    attachments[Path(filename).name] = part.get_payload(decode=True) or b""

            if "DatiAtto.xml" not in attachments:
                risultato["errori"].append("DatiAtto.xml mancante in Atto.msg")
                return risultato
            if INDICE_DOCUMENTI_FILENAME not in attachments:
                risultato["errori"].append(f"{INDICE_DOCUMENTI_FILENAME} mancante in Atto.msg")
                return risultato

            xml_data = attachments["DatiAtto.xml"]
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
