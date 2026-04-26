"""Adapter dai domini IUSENTRA verso documenti indicizzabili."""

from __future__ import annotations

from typing import Any, Iterable

from pct.compilatore_atti import elenco_modelli

from .models import GlobalSearchDocument
from .normalizer import clean_text, italian_date


def as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            return {}
    data: dict[str, Any] = {}
    for key in dir(obj):
        if key.startswith("_"):
            continue
        try:
            value = getattr(obj, key)
        except Exception:
            continue
        if not callable(value) and isinstance(value, (str, int, float, bool, list, dict, type(None))):
            data[key] = value
    return data


def _manager_items(manager: Any, *method_names: str, **kwargs: Any) -> list[Any]:
    if manager is None:
        return []
    for name in method_names:
        method = getattr(manager, name, None)
        if not callable(method):
            continue
        try:
            return list(method(**kwargs))
        except TypeError:
            try:
                return list(method())
            except Exception:
                continue
        except Exception:
            continue
    return []


def _join(*values: Any) -> str:
    return " ".join(clean_text(value) for value in values if clean_text(value))


def _first(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean_text(data.get(key))
        if value:
            return value
    return ""


class BaseSearchAdapter:
    entity_type = "record"
    source_module = "studio"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        return []

    def _doc(
        self,
        context: dict[str, Any],
        *,
        entity_id: str,
        title: str,
        subtitle: str = "",
        body: str = "",
        keywords: str = "",
        metadata: dict[str, Any] | None = None,
        source_url: str = "",
        client_id: str = "",
        fascicolo_id: str = "",
        pratica_id: str = "",
        entity_type: str | None = None,
    ) -> GlobalSearchDocument:
        metadata = dict(metadata or {})
        metadata.setdefault("icon", self.icon_for(entity_type or self.entity_type))
        metadata.setdefault("badges", [self.label_for(entity_type or self.entity_type)])
        metadata.setdefault("actions", self.actions_for(source_url, entity_type or self.entity_type))
        return GlobalSearchDocument(
            tenant_id=str(context.get("tenant_id") or "default"),
            entity_type=entity_type or self.entity_type,
            entity_id=str(entity_id),
            title=clean_text(title),
            subtitle=clean_text(subtitle),
            body=clean_text(body),
            keywords=clean_text(keywords),
            metadata=metadata,
            client_id=clean_text(client_id),
            fascicolo_id=clean_text(fascicolo_id),
            pratica_id=clean_text(pratica_id),
            source_module=self.source_module,
            source_url=source_url or "/",
            visibility="studio",
            permission_scope="studio",
            created_at=clean_text(metadata.get("created_at", "")),
            updated_at=clean_text(metadata.get("updated_at", metadata.get("date", ""))),
        )

    @staticmethod
    def icon_for(entity_type: str) -> str:
        return {
            "fascicolo": "bi-folder2-open",
            "cliente": "bi-person-vcard",
            "soggetto": "bi-people",
            "scadenza": "bi-alarm",
            "appuntamento": "bi-calendar-event",
            "udienza": "bi-building",
            "attivita": "bi-list-task",
            "documento": "bi-file-earmark-text",
            "preventivo": "bi-file-ruled",
            "conferimento": "bi-pen",
            "fattura": "bi-receipt",
            "pagamento": "bi-credit-card",
            "comunicazione": "bi-envelope-paper",
            "template_atto": "bi-file-earmark-richtext",
            "deposito": "bi-send-check",
            "legal_intelligence": "bi-diagram-3",
        }.get(entity_type, "bi-search")

    @staticmethod
    def label_for(entity_type: str) -> str:
        return {
            "fascicolo": "Fascicolo",
            "cliente": "Cliente",
            "soggetto": "Soggetto",
            "scadenza": "Scadenza",
            "appuntamento": "Agenda",
            "udienza": "Udienza",
            "attivita": "Attivita",
            "documento": "Documento",
            "preventivo": "Preventivo",
            "conferimento": "Conferimento",
            "fattura": "Fattura",
            "pagamento": "Pagamento",
            "comunicazione": "Comunicazione",
            "template_atto": "Template atto",
            "deposito": "Telematico",
            "legal_intelligence": "Intelligence",
        }.get(entity_type, entity_type)

    @staticmethod
    def actions_for(source_url: str, entity_type: str) -> list[dict[str, str]]:
        actions = [{"label": "Apri", "url": source_url or "/", "kind": "open"}]
        if entity_type in {"documento", "fascicolo", "deposito", "scadenza", "comunicazione"}:
            actions.append({"label": "Chiedi a Lex", "url": f"/assistente?context={entity_type}", "kind": "lex"})
        return actions


class FascicoliSearchAdapter(BaseSearchAdapter):
    entity_type = "fascicolo"
    source_module = "fascicoli"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("fascicoli"), "tutti", archiviati=True):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if not entity_id:
                continue
            rg = _first(data, "numero_rg", "numero", "n_registro")
            title = _join(f"RG {rg}" if rg else "", _first(data, "titolo", "oggetto"))
            metadata = {
                "stato": _first(data, "stato"),
                "numero_rg": rg,
                "rg": rg,
                "date": italian_date(_first(data, "data_apertura", "apertura", "created_at")),
            }
            docs.append(
                self._doc(
                    context,
                    entity_id=entity_id,
                    title=title or f"Fascicolo {entity_id}",
                    subtitle=_join(_first(data, "nome_cliente", "cliente"), _first(data, "controparte")),
                    body=_join(
                        _first(data, "oggetto", "titolo"),
                        _first(data, "tribunale", "autorita"),
                        _first(data, "giudice"),
                        _first(data, "note"),
                        _first(data, "avvocato_referente"),
                    ),
                    keywords=_join(rg, _first(data, "numero"), _first(data, "id_pratica")),
                    metadata=metadata,
                    source_url=f"/fascicoli/{entity_id}",
                    client_id=_first(data, "id_cliente", "cliente_id"),
                    fascicolo_id=entity_id,
                    pratica_id=_first(data, "id_pratica", "numero"),
                )
            )
        return docs


class DocumentiSearchAdapter(BaseSearchAdapter):
    entity_type = "documento"
    source_module = "documenti_fascicolo"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs: list[GlobalSearchDocument] = []
        for fascicolo in _manager_items(context.get("fascicoli"), "tutti", archiviati=True):
            fasc = as_dict(fascicolo)
            fasc_id = _first(fasc, "id")
            for item in self._document_items(fasc):
                data = as_dict(item)
                doc_id = _first(data, "id", "documento_uid", "id_documento", "id_cat", "nome", "nome_file")
                if not fasc_id or not doc_id:
                    continue
                name = _first(data, "nome", "nome_file", "titolo")
                tipo_atto = _first(data, "tipo_atto", "tipo", "classificazione", "categoria")
                metadata = {
                    "tipo_atto": tipo_atto,
                    "date": italian_date(_first(data, "data_documento", "data_deposito", "created_at")),
                    "firmato": bool(data.get("firmato") or str(name).lower().endswith(".p7m")),
                    "ufficiale": bool(data.get("fonte_documento") or data.get("origine_portale")),
                    "badges": ["Documento", tipo_atto] if tipo_atto else ["Documento"],
                }
                docs.append(
                    self._doc(
                        context,
                        entity_id=f"{fasc_id}:{doc_id}",
                        title=name or "Documento fascicolo",
                        subtitle=_join("Fascicolo", _first(fasc, "numero_rg", "numero"), tipo_atto),
                        body=_join(
                            _first(data, "note", "descrizione", "testo_ocr", "ocr_text"),
                            _first(data, "depositante", "autore"),
                            _first(data, "tags"),
                            _first(fasc, "nome_cliente", "controparte", "oggetto"),
                        ),
                        keywords=_join(doc_id, _first(data, "hash_sha256"), _first(data, "id_deposito")),
                        metadata=metadata,
                        source_url=f"/fascicoli/{fasc_id}?sezione=documenti-fascicolo",
                        client_id=_first(fasc, "id_cliente", "cliente_id"),
                        fascicolo_id=fasc_id,
                        pratica_id=_first(fasc, "id_pratica", "numero"),
                    )
                )
        return docs

    @staticmethod
    def _document_items(fasc: dict[str, Any]) -> Iterable[Any]:
        for key in ("documenti", "documenti_fascicolo", "allegati"):
            items = fasc.get(key) or []
            if isinstance(items, list):
                yield from items


class ClientiSearchAdapter(BaseSearchAdapter):
    entity_type = "cliente"
    source_module = "clienti"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("clienti"), "tutti"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if not entity_id:
                continue
            title = _first(data, "nome_completo") or _join(_first(data, "cognome"), _first(data, "nome")) or _first(data, "ragione_sociale")
            metadata = {
                "stato": _first(data, "stato"),
                "codice_fiscale": _first(data, "codice_fiscale"),
                "partita_iva": _first(data, "partita_iva"),
                "email": _first(data, "email"),
                "telefono": _first(data, "telefono"),
            }
            docs.append(
                self._doc(
                    context,
                    entity_id=entity_id,
                    title=title or "Cliente",
                    subtitle=_join(_first(data, "tipo"), _first(data, "stato")),
                    body=_join(
                        _first(data, "codice_fiscale"),
                        _first(data, "partita_iva"),
                        _first(data, "email"),
                        _first(data, "telefono"),
                        _first(data, "note"),
                    ),
                    keywords=_join(_first(data, "codice_fiscale"), _first(data, "partita_iva")),
                    metadata=metadata,
                    source_url=f"/clienti/{entity_id}",
                    client_id=entity_id,
                )
            )
        return docs


class SoggettiSearchAdapter(ClientiSearchAdapter):
    entity_type = "soggetto"
    source_module = "soggetti"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("soggetti"), "tutti"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if not entity_id:
                continue
            title = _join(_first(data, "cognome"), _first(data, "nome")) or _first(data, "denominazione", "ragione_sociale")
            docs.append(
                self._doc(
                    context,
                    entity_id=entity_id,
                    title=title or "Soggetto",
                    subtitle=_join(_first(data, "tipo"), _first(data, "ruolo")),
                    body=_join(_first(data, "codice_fiscale"), _first(data, "partita_iva"), _first(data, "email"), _first(data, "telefono")),
                    keywords=_join(_first(data, "codice_fiscale"), _first(data, "partita_iva")),
                    metadata={"codice_fiscale": _first(data, "codice_fiscale"), "partita_iva": _first(data, "partita_iva")},
                    source_url=f"/soggetti?focus={entity_id}",
                )
            )
        return docs


class ScadenzeSearchAdapter(BaseSearchAdapter):
    entity_type = "scadenza"
    source_module = "scadenziario"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("scadenziario"), "tutte", solo_aperte=False):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if not entity_id:
                continue
            date_value = _first(data, "data_scadenza", "data", "termine")
            docs.append(
                self._doc(
                    context,
                    entity_id=entity_id,
                    title=_first(data, "titolo") or "Scadenza",
                    subtitle=_join("Scadenza", italian_date(date_value), _first(data, "priorita")),
                    body=_join(_first(data, "descrizione"), _first(data, "note"), _first(data, "tipo")),
                    metadata={"date": italian_date(date_value), "data_scadenza": date_value, "stato": _first(data, "stato")},
                    source_url="/scadenziario",
                    fascicolo_id=_first(data, "id_fascicolo", "fascicolo_id"),
                    client_id=_first(data, "id_cliente", "cliente_id"),
                )
            )
        return docs


class AgendaSearchAdapter(BaseSearchAdapter):
    entity_type = "appuntamento"
    source_module = "agenda"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("agenda"), "tutti"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if not entity_id:
                continue
            date_value = _first(data, "data_ora", "inizio", "data")
            entity_type = "udienza" if "udienza" in _join(_first(data, "tipo"), _first(data, "titolo")).lower() else "appuntamento"
            docs.append(
                self._doc(
                    context,
                    entity_id=entity_id,
                    title=_first(data, "titolo") or "Appuntamento",
                    subtitle=_join(italian_date(date_value), _first(data, "luogo")),
                    body=_join(_first(data, "descrizione"), _first(data, "partecipanti"), _first(data, "note")),
                    metadata={"date": italian_date(date_value), "stato": _first(data, "stato")},
                    source_url=f"/agenda/appuntamento/{entity_id}",
                    fascicolo_id=_first(data, "id_fascicolo", "fascicolo_id"),
                    client_id=_first(data, "id_cliente", "cliente_id"),
                    entity_type=entity_type,
                )
            )
        return docs


class PreventiviSearchAdapter(BaseSearchAdapter):
    entity_type = "preventivo"
    source_module = "preventivi"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        manager = context.get("preventivi")
        docs = []
        for item in _manager_items(manager, "tutti_preventivi"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if entity_id:
                docs.append(
                    self._doc(
                        context,
                        entity_id=entity_id,
                        title=_first(data, "titolo", "oggetto") or f"Preventivo {entity_id}",
                        subtitle=_join(_first(data, "stato"), _first(data, "tipo_compenso")),
                        body=_join(_first(data, "cliente_nome", "nome_cliente"), _first(data, "note"), _first(data, "log_calcolo")),
                        metadata={"stato": _first(data, "stato"), "date": italian_date(_first(data, "data_emissione", "created_at"))},
                        source_url=f"/preventivi/{entity_id}",
                        client_id=_first(data, "id_cliente", "cliente_id"),
                        fascicolo_id=_first(data, "id_fascicolo", "fascicolo_id"),
                    )
                )
        for item in _manager_items(manager, "tutti_conferimenti"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if entity_id:
                docs.append(
                    self._doc(
                        context,
                        entity_id=entity_id,
                        title=_first(data, "oggetto", "titolo") or f"Conferimento {entity_id}",
                        subtitle="Conferimento incarico",
                        body=_join(_first(data, "cliente_nome", "nome_cliente"), _first(data, "note"), _first(data, "tipo_compenso")),
                        metadata={"date": italian_date(_first(data, "data_accettazione", "created_at"))},
                        source_url=f"/preventivi/conferimenti/{entity_id}",
                        client_id=_first(data, "id_cliente", "cliente_id"),
                        fascicolo_id=_first(data, "id_fascicolo", "fascicolo_id"),
                        entity_type="conferimento",
                    )
                )
        return docs


class FattureSearchAdapter(BaseSearchAdapter):
    entity_type = "fattura"
    source_module = "fatturazione"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("fatturazione"), "tutte"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if not entity_id:
                continue
            numero = _first(data, "numero")
            docs.append(
                self._doc(
                    context,
                    entity_id=entity_id,
                    title=f"Parcella {numero or entity_id}",
                    subtitle=_join(_first(data, "stato"), _first(data, "totale")),
                    body=_join(_first(data, "note"), _first(data, "tipo_compenso"), _first(data, "id_preventivo")),
                    keywords=numero,
                    metadata={"numero_fattura": numero, "stato": _first(data, "stato"), "date": italian_date(_first(data, "data_emissione"))},
                    source_url=f"/fatturazione/{entity_id}",
                    client_id=_first(data, "id_cliente"),
                    fascicolo_id=_first(data, "id_fascicolo"),
                )
            )
        return docs


class PagamentiSearchAdapter(BaseSearchAdapter):
    entity_type = "pagamento"
    source_module = "pagamenti"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for item in _manager_items(context.get("pagamenti"), "tutti_link"):
            data = as_dict(item)
            entity_id = _first(data, "id")
            if entity_id:
                docs.append(
                    self._doc(
                        context,
                        entity_id=entity_id,
                        title=_first(data, "descrizione") or f"Pagamento {entity_id}",
                        subtitle=_join(_first(data, "stato"), _first(data, "importo")),
                        body=_join(_first(data, "provider_usato"), _first(data, "provider_tx_id"), _first(data, "note")),
                        metadata={"stato": _first(data, "stato"), "date": italian_date(_first(data, "creato_il", "pagato_il"))},
                        source_url="/pagamenti",
                        client_id=_first(data, "id_cliente"),
                    )
                )
        return docs


class ComunicazioniSearchAdapter(BaseSearchAdapter):
    entity_type = "comunicazione"
    source_module = "comunicazioni"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        manager = context.get("messaggi") or context.get("comunicazioni")
        docs = []
        for item in _manager_items(manager, "tutti"):
            data = as_dict(item)
            entity_id = _first(data, "id", "message_id")
            if entity_id:
                docs.append(
                    self._doc(
                        context,
                        entity_id=entity_id,
                        title=_first(data, "oggetto", "subject", "titolo") or "Comunicazione",
                        subtitle=_join(_first(data, "mittente", "from"), _first(data, "canale", "tipo")),
                        body=_join(_first(data, "corpo", "body", "testo"), _first(data, "destinatario", "to"), _first(data, "note")),
                        metadata={
                            "date": italian_date(_first(data, "data", "created_at", "ricevuto_il")),
                            "non_letto": bool(data.get("non_letto") or data.get("unread")),
                        },
                        source_url=f"/messaggi?focus={entity_id}",
                        client_id=_first(data, "id_cliente", "cliente_id"),
                        fascicolo_id=_first(data, "id_fascicolo", "fascicolo_id"),
                    )
                )
        return docs


class TemplateAttiSearchAdapter(BaseSearchAdapter):
    entity_type = "template_atto"
    source_module = "template_atti"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        try:
            models = elenco_modelli()
        except Exception:
            models = []
        for item in models:
            data = as_dict(item)
            code = _first(data, "id", "codice", "code")
            if not code:
                continue
            docs.append(
                self._doc(
                    context,
                    entity_id=code,
                    title=_first(data, "nome", "titolo") or code,
                    subtitle=_join(_first(data, "categoria"), _first(data, "area")),
                    body=_join(_first(data, "descrizione"), _first(data, "tags")),
                    keywords=code,
                    metadata={"stato": "pronto"},
                    source_url=f"/template-atti/compila/{code}",
                )
            )
        return docs


class DepositiSearchAdapter(BaseSearchAdapter):
    entity_type = "deposito"
    source_module = "telematico"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        docs = []
        for fascicolo in _manager_items(context.get("fascicoli"), "tutti", archiviati=True):
            fasc = as_dict(fascicolo)
            fasc_id = _first(fasc, "id")
            for key in ("depositi", "esiti_deposito", "depositi_telematici"):
                for item in fasc.get(key) or []:
                    data = as_dict(item)
                    entity_id = _first(data, "id", "id_deposito", "identificativo")
                    if not entity_id:
                        continue
                    docs.append(
                        self._doc(
                            context,
                            entity_id=f"{fasc_id}:{entity_id}",
                            title=_first(data, "tipo_atto", "titolo") or f"Deposito {entity_id}",
                            subtitle=_join(_first(data, "stato"), italian_date(_first(data, "data_deposito", "created_at"))),
                            body=_join(_first(data, "esito", "note", "messaggio"), _first(fasc, "numero_rg", "oggetto")),
                            metadata={"stato": _first(data, "stato"), "date": italian_date(_first(data, "data_deposito", "created_at"))},
                            source_url=f"/fascicoli/{fasc_id}?sezione=depositi",
                            fascicolo_id=fasc_id,
                            client_id=_first(fasc, "id_cliente", "cliente_id"),
                        )
                    )
        return docs


class LegalIntelligenceSearchAdapter(BaseSearchAdapter):
    entity_type = "legal_intelligence"
    source_module = "legal_intelligence"

    def collect(self, context: dict[str, Any]) -> list[GlobalSearchDocument]:
        manager = context.get("legal_intelligence")
        docs = []
        for method_name in ("tutti", "lista", "all"):
            items = _manager_items(manager, method_name)
            if not items:
                continue
            for item in items:
                data = as_dict(item)
                entity_id = _first(data, "id", "codice")
                if entity_id:
                    docs.append(
                        self._doc(
                            context,
                            entity_id=entity_id,
                            title=_first(data, "titolo", "nome") or "Intelligence interna",
                            subtitle=_first(data, "materia", "fonte"),
                            body=_join(_first(data, "testo", "descrizione", "note")),
                            source_url="/legal-intelligence",
                        )
                    )
            break
        return docs


def default_adapters() -> list[BaseSearchAdapter]:
    return [
        FascicoliSearchAdapter(),
        ClientiSearchAdapter(),
        SoggettiSearchAdapter(),
        ScadenzeSearchAdapter(),
        AgendaSearchAdapter(),
        DocumentiSearchAdapter(),
        PreventiviSearchAdapter(),
        FattureSearchAdapter(),
        PagamentiSearchAdapter(),
        ComunicazioniSearchAdapter(),
        TemplateAttiSearchAdapter(),
        DepositiSearchAdapter(),
        LegalIntelligenceSearchAdapter(),
    ]
