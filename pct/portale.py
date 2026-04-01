"""
pct/portale.py — Portale Cliente self-service.

Permette all'avvocato di generare un link sicuro per il cliente che può:
  - Visualizzare lo stato dei propri fascicoli
  - Firmare la privacy GDPR digitalmente
  - Caricare documenti dalla fotocamera del cellulare o scanner
  - Aggiornare i propri recapiti
  - Vedere i prossimi appuntamenti

Il link è protetto da token HMAC-SHA256 (256 bit, imforzabile).
I permessi sono granulari per cliente e configurabili dall'avvocato.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple


# ================================================================ Permessi

@dataclass
class PermessiPortale:
    """Controllo granulare di cosa vede/può fare il cliente nel portale."""
    vedi_anagrafica:      bool = True
    modifica_anagrafica:  bool = False   # cliente può aggiornare i recapiti
    vedi_fascicoli:       bool = True
    vedi_attivita:        bool = False   # timeline attività processuali
    vedi_appuntamenti:    bool = False   # prossimi appuntamenti
    vedi_scadenze:        bool = False   # scadenze del fascicolo
    carica_documenti:     bool = True
    firma_privacy:        bool = True
    max_upload_mb:        int  = 10      # limite singolo file

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "PermessiPortale":
        campi = {k for k in PermessiPortale.__dataclass_fields__}
        return PermessiPortale(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Portale

@dataclass
class PortaleCliente:
    """Record del portale di un cliente."""
    id:                   str
    id_cliente:           str
    token_hash:           str               # SHA-256 del token grezzo (mai salvare il raw)
    permessi:             PermessiPortale
    attivo:               bool  = True
    creato_il:            str   = field(default_factory=lambda: datetime.now().isoformat())
    scade_il:             Optional[str] = None   # ISO datetime, None = nessuna scadenza
    creato_da:            str   = ""
    n_accessi:            int   = 0
    ultimo_accesso:       Optional[str] = None
    ip_ultimo_accesso:    Optional[str] = None
    # Firma privacy
    privacy_firmata:      bool  = False
    data_firma_privacy:   Optional[str] = None
    ip_firma_privacy:     Optional[str] = None
    ua_firma_privacy:     Optional[str] = None  # User-Agent al momento della firma

    @property
    def is_attivo(self) -> bool:
        if not self.attivo:
            return False
        if self.scade_il:
            try:
                if datetime.now() > datetime.fromisoformat(self.scade_il):
                    return False
            except (ValueError, TypeError):
                pass
        return True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "PortaleCliente":
        d = dict(d)
        permessi_d = d.pop("permessi", {})
        d["permessi"] = PermessiPortale.from_dict(permessi_d)
        campi = set(PortaleCliente.__dataclass_fields__)
        return PortaleCliente(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Gestore

class GestionePortale:
    """Gestisce la creazione, verifica e revoca dei portali cliente."""

    def __init__(self, db_path: str = "./portale/portali.json",
                 uploads_dir: str = "./portale/uploads"):
        self.db_path   = db_path
        self.uploads_dir = uploads_dir
        self._portali: Dict[str, PortaleCliente] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._portali = {k: PortaleCliente.from_dict(v) for k, v in raw.items()}

    def _salva(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._portali.items()},
                f, ensure_ascii=False, indent=2
            )

    # ---------------------------------------------------------------- Token

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    # ---------------------------------------------------------------- CRUD

    def crea(self,
             id_cliente: str,
             creato_da: str,
             permessi: Optional[PermessiPortale] = None,
             scade_il: Optional[str] = None) -> Tuple[str, PortaleCliente]:
        """
        Crea (o rinnova) il portale per un cliente.
        Restituisce (token_grezzo, PortaleCliente).
        Salvare il token_grezzo da inviare al cliente; non viene mai riesposto.
        """
        # Disattiva eventuali portali precedenti dello stesso cliente
        for p in self._portali.values():
            if p.id_cliente == id_cliente and p.attivo:
                p.attivo = False

        token_grezzo = secrets.token_urlsafe(32)
        portale = PortaleCliente(
            id=str(uuid.uuid4()),
            id_cliente=id_cliente,
            token_hash=self._hash_token(token_grezzo),
            permessi=permessi or PermessiPortale(),
            creato_da=creato_da,
            scade_il=scade_il,
        )
        self._portali[portale.id] = portale
        self._salva()
        return token_grezzo, portale

    def verifica_token(self, token_grezzo: str) -> Optional[PortaleCliente]:
        """Verifica il token e restituisce il portale se valido e attivo."""
        h = self._hash_token(token_grezzo)
        for p in self._portali.values():
            if hmac.compare_digest(p.token_hash, h):
                return p if p.is_attivo else None
        return None

    def get_by_cliente(self, id_cliente: str) -> Optional[PortaleCliente]:
        """Restituisce il portale attivo di un cliente (se esiste)."""
        for p in self._portali.values():
            if p.id_cliente == id_cliente and p.is_attivo:
                return p
        return None

    def get(self, id_portale: str) -> Optional[PortaleCliente]:
        return self._portali.get(id_portale)

    def tutti(self, includi_inattivi: bool = True) -> List[PortaleCliente]:
        portali = sorted(self._portali.values(), key=lambda p: p.creato_il, reverse=True)
        if includi_inattivi:
            return portali
        return [p for p in portali if p.is_attivo]

    def aggiorna_permessi(self, id_portale: str, permessi: PermessiPortale) -> PortaleCliente:
        p = self._portali[id_portale]
        p.permessi = permessi
        self._salva()
        return p

    def revoca(self, id_portale: str):
        if id_portale in self._portali:
            self._portali[id_portale].attivo = False
            self._salva()

    def registra_accesso(self, id_portale: str, ip: str):
        p = self._portali.get(id_portale)
        if p:
            p.n_accessi += 1
            p.ultimo_accesso    = datetime.now().isoformat()
            p.ip_ultimo_accesso = ip
            self._salva()

    def registra_firma_privacy(self, id_portale: str, ip: str, user_agent: str):
        p = self._portali.get(id_portale)
        if p:
            p.privacy_firmata    = True
            p.data_firma_privacy = datetime.now().isoformat()
            p.ip_firma_privacy   = ip
            p.ua_firma_privacy   = user_agent[:300] if user_agent else ""
            self._salva()

    # ---------------------------------------------------------------- Upload dir

    def upload_dir(self, id_cliente: str) -> str:
        d = os.path.join(self.uploads_dir, id_cliente)
        os.makedirs(d, exist_ok=True)
        return d
