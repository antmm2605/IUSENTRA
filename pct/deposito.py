"""
Gestione del deposito telematico civile e penale.

- Civile: Deposito via PEC con busta .enc
- Penale: Deposito tramite Portale Deposito Atti Penali (PDP)

Conformità PST (D.M. 44/2011):
  - Verifica PDF/A pre-firma (via pct.validazione)
  - Marcatura temporale RFC 3161 opzionale (via pct.rfc3161)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .busta import BustaTelematica, DatiBusta, Allegato
from .pec import ClientPEC, ConfigPEC
from .reginde import ClientReGINde
from .firma import FirmaDigitale
from .fascicoli import EsitoDepositoPCT, normalizza_stato_deposito_pct
from .validazione import valida_documento_deposito
from .rfc3161 import richiedi_timestamp, salva_token, TSA_URL_DEFAULT

EsitoDeposito = EsitoDepositoPCT


class DepositoCivile:
    """
    Gestisce il deposito telematico nel processo civile (PCT).

    Flusso:
    1. Preparazione documenti (PDF/A + firma digitale)
    2. Creazione busta telematica (.enc)
    3. Invio via PEC all'ufficio giudiziario
    4. Attesa ricevute (accettazione + consegna)
    5. Verifica esito dal cancelliere
    """

    def __init__(
        self,
        config_pec: ConfigPEC,
        firma: Optional[FirmaDigitale] = None,
        output_dir: str = "./depositi",
    ):
        self.pec = ClientPEC(config_pec)
        self.firma = firma
        self.output_dir = Path(output_dir)
        self.reginde = ClientReGINde()

    def _risolvi_ufficio_destinazione(
        self,
        tribunale: str,
        codice_ufficio: str = "",
    ):
        """Risolvi l'ufficio ufficiale prima di costruire la busta telematica."""
        codice = str(codice_ufficio or "").strip()
        if codice:
            ufficio = self.reginde.ottieni_ufficio(codice)
            if ufficio:
                return ufficio

        tribunale_norm = str(tribunale or "").strip()
        if tribunale_norm and tribunale_norm.isdigit():
            ufficio = self.reginde.ottieni_ufficio(tribunale_norm)
            if ufficio:
                return ufficio

        if tribunale_norm:
            return self.reginde.cerca_ufficio_giudiziario(tribunale_norm)
        return None

    def deposita(
        self,
        dati: DatiBusta,
        tribunale: str,
        attendi_ricevute: bool = True,
        tsa_url: Optional[str] = None,
    ) -> EsitoDeposito:
        """
        Esegue il deposito telematico completo.

        Args:
            dati:              Dati dell'atto da depositare
            tribunale:         Nome del tribunale (es. "MILANO")
            attendi_ricevute:  Se True attende le ricevute PEC
            tsa_url:           URL TSA per marcatura temporale RFC 3161 (None = disabilitata)

        Returns:
            Esito del deposito
        """
        import uuid

        id_deposito = str(uuid.uuid4())[:8].upper()
        timestamp = datetime.now().isoformat()

        # 0. Validazione PDF/A pre-firma (D.M. 44/2011 art. 12)
        if Path(dati.atto_principale).exists():
            esito_pdfa = valida_documento_deposito(dati.atto_principale, atto_principale=True)
            if not esito_pdfa["ok"]:
                return EsitoDeposito(
                    id=id_deposito,
                    timestamp=timestamp,
                    stato="ERRORE",
                    tipo_atto=dati.tipo_atto,
                    busta_path="",
                    pec_destinatario="",
                    messaggio=(
                        "Deposito bloccato — atto principale non conforme: "
                        + "; ".join(esito_pdfa["errori"])
                    ),
                    nome_atto_principale=Path(dati.atto_principale).name,
                )

        # 1. Cerca PEC tribunale
        ufficio = self._risolvi_ufficio_destinazione(
            tribunale=tribunale,
            codice_ufficio=dati.codice_ufficio,
        )
        if not ufficio:
            return EsitoDeposito(
                id=id_deposito,
                timestamp=timestamp,
                stato="ERRORE",
                tipo_atto=dati.tipo_atto,
                busta_path="",
                pec_destinatario="",
                messaggio=f"Ufficio giudiziario '{tribunale}' non trovato nel registro.",
                nome_atto_principale=Path(dati.atto_principale).name,
            )
        dati.codice_ufficio = ufficio.codice

        # 2. Firma documenti (se firma disponibile)
        if self.firma:
            # Verifica scadenza certificato prima di firmare (D.M. 44/2011 art. 12)
            stato_cert = self.firma.verifica_scadenza()
            if stato_cert["scaduto"]:
                return EsitoDeposito(
                    id=id_deposito,
                    timestamp=timestamp,
                    stato="ERRORE",
                    tipo_atto=dati.tipo_atto,
                    busta_path="",
                    pec_destinatario="",
                    messaggio=f"Deposito bloccato: {stato_cert['messaggio']}",
                    nome_atto_principale=Path(dati.atto_principale).name,
                )
            dati.atto_principale = self._firma_documento(dati.atto_principale)
            for allegato in dati.allegati:
                allegato.percorso = self._firma_documento(allegato.percorso)

            # 2b. Marcatura temporale RFC 3161 (opzionale — D.M. 44/2011 art. 12)
            if tsa_url:
                self._apponi_timestamp(dati.atto_principale, tsa_url)

        # 3. Crea busta telematica
        busta = BustaTelematica(dati)
        busta_dir = self.output_dir / id_deposito
        busta_path = busta.crea_busta(str(busta_dir))

        # 4. Invia via PEC
        # Oggetto conforme D.M. 44/2011 art. 14 c.3: "DEPOSITO TELEMATICO - {TipoAtto}"
        # Includi RG solo se entrambi numero_rg e anno_rg sono valorizzati
        # (anno_rg=0 o None produrrebbe "RG 1234/None" — non conforme)
        rg_str = (
            f" - RG {dati.numero_rg}/{dati.anno_rg}"
            if dati.numero_rg and dati.anno_rg
            else ""
        )
        oggetto_pec = f"DEPOSITO TELEMATICO - {dati.tipo_atto}{rg_str}"
        esito_invio = self.pec.invia_busta(
            destinatario_pec=ufficio.pec,
            busta_path=busta_path,
            oggetto=oggetto_pec,
        )

        if not esito_invio["inviato"]:
            return EsitoDeposito(
                id=id_deposito,
                timestamp=timestamp,
                stato="ERRORE",
                tipo_atto=dati.tipo_atto,
                busta_path=busta_path,
                pec_destinatario=ufficio.pec,
                messaggio=f"Errore invio PEC: {esito_invio.get('errore')}",
                nome_atto_principale=Path(dati.atto_principale).name,
            )

        # 5. Attendi ricevute
        ricevute = {}
        if attendi_ricevute:
            ricevute = self.pec.attendi_ricevute()

        stato = "INVIATO"
        if ricevute.get("accettazione"):
            stato = "ACCETTATO_PEC"
        if ricevute.get("consegna"):
            stato = "CONSEGNATO"
        stato = normalizza_stato_deposito_pct(stato)

        return EsitoDeposito(
            id=id_deposito,
            timestamp=timestamp,
            stato=stato,
            tipo_atto=dati.tipo_atto,
            busta_path=busta_path,
            pec_destinatario=ufficio.pec,
            messaggio="Deposito completato con successo.",
            ricevuta_accettazione=ricevute.get("accettazione") or "",
            ricevuta_consegna=ricevute.get("consegna") or "",
            nome_atto_principale=Path(dati.atto_principale).name,
        )

    def _firma_documento(self, percorso: str) -> str:
        """Firma un documento e restituisce il percorso del file firmato."""
        with open(percorso, "rb") as f:
            contenuto = f.read()
        return self.firma.salva_documento_firmato(
            contenuto, percorso, formato="cades"
        )

    def _apponi_timestamp(self, percorso: str, tsa_url: str) -> None:
        """
        Richiede un timestamp RFC 3161 per il documento firmato e salva il token .tsr.

        Non solleva eccezioni: se la TSA non risponde il deposito continua
        senza marcatura (la ricevuta PEC ha valore legale equivalente).
        """
        try:
            with open(percorso, "rb") as f:
                data = f.read()
            esito = richiedi_timestamp(data, tsa_url=tsa_url)
            if esito["ok"] and esito["token"]:
                salva_token(esito["token"], percorso)
        except Exception:
            pass  # timestamp opzionale — non blocca il deposito

    def salva_esito(self, esito: EsitoDeposito) -> str:
        """Salva l'esito del deposito in formato JSON."""
        esito_dir = self.output_dir / esito.id_deposito
        esito_dir.mkdir(parents=True, exist_ok=True)
        esito_path = esito_dir / "esito.json"
        payload = esito.to_dict() if hasattr(esito, "to_dict") else dict(vars(esito))
        if "id" in payload and "id_deposito" not in payload:
            payload["id_deposito"] = payload["id"]
        with open(esito_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return str(esito_path)


class DepositoPenale:
    """
    Deposito telematico nel processo penale tramite PDP REST
    (Portale Deposito Atti Penali — D.Lgs. 150/2022 + D.M. 217/2023).

    NOTA: Questa classe è mantenuta per compatibilità con pct/cli.py.
    Per il deposito dalla UI web usare ClientPDP (pct/pdp.py) che implementa
    correttamente mTLS con certificato CNS/P12 come richiesto dal D.M. 217/2023.

    Autenticazione: mTLS con certificato CNS/CIE — NON username/password.
    URL endpoint: https://appweb.giustizia.it/snt/depositi
    """

    # Endpoint reale PDP REST (D.Lgs. 150/2022 + D.M. 217/2023)
    PDP_BASE_URL = "https://appweb.giustizia.it/snt"

    def __init__(self, credenziali: dict):
        """
        Args:
            credenziali: Dict con 'p12_path' e 'p12_password' per mTLS,
                         oppure 'cert_pem_path' e 'key_pem_path'.
                         I campi 'username'/'password' non sono supportati
                         dall'endpoint PDP reale (richiede mTLS).
        """
        self.credenziali = credenziali
        self._session_token = None

    def autentica(self) -> bool:
        """
        Verifica che il certificato mTLS sia disponibile e leggibile.
        L'autenticazione al PDP avviene tramite mTLS a livello TLS,
        non tramite token Bearer (D.M. 217/2023).

        Returns:
            True se il certificato è configurato e accessibile
        """
        p12 = self.credenziali.get("p12_path", "")
        cert = self.credenziali.get("cert_pem_path", "")
        key = self.credenziali.get("key_pem_path", "")
        if p12 and Path(p12).exists():
            self._session_token = "mtls_p12"
            return True
        if cert and key and Path(cert).exists() and Path(key).exists():
            self._session_token = "mtls_pem"
            return True
        return False

    def deposita_querela(
        self,
        atto_path: str,
        procura: str,
        dati_querelante: dict,
        dati_querelato: dict,
    ) -> dict:
        """
        Deposita una denuncia/querela tramite PDP REST con mTLS.

        Args:
            atto_path: Percorso alla querela firmata digitalmente (.pdf.p7m)
            procura: Codice ufficio della Procura della Repubblica competente
            dati_querelante: Dati del querelante (nome, cf, ecc.)
            dati_querelato: Dati del querelato

        Returns:
            Esito del deposito con codiceEsito, idDeposito, dataDeposito, stato
        """
        import requests
        from requests import Session

        if not self._session_token:
            raise RuntimeError(
                "Certificato mTLS non configurato. Chiamare autentica() prima."
            )

        session = Session()
        p12 = self.credenziali.get("p12_path", "")
        cert = self.credenziali.get("cert_pem_path", "")
        key  = self.credenziali.get("key_pem_path", "")
        if p12 and Path(p12).exists():
            try:
                from requests_pkcs12 import Pkcs12Adapter
                pwd = self.credenziali.get("p12_password", b"")
                session.mount(self.PDP_BASE_URL, Pkcs12Adapter(
                    pkcs12_filename=p12,
                    pkcs12_password=pwd if isinstance(pwd, bytes) else pwd.encode(),
                ))
            except ImportError:
                raise ImportError("Installa requests-pkcs12: pip install requests-pkcs12")
        elif cert and key:
            session.cert = (cert, key)

        with open(atto_path, "rb") as f:
            files = {"atto": (Path(atto_path).name, f, "application/octet-stream")}
            payload = {
                "tipoAtto": "QUERELA",
                "codiceUfficio": procura,
                "codiceFiscaleAvvocato": self.credenziali.get("cf_avvocato", ""),
                "oggetto": dati_querelante.get("oggetto", "Denuncia/Querela"),
            }
            try:
                resp = session.post(
                    f"{self.PDP_BASE_URL}/depositi",
                    files=files,
                    data=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                return {
                    "codiceEsito": "E_CONN",
                    "descrizioneEsito": str(e),
                    "stato": "ERRORE",
                }
