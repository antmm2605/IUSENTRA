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
                expires = datetime.fromisoformat(self.scade_il)
                if datetime.now(expires.tzinfo) > expires:
                    return False
            except (ValueError, TypeError):
                return False
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

    def __init__(self, db_dir: str = "./pagamenti", studio_db=None):
        self.db_dir    = db_dir
        self._cfg_path = os.path.join(db_dir, "config.json")
        self._tx_path  = os.path.join(db_dir, "transazioni.json")
        self._studio_db = studio_db
        self._config: ConfigPagamenti = ConfigPagamenti()
        self._link: Dict[str, LinkPagamento] = {}
        self._original_links: Dict[str, dict] = {}
        self._saved_links: Dict[str, dict] = {}
        self._carica()

    # ---- I/O

    def _carica(self):
        if self._studio_db is not None:
            config_rows = self._studio_db.carica_tabella("payment_config")
            if config_rows:
                try:
                    payload = config_rows[0]
                    self._config = ConfigPagamenti.from_dict(payload if isinstance(payload, dict) else {})
                except Exception:
                    self._config = ConfigPagamenti()
            # I collegamenti si leggono soltanto quando richiesti: i comandi
            # del singolo pagamento non caricano l'archivio dello studio.
            return
        os.makedirs(self.db_dir, exist_ok=True)
        if os.path.exists(self._cfg_path):
            with open(self._cfg_path, encoding="utf-8") as f:
                self._config = ConfigPagamenti.from_dict(json.load(f))
        if os.path.exists(self._tx_path):
            with open(self._tx_path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                payloads = raw.values()
            elif isinstance(raw, list):
                payloads = raw
            else:
                payloads = []
            self._link = {}
            for payload in payloads:
                try:
                    link = LinkPagamento.from_dict(payload)
                except Exception:
                    continue
                self._link[link.id] = link

    def _salva_config(self):
        if self._studio_db is not None:
            payload = self._config.to_dict()

            def _insert(conn, row):
                conn.execute(
                    """
                    INSERT INTO payment_config
                    (config_id, provider_count, updated_at, dati_json)
                    VALUES (?,?,?,?)
                    """,
                    (
                        "default",
                        len(self._config.provider_attivi()),
                        datetime.now().isoformat(),
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("payment_config", [payload], _insert)
            return
        os.makedirs(self.db_dir, exist_ok=True)
        with open(self._cfg_path, "w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)

    def _salva_link(self, link_id=None, *, replace_ids=(), before_write=None):
        if self._studio_db is not None:
            from pct.payment_links_sql import save_links
            selected = self._link if link_id is None else {key: self._link[key] for key in (*replace_ids, link_id)}
            sources = {key: value for key, value in self._original_links.items() if key in selected}
            saved = {key: value for key, value in self._saved_links.items() if key in selected}
            self._original_links.update(save_links(self._studio_db, selected, sources, saved, before_write=before_write))
            self._saved_links.update({key: value.to_dict() for key, value in selected.items()})
            return
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
                  giorni_validita: int = 30, *, replace_pending=False, expected_invoice_revision=None,
                  _expires_at=None) -> LinkPagamento:
        token = secrets.token_urlsafe(32)
        scade = (datetime.now() + timedelta(days=giorni_validita)).isoformat()
        if _expires_at is not None:
            datetime.fromisoformat(_expires_at)
            scade = _expires_at
        lp = LinkPagamento(
            id=str(uuid.uuid4()),
            token=token,
            id_parcella=id_parcella,
            id_cliente=id_cliente,
            importo=importo,
            descrizione=descrizione,
            scade_il=scade,
        )
        previous = (self._sql_links(invoice_id=id_parcella, pending=True) if self._studio_db is not None else
                    [item for item in self._link.values() if item.id_parcella == id_parcella and item.stato == 'ATTESO']) if replace_pending else []
        if any(item.id_cliente != id_cliente for item in previous):
            raise ValueError('Un collegamento precedente indica un cliente discordante: verifica la provenienza prima di sostituirlo.')
        snapshots = {item.id: item.to_dict() for item in previous}
        for item in previous:
            item.stato = StatoPagamento.FALLITO
        self._link[lp.id] = lp

        def verify_invoice(conn):
            if expected_invoice_revision is None:
                return
            from pct.fatturazione import Parcella, parcella_revision, ParcellaConcurrentUpdate
            postgres = getattr(self._studio_db, 'backend_kind', '') == 'postgresql'
            row = conn.execute('SELECT dati_json FROM parcelle WHERE id=?' + (' FOR UPDATE' if postgres else ''),
                               (id_parcella,)).fetchone()
            invoice = Parcella.from_dict(json.loads(row[0])) if row else None
            if invoice is None or invoice.id_cliente != id_cliente or parcella_revision(invoice) != expected_invoice_revision:
                raise ParcellaConcurrentUpdate('Documento aggiornato: rileggi il residuo prima di creare il pagamento.')
        try:
            self._salva_link(lp.id, replace_ids=tuple(snapshots), before_write=verify_invoice)
        except Exception:
            self._link.pop(lp.id, None)
            for item in previous:
                for key, value in snapshots[item.id].items():
                    setattr(item, key, value)
            raise
        return lp

    def get_by_token(self, token: str) -> Optional[LinkPagamento]:
        if self._studio_db is not None:
            from pct.payment_links_sql import read_link
            payload = read_link(self._studio_db, token=token)
            return self._remember_sql_link(payload) if payload is not None else None
        for lp in self._link.values():
            if hmac.compare_digest(lp.token, token):
                return lp
        return None

    def get_by_id(self, link_id: str) -> Optional[LinkPagamento]:
        if self._studio_db is not None:
            from pct.payment_links_sql import read_link
            payload = read_link(self._studio_db, key=link_id)
            return self._remember_sql_link(payload) if payload is not None else None
        return self._link.get(link_id)

    def _remember_sql_link(self, payload):
        from pct.payment_links_sql import PaymentLinkConflict
        # Un timestamp assente nella fonte resta non determinato: il default
        # del costruttore serve alle nuove creazioni, non alla consultazione.
        loaded = LinkPagamento.from_dict({**payload, 'creato_il': payload.get('creato_il')})
        current = self._link.get(loaded.id)
        if current is not None and current.to_dict() != self._saved_links.get(loaded.id):
            if payload != self._original_links.get(loaded.id):
                raise PaymentLinkConflict('Collegamento cambiato: le modifiche locali sono conservate.')
            return current
        if current is None:
            current = loaded
        else:
            for key, value in loaded.to_dict().items():
                setattr(current, key, value)
        self._link[current.id] = current
        self._original_links[current.id] = dict(payload)
        self._saved_links[current.id] = current.to_dict()
        return current

    def _sql_links(self, **filters):
        from pct.payment_links_sql import read_links
        return [self._remember_sql_link(payload) for payload in read_links(self._studio_db, **filters)]

    def get_by_parcella(self, id_parcella: str) -> Optional[LinkPagamento]:
        if self._studio_db is not None:
            links = self._sql_links(invoice_id=id_parcella, pending=True, limit=1)
            return links[0] if links else None
        for lp in self._link.values():
            if lp.id_parcella == id_parcella and lp.stato == StatoPagamento.ATTESO:
                return lp
        return None

    def segna_pagato(self, id_link: str, provider: str, tx_id: str = ""):
        lp = self.get_by_id(id_link)
        if lp:
            if self._studio_db is not None:
                from pct.payment_links_sql import confirmed_link
                replay = confirmed_link(self._studio_db, id_link, provider, tx_id)
                if replay is not None:
                    restored = LinkPagamento.from_dict(replay)
                    for key, value in restored.to_dict().items():
                        setattr(lp, key, value)
                    self._original_links[id_link] = replay
                    self._saved_links[id_link] = lp.to_dict()
                    return
            previous = lp.to_dict()
            lp.stato          = StatoPagamento.PAGATO
            lp.pagato_il      = datetime.now().isoformat()
            lp.provider_usato = provider
            lp.provider_tx_id = tx_id
            try:
                self._salva_link(id_link)
            except Exception:
                for key, value in previous.items():
                    setattr(lp, key, value)
                raise

    def segna_fallito(self, id_link: str, provider: str = ""):
        lp = self.get_by_id(id_link)
        if lp:
            previous = lp.to_dict()
            lp.stato          = StatoPagamento.FALLITO
            lp.provider_usato = provider
            try:
                self._salva_link(id_link)
            except Exception:
                for key, value in previous.items():
                    setattr(lp, key, value)
                raise

    def tutti_link(self) -> List[LinkPagamento]:
        if self._studio_db is not None:
            return self._sql_links()
        return sorted(self._link.values(), key=lambda l: l.creato_il or '', reverse=True)

    def link_per_cliente(self, id_cliente: str) -> List[LinkPagamento]:
        if self._studio_db is not None:
            return self._sql_links(client_id=id_cliente)
        return [item for item in self.tutti_link() if item.id_cliente == id_cliente]

    def link_per_parcella(self, id_parcella: str) -> List[LinkPagamento]:
        if self._studio_db is not None:
            return self._sql_links(invoice_id=id_parcella)
        return [item for item in self.tutti_link() if item.id_parcella == id_parcella]

    def statistiche(self) -> Dict[str, Any]:
        links = self.tutti_link()
        return {
            "totale_link": len(links),
            "attesi": sum(1 for row in links if row.stato == StatoPagamento.ATTESO),
            "pagati": sum(1 for row in links if row.stato == StatoPagamento.PAGATO),
            "falliti": sum(1 for row in links if row.stato == StatoPagamento.FALLITO),
            "scaduti": sum(1 for row in links if row.stato == StatoPagamento.SCADUTO),
            "importo_atteso": round(sum(row.importo for row in links if row.stato == StatoPagamento.ATTESO), 2),
            "importo_pagato": round(sum(row.importo for row in links if row.stato == StatoPagamento.PAGATO), 2),
        }

    # ---- Stripe helpers

    def stripe_crea_sessione(self, lp: LinkPagamento, success_url: str, cancel_url: str) -> str:
        """Crea una Stripe Checkout Session. Restituisce l'URL di checkout."""
        import stripe
        from pct.payment_evidence import exact_cents
        stripe.api_key = self._config.stripe.sk
        session = stripe.checkout.Session.create(
            payment_method_types=["card", "sepa_debit"],
            line_items=[{
                "price_data": {
                    "currency":     lp.valuta.lower(),
                    "unit_amount":  exact_cents(lp.importo),
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
                        "brand_name": "IUSENTRA",
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

    def paypal_cattura_ordine(self, order_id: str, *, evidence=False):
        """Cattura (completa) un ordine PayPal approvato."""
        import requests
        from urllib.parse import quote
        token = self.paypal_token()
        if not token:
            return False
        cfg = self._config.paypal
        try:
            r = requests.post(
                f"{cfg.base_url}/v2/checkout/orders/{quote(order_id, safe='')}/capture",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json",
                         "Prefer": "return=representation",
                         "PayPal-Request-Id": str(uuid.uuid5(uuid.NAMESPACE_URL, 'iusentra-paypal-capture:' + order_id))},
                timeout=10,
            )
            response = r.json()
            if evidence:
                return response if r.status_code in (200, 201) and response.get('status') == 'COMPLETED' else False
            return response.get("status") == "COMPLETED"
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
        from pct.payment_evidence import exact_cents

        cfg = self._config.satispay
        if not cfg.private_key_pem or not cfg.key_id:
            return None
        try:
            amountUnit = exact_cents(lp.importo)
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

