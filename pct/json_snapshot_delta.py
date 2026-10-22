"""Applica la variazione del modello senza cancellare metadati non modificati.

Il chiamante deve già avere verificato che lo snapshot sorgente sia ancora
quello persistito. Non è una fusione tra modifiche concorrenti né un resolver
di identità: gli elementi di una lista si seguono soltanto tramite ID univoci.
"""
from __future__ import annotations


def merge_delta(source, before, after):
    if before == after:
        return source
    if isinstance(source, dict) and isinstance(before, dict) and isinstance(after, dict):
        merged = dict(source)
        for key in before.keys() - after.keys():
            merged.pop(key, None)
        for key, value in after.items():
            if key not in before:
                merged[key] = value
            elif before[key] != value:
                merged[key] = merge_delta(source.get(key), before[key], value)
        return merged
    if all(isinstance(value, list) for value in (source, before, after)):
        def indexed(values):
            if any(not isinstance(value, dict) or not value.get('id') for value in values):
                return None
            mapping = {value['id']: value for value in values}
            return mapping if len(mapping) == len(values) else None
        old, original, new = indexed(before), indexed(source), indexed(after)
        if old is not None and original is not None and new is not None:
            return [merge_delta(original.get(value['id']), old[value['id']], value)
                    if value['id'] in old else value for value in after]
    return after
