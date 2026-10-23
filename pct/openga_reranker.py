"""Confronto locale domanda-oggetto con pesi pubblici gia pronti.

Non genera testo, non apprende dal banco e non modifica catalogo o indice.
Dipendenze opzionali importate solo nell'istanza esplicita, mai all'avvio app.
"""
from __future__ import annotations
import math
import re
import json
import hashlib
from pathlib import Path

MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"

def estratti_strutturali(text):
    """Intervalli letterali dell'oggetto, mai ricostruzioni o sintesi."""
    spans=[]
    quoted=re.search(r"\bavente\s+ad\s+oggetto\s*[:\"“']*\s*",text,re.I)
    if quoted and len(text)-quoted.end()>=30:
        spans.append((quoted.end(),len(text)))
    heading=re.match(r"\s*(?:per\s+l['’])?annullamento\s+(?:(?:del|della|dell['’])\s*)?(?:decreto|provvedimento|ordinanza)\b.{0,180}?,\s*(?:di|del|della)\s+",text,re.I)
    if heading and len(text)-heading.end()>=30:
        spans.append((heading.end(),len(text)))
    return sorted(set(spans))[:2]


def diversifica_descrizioni(query, ordered, protected_count=0):
    """Evita che descrizioni letteralmente uguali dello stesso ufficio/anno
    occupino tutta la lista. Non deduplica provvedimenti nel catalogo.

    Se la domanda contiene un anno si conserva l'ordine di pertinenza.
    Nessun anno privilegiato: tutte le ripetizioni restano in coda.
    """
    import unicodedata
    if re.search(r"\b(?:18|19|20|21)\d{2}\b",str(query)):
        return list(ordered)
    def key(row):
        text=str(row.get("oggetto") or "")
        spans=estratti_strutturali(text)
        if spans:
            begin,end=max(spans,key=lambda pair:pair[1]-pair[0]);text=text[begin:end]
        normalized=unicodedata.normalize("NFKD",text.casefold())
        normalized="".join(ch for ch in normalized if not unicodedata.combining(ch))
        tokens=tuple(re.findall(r"\w+",normalized))
        return(str(row.get("organo_giudicante") or ""),str(row.get("tipo_provvedimento") or ""),tokens,row.get("anno_sentenza"))
    protected=list(ordered[:protected_count]);seen={key(row) for row in protected}
    first=[];deferred=[]
    for row in ordered[protected_count:]:
        marker=key(row)
        if marker in seen:
            deferred.append(row)
        else:
            first.append(row);seen.add(marker)
    return protected+first+deferred


def verifica_pesi(model_path):
    root=Path(model_path).resolve()
    manifest=root/"iusentra-model-manifest.json"
    data=json.loads(manifest.read_text())
    if data.get("repo")!="BAAI/bge-reranker-v2-m3" or data.get("revision")!=MODEL_REVISION:
        raise ValueError("Provenienza o revisione del modello non riscontrata")
    listed=set()
    for row in data.get("files",[]):
        name=row["file"]
        if Path(name).name!=name:
            raise ValueError("Percorso del manifesto non valido")
        path=root/name
        if path.resolve().parent!=root:
            raise ValueError("File del modello fuori dalla cartella verificata")
        with path.open("rb") as stream:
            digest=hashlib.file_digest(stream,"sha256").hexdigest()
        if digest!=row["sha256"]:
            raise ValueError("Impronta dei pesi o della configurazione non corrispondente")
        listed.add(name)
    if not {"model.safetensors","config.json","tokenizer.json"}.issubset(listed):
        raise ValueError("Manifesto del modello incompleto")
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


class RerankerOpenGALocale:
    def __init__(self, model_path, *, device=None, batch_size=4):
        verified_manifest=verifica_pesi(model_path)
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        self.torch=torch
        self.path=Path(model_path)
        self.device=device or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.device=="cuda" and torch.cuda.mem_get_info()[0] < 3*1024**3:
            raise RuntimeError("Memoria GPU libera insufficiente: nessun altro processo viene interrotto")
        self.batch_size=max(1,min(16,int(batch_size)))
        self.tokenizer=AutoTokenizer.from_pretrained(self.path,local_files_only=True,trust_remote_code=False,token=False)
        dtype=torch.float16 if self.device=="cuda" else torch.float32
        self.model=AutoModelForSequenceClassification.from_pretrained(self.path,local_files_only=True,
            trust_remote_code=False,token=False,use_safetensors=True,dtype=dtype).to(self.device)
        self.model.eval().requires_grad_(False)
        self.config={"model":"BAAI/bge-reranker-v2-m3","revision":MODEL_REVISION,"device":self.device,"dtype":str(dtype),"batch_size":self.batch_size,"max_length":512,"training":False,"manifest_sha256":verified_manifest,"estratti":"sottostringhe_strutturali_v1","aggregazione":"max_originale_estratti"}
        self.last_stats={}
    def __call__(self,query,rows):
        from time import perf_counter
        for row in rows:
            if row.get("evidence_scope")!="metadata_only" or row.get("fonte_codice")!="openga":
                raise ValueError("Il confronto pubblico accetta solo metadati OpenGA")
        start=perf_counter();truncated=0
        scores=[-math.inf]*len(rows)
        passages=[];owners=[];spans_log=[]
        for index,row in enumerate(rows):
            text=str(row.get("oggetto") or "")
            title=str(row.get("organo_giudicante") or "")+" | Oggetto: "
            passages.append(title+text);owners.append(index)
            spans=estratti_strutturali(text)
            spans_log.append({"indice":index,"intervalli":spans})
            for begin,end in spans:
                passages.append(title+text[begin:end]);owners.append(index)
        for begin in range(0,len(passages),self.batch_size):
            batch=passages[begin:begin+self.batch_size]
            pairs=[[str(query),text] for text in batch]
            lengths=self.tokenizer(pairs,padding=False,truncation=False,return_length=True)["length"]
            truncated+=sum(length>512 for length in lengths)
            inputs=self.tokenizer(pairs,padding=True,truncation="only_second",return_tensors="pt",max_length=512)
            inputs={key:value.to(self.device) for key,value in inputs.items()}
            with self.torch.inference_mode():
                logits=self.model(**inputs,return_dict=True).logits.view(-1).float().cpu().tolist()
            if not all(math.isfinite(float(score)) for score in logits):
                raise ValueError("Punteggio del confronto non finito")
            for offset,value in enumerate(logits):
                owner=owners[begin+offset];scores[owner]=max(scores[owner],value)
        self.last_stats={"seconds":perf_counter()-start,"pairs":len(passages),"documenti":len(rows),"documenti_troncati":truncated,"estratti":spans_log,"config":self.config}
        return scores
