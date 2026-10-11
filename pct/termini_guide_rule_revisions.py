"""Rettifiche delle associazioni guida dei modelli importati, soltanto su versioni note."""
import json
from pathlib import Path

from pct.guida_pratica.term_revisions import REVISION, SOURCE, CAUTION_SOURCE, family_term, caution_term


def legacy_rules():
    return json.loads((Path(__file__).parent / "data/termini/legacy-reclami-20261011.json").read_text(encoding="utf-8"))


def revised_rule(previous):
    result = {**previous, "metadata": dict(previous["metadata"]), "version": previous["version"] + 1,
              "matter_type": "civil"}
    metadata = result["metadata"]
    metadata["rule_revision"] = REVISION
    if previous["code"] in {"GP_9B6E3BC346B9", "GP_0BD0BDFBBF7F"}:
        metadata["codice_guida"] = ""
        metadata["previous_codice_guida"] = "411003"
        metadata["association_revision_reason"] = "Termine generale estraneo al reclamo ex art. 473-bis.24: conservato senza associazione a questa guida."
        metadata["verified_source"] = SOURCE
    else:
        term = family_term() if metadata["codice_guida"] == "411003" else caution_term()
        result.update(name=term["termine"], base_value=term["giorni"], matter_type="civil",
                      reference_law=term["norma"], suspend_august=False,
                      ferial_suspension_policy=term["ferial_suspension_policy"])
        metadata.update(decorrenza=term["decorrenza"], natura=term["natura"], criticita=term["criticita"],
                        source_event_options=term["source_event_options"], verified_source=term["fonte_verifica"])
    return result


def rectify_imported_reclami(repository):
    results = []
    for known in legacy_rules():
        code = known["code"]
        try:
            actual = repository.get_template_payload(code)
        except ValueError as exc:
            if str(exc) != "Template termine non trovato":
                raise
            results.append({"code": code, "absent": True})
            continue
        source_file = actual.get("metadata", {}).get("source_file", "")
        normalized = str(source_file).replace("\\", "/")
        if not normalized.endswith("pct/data/legal_knowledge_base.full.json"):
            results.append({"code": code, "requires_review": True, "reason": "Provenienza diversa dalla versione nota."})
            continue
        previous = {**known, "metadata": {**known["metadata"], "source_file": source_file}}
        replacement = revised_rule(previous)
        if actual == replacement:
            results.append({"code": code, "already_current": True})
        elif actual != previous:
            results.append({"code": code, "requires_review": True, "reason": "Modello personalizzato o modificato: preservato."})
        else:
            results.append({"code": code, **repository.revise_template(
                code, expected=previous, replacement=replacement, revision=REVISION,
                reason="Rettifica del termine specifico o dell’associazione al reclamo, senza modificare calcoli storici.",
                source=CAUTION_SOURCE if known["metadata"]["codice_guida"] == "014100" else SOURCE)})
    return results
