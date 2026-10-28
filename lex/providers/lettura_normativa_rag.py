"""Lettura integrale per parti quando le norme RAG superano il contesto.

Riusa il lettore della stesura e il provider già selezionato. Le viste di prompt
sono passaggi letterali, mai presentati come nuovo testo integrale archiviato.
"""
from __future__ import annotations

from types import SimpleNamespace
from dataclasses import asdict, is_dataclass
import hashlib

from lex.procedura_atti.lettura_fonti import prepara_letture
from lex.providers.prompt_budget import (
    CHARS_PER_TOKEN, _norma_integrale, _testo, build_rag_prompt, evidence_items, format_evidence_item,
)


def completa_lettura_normativa(*, piano, system_prompt, question, evidence,
                               workflow, context, settings, chiama_modello):
    items=evidence_items(evidence)[:max(settings.max_evidence_items,0)]
    omitted=set(piano.metadata.get("evidenze_escluse_budget") or [])
    normative={n:item for n,item in enumerate(items,1) if _norma_integrale(item)}
    if not any(n in omitted for n in normative):
        return piano,[]
    full={n:_testo(item) for n,item in normative.items()}
    # La formattazione verifica prima le impronte dei testi integrali.
    blocks=[format_evidence_item(n,item,max_chars=settings.evidence_max_chars)[0]
            for n,item in enumerate(items,1)]
    message=system_prompt+"\nDomanda:\n"+question+"\nFonti:\n"+"\n\n".join(blocks)
    view,trace=prepara_letture(SimpleNamespace(fonti=full),richiesta=question,
        chiama_modello=chiama_modello,messaggio_caratteri=len(message),
        budget_caratteri=max(1000,int(settings.input_budget_tokens*CHARS_PER_TOKEN)),forza_parti=True)
    updated=list(items)
    for n,item in normative.items():
        if not isinstance(item,dict) and not is_dataclass(item):
            raise ValueError("Norma integrale senza contratto di evidenza strutturato")
        clone=dict(item) if isinstance(item,dict) else asdict(item)
        # Le fonti originali restano nelle evidenze della pipeline. Questa è
        # soltanto una vista del prompt dopo la ricezione di tutte le parti.
        clone.update(source_type="normativa_letta_per_parti",normative_full_text=None,
                     normative_full_text_sha256=None,content=view.fonti[n],excerpt=view.fonti[n],
                     testo=view.fonti[n],text=view.fonti[n])
        clone["normative_read_view"]=view.fonti[n]
        clone["normative_read_view_sha256"]=hashlib.sha256(view.fonti[n].encode()).hexdigest()
        updated[n-1]=clone
    result=build_rag_prompt(system_prompt=system_prompt,question=question,
        evidence={"items":updated},workflow=workflow,context=context,settings=settings)
    final_omitted=set(result.metadata.get("evidenze_escluse_budget") or [])
    if any(n in final_omitted for n in normative) or result.metadata.get("budget_superato"):
        raise ValueError("Letture completate ma vista finale fuori contesto: nessuna risposta parziale attestata")
    return result,trace
