"""Lettura a parti del testo originale, con passaggi letterali verificati.

Non cambia le Fonti archiviate e non genera sintesi giuridiche da promuovere a
Fonti. Il modello riceve tutte le parti; il messaggio di stesura puo usare i
passaggi selezionati con prova di provenienza e copertura delle letture.
"""
from __future__ import annotations

from copy import copy
import hashlib
import json
import os


SISTEMA_LETTURA = (
    "Leggi il testo normativo ricevuto, distinguendolo dai fatti del caso. "
    "Seleziona passaggi letterali pertinenti alla richiesta, includendo condizioni, eccezioni, decorrenze e rinvii. "
    "Non riassumere e non inventare. Rispondi SOLO JSON: "
    '{"passaggi":["frase copiata esattamente dal testo"],"fine":"ultime 8-15 parole copiate dal testo"}. '
    "Massimo tre passaggi, al massimo 500 caratteri complessivi. "
    "La fine serve al controllo di ricezione, non e necessariamente pertinente alla domanda."
)


def _estrai(risposta: str, testo: str, *, massimo: int = 500) -> list[str]:
    obj=json.loads(risposta)
    if not isinstance(obj,dict) or set(obj)!={"passaggi","fine"} or not isinstance(obj["passaggi"],list):
        raise ValueError("Lettura delle fonti: formato non valido")
    fine=obj["fine"]
    word_count=len(testo.split())
    if (not isinstance(fine,str) or not fine.strip()
            or not min(8,word_count)<=len(fine.split())<=15
            or not testo.rstrip().endswith(fine.strip())):
        raise ValueError("Lettura delle fonti: occorre la coda letterale di 8-15 parole, non una parola presente genericamente alla fine")
    passages=[]
    for value in obj["passaggi"]:
        if not isinstance(value,str) or not value.strip() or value not in testo:
            raise ValueError("Lettura delle fonti: citazione non presente nel testo originale")
        if value not in passages:passages.append(value)
    if len(passages)>3 or sum(len(p) for p in passages)>massimo:
        raise ValueError("Lettura delle fonti: numero o lunghezza dei passaggi oltre il limite")
    if not passages and len(fine)>massimo:
        raise ValueError("Lettura delle fonti: riscontro finale oltre il limite")
    return passages or [fine]


def _seleziona(chiama_modello, testo: str, richiesta: str, *, massimo: int = 500) -> tuple[list[str],str,dict]:
    prompt="Richiesta (non e una Fonte):\n"+richiesta+"\n\nTesto normativo da leggere:\n"+testo
    response,model=chiama_modello(SISTEMA_LETTURA+f" Limite complessivo obbligatorio: {massimo} caratteri.",prompt)
    try:
        passages=_estrai(response,testo,massimo=massimo)
    except (ValueError,TypeError):
        response,model=chiama_modello(SISTEMA_LETTURA+f" Limite obbligatorio: {massimo} caratteri.",prompt+"\nRestituisci JSON valido e soltanto citazioni copiate letteralmente; non cambiare apostrofi o parole.")
        passages=_estrai(response,testo,massimo=massimo)
    return passages,model,dict(getattr(chiama_modello,"ultimo_uso",{}) or {})


def prepara_letture(fonti, *, richiesta: str, chiama_modello, messaggio_caratteri: int, messaggio: str = "", sistema: str = "", budget_caratteri: int | None = None, forza_parti: bool = False):
    budget=budget_caratteri if budget_caratteri is not None else int(os.getenv("LEX_STESURA_CONTESTO_CARATTERI","30000"))
    if type(budget) is not int or budget<1000:raise ValueError("Budget di lettura non valido")
    trace=[]
    integrale = messaggio_caratteri<=budget and not forza_parti
    if messaggio and callable(getattr(chiama_modello, "misura_prompt", None)):
        # Il bridge privato ammette 2 MiB: i messaggi evidentemente enormi
        # vengono suddivisi prima della misura, senza aumentare quel limite.
        serialized=len(json.dumps({"system":sistema,"user":messaggio},ensure_ascii=True).encode())
        if serialized<=1500000:
            measured=chiama_modello.misura_prompt(sistema,messaggio)
            fits=measured["tokens_input"]+4096<=measured["contesto"]
            explicit=budget_caratteri is not None or bool(os.getenv("LEX_STESURA_CONTESTO_CARATTERI"))
            integrale=fits and not forza_parti and (not explicit or messaggio_caratteri<=budget)
            if not explicit:
                budget=max(6000,(measured["contesto"]-4096)*3)
        else:
            integrale=False
    if integrale:
        for n,text in sorted(fonti.fonti.items()):
            trace.append({"fonte":n,"sha256_testo":hashlib.sha256(text.encode()).hexdigest(),
                          "modalita":"integrale_nel_messaggio","caratteri":len(text)})
        return fonti,trace
    overhead=max(0,messaggio_caratteri-sum(len(t) for t in fonti.fonti.values()))
    header="Passaggi letterali selezionati dopo la lettura delle parti del testo originale:\n"
    available=budget-overhead-len(fonti.fonti)*(len(header)+10)-1024
    allowance=min(500,available//max(1,len(fonti.fonti)))
    if allowance<100:
        raise ValueError("Il contesto dei dati richiede elaborazione separata prima della stesura: nessun testo è stato troncato")
    view=copy(fonti);view.fonti={}
    for n,text in sorted(fonti.fonti.items()):
        selected=[];parts=[]
        # Confini deterministici e contigui: nessun carattere viene saltato.
        dimensione_parti=min(6000,budget-len(SISTEMA_LETTURA)-len(richiesta)-1024)
        if dimensione_parti<100:
            raise ValueError("La richiesta non lascia spazio per leggere le fonti nel contesto disponibile")
        for start in range(0,len(text),dimensione_parti):
            part=text[start:start+dimensione_parti]
            passages,model,usage=_seleziona(chiama_modello,part,richiesta)
            selected.extend(p for p in passages if p not in selected)
            parts.append({"inizio":start,"fine":start+len(part),"sha256":hashlib.sha256(part.encode()).hexdigest(),
                          "modello":model,"uso":usage})
        excerpts="\n".join(selected)
        if len(excerpts)>allowance:
            selected,_,_=_seleziona(chiama_modello,excerpts,richiesta,massimo=allowance)
            excerpts="\n".join(selected)
        # Mai accorciare una citazione per ottenere un budget artificiale.
        if len(excerpts)>allowance:
            raise ValueError("I passaggi della Fonte non rientrano nel budget: lettura da completare per blocchi")
        view.fonti[n]=header+excerpts
        trace.append({"fonte":n,"sha256_testo":hashlib.sha256(text.encode()).hexdigest(),"modalita":"lettura_per_parti",
                      "caratteri":len(text),"parti":parts,"passaggi_sha256":hashlib.sha256(excerpts.encode()).hexdigest()})
    if overhead+sum(len(t) for t in view.fonti.values())>budget:
        raise ValueError("Budget complessivo incoerente dopo la lettura: nessuna stesura inviata con fonti troncate")
    return view,trace
