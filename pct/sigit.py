"""
pct/sigit.py — Integrazione con il PTT (Processo Tributario Telematico)
               e SIGIT (Sistema Informativo della Giustizia Tributaria - MEF).

Offre:
  A) CONSULTAZIONE fascicoli tributari (CPT - Corte di Giustizia Tributaria
     di primo grado, CGT - Corte di Giustizia Tributaria di secondo grado)
  B) IMPORTAZIONE pratiche tributarie nel gestionale locale

Riferimenti normativi:
  - D.Lgs. 546/1992 (Codice del Processo Tributario) — artt. 16-bis e ss.
  - D.M. 23 dicembre 2013, n. 163 (Regolamento PTT)
  - D.Lgs. 24 settembre 2015, n. 156 (Riforma processo tributario)
  - D.Lgs. 130/2022 (Riforma giustizia tributaria — CTP→CPT, CTR→CGT)
  - Provvedimento MEF 4 aprile 2014 (regole tecniche PTT)

Accesso: tramite dispositivo CNS/CIE oppure credenziali SPID (livello 2).
In modalità demo restituisce dati fittizi senza richiedere connessione.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pct.portal_direct_guard import ensure_direct_portal_verified

# ---------------------------------------------------------------- SIGIT / PTT endpoints
_SIGIT_BASE             = os.getenv("PCT_SIGIT_BASE_URL", "https://sigit.finanze.it/ptt")
_WSDL_RICERCA_TRIB      = f"{_SIGIT_BASE}/RicercaFascicoliTributarioService?wsdl"
_WSDL_CONSULTA_TRIB     = f"{_SIGIT_BASE}/ConsultazioneDocumentiTributarioService?wsdl"


# ================================================================ Dataclass risultati

@dataclass
class FascicoloSIGIT:
    """Pratica tributaria trovata nel registro SIGIT tramite PTT."""
    numero_rgt: str
    anno_rgt: int
    tipo: str                   # RICORSO | APPELLO | OPPOSIZIONE | OTTEMPERANZA | REVOCAZIONE
    stato: str                  # PENDENTE | DEFINITO | SOSPESO | ESTINTO | RINVIATO
    materia: str = ""           # IVA | IRPEF | IRAP | IMU | REGISTRO | ACCISA | ALTRO
    sezione: str = ""
    giudice_relatore: str = ""
    data_deposito: str = ""     # YYYY-MM-DD — data deposito ricorso
    data_udienza: str = ""      # prossima udienza
    ricorrenti: List[str] = field(default_factory=list)
    resistenti: List[str] = field(default_factory=list)   # Agenzia Entrate, Ente locale, ecc.
    oggetto_controversia: str = ""
    valore_controversia: float = 0.0
    note: str = ""
    codice_commissione: str = ""
    nome_commissione: str = ""


@dataclass
class DocumentoSIGIT:
    """Documento presente nel fascicolo telematico tributario."""
    id_documento: str
    nome: str
    tipo: str                   # RICORSO | APPELLO | MEMORIA | CONTRODEDUZIONI |
                                # ISTANZA_SOSPENSIVA | REPLICA | CONCLUSIONI |
                                # SENTENZA | ORDINANZA | DECRETO | ALLEGATO
    data_deposito: str          # YYYY-MM-DD
    mittente: str
    dimensione_bytes: int = 0
    disponibile: bool = True
    # Raggruppamento per busta/deposito (tutti i file della stessa busta condividono id_deposito)
    id_deposito: str = ""       # identificativo univoco della busta telematica
    tipo_atto: str = ""         # tipo atto della busta (es. "Ricorso", "Memoria", "Sentenza")


@dataclass
class RisultatoImportazioneSIGIT:
    """Esito dell'importazione di una pratica tributaria da SIGIT."""
    successo: bool
    id_fascicolo_locale: Optional[str] = None
    messaggio: str = ""
    fascicolo_sigit: Optional[FascicoloSIGIT] = None
    avvisi: List[str] = field(default_factory=list)


# ================================================================ Client SIGIT

class ClientSIGIT:
    """
    Client per l'accesso al PTT (Processo Tributario Telematico) / SIGIT.
    Usa le stesse credenziali CNS/CIE del PCT civile (P12 o PEM).
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
        commissione: str,
        numero_rgt: Optional[str] = None,
        anno_rgt: Optional[int] = None,
        nome_ricorrente: Optional[str] = None,
        tipo: Optional[str] = None,
        max_risultati: int = 50,
    ) -> List[FascicoloSIGIT]:
        """
        Cerca fascicoli tributari nel SIGIT tramite SOAP.

        Args:
            commissione:    Codice o nome della Corte di Giustizia Tributaria.
            numero_rgt:     Numero RGT (Registro Generale Tributario).
            anno_rgt:       Anno RGT.
            nome_ricorrente: Nome/cognome del ricorrente.
            tipo:           RICORSO | APPELLO | OPPOSIZIONE | OTTEMPERANZA (None = tutti).
            max_risultati:  Numero massimo di risultati.
        """
        ensure_direct_portal_verified("ptt")
        client = self._get_client(_WSDL_RICERCA_TRIB)
        req: Dict[str, Any] = {
            "codiceFiscaleAvvocato": self.cf_avvocato,
            "codiceCommissione":     self._risolvi_codice(commissione),
            "maxRisultati":          max_risultati,
        }
        if numero_rgt:     req["numeroRGT"]          = numero_rgt
        if anno_rgt:       req["annoRGT"]             = anno_rgt
        if nome_ricorrente: req["nominativoRicorrente"] = nome_ricorrente
        if tipo:           req["tipoRicorso"]          = tipo
        try:
            risposta = client.service.ricercaFascicoliTributari(**req)
        except Exception as e:
            raise ConnectionError(f"Errore SIGIT: {e}") from e
        return self._parse_fascicoli(risposta)

    # ---------------------------------------------------------------- Documenti

    def consulta_documenti(
        self,
        codice_commissione: str,
        numero_rgt: str,
        anno_rgt: int,
    ) -> List[DocumentoSIGIT]:
        """Recupera l'elenco dei documenti del fascicolo tributario."""
        ensure_direct_portal_verified("ptt")
        client = self._get_client(_WSDL_CONSULTA_TRIB)
        try:
            risposta = client.service.consultaDocumentiTributari(
                codiceFiscaleAvvocato=self.cf_avvocato,
                codiceCommissione=codice_commissione,
                numeroRGT=numero_rgt,
                annoRGT=anno_rgt,
            )
        except Exception as e:
            raise ConnectionError(f"Errore consultazione SIGIT: {e}") from e
        return self._parse_documenti(risposta)

    # ---------------------------------------------------------------- Import

    def importa_fascicolo(
        self,
        fascicolo_sigit: FascicoloSIGIT,
        gestione_fascicoli,
        gestione_clienti,
        avvocato_referente: str = "",
    ) -> RisultatoImportazioneSIGIT:
        """Importa una pratica tributaria come nuovo Fascicolo nel gestionale."""
        try:
            from pct.fascicoli import (
                TipoFascicolo,
                StatoFascicolo,
                TipoAttivita,
                stato_fascicolo_da_descrizione_portale,
            )

            stato = stato_fascicolo_da_descrizione_portale(
                fascicolo_sigit.stato,
                default=StatoFascicolo.APERTO,
            )

            # Cerca cliente in anagrafica
            id_cliente = ""
            nome_cliente = ""
            if fascicolo_sigit.ricorrenti:
                nome = fascicolo_sigit.ricorrenti[0]
                for c in gestione_clienti.tutti():
                    if nome.upper() in c.nome_completo.upper():
                        id_cliente   = c.id
                        nome_cliente = c.nome_completo
                        break

            oggetto_breve = (
                fascicolo_sigit.oggetto_controversia[:80]
                if fascicolo_sigit.oggetto_controversia
                else f"{fascicolo_sigit.tipo} — {fascicolo_sigit.materia or 'Tributario'}"
            )

            # Prova TipoFascicolo.TRIBUTARIO, fallback ALTRO
            try:
                tipo_fasc = TipoFascicolo.TRIBUTARIO
            except AttributeError:
                tipo_fasc = TipoFascicolo.ALTRO

            fasc = gestione_fascicoli.nuovo(
                titolo=f"RGT {fascicolo_sigit.numero_rgt}/{fascicolo_sigit.anno_rgt} — {oggetto_breve}",
                tipo=tipo_fasc,
                id_cliente=id_cliente,
                nome_cliente=nome_cliente,
                tribunale=fascicolo_sigit.nome_commissione,
                numero_rg=fascicolo_sigit.numero_rgt,
                anno_rg=fascicolo_sigit.anno_rgt,
                sezione=fascicolo_sigit.sezione,
                giudice=fascicolo_sigit.giudice_relatore,
                oggetto=fascicolo_sigit.oggetto_controversia,
                stato=stato,
                avvocato_referente=avvocato_referente,
                data_apertura=fascicolo_sigit.data_deposito or date.today().isoformat(),
                note=(
                    fascicolo_sigit.note
                    or f"Importato da SIGIT/PTT il {date.today()} — materia: {fascicolo_sigit.materia}"
                ),
            )

            avvisi = []
            if fascicolo_sigit.data_udienza:
                try:
                    gestione_fascicoli.aggiungi_attivita(
                        fasc.id,
                        tipo=TipoAttivita.UDIENZA,
                        data=fascicolo_sigit.data_udienza,
                        titolo="Udienza tributaria (importata da SIGIT)",
                        avvocato=avvocato_referente,
                    )
                except Exception as ex:
                    avvisi.append(f"Udienza non importata: {ex}")

            if not id_cliente:
                avvisi.append(
                    "Nessun cliente trovato in anagrafica per il ricorrente. "
                    "Assegnare il cliente manualmente."
                )

            return RisultatoImportazioneSIGIT(
                successo=True,
                id_fascicolo_locale=fasc.id,
                messaggio=(
                    f"Pratica tributaria RGT {fascicolo_sigit.numero_rgt}/"
                    f"{fascicolo_sigit.anno_rgt} importata."
                ),
                fascicolo_sigit=fascicolo_sigit,
                avvisi=avvisi,
            )

        except Exception as e:
            return RisultatoImportazioneSIGIT(
                successo=False,
                messaggio=f"Errore durante l'importazione: {e}",
                fascicolo_sigit=fascicolo_sigit,
            )

    # ---------------------------------------------------------------- Deposito atti

    def deposita_atto(
        self,
        codice_commissione: str,
        tipo_atto: str,
        atto_path: str,
        numero_rgt: str = "",
        anno_rgt: int = 0,
        oggetto: str = "",
    ) -> dict:
        """
        Deposita un atto tributario al PTT (sigit.finanze.it).

        Flusso PTT:
          POST {SIGIT_BASE}/depositi  (multipart/form-data, mTLS)
          Response: { "codiceEsito": "0", "idDeposito": "...", "stato": "INVIATO" }

        Successivamente il sistema invia via PEC:
          - Ricevuta accettazione (fase 4)
          - Esito controlli automatici (fase 5/6)
          - Esito segreteria commissione (fase 7)

        Args:
            codice_commissione: Codice MEF della commissione destinataria
            tipo_atto: Tipo atto (es. RICORSO, MEMORIA, CONTRODEDUZIONI, REPLICA)
            atto_path: Percorso al file firmato (.pdf.p7m)
            numero_rgt, anno_rgt: Riferimento procedimento (opz. per nuovi ricorsi)
            oggetto: Descrizione sintetica dell'atto
        """
        ensure_direct_portal_verified("ptt")
        import uuid
        from pathlib import Path

        if not Path(atto_path).exists():
            return {
                "codiceEsito": "E_FILE",
                "descrizioneEsito": f"File non trovato: {atto_path}",
                "stato": "ERRORE",
            }

        try:
            import requests
            from requests import Session

            session = Session()
            if self.cert_pem_path and self.key_pem_path:
                session.cert = (self.cert_pem_path, self.key_pem_path)
            elif self.p12_path and os.path.exists(self.p12_path):
                try:
                    from requests_pkcs12 import Pkcs12Adapter
                    session.mount(
                        "https://sigit.finanze.it",
                        Pkcs12Adapter(
                            pkcs12_filename=self.p12_path,
                            pkcs12_password=self.p12_password,
                        ),
                    )
                except ImportError:
                    raise ImportError("Installa requests-pkcs12: pip install requests-pkcs12")

            with open(atto_path, "rb") as f:
                files = {"atto": (Path(atto_path).name, f, "application/octet-stream")}
                data = {
                    "codiceFiscaleAvvocato": self.cf_avvocato,
                    "codiceCommissione":     codice_commissione,
                    "tipoAtto":              tipo_atto,
                    "oggetto":               oggetto,
                }
                if numero_rgt:
                    data["numeroRGT"] = numero_rgt
                if anno_rgt:
                    data["annoRGT"] = str(anno_rgt)

                resp = session.post(
                    f"{_SIGIT_BASE}/depositi",
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            return {
                "codiceEsito": "E_CONN",
                "descrizioneEsito": f"Errore connessione SIGIT: {e}",
                "stato": "ERRORE",
            }

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
        base = "https://sigit.finanze.it"

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
                "Nessun certificato disponibile per il PTT/SIGIT. "
                "Configurare PCT_FIRMA_P12 oppure PCT_FIRMA_CERT + PCT_FIRMA_KEY."
            )

        transport = zeep.transports.Transport(session=session, timeout=self.timeout)
        client = zeep.Client(wsdl=wsdl_url, transport=transport)
        self._zeep_cache[wsdl_url] = client
        return client

    def _risolvi_codice(self, nome_o_codice: str) -> str:
        valore = (nome_o_codice or "").strip()
        if not valore:
            return ""
        if valore.isdigit() or valore.upper().startswith(("CPT", "CGT")):
            return valore
        # Ricerca nel bundle uffici (TAR/CGT non coperti da ReGINde)
        try:
            from pct.uffici_giudiziari import get_gestore
            gestore = get_gestore(os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"))
            uffici = gestore.carica()
            uff = next((u for u in uffici if u.get("codice", "").upper() == valore.upper()), None)
            if not uff:
                uff = next((u for u in uffici if valore.lower() in u.get("nome", "").lower()), None)
            return uff["codice"] if uff else valore
        except Exception:
            return valore

    def _parse_fascicoli(self, risposta: Any) -> List[FascicoloSIGIT]:
        fascicoli = []
        try:
            items = risposta.fascicoli or risposta.fascicolo or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                fascicoli.append(FascicoloSIGIT(
                    numero_rgt=str(getattr(item, "numeroRGT", "") or ""),
                    anno_rgt=int(getattr(item, "annoRGT", 0) or 0),
                    tipo=str(getattr(item, "tipoRicorso", "RICORSO") or ""),
                    stato=str(getattr(item, "stato", "PENDENTE") or ""),
                    materia=str(getattr(item, "materia", "") or ""),
                    sezione=str(getattr(item, "sezione", "") or ""),
                    giudice_relatore=str(getattr(item, "giudiceRelatore", "") or ""),
                    data_deposito=_parse_data(getattr(item, "dataDeposito", None)),
                    data_udienza=_parse_data(getattr(item, "dataUdienza", None)),
                    ricorrenti=_parse_lista(getattr(item, "ricorrenti", None)),
                    resistenti=_parse_lista(getattr(item, "resistenti", None)),
                    oggetto_controversia=str(getattr(item, "oggettoControversia", "") or ""),
                    valore_controversia=float(getattr(item, "valoreControversia", 0.0) or 0.0),
                    codice_commissione=str(getattr(item, "codiceCommissione", "") or ""),
                    nome_commissione=str(getattr(item, "nomeCommissione", "") or ""),
                ))
        except (AttributeError, TypeError, ValueError):
            pass
        return fascicoli

    def _parse_documenti(self, risposta: Any) -> List[DocumentoSIGIT]:
        docs = []
        try:
            items = risposta.documenti or risposta.documento or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                docs.append(DocumentoSIGIT(
                    id_documento=str(getattr(item, "idDocumento", "") or ""),
                    nome=str(getattr(item, "nomeFile", "") or ""),
                    tipo=str(getattr(item, "tipoDocumento", "ATTO") or ""),
                    data_deposito=_parse_data(getattr(item, "dataDeposito", None)),
                    mittente=str(getattr(item, "mittente", "") or ""),
                    dimensione_bytes=int(getattr(item, "dimensione", 0) or 0),
                    disponibile=bool(getattr(item, "disponibile", True)),
                    id_deposito=str(getattr(item, "idDeposito", "") or ""),
                    tipo_atto=str(getattr(item, "tipoAtto", "") or ""),
                ))
        except (AttributeError, TypeError, ValueError):
            pass
        return docs


# ================================================================ Demo / offline

class ClientSIGITDemo(ClientSIGIT):
    """Implementazione demo (offline) per PTT/SIGIT — dati fittizi."""

    def __init__(self):
        self.p12_path         = ""
        self.p12_password     = b""
        self.cf_avvocato      = "DEMO"
        self.timeout          = 5
        self._zeep_cache      = {}
        self.cert_pem_path    = ""
        self.key_pem_path     = ""
        self.key_pem_password = None

    def _nome_commissione_demo(self, codice: str) -> str:
        # Mappa demo commissioni tributarie italiane
        _COMMISSIONI = {
            "CPT-MI": "Corte di Giustizia Tributaria di I grado di Milano",
            "CPT-RM": "Corte di Giustizia Tributaria di I grado di Roma",
            "CPT-NA": "Corte di Giustizia Tributaria di I grado di Napoli",
            "CPT-TO": "Corte di Giustizia Tributaria di I grado di Torino",
            "CPT-BO": "Corte di Giustizia Tributaria di I grado di Bologna",
            "CGT-LO": "Corte di Giustizia Tributaria di II grado della Lombardia",
            "CGT-LA": "Corte di Giustizia Tributaria di II grado del Lazio",
        }
        return _COMMISSIONI.get(codice, f"Commissione {codice}")

    def ricerca_fascicoli(
        self, commissione, numero_rgt=None, anno_rgt=None,
        nome_ricorrente=None, tipo=None, max_risultati=50
    ) -> List[FascicoloSIGIT]:
        anno = anno_rgt or date.today().year
        anno_ud = date.today().year + (1 if date.today().month >= 10 else 0)
        nome_comm = (
            self._nome_commissione_demo(commissione)
            if commissione and not commissione.isdigit()
            else f"Corte di Giustizia Tributaria — {commissione}"
        )
        return [
            FascicoloSIGIT(
                numero_rgt=numero_rgt or "1234",
                anno_rgt=anno,
                tipo=tipo or "RICORSO",
                stato="PENDENTE",
                materia="IVA",
                sezione="Prima sezione",
                giudice_relatore="Dr. Carlo Mancini",
                data_deposito=f"{anno}-02-15",
                data_udienza=f"{anno_ud}-06-20",
                ricorrenti=[nome_ricorrente or "Rossi Mario s.r.l."],
                resistenti=["Agenzia delle Entrate — Direzione Provinciale"],
                oggetto_controversia="Impugnazione avviso di accertamento IVA — Demo",
                valore_controversia=45800.00,
                note="Dato demo — collegare al PTT con certificato reale",
                codice_commissione=commissione or "CPT-MI",
                nome_commissione=nome_comm,
            ),
            FascicoloSIGIT(
                numero_rgt=str(int(numero_rgt or "999") + 1) if numero_rgt else "1235",
                anno_rgt=anno,
                tipo="APPELLO",
                stato="SOSPESO",
                materia="IRPEF",
                sezione="Seconda sezione",
                giudice_relatore="Dr.ssa Laura Bianchi",
                data_deposito=f"{anno - 1}-11-08",
                data_udienza="",
                ricorrenti=[nome_ricorrente or "Bianchi Giuseppe"],
                resistenti=["Agenzia delle Entrate — Ufficio Controlli"],
                oggetto_controversia="Appello vs sentenza CTP — IRPEF redditi diversi — Demo",
                valore_controversia=12300.00,
                note="Dato demo — collegare al PTT con certificato reale",
                codice_commissione=commissione or "CPT-MI",
                nome_commissione=nome_comm,
            ),
        ]

    def consulta_documenti(
        self, codice_commissione, numero_rgt, anno_rgt
    ) -> List[DocumentoSIGIT]:
        return [
            DocumentoSIGIT(
                "DEMO-T001", "ricorso_principale.pdf.p7m", "RICORSO",
                f"{anno_rgt}-02-15", "avv.demo@pec.it", 245760,
                id_deposito="BUSTA-PTT-001", tipo_atto="Ricorso tributario",
            ),
            DocumentoSIGIT(
                "DEMO-T002", "allegato_1_fatture.pdf.p7m", "ALLEGATO",
                f"{anno_rgt}-02-15", "avv.demo@pec.it", 98304,
                id_deposito="BUSTA-PTT-001", tipo_atto="Ricorso tributario",
            ),
            DocumentoSIGIT(
                "DEMO-T003", "controdeduzioni_ae.pdf.p7m", "CONTRODEDUZIONI",
                f"{anno_rgt}-04-10", "ae.difesa@pec.agenziaentrate.it", 189440,
                id_deposito="BUSTA-PTT-002", tipo_atto="Controdeduzioni",
            ),
            DocumentoSIGIT(
                "DEMO-T004", "memoria_illustrativa.pdf.p7m", "MEMORIA",
                f"{anno_rgt}-05-20", "avv.demo@pec.it", 134000,
                id_deposito="BUSTA-PTT-003", tipo_atto="Memoria illustrativa",
            ),
            DocumentoSIGIT(
                "DEMO-T005", "sentenza_n123_anno.pdf", "SENTENZA",
                f"{anno_rgt}-09-15", "segreteria.cpt@giustiziatributaria.gov.it", 78000,
                id_deposito="BUSTA-PTT-SEN-001", tipo_atto="Sentenza",
            ),
        ]

    def deposita_atto(
        self,
        codice_commissione: str,
        tipo_atto: str,
        atto_path: str,
        numero_rgt: str = "",
        anno_rgt: int = 0,
        oggetto: str = "",
    ) -> dict:
        """Demo: simula deposito al PTT/SIGIT con risposta conforme alle specifiche MEF."""
        import uuid
        from datetime import datetime as _dt
        from pathlib import Path

        if not Path(atto_path).exists():
            return {
                "codiceEsito":      "E_FILE",
                "descrizioneEsito": f"File non trovato: {atto_path}",
                "stato":            "ERRORE",
            }

        id_dep  = f"PTT-{str(uuid.uuid4())[:8].upper()}"
        ts      = _dt.now().isoformat()
        nome_comm = self._nome_commissione_demo(codice_commissione)

        return {
            "codiceEsito":      "0",
            "descrizioneEsito": "Deposito accettato dal sistema PTT/SIGIT",
            "idDeposito":       id_dep,
            "dataDeposito":     ts,
            "stato":            "INVIATO",
            "commissione":      nome_comm,
            "tipoAtto":         tipo_atto,
            "rifProcedimento":  f"RGT {numero_rgt}/{anno_rgt}" if numero_rgt else "—",
            # Ricevuta accettazione PEC (simulata)
            "ricevutaAccettazione": {
                "mittente":  "noreply@pec.giustiziatributaria.gov.it",
                "oggetto":   f"Accettazione deposito {id_dep} — {tipo_atto}",
                "corpo":     (
                    f"Il deposito con identificativo {id_dep} è stato accettato "
                    f"dal sistema PTT in data {ts}. "
                    f"Procedimento: RGT {numero_rgt}/{anno_rgt}. Commissione: {nome_comm}."
                ),
                "messageId": f"<{id_dep}.acc@pec.giustiziatributaria.gov.it>",
            },
            # Esito controlli automatici (simulato)
            "esitoControlli": {
                "codice":   "OK",
                "messaggi": [
                    "Firma digitale: valida (CAdES-BES)",
                    "Formato file: PDF/A conforme (D.M. 163/2013)",
                    "Dimensione busta: entro i limiti",
                    "Codice fiscale avvocato: verificato",
                    "Commissione tributaria: individuata",
                ],
                "oggettoPEC": f"Esito controlli automatici deposito {id_dep}",
            },
            # Esito segreteria (simulato)
            "esitoSegreteria": {
                "stato":     "ACCETTATO_CANCELLERIA",
                "codice":    "ACCETTATO",
                "messaggio": "Atto depositato e iscritto nel registro RGT.",
                "numeroRGT": numero_rgt or "NUOVO",
                "annoRGT":   anno_rgt or date.today().year,
            },
            "esitoCancelleria": {
                "stato":     "ACCETTATO_CANCELLERIA",
                "codice":    "ACCETTATO",
                "messaggio": "Atto depositato e iscritto nel registro RGT.",
                "numeroRGT": numero_rgt or "NUOVO",
                "annoRGT":   anno_rgt or date.today().year,
            },
        }


# ================================================================ Helpers

def _parse_data(valore: Any) -> str:
    if not valore:
        return ""
    if isinstance(valore, (date, datetime)):
        return valore.strftime("%Y-%m-%d")
    return str(valore)[:10]


def _parse_lista(valore: Any) -> List[str]:
    if not valore:
        return []
    if isinstance(valore, list):
        return [str(v) for v in valore]
    for attr in ("ricorrente", "resistente", "soggetto", "parte"):
        if hasattr(valore, attr):
            items = getattr(valore, attr)
            if not isinstance(items, list):
                items = [items]
            return [str(getattr(i, "nominativo", i)) for i in items]
    return [str(valore)]


def crea_client_sigit(demo: bool = False) -> ClientSIGIT:
    """Factory: restituisce ClientSIGIT o ClientSIGITDemo."""
    if demo:
        return ClientSIGITDemo()
    from pct.config_studio import risolvi_config_firma_corrente

    firma_cfg = risolvi_config_firma_corrente()
    cf  = firma_cfg["cf_avvocato"]
    p12 = firma_cfg["p12_path"]
    pwd = firma_cfg["p12_password"].encode()
    if p12 and os.path.exists(p12):
        return ClientSIGIT(p12_path=p12, p12_password=pwd, codice_fiscale_avvocato=cf)
    cert = firma_cfg["cert_pem_path"]
    key  = firma_cfg["key_pem_path"]
    if cert and key and os.path.exists(cert) and os.path.exists(key):
        key_pwd_str = firma_cfg["key_pem_password"]
        return ClientSIGIT(
            cert_pem_path=cert, key_pem_path=key,
            key_pem_password=key_pwd_str.encode() if key_pwd_str else None,
            codice_fiscale_avvocato=cf,
        )
    raise FileNotFoundError(
        "Nessun certificato configurato per il PTT/SIGIT.\n"
        "Usare le stesse credenziali del PCT civile: PCT_FIRMA_P12 oppure "
        "PCT_FIRMA_CERT + PCT_FIRMA_KEY, oppure configurarle in Impostazioni → Firma Digitale."
    )
