"""Synthetic release smoke test through the running application's private gateway."""
import json
import time
from datetime import date
from pathlib import Path

from lex.gateway.service import LexGateway
from lex.procedura_atti.fonti_scheda import FontiScheda
from lex.procedura_atti.stesura_blocchi import scrivi_blocchi
from web.services.normative_article_reader import risolvi

CASES = [
    {"id":"credito", "blocco":"Fatto", "richiesta":"Alfa Fittizia ha emesso fattura di 1500 euro; Beta Fittizia ha pagato un acconto di 500 euro. Il residuo calcolato dal software è 1000 euro. Riporta i tre importi, senza aggiungere interessi o spese.", "required":["1500","500","1000"]},
    {"id":"dato_mancante", "blocco":"Fatto", "richiesta":"Alfa Fittizia ha consegnato merce a Beta Fittizia. La data di consegna non è nota. Riportala come [DATO MANCANTE: data di consegna], senza inventare date.", "required":["DATO MANCANTE"]},
    {"id":"rimedio", "blocco":"Conclusioni", "richiesta":"Decisione dell’avvocato: Alfa Fittizia esercita esclusivamente il recesso con doppio della caparra verso Beta Fittizia nel contratto di compravendita documentato. Scrivi soltanto la richiesta del pagamento di 4000 euro già calcolati, per effetto del recesso. Non aggiungere interessi, spese, risoluzione, rinunce, rilascio di beni, altri accertamenti o domande ulteriori. Usa solo la Fonte [1].", "required":["4000"]},
]


def main():
    gateway = LexGateway()
    config = gateway.config.providers["llamacpp"]
    if not config.enabled or not config.is_local:
        raise RuntimeError("Private model must be enabled")
    item = risolvi(Path("/data/normativa/codici_leggi.sqlite"), atto="codice_civile", articolo="1385")
    refs=[{"n":1,"atto":"codice_civile","articolo":"1385","sigla":"c.c."}]
    results=[]
    for case in CASES:
        def call(system, message):
            response=gateway.ask(user_id="release-synthetic-only",prompt=message,task="redazione_atto",requested_provider="llamacpp",allow_external=False,system_prompt=system,max_tokens=700,extra_body={"chat_template_kwargs":{"enable_thinking":False}})
            route=response.raw["lex_route"]
            if route["provider_order"] != ["llamacpp"] or route["external_allowed"]:
                raise RuntimeError("Unexpected provider route")
            return response.content,response.provider+":"+response.model
        source=FontiScheda("synthetic","Synthetic",fonti={1:item["text"]} if case["id"]=="rimedio" else {},fonti_ref=refs if case["id"]=="rimedio" else [])
        start=time.monotonic()
        result=scrivi_blocchi(chiama_modello=call,oggetto=case["richiesta"],risolta={"titolo":"Prova sintetica di rilascio","campi":[],"scrive_lex":[{"blocco":case["blocco"],"compito":"Scrivi soltanto il blocco richiesto rispettando la richiesta."}]},fonti=source,blocco_scadenze="",termini=[],fatti_testo=case["richiesta"],oggi=date(2026,10,24),assistito="Alfa Fittizia",controparte="Beta Fittizia",campi_modello=["facts","requests_or_conclusions"],ruolo_assistito="attore")
        compact=result.testo.lower().replace(".","").replace(" ","")
        required=all(s.lower().replace(" ","") in compact for s in case["required"])
        expected_incomplete = result.stato_consegna["stato"] == "bozza_incompleta" and "[DATO MANCANTE" in result.testo
        blocking = [g for g in result.revisione["gravi"] if not (expected_incomplete and g[0] == "vuoto")]
        ok=required and not blocking and case["blocco"] in result.blocchi
        results.append({"id":case["id"],"ok":ok,"seconds":round(time.monotonic()-start,2),"text":result.testo,"review":result.revisione,"delivery":result.stato_consegna,"model":result.modello_ai,"first_draft":result.prima_stesura,"first_review":result.revisione_prima_stesura,"draft_count":result.numero_stesure})
        print("PRIVATE_LEX_CASE_JSON="+json.dumps(results[-1],ensure_ascii=False),flush=True)
    print("PRIVATE_LEX_RESULT_JSON="+json.dumps({"passed":sum(r["ok"] for r in results),"total":len(results),"synthetic_only":True}),flush=True)
    if not all(r["ok"] for r in results):
        raise RuntimeError("Synthetic question check failed: review the preserved responses")


if __name__=="__main__":
    main()
