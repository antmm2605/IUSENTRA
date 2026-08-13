"""Preparazione ministeriale della busta di deposito PCT."""

import hashlib
import mimetypes
import re
from copy import deepcopy
from io import BytesIO
import tempfile
import uuid
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import make_msgid
from pathlib import Path
from typing import Any, List, Optional
from dataclasses import dataclass, field
from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .path_security import UnsafeRuntimePath, resolve_runtime_path
from .atto_enc_validation import inspect_atto_enc_payload
from .document_crypto import ENC_MAGIC, decrypt_doc
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
SICID_PROFESSIONISTA_NS = "http://schemi.processotelematico.giustizia.it/sicid/professionista/v2"
SIGP_ATTI_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/atti/v3"
SIGP_ALLEGATI_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/allegati/v3"
SIGP_TIPI_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/v2"
SIGP_EVENTI_PARTE_NS = "http://schemi.processotelematico.giustizia.it/sigp/eventi/parte/v2"
SIGP_INTRO_NS = "http://schemi.processotelematico.giustizia.it/sigp/cartabia/introduttivi/v3"
SIGP_CORSO_CAUSA_NS = "http://schemi.processotelematico.giustizia.it/sigp/cartabia/corsocausa/v3"
SIGP_PROFESSIONISTA_NS = "http://schemi.processotelematico.giustizia.it/sigp/professionista/v3"
SIGP_SISTEMA_NS = "http://schemi.processotelematico.giustizia.it/sigp/sistema/pubblico/v3"
SIGP_ANAGRAFICHE_NS = "http://schemi.processotelematico.giustizia.it/sigp/tipi/anagrafiche/v2"
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
CASSAZIONE_TIPI_NS = "http://schemi.processotelematico.giustizia.it/cassazione/tipi/v13"
CASSAZIONE_EVENTI_NS = "http://schemi.processotelematico.giustizia.it/cassazione/eventi/v13"
MINISTERIAL_ALLEGATI_NS = "http://schemi.processotelematico.giustizia.it/tipi/allegati/v1"
MINISTERIAL_ALLEGATI_V2_NS = "http://schemi.processotelematico.giustizia.it/tipi/allegati/v2"
CASSAZIONE_ALLEGATI_NS = "http://schemi.processotelematico.giustizia.it/cassazione/tipi/allegati/v13"
MINISTERIAL_EVENTI_PARTE_NS = "http://schemi.processotelematico.giustizia.it/eventi/parte"
MINISTERIAL_EVENTI_PROFESSIONISTA_NS = "http://schemi.processotelematico.giustizia.it/eventi/professionista"
SIGP_EVENTI_PROFESSIONISTA_NS = "http://schemi.processotelematico.giustizia.it/sigp/eventi/professionista"
SIECIC_EVENTI_NS = "http://schemi.processotelematico.giustizia.it/siecic/eventi"
SIECIC_EVENTI_CRISI_NS = "http://schemi.processotelematico.giustizia.it/eventi/crisiimpresa"
SIECIC_TIPIBASE_NS = "http://schemi.processotelematico.giustizia.it/siecic/tipibase/v4"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XSD_NS = "http://www.w3.org/2001/XMLSchema"
DATIATTO_ROOT_NS_BY_GENERATOR_CLASS = {
    "IntroduttiviSicid": SICID_INTRO_V7_NS,
    "Parte": SICID_PARTE_V7_NS,
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
    "Professionista": SICID_PROFESSIONISTA_NS,
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
        "Professionista",
    }
)
DATIATTO_V7_SICID_PARTE_ROOTS = frozenset({"AttoRichiestaVisibilita", "MemorieCartabia"})
DATIATTO_V7_SICID_INTRO_ROOTS = frozenset(
    {"RicorsoImmigrazioneConvalida", "RicorsoReclamoSospensiva"}
)
DATIATTO_ATTI_NS_BY_GENERATOR_CLASS = {
    "IntroduttiviSicid": MINISTERIAL_ATTI_V7_NS,
    "Parte": MINISTERIAL_ATTI_V7_NS,
    "Introduttivi_SIGP": SIGP_ATTI_NS,
    "CorsoCausa_SIGP": SIGP_ATTI_NS,
    "Professionista_SIGP": SIGP_ATTI_NS,
    "AttoSistema_SIGP": SIGP_ATTI_NS,
    "ParteCassazione": CASSAZIONE_ATTI_NS,
    "AttoSistemaSicid": MINISTERIAL_ATTI_V7_NS,
    "AttoSistemaSiecic": MINISTERIAL_ATTI_V7_NS,
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

SICID_PARTE_MODIFICHE_ANAGRAFICA_REQUIRED_ROOTS = frozenset(
    {
        "AttoCostituzioneNuovoAvvocato",
        "ComparsaCostituzioneAppello",
        "ComparsaCostituzioneAppelloIncidentale",
        "CostituzioneConRiconvenzionale",
        "CostituzioneSemplice",
        "Reclamo",
        "RicorsoCautelareCorsoCausa",
        "RicorsoSequestroConservativoCorsoCausa",
        "RicorsoSequestroGiudiziarioCorsoCausa",
    }
)

SICID_PARTE_ISTANZA_EVENT_BY_KEY = {
    "depositoNotaSpese": "depositoNotaSpese",
    "DepositoProveExArt210Cpc": "DepositoProveExArt210Cpc",
    "IstanzaCongiuntaFissazioneUdienza": "IstanzaCongiuntaFissazioneUdienza",
    "IstanzaAnticipazioneUdienza": "IstanzaAnticipazioneDifferimentoUdienza",
    "IstanzaDifferimentoUdienza": "IstanzaAnticipazioneDifferimentoUdienza",
    "IstanzaCorrezioneErroreMateriale": "IstanzaCorrezioneErroreMateriale",
    "IstanzaDeferimentoGiuramento": "IstanzaDeferimentoGiuramento",
    "IstanzaEstromissione": "IstanzaEstromissione",
    "IstanzaFissazioneUdienza": "IstanzaFissazioneUdienza",
    "IstanzaFissazioneUdienzaCollegamentiAudioVisivi": "IstanzaFissazioneUdienzaCollegamentiAudioVisivi",
    "IstanzaInterruzione": "IstanzaInterruzione",
    "IstanzaRevocaUdienzaCollegamentiAudioVisivi": "IstanzaRevocaUdienzaCollegamentiAudioVisivi",
    "IstanzaRicusazioneGiudice": "IstanzaRicusazioneGiudice",
    "IstanzaRimessioneInIstruttoria": "IstanzaRimessioneInIstruttoria",
    "IstanzaRimessioneTermini": "IstanzaRimessioneTermini",
    "IstanzaRinuncia": "IstanzaRinuncia",
    "IstanzaRinvioXDiscussioneOrale": "IstanzaRinvioXDiscussioneOrale",
    "IstanzaSospensioneProvvisoriaEsecuzione": "IstanzaSospensioneProvvisoriaEsecuzione",
    "IstanzaTrasformazioneInConsensuale": "IstanzaTrasformazioneInConsensuale",
    "IstanzaExArt186Bis": "IstanzaExArt186Bis",
    "IstanzaExArt186Quater": "IstanzaExArt186Quater",
    "IstanzaExArt186Ter": "IstanzaExArt186Ter",
    "MemoriaReplica183UC": "MemoriaReplica183UC",
    "DepositoMemoria2409": "DepositoMemoria2409",
    "MemoriaIstruttoria183UC": "MemoriaIstruttoria183UC",
    "NoteConclusionali350Bis": "NoteConclusionali",
    "NoteScrittePC": "NoteScrittePC",
    "NoteScrittePC_DiscussioneOrale": "NoteScrittePC",
    "IstanzaRichiestaEsecutorietaExArt647": "IstanzaRichiestaEsecutorietaExArt647",
    "RichiestaFormulaEsecutiva": "IstanzaRichiestaEsecutorietaExArt647",
    "RichiestaInefficaciaMisuraCautelare": "RichiestaInefficaciaMisuraCautelare",
    "IstanzaRichiestaInefficaciaExArt188": "IstanzaRichiestaInefficaciaExArt188",
}

SICID_PARTE_RICORSO_EVENT_BY_KEY = {
    "DepositoRicorsoDiRiassunzione": "DepositoRicorsoDiRiassunzione",
    "DepositoRicorsoFissazioneUdienzaDiProsecuzioneProcedimento": (
        "DepositoRicorsoFissazioneUdienzaDiProsecuzioneProcedimento"
    ),
    "OpposizioneTardivaExArt668": "OpposizioneTardivaExArt668",
    "RichiestaFissazioneModalitaProvvedimento": "RichiestaFissazioneModalitaProvvedimento",
}

SICID_PARTE_DOCUMENT_EVENT_BY_KEY = {
    "DocumentazioneIntegrativaAUSL": "DocumentazioneIntegrativaAUSL",
    "DocumentazioneIntegrativaPM": "DocumentazioneIntegrativaPM",
    "InventarioEreditaGiacente": "InventarioEreditaGiacente",
    "RelazioneAmministrazioneSostegno": "RelazioneAmministrazioneSostegno",
    "RelazioneFinaleArt2409cc": "RelazioneFinaleArt2409cc",
    "RelazioneIspettoreArt2409cc": "RelazioneIspettoreArt2409cc",
    "RendicontoAmministrazioneSostegno": "RendicontoAmministrazioneSostegno",
    "RendicontoEreditaGiacente": "RendicontoEreditaGiacente",
}

DEPOSITO_SEMPLICE_EVENT_BY_GENERATOR_AND_KEY = {
    "Professionista": {
        "DepositoGiuramentoTelematico": "DepositoGiuramentoTelematico",
        "DepositoIntegrazionePerizia": "integrazionePerizia",
        "DepositoPerizia": "depositoPerizia",
        "DepositoRichiestaProrogaTerminiPerizia": "richiestaProrogaTerminiPerizia",
        "DepositoIstanzaGenerica": "AttoNonCodificato",
        "DepositoIstanzaLiquidazioneCTU": "istanzaLiquidazioneCTU",
        "NotaDepositoProfessionista": "AttoNonCodificato",
    },
    "Professionista_SIGP": {
        "DepositoPerizia": "depositoPerizia",
        "DepositoRichiestaProrogaTerminiPerizia": "richiestaProrogaTerminiPerizia",
        "DepositoIstanzaGenerica": "AttoNonCodificato",
        "DepositoIstanzaLiquidazioneCTU": "istanzaLiquidazioneCTU",
        "NotaDepositoProfessionista": "AttoNonCodificato",
    },
    "ProfSiecicEsecuzioni": {
        "AttoNonCodificato": "attoNonCodificato",
        "DepositoIntegrazioneCTU": "depositoIntegrazioneCTU",
        "DepositoRelazioneCTU": "depositoRelazioneCTU",
        "NotaDeposito": "attoNonCodificato",
    },
    "ProfSiecicConcorsuali": {
        "AttoNonCodificato": "attoNonCodificato",
        "DepositoIntegrazioneCTU": "depositoIntegrazioneCTU",
        "DepositoRelazioneCTU": "depositoRelazioneCTU",
        "NotaDeposito": "attoNonCodificato",
    },
    "CusSiecicEsecuzioni": {
        "AttoNonCodificatoCustode": "attoNonCodificato",
        "IstanzaGenericaCustode": "istanzaGenericaCustode",
        "IstanzaLiquidazioneCustode": "istanzaLiquidazioneCustode",
        "NotaDepositoCustode": "attoNonCodificato",
        "RendicontoCustode": "rendicontoCustode",
    },
    "DelSiecicEsecuzioni": {
        "attoNonCodificato": "attoNonCodificato",
        "avvisoVendita": "avvisoVendita",
        "depositoPrezzo": "depositoPrezzo",
        "istanzaRevocaDecadenzaAggiudicatario": "istanzaRevocaDecadenzaAggiudicatario",
        "NotaDeposito": "attoNonCodificato",
        "relazionePeriodicaDelegato": "relazionePeriodicaDelegato",
        "verbaleAggiudicazione": "verbaleAggiudicazione",
    },
}

SIECIC_PARTE_ATTO_GENERICO_EVENT_BY_GENERATOR_AND_KEY = {
    "ParteSiecicEsecuzioni": {
        "DepositoRinunciaMandato": "depositoRinunciaMandato",
        "DepositoRinunciaEsecuzione": "depositoRinunciaEsecuzione",
        "AttoGenerico": "attoNonCodificato",
        "DepositoIstanza41TUB": "depositoIstanza41TUB",
        "NotaDeposito": "attoNonCodificato",
        "NoteTrattazione": "attoNonCodificato",
        "RichiestaFormulaEsecutiva": "attoNonCodificato",
    },
    "ParteSiecicConcorsuali": {
        "AttoGenerico": "attoNonCodificato",
        "DepositoMemorie": "depositoMemorie",
        "NoteTrattazione": "attoNonCodificato",
    },
}


@dataclass
class Allegato:
    """Rappresenta un allegato nella busta telematica."""

    percorso: str
    descrizione: str
    tipo: str = "ALLEGATO"  # ATTO_PRINCIPALE | ALLEGATO | PROCURA
    nome_file: str = ""


@dataclass
class DatiBusta:
    """Dati strutturati per la creazione della busta telematica."""

    codice_ufficio: str
    codice_registro: str
    oggetto: str
    tipo_atto: str
    atto_principale: str
    ruolo_ministeriale: str = ""
    allegati: List[Allegato] = field(default_factory=list)
    atto_principale_nome: str = ""
    numero_rg: Optional[str] = None
    anno_rg: Optional[int] = None
    operatore: str = ""
    cf_mittente: str = ""
    valore_causa: Optional[float] = None
    contributo_unificato: dict[str, Any] | None = None
    contributo_unificato_richiesto: bool = False
    contributo_unificato_xml_mode: str = ""
    anagrafica_procedimento_xml: bytes | str | None = None
    datiatto_generator_class: str = ""
    datiatto_root_name: str = ""
    datiatto_studio_variable: str = ""
    datiatto_catalog_key: str = ""
    datiatto_generator_mode: str = ""
    datiatto_required_data: List[str] = field(default_factory=list)
    datiatto_extra: dict[str, Any] = field(default_factory=dict)
    professionista: dict[str, Any] = field(default_factory=dict)
    parti: List[dict[str, Any]] = field(default_factory=list)
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
        self._last_role_audit: dict[str, Any] = {}
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
    def _read_document_payload(path: Path) -> bytes:
        payload = decrypt_doc(path.read_bytes())
        if payload.startswith(ENC_MAGIC):
            raise ValueError(f"Documento {path.name} ancora cifrato a riposo dopo la lettura.")
        return payload

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
        name = Path(str(filename or "")).name
        if not name:
            return "documento"

        # Le sostituzioni versionate del fascicolo aggiungono un suffisso tecnico
        # al path fisico. Quel suffisso non appartiene al nome ministeriale.
        signed_storage_name = re.fullmatch(
            r"(?i)(?P<base>.+\.(?:pdf|rtf|txt|jpg|jpeg|gif|tif|tiff|xml|eml|msg|doc|docx))_[0-9a-f]{4}"
            r"(?P<signature>\.p7m)",
            name,
        )
        if signed_storage_name:
            return f"{signed_storage_name.group('base')}{signed_storage_name.group('signature')}"

        storage_name = re.fullmatch(
            r"(?i)(?P<base>.+)_[0-9a-f]{4}(?P<extension>\.(?:pdf|rtf|txt|jpg|jpeg|gif|tif|tiff|xml|eml|msg))",
            name,
        )
        if storage_name:
            return f"{storage_name.group('base')}{storage_name.group('extension')}"
        return name

    @staticmethod
    def _nome_file_unico(filename: str, used: set[str]) -> str:
        name = Path(str(filename or "")).name or "documento"
        candidate = name
        suffix = 2
        while candidate.casefold() in used:
            path = Path(name)
            if path.suffix.casefold() == ".p7m" and len(path.suffixes) >= 2:
                compound_suffix = "".join(path.suffixes[-2:])
                stem = name[: -len(compound_suffix)]
                candidate = f"{stem}_{suffix}{compound_suffix}"
            else:
                candidate = f"{path.stem}_{suffix}{path.suffix}"
            suffix += 1
        used.add(candidate.casefold())
        return candidate

    @staticmethod
    def _content_id_documento(filename: str, payload: bytes, index: int) -> str:
        digest = hashlib.sha256(
            str(index).encode("ascii") + b"\0" + filename.encode("utf-8") + b"\0" + payload
        ).hexdigest()[:32]
        return f"part{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:]}"

    @staticmethod
    def _ruolo_allegato_ministeriale(filename: str, tipo: str = "", descrizione: str = "") -> str:
        text = f"{filename} {tipo} {descrizione}".casefold()
        if "procura" in text:
            return "ProcuraLiti"
        if "iscrizione" in text and "ruolo" in text:
            return "NotaIscrizioneRuolo"
        return "AllegatoSemplice"

    @staticmethod
    def _ruolo_ministeriale_registro(
        codice_registro: str,
        tipo_atto: str = "",
        ruolo_ministeriale: str = "",
    ) -> str:
        explicit = str(ruolo_ministeriale or "").strip()
        allowed = {
            "AffariCivili",
            "AffariCiviliMinorenni",
            "Agraria",
            "CassazioneCivile",
            "Contenzioso",
            "EsecuzioniCivili",
            "EspropriazioniImmobiliari",
            "GiudiceDiPace",
            "Lavoro",
            "Minorenni",
            "Notifiche",
            "Pagamenti",
            "ProcedimentoUnitario",
            "Speciale",
            "VolontariaGiurisdizione",
        }
        if explicit:
            if explicit not in allowed:
                raise ValueError(f"Ruolo ministeriale non riconosciuto: {explicit}.")
            return explicit
        text = f"{codice_registro} {tipo_atto}".upper()
        if "SIGP" in text or "GIUDICE DI PACE" in text:
            return "GiudiceDiPace"
        if "CASS" in text:
            return "CassazioneCivile"
        if "RGL" in text or "LAVOR" in text:
            return "Lavoro"
        if "RGEI" in text or "ESIM" in text or "ESPROPRIAZION" in text:
            return "EspropriazioniImmobiliari"
        if "RGE" in text or "ESM" in text or "ESECUZION" in text:
            return "EsecuzioniCivili"
        if "SIMIN" in text or "MINORENN" in text:
            return "Minorenni"
        if "VG" in text or "VOLONTARIA" in text:
            return "VolontariaGiurisdizione"
        return "Contenzioso"

    def _verifica_ruolo_ministeriale_xml(self, payload: bytes) -> None:
        expected = self._ruolo_ministeriale_registro(
            self.dati.codice_registro,
            self.dati.tipo_atto,
            self.dati.ruolo_ministeriale,
        )
        root = etree.fromstring(payload)
        actual = [
            str(child.get("ruolo") or "").strip()
            for child in root
            if isinstance(child.tag, str)
            and etree.QName(child).localname in {"destinazione", "procedimento"}
            and str(child.get("ruolo") or "").strip()
        ]
        self._last_role_audit = {
            "dati_atto_ruolo_atteso": expected,
            "dati_atto_ruoli_effettivi": actual,
            "dati_atto_ruolo_coerente": bool(actual) and all(role == expected for role in actual),
        }
        if not actual:
            raise ValueError("DatiAtto.xml non contiene il ruolo ministeriale del deposito.")
        if any(role != expected for role in actual):
            raise ValueError(
                "DatiAtto.xml contiene un ruolo diverso dalla pratica: "
                f"atteso {expected}, trovato {', '.join(actual)}."
            )

    def _usa_dati_atto_ministeriale(self) -> bool:
        return bool(self.dati.anagrafica_procedimento_xml or str(self.dati.datiatto_root_name or "").strip())

    def _usa_indice_busta_interno(self) -> bool:
        # Studio Telematico inserisce IndiceBusta nel DatiAtto ministeriale
        # firmato e non aggiunge un IndiceBusta.xml separato ad Atto.msg.
        return self._usa_dati_atto_ministeriale()

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

        document_names = [
            main_name,
            *(self.nome_file_ministeriale(Path(allegato.percorso).name) for allegato in self.dati.allegati),
        ]
        for name in document_names:
            if not name.casefold().endswith(".p7m"):
                continue
            payload = attachments.get(name, b"")
            if payload.startswith(ENC_MAGIC):
                result["errori"].append(
                    f"{name} contiene ancora la cifratura interna PCTENC e non puo' essere inviato al PST"
                )
                return result
            try:
                from pct.firma import busta_cades_valida, estrai_contenuto_cades

                cades_ok = busta_cades_valida(payload)
                embedded = estrai_contenuto_cades(payload)
            except Exception as exc:
                result["errori"].append(f"{name} non verificabile come CAdES: {exc}")
                return result
            if not cades_ok or embedded is None:
                result["errori"].append(
                    f"{name} non e' un contenitore CAdES con contenuto incorporato e firmatario leggibile"
                )
                return result

        if require_dati_atto_firmato and dati_atto_filename != DATI_ATTO_FIRMATO_FILENAME:
            result["errori"].append("DatiAtto.xml.p7m firmato obbligatorio per la busta reale")
            return result
        if require_dati_atto_firmato and dati_atto_filename not in attachments:
            result["errori"].append("DatiAtto.xml.p7m firmato mancante in Atto.msg")
            return result
        if require_dati_atto_firmato:
            from pct.firma import attributi_cades_bes_mancanti

            missing_attrs = attributi_cades_bes_mancanti(attachments[dati_atto_filename])
            if missing_attrs:
                result["errori"].append(
                    "DatiAtto.xml.p7m non aderente al profilo CAdES-BES: mancano "
                    + ", ".join(missing_attrs)
                )
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
        if len(indice_nodes) != 1:
            return "DatiAtto.xml.p7m deve contenere un solo IndiceBusta ministeriale interno"
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
        ap_payload = self._read_document_payload(ap_path)
        ap_filename = self._nome_file_unico(
            self.nome_file_ministeriale(self.dati.atto_principale_nome or ap_path.name),
            used_names,
        )
        parts.append(
            _DocumentoBusta(
                filename=ap_filename,
                payload=ap_payload,
                maintype="application",
                subtype="pkcs7-mime",
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
            payload = self._read_document_payload(all_path)
            filename = self._nome_file_unico(
                self.nome_file_ministeriale(allegato.nome_file or all_path.name),
                used_names,
            )
            parts.append(
                _DocumentoBusta(
                    filename=filename,
                    payload=payload,
                    maintype="application",
                    subtype="pkcs7-mime",
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
                subtype="pkcs7-mime",
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
        if generator_class == "IntroduttiviSicid" and root_name in DATIATTO_V7_SICID_INTRO_ROOTS:
            return SICID_INTRO_V7_NS
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
        if generator_class == "IntroduttiviSicid" and self._datiatto_root_name() in DATIATTO_V7_SICID_INTRO_ROOTS:
            return MINISTERIAL_ATTI_V7_NS
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

    def _datiatto_allegati_namespace(self) -> str:
        atti_namespace = self._datiatto_atti_namespace()
        if atti_namespace == SIGP_ATTI_NS:
            return SIGP_ALLEGATI_NS
        if atti_namespace == CASSAZIONE_ATTI_NS:
            return CASSAZIONE_ALLEGATI_NS
        if atti_namespace == MINISTERIAL_ATTI_V7_NS:
            return MINISTERIAL_ALLEGATI_V2_NS
        return MINISTERIAL_ALLEGATI_NS

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

    def _catalog_key(self) -> str:
        return str(
            self.dati.datiatto_catalog_key
            or self._datiatto_extra().get("tipo_deposito_telematico_key")
            or ""
        ).strip()

    def _required_extra_text(self, key: str, label: str) -> str:
        value = self._extra_text(key)
        if not value:
            raise ValueError(f"{label} mancante: completa il dato prima di generare la busta.")
        return value

    def _extra_bool(self, key: str, *, default: bool | None = None) -> bool:
        raw = self._datiatto_extra().get(key)
        return self._extra_bool_from_value(raw, default=default)

    @staticmethod
    def _extra_bool_from_value(raw: Any, *, default: bool | None = None) -> bool:
        if isinstance(raw, bool):
            return raw
        text = str(raw or "").strip().casefold()
        if text in {"1", "true", "si", "sì", "yes"}:
            return True
        if text in {"0", "false", "no"}:
            return False
        if default is not None:
            return default
        raise ValueError("Valore vero/falso mancante: completa il dato prima di generare la busta.")

    def _append_riferimento_fascicolo(
        self,
        parent: etree._Element,
        *,
        namespace: str,
        name: str,
        numero_key: str,
        anno_key: str,
        label: str,
        required: bool = True,
        children_namespace: str | None = None,
    ) -> etree._Element | None:
        numero = self._extra_text(numero_key)
        anno = self._extra_text(anno_key)
        if not numero and not anno and not required:
            return None
        if not numero or not re.sub(r"\D+", "", numero):
            raise ValueError(f"Numero {label} mancante: completa il dato prima di generare la busta.")
        if not anno.isdigit():
            raise ValueError(f"Anno {label} mancante: completa il dato prima di generare la busta.")
        node = etree.SubElement(parent, f"{{{namespace}}}{name}")
        child_ns = children_namespace or namespace
        etree.SubElement(node, f"{{{child_ns}}}numero").text = re.sub(r"\D+", "", numero)
        etree.SubElement(node, f"{{{child_ns}}}anno").text = anno
        return node

    def _append_riferimento_provvedimento(
        self,
        parent: etree._Element,
        *,
        namespace: str,
        name: str,
        numero_key: str,
        anno_key: str,
        label: str,
        children_namespace: str | None = None,
    ) -> etree._Element:
        return self._append_riferimento_fascicolo(
            parent,
            namespace=namespace,
            name=name,
            numero_key=numero_key,
            anno_key=anno_key,
            label=label,
            required=True,
            children_namespace=children_namespace,
        )  # type: ignore[return-value]

    def _aggiungi_dati_appello(self, root: etree._Element, *, name: str = "DatiAppello") -> None:
        ns = self._datiatto_namespace()
        atti_ns = self._datiatto_atti_namespace()
        dati = etree.SubElement(root, f"{{{ns}}}{name}")
        self._append_riferimento_fascicolo(
            dati,
            namespace=atti_ns,
            name="Fascicolo",
            numero_key="precedente_fascicolo_numero",
            anno_key="precedente_fascicolo_anno",
            label="del fascicolo precedente",
            required=False,
        )
        self._append_riferimento_provvedimento(
            dati,
            namespace=atti_ns,
            name="Provvedimento",
            numero_key="precedente_provvedimento_numero",
            anno_key="precedente_provvedimento_anno",
            label="del provvedimento impugnato",
        )

    def _aggiungi_dati_riassunzione(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        atti_ns = self._datiatto_atti_namespace()
        dati = etree.SubElement(root, f"{{{ns}}}DatiProcedimento")
        self._append_riferimento_fascicolo(
            dati,
            namespace=atti_ns,
            name="numeroRicorso",
            numero_key="precedente_fascicolo_numero",
            anno_key="precedente_fascicolo_anno",
            label="del procedimento da riassumere",
        )
        etree.SubElement(dati, f"{{{atti_ns}}}dataProvvedimento").text = self._format_date_field(
            self._required_extra_text("data_precedente_provvedimento", "Data del provvedimento precedente"),
            "Data del provvedimento precedente",
        )
        if "Appello" in self._catalog_key():
            self._aggiungi_dati_appello(root)

    def _aggiungi_dati_decreto_opposto(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        dati = etree.SubElement(root, f"{{{ns}}}DatiDecreto")
        self._append_riferimento_fascicolo(
            dati,
            namespace=ns,
            name="causa",
            numero_key="decreto_causa_numero",
            anno_key="decreto_causa_anno",
            label="della causa del decreto",
            required=False,
            children_namespace=self._datiatto_atti_namespace(),
        )
        self._append_riferimento_provvedimento(
            dati,
            namespace=ns,
            name="decreto",
            numero_key="decreto_numero",
            anno_key="decreto_anno",
            label="del decreto ingiuntivo",
            children_namespace=self._datiatto_atti_namespace(),
        )
        etree.SubElement(dati, f"{{{ns}}}data").text = self._format_date_field(
            self._required_extra_text("decreto_data", "Data del decreto ingiuntivo"),
            "Data del decreto ingiuntivo",
        )

    def _aggiungi_tipo_decreto(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        key = self._catalog_key().casefold()
        if "sommaandconsegnabeni" in key:
            choice = "somma-beni"
        elif "onericondomin" in key:
            choice = "oneri-condominiali"
        elif "consegnabeni" in key:
            choice = "consegna-beni"
        else:
            choice = "somma"
        tipo = etree.SubElement(
            root,
            f"{{{ns}}}TipoDecreto",
            esecutivo="true" if self._extra_bool("decreto_esecutivo", default=False) else "false",
        )
        amount = float(self.dati.valore_causa or 0.0)
        etree.SubElement(tipo, f"{{{ns}}}{choice}").text = f"{amount:.2f}"

    def _aggiungi_dati_matrimonio(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        dati = etree.SubElement(root, f"{{{ns}}}DatiMatrimonio")
        fields = (
            ("ParteCivile", "matrimonio_parte_civile"),
            ("ParteReligiosa", "matrimonio_parte_religiosa"),
            ("NumeroMatrimonio", "matrimonio_numero"),
            ("RegistroMatrimonio", "matrimonio_registro"),
            ("SerieMatrimonio", "matrimonio_serie"),
            ("CittaMatrimonio", "matrimonio_citta"),
            ("ProvinciaMatrimonio", "matrimonio_provincia"),
            ("DataCelebrazioneMatrimonio", "matrimonio_data_celebrazione"),
            ("DataOmologazioneMatrimonio", "matrimonio_data_omologazione"),
            ("LuogoTrascrizioneMatrmonio", "matrimonio_luogo_trascrizione"),
            ("AnnoRegistrazione", "matrimonio_anno_registrazione"),
        )
        for xml_name, field_name in fields:
            value = self._extra_text(field_name)
            if not value:
                continue
            if xml_name.startswith("Data"):
                value = self._format_date_field(value, xml_name)
            etree.SubElement(dati, f"{{{ns}}}{xml_name}").text = value

    def _aggiungi_dati_divorzio(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        key = self._catalog_key().casefold()
        wrapper_name = "Congiunto" if "congiunt" in key else "Giudiziale"
        separation_name = (
            "SeparazioneConsensuale"
            if self._required_extra_text("separazione_tipo", "Tipo di separazione").casefold() == "consensuale"
            else "SeparazioneGiudiziale"
        )
        dati = etree.SubElement(root, f"{{{ns}}}DatiDivorzio")
        wrapper = etree.SubElement(dati, f"{{{ns}}}{wrapper_name}")
        separation = etree.SubElement(wrapper, f"{{{ns}}}{separation_name}")
        if separation_name == "SeparazioneGiudiziale":
            self._append_riferimento_fascicolo(
                separation,
                namespace=ns,
                name="Causa",
                numero_key="separazione_causa_numero",
                anno_key="separazione_causa_anno",
                label="della separazione",
                required=False,
                children_namespace=self._datiatto_atti_namespace(),
            )
            self._append_riferimento_provvedimento(
                separation,
                namespace=ns,
                name="Sentenza",
                numero_key="separazione_sentenza_numero",
                anno_key="separazione_sentenza_anno",
                label="della sentenza di separazione",
                children_namespace=self._datiatto_atti_namespace(),
            )

    def _aggiungi_modifica_condizioni_divorzio(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        dati = etree.SubElement(root, f"{{{ns}}}DatiDivorzioVG")
        sentenza = etree.SubElement(dati, f"{{{ns}}}Sentenza")
        atti_ns = self._datiatto_atti_namespace()
        etree.SubElement(sentenza, f"{{{atti_ns}}}numero").text = self._required_extra_text(
            "divorzio_sentenza_numero", "Numero della sentenza di divorzio"
        )
        etree.SubElement(sentenza, f"{{{atti_ns}}}anno").text = self._required_extra_text(
            "divorzio_sentenza_anno", "Anno della sentenza di divorzio"
        )
        etree.SubElement(root, f"{{{ns}}}DatiSeparazioneConsensuale")

    def _aggiungi_dati_successione(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        defunto = etree.SubElement(root, f"{{{ns}}}DatiDefunto")
        etree.SubElement(defunto, f"{{{ns}}}TipoAttoIntroduttivo").text = self._extra_text(
            "successione_tipo_atto", "Istanza"
        )
        etree.SubElement(defunto, f"{{{ns}}}Cognome").text = self._required_extra_text(
            "defunto_cognome", "Cognome del defunto"
        )
        etree.SubElement(defunto, f"{{{ns}}}Nome").text = self._required_extra_text(
            "defunto_nome", "Nome del defunto"
        )
        testamento = etree.SubElement(root, f"{{{ns}}}DatiTestamento")
        etree.SubElement(testamento, f"{{{ns}}}Tipo").text = self._extra_text(
            "testamento_tipo", "NonSpecificato"
        )
        istante = etree.SubElement(
            root,
            f"{{{ns}}}TipoIstante",
            parte=self._extra_text("successione_parte_istante", "Proprio"),
        )
        istante.text = self._extra_text("successione_istante", "Ricorrente")

    def _aggiungi_anagrafica_minorenni(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        etree.SubElement(root, f"{{{ns}}}AnagraficaMinorenni")

    def _aggiungi_soggetto_interessato(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        cognome = self._extra_text("soggetto_interessato_cognome")
        nome = self._extra_text("soggetto_interessato_nome")
        if not cognome or not nome:
            raise ValueError("Nome e cognome del soggetto interessato mancanti: completa i dati prima della busta.")
        subject = etree.SubElement(root, f"{{{ns}}}SoggettoInteressato")
        etree.SubElement(subject, f"{{{ns}}}Cognome").text = cognome
        etree.SubElement(subject, f"{{{ns}}}Nome").text = nome

    def _aggiungi_dati_immigrazione_v7(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        self._append_text_if_present(root, ns, "codVestanet", self._extra_text("codice_vestanet"))
        self._append_text_if_present(root, ns, "nazioneProvenienza", self._extra_text("nazione_provenienza"))
        etree.SubElement(root, f"{{{ns}}}CUI").text = self._required_extra_text("cui", "CUI")
        data_decreto = self._extra_text("data_decreto_immigrazione")
        if data_decreto:
            etree.SubElement(root, f"{{{ns}}}dataDecreto").text = self._format_date_field(
                data_decreto, "Data del decreto"
            )
        if self._datiatto_root_name() == "RicorsoReclamoSospensiva":
            self._aggiungi_dati_appello(root, name="DatiReclamo")

    def _aggiungi_dati_specifici_introduttivo_sicid(self, root: etree._Element) -> None:
        root_name = self._datiatto_root_name()
        if root_name in {"CitazioneAppello", "RicorsoAppello"}:
            self._aggiungi_dati_appello(root)
        elif root_name == "CitazioneInRiassunzione":
            self._aggiungi_dati_riassunzione(root)
        elif root_name in {"OpposizioneDecretoIngiuntivo", "RicorsoOpposizioneDecretoIngiuntivo"}:
            self._aggiungi_dati_decreto_opposto(root)
        elif root_name == "RicorsoDecretoIngiuntivo":
            self._aggiungi_tipo_decreto(root)
        elif root_name in {"RicorsoSeparazione", "RicorsoDivorzio", "ModificaCondizioniSeparazione", "ModificaCondizioniDivorzio"}:
            self._aggiungi_dati_matrimonio(root)
            if root_name == "RicorsoDivorzio":
                self._aggiungi_dati_divorzio(root)
            elif root_name == "ModificaCondizioniSeparazione":
                self._aggiungi_dati_divorzio(root)
            elif root_name == "ModificaCondizioniDivorzio":
                self._aggiungi_modifica_condizioni_divorzio(root)
        elif root_name == "Successioni":
            self._aggiungi_dati_successione(root)
        elif root_name == "RicorsoMinorenni":
            self._aggiungi_anagrafica_minorenni(root)
        elif root_name == "RicorsoMinorenniSoggettoInteressato":
            self._aggiungi_soggetto_interessato(root)
        elif root_name in DATIATTO_V7_SICID_INTRO_ROOTS:
            self._aggiungi_dati_immigrazione_v7(root)

    def _aggiungi_altri_dati_sigp(self, root: etree._Element) -> None:
        etree.SubElement(root, f"{{{self._datiatto_namespace()}}}AltriDati")

    def _aggiungi_sanzione_opposta_sigp(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        key_suffix = self._catalog_key_suffix()
        numero = self._required_extra_text("osa_numero_verbale", "Numero del verbale o della sanzione")
        data = self._format_date_field(
            self._required_extra_text("osa_data_verbale", "Data del verbale o della sanzione"),
            "Data del verbale o della sanzione",
        )
        motivazione = self._extra_text("osa_motivazione", "Altro")
        sanzione = etree.SubElement(root, f"{{{ns}}}SanzioneOpposta")
        if key_suffix == "OSA_CartellaEsattoriale":
            riferimento = self._required_extra_text("osa_riferimento_cartella", "Riferimento della cartella")
            if len(riferimento) != 17:
                raise ValueError("Riferimento della cartella non valido: deve contenere 17 caratteri.")
            verbale = etree.SubElement(sanzione, f"{{{ns}}}Cartella", RiferimentoCartella=riferimento)
        elif key_suffix == "OSA_IngiunzionePagamento":
            riferimento = self._required_extra_text("osa_riferimento_ordinanza", "Riferimento dell'ordinanza")
            verbale = etree.SubElement(sanzione, f"{{{ns}}}OrdinanzaDiIngiunzione", RiferimentoOrdinanza=riferimento)
        else:
            verbale = etree.SubElement(sanzione, f"{{{ns}}}Verbale")
        etree.SubElement(verbale, f"{{{SIGP_TIPI_NS}}}NumeroVerbale").text = numero
        etree.SubElement(verbale, f"{{{SIGP_TIPI_NS}}}DataVerbale").text = data
        etree.SubElement(verbale, f"{{{SIGP_TIPI_NS}}}Motivazione").text = motivazione

    def _aggiungi_dati_specifici_introduttivo_sigp(self, root: etree._Element) -> None:
        root_name = self._datiatto_root_name()
        if root_name == "Citazione":
            self._aggiungi_altri_dati_sigp(root)
        elif root_name == "CitazioneInRiassunzione":
            self._aggiungi_dati_riassunzione(root)
            self._aggiungi_altri_dati_sigp(root)
        elif root_name == "OpposizioneDecretoIngiuntivo":
            self._aggiungi_dati_decreto_opposto(root)
            self._aggiungi_altri_dati_sigp(root)
        elif root_name in {"Ricorso", "OSA"}:
            self._aggiungi_altri_dati_sigp(root)
            if root_name == "OSA":
                self._aggiungi_sanzione_opposta_sigp(root)
        elif root_name == "RicorsoDecretoIngiuntivo":
            self._aggiungi_tipo_decreto(root)

    def _aggiungi_dati_specifici_corso_causa_sigp(self, root: etree._Element) -> None:
        root_name = self._datiatto_root_name()
        if root_name == "CostituzioneSemplice":
            self._aggiungi_modifiche_anagrafica_base(root)
        elif root_name == "IstanzaGenerica":
            key_suffix = self._catalog_key_suffix()
            event_name = {
                "IstanzaExArt186Bis": "IstanzaExArt186Bis",
                "IstanzaExArt186Ter": "IstanzaExArt186Ter",
                "IstanzaExArt186Quater": "IstanzaExArt186Quater",
                "RichiestaEsecutorietaExArt647": "IstanzaRichiestaEsecutorietaExArt647",
                "IstanzaGenerica": "IstanzaGenerica",
            }.get(key_suffix)
            if not event_name:
                raise ValueError("Tipo di istanza non riconosciuto: seleziona nuovamente il deposito.")
            deposito = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}deposito")
            etree.SubElement(deposito, f"{{{SIGP_EVENTI_PARTE_NS}}}{event_name}")

    def _catalog_key_suffix(self) -> str:
        key = self._catalog_key()
        return key.rsplit("::", 1)[-1] if "::" in key else key

    def _aggiungi_modifiche_anagrafica_sicid(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        source = self._anagrafica_procedimento_node()
        partecipanti = source.xpath("./*[local-name()='Partecipanti']")
        soggetti = source.xpath("./*[local-name()='Soggetti']")
        if not partecipanti or not soggetti:
            raise ValueError(
                "Dati di cliente, controparte e avvocato incompleti: completa il fascicolo prima di generare la busta."
            )
        modifiche = etree.SubElement(root, f"{{{ns}}}ModificheAnagrafica")
        costituzione = etree.SubElement(modifiche, f"{{{ns}}}CostituzioneParti")
        partecipanti_costituzione = deepcopy(partecipanti[0])
        for participant in list(partecipanti_costituzione):
            if etree.QName(participant).localname not in {"Parte", "Chiamato"}:
                partecipanti_costituzione.remove(participant)
        if not list(partecipanti_costituzione):
            raise ValueError("Cliente da costituire mancante: completa il fascicolo prima di generare la busta.")
        costituzione.append(partecipanti_costituzione)
        costituzione.append(deepcopy(soggetti[0]))

    def _aggiungi_nomina_ctp_sicid(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        source = self._anagrafica_procedimento_node()
        participants = source.xpath("./*[local-name()='Partecipanti']/*[local-name()='Parte']")
        if not participants:
            raise ValueError("Cliente da rappresentare mancante per la nomina del consulente tecnico di parte.")
        parte = deepcopy(participants[0])
        parte.tag = f"{{{ns}}}Parte"
        parte_id = self._xml_id(str(parte.get("ID") or ""), "parte_ctp_1")
        parte.set("ID", parte_id)
        root.append(parte)
        nomina = etree.SubElement(root, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}NominaConsulenteParte")
        etree.SubElement(nomina, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}parte", ref=parte_id)
        etree.SubElement(nomina, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}consulente").text = self._extra_text(
            "consulente_tecnico", "Vedi atto"
        )

    def _aggiungi_evento_istanza_sicid(
        self,
        parent: etree._Element,
        *,
        event_name: str,
        key_suffix: str,
    ) -> None:
        event = etree.SubElement(parent, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}{event_name}")
        if event_name == "IstanzaFissazioneUdienzaCollegamentiAudioVisivi":
            etree.SubElement(event, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}note").text = (
                "Istanza di fissazione udienza con collegamenti audiovisivi"
            )
        elif event_name == "IstanzaRevocaUdienzaCollegamentiAudioVisivi":
            etree.SubElement(event, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}note").text = (
                "Istanza di revoca della fissazione udienza con collegamenti audiovisivi"
            )
        elif event_name == "NoteScrittePC":
            etree.SubElement(event, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}discussioneOrale").text = (
                "true" if key_suffix == "NoteScrittePC_DiscussioneOrale" else "false"
            )

    def _aggiungi_istanza_generica_sicid(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        key_suffix = self._catalog_key_suffix()
        if key_suffix == "RichiestaFormulaEsecutiva":
            etree.SubElement(root, f"{{{ns}}}note").text = "Richiesta di formula esecutiva: vedi istanza"
        deposito = etree.SubElement(root, f"{{{ns}}}deposito")
        event_name = SICID_PARTE_ISTANZA_EVENT_BY_KEY.get(key_suffix)
        if event_name:
            self._aggiungi_evento_istanza_sicid(
                deposito,
                event_name=event_name,
                key_suffix=key_suffix,
            )

    def _aggiungi_ricorso_generico_sicid(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        key_suffix = self._catalog_key_suffix()
        deposito = etree.SubElement(root, f"{{{ns}}}deposito")
        event_name = SICID_PARTE_RICORSO_EVENT_BY_KEY.get(key_suffix)
        if event_name:
            etree.SubElement(deposito, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}{event_name}")

    def _aggiungi_documenti_richiesti_sicid(self, root: etree._Element) -> None:
        event_name = SICID_PARTE_DOCUMENT_EVENT_BY_KEY.get(self._catalog_key_suffix())
        if not event_name:
            return
        documenti = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}documenti")
        etree.SubElement(documenti, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}{event_name}")

    def _aggiungi_memorie_cartabia_sicid(self, root: etree._Element) -> None:
        key_suffix = self._catalog_key_suffix()
        event_names = {
            "Memoria171ter1": "Memoria171ter1",
            "Repliche171ter2": "Repliche171ter2",
            "Controrepliche171ter3": "Controrepliche171ter3",
            "IstanzaAccoglimentoDomanda183ter": "IstanzaAccoglimentoDomanda183ter",
            "IstanzaRigettoDomanda183quater": "IstanzaRigettoDomanda183quater",
        }
        event_name = event_names.get(key_suffix)
        if not event_name:
            return
        istanze = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}istanze")
        etree.SubElement(istanze, f"{{{MINISTERIAL_EVENTI_PARTE_NS}}}{event_name}")

    def _aggiungi_dati_specifici_parte_sicid(self, root: etree._Element) -> None:
        root_name = self._datiatto_root_name()
        if root_name in SICID_PARTE_MODIFICHE_ANAGRAFICA_REQUIRED_ROOTS:
            self._aggiungi_modifiche_anagrafica_sicid(root)
        if root_name == "AttoCostituzioneNuovoAvvocato":
            etree.SubElement(root, f"{{{self._datiatto_atti_namespace()}}}domanda")
        if root_name == "Reclamo":
            key_suffix = self._catalog_key_suffix()
            tipo_parte = {
                "ReclamoRicorrente": "Ricorrente",
                "ReclamoResistente": "Resistente",
                "ReclamoIntervenuto": "Intervenuto",
            }.get(key_suffix)
            if not tipo_parte:
                raise ValueError("Ruolo nel reclamo mancante: scegli ricorrente, resistente o intervenuto.")
            etree.SubElement(root, f"{{{self._datiatto_namespace()}}}TipoParte").text = tipo_parte
        elif root_name == "IstanzaGenerica":
            self._aggiungi_istanza_generica_sicid(root)
        elif root_name == "Ricorso":
            self._aggiungi_ricorso_generico_sicid(root)
        elif root_name == "MemoriaGenerica":
            etree.SubElement(root, f"{{{self._datiatto_namespace()}}}istanze")
        elif root_name == "Preverbale":
            etree.SubElement(
                root,
                f"{{{self._datiatto_namespace()}}}accesso",
                altraParte="true" if self._extra_bool("preverbale_visibile_controparte", default=True) else "false",
            )
        elif root_name == "NominaCTPexart87":
            self._aggiungi_nomina_ctp_sicid(root)
        elif root_name == "ProduzioneDocumentiRichiesti":
            self._aggiungi_documenti_richiesti_sicid(root)
        elif root_name == "MemorieCartabia":
            self._aggiungi_memorie_cartabia_sicid(root)

    def _aggiungi_deposito_semplice_ministeriale(self, root: etree._Element) -> None:
        generator_class = self._datiatto_generator_class()
        key_suffix = self._catalog_key_suffix()
        event_name = DEPOSITO_SEMPLICE_EVENT_BY_GENERATOR_AND_KEY.get(generator_class, {}).get(key_suffix)
        if not event_name:
            raise ValueError(
                "Tipo di deposito non riconosciuto per il professionista incaricato: seleziona nuovamente il tipo di atto."
            )
        if generator_class == "Professionista":
            event_namespace = MINISTERIAL_EVENTI_PROFESSIONISTA_NS
        elif generator_class == "Professionista_SIGP":
            event_namespace = SIGP_EVENTI_PROFESSIONISTA_NS
        else:
            event_namespace = SIECIC_EVENTI_NS
        deposito = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}deposito")
        attributes = {}
        if event_name == "attoNonCodificato":
            attributes["descrizione"] = str(self.dati.tipo_atto or key_suffix).strip()
        if generator_class == "DelSiecicEsecuzioni" and event_name in {
            "avvisoVendita",
            "depositoPrezzo",
            "istanzaRevocaDecadenzaAggiudicatario",
            "verbaleAggiudicazione",
        }:
            attributes["lotto"] = self._lotto_delegato()
        etree.SubElement(deposito, f"{{{event_namespace}}}{event_name}", **attributes)

    def _lotto_delegato(self) -> str:
        lotto = self._required_extra_text("lotto_numero", "Numero del lotto")
        if not lotto.isdigit() or int(lotto) <= 0:
            raise ValueError("Numero del lotto non valido: inserisci un numero maggiore di zero.")
        return str(int(lotto))

    def _aggiungi_dati_specifici_delegato_siecic(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        root_name = self._datiatto_root_name()
        if root_name == "MinutaDecreto":
            etree.SubElement(root, f"{{{ns}}}lotto").text = self._lotto_delegato()
        elif root_name == "ProgettoDistribuzione":
            dispositivo = etree.SubElement(root, f"{{{ns}}}dispositivo")
            etree.SubElement(dispositivo, f"{{{SIECIC_EVENTI_NS}}}accoglimentoPianoRiparto")
        elif root_name == "AggiudicazioneLotto":
            offerente_cf = re.sub(
                r"[^A-Za-z0-9]",
                "",
                self._required_extra_text("aggiudicatario_codice_fiscale", "Codice fiscale dell'aggiudicatario"),
            ).upper()
            etree.SubElement(root, f"{{{ns}}}Lotto").text = self._lotto_delegato()
            senza_incanto = etree.SubElement(root, f"{{{ns}}}SenzaIncanto")
            etree.SubElement(senza_incanto, f"{{{ns}}}ImportoAumento").text = self._format_decimal_field(
                self._required_extra_text("aggiudicazione_importo_aumento", "Importo minimo in aumento"),
                "Importo minimo in aumento",
            )
            offerta = etree.SubElement(senza_incanto, f"{{{ns}}}Offerte")
            etree.SubElement(offerta, f"{{{SIECIC_TIPIBASE_NS}}}importo").text = self._format_decimal_field(
                self._required_extra_text("aggiudicazione_importo_offerta", "Importo dell'offerta"),
                "Importo dell'offerta",
            )
            etree.SubElement(offerta, f"{{{ns}}}Cauzione").text = self._format_decimal_field(
                self._required_extra_text("aggiudicazione_cauzione", "Cauzione dell'offerta"),
                "Cauzione dell'offerta",
            )
            etree.SubElement(offerta, f"{{{ns}}}Spese", **{f"{{{XSI_NS}}}nil": "true"})
            offerente = etree.SubElement(offerta, f"{{{ns}}}Offerente")
            etree.SubElement(offerente, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cognome").text = self._required_extra_text(
                "aggiudicatario_cognome", "Cognome o denominazione dell'aggiudicatario"
            )
            nome = self._extra_text("aggiudicatario_nome")
            if nome:
                etree.SubElement(offerente, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}nome").text = nome
            etree.SubElement(offerente, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}codiceFiscale").text = offerente_cf
            etree.SubElement(senza_incanto, f"{{{ns}}}Aggiudicatario", codiceFiscale=offerente_cf)
            etree.SubElement(root, f"{{{ns}}}TermineConguaglio").text = self._format_date_field(
                self._required_extra_text("aggiudicazione_termine_conguaglio", "Termine per il conguaglio"),
                "Termine per il conguaglio",
            )

    def _partecipanti_e_soggetti_costituzione(self) -> tuple[etree._Element, etree._Element]:
        source = self._anagrafica_procedimento_node()
        partecipanti = source.xpath("./*[local-name()='Partecipanti']")
        soggetti = source.xpath("./*[local-name()='Soggetti']")
        if not partecipanti or not soggetti:
            raise ValueError(
                "Dati di cliente e avvocato incompleti: completa il fascicolo prima di generare la busta."
            )
        partecipanti_costituzione = deepcopy(partecipanti[0])
        for participant in list(partecipanti_costituzione):
            if etree.QName(participant).localname not in {"Parte", "Chiamato"}:
                partecipanti_costituzione.remove(participant)
        if not list(partecipanti_costituzione):
            raise ValueError("Cliente da costituire mancante: completa il fascicolo prima di generare la busta.")
        return partecipanti_costituzione, deepcopy(soggetti[0])

    def _aggiungi_modifiche_anagrafica_base(self, root: etree._Element) -> None:
        partecipanti, soggetti = self._partecipanti_e_soggetti_costituzione()
        modifiche = etree.SubElement(root, f"{{{self._datiatto_atti_namespace()}}}ModificheAnagrafica")
        modifiche.append(partecipanti)
        modifiche.append(soggetti)

    def _aggiungi_riferimento_soggetto_siecic(
        self,
        parent: etree._Element,
        name: str,
        codice_fiscale: str,
    ) -> etree._Element:
        clean = re.sub(r"[^A-Za-z0-9]", "", str(codice_fiscale or "")).upper()
        if not clean:
            raise ValueError(f"Codice fiscale {name} mancante: completa il dato prima di generare la busta.")
        return etree.SubElement(parent, f"{{{SIECIC_TIPIBASE_NS}}}{name}", codiceFiscale=clean)

    def _aggiungi_precisazione_credito_siecic(self, root: etree._Element) -> None:
        capitale = self._required_extra_text("credito_capitale", "Capitale del credito")
        importo = self._extra_text("credito_importo", capitale)
        data_decorrenza = self._format_date_field(
            self._required_extra_text("credito_data_decorrenza", "Data di decorrenza del credito"),
            "Data di decorrenza del credito",
        )
        data_aggiornamento = self._extra_text("credito_data_aggiornamento")
        credito = etree.SubElement(root, f"{{{SIECIC_TIPIBASE_NS}}}precisazioneCredito")
        etree.SubElement(credito, f"{{{SIECIC_TIPIBASE_NS}}}capitale").text = self._format_decimal_field(
            capitale, "Capitale del credito"
        )
        etree.SubElement(
            credito,
            f"{{{SIECIC_TIPIBASE_NS}}}naturaPrivilegio",
            **{f"{{{XSI_NS}}}nil": "true"},
        )
        etree.SubElement(credito, f"{{{SIECIC_TIPIBASE_NS}}}importo").text = self._format_decimal_field(
            importo, "Importo del credito"
        )
        aggiornamento = etree.SubElement(credito, f"{{{SIECIC_TIPIBASE_NS}}}dataAggiornamento")
        if data_aggiornamento:
            aggiornamento.text = self._format_date_field(data_aggiornamento, "Data aggiornamento del credito")
        else:
            aggiornamento.set(f"{{{XSI_NS}}}nil", "true")
        etree.SubElement(credito, f"{{{SIECIC_TIPIBASE_NS}}}dataDecorrenza").text = data_decorrenza

    def _aggiungi_atto_generico_siecic(self, root: etree._Element) -> None:
        generator_class = self._datiatto_generator_class()
        key_suffix = self._catalog_key_suffix()
        event_name = SIECIC_PARTE_ATTO_GENERICO_EVENT_BY_GENERATOR_AND_KEY.get(generator_class, {}).get(key_suffix)
        if not event_name:
            raise ValueError("Tipo di atto in corso causa non riconosciuto: seleziona nuovamente il deposito.")
        deposito = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}deposito")
        attributes = {"descrizione": str(self.dati.tipo_atto or key_suffix).strip()} if event_name == "attoNonCodificato" else {}
        event = etree.SubElement(deposito, f"{{{SIECIC_EVENTI_NS}}}{event_name}", **attributes)
        if event_name in {"depositoIstanza41TUB", "depositoRinunciaEsecuzione", "depositoRinunciaMandato", "depositoMemorie"}:
            subjects = self._anagrafica_subjects()
            etree.SubElement(
                event,
                f"{{{SIECIC_EVENTI_NS}}}parte",
                codiceFiscale=subjects["parte_cf"],
            )

    def _aggiungi_dati_specifici_parte_siecic(self, root: etree._Element) -> None:
        generator_class = self._datiatto_generator_class()
        root_name = self._datiatto_root_name()
        key_suffix = self._catalog_key_suffix()
        subjects = self._anagrafica_subjects()
        if root_name == "AttoCostituzioneAvvocato":
            self._aggiungi_modifiche_anagrafica_base(root)
            deposito = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}deposito")
            etree.SubElement(deposito, f"{{{SIECIC_EVENTI_NS}}}costituzioneAvvocato")
        elif root_name == "AttoGenerico":
            self._aggiungi_atto_generico_siecic(root)
        elif root_name == "AttoGenericoCCIPU":
            deposito = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}deposito")
            etree.SubElement(deposito, f"{{{SIECIC_EVENTI_NS}}}costituzioneCreditore")
        elif root_name == "NotaDepositoCCI":
            dispositivo = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}dispositivo")
            etree.SubElement(dispositivo, f"{{{SIECIC_EVENTI_CRISI_NS}}}AttoNonCodificato")
        elif root_name == "AttoIntervento":
            self._aggiungi_modifiche_anagrafica_base(root)
            self._aggiungi_precisazione_credito_siecic(root)
        elif root_name in {"IstanzaAssegnazione", "IstanzaDistribuzione"}:
            self._aggiungi_riferimento_soggetto_siecic(root, "creditore", subjects["parte_cf"])
        elif root_name == "NotaPrecisazioneCredito":
            self._aggiungi_riferimento_soggetto_siecic(root, "creditore", subjects["parte_cf"])
            self._aggiungi_precisazione_credito_siecic(root)
        elif root_name == "RinunciaDebitori":
            self._aggiungi_riferimento_soggetto_siecic(root, "creditore", subjects["parte_cf"])
            self._aggiungi_riferimento_soggetto_siecic(root, "debitore", subjects["controparte_cf"])
        elif root_name == "Opposizione":
            self._aggiungi_modifiche_anagrafica_base(root)
            deposito = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}deposito")
            etree.SubElement(deposito, f"{{{SIECIC_EVENTI_NS}}}{key_suffix}")
            etree.SubElement(root, f"{{{self._datiatto_namespace()}}}IstanzaSospensione").text = (
                "true" if self._extra_bool("opposizione_istanza_sospensione", default=False) else "false"
            )

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
        return (
            self._datiatto_root_name() == "ProgettoDistribuzione"
            and self._datiatto_generator_class() != "DelSiecicEsecuzioni"
        )

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

    def _contributo_unificato_dati(self) -> tuple[str, float]:
        contribution = self.dati.contributo_unificato if isinstance(self.dati.contributo_unificato, dict) else {}
        mode = str(contribution.get("mode") or "").strip().casefold()
        if not self.dati.contributo_unificato_richiesto and not mode:
            return "", 0.0
        if self.dati.contributo_unificato_richiesto and not bool(contribution.get("resolved")):
            raise ValueError(
                str(contribution.get("blocking_message") or "").strip()
                or "Contributo unificato non definito: indica se il deposito è esente, pagato o prenotato a debito."
            )
        if mode not in {"esente", "pagato", "prenotato_a_debito"}:
            if self.dati.contributo_unificato_richiesto:
                raise ValueError(
                    "Contributo unificato non definito: indica se il deposito è esente, pagato o prenotato a debito."
                )
            return "", 0.0
        amount = 0.0
        if mode == "pagato":
            try:
                amount = float(contribution.get("importo"))
            except (TypeError, ValueError):
                amount = 0.0
            if amount <= 0:
                raise ValueError(
                    "Importo del contributo unificato mancante: inserisci l’importo prima di generare la busta."
                )
        if self.dati.contributo_unificato_xml_mode == "cassazione_integrazione_spese" and mode == "esente":
            raise ValueError(
                "Questo deposito integra spese già dovute: indica l’importo pagato o prenotato a debito."
            )
        return mode, amount

    @staticmethod
    def _append_importo_contributo(
        parent: etree._Element,
        *,
        namespace: str,
        amount: float,
        debt: bool,
        cassazione: bool = False,
    ) -> etree._Element:
        attributes = {"debito": "true" if debt else "false"}
        if cassazione:
            attributes["tipoContributoUnificato"] = "Determinato" if amount > 0 else "Indeterminato"
        node = etree.SubElement(parent, f"{{{namespace}}}Importo", **attributes)
        node.text = f"{amount:.2f}"
        return node

    def _aggiungi_istanza_vendita_ministeriale(self, root: etree._Element) -> None:
        subjects = self._anagrafica_subjects()
        creditore_cf = self._extra_text("procedente_codice_fiscale") or subjects["parte_cf"]
        if not creditore_cf:
            raise ValueError("Codice fiscale del creditore mancante per l’istanza di vendita.")
        etree.SubElement(
            root,
            f"{{{SIECIC_TIPIBASE_NS}}}creditore",
            codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", creditore_cf).upper(),
        )
        mode, amount = self._contributo_unificato_dati()
        if mode in {"pagato", "prenotato_a_debito"}:
            contribution = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}contributoUnificato")
            self._append_importo_contributo(
                contribution,
                namespace=self._datiatto_atti_namespace(),
                amount=amount,
                debt=mode == "prenotato_a_debito",
            )

    @staticmethod
    def _append_cassazione_esenzione(parent: etree._Element, name: str) -> None:
        expense = etree.SubElement(parent, f"{{{CASSAZIONE_ATTI_NS}}}{name}")
        etree.SubElement(expense, f"{{{CASSAZIONE_ATTI_NS}}}Esente").text = "true"

    def _aggiungi_spese_giustizia_cassazione(self, root: etree._Element, *, integration: bool) -> None:
        mode, amount = self._contributo_unificato_dati()
        if not mode:
            return
        spese = etree.SubElement(root, f"{{{self._datiatto_namespace()}}}speseGiustizia")
        contribution = etree.SubElement(spese, f"{{{CASSAZIONE_ATTI_NS}}}ContributoUnificato")
        if mode == "esente" and not integration:
            etree.SubElement(contribution, f"{{{CASSAZIONE_ATTI_NS}}}Esente").text = "true"
        else:
            self._append_importo_contributo(
                contribution,
                namespace=CASSAZIONE_ATTI_NS,
                amount=amount,
                debt=mode == "prenotato_a_debito",
                cassazione=True,
            )
        if integration:
            for name in (
                "integrazione_69_2009_art_13_co_2_bis_tu",
                "diritti_registrazione_ruolo_tu_art_30",
                "notifica_avvocati_art_34_tu",
            ):
                expense = etree.SubElement(spese, f"{{{CASSAZIONE_ATTI_NS}}}{name}")
                self._append_importo_contributo(
                    expense,
                    namespace=CASSAZIONE_ATTI_NS,
                    amount=0.0,
                    debt=False,
                )
        else:
            for name in (
                "integrazione_69_2009_art_13_co_2_bis_tu",
                "diritti_registrazione_ruolo_tu_art_30",
                "notifica_avvocati_art_34_tu",
            ):
                self._append_cassazione_esenzione(spese, name)

    def _aggiungi_richiesta_visibilita_ministeriale(self, root: etree._Element) -> None:
        ns = self._datiatto_namespace()
        at_ns = SIGP_ANAGRAFICHE_NS if "SIGP" in self._datiatto_generator_class() else MINISTERIAL_ANAGRAFICHE_NS
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

    def _pignoramento_terzi(self) -> list[dict[str, Any]]:
        raw = self._datiatto_extra().get("terzi")
        terzi = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        if not terzi:
            legacy = self._datiatto_extra().get("terzo")
            if isinstance(legacy, dict) and legacy:
                terzi = [legacy]
        if not terzi:
            raise ValueError("Terzi pignorati mancanti: inserisci almeno un terzo prima di generare la busta.")
        codici = [
            re.sub(r"[^A-Za-z0-9]", "", str(item.get("codice_fiscale") or item.get("codiceFiscale") or "")).upper()
            for item in terzi
        ]
        if any(not codice for codice in codici):
            raise ValueError("Codice fiscale di un terzo pignorato mancante.")
        if len(codici) != len(set(codici)):
            raise ValueError("Lo stesso terzo pignorato è stato inserito più volte.")
        return terzi

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
                bene.get("descrizione") or ""
            ).strip()
            if not node.xpath("./*[local-name()='descrizione']/text()[normalize-space()]"):
                raise ValueError(f"Descrizione del bene pignorato {index} mancante.")
            if is_immobile:
                indirizzo_data = bene.get("indirizzo") if isinstance(bene.get("indirizzo"), dict) else {}
                catastali = bene.get("dati_catastali") if isinstance(bene.get("dati_catastali"), dict) else {}
                required = {
                    "indirizzo": indirizzo_data.get("via"),
                    "CAP": indirizzo_data.get("cap"),
                    "comune": indirizzo_data.get("localita"),
                    "provincia": indirizzo_data.get("provincia"),
                    "catasto": bene.get("catasto"),
                    "sezione catastale": catastali.get("sezione"),
                    "foglio": catastali.get("foglio"),
                    "particella": catastali.get("particella"),
                    "classe": bene.get("classe"),
                }
                missing = [label for label, value in required.items() if not str(value or "").strip()]
                if missing:
                    raise ValueError(f"Dati del bene immobile {index} mancanti: {', '.join(missing)}.")
                catasto = str(bene.get("catasto") or "").strip().upper()
                if catasto not in {"NCEU", "NCT"}:
                    raise ValueError(f"Catasto del bene immobile {index} non valido: seleziona NCEU o NCT.")
                indirizzo = etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}indirizzo")
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}via").text = str(
                    indirizzo_data.get("via")
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cap").text = str(
                    indirizzo_data.get("cap")
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}localita").text = str(
                    indirizzo_data.get("localita")
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}provincia").text = str(
                    indirizzo_data.get("provincia")
                ).strip()
                etree.SubElement(indirizzo, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}stato").text = "IT"
                etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}catasto").text = str(
                    catasto
                ).strip()
                dati_catastali = etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}datiCatastali")
                etree.SubElement(dati_catastali, f"{{{SIECIC_TIPIBASE_NS}}}sezione").text = str(
                    catastali.get("sezione")
                ).strip()
                etree.SubElement(dati_catastali, f"{{{SIECIC_TIPIBASE_NS}}}foglio").text = str(
                    catastali.get("foglio")
                ).strip()
                etree.SubElement(dati_catastali, f"{{{SIECIC_TIPIBASE_NS}}}particella").text = str(
                    catastali.get("particella")
                ).strip()
                classe = etree.SubElement(
                    node,
                    f"{{{SIECIC_TIPIBASE_NS}}}classe",
                    classato="true" if self._extra_bool_from_value(bene.get("classato"), default=True) else "false",
                )
                classe.text = str(bene.get("classe")).strip().upper()
            valore = bene.get("valore") or bene.get("stima") or ""
            if not is_immobile:
                etree.SubElement(node, f"{{{SIECIC_TIPIBASE_NS}}}valoreBene").text = self._format_decimal_field(
                    valore, "Valore bene pignorato"
                )
        return bene_ids

    def _aggiungi_pignoramento_estensione_anagrafica(self, root: etree._Element, bene_ids: list[str]) -> None:
        ns = self._datiatto_namespace()
        subjects = self._anagrafica_subjects()
        # I riferimenti devono usare gli stessi codici fiscali presenti
        # nell'AnagraficaProcedimento, altrimenti i vincoli XSD key/keyref falliscono.
        procedente_cf = subjects["parte_cf"] or self._extra_text("procedente_codice_fiscale")
        debitore_cf = subjects["controparte_cf"] or self._extra_text("debitore_codice_fiscale")
        avvocato_cf = subjects["avvocato_cf"] or self._extra_text("avvocato_codice_fiscale")
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
                f"{{{ns}}}dirittiReali",
                quota="1.0",
                stato="Inventariato",
                stima=self._format_decimal_field(
                    self._datiatto_extra().get("stima_diritto"),
                    "Stima diritto pignorato",
                ),
            )
            diritto.text = "1"

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
            required = {
                "cognome o denominazione": custode.get("cognome"),
                "codice fiscale": custode.get("codiceFiscale") or custode.get("codice_fiscale"),
                "indirizzo": custode.get("via"),
                "CAP": custode.get("cap"),
                "comune": custode.get("localita"),
                "provincia": custode.get("provincia"),
            }
            missing = [label for label, value in required.items() if not str(value or "").strip()]
            if missing:
                raise ValueError("Dati del custode mancanti: " + ", ".join(missing) + ".")
            custode_node = etree.SubElement(presso, f"{{{ns}}}Custode")
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}via").text = str(
                custode.get("via")
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cap").text = str(
                custode.get("cap")
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}localita").text = str(
                custode.get("localita")
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}provincia").text = str(
                custode.get("provincia")
            ).strip()
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}stato").text = "IT"
            etree.SubElement(custode_node, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cognome").text = str(
                custode.get("cognome")
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
            for index, terzo in enumerate(self._pignoramento_terzi(), start=1):
                terzo_cf = str(terzo.get("codice_fiscale") or terzo.get("codiceFiscale") or "").strip()
                dati_terzo = etree.SubElement(presso, f"{{{ns}}}DatiTerzo", codiceFiscale=re.sub(r"[^A-Za-z0-9]", "", terzo_cf).upper())
                data_precetto = terzo.get("data_notifica_precetto") or self._datiatto_extra().get("data_notifica_precetto")
                if data_precetto:
                    etree.SubElement(dati_terzo, f"{{{ns}}}dataNotificaPrecetto").text = self._format_date_field(
                        data_precetto, f"Data notifica precetto del terzo {index}"
                    )
                etree.SubElement(dati_terzo, f"{{{ns}}}dataNotificaPignoramento").text = self._format_date_field(
                    terzo.get("data_notifica_pignoramento") or self._datiatto_extra().get("data_notifica_pignoramento"),
                    f"Data notifica pignoramento del terzo {index}",
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
        tipologia_raw = str(titolo.get("tipologia") or "").strip()
        tipologie = {
            "sentenza": "1",
            "sentenza di condanna i grado": "1",
            "sentenza di condanna ii grado": "2",
            "decreto ingiuntivo": "3",
            "cambiale": "4",
            "ordinanza": "5",
            "ordinanza in corso di causa (art.186 quater cpc)": "6",
            "ingiunzione in corso di causa (art. 183 ter cpc)": "7",
            "omologa separazione consensuale": "8",
            "verbale di conciliazione": "9",
            "cartella esattoriale": "10",
            "assegno": "11",
            "contratto di finanziamento": "12",
            "contratto di vendita": "13",
            "contratto di sovvenzione": "14",
            "polizza di pegno": "15",
            "fattura": "16",
            "mutuo fondiario": "17",
            "mutuo ipotecario": "18",
            "atto notarile": "19",
            "lodo arbitrale": "20",
            "lodo arbritrale": "20",
            "scrittura contabile autenticata": "21",
            "atto da specificare": "99",
        }
        tipologia = tipologie.get(tipologia_raw.casefold(), tipologia_raw)
        if tipologia not in {*(str(index) for index in range(1, 22)), "99"}:
            raise ValueError(
                "Tipologia del titolo esecutivo non valida: seleziona una voce prevista dalla tabella ministeriale."
            )
        esecutivo = etree.SubElement(
            titolo_node,
            f"{{{SIECIC_TIPIBASE_NS}}}titoloEsecutivo",
            tipologia=tipologia,
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
        anagrafica = self._anagrafica_procedimento_node()
        if self._pignoramento_branch() == "mobiliare_presso_terzi":
            participants = anagrafica.xpath("./*[local-name()='Partecipanti']")
            if not participants:
                raise ValueError("Partecipanti mancanti nell'anagrafica del pignoramento.")
            for index, terzo in enumerate(self._pignoramento_terzi(), start=1):
                cf = re.sub(r"[^A-Za-z0-9]", "", str(terzo.get("codice_fiscale") or terzo.get("codiceFiscale") or "")).upper()
                denominazione = str(terzo.get("denominazione") or terzo.get("cognome") or "").strip()
                nome = str(terzo.get("nome") or "").strip()
                via = str(terzo.get("via") or "").strip()
                cap = str(terzo.get("cap") or "").strip()
                localita = str(terzo.get("localita") or "").strip()
                provincia = str(terzo.get("provincia") or "").strip().upper()
                missing = [
                    label
                    for label, value in (
                        ("denominazione o cognome", denominazione),
                        ("indirizzo", via),
                        ("CAP", cap),
                        ("località", localita),
                        ("provincia", provincia),
                    )
                    if not value
                ]
                if missing:
                    raise ValueError(f"Dati del terzo pignorato {index} mancanti: " + ", ".join(missing) + ".")
                altro = etree.SubElement(
                    participants[0],
                    f"{{{MINISTERIAL_ATTI_V7_NS}}}Altro",
                    naturaGiuridica="PFI" if len(cf) == 16 else "ENP",
                    ID=f"terzo_{index}",
                )
                etree.SubElement(altro, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}denominazione").text = denominazione
                if nome:
                    etree.SubElement(altro, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}nome").text = nome
                etree.SubElement(altro, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}codiceFiscale").text = cf
                address = etree.SubElement(altro, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}indirizzo")
                etree.SubElement(address, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}via").text = via
                etree.SubElement(address, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}cap").text = cap
                etree.SubElement(address, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}localita").text = localita
                etree.SubElement(address, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}provincia").text = provincia
                etree.SubElement(address, f"{{{MINISTERIAL_ANAGRAFICHE_NS}}}stato").text = str(terzo.get("stato") or "IT").strip()
        root.append(anagrafica)
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

    @staticmethod
    def _retagged_clone(node: etree._Element, namespace: str, name: str) -> etree._Element:
        clone = deepcopy(node)
        clone.tag = f"{{{namespace}}}{name}"
        return clone

    def _anagrafica_procedimento_pu_node(
        self,
    ) -> tuple[etree._Element, etree._Element, list[etree._Element], list[etree._Element]]:
        source = self._anagrafica_procedimento_node()
        key = self._catalog_key()
        debtor_request = "IstanzaDebitore" in key
        debtors = source.xpath("./*[local-name()='Partecipanti']/*[local-name()='Parte']") if debtor_request else source.xpath(
            "./*[local-name()='Partecipanti']/*[local-name()='ControParte']"
        )
        creditors = source.xpath("./*[local-name()='Partecipanti']/*[local-name()='Parte']")
        if not debtors:
            role = "debitore" if debtor_request else "controparte debitrice"
            raise ValueError(f"Anagrafica {role} mancante: completa le parti prima di generare la busta.")

        pu = etree.Element(
            f"{{{MINISTERIAL_ATTI_V7_NS}}}AnagraficaProcedimentoPU",
            nsmap={"pt": MINISTERIAL_ATTI_V7_NS, "at": MINISTERIAL_ANAGRAFICHE_NS},
        )
        participants = etree.SubElement(pu, f"{{{MINISTERIAL_ATTI_V7_NS}}}Partecipanti")
        for debtor in debtors:
            participants.append(self._retagged_clone(debtor, MINISTERIAL_ATTI_V7_NS, "Parte"))
        # Nella struttura PU i difensori del creditore sono riportati nella
        # sezione TipoParteIstante, non nell'anagrafica dei debitori.
        etree.SubElement(pu, f"{{{MINISTERIAL_ATTI_V7_NS}}}Soggetti")
        return pu, source, debtors, creditors

    def _aggiungi_tipo_parte_creditore_ccipu(
        self,
        root: etree._Element,
        source: etree._Element,
        creditors: list[etree._Element],
    ) -> None:
        if not creditors:
            raise ValueError("Creditore istante mancante: completa le parti prima di generare la busta.")
        ns = self._datiatto_namespace()
        tipo = etree.SubElement(root, f"{{{ns}}}TipoParteIstante")
        attorneys = source.xpath("./*[local-name()='Soggetti']/*[local-name()='Avvocato']")
        for creditor in creditors:
            creditor_id = str(creditor.get("ID") or "").strip()
            item = etree.SubElement(tipo, f"{{{ns}}}Creditore")
            item.append(self._retagged_clone(creditor, ns, "creditore"))
            for attorney in attorneys:
                represented_ids = {
                    str(ref.get("ref") or "").strip()
                    for ref in attorney.xpath("./*[local-name()='parteRappresentata']")
                }
                if creditor_id and creditor_id not in represented_ids:
                    continue
                item.append(self._retagged_clone(attorney, ns, "avvocato"))

    def _aggiungi_dati_specifici_introduttivo_siecic_concorsuali(self, root: etree._Element) -> bool:
        root_name = self._datiatto_root_name()
        pu_roots = {
            "RicorsoAmmissConcordatoPreventivoCCIPU",
            "RicorsoDichiarazioneInsolvenzaCCIPU",
            "RicorsoLiquidazioneControllataCCIPU",
            "RicorsoLiquidazioneGiudizialeCCIPU",
            "RicorsoOmologaAccordiRistrutturazCCIPU",
        }
        if root_name not in pu_roots:
            return False

        ns = self._datiatto_namespace()
        pu, source, debtors, creditors = self._anagrafica_procedimento_pu_node()
        root.append(pu)

        if root_name in {
            "RicorsoAmmissConcordatoPreventivoCCIPU",
            "RicorsoOmologaAccordiRistrutturazCCIPU",
        }:
            extension = etree.SubElement(root, f"{{{ns}}}EstensioneAnagrafica")
            for debtor in debtors:
                debtor_id = str(debtor.get("ID") or "").strip()
                if not debtor_id:
                    raise ValueError("Identificativo del debitore mancante nell'anagrafica ministeriale.")
                item = etree.SubElement(extension, f"{{{ns}}}DatiDebitore", ref=debtor_id)
                etree.SubElement(item, f"{{{ns}}}formaSocietaria").text = "N/A"

        etree.SubElement(root, f"{{{ns}}}misureCautelari").text = str(
            self._extra_bool("misure_cautelari", default=False)
        ).lower()
        etree.SubElement(root, f"{{{ns}}}misureProtettive").text = str(
            self._extra_bool("misure_protettive", default=False)
        ).lower()
        group = self._extra_text("gruppo_debitori").upper()
        if group:
            if group not in {"GI", "CF"}:
                raise ValueError("Gruppo debitori non valido: seleziona gruppo di imprese o crisi familiare.")
            etree.SubElement(root, f"{{{ns}}}gruppoDebitori").text = group

        if root_name in {
            "RicorsoLiquidazioneControllataCCIPU",
            "RicorsoLiquidazioneGiudizialeCCIPU",
            "RicorsoDichiarazioneInsolvenzaCCIPU",
        }:
            self._aggiungi_tipo_parte_creditore_ccipu(root, source, creditors)
        else:
            concordato = (
                "Ordinario"
                if root_name == "RicorsoOmologaAccordiRistrutturazCCIPU"
                else self._required_extra_text("tipo_concordato_ccipu", "Tipo di concordato")
            )
            concordato_map = {
                "ordinario": "Ordinario",
                "bianco": "Bianco",
                "in bianco": "Bianco",
                "inbianco": "Bianco",
            }
            concordato_value = concordato_map.get(concordato.casefold())
            if not concordato_value:
                raise ValueError("Tipo di concordato non valido: seleziona ordinario o in bianco.")
            etree.SubElement(root, f"{{{ns}}}tipoConcordato").text = concordato_value
        return True

    def _aggiungi_base_cassazione(self, root: etree._Element) -> None:
        key = self._catalog_key()
        destination = self._datiatto_root_name() == "Ricorso" or "IscrittoDalControricorrente" in key
        if destination:
            etree.SubElement(
                root,
                f"{{{CASSAZIONE_ATTI_NS}}}destinazione",
                ufficio=str(self.dati.codice_ufficio or "").strip(),
                ruolo="CassazioneCivile",
            )
            return
        self._aggiungi_riferimento_procedimento_ministeriale(root)

    def _cassazione_tipo_ricorso(self) -> str:
        value = self._required_extra_text("tipo_ricorso_cassazione", "Tipo di ricorso")
        mapping = {
            "ricorso ordinario": "RicorsoOrdinario",
            "ricorsoordinario": "RicorsoOrdinario",
            "regolamento di competenza": "RegolamentoDiCompetenza",
            "regolamentodicompetenza": "RegolamentoDiCompetenza",
            "regolamento di giurisdizione": "RegolamentoPreventivoDiGiurisdizione",
            "regolamentopreventivodigiurisdizione": "RegolamentoPreventivoDiGiurisdizione",
            "ricorso per revocazione": "RicorsoPerRevocazione",
            "ricorsoperrevocazione": "RicorsoPerRevocazione",
            "ricorso ex art. 348 ter": "Ricorso_ex_art_348_TER",
            "ricorso ex art.348 ter": "Ricorso_ex_art_348_TER",
            "ricorso_ex_art_348_ter": "Ricorso_ex_art_348_TER",
        }
        normalized = mapping.get(value.casefold(), value)
        allowed = {
            "RegolamentoPreventivoDiGiurisdizione",
            "RicorsoOrdinario",
            "RegolamentoDiCompetenza",
            "RicorsoPerRevocazione",
            "Ricorso_ex_art_348_TER",
        }
        if normalized not in allowed:
            raise ValueError("Tipo di ricorso non valido: seleziona una voce prevista dalla tabella ministeriale.")
        return normalized

    def _aggiungi_provvedimento_impugnato_cassazione(self, root: etree._Element) -> None:
        raw = self._datiatto_extra().get("provvedimento_impugnato")
        data = raw if isinstance(raw, dict) else {}
        ufficio = str(data.get("ufficio") or self._extra_text("provvedimento_ufficio")).strip()
        ruolo = str(data.get("ruolo") or self._extra_text("provvedimento_ruolo")).strip()
        numero = str(data.get("numero_fascicolo") or self._extra_text("provvedimento_fascicolo_numero")).strip()
        anno = str(data.get("anno_fascicolo") or self._extra_text("provvedimento_fascicolo_anno")).strip()
        missing = []
        if not ufficio:
            missing.append("ufficio del provvedimento impugnato")
        if not ruolo:
            missing.append("ruolo del fascicolo impugnato")
        if not numero:
            missing.append("numero del fascicolo impugnato")
        if not anno:
            missing.append("anno del fascicolo impugnato")
        if missing:
            raise ValueError("Dati del provvedimento impugnato mancanti: " + ", ".join(missing) + ".")
        allowed_roles = {
            "Speciale",
            "Contenzioso",
            "Lavoro",
            "Agraria",
            "VolontariaGiurisdizione",
            "EsecuzioniCivili",
            "EspropriazioniImmobiliari",
            "Notifiche",
            "AffariCivili",
        }
        if ruolo not in allowed_roles:
            raise ValueError("Ruolo del fascicolo impugnato non valido: seleziona una voce ministeriale.")
        if not re.sub(r"\D+", "", numero) or not anno.isdigit():
            raise ValueError("Numero o anno del fascicolo impugnato non validi.")

        provvedimento = etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}Provvedimento")
        fascicolo = etree.SubElement(provvedimento, f"{{{CASSAZIONE_ATTI_NS}}}DatiFascicolo")
        etree.SubElement(fascicolo, f"{{{CASSAZIONE_ATTI_NS}}}Ufficio").text = ufficio
        etree.SubElement(fascicolo, f"{{{CASSAZIONE_ATTI_NS}}}Ruolo").text = ruolo
        rito = str(data.get("rito") or self._extra_text("provvedimento_rito")).strip()
        if rito:
            etree.SubElement(fascicolo, f"{{{CASSAZIONE_ATTI_NS}}}Rito").text = rito
        etree.SubElement(fascicolo, f"{{{CASSAZIONE_ATTI_NS}}}Numero").text = re.sub(r"\D+", "", numero)
        sub = str(data.get("sub") or self._extra_text("provvedimento_fascicolo_sub")).strip()
        if sub:
            etree.SubElement(fascicolo, f"{{{CASSAZIONE_ATTI_NS}}}Sub").text = sub
        etree.SubElement(fascicolo, f"{{{CASSAZIONE_ATTI_NS}}}Anno").text = anno

    def _aggiungi_inizio_primo_grado_cassazione(self, root: etree._Element, *, required: bool) -> None:
        anno = self._extra_text("inizio_primo_grado_anno")
        ufficio = self._extra_text("inizio_primo_grado_ufficio")
        if not anno and not ufficio and not required:
            return
        if not anno.isdigit() or len(anno) != 4:
            raise ValueError("Anno di inizio del giudizio di primo grado mancante o non valido.")
        if not ufficio:
            raise ValueError("Ufficio del giudizio di primo grado mancante.")
        node = etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}InizioGiudizioPrimoGrado")
        etree.SubElement(node, f"{{{CASSAZIONE_TIPI_NS}}}anno").text = anno
        etree.SubElement(node, f"{{{CASSAZIONE_TIPI_NS}}}Ufficio").text = ufficio

    def _aggiungi_materia_cassazione(self, root: etree._Element) -> None:
        materia = self._required_extra_text("materia_ricorso_cassazione", "Materia del ricorso")
        if not re.fullmatch(r"\d{3}", materia):
            raise ValueError("Materia del ricorso non valida: seleziona il codice previsto dalla tabella ministeriale.")
        node = etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}Materia")
        etree.SubElement(node, f"{{{CASSAZIONE_TIPI_NS}}}materia").text = materia
        self._append_text_if_present(
            node,
            CASSAZIONE_TIPI_NS,
            "paroleChiave",
            self._datiatto_extra().get("parole_chiave_cassazione"),
        )

    def _aggiungi_motivi_cassazione(self, root: etree._Element, *, counter: bool) -> None:
        key = "contromotivi_cassazione" if counter else "motivi_cassazione"
        raw = self._datiatto_extra().get(key)
        items = raw if isinstance(raw, list) else []
        label = "Contromotivi" if counter else "Motivi"
        if not items:
            raise ValueError(f"{label} mancanti: inserisci almeno una voce prima di generare la busta.")
        container_name = "ControMotivi" if counter else "Motivi"
        item_name = "ControMotivo" if counter else "Motivo"
        container = etree.SubElement(root, f"{{{CASSAZIONE_TIPI_NS}}}{container_name}")
        for index, item_raw in enumerate(items, start=1):
            item = item_raw if isinstance(item_raw, dict) else {}
            if counter:
                number = str(item.get("numero_riferimento_motivo") or item.get("numero") or index).strip()
                page = str(item.get("pagina") or item.get("riferimento_pagina") or "").strip()
                if not number.isdigit() or not page.isdigit() or int(page) <= 0:
                    raise ValueError("Numero del motivo o pagina del contromotivo non validi.")
                node = etree.SubElement(
                    container,
                    f"{{{CASSAZIONE_TIPI_NS}}}{item_name}",
                    numeroRiferimentoMotivo=number,
                    riferimentoPagina=page,
                )
            else:
                number = str(item.get("numero") or index).strip()
                article = str(item.get("numero_art_360") or "").strip()
                if not number or article not in {"1", "2", "3", "4", "5"}:
                    raise ValueError("Numero del motivo o riferimento all'art. 360 non validi.")
                attrs = {"numeroMotivo": number, "numeroArt360": article}
                page = str(item.get("pagina") or item.get("riferimento_pagina") or "").strip()
                if page:
                    if not page.isdigit() or int(page) <= 0:
                        raise ValueError("Pagina del motivo non valida.")
                    attrs["riferimentoPagina"] = page
                node = etree.SubElement(container, f"{{{CASSAZIONE_TIPI_NS}}}{item_name}", **attrs)
            self._append_text_if_present(node, CASSAZIONE_TIPI_NS, "descrizione", item.get("descrizione"))

    def _modifiche_anagrafica_cassazione_node(self) -> etree._Element:
        node = self._anagrafica_procedimento_node()
        node.tag = f"{{{CASSAZIONE_ATTI_NS}}}ModificheAnagrafica"
        participants = node.xpath("./*[local-name()='Partecipanti']")
        if not participants:
            raise ValueError("Parti da integrare mancanti nell'anagrafica.")
        for participant in list(participants[0]):
            if etree.QName(participant).localname != "Parte":
                participants[0].remove(participant)
        if not list(participants[0]):
            raise ValueError("Parte da integrare mancante nell'anagrafica.")
        return node

    def _aggiungi_dati_specifici_cassazione(self, root: etree._Element) -> bool:
        root_name = self._datiatto_root_name()
        if root_name in {"Ricorso", "ControRicorso", "ControRicorsoIncidentale"}:
            ns = CASSAZIONE_PARTE_NS
            etree.SubElement(root, f"{{{ns}}}TipoRicorso").text = self._cassazione_tipo_ricorso()
            request_date = self._required_extra_text("data_richiesta_notifica_cassazione", "Data della prima notifica")
            effective_date = self._extra_text("data_effettiva_notifica_cassazione") or request_date
            etree.SubElement(root, f"{{{ns}}}dataRichiestaNotifica").text = self._format_date_field(
                request_date, "Data della prima notifica"
            )
            etree.SubElement(root, f"{{{ns}}}dataEffettivaNotifica").text = self._format_date_field(
                effective_date, "Data di perfezionamento della notifica"
            )
            self._aggiungi_provvedimento_impugnato_cassazione(root)
            self._aggiungi_inizio_primo_grado_cassazione(root, required=root_name == "Ricorso")
            self._aggiungi_materia_cassazione(root)
            if self.dati.valore_causa is not None:
                etree.SubElement(root, f"{{{ns}}}valoreCausa").text = f"{float(self.dati.valore_causa):.2f}"
            elif root_name == "ControRicorsoIncidentale":
                contribution_mode, _ = self._contributo_unificato_dati()
                if contribution_mode != "esente":
                    raise ValueError("Valore della causa mancante: inseriscilo prima di generare la busta.")
                etree.SubElement(root, f"{{{ns}}}valoreCausa").text = "0.00"
            self._aggiungi_spese_giustizia_cassazione(root, integration=False)
            if root_name in {"Ricorso", "ControRicorsoIncidentale"} and not root.xpath(
                "./*[local-name()='speseGiustizia']"
            ):
                raise ValueError("Spese di giustizia non definite: indica pagamento, debito o esenzione.")
            root.append(self._anagrafica_procedimento_node())
            if root_name in {"Ricorso", "ControRicorsoIncidentale"}:
                self._aggiungi_motivi_cassazione(root, counter=False)
            if root_name in {"ControRicorso", "ControRicorsoIncidentale"}:
                self._aggiungi_motivi_cassazione(root, counter=True)
            etree.SubElement(root, f"{{{CASSAZIONE_ATTI_NS}}}DocumentiECLI")
            return True
        if root_name == "AttoGenerico":
            etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}deposito")
            return True
        if root_name == "IntegrazioneAnagrafica":
            root.append(self._modifiche_anagrafica_cassazione_node())
            deposito = etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}deposito")
            event_name = self._catalog_key().split("::", 1)[-1]
            allowed = {
                "IntegrazioneContradittorio",
                "ProcuraSpecialeCostituzione",
                "ProcuraSpecialeSostituzioneRevoca",
                "VariazioneDomicilio",
            }
            if event_name not in allowed:
                raise ValueError("Tipo di integrazione anagrafica non riconosciuto.")
            etree.SubElement(deposito, f"{{{CASSAZIONE_EVENTI_NS}}}{event_name}")
            return True
        return False

    def _aggiungi_destinazione_e_oggetto_ministeriali(self, root: etree._Element) -> None:
        atti_ns = self._datiatto_atti_namespace()
        etree.SubElement(
            root,
            f"{{{atti_ns}}}destinazione",
            ufficio=str(self.dati.codice_ufficio or "").strip(),
            ruolo=self._ruolo_ministeriale_registro(
                self.dati.codice_registro,
                self.dati.tipo_atto,
                self.dati.ruolo_ministeriale,
            ),
        )
        if self._is_datiatto_sistema():
            return
        etree.SubElement(root, f"{{{atti_ns}}}Oggetto").text = str(self.dati.oggetto or "").strip()
        if not self._is_datiatto_introduttivo():
            return
        contribution_mode, amount = self._contributo_unificato_dati()

        valore = 0.0
        if self.dati.valore_causa is not None:
            try:
                valore = float(self.dati.valore_causa)
            except (TypeError, ValueError):
                valore = 0.0
            if valore > 0:
                etree.SubElement(root, f"{{{atti_ns}}}ValoreCausa").text = f"{valore:.2f}"
        xml_mode = str(self.dati.contributo_unificato_xml_mode or "").strip()
        writes_intro_contribution = xml_mode == "atto_introduttivo" or (
            not xml_mode and self._is_datiatto_introduttivo()
        )
        if writes_intro_contribution and contribution_mode == "esente" and valore <= 0:
            etree.SubElement(root, f"{{{atti_ns}}}ValoreCausa").text = "0.00"

        if writes_intro_contribution and contribution_mode in {"pagato", "prenotato_a_debito"}:
            node = etree.SubElement(root, f"{{{atti_ns}}}ContributoUnificato")
            self._append_importo_contributo(
                node,
                namespace=atti_ns,
                amount=amount,
                debt=contribution_mode == "prenotato_a_debito",
            )

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
            ruolo=self._ruolo_ministeriale_registro(
                self.dati.codice_registro,
                self.dati.tipo_atto,
                self.dati.ruolo_ministeriale,
            ),
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
        contribution_mode, contribution_amount = self._contributo_unificato_dati()
        if generator_class == "UNEP":
            from pct.datiatto_unep import ROOT_NS as UNEP_ROOT_NS
            from pct.datiatto_unep import build_unep_datiatto
            from pct.datiatto_xsd import validate_datiatto_xml

            payload = build_unep_datiatto(
                self.dati,
                document_parts,
                contribution_mode=contribution_mode,
                contribution_amount=contribution_amount,
            )
            validation = validate_datiatto_xml(payload, expected_root_namespace=UNEP_ROOT_NS)
            if not validation.ok:
                detail = "; ".join(validation.errors[:3]) or "controllo ufficiale non superato"
                raise ValueError(f"Dati del deposito UNEP non conformi: {detail}")
            self._verifica_ruolo_ministeriale_xml(payload)
            return payload
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
                "evt": (
                    CASSAZIONE_EVENTI_NS
                    if generator_class.startswith("ParteCassazione")
                    else (
                        MINISTERIAL_EVENTI_PARTE_NS
                        if generator_class == "Parte"
                        else SIECIC_EVENTI_NS
                    )
                ),
                "xsi": XSI_NS,
                "xsd": XSD_NS,
            },
        )
        if self._is_datiatto_introduttivo() and (
            "citazione" in root_name.casefold() or root_name == "OpposizioneDecretoIngiuntivo"
        ):
            root.set("Datacitazione", self._normalizza_data_notifica_citazione())
        if self._is_datiatto_introduttivo():
            self._aggiungi_destinazione_e_oggetto_ministeriali(root)
        elif self._is_datiatto_sistema():
            self._aggiungi_destinazione_e_oggetto_ministeriali(root)
        elif self._is_datiatto_procedimento_base():
            self._aggiungi_riferimento_procedimento_ministeriale(root)
        elif self._is_datiatto_cassazione():
            self._aggiungi_base_cassazione(root)

        if self._usa_indice_busta_interno():
            indice = etree.SubElement(root, f"{{{self._datiatto_atti_namespace()}}}IndiceBusta")
            allegati_ns = self._datiatto_allegati_namespace()
            etree.SubElement(indice, f"{{{allegati_ns}}}AttoPrincipale", id=main_part.content_id)
            for part in document_parts:
                if part.is_main:
                    continue
                etree.SubElement(indice, f"{{{allegati_ns}}}{part.ruolo_indice}", id=part.content_id)
        if self._is_datiatto_sistema():
            etree.SubElement(root, f"{{{namespace}}}RefId").text = self._xml_id(self.id_busta, "deposito")

        if generator_class == "Parte":
            self._aggiungi_dati_specifici_parte_sicid(root)
        elif generator_class in {"ParteSiecicEsecuzioni", "ParteSiecicConcorsuali"}:
            self._aggiungi_dati_specifici_parte_siecic(root)
        elif generator_class == "CorsoCausa_SIGP":
            self._aggiungi_dati_specifici_corso_causa_sigp(root)
        elif generator_class == "DelSiecicEsecuzioni":
            if root_name == "DepositoSemplice":
                self._aggiungi_deposito_semplice_ministeriale(root)
            self._aggiungi_dati_specifici_delegato_siecic(root)
        elif root_name == "DepositoSemplice" and generator_class in DEPOSITO_SEMPLICE_EVENT_BY_GENERATOR_AND_KEY:
            self._aggiungi_deposito_semplice_ministeriale(root)

        cassazione_specifica = False
        if self._is_datiatto_cassazione():
            cassazione_specifica = self._aggiungi_dati_specifici_cassazione(root)

        if self._is_pignoramento_siecic():
            self._aggiungi_pignoramento_ministeriale(root)
        elif self.dati.contributo_unificato_xml_mode == "siecic_istanza_vendita":
            self._aggiungi_istanza_vendita_ministeriale(root)
        elif self._is_richiesta_visibilita():
            self._aggiungi_richiesta_visibilita_ministeriale(root)
        elif self._is_progetto_distribuzione():
            self._aggiungi_progetto_distribuzione_ministeriale(root)

        if self.dati.contributo_unificato_xml_mode == "cassazione_spese_giustizia" and not cassazione_specifica:
            if self.dati.valore_causa is not None:
                etree.SubElement(root, f"{{{self._datiatto_namespace()}}}valoreCausa").text = f"{float(self.dati.valore_causa):.2f}"
            self._aggiungi_spese_giustizia_cassazione(root, integration=False)
        elif self.dati.contributo_unificato_xml_mode == "cassazione_integrazione_spese" and not cassazione_specifica:
            self._aggiungi_spese_giustizia_cassazione(root, integration=True)

        cassazione_anagrafica_roots = {"Ricorso", "ControRicorso", "ControRicorsoIncidentale", "IntegrazioneAnagrafica"}
        if self._is_datiatto_introduttivo() and not self._is_pignoramento_siecic():
            concorsuale_pu = (
                generator_class == "IntroduttiviSiecicConcorsuali"
                and self._aggiungi_dati_specifici_introduttivo_siecic_concorsuali(root)
            )
            if not concorsuale_pu:
                root.append(self._anagrafica_procedimento_node())
                if generator_class == "IntroduttiviSicid":
                    self._aggiungi_dati_specifici_introduttivo_sicid(root)
                elif generator_class == "Introduttivi_SIGP":
                    self._aggiungi_dati_specifici_introduttivo_sigp(root)
        elif (
            self._is_datiatto_cassazione()
            and root_name in cassazione_anagrafica_roots
            and not cassazione_specifica
        ):
            root.append(self._anagrafica_procedimento_node())
        payload = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        from pct.datiatto_xsd import validate_datiatto_xml

        validation = validate_datiatto_xml(payload, expected_root_namespace=namespace)
        if not validation.ok:
            detail = "; ".join(validation.errors[:3]) or "controllo ufficiale non superato"
            raise ValueError(f"Dati del deposito non conformi: {detail}")
        self._verifica_ruolo_ministeriale_xml(payload)
        return payload

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
                (
                    DATI_ATTO_FILENAME
                    if self._usa_dati_atto_ministeriale()
                    else self._mime_content_id(dati_atto_filename)
                ),
            )
        )

        for part in document_parts:
            payloads.append((part.filename, part.payload, part.maintype, part.subtype, part.content_id))
        return payloads

    def _crea_atto_msg(
        self,
        *,
        xml_content: bytes,
        indice_busta_xml: bytes | None,
        indice_pdf: bytes,
        dati_atto_firmato: bytes | None = None,
        document_parts: list[_DocumentoBusta] | None = None,
    ) -> bytes:
        message = EmailMessage(policy=policy.SMTP)
        message["Message-ID"] = make_msgid(domain="juris.it")
        message["X-Mailer"] = "fa9772aa-c144-4f2b-8263-b0cd033c86a8"
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
            part.add_header("Content-Disposition", "attachment", filename=filename)
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

    # Dimensione massima ragionevole di una RT.xml (le ricevute pagoPA sono
    # pochi KB: oltre 2 MB non e' una ricevuta e non va parsata).
    _RT_MAX_BYTES = 2 * 1024 * 1024

    def _audit_ricevute_telematiche_pagamento(self) -> dict:
        """Legge e verifica le RT pagoPA allegate alla busta (gap pagamenti giustizia).

        Fonte: schema ministeriale PagamentiTelematiciGiustizia + vademecum
        pagamenti PST. Riconcilia l'importo provato dalle ricevute con il
        contributo unificato dichiarato in DatiAtto; esiti negativi bloccano.
        """

        from pct.pagamenti_giustizia import riepilogo_rt_allegate  # noqa: PLC0415

        candidati: list[tuple[str, bytes]] = []
        for allegato in self.dati.allegati:
            path = Path(allegato.percorso)
            nome = path.name.casefold()
            if not (nome.endswith(".xml") or nome.endswith(".xml.p7m")):
                continue
            try:
                if not path.exists() or path.stat().st_size > self._RT_MAX_BYTES:
                    continue
                candidati.append((path.name, path.read_bytes()))
            except OSError:
                continue
        if not candidati:
            return {"ricevute": [], "totale_eseguito": 0.0, "issues": []}
        try:
            contribution_mode, amount = self._contributo_unificato_dati()
        except Exception:
            contribution_mode, amount = "", 0.0
        importo_atteso = float(amount or 0.0) if contribution_mode == "pagato" else None
        try:
            return riepilogo_rt_allegate(
                candidati,
                importo_atteso=importo_atteso,
                pagamento_richiesto=contribution_mode == "pagato",
            )
        except Exception:
            # L'analisi delle ricevute non deve mai far fallire l'audit busta.
            return {"ricevute": [], "totale_eseguito": 0.0, "issues": []}

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

        role_audit = dict(self._last_role_audit or {})
        if role_audit and role_audit.get("dati_atto_ruolo_coerente") is not True:
            issues.append(
                {
                    "code": "DATI-ATTO-RUOLO",
                    "level": "BLOCK",
                    "title": "Ruolo ministeriale non coerente con il fascicolo",
                    "detail": (
                        f"Atteso {role_audit.get('dati_atto_ruolo_atteso') or 'ruolo della pratica'}; "
                        f"trovato {', '.join(role_audit.get('dati_atto_ruoli_effettivi') or []) or 'nessun ruolo'}."
                    ),
                    "source": "Studio Telematico: ruolo selezionato nella pratica e attributo ruolo del DatiAtto.xml",
                    "suggested_action": "Rigenera la busta dopo avere riallineato registro, sezione e ruolo della pratica.",
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

        ricevute_pagamento = self._audit_ricevute_telematiche_pagamento()
        issues.extend(ricevute_pagamento.get("issues", []))

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
            **role_audit,
            "ricevute_pagamento": ricevute_pagamento,
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
            "atto_enc_size": transport.get("atto_enc_size"),
            "atto_enc_cms_valid": transport.get("atto_enc_cms_valid") is True,
            "cms_content_type": transport.get("cms_content_type", ""),
            "cms_recipients": transport.get("cms_recipients"),
            "content_encryption_algorithm": transport.get(
                "content_encryption_algorithm",
                "",
            ),
            "content_encryption_algorithm_oid": transport.get(
                "content_encryption_algorithm_oid",
                "",
            ),
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
                from pct.firma import profilo_cades_bes_valido
            except Exception as exc:
                raise ValueError("Verifica CAdES non disponibile per DatiAtto.xml.p7m.") from exc
            if not profilo_cades_bes_valido(dati_atto_firmato):
                raise ValueError("DatiAtto.xml.p7m non contiene una firma CAdES-BES completa.")

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
