"""Strumenti del collaudo end-to-end della catena: orologio governato e pratica di prova su uno studio temporaneo.

I documenti entrano dal punto d'ingresso reale (``GestioneFascicoli.aggiungi_documento``, con l'osservatore che accoda
l'evento del registro), la lettura passa dal ciclo vero (``archivio_letture_runtime.leggi_fascicolo``: registro,
catalogo, archivio dei fatti, consegna ai presìdi, Lettura preparata), la Lettura dal contesto vero
(``load_fascicolo_lettura_context``) e il guardiano dal runtime vero. Il giorno corrente è governato da ``Orologio``
per far avanzare la pratica (udienza fissata, provvedimento, sentenza, giudicato) senza aspettare i mesi veri.
Dati fittizi: nessun dato reale di clienti.
"""

from __future__ import annotations

import datetime as _dt
import importlib
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")
_VERO_DATETIME, _VERA_DATE = _dt.datetime, _dt.date

# I moduli della catena che leggono il giorno corrente (grep di datetime.now, date.today, oggi_roma: 19/11/2026).
MODULI_CON_OROLOGIO = (
    "pct.ora_italiana", "pct.ragionamento.motore", "pct.fascicolo_lettura", "pct.archivio_letture.presidi",
    "pct.archivio_letture.ciclo", "web.services.consegna_presidi_runtime", "pct.agenda", "pct.scadenziario",
    "web.services.archivio_letture_runtime", "web.services.sentenza_proposte_runtime",
    "web.services.rettifiche_termini_runtime", "pct.pannelli_pronti.impronta", "web.services.bozze_passi_runtime",
    "lex.context.fascicolo_lettura_context", "web.services.ragionamento_raccolta",
)


class _MetaDatetime(type):
    def __instancecheck__(cls, oggetto):
        return isinstance(oggetto, _VERO_DATETIME)


class _MetaDate(type):
    def __instancecheck__(cls, oggetto):
        return isinstance(oggetto, _VERA_DATE)


class Orologio:
    """Il giorno corrente della pratica di prova (ora fissa 10:00 a Roma)."""

    def __init__(self) -> None:
        self.adesso = _VERO_DATETIME(2026, 1, 1, 10, 0, tzinfo=ROMA)

    def al(self, giorno: str, ora: str = "10:00") -> None:
        h, m = (int(x) for x in ora.split(":"))
        self.adesso = _VERO_DATETIME.fromisoformat(giorno).replace(hour=h, minute=m, tzinfo=ROMA)

    @property
    def oggi(self) -> _dt.date:
        return self.adesso.date()

    def classi(self):
        orologio = self

        class FintoDatetime(_VERO_DATETIME, metaclass=_MetaDatetime):
            @classmethod
            def now(cls, tz=None):
                return orologio.adesso.astimezone(tz) if tz else orologio.adesso.replace(tzinfo=None)

            @classmethod
            def today(cls):
                return orologio.adesso.replace(tzinfo=None)

            @classmethod
            def utcnow(cls):
                return orologio.adesso.astimezone(_dt.timezone.utc).replace(tzinfo=None)

        class FintaDate(_VERA_DATE, metaclass=_MetaDate):
            @classmethod
            def today(cls):
                return orologio.adesso.date()

        return FintoDatetime, FintaDate

    def installa(self, monkeypatch) -> None:
        finto_datetime, finta_date = self.classi()
        for nome in MODULI_CON_OROLOGIO:
            modulo = importlib.import_module(nome)
            if getattr(modulo, "datetime", None) is _VERO_DATETIME:
                monkeypatch.setattr(modulo, "datetime", finto_datetime)
            if getattr(modulo, "date", None) is _VERA_DATE:
                monkeypatch.setattr(modulo, "date", finta_date)
            if callable(getattr(modulo, "oggi_roma", None)):
                monkeypatch.setattr(modulo, "oggi_roma", lambda: self.oggi)


def pdf(righe: list[str]) -> bytes:
    from tests.test_archivio_letture_runtime import _pdf

    return _pdf(righe)


_CLIENT = "_catena_collaudo_client"


def client_dello_studio(app):
    """Un avvocato dello studio con la sessione aperta (stesso accesso della pagina)."""
    client = app.extensions.get(_CLIENT)
    if client is None:
        from tests.test_topbar_operational_api import _create_user, _login

        _create_user(app, "operatore", "Operatore123!")
        app.config["LEX_INDEXING_SYNC"] = True
        client = app.test_client()
        _login(client)
        app.extensions[_CLIENT] = client
    return client


@dataclass
class Fotografia:
    """Ciò che la pratica mostra dopo un passo: modello, Lettura, scadenziario, agenda, guardiano."""

    lettura: dict[str, Any]
    guardiano: dict[str, Any]
    scadenze: list[dict[str, Any]]
    agenda: list[dict[str, Any]]
    stato: str
    note: list[str] = field(default_factory=list)

    @property
    def ragionamento(self) -> dict[str, Any]:
        return self.lettura.get("ragionamento") or {}

    def conclusione(self, codice: str) -> dict[str, Any] | None:
        return next((c for c in self.ragionamento.get("conclusioni") or [] if c.get("codice") == codice), None)

    def aperte(self) -> list[dict[str, Any]]:
        return [s for s in self.scadenze if s["stato"] in {"APERTO", "BOZZA"}]

    def scadenza_il(self, giorno: str, *, stato: str = "APERTO") -> list[dict[str, Any]]:
        return [s for s in self.scadenze if s["data"] == giorno and s["stato"] == stato]

    def udienze(self) -> list[dict[str, Any]]:
        return [a for a in self.agenda if a["tipo"] == "UDIENZA" and a["stato"] not in {"ANNULLATO"}]

    def avvisi(self) -> list[str]:
        return [v["codice"] for v in self.guardiano.get("incoerenze") or [] if not str(v.get("esito_riparazione", "")).startswith("riparata")]

    def passi(self) -> list[str]:
        return [p.get("azione", "") for p in self.lettura.get("prossimi_passi") or []]


class Pratica:
    """Una pratica di prova nello studio temporaneo."""

    def __init__(self, app, orologio: Orologio, *, titolo: str, tipo, cliente: str, controparte: str, ufficio: str,
                 rg: str = "", anno: int = 2026, codice_oggetto: str = "", **altro) -> None:
        self.app, self.orologio = app, orologio
        with app.app_context():
            fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().nuovo(
                titolo, tipo, nome_cliente=cliente, tribunale=ufficio, numero_rg=rg, anno_rg=anno, controparte=controparte,
                codice_oggetto_pst=codice_oggetto, **altro)
        self.id = fascicolo.id

    def documento(self, nome: str, righe: list[str]) -> str:
        """Il caricamento dello studio dalla pagina del fascicolo: la stessa rotta, l'indicizzazione e l'evento veri."""
        import io

        risposta = client_dello_studio(self.app).post(
            f"/fascicoli/{self.id}/documenti/carica",
            data={"files": (io.BytesIO(pdf(righe)), nome), "classificazione_modalita": "auto"},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
            content_type="multipart/form-data",
        )
        dati = risposta.get_json() or {}
        assert risposta.status_code == 200 and dati.get("ok") and dati.get("documenti_id"), dati
        return dati["documenti_id"][0]

    def leggi(self) -> Fotografia:
        """Il ciclo vero delle letture, la Lettura vera e il guardiano, nel contesto dello studio."""
        with self.app.test_request_context("/"):
            from flask import g
            from types import SimpleNamespace

            g.utente_corrente = SimpleNamespace(id="avv1", username="avv1", ruolo="admin", is_admin=True,
                                                ha_permesso=lambda _p: True)
            from lex.context.fascicolo_lettura_context import load_fascicolo_lettura_context
            from web.helpers import get_fascicoli, get_scadenziario
            from web.services.archivio_letture_runtime import leggi_fascicolo
            from web.services.catena_guardiano_raccolta import appuntamenti
            from web.services.catena_guardiano_runtime import controlla_fascicolo

            fascicolo = get_fascicoli().get(self.id)
            self.ultimo_ciclo = leggi_fascicolo(fascicolo, forza=True)
            lettura = load_fascicolo_lettura_context(fascicolo_id=self.id)
            guardiano = controlla_fascicolo(self.id, origine="collaudo", lettura=lettura, oggi=self.orologio.oggi)
            # Le riparazioni hanno scritto: la Lettura successiva le vede (come il ricalcolo dopo l'impronta).
            lettura = load_fascicolo_lettura_context(fascicolo_id=self.id)
            fascicolo = get_fascicoli().get(self.id)
            scadenze = [{"id": s.id, "titolo": s.titolo, "data": str(s.data_scadenza or "")[:10],
                         "stato": str(getattr(s.stato, "value", s.stato)), "note": s.note or ""}
                        for s in get_scadenziario().tutte(id_fascicolo=self.id, solo_aperte=False)]
            agenda = appuntamenti(fascicolo)
            return Fotografia(lettura=lettura, guardiano=guardiano, scadenze=scadenze, agenda=agenda,
                              stato=str(getattr(fascicolo.stato, "value", fascicolo.stato)))

    def ricontrolla(self) -> dict[str, Any]:
        """Un secondo giro del guardiano sulla stessa Lettura: la catena è chiusa se non trova più nulla."""
        with self.app.test_request_context("/"):
            from lex.context.fascicolo_lettura_context import load_fascicolo_lettura_context
            from web.services.catena_guardiano_runtime import controlla_fascicolo

            lettura = load_fascicolo_lettura_context(fascicolo_id=self.id)
            return controlla_fascicolo(self.id, origine="collaudo", lettura=lettura, oggi=self.orologio.oggi)
