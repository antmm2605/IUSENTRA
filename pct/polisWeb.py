"""
pct/polisWeb.py — Integrazione con il Portale Servizi Telematici (PST)
                   del Ministero della Giustizia.

Offre due blocchi funzionali:

A) CONSULTAZIONE (lettura):
   - RicercaFascicoliRegistro: cerca pratiche nel registro civile/penale
   - ConsultazioneAvanzataDocumenti: recupera documenti dal fascicolo telematico
   → Usa i web service SOAP ufficiali PST (autenticazione con certificato P12)

B) DEPOSITO (scrittura):
   - Il deposito civile avviene già via PEC + busta .enc (pct/deposito.py)
   - PolisWeb NON è il canale di deposito: è un portale di consultazione
   → Per il deposito usare DepositoCivile in pct/deposito.py

Requisiti:
  - pip install zeep  (SOAP client)
  - Certificato P12 del professionista (già configurato come PCT_FIRMA_P12)

Riferimenti:
  - Specifiche PST/PCT: https://pst.giustizia.it/PST/it/page_1_0.wp
  - DM 44/2011 e Provvedimento DGSIA del 18/7/2011
"""
from __future__ import annotations

import os
import ssl
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- PST endpoints
# I web service del PST sono accessibili con autenticazione a certificato.
# Gli endpoint possono variare per distretto; qui i principali nazionali.
_WSP_BASE = os.getenv("PCT_PST_BASE_URL", "https://wspa.giustizia.it/wspa")
_WSDL_RICERCA     = f"{_WSP_BASE}/RicercaFascicoliRegistroService?wsdl"
_WSDL_CONSULTAZIONE = f"{_WSP_BASE}/ConsultazioneAvanzataDocumentiService?wsdl"
_WSDL_REGINDE     = f"{_WSP_BASE}/ConsultazioneRegistroService?wsdl"


# ================================================================ Dataclass risultati

@dataclass
class FascicoloPolisWeb:
    """
    Pratica trovata nel registro del tribunale tramite PolisWeb.
    Da usare come sorgente per l'importazione nel fascicolo interno.
    """
    numero_rg: str
    anno_rg: int
    ruolo: str                  # CIVILE_COGNIZIONE | ESECUZIONI | FALLIMENTI | …
    stato: str                  # PENDENTE | DEFINITO | SOSPESO
    oggetto: str                # oggetto della causa
    sezione: str = ""
    giudice: str = ""
    data_iscrizione: str = ""   # YYYY-MM-DD
    data_udienza: str = ""      # prossima udienza
    parti: List[str] = field(default_factory=list)
    note: str = ""
    codice_ufficio: str = ""    # codice MinGiust del tribunale
    nome_ufficio: str = ""


@dataclass
class DocumentoPolisWeb:
    """Documento presente nel fascicolo telematico del tribunale."""
    id_documento: str
    nome: str
    tipo: str                   # ATTO | MEMORIA | SENTENZA | ORDINANZA | …
    data_deposito: str          # YYYY-MM-DD
    mittente: str
    dimensione_bytes: int = 0
    disponibile: bool = True


@dataclass
class RisultatoImportazione:
    """Esito dell'importazione di una pratica da PolisWeb."""
    successo: bool
    id_fascicolo_locale: Optional[str] = None
    messaggio: str = ""
    fascicolo_polis: Optional[FascicoloPolisWeb] = None
    documenti_importati: int = 0
    avvisi: List[str] = field(default_factory=list)


# ================================================================ Client PolisWeb

class ClientPolisWeb:
    """
    Client per l'accesso ai web service del PST (Portale Servizi Telematici).

    Autentica via certificato digitale P12 del professionista e fornisce:
    - ricerca_fascicoli(): cerca pratiche per RG, anno, tribunale
    - consulta_documenti(): lista documenti in un fascicolo
    - importa_fascicolo(): importa una pratica PolisWeb nel gestionale locale

    Tutti i metodi gestiscono il caso in cui zeep non sia installato
    (sollevano ImportError con istruzioni).
    """

    def __init__(
        self,
        p12_path: str,
        p12_password: bytes,
        codice_fiscale_avvocato: str = "",
        timeout: int = 30,
    ):
        """
        Args:
            p12_path:                 Percorso al file PKCS#12 del professionista.
            p12_password:             Password del certificato P12.
            codice_fiscale_avvocato:  CF dell'avvocato (necessario per alcune query).
            timeout:                  Timeout HTTP in secondi.
        """
        self.p12_path    = p12_path
        self.p12_password = p12_password
        self.cf_avvocato = codice_fiscale_avvocato.upper()
        self.timeout     = timeout
        self._zeep_cache: Dict[str, Any] = {}

    # ---------------------------------------------------------------- Ricerca fascicoli

    def ricerca_fascicoli(
        self,
        tribunale: str,
        numero_rg: Optional[str] = None,
        anno_rg: Optional[int] = None,
        nome_parte: Optional[str] = None,
        codice_fiscale_parte: Optional[str] = None,
        max_risultati: int = 50,
    ) -> List[FascicoloPolisWeb]:
        """
        Cerca fascicoli nel registro del tribunale tramite PST SOAP.

        Args:
            tribunale:            Nome del tribunale (es. "MILANO") o codice ufficio.
            numero_rg:            Numero RG (facoltativo).
            anno_rg:              Anno RG (facoltativo).
            nome_parte:           Nome di una parte (attore/convenuto).
            codice_fiscale_parte: CF di una parte.
            max_risultati:        Numero massimo di risultati.

        Returns:
            Lista di FascicoloPolisWeb.

        Raises:
            ImportError: se zeep non è installato.
            ConnectionError: se il PST non è raggiungibile.
            PermissionError: se il certificato non è valido / scaduto.
        """
        client = self._get_client(_WSDL_RICERCA)

        # Costruzione request conforme al WSDL PST
        request_dict = {
            "codiceFiscaleAvvocato": self.cf_avvocato,
            "codiceUfficio": self._risolvi_codice_ufficio(tribunale),
            "maxRisultati": max_risultati,
        }
        if numero_rg:
            request_dict["numeroRG"] = numero_rg
        if anno_rg:
            request_dict["annoRG"] = anno_rg
        if nome_parte:
            request_dict["nominativoParte"] = nome_parte
        if codice_fiscale_parte:
            request_dict["codiceFiscaleParte"] = codice_fiscale_parte.upper()

        try:
            risposta = client.service.ricercaFascicoli(**request_dict)
        except Exception as e:
            raise ConnectionError(f"Errore chiamata PST: {e}") from e

        return self._parse_fascicoli(risposta)

    # ---------------------------------------------------------------- Consultazione documenti

    def consulta_documenti(
        self,
        codice_ufficio: str,
        numero_rg: str,
        anno_rg: int,
    ) -> List[DocumentoPolisWeb]:
        """
        Recupera l'elenco dei documenti depositati nel fascicolo telematico.

        Args:
            codice_ufficio: Codice MinGiust del tribunale.
            numero_rg:      Numero RG della causa.
            anno_rg:        Anno RG.

        Returns:
            Lista di DocumentoPolisWeb.
        """
        client = self._get_client(_WSDL_CONSULTAZIONE)
        try:
            risposta = client.service.consultazioneAvanzataDocumenti(
                codiceFiscaleAvvocato=self.cf_avvocato,
                codiceUfficio=codice_ufficio,
                numeroRG=numero_rg,
                annoRG=anno_rg,
            )
        except Exception as e:
            raise ConnectionError(f"Errore consultazione PST: {e}") from e

        return self._parse_documenti(risposta)

    # ---------------------------------------------------------------- Import pratica

    def importa_fascicolo(
        self,
        fascicolo_pw: FascicoloPolisWeb,
        gestione_fascicoli,        # GestioneFascicoli instance
        gestione_clienti,          # GestioneClienti instance
        avvocato_referente: str = "",
    ) -> RisultatoImportazione:
        """
        Importa una pratica PolisWeb come nuovo Fascicolo nel gestionale.

        Il metodo:
        1. Cerca il cliente tra le parti (per CF o nome)
        2. Crea o riutilizza il Cliente
        3. Crea il Fascicolo con tutti i dati disponibili
        4. Aggiunge le attività processuali note (udienza prossima)

        Args:
            fascicolo_pw:       Pratica PolisWeb da importare.
            gestione_fascicoli: Istanza di GestioneFascicoli.
            gestione_clienti:   Istanza di GestioneClienti.
            avvocato_referente: Username avvocato responsabile.

        Returns:
            RisultatoImportazione con id_fascicolo_locale se successo.
        """
        try:
            from pct.fascicoli import TipoFascicolo, StatoFascicolo, TipoAttivita, EsitoAttivita
            from pct.clienti import TipoCliente

            # 1. Mappa il tipo ruolo → TipoFascicolo
            tipo_map = {
                "CIVILE_COGNIZIONE":   TipoFascicolo.CIVILE,
                "ESECUZIONI":          TipoFascicolo.CIVILE,
                "FALLIMENTI":          TipoFascicolo.CIVILE,
                "PENALE":              TipoFascicolo.PENALE,
                "LAVORO":              TipoFascicolo.LAVORO,
                "FAMIGLIA":            TipoFascicolo.FAMIGLIA,
                "MINORI":              TipoFascicolo.FAMIGLIA,
                "VOLONTARIA":          TipoFascicolo.ALTRO,
            }
            tipo_fascicolo = tipo_map.get(
                fascicolo_pw.ruolo.upper(), TipoFascicolo.CIVILE
            )
            stato_map = {
                "PENDENTE": StatoFascicolo.IN_CORSO,
                "DEFINITO": StatoFascicolo.DEFINITO,
                "SOSPESO":  StatoFascicolo.SOSPESO,
            }
            stato = stato_map.get(
                fascicolo_pw.stato.upper(), StatoFascicolo.APERTO
            )

            # 2. Trova o crea cliente (prima parte registrata)
            id_cliente = ""
            nome_cliente = ""
            if fascicolo_pw.parti:
                nome_parte = fascicolo_pw.parti[0]
                # Cerca per nome
                clienti_esistenti = gestione_clienti.tutti()
                for c in clienti_esistenti:
                    if nome_parte.upper() in c.nome_completo.upper():
                        id_cliente = c.id
                        nome_cliente = c.nome_completo
                        break

            # 3. Crea fascicolo
            fasc = gestione_fascicoli.crea(
                titolo=f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg} — {fascicolo_pw.oggetto[:80]}",
                tipo=tipo_fascicolo,
                id_cliente=id_cliente,
                nome_cliente=nome_cliente,
                tribunale=fascicolo_pw.nome_ufficio,
                numero_rg=fascicolo_pw.numero_rg,
                anno_rg=fascicolo_pw.anno_rg,
                sezione=fascicolo_pw.sezione,
                giudice=fascicolo_pw.giudice,
                oggetto=fascicolo_pw.oggetto,
                stato=stato,
                avvocato_referente=avvocato_referente,
                data_apertura=fascicolo_pw.data_iscrizione or date.today().isoformat(),
                note=fascicolo_pw.note or f"Importato da PolisWeb il {date.today()}",
            )

            avvisi = []

            # 4. Aggiungi prossima udienza come attività
            if fascicolo_pw.data_udienza:
                try:
                    gestione_fascicoli.aggiungi_attivita(
                        fasc.id,
                        tipo=TipoAttivita.UDIENZA,
                        data=fascicolo_pw.data_udienza,
                        titolo="Udienza (importata da PolisWeb)",
                        descrizione=f"Udienza automaticamente importata da PolisWeb — RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
                        avvocato=avvocato_referente,
                    )
                except Exception as e:
                    avvisi.append(f"Udienza non importata: {e}")

            if not id_cliente:
                avvisi.append(
                    "Nessun cliente trovato in anagrafica per le parti della causa. "
                    "Assegnare il cliente manualmente."
                )

            return RisultatoImportazione(
                successo=True,
                id_fascicolo_locale=fasc.id,
                messaggio=f"Pratica RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg} importata.",
                fascicolo_polis=fascicolo_pw,
                avvisi=avvisi,
            )

        except Exception as e:
            return RisultatoImportazione(
                successo=False,
                messaggio=f"Errore durante l'importazione: {e}",
                fascicolo_polis=fascicolo_pw,
            )

    # ---------------------------------------------------------------- SOAP helpers

    def _get_client(self, wsdl_url: str):
        """
        Crea (e memorizza in cache) un client zeep con autenticazione
        tramite certificato client P12.
        """
        if wsdl_url in self._zeep_cache:
            return self._zeep_cache[wsdl_url]

        try:
            import zeep
            import zeep.transports
            from requests import Session
            from requests_pkcs12 import Pkcs12Adapter
        except ImportError as e:
            if "requests_pkcs12" in str(e):
                raise ImportError(
                    "Installa requests-pkcs12: pip install requests-pkcs12"
                ) from e
            raise ImportError(
                "Installa zeep: pip install zeep"
            ) from e

        session = Session()
        adapter = Pkcs12Adapter(
            pkcs12_filename=self.p12_path,
            pkcs12_password=self.p12_password,
        )
        session.mount("https://wspa.giustizia.it", adapter)
        transport = zeep.transports.Transport(session=session, timeout=self.timeout)
        client = zeep.Client(wsdl=wsdl_url, transport=transport)
        self._zeep_cache[wsdl_url] = client
        return client

    def _risolvi_codice_ufficio(self, nome_o_codice: str) -> str:
        """Risolve nome tribunale → codice ufficio MinGiust."""
        from pct.reginde import ClientReGINde
        if nome_o_codice.isdigit():
            return nome_o_codice
        reginde = ClientReGINde()
        uff = reginde.cerca_ufficio_giudiziario(nome_o_codice)
        return uff.codice if uff else nome_o_codice

    # ---------------------------------------------------------------- Parser risposte SOAP

    def _parse_fascicoli(self, risposta: Any) -> List[FascicoloPolisWeb]:
        """Converte la risposta SOAP in lista di FascicoloPolisWeb."""
        fascicoli = []
        try:
            items = risposta.fascicoli or risposta.fascicolo or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                f = FascicoloPolisWeb(
                    numero_rg=str(getattr(item, "numeroRG", "") or ""),
                    anno_rg=int(getattr(item, "annoRG", 0) or 0),
                    ruolo=str(getattr(item, "ruolo", "CIVILE_COGNIZIONE") or ""),
                    stato=str(getattr(item, "stato", "PENDENTE") or ""),
                    oggetto=str(getattr(item, "oggetto", "") or ""),
                    sezione=str(getattr(item, "sezione", "") or ""),
                    giudice=str(getattr(item, "giudice", "") or ""),
                    data_iscrizione=_parse_data(getattr(item, "dataIscrizione", None)),
                    data_udienza=_parse_data(getattr(item, "dataUdienza", None)),
                    parti=_parse_parti(getattr(item, "parti", None)),
                    codice_ufficio=str(getattr(item, "codiceUfficio", "") or ""),
                    nome_ufficio=str(getattr(item, "nomeUfficio", "") or ""),
                )
                fascicoli.append(f)
        except (AttributeError, TypeError, ValueError):
            pass
        return fascicoli

    def _parse_documenti(self, risposta: Any) -> List[DocumentoPolisWeb]:
        """Converte la risposta SOAP in lista di DocumentoPolisWeb."""
        documenti = []
        try:
            items = risposta.documenti or risposta.documento or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                d = DocumentoPolisWeb(
                    id_documento=str(getattr(item, "idDocumento", "") or ""),
                    nome=str(getattr(item, "nomeFile", "") or ""),
                    tipo=str(getattr(item, "tipoDocumento", "ATTO") or ""),
                    data_deposito=_parse_data(getattr(item, "dataDeposito", None)),
                    mittente=str(getattr(item, "mittente", "") or ""),
                    dimensione_bytes=int(getattr(item, "dimensione", 0) or 0),
                    disponibile=bool(getattr(item, "disponibile", True)),
                )
                documenti.append(d)
        except (AttributeError, TypeError, ValueError):
            pass
        return documenti


# ================================================================ Demo / offline

class ClientPolisWebDemo(ClientPolisWeb):
    """
    Implementazione demo (offline) per sviluppo e test senza connessione PST.
    Restituisce dati fittizi verosimili.
    """

    def _nome_ufficio_demo(self, codice_o_nome: str) -> str:
        try:
            import os
            from pct.uffici_giudiziari import get_gestore
            gestore = get_gestore(os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"))
            uff = next((u for u in gestore.carica() if u.get("codice") == codice_o_nome), None)
            return uff["nome"] if uff else f"Ufficio {codice_o_nome}"
        except Exception:
            return f"Ufficio {codice_o_nome}"

    def __init__(self):
        # Non richiede certificato
        self.p12_path = ""
        self.p12_password = b""
        self.cf_avvocato = "DEMO"
        self.timeout = 5
        self._zeep_cache = {}

    def ricerca_fascicoli(self, tribunale: str, numero_rg=None,
                          anno_rg=None, nome_parte=None,
                          codice_fiscale_parte=None,
                          max_risultati: int = 50) -> List[FascicoloPolisWeb]:
        """Ritorna fascicoli demo."""
        anno = anno_rg or date.today().year
        return [
            FascicoloPolisWeb(
                numero_rg=numero_rg or "1234",
                anno_rg=anno,
                ruolo="CIVILE_COGNIZIONE",
                stato="PENDENTE",
                oggetto="Causa di risarcimento danni — Demo",
                sezione="Prima sezione civile",
                giudice="Dr. Mario Rossi",
                data_iscrizione=f"{anno}-01-15",
                data_udienza=f"{date.today().year + (1 if date.today().month >= 10 else 0)}-03-20",
                parti=["Mario Bianchi", "Alfa S.p.A."],
                note="Dato demo — collegare al PST con certificato reale",
                codice_ufficio=tribunale if tribunale.isdigit() else "0000000",
                nome_ufficio=self._nome_ufficio_demo(tribunale),
            )
        ]

    def consulta_documenti(self, codice_ufficio, numero_rg, anno_rg) -> List[DocumentoPolisWeb]:
        return [
            DocumentoPolisWeb(
                id_documento="DEMO-001",
                nome="atto_citazione.pdf.p7m",
                tipo="ATTO",
                data_deposito=f"{anno_rg}-01-15",
                mittente="avv.demo@pec.it",
                dimensione_bytes=245760,
            ),
            DocumentoPolisWeb(
                id_documento="DEMO-002",
                nome="memoria_difensiva.pdf.p7m",
                tipo="MEMORIA",
                data_deposito=f"{anno_rg}-03-10",
                mittente="avv.controparte@pec.it",
                dimensione_bytes=189440,
            ),
        ]


# ================================================================ Utils

def _parse_data(valore: Any) -> str:
    """Converte una data SOAP in stringa ISO YYYY-MM-DD."""
    if not valore:
        return ""
    if isinstance(valore, (datetime, date)):
        return valore.strftime("%Y-%m-%d")
    return str(valore)[:10]


def _parse_parti(valore: Any) -> List[str]:
    """Estrae la lista delle parti dalla risposta SOAP."""
    if not valore:
        return []
    if isinstance(valore, list):
        return [str(p) for p in valore]
    if hasattr(valore, "parte"):
        parti = valore.parte
        if not isinstance(parti, list):
            parti = [parti]
        return [str(p.nominativo or p) for p in parti]
    return [str(valore)]


def crea_client(
    p12_path: Optional[str] = None,
    p12_password: Optional[bytes] = None,
    cf_avvocato: str = "",
    demo: bool = False,
) -> ClientPolisWeb:
    """
    Factory: crea il client PolisWeb appropriato.

    Args:
        p12_path:      Percorso al P12 (None = usa PCT_FIRMA_P12 da env).
        p12_password:  Password P12 (None = usa PCT_FIRMA_PASSWORD da env).
        cf_avvocato:   Codice fiscale avvocato (None = usa PCT_CF_AVVOCATO da env).
        demo:          True = usa ClientPolisWebDemo (no connessione reale).

    Returns:
        ClientPolisWeb o ClientPolisWebDemo.
    """
    if demo:
        return ClientPolisWebDemo()

    p12  = p12_path     or os.getenv("PCT_FIRMA_P12", "")
    pwd  = p12_password or os.getenv("PCT_FIRMA_PASSWORD", "").encode()
    cf   = cf_avvocato  or os.getenv("PCT_CF_AVVOCATO", "")

    if not p12 or not os.path.exists(p12):
        raise FileNotFoundError(
            f"Certificato P12 non trovato: {p12!r}. "
            "Configurare PCT_FIRMA_P12 nel file .env"
        )
    return ClientPolisWeb(p12_path=p12, p12_password=pwd, codice_fiscale_avvocato=cf)
