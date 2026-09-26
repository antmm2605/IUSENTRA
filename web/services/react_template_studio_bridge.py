"""Modelli di studio (template atti scritti dallo studio) per la shell React.

Scheda, creazione, modifica e compilazione dei modelli dello studio, con le
stesse regole della vista storica: i modelli integrati non si modificano (si
clonano), i campi guidati si precompilano da cliente, fascicolo e parti, e il
testo si genera con il motore dei template (`pct.template_atti`). Il PDF resta
la route esistente `POST /template-atti/<id>/pdf`.

Le funzioni girano dentro una richiesta Flask: usano gli stessi accessi ai dati
e le stesse funzioni di supporto del blueprint `template_atti`.
"""

from __future__ import annotations

from typing import Any, Mapping


# Variabili inseribili nel testo di un modello (stesso elenco della vista storica).
GRUPPI_VARIABILI: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Studio", ("studio_nome", "studio_indirizzo", "studio_iban", "avvocato_nome", "data_oggi")),
    ("Cliente", ("cliente.nome_completo", "cliente.codice_fiscale", "cliente.data_nascita", "cliente.luogo_nascita", "cliente.indirizzo", "cliente.tipo.value")),
    ("Fascicolo", ("fascicolo.titolo", "fascicolo.numero_rg", "fascicolo.tribunale", "fascicolo.tipo.value")),
    ("Soggetti / Parti", (
        "parti.assistito_principale.nome_completo",
        "parti.assistito_principale.identificativo",
        "parti.controparte_principale.nome_completo",
        "parti.controparte_principale.identificativo",
        "parti.difensore_controparte_principale.nome_completo",
        "parti.difensore_controparte_principale.pec",
    )),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bp():
    from web.blueprints import template_atti as bp

    return bp


def _campo(field: Mapping[str, Any]) -> dict[str, Any]:
    tipo = _text(field.get("type")) or "text"
    return {
        "name": _text(field.get("name")),
        "label": _text(field.get("label")) or _text(field.get("name")),
        "type": tipo if tipo in {"text", "textarea", "number", "date", "select", "email"} else "text",
        "placeholder": _text(field.get("placeholder")),
        "rows": int(field.get("rows") or (4 if tipo == "textarea" else 1)),
        "options": [
            {"value": _text(opt.get("value") if isinstance(opt, Mapping) else opt), "label": _text(opt.get("label") if isinstance(opt, Mapping) else opt)}
            for opt in list(field.get("options") or [])
        ],
        "required": bool(field.get("required")),
    }


def _sezioni(template: Any) -> list[dict[str, Any]]:
    bp = _bp()
    campi = list(getattr(template, "campi_guidati", []) or []) or bp._fallback_template_fields()
    return [
        {"title": _text(sezione.get("title")) or "Contenuto", "fields": [_campo(f) for f in sezione.get("fields", []) if _text(f.get("name"))]}
        for sezione in bp._group_template_fields(campi)
    ]


def _riepilogo(template: Any) -> dict[str, Any]:
    tid = _text(getattr(template, "id", ""))
    builtin = bool(getattr(template, "builtin", False))
    return {
        "id": tid,
        "title": _text(getattr(template, "titolo", "")),
        "category": _text(getattr(template, "categoria", "")),
        "area": _text(getattr(template, "area", "")),
        "branch": _text(getattr(template, "branca", "")),
        "notes": _text(getattr(template, "note", "")),
        "builtin": builtin,
        "keywords": [_text(k) for k in list(getattr(template, "parole_chiave", []) or []) if _text(k)],
        "updatedAt": _text(getattr(template, "modificato_il", "") or getattr(template, "creato_il", "")),
        "useHref": f"/template-atti/{tid}/usa",
        "editHref": "" if builtin else f"/template-atti/{tid}/modifica",
        "detailHref": f"/template-atti/scheda/{tid}",
        "cloneAction": f"/api/v1/ui/template-atti/studio/{tid}/clona",
        "deleteAction": "" if builtin else f"/api/v1/ui/template-atti/studio/{tid}/elimina",
        "pdfAction": f"/template-atti/{tid}/pdf",
    }


def scheda_modello(id_template: str) -> tuple[dict[str, Any], int]:
    gt = _bp()._get_gt()
    template = gt.get(id_template)
    if not template:
        return {"ok": False, "message": "Modello non trovato.", "item": None}, 404
    correlati = []
    for candidato in gt.tutti():
        if candidato.id == template.id:
            continue
        stessa_branca = template.branca and candidato.branca == template.branca
        stessa_area = template.area and candidato.area == template.area
        if stessa_branca or stessa_area:
            correlati.append({"id": candidato.id, "title": candidato.titolo, "href": f"/template-atti/scheda/{candidato.id}"})
        if len(correlati) >= 8:
            break
    item = _riepilogo(template)
    item["sections"] = _sezioni(template)
    item["body"] = _text(getattr(template, "corpo", ""))
    item["related"] = correlati
    item["compilerCode"] = _text(getattr(template, "link_compilatore_code", ""))
    item["compilerHref"] = f"/template-atti/compila/{item['compilerCode']}" if item["compilerCode"] else ""
    return {"ok": True, "item": item}, 200


def modulo_modello(id_template: str = "") -> tuple[dict[str, Any], int]:
    from pct.template_atti import CATEGORIE

    valori = {"titolo": "", "categoria": CATEGORIE[0] if CATEGORIE else "Altro", "corpo": "", "note": ""}
    riepilogo: dict[str, Any] | None = None
    if id_template:
        template = _bp()._get_gt().get(id_template)
        if not template:
            return {"ok": False, "message": "Modello non trovato.", "item": None}, 404
        riepilogo = _riepilogo(template)
        valori = {
            "titolo": _text(template.titolo),
            "categoria": _text(template.categoria),
            "corpo": str(template.corpo or ""),
            "note": _text(template.note),
        }
    return {
        "ok": True,
        "categories": list(CATEGORIE),
        "values": valori,
        "item": riepilogo,
        "variableGroups": [{"title": titolo, "variables": list(variabili)} for titolo, variabili in GRUPPI_VARIABILI],
        "importAction": "/template-atti/api/importa-documento",
    }, 200


def salva_modello(payload: Mapping[str, Any], id_template: str = "") -> tuple[dict[str, Any], int]:
    from pct.template_atti import CATEGORIE

    ignoti = sorted(set(payload) - {"titolo", "categoria", "corpo", "note"})
    errori: dict[str, str] = {k: "Campo non accettato." for k in ignoti}
    titolo = _text(payload.get("titolo"))
    corpo = str(payload.get("corpo") or "").strip()
    categoria = _text(payload.get("categoria")) or "Altro"
    if not titolo:
        errori["titolo"] = "Il titolo è obbligatorio."
    if not corpo:
        errori["corpo"] = "Il testo del modello è obbligatorio."
    if categoria not in CATEGORIE and categoria != "Altro":
        errori["categoria"] = "Categoria non prevista."
    if errori:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errori}, 400
    gt = _bp()._get_gt()
    if id_template:
        template = gt.get(id_template)
        if not template:
            return {"ok": False, "message": "Modello non trovato.", "errors": {}}, 404
        if getattr(template, "builtin", False):
            return {
                "ok": False,
                "message": "I modelli integrati non si modificano: clonalo e modifica la copia.",
                "errors": {"builtin": "Modello integrato."},
            }, 400
        try:
            template = gt.aggiorna(id_template, titolo=titolo, categoria=categoria, corpo=corpo, note=_text(payload.get("note")))
        except ValueError:
            return {"ok": False, "message": "Modello non aggiornato: controlla i dati inseriti.", "errors": {}}, 400
        return {"ok": True, "message": "Modello aggiornato.", "item": _riepilogo(template), "errors": {}}, 200
    template = gt.crea(titolo=titolo, categoria=categoria, corpo=corpo, note=_text(payload.get("note")))
    return {"ok": True, "message": f"Modello «{template.titolo}» creato.", "item": _riepilogo(template), "errors": {}}, 201


def _cliente_label(cliente: Any) -> str:
    return _text(getattr(cliente, "nome_completo", "")) or _text(getattr(cliente, "ragione_sociale", "")) or _text(getattr(cliente, "id", ""))


def uso_modello(id_template: str, *, id_cliente: str = "", id_fascicolo: str = "") -> tuple[dict[str, Any], int]:
    from web.helpers import get_clienti, get_fascicoli

    bp = _bp()
    template = bp._get_gt().get(id_template)
    if not template:
        return {"ok": False, "message": "Modello non trovato.", "item": None}, 404
    gc = get_clienti()
    gf = get_fascicoli()
    cliente = gc.get(id_cliente) if id_cliente else None
    fascicolo = gf.get(id_fascicolo) if id_fascicolo else None
    if fascicolo and not cliente and getattr(fascicolo, "id_cliente", ""):
        cliente = gc.get(fascicolo.id_cliente)
    _soggetti, parti = bp._build_parti_template_context(id_fascicolo)
    valori = bp._prefill_template_fields(template, cliente=cliente, fascicolo=fascicolo, parti=parti)
    valori.pop("_prefill_resolution", None)
    id_cliente_scelto = _text(getattr(cliente, "id", "")) if cliente else ""
    fascicoli = [
        {"id": f.id, "label": " · ".join(x for x in (_text(getattr(f, "titolo", "")), _text(getattr(f, "numero_rg", ""))) if x) or f.id}
        for f in gf.tutti()
        if id_cliente_scelto and getattr(f, "id_cliente", "") == id_cliente_scelto
    ]
    clienti = sorted(({"id": c.id, "label": _cliente_label(c)} for c in gc.tutti()), key=lambda c: c["label"].lower())
    return {
        "ok": True,
        "item": _riepilogo(template),
        "sections": _sezioni(template),
        "values": {k: bp._valore_form(v) if hasattr(bp, "_valore_form") else _text(v) for k, v in valori.items()},
        "clients": clienti,
        "matters": fascicoli,
        "selectedClientId": id_cliente_scelto,
        "selectedMatterId": _text(getattr(fascicolo, "id", "")) if fascicolo else "",
    }, 200


_CAMPI_STORICI = {
    "destinatario_nome": "",
    "destinatario_indirizzo": "",
    "oggetto_diffida": "",
    "importo_dovuto": "",
    "titolo_credito": "",
    "termine_giorni": "15",
    "tribunale_competente": "",
    "durata_anni": "5",
}


def genera_testo(id_template: str, payload: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    from flask import current_app

    from web.helpers import get_clienti, get_fascicoli

    bp = _bp()
    gt = bp._get_gt()
    template = gt.get(id_template)
    if not template:
        return {"ok": False, "message": "Modello non trovato."}, 404
    campi_inviati = payload.get("fields") if isinstance(payload.get("fields"), Mapping) else {}
    id_cliente = _text(payload.get("clientId"))
    id_fascicolo = _text(payload.get("matterId"))
    cliente = get_clienti().get(id_cliente) if id_cliente else None
    fascicolo = get_fascicoli().get(id_fascicolo) if id_fascicolo else None
    variabili = bp._variabili_base(current_app.config)
    soggetti, parti = bp._build_parti_template_context(id_fascicolo)
    variabili.update({"cliente": cliente, "fascicolo": fascicolo, "soggetti": soggetti, "parti": parti})
    nomi = [f.get("name") for f in (list(getattr(template, "campi_guidati", []) or []) or bp._fallback_template_fields())]
    for nome in nomi:
        if nome:
            variabili[nome] = _text(campi_inviati.get(nome))
    for nome, predefinito in _CAMPI_STORICI.items():
        variabili.setdefault(nome, _text(campi_inviati.get(nome)) or predefinito)
    try:
        testo = gt.renderizza(id_template, variabili)
    except Exception as exc:
        return {"ok": False, "message": f"Generazione non riuscita: {exc}"}, 400
    return {
        "ok": True,
        "message": "Testo generato.",
        "text": testo,
        "html": bp._to_editor_html(testo),
        "pdfAction": f"/template-atti/{id_template}/pdf",
    }, 200


def clona_modello(id_template: str) -> tuple[dict[str, Any], int]:
    gt = _bp()._get_gt()
    template = gt.get(id_template)
    if not template:
        return {"ok": False, "message": "Modello non trovato."}, 404
    copia = gt.crea(titolo=f"[Copia] {template.titolo}", categoria=template.categoria, corpo=template.corpo, note=template.note)
    return {"ok": True, "message": f"Modello clonato: «{copia.titolo}».", "item": _riepilogo(copia), "redirect_href": f"/template-atti/{copia.id}/modifica"}, 201


def elimina_modello(id_template: str) -> tuple[dict[str, Any], int]:
    gt = _bp()._get_gt()
    template = gt.get(id_template)
    if not template:
        return {"ok": False, "message": "Modello non trovato."}, 404
    if getattr(template, "builtin", False):
        return {"ok": False, "message": "I modelli integrati non si eliminano."}, 400
    try:
        gt.elimina(id_template)
    except ValueError:
        return {"ok": False, "message": "Modello non eliminato: elemento non disponibile."}, 400
    return {"ok": True, "message": "Modello eliminato.", "redirect_href": "/template-atti"}, 200


__all__ = [
    "clona_modello",
    "elimina_modello","genera_testo", "modulo_modello", "salva_modello", "scheda_modello", "uso_modello"]
