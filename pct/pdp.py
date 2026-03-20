"""
pct/pdp.py — Integrazione con il Portale Deposito Atti Penale (PDP)
               e il Sistema SNT (Sistema Notifiche Telematiche) del MinGiust.

Offre:
  A) CONSULTAZIONE fascicoli penali (RGNR, RG Dibattimento, GIP/GUP)
  B) IMPORTAZIONE pratiche penali nel gestionale locale

Riferimenti normativi:
  - D.Lgs. 150/2022 (Riforma Cartabia) — art. 87 e ss.
  - D.M. 217/2023 — regole tecniche PCT penale
  - Provvedimento DGSIA del 14/11/2023

Il PDP usa le stesse credenziali CNS/smart-card del PCT civile (stesso P12/PEM).
In modalità demo restituisce dati fittizi senza richiedere connessione.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- PDP endpoints
_PDP_BASE             = os.getenv("PCT_PDP_BASE_URL", "https://appweb.giustizia.it/snt")
_WSDL_RICERCA_PENALE  = f"{_PDP_BASE}/RicercaFascicoliPenaleService?wsdl"
_WSDL_CONSULTA_PENALE = f"{_PDP_BASE}/ConsultazioneDocumentiPenaleService?wsdl"


# ================================================================ Dataclass risultati

@dataclass
class FascicoloPDP:
    """Pratica penale trovata nel registro del tribunale tramite PDP/SNT."""
    numero_rg: str
    anno_rg: int
    tipo_registro: str          # RGNR | RG | RGES | GIP | GUP | DIBATTIMENTO
    fase: str                   # INDAGINI | UDIENZA_PRELIMINARE | DIBATTIMENTO | APPELLO | ESECUZIONE
    stato: str                  # PENDENTE | DEFINITO | ARCHIVIATO | SOSPESO
    reato: str = ""             # descrizione sintetica del reato/imputazione
    sezione: str = ""
    giudice: str = ""
    data_iscrizione: str = ""   # YYYY-MM-DD
    data_udienza: str = ""      # prossima udienza
    imputati: List[str] = field(default_factory=list)
    parti_offese: List[str] = field(default_factory=list)
    note: str = ""
    codice_ufficio: str = ""
    nome_ufficio: str = ""


@dataclass
class DocumentoPDP:
    """Documento presente nel fascicolo telematico penale."""
    id_documento: str
    nome: str
    tipo: str                   # ATTO | MEMORIA | SENTENZA | DECRETO | ORDINANZA | RICHIESTA
    data_deposito: str          # YYYY-MM-DD
    mittente: str
    dimensione_bytes: int = 0
    disponibile: bool = True


@dataclass
class RisultatoImportazionePDP:
    """Esito dell'importazione di una pratica penale da PDP."""
    successo: bool
    id_fascicolo_locale: Optional[str] = None
    messaggio: str = ""
    fascicolo_pdp: Optional[FascicoloPDP] = None
    avvisi: List[str] = field(default_factory=list)


# ================================================================ Client PDP

class ClientPDP:
    """
    Client per l'accesso al Portale Deposito Atti Penale (PDP) / SNT.
    Usa le stesse credenziali del PCT civile (P12 o PEM).
    """

    def __init__(
        self,
        p12_path: str = "",
        p12_password: bytes = b"",
        codice_fiscale_avvocato: str = "",
        timeout: int = 30,
        cert_pem_path: str = "",
        key_pem_path: str = "",
        key_pem_password: Optional[bytes] = None,
    ):
        self.p12_path         = p12_path
        self.p12_password     = p12_password
        self.cert_pem_path    = cert_pem_path
        self.key_pem_path     = key_pem_path
        self.key_pem_password = key_pem_password
        self.cf_avvocato      = codice_fiscale_avvocato.upper()
        self.timeout          = timeout
        self._zeep_cache: Dict[str, Any] = {}

    # ---------------------------------------------------------------- Ricerca

    def ricerca_fascicoli(
        self,
        ufficio: str,
        numero_rg: Optional[str] = None,
        anno_rg: Optional[int] = None,
        nome_imputato: Optional[str] = None,
        tipo_registro: Optional[str] = None,
        max_risultati: int = 50,
    ) -> List[FascicoloPDP]:
        """
        Cerca fascicoli penali nel registro del tribunale tramite PDP SOAP.

        Args:
            ufficio:       Codice o nome dell'ufficio giudiziario.
            numero_rg:     Numero RG (RGNR o RG dibattimento).
            anno_rg:       Anno RG.
            nome_imputato: Nome/cognome dell'imputato.
            tipo_registro: RGNR | RG | GIP | GUP | DIBATTIMENTO (None = tutti).
            max_risultati: Numero massimo di risultati.
        """
        client = self._get_client(_WSDL_RICERCA_PENALE)
        req: Dict[str, Any] = {
            "codiceFiscaleAvvocato": self.cf_avvocato,
            "codiceUfficio":         self._risolvi_codice(ufficio),
            "maxRisultati":          max_risultati,
        }
        if numero_rg:     req["numeroRG"]          = numero_rg
        if anno_rg:       req["annoRG"]             = anno_rg
        if nome_imputato: req["nominativoImputato"] = nome_imputato
        if tipo_registro: req["tipoRegistro"]       = tipo_registro
        try:
            risposta = client.service.ricercaFascicoliPenale(**req)
        except Exception as e:
            raise ConnectionError(f"Errore PDP: {e}") from e
        return self._parse_fascicoli(risposta)

    # ---------------------------------------------------------------- Documenti

    def consulta_documenti(
        self,
        codice_ufficio: str,
        numero_rg: str,
        anno_rg: int,
    ) -> List[DocumentoPDP]:
        """Recupera l'elenco dei documenti del fascicolo penale."""
        client = self._get_client(_WSDL_CONSULTA_PENALE)
        try:
            risposta = client.service.consultaDocumentiPenale(
                codiceFiscaleAvvocato=self.cf_avvocato,
                codiceUfficio=codice_ufficio,
                numeroRG=numero_rg,
                annoRG=anno_rg,
            )
        except Exception as e:
            raise ConnectionError(f"Errore consultazione PDP: {e}") from e
        return self._parse_documenti(risposta)

    # ---------------------------------------------------------------- Import

    def importa_fascicolo(
        self,
        fascicolo_pdp: FascicoloPDP,
        gestione_fascicoli,
        gestione_clienti,
        avvocato_referente: str = "",
    ) -> RisultatoImportazionePDP:
        """Importa una pratica penale come nuovo Fascicolo nel gestionale."""
        try:
            from pct.fascicoli import TipoFascicolo, StatoFascicolo, TipoAttivita

            stato_map = {
                "PENDENTE":   StatoFascicolo.IN_CORSO,
                "DEFINITO":   StatoFascicolo.DEFINITO,
                "ARCHIVIATO": StatoFascicolo.ARCHIVIATO,
                "SOSPESO":    StatoFascicolo.SOSPESO,
            }
            stato = stato_map.get(fascicolo_pdp.stato.upper(), StatoFascicolo.APERTO)

            id_cliente = ""
            nome_cliente = ""
            if fascicolo_pdp.imputati:
                nome = fascicolo_pdp.imputati[0]
                for c in gestione_clienti.tutti():
                    if nome.upper() in c.nome_completo.upper():
                        id_cliente   = c.id
                        nome_cliente = c.nome_completo
                        break

            reato_breve = (fascicolo_pdp.reato[:80]
                           if fascicolo_pdp.reato
                           else f"Proc. {fascicolo_pdp.tipo_registro}")
            fasc = gestione_fascicoli.crea(
                titolo=f"RG {fascicolo_pdp.numero_rg}/{fascicolo_pdp.anno_rg} — {reato_breve}",
                tipo=TipoFascicolo.PENALE,
                id_cliente=id_cliente,
                nome_cliente=nome_cliente,
                tribunale=fascicolo_pdp.nome_ufficio,
                numero_rg=fascicolo_pdp.numero_rg,
                anno_rg=fascicolo_pdp.anno_rg,
                sezione=fascicolo_pdp.sezione,
                giudice=fascicolo_pdp.giudice,
                oggetto=fascicolo_pdp.reato,
                stato=stato,
                avvocato_referente=avvocato_referente,
                data_apertura=fascicolo_pdp.data_iscrizione or date.today().isoformat(),
                note=fascicolo_pdp.note or f"Importato da PDP il {date.today()}",
            )

            avvisi = []
            if fascicolo_pdp.data_udienza:
                try:
                    gestione_fascicoli.aggiungi_attivita(
                        fasc.id,
                        tipo=TipoAttivita.UDIENZA,
                        data=fascicolo_pdp.data_udienza,
                        titolo="Udienza penale (importata da PDP)",
                        avvocato=avvocato_referente,
                    )
                except Exception as ex:
                    avvisi.append(f"Udienza non importata: {ex}")

            if not id_cliente:
                avvisi.append(
                    "Nessun cliente trovato in anagrafica per l'imputato. "
                    "Assegnare il cliente manualmente."
                )

            return RisultatoImportazionePDP(
                successo=True,
                id_fascicolo_locale=fasc.id,
                messaggio=f"Pratica penale RG {fascicolo_pdp.numero_rg}/{fascicolo_pdp.anno_rg} importata.",
                fascicolo_pdp=fascicolo_pdp,
                avvisi=avvisi,
            )

        except Exception as e:
            return RisultatoImportazionePDP(
                successo=False,
                messaggio=f"Errore durante l'importazione: {e}",
                fascicolo_pdp=fascicolo_pdp,
            )

    # ---------------------------------------------------------------- SOAP helpers

    def _get_client(self, wsdl_url: str):
        if wsdl_url in self._zeep_cache:
            return self._zeep_cache[wsdl_url]
        try:
            import zeep
            import zeep.transports
            from requests import Session
        except ImportError:
            raise ImportError("Installa zeep: pip install zeep")

        session = Session()
        base = "https://appweb.giustizia.it"

        usa_pem = (
            self.cert_pem_path and self.key_pem_path
            and os.path.exists(self.cert_pem_path)
            and os.path.exists(self.key_pem_path)
        )
        if usa_pem:
            session.cert = (self.cert_pem_path, self.key_pem_path)
        elif self.p12_path and os.path.exists(self.p12_path):
            try:
                from requests_pkcs12 import Pkcs12Adapter
            except ImportError:
                raise ImportError("Installa requests-pkcs12: pip install requests-pkcs12")
            session.mount(
                base,
                Pkcs12Adapter(
                    pkcs12_filename=self.p12_path,
                    pkcs12_password=self.p12_password,
                ),
            )
        else:
            raise FileNotFoundError(
                "Nessun certificato disponibile per il PDP Penale. "
                "Configurare PCT_FIRMA_P12 oppure PCT_FIRMA_CERT + PCT_FIRMA_KEY."
            )

        transport = zeep.transports.Transport(session=session, timeout=self.timeout)
        client = zeep.Client(wsdl=wsdl_url, transport=transport)
        self._zeep_cache[wsdl_url] = client
        return client

    def _risolvi_codice(self, nome_o_codice: str) -> str:
        from pct.reginde import ClientReGINde
        if nome_o_codice.isdigit():
            return nome_o_codice
        r = ClientReGINde()
        uff = r.cerca_ufficio_giudiziario(nome_o_codice)
        return uff.codice if uff else nome_o_codice

    def _parse_fascicoli(self, risposta: Any) -> List[FascicoloPDP]:
        fascicoli = []
        try:
            items = risposta.fascicoli or risposta.fascicolo or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                fascicoli.append(FascicoloPDP(
                    numero_rg=str(getattr(item, "numeroRG", "") or ""),
                    anno_rg=int(getattr(item, "annoRG", 0) or 0),
                    tipo_registro=str(getattr(item, "tipoRegistro", "RGNR") or ""),
                    fase=str(getattr(item, "fase", "INDAGINI") or ""),
                    stato=str(getattr(item, "stato", "PENDENTE") or ""),
                    reato=str(getattr(item, "reato", "") or ""),
                    sezione=str(getattr(item, "sezione", "") or ""),
                    giudice=str(getattr(item, "giudice", "") or ""),
                    data_iscrizione=_parse_data(getattr(item, "dataIscrizione", None)),
                    data_udienza=_parse_data(getattr(item, "dataUdienza", None)),
                    imputati=_parse_lista(getattr(item, "imputati", None)),
                    parti_offese=_parse_lista(getattr(item, "partiOffese", None)),
                    codice_ufficio=str(getattr(item, "codiceUfficio", "") or ""),
                    nome_ufficio=str(getattr(item, "nomeUfficio", "") or ""),
                ))
        except (AttributeError, TypeError, ValueError):
            pass
        return fascicoli

    def _parse_documenti(self, risposta: Any) -> List[DocumentoPDP]:
        docs = []
        try:
            items = risposta.documenti or risposta.documento or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                docs.append(DocumentoPDP(
                    id_documento=str(getattr(item, "idDocumento", "") or ""),
                    nome=str(getattr(item, "nomeFile", "") or ""),
                    tipo=str(getattr(item, "tipoDocumento", "ATTO") or ""),
                    data_deposito=_parse_data(getattr(item, "dataDeposito", None)),
                    mittente=str(getattr(item, "mittente", "") or ""),
                    dimensione_bytes=int(getattr(item, "dimensione", 0) or 0),
                    disponibile=bool(getattr(item, "disponibile", True)),
                ))
        except (AttributeError, TypeError, ValueError):
            pass
        return docs


# ================================================================ Demo / offline

class ClientPDPDemo(ClientPDP):
    """Implementazione demo (offline) per PDP Penale — dati fittizi."""

    def __init__(self):
        self.p12_path         = ""
        self.p12_password     = b""
        self.cf_avvocato      = "DEMO"
        self.timeout          = 5
        self._zeep_cache      = {}
        self.cert_pem_path    = ""
        self.key_pem_path     = ""
        self.key_pem_password = None

    def _nome_ufficio_demo(self, codice: str) -> str:
        try:
            from pct.uffici_giudiziari import get_gestore
            gestore = get_gestore(os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"))
            uff = next((u for u in gestore.carica() if u.get("codice") == codice), None)
            return uff["nome"] if uff else f"Ufficio {codice}"
        except Exception:
            return f"Ufficio {codice}"

    def ricerca_fascicoli(
        self, ufficio, numero_rg=None, anno_rg=None,
        nome_imputato=None, tipo_registro=None, max_risultati=50
    ) -> List[FascicoloPDP]:
        anno = anno_rg or date.today().year
        anno_ud = date.today().year + (1 if date.today().month >= 10 else 0)
        return [
            FascicoloPDP(
                numero_rg=numero_rg or "4521",
                anno_rg=anno,
                tipo_registro=tipo_registro or "RGNR",
                fase="DIBATTIMENTO",
                stato="PENDENTE",
                reato="Art. 640 c.p. — Truffa aggravata — Demo",
                sezione="Quarta sezione penale",
                giudice="Dr.ssa Anna Ferrari",
                data_iscrizione=f"{anno}-03-10",
                data_udienza=f"{anno_ud}-05-14",
                imputati=["Verdi Giuseppe"],
                parti_offese=["Bianchi Mario"],
                note="Dato demo — collegare al PDP con certificato reale",
                codice_ufficio=ufficio if ufficio.isdigit() else "0000000",
                nome_ufficio=self._nome_ufficio_demo(ufficio) if ufficio.isdigit() else ufficio,
            )
        ]

    def consulta_documenti(self, codice_ufficio, numero_rg, anno_rg) -> List[DocumentoPDP]:
        return [
            DocumentoPDP("DEMO-P001", "richiesta_rinvio_giudizio.pdf.p7m", "RICHIESTA",
                         f"{anno_rg}-03-10", "pm.demo@pec.it", 189440),
            DocumentoPDP("DEMO-P002", "decreto_che_dispone_giudizio.pdf.p7m", "DECRETO",
                         f"{anno_rg}-04-22", "cancelleria.penale@pec.it", 95000),
            DocumentoPDP("DEMO-P003", "memoria_difensiva.pdf.p7m", "MEMORIA",
                         f"{anno_rg}-05-01", "avv.demo@pec.it", 134000),
        ]


# ================================================================ Utils

def _parse_data(valore: Any) -> str:
    if not valore:
        return ""
    if isinstance(valore, (datetime, date)):
        return valore.strftime("%Y-%m-%d")
    return str(valore)[:10]


def _parse_lista(valore: Any) -> List[str]:
    if not valore:
        return []
    if isinstance(valore, list):
        return [str(v) for v in valore]
    # Struttura SOAP con sotto-elemento 'imputato' o 'parte'
    for attr in ("imputato", "parte", "soggetto"):
        if hasattr(valore, attr):
            items = getattr(valore, attr)
            if not isinstance(items, list):
                items = [items]
            return [str(getattr(i, "nominativo", i)) for i in items]
    return [str(valore)]


def crea_client_pdp(demo: bool = False) -> ClientPDP:
    """Factory: restituisce ClientPDP o ClientPDPDemo."""
    if demo:
        return ClientPDPDemo()
    cf  = os.getenv("PCT_CF_AVVOCATO", "")
    p12 = os.getenv("PCT_FIRMA_P12", "")
    pwd = os.getenv("PCT_FIRMA_PASSWORD", "").encode()
    if p12 and os.path.exists(p12):
        return ClientPDP(p12_path=p12, p12_password=pwd, codice_fiscale_avvocato=cf)
    cert = os.getenv("PCT_FIRMA_CERT", "")
    key  = os.getenv("PCT_FIRMA_KEY", "")
    if cert and key and os.path.exists(cert) and os.path.exists(key):
        key_pwd_str = os.getenv("PCT_FIRMA_KEY_PASSWORD", "")
        return ClientPDP(
            cert_pem_path=cert, key_pem_path=key,
            key_pem_password=key_pwd_str.encode() if key_pwd_str else None,
            codice_fiscale_avvocato=cf,
        )
    raise FileNotFoundError(
        "Nessun certificato configurato per il PDP Penale.\n"
        "Usare le stesse credenziali del PCT civile: PCT_FIRMA_P12 oppure "
        "PCT_FIRMA_CERT + PCT_FIRMA_KEY."
    )
