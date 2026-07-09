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
from typing import Any, List, Optional
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
INDICE_BUSTA_TIPI_ALLEGATO = frozenset({"SM", "IR", "PL", "DA", "RT", "RU", "PA", "RA", "PC", "D", "A", "IA"})
MINISTERIAL_ATTI_NS = "http://schemi.processotelematico.giustizia.it/tipi/atti/v6"
MINISTERIAL_ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/tipi/anagrafiche/v4"
MINISTERIAL_INTRO_NS = "http://schemi.processotelematico.giustizia.it/sicid/introduttivi/v6"
MINISTERIAL_PARTE_NS = "http://schemi.processotelematico.giustizia.it/sicid/parte/v6"
MINISTERIAL_ATTI_V7_NS = "http://schemi.processotelematico.giustizia.it/tipi/atti/v7"
SICID_INTRO_V7_NS = "http://schemi.processotelematico.giustizia.it/sicid/introduttivi/v7"
SICID_PARTE_V7_NS = "http://schemi.processotelematico.giustizia.it/sicid/parte/v7"
SIGP_ATTI_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/atti/v3"
SIGP_INTRO_NS = "http://schemi.processotelematico.giustizia.it/sigp/cartabia/introduttivi/v3"
SIGP_CORSO_CAUSA_NS = "http://schemi.processotelematico.giustizia.it/sigp/cartabia/corsocausa/v3"
SIGP_PROFESSIONISTA_NS = "http://schemi.processotelematico.giustizia.it/sigp/professionista/v3"
SIGP_SISTEMA_NS = "http://schemi.processotelematico.giustizia.it/sigp/sistema/pubblico/v3"
SIECIC_INTRO_CONCORSUALI_NS = "http://schemi.processotelematico.giustizia.it/siecic/concorsuali/introduttivi/v7"
SIECIC_INTRO_ESECUZIONI_NS = "http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/introduttivi/v8"
SIECIC_PARTE_CONCORSUALI_NS = "http://schemi.processotelematico.giustizia.it/siecic/concorsuali/parte/v8"
SIECIC_PARTE_ESECUZIONI_NS = "http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/parte/v8"
SIECIC_CUR_CONCORSUALI_NS = "http://schemi.processotelematico.giustizia.it/siecic/concorsuali/curatore/v11"
SIECIC_CUS_ESECUZIONI_NS = "http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/custode/v4"
SIECIC_DEL_ESECUZIONI_NS = "http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/delegato/v7"
SIECIC_PROF_CONCORSUALI_NS = "http://schemi.processotelematico.giustizia.it/siecic/concorsuali/professionista/v6"
SIECIC_PROF_ESECUZIONI_NS = "http://schemi.processotelematico.giustizia.it/siecic/esecuzioni/professionista/v6"
SICID_SISTEMA_NS = "http://schemi.processotelematico.giustizia.it/sicid/sistema/pubblico/v3"
SIECIC_SISTEMA_NS = "http://schemi.processotelematico.giustizia.it/siecic/sistema/pubblico/v3"
CASSAZIONE_PARTE_NS = "http://schemi.processotelematico.giustizia.it/cassazione/Parte/v13"
CASSAZIONE_ATTI_NS = "http://schemi.processotelematico.giustizia.it/cassazione/tipi/atti/v13"
MINISTERIAL_ALLEGATI_NS = "http://schemi.processotelematico.giustizia.it/tipi/allegati/v1"
SIECIC_EVENTI_NS = "http://schemi.processotelematico.giustizia.it/siecic/eventi"
SIECIC_TIPIBASE_NS = "http://schemi.processotelematico.giustizia.it/siecic/tipibase/v4"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XSD_NS = "http://www.w3.org/2001/XMLSchema"
DATIATTO_ROOT_NS_BY_GENERATOR_CLASS = {
    "IntroduttiviSicid": MINISTERIAL_INTRO_NS,
    "Parte": MINISTERIAL_PARTE_NS,
    "Introduttivi_SIGP": SIGP_INTRO_NS,
    "CorsoCausa_SIGP": SIGP_CORSO_CAUSA_NS,
    "Professionista_SIGP": SIGP_PROFESSIONISTA_NS,
    "AttoSistema_SIGP": SIGP_SISTEMA_NS,
    "IntroduttiviSiecicConcorsuali": SIECIC_INTRO_CONCORSUALI_NS,
    "IntroduttiviSiecicEsecuzioni": SIECIC_INTRO_ESECUZIONI_NS,
    "ParteSiecicConcorsuali": SIECIC_PARTE_CONCORSUALI_NS,
    "ParteSiecicEsecuzioni": SIECIC_PARTE_ESECUZIONI_NS,
    "CurSiecicConcorsuali": SIECIC_CUR_CONCORSUALI_NS,
    "CusSiecicEsecuzioni": SIECIC_CUS_ESECUZIONI_NS,
    "DelSiecicEsecuzioni": SIECIC_DEL_ESECUZIONI_NS,
    "ProfSiecicConcorsuali": SIECIC_PROF_CONCORSUALI_NS,
    "ProfSiecicEsecuzioni": SIECIC_PROF_ESECUZIONI_NS,
    "Professionista": SICID_PARTE_V7_NS,
    "AttoSistemaSicid": SICID_SISTEMA_NS,
    "AttoSistemaSiecic": SIECIC_SISTEMA_NS,
    "ParteCassazione": CASSAZIONE_PARTE_NS,
}
DATIATTO_V7_ATTI_GENERATOR_CLASSES = frozenset(
    {
        "IntroduttiviSiecicConcorsuali",
        "IntroduttiviSiecicEsecuzioni",
        "ParteSiecicConcorsuali",
        "ParteSiecicEsecuzioni",
        "CurSiecicConcorsuali",
        "CusSiecicEsecuzioni",
        "DelSiecicEsecuzioni",
        "ProfSiecicConcorsuali",
        "ProfSiecicEsecuzioni",
    }
)
DATIATTO_V7_SICID_PARTE_ROOTS = frozenset({"AttoRichiestaVisibilita", "MemorieCartabia"})
DATIATTO_ATTI_NS_BY_GENERATOR_CLASS = {
    "IntroduttiviSicid": MINISTERIAL_ATTI_NS,
    "Parte": MINISTERIAL_ATTI_NS,
    "Introduttivi_SIGP": SIGP_ATTI_NS,
    "CorsoCausa_SIGP": SIGP_ATTI_NS,
    "Professionista_SIGP": SIGP_ATTI_NS,
    "AttoSistema_SIGP": SIGP_SISTEMA_NS,
    "ParteCassazione": CASSAZIONE_ATTI_NS,
    "AttoSistemaSicid": SICID_SISTEMA_NS,
    "AttoSistemaSiecic": SIECIC_SISTEMA_NS,
}
MINISTERIAL_PROCEDIMENTO_BASE_ROOTS = frozenset(
    {
        "Comparsa180",
        "DepositoNoteConclusionali",
        "Memoria183",
        "MemoriaReplica183",
        "MemoriaReplica183N3",
        "PrecisazioneConclusioni",
        "ProduzioneDocumentiRichiesti",
        "ScrittiDifensivi",
    }
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
    valore_causa: Optional[float] = None
    anagrafica_procedimento_xml: bytes | str | None = None
    datiatto_generator_class: str = ""
    datiatto_root_name: str = ""
    datiatto_studio_variable: str = ""
    datiatto_generator_mode: str = ""
    datiatto_required_data: List[str] = field(default_factory=list)
    datiatto_extra: dict[str, Any] = field(default_factory=dict)
    data_notifica_citazione: str = ""


@dataclass(frozen=True)
class _DocumentoBusta:
    filename: str
    payload: bytes
    maintype: str
    subtype: str
    content_id: str
    ruolo_indice: str
    tipo_indice_esterno: str
    source_name: str
    descrizione: str = ""
    is_main: bool = False


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
    def nome_file_ministeriale(filename: str) -> str:
        """Nome fisico esposto in Atto.msg e IndiceBusta.xml."""
        return Path(str(filename or "")).name

    @staticmethod
    def _nome_file_unico(filename: str, used: set[str]) -> str:
        name = Path(str(filename or "")).name or "documento"
        candidate = name
        suffix = 2
        while candidate.casefold() in used:
            path = Path(name)
            candidate = f"{path.stem}_{suffix}{path.suffix}"
            suffix += 1
        used.add(candidate.casefold())
        return candidate

    @staticmethod
    def _content_id_documento(filename: str, payload: bytes, index: int) -> str:
        digest = hashlib.sha256(
            str(index).encode("ascii") + b"\0" + filename.encode("utf-8") + b"\0" + payload
        ).hexdigest()[:32]
        return f"part{digest}"

    @staticmethod
    def _ruolo_allegato_ministeriale(filename: str, tipo: str = "", descrizione: str = "") -> str:
        text = f"{filename} {tipo} {descrizione}".casefold()
        if "procura" in text:
            return "ProcuraLiti"
        if "iscrizione" in text and "ruolo" in text:
            return "NotaIscrizioneRuolo"
        return "AllegatoSemplice"

    @staticmethod
    def _ruolo_ministeriale_registro(codice_registro: str, tipo_atto: str = "") -> str:
        text = f"{codice_registro} {tipo_atto}".upper()
        if "RGL" in text or "LAVOR" in text:
            return "Lavoro"
        if "VG" in text or "VOLONTARIA" in text:
            return "VolontariaGiurisdizione"
        return "Contenzioso"

    def _usa_dati_atto_ministeriale(self) -> bool:
        return bool(self.dati.anagrafica_procedimento_xml or str(self.dati.datiatto_root_name or "").strip())

    def _usa_indice_busta_interno(self) -> bool:
        # Il PST reale rifiuta la busta se l'indice resta solo nel DatiAtto:
        # Atto.msg deve trasportare IndiceBusta.xml come parte MIME nominata.
        return False

    def usa_indice_busta_esterno(self) -> bool:
        return not self._usa_indice_busta_interno()

    @staticmethod
    def _indice_busta_tipo_allegato(filename: str, tipo: str = "", descrizione: str = "") -> str:
        explicit = str(tipo or "").strip().upper()
        if explicit in INDICE_BUSTA_TIPI_ALLEGATO:
            return explicit
        if explicit in {"RICEVUTA_TELEMATICA", "RICEVUTA_TELEMATICA_PAGAMENTO", "PAGAMENTO_TELEMATICO"}:
            return "RT"
        text = f"{filename} {tipo} {descrizione}".casefold()
        compact = text.replace("-", "_").replace(" ", "_")
        if "procura" in text:
            return "PL"
        if "iscrizione" in text and "ruolo" in text:
            return "IR"
        if "avvenuta consegna" in text or "consegna" in text:
            return "RA"
        if filename.casefold().endswith(".eml") and (
            "notifica" in text or "notificazione" in text or "posta certificata" in text
        ):
            return "PA"
        if (
            "rt_" in compact
            or "ricevuta telematica" in text
            or "pagopa" in text
            or ("contributo" in text and "unificat" in text and ("ricevut" in text or "pagament" in text))
            or ("ricevut" in text and "pagament" in text and "telematic" in text)
        ):
            return "RT"
        return "SM"

    def _crea_indice_busta_xml(
        self,
        *,
        dati_atto_filename: str = DATI_ATTO_FILENAME,
        document_parts: list[_DocumentoBusta] | None = None,
    ) -> bytes:
        """Genera l'IndiceBusta.xml ministeriale richiesto nel file Atto.msg."""
        if document_parts is None:
            document_parts = self._documenti_busta_preparati(self._crea_indice_documenti_pdf())
        main_part = next((part for part in document_parts if part.is_main), None)
        if main_part is None:
            raise ValueError("Atto principale non disponibile per IndiceBusta.xml.")
        root = etree.Element("IndiceBusta")
        etree.SubElement(root, "Atto", Nome=main_part.filename, ID=main_part.content_id)

        allegati: list[tuple[str, str, str]] = [
            (dati_atto_filename, self._mime_content_id(dati_atto_filename), "DA")
        ]
        for part in document_parts:
            if part.is_main:
                continue
            allegati.append((part.filename, part.content_id, part.tipo_indice_esterno))

        used_ids: set[str] = {main_part.content_id}
        for filename, content_id, tipo in allegati:
            if content_id in used_ids:
                raise ValueError(f"Content-ID duplicato in {INDICE_BUSTA_FILENAME}: {content_id}")
            used_ids.add(content_id)
            etree.SubElement(root, "Allegato", Nome=filename, ID=content_id, Tipo=tipo)

        payload = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            doctype='<!DOCTYPE IndiceBusta SYSTEM "IndiceBusta.dtd">',
        )
        return payload

    @staticmethod
    def _atto_msg_filename(part: EmailMessage) -> str:
        filename = part.get_filename() or part.get_param("name", header="Content-Type") or ""
        if not filename:
            content_id = str(part.get("Content-ID") or "").strip("<> ")
            if "." in content_id:
                filename = content_id
        return Path(filename).name if filename else ""

    @classmethod
    def _atto_msg_file_parts(cls, atto_msg: bytes) -> tuple[dict[str, bytes], dict[str, dict], list[str]]:
        message = BytesParser(policy=policy.default).parsebytes(atto_msg)
        payloads: dict[str, bytes] = {}
        metadata: dict[str, dict] = {}
        unnamed_parts: list[str] = []
        parts = message.iter_parts() if message.is_multipart() else [message]
        for part in parts:
            filename = cls._atto_msg_filename(part)
            if not filename:
                if part.get_payload(decode=True):
                    unnamed_parts.append(part.get_content_type())
                continue
            decoded_payload = part.get_payload(decode=True)
            if decoded_payload is None and part.is_multipart():
                decoded_payload = part.as_bytes(policy=policy.SMTP)
            payloads[filename] = decoded_payload or b""
            metadata[filename] = {
                "content_type": part.get_content_type(),
                "content_type_name": Path(str(part.get_param("name", header="Content-Type") or "")).name,
                "content_disposition": part.get_content_disposition() or "",
                "content_id": str(part.get("Content-ID") or "").strip("<> "),
                "content_transfer_encoding": str(part.get("Content-Transfer-Encoding") or "").lower(),
            }
        return payloads, metadata, unnamed_parts

    @classmethod
    def _atto_msg_attachments(cls, atto_msg: bytes) -> dict[str, bytes]:
        attachments, _, _ = cls._atto_msg_file_parts(atto_msg)
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
            "indice_busta_content_ids": [],
            "dati_atto_indice_busta_interno": False,
        }
        attachments, part_metadata, unnamed_parts = self._atto_msg_file_parts(atto_msg)
        if unnamed_parts:
            result["errori"].append(
                "Atto.msg contiene parti MIME senza nome file: " + ", ".join(sorted(unnamed_parts))
            )
            return result
        usa_indice_interno = self._usa_indice_busta_interno()
        required = {dati_atto_filename, INDICE_DOCUMENTI_FILENAME}
        if not usa_indice_interno:
            required.add(INDICE_BUSTA_FILENAME)
        missing = sorted(name for name in required if name not in attachments)
        if missing:
            result["errori"].append("Atto.msg incompleto: mancano " + ", ".join(missing))
            return result

        if not usa_indice_interno:
            indice_meta = part_metadata.get(INDICE_BUSTA_FILENAME, {})
            if indice_meta.get("content_type") != "text/xml":
                result["errori"].append(f"{INDICE_BUSTA_FILENAME} deve essere una parte MIME text/xml")
                return result
            if indice_meta.get("content_type_name") != INDICE_BUSTA_FILENAME:
                result["errori"].append(
                    f"{INDICE_BUSTA_FILENAME} deve comparire anche nel parametro name del Content-Type MIME"
                )
                return result

        main_name = self.nome_file_ministeriale(Path(self.dati.atto_principale).name)
        if main_name not in attachments:
            result["errori"].append(f"Atto principale {main_name} mancante in Atto.msg")
            return result
        for allegato in self.dati.allegati:
            name = self.nome_file_ministeriale(Path(allegato.percorso).name)
            if name not in attachments:
                result["errori"].append(f"Allegato {name} mancante in Atto.msg")
                return result

        if require_dati_atto_firmato and dati_atto_filename != DATI_ATTO_FIRMATO_FILENAME:
            result["errori"].append("DatiAtto.xml.p7m firmato obbligatorio per la busta reale")
            return result
        if require_dati_atto_firmato and dati_atto_filename not in attachments:
            result["errori"].append("DatiAtto.xml.p7m firmato mancante in Atto.msg")
            return result

        if not usa_indice_interno:
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
            atto_id = str(atto_node.get("ID") or "").strip()
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
                {
                    "nome": str(node.get("Nome") or ""),
                    "id": str(node.get("ID") or ""),
                    "tipo": str(node.get("Tipo") or ""),
                }
                for node in allegati
            ]
            expected_indice_types: dict[str, str] = {
                dati_atto_filename: "DA",
                INDICE_DOCUMENTI_FILENAME: "SM",
            }
            for allegato in self.dati.allegati:
                expected_name = self.nome_file_ministeriale(Path(allegato.percorso).name)
                expected_indice_types[expected_name] = self._indice_busta_tipo_allegato(
                    expected_name,
                    allegato.tipo,
                    allegato.descrizione,
                )
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
            indexed_entries: list[tuple[str, str, str]] = [(atto_name, atto_id, "Atto")]
            for node in allegati:
                nome = str(node.get("Nome") or "").strip()
                indice_id = str(node.get("ID") or "").strip()
                tipo = str(node.get("Tipo") or "").strip()
                if not nome or not tipo:
                    result["errori"].append(f"{INDICE_BUSTA_FILENAME} contiene allegato senza Nome o Tipo")
                    return result
                if tipo not in INDICE_BUSTA_TIPI_ALLEGATO:
                    result["errori"].append(
                        f"{INDICE_BUSTA_FILENAME} contiene Tipo={tipo} non ammesso dalla DTD ministeriale"
                    )
                    return result
                expected_tipo = expected_indice_types.get(nome)
                if expected_tipo and tipo != expected_tipo:
                    if expected_tipo == "RT":
                        result["errori"].append(
                            f"Ricevuta telematica {nome} non marcata in {INDICE_BUSTA_FILENAME} con Tipo=RT"
                        )
                    else:
                        result["errori"].append(
                            f"{INDICE_BUSTA_FILENAME} classifica {nome} come Tipo={tipo}, atteso Tipo={expected_tipo}"
                        )
                    return result
                if nome not in attachments:
                    result["errori"].append(f"{INDICE_BUSTA_FILENAME} richiama un allegato assente: {nome}")
                    return result
                indexed_entries.append((nome, indice_id, f"Allegato Tipo={tipo}"))

            indexed_names = [nome for nome, _indice_id, _kind in indexed_entries]
            duplicate_names = sorted({nome for nome in indexed_names if indexed_names.count(nome) > 1})
            if duplicate_names:
                result["errori"].append(
                    f"{INDICE_BUSTA_FILENAME} contiene riferimenti duplicati: " + ", ".join(duplicate_names)
                )
                return result

            expected_indexed_names = set(attachments) - {INDICE_BUSTA_FILENAME}
            indexed_name_set = set(indexed_names)
            missing_from_index = sorted(expected_indexed_names - indexed_name_set)
            if missing_from_index:
                result["errori"].append(
                    "Atto.msg contiene allegati non definiti in "
                    f"{INDICE_BUSTA_FILENAME}: " + ", ".join(missing_from_index)
                )
                return result

            content_id_errors: list[str] = []
            content_id_rows: list[dict[str, str]] = []
            for nome, indice_id, kind in indexed_entries:
                mime_content_id = str(part_metadata.get(nome, {}).get("content_id") or "").strip()
                content_id_rows.append({"nome": nome, "indice_id": indice_id, "content_id": mime_content_id})
                if not indice_id:
                    content_id_errors.append(f"{kind} {nome} senza ID in {INDICE_BUSTA_FILENAME}")
                elif not mime_content_id:
                    content_id_errors.append(f"{nome} senza Content-ID MIME in Atto.msg")
                elif indice_id != mime_content_id:
                    content_id_errors.append(
                        f"{nome}: ID indice {indice_id} diverso da Content-ID MIME {mime_content_id}"
                    )
            result["indice_busta_content_ids"] = content_id_rows
            if content_id_errors:
                result["errori"].append(
                    f"{INDICE_BUSTA_FILENAME} non allineato ai Content-ID MIME: "
                    + "; ".join(content_id_errors)
                )
                return result

            result["documenti"] = [atto_name, *[row["nome"] for row in result["indice_busta_allegati"] if row["nome"]]]
            if INDICE_DOCUMENTI_FILENAME not in result["documenti"]:
                result["errori"].append(f"{INDICE_DOCUMENTI_FILENAME} non richiamato da {INDICE_BUSTA_FILENAME}")
                return result
        else:
            result["indice_busta_dati_atto_filename"] = dati_atto_filename
            result["documenti"] = sorted(set(attachments) - {dati_atto_filename})

        dati_atto_xml_for_index_check = b""
        if dati_atto_filename in attachments:
            if dati_atto_filename == DATI_ATTO_FIRMATO_FILENAME:
                try:
                    from pct.firma import estrai_contenuto_cades

                    dati_atto_xml_for_index_check = estrai_contenuto_cades(attachments[dati_atto_filename])
                except Exception as exc:
                    result["errori"].append(
                        f"{dati_atto_filename} non estraibile per verifica indice busta: {exc}"
                    )
                    return result
            else:
                dati_atto_xml_for_index_check = attachments[dati_atto_filename]

        dati_atto_has_internal_index = False
        if dati_atto_xml_for_index_check:
            try:
                dati_atto_root = etree.fromstring(dati_atto_xml_for_index_check)
            except Exception as exc:
                result["errori"].append(f"{dati_atto_filename} non leggibile per verifica indice busta: {exc}")
                return result
            dati_atto_has_internal_index = bool(dati_atto_root.xpath("//*[local-name()='IndiceBusta']"))
            result["dati_atto_indice_busta_interno"] = dati_atto_has_internal_index

        if not usa_indice_interno and dati_atto_has_internal_index:
            result["errori"].append(
                f"Indice busta ambiguo: {INDICE_BUSTA_FILENAME} e IndiceBusta interno in "
                f"{dati_atto_filename} non possono coesistere nel deposito reale."
            )
            return result

        require_indice_interno = require_dati_atto_firmato and self._usa_indice_busta_interno()
        if require_indice_interno:
            internal_error = self._verifica_indice_interno_dati_atto(
                dati_atto_xml_for_index_check,
                attachments=attachments,
                part_metadata=part_metadata,
                dati_atto_filename=dati_atto_filename,
                main_name=main_name,
            )
            if internal_error:
                result["errori"].append(internal_error)
                return result
        result["valida"] = True
        return result

    def _verifica_indice_interno_dati_atto(
        self,
        dati_atto_xml: bytes,
        *,
        attachments: dict[str, bytes],
        part_metadata: dict[str, dict],
        dati_atto_filename: str,
        main_name: str,
    ) -> str:
        try:
            root = etree.fromstring(dati_atto_xml)
        except Exception as exc:
            return f"DatiAtto.xml firmato non leggibile: {exc}"

        indice_nodes = root.xpath("//*[local-name()='IndiceBusta']")
        if not indice_nodes:
            return "DatiAtto.xml.p7m non contiene IndiceBusta ministeriale interno"
        indice = indice_nodes[0]
        atto_nodes = [
            node
            for node in indice
            if isinstance(node.tag, str) and etree.QName(node).localname == "AttoPrincipale"
        ]
        if len(atto_nodes) != 1:
            return "IndiceBusta interno deve contenere un solo AttoPrincipale"

        content_id_to_name: dict[str, str] = {}
        for filename, meta in part_metadata.items():
            content_id = str(meta.get("content_id") or "").strip()
            if content_id:
                content_id_to_name[content_id] = filename

        referenced_names: set[str] = set()
        for node in indice:
            if not isinstance(node.tag, str):
                continue
            ref_id = str(node.get("id") or "").strip()
            if not ref_id:
                return "IndiceBusta interno contiene un riferimento senza attributo id"
            filename = content_id_to_name.get(ref_id)
            if not filename:
                return f"IndiceBusta interno richiama Content-ID assente in Atto.msg: {ref_id}"
            referenced_names.add(filename)

        atto_id = str(atto_nodes[0].get("id") or "").strip()
        if content_id_to_name.get(atto_id) != main_name:
            return f"AttoPrincipale interno richiama {content_id_to_name.get(atto_id) or atto_id}, non {main_name}"

        expected_docs = set(attachments) - {INDICE_BUSTA_FILENAME, dati_atto_filename}
        missing_refs = sorted(expected_docs - referenced_names)
        if missing_refs:
            return "IndiceBusta interno non richiama tutti i documenti della busta: " + ", ".join(missing_refs)
        return ""

    def crea_dati_atto_xml_per_firma(self) -> bytes:
        """Restituisce DatiAtto.xml non firmato da inviare al Local Signer."""
        indice_pdf = self._crea_indice_documenti_pdf()
        document_parts = self._documenti_busta_preparati(indice_pdf)
        return self._crea_xml_dati_atto(indice_pdf, document_parts=document_parts)

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
                "nome": self.nome_file_ministeriale(Path(self.dati.atto_principale).name),
                "descrizione": self.dati.tipo_atto or "Atto principale",
            },
        ]
        for index, allegato in enumerate(self.dati.allegati, start=3):
            rows.append(
                {
                    "numero": str(index),
                    "ruolo": allegato.tipo or "Allegato",
                    "nome": self.nome_file_ministeriale(Path(allegato.percorso).name),
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

    def _documenti_busta_preparati(self, indice_pdf_bytes: bytes) -> list[_DocumentoBusta]:
        used_names: set[str] = set()
        parts: list[_DocumentoBusta] = []

        ap_path = self._runtime_path(self.dati.atto_principale, must_be_file=True)
        ap_payload = ap_path.read_bytes()
        ap_filename = self._nome_file_unico(self.nome_file_ministeriale(ap_path.name), used_names)
        ap_main, ap_sub = self._mime_type(ap_path.name)
        parts.append(
            _DocumentoBusta(
                filename=ap_filename,
                payload=ap_payload,
                maintype=ap_main,
                subtype=ap_sub,
                content_id=self._content_id_documento(ap_filename, ap_payload, 1),
                ruolo_indice="AttoPrincipale",
                tipo_indice_esterno="AT",
                source_name=ap_path.name,
                descrizione=self.dati.tipo_atto or "Atto principale",
                is_main=True,
            )
        )

        for index, allegato in enumerate(self.dati.allegati, start=2):
            all_path = self._runtime_path(allegato.percorso, must_be_file=True)
            payload = all_path.read_bytes()
            filename = self._nome_file_unico(self.nome_file_ministeriale(all_path.name), used_names)
            maintype, subtype = self._mime_type(all_path.name)
            parts.append(
                _DocumentoBusta(
                    filename=filename,
                    payload=payload,
                    maintype=maintype,
                    subtype=subtype,
                    content_id=self._content_id_documento(filename, payload, index),
                    ruolo_indice=self._ruolo_allegato_ministeriale(
                        filename,
                        allegato.tipo,
                        allegato.descrizione,
                    ),
                    tipo_indice_esterno=self._indice_busta_tipo_allegato(
                        filename,
                        allegato.tipo,
                        allegato.descrizione,
                    ),
                    source_name=all_path.name,
                    descrizione=allegato.descrizione or "Documento allegato",
                    is_main=False,
                )
            )

        index_payload = indice_pdf_bytes
        index_filename = self._nome_file_unico(INDICE_DOCUMENTI_FILENAME, used_names)
        parts.append(
            _DocumentoBusta(
                filename=index_filename,
                payload=index_payload,
                maintype="application",
                subtype="pdf",
                content_id=self._content_id_documento(index_filename, index_payload, len(parts) + 1),
                ruolo_indice="AllegatoSemplice",
                tipo_indice_esterno="SM",
                source_name=INDICE_DOCUMENTI_FILENAME,
                descrizione="Indice documenti depositati",
                is_main=False,
            )
        )
        return parts

    def _datiatto_root_name(self) -> str:
        raw = str(self.dati.datiatto_root_name or "").strip()
        if raw:
            return raw
        if self.dati.anagrafica_procedimento_xml:
            return "Ricorso"
        return ""

    def _datiatto_generator_class(self) -> str:
        raw = str(self.dati.datiatto_generator_class or "").strip()
        if raw:
            return raw
        if self._datiatto_root_name() in {"Ricorso", "Citazione"}:
            return "IntroduttiviSicid"
        return ""

    def _datiatto_generator_mode(self) -> str:
        return str(self.dati.datiatto_generator_mode or "").strip()

    def _datiatto_namespace(self) -> str:
        generator_class = self._datiatto_generator_class()
        root_name = self._datiatto_root_name()
        if generator_class == "Parte" and root_name in DATIATTO_V7_SICID_PARTE_ROOTS:
            return SICID_PARTE_V7_NS
        if generator_class in DATIATTO_ROOT_NS_BY_GENERATOR_CLASS:
            return DATIATTO_ROOT_NS_BY_GENERATOR_CLASS[generator_class]
        if generator_class.startswith("Introduttivi"):
            return MINISTERIAL_INTRO_NS
        if generator_class.startswith("Parte"):
            return MINISTERIAL_PARTE_NS
        return ""

    def _datiatto_atti_namespace(self) -> str:
        generator_class = self._datiatto_generator_class()
        if generator_class in DATIATTO_V7_ATTI_GENERATOR_CLASSES:
            return MINISTERIAL_ATTI_V7_NS
        if generator_class == "Parte" and self._datiatto_root_name() in DATIATTO_V7_SICID_PARTE_ROOTS:
            return MINISTERIAL_ATTI_V7_NS
        if generator_class in DATIATTO_ATTI_NS_BY_GENERATOR_CLASS:
            return DATIATTO_ATTI_NS_BY_GENERATOR_CLASS[generator_class]
        if "SIGP" in generator_class:
            return SIGP_ATTI_NS
        if generator_class.startswith("ParteCassazione"):
            return CASSAZIONE_ATTI_NS
        return MINISTERIAL_ATTI_NS

    def _is_datiatto_introduttivo(self) -> bool:
        return self._datiatto_generator_class().startswith("Introduttivi")

    def _is_datiatto_procedimento_base(self) -> bool:
        generator_class = self._datiatto_generator_class()
        mode = self._datiatto_generator_mode()
        is_procedimento = (
            mode == "procedimento_base"
            or (
                generator_class.startswith("Parte")
                and not generator_class.startswith("ParteCassazione")
            )
            or generator_class.startswith("CorsoCausa")
            or generator_class.startswith("Professionista")
            or generator_class.startswith("ProfSiecic")
            or generator_class.startswith("CurSiecic")
            or generator_class.startswith("CusSiecic")
            or generator_class.startswith("DelSiecic")
        )
        return bool(is_procedimento and not generator_class.startswith("ParteCassazione") and self._datiatto_root_name())

    def _is_datiatto_sistema(self) -> bool:
        return self._datiatto_generator_class().startswith("AttoSistema")

    def _is_datiatto_cassazione(self) -> bool:
        return self._datiatto_generator_class().startswith("ParteCassazione")

    def _normalizza_data_notifica_citazione(self) -> str:
        raw = str(self.dati.data_notifica_citazione or "").strip()
        if not raw:
            raise ValueError("Data notificazione citazione mancante: compila il campo prima di generare DatiAtto.xml.")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return raw
        match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match:
            giorno, mese, anno = match.groups()
            return f"{anno}-{mese}-{giorno}"
        raise ValueError("Data notificazione citazione non valida: usa il formato italiano o il campo data.")

    def _datiatto_extra(self) -> dict[str, Any]:
        extra = self.dati.datiatto_extra
        return extra if isinstance(extra, dict) else {}

    def _extra_text(self, key: str, default: str = "") -> str:
        return str(self._datiatto_extra().get(key) or default).strip()

    @staticmethod
    def _element_text(node: etree._Element | None, *names: str) -> str:
        if node is None:
            return ""
        for name in names:
            values = node.xpath(f".//*[local-name()='{name}']/text()")
            for value in values:
                text = str(value or "").strip()
                if text:
                    return text
            attr_value = node.get(name)
            if attr_value:
                return str(attr_value).strip()
        return ""

    @staticmethod
    def _first_child_by_localname(node: etree._Element, localname: str) -> etree._Element | None:
        found = node.xpath(f".//*[local-name()='{localname}']")
        return found[0] if found else None

    @staticmethod
    def _format_date_field(value: Any, label: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError(f"{label} mancante per DatiAtto.xml.")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return raw
        match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match:
            giorno, mese, anno = match.groups()
            return f"{anno}-{mese}-{giorno}"
        raise ValueError(f"{label} non valida: usa il formato italiano o il campo data.")

    @staticmethod
    def _format_decimal_field(value: Any, label: str) -> str:
        raw = str(value or "").strip().replace("€", "").replace(" ", "")
        if not raw:
            raise ValueError(f"{label} mancante per DatiAtto.xml.")
        raw = raw.replace(".", "").replace(",", ".") if "," in raw else raw
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} non valido per DatiAtto.xml.") from exc
        if number <= 0:
            raise ValueError(f"{label} deve essere maggiore di zero per DatiAtto.xml.")
        return f"{number:.2f}"

    def _anagrafica_subjects(self) -> dict[str, str]:
        node = self._anagrafica_procedimento_node()
        parte = self._first_child_by_localname(node, "Parte")
        controparte = self._first_child_by_localname(node, "ControParte")
        avvocato = self._first_child_by_localname(node, "Avvocato")
        parte_id = parte.get("ID") if parte is not None else ""
        parte_cf = self._element_text(parte, "codiceFiscale") or self._extra_text("parte_codice_fiscale")
        controparte_cf = self._element_text(controparte, "codiceFiscale") or self._extra_text("debitore_codice_fiscale")
        avvocato_cf = self._element_text(avvocato, "codiceFiscale") or self.dati.cf_mittente
        avvocato_cognome = self._element_text(avvocato, "cognome", "denominazione")
        avvocato_nome = self._element_text(avvocato, "nome")
        if not avvocato_cognome and self.dati.operatore:
            parts = [part for part in str(self.dati.operatore or "").replace("Avv.", "").split() if part]
            if parts:
                avvocato_cognome = parts[-1]
                avvocato_nome = " ".join(parts[:-1])
        return {
            "parte_id": self._xml_id(parte_id, "parte_1"),
            "parte_cf": re.sub(r"[^A-Za-z0-9]", "", parte_cf).upper(),
            "controparte_cf": re.sub(r"[^A-Za-z0-9]", "", controparte_cf).upper(),
            "avvocato_cf": re.sub(r"[^A-Za-z0-9]", "", avvocato_cf).upper(),
            "avvocato_cognome": avvocato_cognome,
            "avvocato_nome": avvocato_nome,
            "avvocato_via": self._element_text(avvocato, "via"),
            "avvocato_cap": self._element_text(avvocato, "cap"),
            "avvocato_localita": self._element_text(avvocato, "localita"),
            "avvocato_provincia": self._element_text(avvocato, "provincia"),
        }

    def _is_richiesta_visibilita(self) -> bool:
        return self._datiatto_root_name() == "AttoRichiestaVisibilita"

    def _is_progetto_distribuzione(self) -> bool:
        return self._datiatto_root_name() == "ProgettoDistribuzione"

    def _is_pignoramento_siecic(self) -> bool:
        return (
            self._datiatto_generator_class() == "IntroduttiviSiecicEsecuzioni"
            and self._datiatto_root_name() == "IscrizioneRuoloPignoramento"
        )

    def _append_text_if_present(self, parent: etree._Element, ns: str, name: str, value: Any) -> etree._Element | None:
        text = str(value or "").strip()
        if not text:
            return None
        child = etree.SubElement(parent, f"{{{ns}}}{name}")
        child.text = text
        return child

    def _aggiungi_richiesta_visibilita_ministeriale(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        at_ns = MINISTERIAL_ANAGRAFICHE_NS
        subjects = self._anagrafica_subjects()
        missing = []
        if not subjects["parte_cf"]:
            missing.append("codice fiscale parte")
        if not subjects["avvocato_cf"]:
            missing.append("codice fiscale avvocato")
        if not subjects["avvocato_cognome"]:
            missing.append("cognome avvocato")
        if missing:
            raise ValueError("Dati richiesta visibilità mancanti: " + ", ".join(missing) + ".")

        parte_id = subjects["parte_id"] or "parte_1"
        parte = etree.SubElement(root, f"{{{ns}}}Parte", ID=parte_id, codiceFiscale=subjects["parte_cf"])
        avvocato = etree.SubElement(root, f"{{{ns}}}Avvocato")
        etree.SubElement(avvocato, f"{{{at_ns}}}cognome").text = subjects["avvocato_cognome"]
        if subjects["avvocato_nome"]:
            etree.SubElement(avvocato, f"{{{at_ns}}}nome").text = subjects["avvocato_nome"]
        etree.SubElement(avvocato, f"{{{at_ns}}}codiceFiscale").text = subjects["avvocato_cf"]
        if all(subjects[key] for key in ("avvocato_via", "avvocato_cap", "avvocato_localita", "avvocato_provincia")):
            indirizzo = etree.SubElement(avvocato, f"{{{at_ns}}}indirizzo")
            self._append_text_if_present(indirizzo, at_ns, "via", subjects["avvocato_via"])
            self._append_text_if_present(indirizzo, at_ns, "cap", subjects["avvocato_cap"])
            self._append_text_if_present(indirizzo, at_ns, "localita", subjects["avvocato_localita"])
            self._append_text_if_present(indirizzo, at_ns, "provincia", subjects["avvocato_provincia"])
            etree.SubElement(indirizzo, f"{{{at_ns}}}stato").text = "IT"
        etree.SubElement(avvocato, f"{{{at_ns}}}parteRappresentata", ref=parte_id)

    def _aggiungi_progetto_distribuzione_ministeriale(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        deposito = etree.SubElement(root, f"{{{ns}}}deposito")
        evento = etree.SubElement(deposito, f"{{{SIECIC_EVENTI_NS}}}depositoPianoRiparto")
        evento.text = self._extra_text("deposito_progetto", "Vedi progetto")

    def _pignoramento_branch(self) -> str:
        raw = self._extra_text("tipo_pignoramento").casefold()
        if raw in {"immobiliare", "mobiliare_presso_debitore", "mobiliare_presso_terzi"}:
            return raw
        tipo_atto = str(self.dati.tipo_atto or "").casefold()
        if "terz" in tipo_atto:
            return "mobiliare_presso_terzi"
        if "debitore" in tipo_atto:
            return "mobiliare_presso_debitore"
        return "immobiliare"

    def _pignoramento_beni(self) -> list[dict[str, Any]]:
        beni = self._datiatto_extra().get("beni_pignorati")
        if isinstance(beni, list):
            normalized = [item for item in beni if isinstance(item, dict)]
            if normalized:
                return normalized
        raise ValueError("Beni pignorati mancanti per DatiAtto.xml.")

    def _aggiungi_pignoramento_beni(self, root: etree._Element) -> list[str]:
        ns = self._datiatto_namespace()
        beni_node = etree.SubElement(root, f"{{{ns}}}Beni")
        bene_ids: list[str] = []
        for index, bene in enumerate(self._pignoramento_beni(), start=1):
            bene_id = self._xml_id(str(bene.get("id") or ""), f"bene_{index}")
            bene_ids.append(bene_id)
            tipo = str(bene.get("tipo") or self._pignoramento_branch()).casefold()
            is_immobile = "immob" in tipo
            local = "beneImmobileTavolare" if is_immobile else "beneMobile"
            node = etree.SubElement(beni_node, f"{{{SIECIC_TIPIBASE_NS}}}{local}", ID=bene_id)
            if not is_immobile:
                etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}tipologia").text = str(
                    bene.get("tipologia") or "MOBILI"
                ).strip()
            etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}descrizione").text = str(
                bene.get("descrizione") or "Bene pignorato"
            ).strip()
            if is_immobile:
                indirizzo_data = bene.get("indirizzo") if isinstance(bene.get("indirizzo"), dict) else {}
                indirizzo = etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}indirizzo")
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}via").text = str(
                    indirizzo_data.get("via") or "Indirizzo non specificato"
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cap").text = str(
                    indirizzo_data.get("cap") or "00000"
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}localita").text = str(
                    indirizzo_data.get("localita") or "Comune"
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}provincia").text = str(
                    indirizzo_data.get("provincia") or "RM"
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}stato").text = "IT"
                etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}catasto").text = str(
                    bene.get("catasto") or "NCEU"
                ).strip()
                catastali = bene.get("dati_catastali") if isinstance(bene.get("dati_catastali"), dict) else {}
                dati_catastali = etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}datiCatastali")
                etree.SubElement(dati_catastali, f"{{{SIECIC_TIPIBASE_NS}}}sezione").text = str(
                    catastali.get("sezione") or "U"
                ).strip()
                etree.SubElement(dati_catastali, f"{{{SIECIC_TIPIBASE_NS}}}foglio").text = str(
                    catastali.get("foglio") or "1"
                ).strip()
                etree.SubElement(dati_catastali, f"{{{SIECIC_TIPIBASE_NS}}}particella").text = str(
                    catastali.get("particella") or "1"
                ).strip()
                classe = etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}classe", classato="false")
                classe.text = str(bene.get("classe") or "A")
            valore = bene.get("valore") or bene.get("stima") or ""
            if not is_immobile:
                etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}valoreBene").text = self._format_decimal_field(
                    valore, "Valore bene pignorato"
                )
        return bene_ids

    def _aggiungi_pignoramento_estensione_anagrafica(self, root: etree._Element, bene_ids: list[str]) -> None:
        ns = self._datiatto_namespace()
        subjects = self._anagrafica_subjects()
        procedente_cf = self._extra_text("procedente_codice_fiscale") or subjects["parte_cf"]
        debitore_cf = self._extra_text("debitore_codice_fiscale") or subjects["controparte_cf"]
        avvocato_cf = self._extra_text("avvocato_codice_fiscale") or subjects["avvocato_cf"]
        missing = []
        if not procedente_cf:
            missing.append("codice fiscale procedente")
        if not debitore_cf:
            missing.append("codice fiscale debitore")
        if not avvocato_cf:
            missing.append("codice fiscale avvocato")
        if missing:
            raise ValueError("Dati anagrafici pignoramento mancanti: " + ", ".join(missing) + ".")

        est = etree.SubElement(root, f"{{{ns}}}EstensioneAnagrafica")
        debitore = etree.SubElement(est, f"{{{ns}}}DatiDebitore", codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", debitore_cf).upper())
        data_precetto = self._datiatto_extra().get("data_notifica_precetto")
        if data_precetto:
            etree.SubElement(debitore, f"{{{ns}}}dataNotificaPrecetto").text = self._format_date_field(
                data_precetto, "Data notifica precetto"
            )
        etree.SubElement(debitore, f"{{{ns}}}dataPignoramento").text = self._format_date_field(
            self._datiatto_extra().get("data_pignoramento"),
            "Data pignoramento",
        )
        for bene_id in bene_ids:
            bene_ref = etree.SubElement(debitore, f"{{{ns}}}benePignorato", refBene=bene_id)
            diritto = etree.SubElement(
                bene_ref,
                f"{{{SIECIC_TIPIBASE_NS}}}dirittiReali",
                quota="1.0",
                stato="Inventariato",
                stima=self._format_decimal_field(
                    self._datiatto_extra().get("stima_diritto") or self._datiatto_extra().get("importo_precetto"),
                    "Stima diritto pignorato",
                ),
            )
            diritto.text = "Proprieta"

        procedente = etree.SubElement(est, f"{{{ns}}}DatiProcedente", codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", procedente_cf).upper())
        etree.SubElement(
            procedente,
            f"{{{ns}}}riferimentoAvvocato",
            codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", avvocato_cf).upper(),
        )

    def _aggiungi_pignoramento_estensione_rito(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        est = etree.SubElement(root, f"{{{ns}}}EstensioneDatiRito")
        branch = self._pignoramento_branch()
        if branch == "mobiliare_presso_debitore":
            presso = etree.SubElement(est, f"{{{ns}}}pressoDebitore")
            data_citazione = self._datiatto_extra().get("data_citazione")
            if data_citazione:
                etree.SubElement(presso, f"{{{ns}}}dataCitazione").text = self._format_date_field(
                    data_citazione, "Data citazione"
                )
            custode_data = self._datiatto_extra().get("custode")
            custode = custode_data if isinstance(custode_data, dict) else {}
            if not custode:
                raise ValueError("Custode mancante per DatiAtto.xml.")
            custode_node = etree.SubElement(presso, f"{{{ns}}}Custode")
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}via").text = str(
                custode.get("via") or "Indirizzo non specificato"
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cap").text = str(
                custode.get("cap") or "00000"
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}localita").text = str(
                custode.get("localita") or "Comune"
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}provincia").text = str(
                custode.get("provincia") or "RM"
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}stato").text = "IT"
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cognome").text = str(
                custode.get("cognome") or "Custode"
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}nome").text = str(
                custode.get("nome") or ""
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}codiceFiscale").text = re.sub(
                r"[^A-Za-z0-9]", "", str(custode.get("codiceFiscale") or custode.get("codice_fiscale") or "")
            ).upper()
            if not custode_node.xpath("./*[local-name()='codiceFiscale']/text()"):
                raise ValueError("Codice fiscale custode mancante per DatiAtto.xml.")
            self._append_text_if_present(custode_node, MINISTERIAL_ANAGRAFICHE_NS, "PEC", custode.get("pec"))
        elif branch == "mobiliare_presso_terzi":
            presso = etree.SubElement(est, f"{{{ns}}}pressoTerzo")
            etree.SubElement(presso, f"{{{ns}}}dataCitazione").text = self._format_date_field(
                self._datiatto_extra().get("data_citazione"),
                "Data citazione terzo",
            )
            terzo_data = self._datiatto_extra().get("terzo")
            terzo = terzo_data if isinstance(terzo_data, dict) else {}
            terzo_cf = str(terzo.get("codice_fiscale") or terzo.get("codiceFiscale") or "").strip()
            if not terzo_cf:
                raise ValueError("Dati terzo mancanti per DatiAtto.xml.")
            dati_terzo = etree.SubElement(presso, f"{{{ns}}}DatiTerzo", codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", terzo_cf).upper())
            etree.SubElement(dati_terzo, f"{{{ns}}}dataNotificaPignoramento").text = self._format_date_field(
                terzo.get("data_notifica_pignoramento") or self._datiatto_extra().get("data_notifica_pignoramento"),
                "Data notifica pignoramento",
            )
            data_precetto = terzo.get("data_notifica_precetto") or self._datiatto_extra().get("data_notifica_precetto")
            if data_precetto:
                etree.SubElement(dati_terzo, f"{{{ns}}}dataNotificaPrecetto").text = self._format_date_field(
                    data_precetto, "Data notifica precetto"
                )
        else:
            etree.SubElement(est, f"{{{ns}}}immobiliare").text = "immobiliare"

    def _aggiungi_pignoramento_titolo(self, root: etree._Element) -> None:
        titolo_data = self._datiatto_extra().get("titolo")
        titolo = titolo_data if isinstance(titolo_data, dict) else {}
        descrizione = str(titolo.get("descrizione") or "").strip()
        if not descrizione:
            raise ValueError("Titolo esecutivo mancante per DatiAtto.xml.")
        debitore_cf = self._extra_text("debitore_codice_fiscale") or self._anagrafica_subjects()["controparte_cf"]
        if not debitore_cf:
            raise ValueError("Debitore del titolo mancante per DatiAtto.xml.")
        titolo_node = etree.SubElement(root, f"{{{SIECIC_TIPIBASE_NS}}}titolo")
        esecutivo = etree.SubElement(
            titolo_node,
            f"{{{SIECIC_TIPIBASE_NS}}}titoloEsecutivo",
            tipologia=str(titolo.get("tipologia") or "Sentenza"),
        )
        etree.SubElement(esecutivo, f"{{{SIECIC_TIPIBASE_NS}}}descrizione").text = descrizione
        if titolo.get("numero"):
            etree.SubElement(esecutivo, f"{{{SIECIC_TIPIBASE_NS}}}numero").text = str(titolo["numero"]).strip()
        if titolo.get("data_emissione"):
            etree.SubElement(esecutivo, f"{{{SIECIC_TIPIBASE_NS}}}dataEmissione").text = self._format_date_field(
                titolo["data_emissione"], "Data emissione titolo"
            )
        etree.SubElement(
            titolo_node,
            f"{{{SIECIC_TIPIBASE_NS}}}debitore",
            codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", debitore_cf).upper(),
        )

    def _aggiungi_pignoramento_ministeriale(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        root.append(self._anagrafica_procedimento_node())
        etree.SubElement(root, f"{{{ns}}}DataConsegnaPignoramento").text = self._format_date_field(
            self._datiatto_extra().get("data_consegna_pignoramento"),
            "Data consegna pignoramento",
        )
        etree.SubElement(root, f"{{{ns}}}ImportoPrecetto").text = self._format_decimal_field(
            self._datiatto_extra().get("importo_precetto"),
            "Importo precetto",
        )
        bene_ids = self._aggiungi_pignoramento_beni(root)
        self._aggiungi_pignoramento_estensione_anagrafica(root, bene_ids)
        self._aggiungi_pignoramento_estensione_rito(root)
        self._append_text_if_present(root, ns, "CronologicoPignoramento", self._datiatto_extra().get("cronologico_pignoramento"))
        self._aggiungi_pignoramento_titolo(root)

    def _aggiungi_destinazione_e_oggetto_ministeriali(self, root: etree._Element) -> None:
        atti_ns = self._datiatto_atti_namespace()
        etree.SubElement(
            root,
            f"{{{atti_ns}}}destinazione",
            ufficio=str(self.dati.codice_ufficio or "").strip(),
            ruolo=self._ruolo_ministeriale_registro(self.dati.codice_registro, self.dati.tipo_atto),
        )
        etree.SubElement(root, f"{{{atti_ns}}}Oggetto").text = str(self.dati.oggetto or "").strip()
        if self.dati.valore_causa is not None:
            try:
                valore = float(self.dati.valore_causa)
            except (TypeError, ValueError):
                valore = 0.0
            if valore > 0:
                etree.SubElement(root, f"{{{atti_ns}}}ValoreCausa").text = f"{valore:.2f}"

    def _aggiungi_riferimento_procedimento_ministeriale(self, root: etree._Element) -> None:
        atti_ns = self._datiatto_atti_namespace()
        numero_rg = str(self.dati.numero_rg or "").strip()
        anno_rg = str(self.dati.anno_rg or "").strip()
        numero_rg_digits = re.sub(r"\D+", "", numero_rg)
        if not numero_rg_digits or not anno_rg.isdigit():
            raise ValueError(
                "Numero RG e anno RG mancanti o non validi: servono per generare il DatiAtto.xml dell'atto in corso causa."
            )
        procedimento = etree.SubElement(
            root,
            f"{{{atti_ns}}}procedimento",
            ufficio=str(self.dati.codice_ufficio or "").strip(),
            ruolo=self._ruolo_ministeriale_registro(self.dati.codice_registro, self.dati.tipo_atto),
        )
        etree.SubElement(procedimento, f"{{{atti_ns}}}numero").text = numero_rg_digits
        etree.SubElement(procedimento, f"{{{atti_ns}}}anno").text = anno_rg

    def _anagrafica_procedimento_node(self) -> etree._Element:
        raw = self.dati.anagrafica_procedimento_xml
        if raw is None:
            raise ValueError("AnagraficaProcedimento ministeriale mancante per DatiAtto.xml.")
        payload = raw.encode("utf-8") if isinstance(raw, str) else raw
        try:
            node = etree.fromstring(payload)
        except Exception as exc:
            raise ValueError("AnagraficaProcedimento ministeriale non leggibile.") from exc
        if etree.QName(node).localname != "AnagraficaProcedimento":
            raise ValueError("AnagraficaProcedimento ministeriale non valido.")
        return node

    def _crea_xml_dati_atto_ministeriale(self, document_parts: list[_DocumentoBusta]) -> bytes:
        main_part = next((part for part in document_parts if part.is_main), None)
        if main_part is None:
            raise ValueError("Atto principale mancante per DatiAtto.xml ministeriale.")
        root_name = self._datiatto_root_name()
        generator_class = self._datiatto_generator_class()
        if not root_name:
            root_name = "Ricorso"
            generator_class = generator_class or "IntroduttiviSicid"
        namespace = self._datiatto_namespace()
        if namespace and (
            self._is_datiatto_introduttivo()
            or self._is_datiatto_procedimento_base()
            or self._is_datiatto_sistema()
            or self._is_datiatto_cassazione()
        ):
            pass
        else:
            raise ValueError(
                f"DatiAtto.xml {root_name} non completabile con i dati attuali: "
                f"servono i campi obbligatori previsti dallo schema {generator_class or 'ministeriale'}."
            )

        root = etree.Element(
            f"{{{namespace}}}{root_name}",
            nsmap={
                None: namespace,
                "pt": self._datiatto_atti_namespace(),
                "at": MINISTERIAL_ANAGRAFICHE_NS,
                "st": SIECIC_TIPIBASE_NS,
                "evt": SIECIC_EVENTI_NS,
                "xsi": XSI_NS,
                "xsd": XSD_NS,
            },
        )
        if self._is_datiatto_introduttivo() and "citazione" in root_name.casefold():
            root.set("Datacitazione", self._normalizza_data_notifica_citazione())
        if self._is_datiatto_introduttivo():
            self._aggiungi_destinazione_e_oggetto_ministeriali(root)
        elif self._is_datiatto_sistema():
            self._aggiungi_destinazione_e_oggetto_ministeriali(root)
        elif self._is_datiatto_procedimento_base():
            self._aggiungi_riferimento_procedimento_ministeriale(root)
        elif self._is_datiatto_cassazione():
            if self.dati.numero_rg and self.dati.anno_rg:
                self._aggiungi_riferimento_procedimento_ministeriale(root)
            else:
                self._aggiungi_destinazione_e_oggetto_ministeriali(root)

        if self._usa_indice_busta_interno():
            indice = etree.SubElement(root, f"{{{MINISTERIAL_ATTI_NS}}}IndiceBusta")
            etree.SubElement(indice, f"{{{MINISTERIAL_ALLEGATI_NS}}}AttoPrincipale", id=main_part.content_id)
            for part in document_parts:
                if part.is_main:
                    continue
                etree.SubElement(indice, f"{{{MINISTERIAL_ALLEGATI_NS}}}{part.ruolo_indice}", id=part.content_id)

        if self._is_pignoramento_siecic():
            self._aggiungi_pignoramento_ministeriale(root)
        elif self._is_richiesta_visibilita():
            self._aggiungi_richiesta_visibilita_ministeriale(root)
        elif self._is_progetto_distribuzione():
            self._aggiungi_progetto_distribuzione_ministeriale(root)

        if (self._is_datiatto_introduttivo() and not self._is_pignoramento_siecic()) or self._is_datiatto_cassazione():
            root.append(self._anagrafica_procedimento_node())
        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _crea_xml_dati_atto(
        self,
        indice_pdf_bytes: bytes | None = None,
        *,
        document_parts: list[_DocumentoBusta] | None = None,
    ) -> bytes:
        """Crea il file XML DatiAtto.xml con i metadati dell'atto."""
        if indice_pdf_bytes is None:
            indice_pdf_bytes = self._crea_indice_documenti_pdf()
        if document_parts is None:
            document_parts = self._documenti_busta_preparati(indice_pdf_bytes)
        if self._usa_dati_atto_ministeriale():
            return self._crea_xml_dati_atto_ministeriale(document_parts)
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
        etree.SubElement(ap, "NomeFile").text = self.nome_file_ministeriale(Path(self.dati.atto_principale).name)
        etree.SubElement(ap, "Hash").text = self._hash_file(self.dati.atto_principale)

        for i, allegato in enumerate(self.dati.allegati, 1):
            all_el = etree.SubElement(docs, "Allegato")
            etree.SubElement(all_el, "NomeFile").text = self.nome_file_ministeriale(Path(allegato.percorso).name)
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
        if lower.endswith((".eml", ".msg")):
            return "application", "octet-stream"
        guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, _, subtype = guessed.partition("/")
        return maintype or "application", subtype or "octet-stream"

    @staticmethod
    def _mime_content_id(filename: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
            return filename
        digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
        return f"part-{digest}"

    def _document_payloads(
        self,
        *,
        xml_content: bytes,
        indice_busta_xml: bytes | None,
        indice_pdf: bytes,
        dati_atto_firmato: bytes | None = None,
        document_parts: list[_DocumentoBusta] | None = None,
    ) -> list[tuple[str, bytes, str, str, str]]:
        dati_atto_filename = DATI_ATTO_FIRMATO_FILENAME if dati_atto_firmato else DATI_ATTO_FILENAME
        dati_atto_payload = dati_atto_firmato or xml_content
        dati_atto_mime = ("application", "pkcs7-mime") if dati_atto_firmato else ("text", "xml")
        if document_parts is None:
            document_parts = self._documenti_busta_preparati(indice_pdf)
        payloads: list[tuple[str, bytes, str, str, str]] = []
        if indice_busta_xml is not None:
            payloads.append(
                (
                INDICE_BUSTA_FILENAME,
                indice_busta_xml,
                "text",
                "xml",
                self._mime_content_id(INDICE_BUSTA_FILENAME),
                )
            )
        payloads.append(
            (
                dati_atto_filename,
                dati_atto_payload,
                dati_atto_mime[0],
                dati_atto_mime[1],
                self._mime_content_id(dati_atto_filename),
            )
        )

        for part in document_parts:
            payloads.append((part.filename, part.payload, part.maintype, part.subtype, part.content_id))
        return payloads

    def _crea_atto_msg(
        self,
        *,
        xml_content: bytes,
        indice_busta_xml: bytes,
        indice_pdf: bytes,
        dati_atto_firmato: bytes | None = None,
        document_parts: list[_DocumentoBusta] | None = None,
    ) -> bytes:
        message = EmailMessage(policy=policy.SMTP)
        message["Subject"] = f"Atto deposito telematico {self.id_busta[:8]}"
        message["From"] = self.dati.cf_mittente or self.dati.operatore or "iusentra@localhost"
        message["To"] = self.dati.codice_ufficio
        message["Date"] = format_datetime(self.timestamp.astimezone())
        message["X-IUSENTRA-Busta-ID"] = self.id_busta
        message.make_related()
        for filename, payload, maintype, subtype, content_id in self._document_payloads(
            xml_content=xml_content,
            indice_busta_xml=indice_busta_xml,
            indice_pdf=indice_pdf,
            dati_atto_firmato=dati_atto_firmato,
            document_parts=document_parts,
        ):
            part = EmailMessage(policy=policy.SMTP)
            if maintype == "text":
                text_payload = payload.decode("utf-8")
                cte = "7bit" if text_payload.isascii() else "quoted-printable"
                part.set_content(text_payload, subtype=subtype, charset="utf-8", cte=cte)
            else:
                part.set_content(payload, maintype=maintype, subtype=subtype, cte="base64")
            part.set_param("name", filename, header="Content-Type")
            part["Content-ID"] = f"<{content_id}>"
            part.add_header("Content-Disposition", "inline", filename=filename)
            message.attach(part)
        return message.as_bytes(policy=policy.SMTP)

    def stima_dimensione_busta(self) -> int:
        """Stima la dimensione della busta simulata, includendo un overhead minimo."""
        indice_pdf = self._crea_indice_documenti_pdf()
        document_parts = self._documenti_busta_preparati(indice_pdf)
        indice_busta_xml = (
            None if self._usa_indice_busta_interno() else self._crea_indice_busta_xml(document_parts=document_parts)
        )
        totale = (
            len(self._crea_xml_dati_atto(indice_pdf, document_parts=document_parts))
            + (len(indice_busta_xml) if indice_busta_xml is not None else 0)
            + len(indice_pdf)
            + 4096
        )
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
        indice_busta_mime_contract_ok = False
        indice_busta_tipi_ok = False
        dati_atto_indice_busta_interno = False
        indice_busta_ambiguous = False
        dati_atto_signed = bool((self._last_transport_audit or {}).get("dati_atto_signed"))
        try:
            document_parts = self._documenti_busta_preparati(indice_pdf)
            root = etree.fromstring(self._crea_xml_dati_atto(indice_pdf, document_parts=document_parts))
            if self._usa_dati_atto_ministeriale():
                indice_nodes = root.xpath("//*[local-name()='IndiceBusta']")
                dati_atto_indice_busta_interno = bool(indice_nodes)
                if self._usa_indice_busta_interno():
                    atto_nodes = root.xpath("//*[local-name()='IndiceBusta']/*[local-name()='AttoPrincipale']")
                    ref_ids = {
                        str(node.get("id") or "").strip()
                        for node in (indice_nodes[0] if indice_nodes else [])
                        if isinstance(node.tag, str)
                    }
                    expected_ids = {part.content_id for part in document_parts}
                    xml_ok = bool(indice_nodes and len(atto_nodes) == 1 and expected_ids <= ref_ids)
                else:
                    indice_busta_ambiguous = dati_atto_indice_busta_interno
                    expected_root_name = self._datiatto_root_name() or "Ricorso"
                    root_localname = etree.QName(root).localname
                    has_required_ministerial_body = (
                        bool(root.xpath("//*[local-name()='AnagraficaProcedimento']"))
                        if self._is_datiatto_introduttivo()
                        else bool(root.xpath("//*[local-name()='procedimento']"))
                    )
                    xml_ok = (
                        root_localname == expected_root_name
                        and has_required_ministerial_body
                        and not indice_busta_ambiguous
                    )
                indice_documenti_generated = any(part.filename == INDICE_DOCUMENTI_FILENAME for part in document_parts)
            else:
                ns = {"p": self.NAMESPACE}
                if root.find(".//p:Documenti/p:Attoprincipale", ns) is None:
                    xml_ok = False
                indice_node = root.find(
                    f".//p:Documenti/p:Allegato[p:NomeFile='{INDICE_DOCUMENTI_FILENAME}']",
                    ns,
                )
                if indice_node is None:
                    indice_documenti_generated = False

            if self._usa_indice_busta_interno():
                indice_busta_generated = xml_ok
                indice_busta_mime_contract_ok = xml_ok
                indice_busta_tipi_ok = xml_ok
            else:
                indice_root = etree.fromstring(
                    self._crea_indice_busta_xml(
                        dati_atto_filename=DATI_ATTO_FIRMATO_FILENAME if dati_atto_signed else DATI_ATTO_FILENAME,
                        document_parts=document_parts,
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
                expected_external_ids: dict[str, str] = {}
                main_part = next((part for part in document_parts if part.is_main), None)
                if atto_node is not None and main_part is not None:
                    expected_external_ids[main_part.filename] = main_part.content_id
                dati_atto_audit_filename = DATI_ATTO_FIRMATO_FILENAME if dati_atto_signed else DATI_ATTO_FILENAME
                expected_external_ids[dati_atto_audit_filename] = self._mime_content_id(dati_atto_audit_filename)
                expected_external_types: dict[str, str] = {dati_atto_audit_filename: "DA"}
                for part in document_parts:
                    if not part.is_main:
                        expected_external_ids[part.filename] = part.content_id
                        expected_external_types[part.filename] = part.tipo_indice_esterno
                actual_external_ids: dict[str, str] = {}
                actual_external_types: dict[str, str] = {}
                if atto_node is not None:
                    actual_external_ids[str(atto_node.get("Nome") or "").strip()] = str(
                        atto_node.get("ID") or ""
                    ).strip()
                for node in indice_root.findall("Allegato"):
                    nome = str(node.get("Nome") or "").strip()
                    actual_external_ids[nome] = str(node.get("ID") or "").strip()
                    actual_external_types[nome] = str(node.get("Tipo") or "").strip()
                indice_busta_generated = (
                    indice_root.tag == "IndiceBusta"
                    and atto_node is not None
                    and bool(atto_node.get("Nome"))
                    and dati_node is not None
                )
                indice_busta_mime_contract_ok = indice_busta_generated and actual_external_ids == expected_external_ids
                indice_busta_tipi_ok = (
                    indice_busta_generated
                    and not any(tipo not in INDICE_BUSTA_TIPI_ALLEGATO for tipo in actual_external_types.values())
                    and all(actual_external_types.get(nome) == tipo for nome, tipo in expected_external_types.items())
                )
        except Exception as exc:
            xml_ok = False
            indice_documenti_generated = False
            indice_busta_generated = False
            indice_busta_mime_contract_ok = False
            indice_busta_tipi_ok = False
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

        if indice_busta_ambiguous:
            issues.append(
                {
                    "code": "INDICE-BUSTA-AMBIGUO",
                    "level": "BLOCK",
                    "title": "IndiceBusta duplicato",
                    "detail": (
                        f"{INDICE_BUSTA_FILENAME} esterno e IndiceBusta interno nel DatiAtto.xml.p7m "
                        "non devono coesistere: il PST reale lo segnala come indice busta ambiguo."
                    ),
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Rigenera DatiAtto.xml senza IndiceBusta interno e ripeti la simulazione PEC.",
                }
            )

        if not indice_busta_generated:
            issues.append(
                {
                    "code": "INDICE-BUSTA-MISSING",
                    "level": "BLOCK",
                    "title": "IndiceBusta ministeriale non generato",
                    "detail": (
                        "Atto.msg deve contenere IndiceBusta.xml come parte MIME nominata, "
                        "con riferimenti coerenti ai file fisici della busta."
                    ),
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Rigenera la busta e verifica l'indice ministeriale prima dell'invio reale.",
                }
            )
        elif not indice_busta_mime_contract_ok:
            issues.append(
                {
                    "code": "INDICE-BUSTA-MIME-CONTRACT",
                    "level": "BLOCK",
                    "title": "IndiceBusta non allineato agli allegati MIME",
                    "detail": (
                        "Ogni Nome/ID dell'IndiceBusta deve corrispondere al file e al Content-ID "
                        "della parte MIME presente in Atto.msg."
                    ),
                    "source": f"Specifiche tecniche D.M. 44/2011 rev. {PST_DM44_SPECIFICHE_REVISION}",
                    "suggested_action": "Rigenera Atto.msg e ripeti la simulazione PEC prima dell'invio reale.",
                }
            )
        elif not indice_busta_tipi_ok:
            issues.append(
                {
                    "code": "INDICE-BUSTA-TIPI",
                    "level": "BLOCK",
                    "title": "Tipi IndiceBusta non conformi",
                    "detail": (
                        "Ogni allegato deve essere classificato con il Tipo ministeriale corretto; "
                        "le ricevute telematiche di pagamento devono essere indicate con Tipo=RT."
                    ),
                    "source": "IndiceBusta.dtd ministeriale: attributo Tipo dell'elemento Allegato",
                    "suggested_action": "Rigenera la busta dopo la classificazione corretta degli allegati RT/PA/RA/PL/IR/SM.",
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
        transport_indice_ok = (
            transport.get("atto_msg_indice_busta_valid") is True
            and transport.get("indice_busta_ambiguous") is not True
        ) or not transport
        real_transport = (
            transport.get("uses_real_encryption") is True
            and transport.get("atto_enc_cms_valid") is True
            and transport.get("busta_verifica_valida") is True
            and transport.get("atto_msg_indice_busta_valid") is True
            and transport.get("indice_busta_ambiguous") is not True
        )
        if not transport_indice_ok:
            issues.append(
                {
                    "code": "INDICE-BUSTA-STRUCTURE",
                    "level": "BLOCK",
                    "title": "IndiceBusta non coerente con Atto.msg",
                    "detail": (
                        "Atto.msg deve contenere parti fisiche coerenti con IndiceBusta.xml: "
                        "ogni Nome e ID deve corrispondere al file e al Content-ID MIME."
                    ),
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

        t002_status = (
            "ok"
            if xml_ok
            and indice_busta_generated
            and indice_busta_mime_contract_ok
            and indice_busta_tipi_ok
            and dati_atto_signed
            and transport_indice_ok
            else "warning"
        )
        if (
            not xml_ok
            or not indice_busta_generated
            or not indice_busta_mime_contract_ok
            or not indice_busta_tipi_ok
            or not transport_indice_ok
        ):
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
            "dati_atto_indice_busta_interno": transport.get(
                "dati_atto_indice_busta_interno",
                dati_atto_indice_busta_interno,
            )
            is True,
            "indice_busta_ambiguous": transport.get("indice_busta_ambiguous", indice_busta_ambiguous) is True,
            "indice_busta_mode": transport.get("indice_busta_mode")
            or ("interno_dati_atto" if self._usa_indice_busta_interno() else "indice_busta_xml"),
            "indice_busta_external_included": transport.get("indice_busta_external_included")
            if "indice_busta_external_included" in transport
            else not self._usa_indice_busta_interno(),
            "indice_busta_mime_contract_ok": indice_busta_mime_contract_ok,
            "indice_busta_tipi_ok": transport.get("indice_busta_tipi_ok", indice_busta_tipi_ok) is True,
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
        document_parts = self._documenti_busta_preparati(indice_pdf)
        indice_busta_xml = (
            None
            if self._usa_indice_busta_interno()
            else self._crea_indice_busta_xml(
                dati_atto_filename=dati_atto_filename,
                document_parts=document_parts,
            )
        )
        xml_content = self._crea_xml_dati_atto(indice_pdf, document_parts=document_parts)
        if dati_atto_firmato:
            try:
                from pct.firma import estrai_contenuto_cades
            except Exception as exc:
                raise ValueError("Estrazione CAdES non disponibile per DatiAtto.xml.p7m.") from exc
            if estrai_contenuto_cades(dati_atto_firmato) != xml_content:
                raise ValueError(
                    "DatiAtto.xml.p7m non contiene il DatiAtto.xml generato per questa busta."
                )
        atto_msg = self._crea_atto_msg(
            xml_content=xml_content,
            indice_busta_xml=indice_busta_xml,
            indice_pdf=indice_pdf,
            dati_atto_firmato=dati_atto_firmato,
            document_parts=document_parts,
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
            "indice_busta_mime_contract_ok": True,
            "indice_busta_tipi_ok": True,
            "dati_atto_signed": bool(dati_atto_firmato),
            "dati_atto_filename": dati_atto_filename,
            "indice_busta_generated": True,
            "indice_busta_mode": "interno_dati_atto" if self._usa_indice_busta_interno() else "indice_busta_xml",
            "indice_busta_external_included": not self._usa_indice_busta_interno(),
            "indice_busta_atto_filename": indice_msg_check.get("indice_busta_atto_filename", ""),
            "indice_busta_dati_atto_filename": indice_msg_check.get("indice_busta_dati_atto_filename", ""),
            "indice_busta_documenti": indice_msg_check.get("documenti", []),
            "indice_busta_filename": INDICE_BUSTA_FILENAME,
            "dati_atto_indice_busta_interno": indice_msg_check.get("dati_atto_indice_busta_interno") is True,
            "indice_busta_ambiguous": False,
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
            "indice_busta_mime_contract_ok": True,
            "indice_busta_tipi_ok": True,
            "content_encryption_algorithm": encrypted_audit.get("encryption_algorithm", ""),
            "content_encryption_algorithm_oid": encrypted_audit.get("encryption_algorithm_oid", ""),
            "cms_content_type": encrypted_audit.get("content_type", ""),
            "cms_recipients": encrypted_audit.get("recipients"),
            "dati_atto_signed": bool(dati_atto_firmato),
            "dati_atto_filename": dati_atto_filename,
            "indice_busta_generated": True,
            "indice_busta_mode": "interno_dati_atto" if self._usa_indice_busta_interno() else "indice_busta_xml",
            "indice_busta_external_included": not self._usa_indice_busta_interno(),
            "indice_busta_atto_filename": indice_msg_check.get("indice_busta_atto_filename", ""),
            "indice_busta_dati_atto_filename": indice_msg_check.get("indice_busta_dati_atto_filename", ""),
            "indice_busta_documenti": indice_msg_check.get("documenti", []),
            "indice_busta_filename": INDICE_BUSTA_FILENAME,
            "dati_atto_indice_busta_interno": indice_msg_check.get("dati_atto_indice_busta_interno") is True,
            "indice_busta_ambiguous": False,
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
