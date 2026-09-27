"""Checklist degli atti e percorso guidato di raccolta documenti per la shell React.

Sostituisce le viste storiche `/checklist`, `/checklist/<id>` e il percorso
`/fascicoli/<id>/wizard/<modello>/step/<n>` e `/completa`. Il catalogo è lo
stesso (`pct/checklist_atti.py`): per ogni atto i documenti da allegare, i
controlli (quelli critici bloccano il deposito) e il canale.

Il percorso guidato raccoglie i documenti nel fascicolo con la stessa via dei
caricamenti dello studio (`/fascicoli/<id>/documenti/carica`: registro delle
letture, ricevute pagoPA, indice di Lex); qui si calcola solo lo stato dei
passi. Il deposito si prepara nella pagina React del deposito
(`/fascicoli/<id>/deposito/prepara`): il percorso non ne duplica i controlli.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from pct import checklist_atti as catalogo_atti

CHIAVE_SALTATI = "wiz_skip_{fascicolo}_{modello}"


def _t(value: Any) -> str:
    return "" if value is None else str(getattr(value, "value", value)).strip()


def etichetta_categoria(categoria: str) -> str:
    return catalogo_atti.CATEGORIE.get(categoria, categoria)


def _canale(template: Any) -> dict[str, str]:
    codice = _t(getattr(template, "canale", ""))
    return {"code": codice, "label": catalogo_atti.CANALE_LABEL.get(codice, codice), "note": _t(getattr(template, "nota_canale", ""))}


def _riassunto(template: Any) -> dict[str, Any]:
    return {
        "id": template.id,
        "name": template.nome,
        "category": etichetta_categoria(template.categoria),
        "area": template.area,
        "branch": template.branca,
        "subbranch": template.sottobranca,
        "description": template.descrizione,
        "channel": _canale(template),
        "requiredDocuments": catalogo_atti.conta_documenti_obbligatori(template),
        "criticalChecks": catalogo_atti.conta_item_critici(template),
        "href": f"/checklist/{template.id}",
    }


def catalogo(*, area: str = "", q: str = "") -> dict[str, Any]:
    aree = catalogo_atti.costruisci_catalogo_checklist(area=area, q=q)
    completo = catalogo_atti.costruisci_catalogo_checklist()
    copertura = catalogo_atti.statistiche_copertura_template_atti()
    return {
        "ok": True,
        "filters": {"area": area, "q": q},
        "areas": [{"name": a["nome"], "count": a["template_count"]} for a in completo],
        "totals": {
            "templates": sum(a["template_count"] for a in aree),
            "areas": len(aree),
            "requiredDocuments": sum(a["documenti_obbligatori"] for a in aree),
            "criticalChecks": sum(a["critici_count"] for a in aree),
            "catalogTemplates": len(catalogo_atti.TUTTI_I_TEMPLATE),
        },
        "coverage": {k: int(v or 0) for k, v in (copertura or {}).items() if isinstance(v, (int, float))},
        "catalog": [
            {
                "name": a["nome"],
                "templates": a["template_count"],
                "requiredDocuments": a["documenti_obbligatori"],
                "criticalChecks": a["critici_count"],
                "branches": [
                    {
                        "name": b["nome"],
                        "subbranches": [
                            {"name": s["nome"], "templates": [_riassunto(t) for t in s["templates"]]}
                            for s in b["sottobranche"]
                        ],
                    }
                    for b in a["branche"]
                ],
            }
            for a in aree
        ],
    }


def _documenti(template: Any) -> list[dict[str, Any]]:
    return [
        {"number": d.numero, "fileName": d.nome_file, "description": d.descrizione, "required": bool(d.obbligatorio), "note": _t(d.note)}
        for d in template.documenti
    ]


def scheda(id_modello: str, *, fascicolo: Any = None, parte: str = "", rg: str = "", data: str = "") -> tuple[dict[str, Any], int]:
    template = catalogo_atti.get_template(id_modello)
    if not template:
        return {"ok": False, "message": "Modello di checklist non trovato."}, 404
    parte = parte or (_t(getattr(fascicolo, "controparte", "")) if fascicolo is not None else "")
    rg = rg or (_t(getattr(fascicolo, "numero_rg", "")) if fascicolo is not None else "")
    data = data or date.today().isoformat()
    return {
        "ok": True,
        "item": {
            **_riassunto(template),
            "folderName": catalogo_atti.nome_cartella_compilato(template, parte=parte, rg=rg, data=data),
            "folderPattern": template.nome_cartella,
            "context": {"party": parte, "rg": rg, "date": data},
            "documents": _documenti(template),
            "checks": [{"text": c.testo, "critical": bool(c.critico), "note": _t(c.note)} for c in template.checklist],
            "generalNotes": _t(template.note_generali),
            "matter": {
                "id": _t(getattr(fascicolo, "id", "")),
                "title": _t(getattr(fascicolo, "titolo", "")),
                "wizardHref": f"/fascicoli/{_t(getattr(fascicolo, 'id', ''))}/wizard/{template.id}",
            } if fascicolo is not None else None,
        },
    }, 200


def _tag_passo(id_modello: str, numero: int) -> str:
    return f"[wizard:{id_modello}:step{numero}]"


def documento_del_passo(fascicolo: Any, richiesto: Any, id_modello: str) -> Any:
    """Il documento del fascicolo che soddisfa il passo: marcato dal percorso o con il nome previsto."""
    tag = _tag_passo(id_modello, richiesto.numero)
    prefisso = _t(richiesto.nome_file).lower()
    for documento in getattr(fascicolo, "documenti", []) or []:
        if tag in (_t(getattr(documento, "note", ""))):
            return documento
        if prefisso and _t(getattr(documento, "nome", "")).lower().startswith(prefisso):
            return documento
    return None


def _stato_passi(fascicolo: Any, template: Any, saltati: Iterable[int]) -> list[dict[str, Any]]:
    saltati = {int(n) for n in saltati}
    passi = []
    for richiesto in template.documenti:
        documento = documento_del_passo(fascicolo, richiesto, template.id)
        stato = "done" if documento is not None else ("skipped" if not richiesto.obbligatorio and richiesto.numero in saltati else "pending")
        passi.append(
            {
                "number": richiesto.numero,
                "fileName": richiesto.nome_file,
                "description": richiesto.descrizione,
                "required": bool(richiesto.obbligatorio),
                "note": _t(richiesto.note),
                "status": stato,
                "uploadName": richiesto.nome_file,
                "uploadNote": _tag_passo(template.id, richiesto.numero),
                "document": {
                    "id": _t(getattr(documento, "id", "")),
                    "name": _t(getattr(documento, "nome", "")),
                    "date": _t(getattr(documento, "data_documento", "")),
                    "viewHref": f"/fascicoli/{fascicolo.id}/documenti/{_t(getattr(documento, 'id', ''))}/visualizza",
                    "downloadHref": f"/fascicoli/{fascicolo.id}/documenti/{_t(getattr(documento, 'id', ''))}/scarica",
                } if documento is not None else None,
            }
        )
    return passi


def _tipi_documento() -> list[dict[str, str]]:
    from pct.fascicoli import TipoDocumento

    return [{"value": tipo.value, "label": tipo.value.replace("_", " ").capitalize()} for tipo in TipoDocumento]


def percorso(fascicolo: Any, id_modello: str, saltati: Iterable[int]) -> tuple[dict[str, Any], int]:
    template = catalogo_atti.get_template(id_modello)
    if fascicolo is None:
        return {"ok": False, "message": "Fascicolo non trovato."}, 404
    if not template:
        return {"ok": False, "message": "Modello di checklist non trovato."}, 404
    passi = _stato_passi(fascicolo, template, saltati)
    mancanti = [p for p in passi if p["required"] and p["status"] == "pending"]
    return {
        "ok": True,
        "matter": {
            "id": fascicolo.id,
            "title": _t(getattr(fascicolo, "titolo", "")),
            "rg": _t(getattr(fascicolo, "rg_completo", "")) or _t(getattr(fascicolo, "numero_rg", "")),
            "client": _t(getattr(fascicolo, "nome_cliente", "")),
            "counterpart": _t(getattr(fascicolo, "controparte", "")),
            "office": _t(getattr(fascicolo, "tribunale", "")),
            "href": f"/fascicoli/{fascicolo.id}",
            "uploadAction": f"/fascicoli/{fascicolo.id}/documenti/carica",
            "depositHref": f"/fascicoli/{fascicolo.id}/deposito/prepara",
        },
        "template": {**_riassunto(template), "checks": [{"text": c.testo, "critical": bool(c.critico), "note": _t(c.note)} for c in template.checklist]},
        "folderName": catalogo_atti.nome_cartella_compilato(template, _t(getattr(fascicolo, "controparte", "")), _t(getattr(fascicolo, "numero_rg", ""))),
        "steps": passi,
        "nextStep": mancanti[0]["number"] if mancanti else None,
        "complete": not mancanti,
        "missingRequired": len(mancanti),
        "documentTypes": _tipi_documento(),
        "skipAction": f"/api/v1/ui/checklist/percorso/{fascicolo.id}/{template.id}/salta",
        "indexAction": f"/api/v1/ui/checklist/percorso/{fascicolo.id}/{template.id}/indice",
    }, 200


def testo_indice(fascicolo: Any, template: Any, saltati: Iterable[int], *, adesso: datetime | None = None) -> str:
    """L'indice dei documenti raccolti (testo semplice, con l'impronta SHA-256 di ciascuno)."""
    saltati = {int(n) for n in saltati}
    righe = []
    for richiesto in template.documenti:
        documento = documento_del_passo(fascicolo, richiesto, template.id)
        if documento is not None:
            righe.append(
                f"  {richiesto.numero:02d}. {documento.nome}\n"
                f"      {richiesto.descrizione}"
                f" | {_t(getattr(documento, 'data_documento', '')) or 'data n.d.'}"
                f" | sha256: {_t(getattr(documento, 'hash_sha256', ''))[:16]}..."
            )
        elif not richiesto.obbligatorio and richiesto.numero in saltati:
            righe.append(f"  {richiesto.numero:02d}. [non allegato] {richiesto.nome_file} ({richiesto.descrizione} - facoltativo)")
        else:
            righe.append(f"  {richiesto.numero:02d}. [MANCANTE] {richiesto.nome_file} ({richiesto.descrizione})")
    separatore = "=" * 64
    quando = (adesso or datetime.now()).strftime("%d/%m/%Y %H:%M")
    return "\n".join(
        [
            separatore,
            f"  INDICE DOCUMENTI - {template.nome.upper()}",
            separatore,
            f"  Fascicolo  : {_t(getattr(fascicolo, 'titolo', ''))}",
            f"  RG         : {_t(getattr(fascicolo, 'rg_completo', '')) or 'n.d.'}",
            f"  Cliente    : {_t(getattr(fascicolo, 'nome_cliente', ''))}",
            f"  Controparte: {_t(getattr(fascicolo, 'controparte', ''))}",
            f"  Tribunale  : {_t(getattr(fascicolo, 'tribunale', '')) or 'n.d.'}",
            f"  Cartella   : {catalogo_atti.nome_cartella_compilato(template, _t(getattr(fascicolo, 'controparte', '')), _t(getattr(fascicolo, 'numero_rg', '')))}",
            f"  Generato il: {quando}",
            separatore,
            "",
            *righe,
            "",
            separatore,
        ]
    )


__all__ = ["CHIAVE_SALTATI", "catalogo", "documento_del_passo", "percorso", "scheda", "testo_indice"]
