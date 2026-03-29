"""
pct/pat.py — Integrazione con il PAT (Processo Amministrativo Telematico)
              e SIGA (Sistema Informativo della Giustizia Amministrativa).

Offre:
  A) CONSULTAZIONE fascicoli amministrativi (TAR e Consiglio di Stato)
  B) IMPORTAZIONE pratiche amministrative nel gestionale locale

Riferimenti normativi:
  - D.Lgs. 104/2010 (Codice del Processo Amministrativo) — art. 136
  - D.P.C.M. 16/02/2016 — regole tecniche PAT
  - D.P.C.S.G.A. 28/07/2021 — aggiornamento specifiche SIGA

Accesso: tramite dispositivo CNS/CIE oppure credenziali SPID (livello 2).
In modalità demo restituisce dati fittizi senza richiedere connessione.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- PAT / SIGA endpoints
_PAT_BASE           = os.getenv("PCT_PAT_BASE_URL", "https://pac.giustizia-amministrativa.it/pac")
_WSDL_RICERCA_AMM   = f"{_PAT_BASE}/RicercaRicorsiService?wsdl"
_WSDL_CONSULTA_AMM  = f"{_PAT_BASE}/ConsultazioneDocumentiService?wsdl"


# ================================================================ Dataclass risultati

@dataclass
class FascicoloPAT:
    """Pratica amministrativa trovata nel registro SIGA tramite PAT."""
    numero_ricorso: str
    anno: int
    tipo: str                   # RICORSO | APPELLO | REGOLAMENTO | OPPOSIZIONE | OTTEMPERANZA
    stato: str                  # PENDENTE | DEFINITO | SOSPESO | RINVIATO
    materia: str = ""           # APPALTI | URBANISTICA | PERSONALE | TRIBUTI | AMBIENTE | ALTRO
    sezione: str = ""
    giudice_relatore: str = ""
    data_deposito: str = ""     # YYYY-MM-DD — data deposito ricorso
    data_udienza: str = ""      # prossima udienza
    ricorrenti: List[str] = field(default_factory=list)
    resistenti: List[str] = field(default_factory=list)   # enti resistenti
    controinteressati: List[str] = field(default_factory=list)
    oggetto: str = ""
    note: str = ""
    codice_ufficio: str = ""
    nome_ufficio: str = ""


@dataclass
class DocumentoPAT:
    """Documento presente nel fascicolo telematico amministrativo."""
    id_documento: str
    nome: str
    tipo: str                   # RICORSO | MEMORIA | SENTENZA | ORDINANZA | DECRETO | ALLEGATO
    data_deposito: str          # YYYY-MM-DD
    mittente: str
    dimensione_bytes: int = 0
    disponibile: bool = True
    # Raggruppamento per busta/deposito (tutti i file della stessa busta condividono id_deposito)
    id_deposito: str = ""       # identificativo univoco della busta telematica
    tipo_atto: str = ""         # tipo atto della busta (es. "Ricorso", "Memoria", "Ordinanza")


@dataclass
class RisultatoImportazionePAT:
    """Esito dell'importazione di una pratica amministrativa da PAT."""
    successo: bool
    id_fascicolo_locale: Optional[str] = None
    messaggio: str = ""
    fascicolo_pat: Optional[FascicoloPAT] = None
    avvisi: List[str] = field(default_factory=list)


# ================================================================ Client PAT

class ClientPAT:
    """
    Client per l'accesso al PAT / SIGA (Processo Amministrativo Telematico).
    Autenticazione tramite CNS/CIE (P12) o SPID (non supportato in questa versione).
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
        numero_ricorso: Optional[str] = None,
        anno: Optional[int] = None,
        nome_ricorrente: Optional[str] = None,
        materia: Optional[str] = None,
        max_risultati: int = 50,
    ) -> List[FascicoloPAT]:
        """
        Cerca fascicoli amministrativi nel registro SIGA.

        Args:
            ufficio:         Codice o nome del TAR / Consiglio di Stato.
            numero_ricorso:  Numero del ricorso (es. "1234").
            anno:            Anno di deposito.
            nome_ricorrente: Nome/ragione sociale del ricorrente.
            materia:         Materia del ricorso (APPALTI, URBANISTICA, ecc.).
            max_risultati:   Numero massimo di risultati.
        """
        client = self._get_client(_WSDL_RICERCA_AMM)
        req: Dict[str, Any] = {
            "codiceFiscaleAvvocato": self.cf_avvocato,
            "codiceUfficio":         self._risolvi_codice(ufficio),
            "maxRisultati":          max_risultati,
        }
        if numero_ricorso:  req["numeroRicorso"]    = numero_ricorso
        if anno:            req["anno"]              = anno
        if nome_ricorrente: req["nominativoRicorrente"] = nome_ricorrente
        if materia:         req["materia"]           = materia
        try:
            risposta = client.service.ricercaRicorsi(**req)
        except Exception as e:
            raise ConnectionError(f"Errore PAT/SIGA: {e}") from e
        return self._parse_fascicoli(risposta)

    # ---------------------------------------------------------------- Documenti

    def consulta_documenti(
        self,
        codice_ufficio: str,
        numero_ricorso: str,
        anno: int,
    ) -> List[DocumentoPAT]:
        """Recupera l'elenco dei documenti del fascicolo amministrativo."""
        client = self._get_client(_WSDL_CONSULTA_AMM)
        try:
            risposta = client.service.consultazioneDocumenti(
                codiceFiscaleAvvocato=self.cf_avvocato,
                codiceUfficio=codice_ufficio,
                numeroRicorso=numero_ricorso,
                anno=anno,
            )
        except Exception as e:
            raise ConnectionError(f"Errore consultazione PAT: {e}") from e
        return self._parse_documenti(risposta)

    # ---------------------------------------------------------------- Import

    def importa_fascicolo(
        self,
        fascicolo_pat: FascicoloPAT,
        gestione_fascicoli,
        gestione_clienti,
        avvocato_referente: str = "",
    ) -> RisultatoImportazionePAT:
        """Importa una pratica amministrativa come nuovo Fascicolo nel gestionale."""
        try:
            from pct.fascicoli import TipoFascicolo, StatoFascicolo, TipoAttivita

            stato_map = {
                "PENDENTE": StatoFascicolo.IN_CORSO,
                "DEFINITO": StatoFascicolo.DEFINITO,
                "SOSPESO":  StatoFascicolo.SOSPESO,
                "RINVIATO": StatoFascicolo.SOSPESO,
            }
            stato = stato_map.get(fascicolo_pat.stato.upper(), StatoFascicolo.APERTO)

            # Riconcilia ricorrenti e resistenti con l'anagrafica
            from pct.polisWeb import riconcilia_soggetti_pst
            tutti_soggetti = list(fascicolo_pat.ricorrenti or []) + list(fascicolo_pat.resistenti or [])
            rif = f"N.RG {fascicolo_pat.numero_ricorso}/{fascicolo_pat.anno} — {fascicolo_pat.nome_ufficio}"
            id_cliente, nome_cliente, avvisi = riconcilia_soggetti_pst(
                nomi=tutti_soggetti,
                gestione_clienti=gestione_clienti,
                riferimento=rif,
                portale="PAT",
            )

            oggetto_breve = fascicolo_pat.oggetto[:80] if fascicolo_pat.oggetto else (
                fascicolo_pat.materia or f"Ricorso {fascicolo_pat.tipo}"
            )
            fasc = gestione_fascicoli.nuovo(
                titolo=f"N.RG {fascicolo_pat.numero_ricorso}/{fascicolo_pat.anno} — {oggetto_breve}",
                tipo=TipoFascicolo.AMMINISTRATIVO,
                id_cliente=id_cliente,
                nome_cliente=nome_cliente,
                tribunale=fascicolo_pat.nome_ufficio,
                numero_rg=fascicolo_pat.numero_ricorso,
                anno_rg=fascicolo_pat.anno,
                sezione=fascicolo_pat.sezione,
                giudice=fascicolo_pat.giudice_relatore,
                oggetto=fascicolo_pat.oggetto or fascicolo_pat.materia,
                stato=stato,
                avvocato_referente=avvocato_referente,
                data_apertura=fascicolo_pat.data_deposito or date.today().isoformat(),
                note=fascicolo_pat.note or f"Importato da PAT il {date.today()}",
            )

            if fascicolo_pat.data_udienza:
                try:
                    gestione_fascicoli.aggiungi_attivita(
                        fasc.id,
                        tipo=TipoAttivita.UDIENZA,
                        data=fascicolo_pat.data_udienza,
                        titolo="Udienza TAR (importata da PAT)",
                        avvocato=avvocato_referente,
                    )
                except Exception as ex:
                    avvisi.append(f"Udienza non importata: {ex}")

            if not id_cliente:
                avvisi.append(
                    "Nessun soggetto valido tra ricorrenti/resistenti. "
                    "Assegnare il cliente manualmente."
                )

            return RisultatoImportazionePAT(
                successo=True,
                id_fascicolo_locale=fasc.id,
                messaggio=f"Pratica amm. N.RG {fascicolo_pat.numero_ricorso}/{fascicolo_pat.anno} importata.",
                fascicolo_pat=fascicolo_pat,
                avvisi=avvisi,
            )

        except Exception as e:
            return RisultatoImportazionePAT(
                successo=False,
                messaggio=f"Errore durante l'importazione: {e}",
                fascicolo_pat=fascicolo_pat,
            )

    # ---------------------------------------------------------------- Deposito atti

    def deposita_atto(
        self,
        codice_ufficio: str,
        tipo_atto: str,
        atto_path: str,
        numero_ricorso: str = "",
        anno: int = 0,
        oggetto: str = "",
    ) -> dict:
        """
        Deposita un atto al sistema PAT/SIGA (Processo Amministrativo Telematico).

        Flusso atteso dal portale SIGA (spec. D.P.C.M. 16/02/2016 e D.P.C.S.G.A. 28/07/2021):
          SOAP depositoAtto → risposta immediata
          Response: { "codiceEsito": "0", "descrizioneEsito": "Deposito accettato",
                      "idDeposito": "...", "dataDeposito": "...", "stato": "INVIATO" }

        Successivamente il sistema SIGA invia via PEC:
          - Ricevuta accettazione (fase 4)
          - Esito controlli automatici (fase 5/6)
          - Esito cancelleria (fase 7)

        Args:
            codice_ufficio:  Codice TAR/CdS destinatario
            tipo_atto:       Tipo atto (RICORSO, MEMORIA, APPELLO, MOTIVI_AGGIUNTI, ecc.)
            atto_path:       Percorso al file firmato (.pdf.p7m)
            numero_ricorso, anno: Riferimento procedimento
            oggetto:         Descrizione sintetica

        Returns:
            dict con codiceEsito, idDeposito, dataDeposito, stato, messaggio
        """
        import uuid
        from pathlib import Path

        if not Path(atto_path).exists():
            return {
                "codiceEsito": "E_FILE",
                "descrizioneEsito": f"File non trovato: {atto_path}",
                "stato": "ERRORE",
            }

        try:
            client = self._get_client(_WSDL_CONSULTA_AMM)   # riuso client SIGA
            import base64

            with open(atto_path, "rb") as f:
                atto_b64 = base64.b64encode(f.read()).decode()

            req = {
                "codiceFiscaleAvvocato": self.cf_avvocato,
                "codiceUfficio":         codice_ufficio,
                "tipoAtto":              tipo_atto,
                "attoFirmato":           atto_b64,
                "oggetto":               oggetto,
            }
            if numero_ricorso:
                req["numeroRicorso"] = numero_ricorso
            if anno:
                req["anno"] = anno

            risposta = client.service.depositoAtto(**req)
            return {
                "codiceEsito":      getattr(risposta, "codiceEsito", "0"),
                "descrizioneEsito": getattr(risposta, "descrizioneEsito", "Deposito accettato"),
                "idDeposito":       getattr(risposta, "idDeposito", ""),
                "dataDeposito":     getattr(risposta, "dataDeposito", ""),
                "stato":            "INVIATO",
            }
        except Exception as e:
            return {
                "codiceEsito": "E_CONN",
                "descrizioneEsito": f"Errore connessione PAT/SIGA: {e}",
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
        base = "https://pac.giustizia-amministrativa.it"

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
                "Nessun certificato disponibile per il PAT. "
                "Configurare PCT_FIRMA_P12 oppure PCT_FIRMA_CERT + PCT_FIRMA_KEY."
            )

        transport = zeep.transports.Transport(session=session, timeout=self.timeout)
        client = zeep.Client(wsdl=wsdl_url, transport=transport)
        self._zeep_cache[wsdl_url] = client
        return client

    def _risolvi_codice(self, nome_o_codice: str) -> str:
        from pct.reginde import ClientReGINde
        if nome_o_codice.isdigit() or nome_o_codice.startswith("T"):
            return nome_o_codice
        r = ClientReGINde()
        uff = r.cerca_ufficio_giudiziario(nome_o_codice)
        return uff.codice if uff else nome_o_codice

    def _parse_fascicoli(self, risposta: Any) -> List[FascicoloPAT]:
        fascicoli = []
        try:
            items = risposta.ricorsi or risposta.ricorso or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                fascicoli.append(FascicoloPAT(
                    numero_ricorso=str(getattr(item, "numeroRicorso", "") or ""),
                    anno=int(getattr(item, "anno", 0) or 0),
                    tipo=str(getattr(item, "tipo", "RICORSO") or ""),
                    stato=str(getattr(item, "stato", "PENDENTE") or ""),
                    materia=str(getattr(item, "materia", "") or ""),
                    sezione=str(getattr(item, "sezione", "") or ""),
                    giudice_relatore=str(getattr(item, "giudiceRelatore", "") or ""),
                    data_deposito=_parse_data(getattr(item, "dataDeposito", None)),
                    data_udienza=_parse_data(getattr(item, "dataUdienza", None)),
                    ricorrenti=_parse_soggetti(getattr(item, "ricorrenti", None)),
                    resistenti=_parse_soggetti(getattr(item, "resistenti", None)),
                    controinteressati=_parse_soggetti(getattr(item, "controinteressati", None)),
                    oggetto=str(getattr(item, "oggetto", "") or ""),
                    codice_ufficio=str(getattr(item, "codiceUfficio", "") or ""),
                    nome_ufficio=str(getattr(item, "nomeUfficio", "") or ""),
                ))
        except (AttributeError, TypeError, ValueError):
            pass
        return fascicoli

    def _parse_documenti(self, risposta: Any) -> List[DocumentoPAT]:
        docs = []
        try:
            items = risposta.documenti or risposta.documento or []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                docs.append(DocumentoPAT(
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

class ClientPATDemo(ClientPAT):
    """Implementazione demo (offline) per PAT Amministrativo — dati fittizi."""

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
        self, ufficio, numero_ricorso=None, anno=None,
        nome_ricorrente=None, materia=None, max_risultati=50
    ) -> List[FascicoloPAT]:
        anno = anno or date.today().year
        anno_ud = date.today().year + (1 if date.today().month >= 10 else 0)
        return [
            FascicoloPAT(
                numero_ricorso=numero_ricorso or "1876",
                anno=anno,
                tipo="RICORSO",
                stato="PENDENTE",
                materia=materia or "APPALTI",
                sezione="Prima sezione",
                giudice_relatore="Cons. Maria Romano",
                data_deposito=f"{anno}-02-28",
                data_udienza=f"{anno_ud}-09-24",
                ricorrenti=["Costruzioni Alfa S.r.l."],
                resistenti=["Comune di Roma"],
                controinteressati=["Costruzioni Beta S.p.A."],
                oggetto="Annullamento aggiudicazione gara appalto — Demo",
                note="Dato demo — collegare al PAT con certificato CNS reale",
                codice_ufficio=ufficio if (ufficio.isdigit() or ufficio.startswith("T")) else "T0001",
                nome_ufficio=self._nome_ufficio_demo(ufficio) if (ufficio.isdigit() or ufficio.startswith("T")) else ufficio,
            )
        ]

    def consulta_documenti(self, codice_ufficio, numero_ricorso, anno) -> List[DocumentoPAT]:
        return [
            DocumentoPAT("DEMO-A001", "ricorso_principale.pdf.p7m", "RICORSO",
                         f"{anno}-02-28", "avv.demo@pec.it", 312000,
                         id_deposito="BUSTA-PAT-001", tipo_atto="Ricorso principale"),
            DocumentoPAT("DEMO-A002", "memoria_resistente.pdf.p7m", "MEMORIA",
                         f"{anno}-05-15", "avv.ente@pec.avvocaturastato.it", 204800,
                         id_deposito="BUSTA-PAT-002", tipo_atto="Memoria del resistente"),
            DocumentoPAT("DEMO-A003", "ordinanza_cautelare.pdf.p7m", "ORDINANZA",
                         f"{anno}-03-10", "tar.demo@giustizia-amministrativa.it", 48000,
                         id_deposito="BUSTA-PAT-003", tipo_atto="Ordinanza cautelare"),
        ]

    def deposita_atto(
        self,
        codice_ufficio: str,
        tipo_atto: str,
        atto_path: str,
        numero_ricorso: str = "",
        anno: int = 0,
        oggetto: str = "",
    ) -> dict:
        """
        Demo: simula il deposito di un atto al PAT/SIGA.

        Risposta conforme alle specifiche SIGA (D.P.C.M. 16/02/2016):
          codiceEsito  "0"  = deposito accettato
          codiceEsito  "1"  = deposito con avvertimenti (WARN)
          codiceEsito  "2"  = deposito rifiutato (ERRORE)

        Fasi simulate:
          1. SOAP depositoAtto → risposta immediata (INVIATO)
          2. PEC di accettazione busta → ACCETTATO_PEC
          3. PEC esito controlli automatici → WARN_CONTROLLI / OK
          4. PEC esito cancelleria TAR/CdS → ACCETTATO_CANCELLERIA

        Gli step 2-4 in produzione arrivano via PEC dal sistema SIGA.
        In demo mode il ciclo completo è restituito in un'unica risposta.
        """
        import uuid
        from datetime import datetime as _dt
        from pathlib import Path

        if not Path(atto_path).exists():
            return {
                "codiceEsito":      "E_FILE",
                "descrizioneEsito": f"File non trovato: {atto_path}",
                "stato":            "ERRORE",
            }

        id_dep  = f"PAT-{str(uuid.uuid4())[:8].upper()}"
        ts      = _dt.now().isoformat()
        is_tar  = codice_ufficio.isdigit() or codice_ufficio.startswith("T")
        ufficio = self._nome_ufficio_demo(codice_ufficio) if is_tar else codice_ufficio

        return {
            # ── Fase 1: risposta immediata all'invio ───────────────────────────
            "codiceEsito":       "0",
            "descrizioneEsito":  "Deposito accettato dal sistema PAT/SIGA",
            "idDeposito":        id_dep,
            "dataDeposito":      ts,
            "stato":             "INVIATO",
            "ufficio":           ufficio,
            "tipoAtto":          tipo_atto,
            "rifProcedimento":   f"{numero_ricorso}/{anno}" if numero_ricorso else "—",
            # ── Fase 2: ricevuta accettazione PEC (simulata) ───────────────────
            "ricevutaAccettazione": {
                "mittente":  "noreply@pec.giustizia-amministrativa.it",
                "oggetto":   f"Accettazione deposito {id_dep} — {tipo_atto}",
                "corpo":     (
                    f"Il deposito con identificativo {id_dep} è stato accettato "
                    f"dal sistema SIGA in data {ts}. "
                    f"Procedimento: {numero_ricorso}/{anno}. Ufficio: {ufficio}."
                ),
                "messageId": f"<{id_dep}.acc@pec.giustizia-amministrativa.it>",
            },
            # ── Fase 3: esito controlli automatici (simulato) ──────────────────
            "esitoControlli": {
                "codice":   "OK",
                "messaggi": [
                    "Firma digitale: valida (CAdES-BES o PAdES)",
                    "Formato file: PDF/A conforme",
                    "Dimensione busta: entro i limiti (< 30 MB)",
                    "Codice fiscale avvocato: verificato",
                    "Tipo atto: coerente con il registro TAR",
                ],
                "oggettoPEC": f"Esito controlli automatici deposito {id_dep}",
            },
            # ── Fase 4: esito cancelleria (simulato) ───────────────────────────
            "esitoCancelleria": {
                "stato":   "ACCETTATO_CANCELLERIA",
                "oggetto": f"Esito deposito {id_dep} — {tipo_atto} accettato",
                "corpo":   (
                    f"Il deposito {id_dep} relativo al procedimento "
                    f"{numero_ricorso}/{anno} è stato accettato dalla segreteria. "
                    f"Numero di RG assegnato: N.RG {numero_ricorso or 'NUOVO'}/{anno or '2026'}."
                ),
            },
        }


# ================================================================ Utils

def _parse_data(valore: Any) -> str:
    if not valore:
        return ""
    if isinstance(valore, (datetime, date)):
        return valore.strftime("%Y-%m-%d")
    return str(valore)[:10]


def _parse_soggetti(valore: Any) -> List[str]:
    if not valore:
        return []
    if isinstance(valore, list):
        return [str(v) for v in valore]
    for attr in ("soggetto", "parte", "ricorrente", "resistente"):
        if hasattr(valore, attr):
            items = getattr(valore, attr)
            if not isinstance(items, list):
                items = [items]
            return [str(getattr(i, "denominazione", getattr(i, "nominativo", i))) for i in items]
    return [str(valore)]


def crea_client_pat(demo: bool = False) -> ClientPAT:
    """Factory: restituisce ClientPAT o ClientPATDemo."""
    if demo:
        return ClientPATDemo()
    cf  = os.getenv("PCT_CF_AVVOCATO", "")
    p12 = os.getenv("PCT_FIRMA_P12", "")
    pwd = os.getenv("PCT_FIRMA_PASSWORD", "").encode()
    if p12 and os.path.exists(p12):
        return ClientPAT(p12_path=p12, p12_password=pwd, codice_fiscale_avvocato=cf)
    cert = os.getenv("PCT_FIRMA_CERT", "")
    key  = os.getenv("PCT_FIRMA_KEY", "")
    if cert and key and os.path.exists(cert) and os.path.exists(key):
        key_pwd_str = os.getenv("PCT_FIRMA_KEY_PASSWORD", "")
        return ClientPAT(
            cert_pem_path=cert, key_pem_path=key,
            key_pem_password=key_pwd_str.encode() if key_pwd_str else None,
            codice_fiscale_avvocato=cf,
        )
    raise FileNotFoundError(
        "Nessun certificato configurato per il PAT Amministrativo.\n"
        "Usare le stesse credenziali CNS del PCT civile: PCT_FIRMA_P12 oppure "
        "PCT_FIRMA_CERT + PCT_FIRMA_KEY."
    )
