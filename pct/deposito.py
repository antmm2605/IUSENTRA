"""
Gestione del deposito telematico civile e penale.

- Civile: Deposito via PEC con busta .enc
- Penale: Deposito tramite Portale Deposito Atti Penali (PDP)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from .busta import BustaTelematica, DatiBusta, Allegato
from .pec import ClientPEC, ConfigPEC
from .reginde import ClientReGINde
from .firma import FirmaDigitale


@dataclass
class EsitoDeposito:
    """Esito di un deposito telematico."""

    id_deposito: str
    timestamp: str
    stato: str  # INVIATO | ACCETTATO | CONSEGNATO | RIFIUTATO | ERRORE
    busta_path: str
    pec_destinatario: str
    messaggio: str = ""
    ricevuta_accettazione: Optional[str] = None
    ricevuta_consegna: Optional[str] = None


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

    def deposita(
        self,
        dati: DatiBusta,
        tribunale: str,
        attendi_ricevute: bool = True,
    ) -> EsitoDeposito:
        """
        Esegue il deposito telematico completo.

        Args:
            dati: Dati dell'atto da depositare
            tribunale: Nome del tribunale (es. "MILANO")
            attendi_ricevute: Se True attende le ricevute PEC

        Returns:
            Esito del deposito
        """
        import uuid

        id_deposito = str(uuid.uuid4())[:8].upper()
        timestamp = datetime.now().isoformat()

        # 1. Cerca PEC tribunale
        ufficio = self.reginde.cerca_ufficio_giudiziario(tribunale)
        if not ufficio:
            return EsitoDeposito(
                id_deposito=id_deposito,
                timestamp=timestamp,
                stato="ERRORE",
                busta_path="",
                pec_destinatario="",
                messaggio=f"Ufficio giudiziario '{tribunale}' non trovato nel registro.",
            )

        # 2. Firma documenti (se firma disponibile)
        if self.firma:
            # Verifica scadenza certificato prima di firmare (D.M. 44/2011 art. 12)
            stato_cert = self.firma.verifica_scadenza()
            if stato_cert["scaduto"]:
                return EsitoDeposito(
                    id_deposito=id_deposito,
                    timestamp=timestamp,
                    stato="ERRORE",
                    busta_path="",
                    pec_destinatario="",
                    messaggio=f"Deposito bloccato: {stato_cert['messaggio']}",
                )
            dati.atto_principale = self._firma_documento(dati.atto_principale)
            for allegato in dati.allegati:
                allegato.percorso = self._firma_documento(allegato.percorso)

        # 3. Crea busta telematica
        busta = BustaTelematica(dati)
        busta_dir = self.output_dir / id_deposito
        busta_path = busta.crea_busta(str(busta_dir))

        # 4. Invia via PEC
        # Oggetto conforme D.M. 44/2011 art. 14 c.3: "DEPOSITO TELEMATICO - {TipoAtto}"
        rg_str = f" - RG {dati.numero_rg}/{dati.anno_rg}" if dati.numero_rg else ""
        oggetto_pec = f"DEPOSITO TELEMATICO - {dati.tipo_atto}{rg_str}"
        esito_invio = self.pec.invia_busta(
            destinatario_pec=ufficio.pec,
            busta_path=busta_path,
            oggetto=oggetto_pec,
        )

        if not esito_invio["inviato"]:
            return EsitoDeposito(
                id_deposito=id_deposito,
                timestamp=timestamp,
                stato="ERRORE",
                busta_path=busta_path,
                pec_destinatario=ufficio.pec,
                messaggio=f"Errore invio PEC: {esito_invio.get('errore')}",
            )

        # 5. Attendi ricevute
        ricevute = {}
        if attendi_ricevute:
            ricevute = self.pec.attendi_ricevute()

        stato = "INVIATO"
        if ricevute.get("accettazione"):
            stato = "ACCETTATO"
        if ricevute.get("consegna"):
            stato = "CONSEGNATO"

        return EsitoDeposito(
            id_deposito=id_deposito,
            timestamp=timestamp,
            stato=stato,
            busta_path=busta_path,
            pec_destinatario=ufficio.pec,
            messaggio="Deposito completato con successo.",
            ricevuta_accettazione=ricevute.get("accettazione"),
            ricevuta_consegna=ricevute.get("consegna"),
        )

    def _firma_documento(self, percorso: str) -> str:
        """Firma un documento e restituisce il percorso del file firmato."""
        with open(percorso, "rb") as f:
            contenuto = f.read()
        return self.firma.salva_documento_firmato(
            contenuto, percorso, formato="cades"
        )

    def salva_esito(self, esito: EsitoDeposito) -> str:
        """Salva l'esito del deposito in formato JSON."""
        esito_dir = self.output_dir / esito.id_deposito
        esito_dir.mkdir(parents=True, exist_ok=True)
        esito_path = esito_dir / "esito.json"
        with open(esito_path, "w", encoding="utf-8") as f:
            json.dump(asdict(esito), f, ensure_ascii=False, indent=2)
        return str(esito_path)


class DepositoPenale:
    """
    Gestisce il deposito telematico nel processo penale tramite PDP
    (Portale Deposito Atti Penali del Ministero della Giustizia).

    Tipi di atti supportati:
    - Denuncia/Querela
    - Memoria difensiva
    - Opposizione a decreto penale
    - Richiesta di riesame
    """

    PDP_BASE_URL = "https://pdp.giustizia.it"

    def __init__(self, credenziali: dict):
        """
        Args:
            credenziali: Dict con 'username' e 'password' per il PST
        """
        self.credenziali = credenziali
        self._session_token = None

    def autentica(self) -> bool:
        """
        Autentica al Portale dei Servizi Telematici (PST).

        Returns:
            True se autenticazione riuscita
        """
        import requests

        try:
            resp = requests.post(
                f"{self.PDP_BASE_URL}/auth/login",
                json=self.credenziali,
                timeout=15,
            )
            resp.raise_for_status()
            self._session_token = resp.json().get("token")
            return bool(self._session_token)
        except requests.RequestException:
            return False

    def deposita_querela(
        self,
        atto_path: str,
        procura: str,
        dati_querelante: dict,
        dati_querelato: dict,
    ) -> dict:
        """
        Deposita una denuncia/querela tramite PDP.

        Args:
            atto_path: Percorso alla querela firmata digitalmente (.pdf.p7m)
            procura: Nome della Procura della Repubblica competente
            dati_querelante: Dati del querelante (nome, cf, ecc.)
            dati_querelato: Dati del querelato

        Returns:
            Esito del deposito con numero di protocollo
        """
        import requests

        if not self._session_token:
            raise RuntimeError("Autenticazione richiesta. Chiamare autentica() prima.")

        headers = {"Authorization": f"Bearer {self._session_token}"}

        with open(atto_path, "rb") as f:
            files = {"atto": (Path(atto_path).name, f, "application/octet-stream")}
            payload = {
                "tipo_atto": "QUERELA",
                "procura": procura,
                "querelante": json.dumps(dati_querelante),
                "querelato": json.dumps(dati_querelato),
            }
            try:
                resp = requests.post(
                    f"{self.PDP_BASE_URL}/deposito/querela",
                    headers=headers,
                    files=files,
                    data=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                return {"esito": "ERRORE", "messaggio": str(e)}
