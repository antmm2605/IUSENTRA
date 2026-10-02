"""Gli stessi nomi professionali già usati dalla lista documenti del fascicolo."""
from collections import Counter


def nomi_documenti(fascicolo) -> dict[str, str]:
    from web.services.react_fascicoli_bridge import _document_name_with_signature_suffix, _professional_document_name

    counters = Counter()
    result = {}
    for doc in getattr(fascicolo, "documenti", []) or []:
        name = _professional_document_name(doc, counters)
        result[str(doc.id)] = _document_name_with_signature_suffix(
            doc, name, doc.nome, doc.nome_originale, getattr(doc, "nome_portale", ""), doc.percorso,
        )
    return result
