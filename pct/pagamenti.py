"""
pct/pagamenti.py — Gestione pagamenti digitali multi-provider.

Provider supportati:
  ★ Stripe       — carte, SEPA, Apple Pay, Google Pay, Bancomat Pay
  ★ PayPal       — conto PayPal + carte
  ★ Satispay     — mobile payment italiano (consigliato per clienti IT)
  ★ SumUp        — carte online + POS fisico
  ★ Bonifico     — manuale SEPA (nessuna commissione)

Provider non inclusi per policy (retail B2C, non adatti studi legali):
  - Klarna, Scalapay, Afterpay (BNPL retail)

Commissioni indicative (2025):
  Stripe:   1.5 % + 0,25 € (carte EU)
  PayPal:   3.4 % + 0,35 €
  Satispay: 0 % < 10 €;  1 % > 10 € (max 1,50 €) — CONSIGLIATO
  SumUp:    1.69 % (carte)
  Bonifico: 0 % (manuale)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional


# ================================================================ Enumerazioni

class StatoPagamento(str):
    ATTESO    = "ATTESO"
    PAGATO    = "PAGATO"
    FALLITO   = "FALLITO"
    SCADUTO   = "SCADUTO"
    ANNULLATO = "ANNULLATO"


# ================================================================ Configurazione provider

@dataclass
class StripeConfig:
    abilitato:        bool  = False
    modo:             str   = "test"       # "test" | "live"
    pk_test:          str   = ""           # Publishable key test
    sk_test:          str   = ""           # Secret key test
    pk_live:          str   = ""
    sk_live:          str   = ""
    webhook_secret:   str   = ""           # whsec_...

    @property
    def pk(self) -> str:
        return self.pk_live if self.modo == "live" else self.pk_test

    @property
    def sk(self) -> str:
        return self.sk_live if self.modo == "live" else self.sk_test


@dataclass
class PayPalConfig:
    abilitato:        bool  = False
    modo:             str   = "sandbox"    # "sandbox" | "live"
    client_id:        str   = ""
    client_secret:    str   = ""

    @property
    def base_url(self) -> str:
        if self.modo == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"


@dataclass
class SatispayConfig:
    abilitato:        bool  = False
    modo:             str   = "sandbox"    # "sandbox" | "production"
    key_id:           str   = ""
    private_key_pem:  str   = ""           # chiave RSA privata

    @property
    def base_url(self) -> str:
        if self.modo == "production":
            return "https://authservices.satispay.com"
        return "https://staging.authservices.satispay.com"


@dataclass
class SumUpConfig:
    abilitato:        bool  = False
    api_key:          str   = ""           # Bearer token
    merchant_code:    str   = ""


@dataclass
class BonificoConfig:
    abilitato:        bool  = True
    iban:             str   = ""
    intestazione:     str   = ""
    banca:            str   = ""
    note_aggiuntive:  str   = ""


@dataclass
class ConfigPagamenti:
    stripe:   StripeConfig   = field(default_factory=StripeConfig)
    paypal:   PayPalConfig   = field(default_factory=PayPalConfig)
    satispay: SatispayConfig = field(default_factory=SatispayConfig)
    sumup:    SumUpConfig    = field(default_factory=SumUpConfig)
    bonifico: BonificoConfig = field(default_factory=BonificoConfig)

    def provider_attivi(self) -> List[str]:
        attivi = []
        if self.stripe.abilitato and self.stripe.sk:
            attivi.append("stripe")
        if self.paypal.abilitato and self.paypal.client_id:
            attivi.append("paypal")
        if self.satispay.abilitato and self.satispay.key_id:
            attivi.append("satispay")
        if self.sumup.abilitato and self.sumup.api_key:
            attivi.append("sumup")
        if self.bonifico.abilitato:
            attivi.append("bonifico")
        return attivi

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stripe":   asdict(self.stripe),
            "paypal":   asdict(self.paypal),
            "satispay": asdict(self.satispay),
            "sumup":    asdict(self.sumup),
            "bonifico": asdict(self.bonifico),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ConfigPagamenti":
        def _load(cls, key):
            raw = d.get(key, {})
            campi = set(cls.__dataclass_fields__)
            return cls(**{k: v for k, v in raw.items() if k in campi})
        return ConfigPagamenti(
            stripe=_load(StripeConfig, "stripe"),
            paypal=_load(PayPalConfig, "paypal"),
            satispay=_load(SatispayConfig, "satispay"),
            sumup=_load(SumUpConfig, "sumup"),
            bonifico=_load(BonificoConfig, "bonifico"),
        )


# ================================================================ Link di pagamento

@dataclass
class LinkPagamento:
    id:               str
    token:            str
    id_parcella:      str
    id_cliente:       str
    importo:          float
    descrizione:      str
    valuta:           str   = "EUR"
    stato:            str   = StatoPagamento.ATTESO
    creato_il:        str   = field(default_factory=lambda: datetime.now().isoformat())
    scade_il:         Optional[str] = None
    pagato_il:        Optional[str] = None
    provider_usato:   Optional[str] = None
    provider_tx_id:   Optional[str] = None  # ID transazione del provider
    note:             str   = ""

    @property
    def is_valido(self) -> bool:
        if self.stato != StatoPagamento.ATTESO:
            return False
        if self.scade_il:
            try:
                if datetime.now() > datetime.fromisoformat(self.scade_il):
                    return False
            except (ValueError, TypeError):
                pass
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "LinkPagamento":
        campi = set(LinkPagamento.__dataclass_fields__)
        return LinkPagamento(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Gestione

class GestionePagamenti:
    """Gestisce config provider e link di pagamento."""

    CONFIG_FILE = "config.json"

    def __init__(self, db_dir: str = "./pagamenti"):
        self.db_dir    = db_dir
        self._cfg_path = os.path.join(db_dir, "config.json")
        self._tx_path  = os.path.join(db_dir, "transazioni.json")
        self._config: ConfigPagamenti = ConfigPagamenti()
        self._link: Dict[str, LinkPagamento] = {}
        self._carica()

    # ---- I/O

    def _carica(self):
        os.makedirs(self.db_dir, exist_ok=True)
        if os.path.exists(self._cfg_path):
            with open(self._cfg_path, encoding="utf-8") as f:
                self._config = ConfigPagamenti.from_dict(json.load(f))
        if os.path.exists(self._tx_path):
            with open(self._tx_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._link = {k: LinkPagamento.from_dict(v) for k, v in raw.items()}

    def _salva_config(self):
        os.makedirs(self.db_dir, exist_ok=True)
        with open(self._cfg_path, "w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)

    def _salva_link(self):
        with open(self._tx_path, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self._link.items()},
                      f, ensure_ascii=False, indent=2)

    # ---- Config

    @property
    def config(self) -> ConfigPagamenti:
        return self._config

    def aggiorna_config(self, config: ConfigPagamenti):
        self._config = config
        self._salva_config()

    # ---- Link pagamento

    def crea_link(self,
                  id_parcella: str,
                  id_cliente: str,
                  importo: float,
                  descrizione: str,
                  giorni_validita: int = 30) -> LinkPagamento:
        token = secrets.token_urlsafe(32)
        scade = (datetime.now() + timedelta(days=giorni_validita)).isoformat()
        lp = LinkPagamento(
            id=str(uuid.uuid4()),
            token=token,
            id_parcella=id_parcella,
            id_cliente=id_cliente,
            importo=importo,
            descrizione=descrizione,
            scade_il=scade,
        )
        self._link[lp.id] = lp
        self._salva_link()
        return lp

    def get_by_token(self, token: str) -> Optional[LinkPagamento]:
        for lp in self._link.values():
            if hmac.compare_digest(lp.token, token):
                return lp
        return None

    def get_by_parcella(self, id_parcella: str) -> Optional[LinkPagamento]:
        for lp in self._link.values():
            if lp.id_parcella == id_parcella and lp.stato == StatoPagamento.ATTESO:
                return lp
        return None

    def segna_pagato(self, id_link: str, provider: str, tx_id: str = ""):
        lp = self._link.get(id_link)
        if lp:
            lp.stato          = StatoPagamento.PAGATO
            lp.pagato_il      = datetime.now().isoformat()
            lp.provider_usato = provider
            lp.provider_tx_id = tx_id
            self._salva_link()

    def segna_fallito(self, id_link: str, provider: str = ""):
        lp = self._link.get(id_link)
        if lp:
            lp.stato          = StatoPagamento.FALLITO
            lp.provider_usato = provider
            self._salva_link()

    def tutti_link(self) -> List[LinkPagamento]:
        return sorted(self._link.values(), key=lambda l: l.creato_il, reverse=True)

    # ---- Stripe helpers

    def stripe_crea_sessione(self, lp: LinkPagamento, success_url: str, cancel_url: str) -> str:
        """Crea una Stripe Checkout Session. Restituisce l'URL di checkout."""
        import stripe
        stripe.api_key = self._config.stripe.sk
        session = stripe.checkout.Session.create(
            payment_method_types=["card", "sepa_debit"],
            line_items=[{
                "price_data": {
                    "currency":     lp.valuta.lower(),
                    "unit_amount":  int(lp.importo * 100),  # in centesimi
                    "product_data": {"name": lp.descrizione},
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={"link_id": lp.id, "parcella": lp.id_parcella},
        )
        return session.url

    def stripe_verifica_webhook(self, payload: bytes, sig_header: str) -> Optional[Dict]:
        """Verifica firma webhook Stripe. Restituisce l'evento o None."""
        try:
            import stripe
            stripe.api_key = self._config.stripe.sk
            event = stripe.Webhook.construct_event(
                payload, sig_header, self._config.stripe.webhook_secret
            )
            return event
        except Exception:
            return None

    # ---- PayPal helpers

    def paypal_token(self) -> Optional[str]:
        """Ottieni access token PayPal via OAuth2."""
        import requests, base64
        cfg = self._config.paypal
        creds = base64.b64encode(f"{cfg.client_id}:{cfg.client_secret}".encode()).decode()
        try:
            r = requests.post(
                f"{cfg.base_url}/v1/oauth2/token",
                headers={"Authorization": f"Basic {creds}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials"},
                timeout=10,
            )
            return r.json().get("access_token")
        except Exception:
            return None

    def paypal_crea_ordine(self, lp: LinkPagamento, return_url: str, cancel_url: str) -> Optional[Dict]:
        """Crea ordine PayPal. Restituisce il dict con id e approve_url."""
        import requests
        token = self.paypal_token()
        if not token:
            return None
        cfg = self._config.paypal
        try:
            r = requests.post(
                f"{cfg.base_url}/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "amount": {"currency_code": lp.valuta, "value": f"{lp.importo:.2f}"},
                        "description": lp.descrizione,
                        "custom_id": lp.id,
                    }],
                    "application_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                        "brand_name": "Studio Legale PCT",
                        "user_action": "PAY_NOW",
                    },
                },
                timeout=10,
            )
            data = r.json()
            approve_url = next(
                (l["href"] for l in data.get("links", []) if l["rel"] == "approve"), None
            )
            return {"id": data.get("id"), "approve_url": approve_url}
        except Exception:
            return None

    def paypal_cattura_ordine(self, order_id: str) -> bool:
        """Cattura (completa) un ordine PayPal approvato."""
        import requests
        token = self.paypal_token()
        if not token:
            return False
        cfg = self._config.paypal
        try:
            r = requests.post(
                f"{cfg.base_url}/v2/checkout/orders/{order_id}/capture",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                timeout=10,
            )
            return r.json().get("status") == "COMPLETED"
        except Exception:
            return False

    # ---- SumUp helpers

    def sumup_crea_checkout(self, lp: LinkPagamento, return_url: str) -> Optional[Dict]:
        """Crea checkout SumUp. Restituisce checkout_id."""
        import requests
        cfg = self._config.sumup
        try:
            r = requests.post(
                "https://api.sumup.com/v0.1/checkouts",
                headers={"Authorization": f"Bearer {cfg.api_key}",
                         "Content-Type": "application/json"},
                json={
                    "checkout_reference": lp.id,
                    "amount":            lp.importo,
                    "currency":          lp.valuta,
                    "pay_to_email":      "",
                    "merchant_code":     cfg.merchant_code,
                    "description":       lp.descrizione,
                    "return_url":        return_url,
                },
                timeout=10,
            )
            data = r.json()
            return {"checkout_id": data.get("id"), "status": data.get("status")}
        except Exception:
            return None

    # ---- Satispay helpers (HTTP Signature)

    def satispay_crea_pagamento(self, lp: LinkPagamento, callback_url: str) -> Optional[Dict]:
        """Crea richiesta di pagamento Satispay."""
        import requests, time, base64
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        cfg = self._config.satispay
        if not cfg.private_key_pem or not cfg.key_id:
            return None
        try:
            amountUnit = int(lp.importo * 100)
            body = json.dumps({
                "flow":          "MATCH_CODE",
                "amount_unit":   amountUnit,
                "currency":      lp.valuta,
                "description":   lp.descrizione,
                "callback_url":  callback_url,
                "metadata":      {"link_id": lp.id},
            })
            # Firma HTTP Signature
            digest = base64.b64encode(
                hashlib.sha256(body.encode()).digest()
            ).decode()
            date_header = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            sign_string = (f"(request-target): post /g_business/v1/payment_requests\n"
                           f"host: {cfg.base_url.replace('https://', '')}\n"
                           f"date: {date_header}\n"
                           f"digest: SHA-256={digest}")
            private_key = serialization.load_pem_private_key(
                cfg.private_key_pem.encode(), password=None)
            sig_bytes = private_key.sign(sign_string.encode(), padding.PKCS1v15(), hashes.SHA256())
            sig_b64 = base64.b64encode(sig_bytes).decode()
            auth_header = (f'Signature keyId="{cfg.key_id}",'
                           f'algorithm="rsa-sha256",'
                           f'headers="(request-target) host date digest",'
                           f'signature="{sig_b64}"')
            r = requests.post(
                f"{cfg.base_url}/g_business/v1/payment_requests",
                headers={
                    "Authorization": auth_header,
                    "Date":          date_header,
                    "Digest":        f"SHA-256={digest}",
                    "Content-Type":  "application/json",
                },
                data=body,
                timeout=10,
            )
            data = r.json()
            return {"id": data.get("id"), "redirect_url": data.get("redirect_url"),
                    "code_identifier": data.get("code_identifier")}
        except Exception as e:
            return {"errore": str(e)}
