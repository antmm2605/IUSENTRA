"""Rettifiche puntuali dei modelli nativi con riscontro integrale del precedente."""
from pct.guida_pratica.term_revisions import CAUTION_SOURCE, REVISION
from pct.termini_processuali import DEFAULT_TEMPLATES, DeadlineTemplate


def rectify_native_caution(repository):
    code = "CIV_RECLAMO_CAUTELARE_669_TERDECIES"
    previous = DeadlineTemplate(code=code, name="Reclamo cautelare", base_value=15,
                                reference_law="Art. 669-terdecies c.p.c.",
                                metadata={"source_event": "pronuncia_udienza"}).to_dict()
    current = next(template.to_dict() for template in DEFAULT_TEMPLATES if template.code == code)
    try:
        actual = repository.get_template_payload(code)
    except ValueError as exc:
        if str(exc) != "Template termine non trovato":
            raise
        return {"requires_review": True, "revision": REVISION,
                "reason": "Modello cautelare assente dall’archivio adottato: nessuna regola inserita implicitamente."}
    if actual == current:
        return {"already_current": True, "revision": REVISION}
    if actual != previous:
        return {"requires_review": True, "revision": REVISION,
                "reason": "Modello personalizzato o diverso dalla versione ufficiale precedente."}
    return repository.revise_template(
        code, expected=previous, replacement=current, revision=REVISION,
        reason="Esclusione feriale del procedimento cautelare e decorrenze dell'art. 669-terdecies.",
        source=CAUTION_SOURCE,
    )
