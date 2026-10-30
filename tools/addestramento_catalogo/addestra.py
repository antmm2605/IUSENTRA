"""Addestramento QLoRA del modello di catalogazione sul PC dell'avvocato (RTX 3060 12 GB, WSL Ubuntu).

Uso:
    python addestra.py --pacchetto ~/iusentra-addestramento/pacchetto --uscita ~/iusentra-addestramento/adattatore

Modelli base: Qwen 4B (scelta dell'avvocato del 30/10/2026) e, per il confronto, Spark-X2.5 4B con gli stessi esempi. Si addestrano solo gli adattatori LoRA su un modello
quantizzato a 4 bit; la perdita è calcolata solo sulla risposta (il JSON del catalogo), non sulla domanda.
Con `--domanda breve` (predefinita) l'elenco delle voci resta fuori dalla domanda: il modello le impara dagli
esempi e `valuta.py` usa la stessa domanda, letta da `addestramento.json` dell'adattatore.
Le righe «verifica», «verifica_avvocato» e «da_rivedere» non sono mai usate qui.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dati import conversazione, gruppo, leggi_pacchetto, prefisso_breve

MODELLO_BASE = "Qwen/Qwen3-4B-Instruct-2507"
# Spark-X2.5 4B (iFLYTEK, Apache 2.0): la stessa famiglia della seconda lettura di Lex nel catalogo
# («maternion/spark-x2.5:4b» su Ollama). Architettura propria: si carica con il codice del modello.
MODELLO_SPARK = "XHToken/Spark-X2.5-4B"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pacchetto", type=Path, required=True)
    parser.add_argument("--uscita", type=Path, required=True)
    parser.add_argument("--modello", default=MODELLO_BASE, help=f"es. {MODELLO_BASE} oppure {MODELLO_SPARK}")
    parser.add_argument("--codice-del-modello", action="store_true",
                        help="trust_remote_code: necessario per Spark-X2.5, che ha un'architettura propria")
    parser.add_argument("--epoche", type=float, default=1.0)
    parser.add_argument("--lunghezza-massima", type=int, default=4096)
    parser.add_argument("--accumulo", type=int, default=16, help="esempi per aggiornamento dei pesi (lotto × accumulo)")
    parser.add_argument("--lotto", type=int, default=1,
                        help="esempi elaborati insieme sulla GPU: con la domanda breve 4 stanno nei 12 GB e dimezzano i tempi")
    parser.add_argument("--passo", type=float, default=1e-4)
    parser.add_argument("--massimo-righe", type=int, default=0, help="0 = tutte; utile per una prova breve")
    parser.add_argument("--domanda", choices=("breve", "completa"), default="breve",
                        help="breve = senza l'elenco delle voci (sequenze di un terzo); completa = come Lex")
    args = parser.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )

    prefisso, righe, manifesto = leggi_pacchetto(args.pacchetto)
    if args.domanda == "breve":
        prefisso = prefisso_breve(prefisso)
    addestramento = gruppo(righe, "addestramento")
    random.Random(20261030).shuffle(addestramento)
    if args.massimo_righe:
        addestramento = addestramento[:args.massimo_righe]
    print(f"Righe di addestramento: {len(addestramento)} (pacchetto: {manifesto['per_gruppo']})", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(args.modello, trust_remote_code=args.codice_del_modello)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Riempimento a sinistra: la risposta resta in fondo alla sequenza, dove la perdita la cerca.
    tokenizer.padding_side = "left"

    def codifica(riga: dict) -> dict:
        domanda = tokenizer.apply_chat_template(conversazione(prefisso, riga, con_risposta=False), tokenize=False,
                                                add_generation_prompt=True)
        completa = tokenizer.apply_chat_template(conversazione(prefisso, riga), tokenize=False)
        ids_domanda = tokenizer(domanda, add_special_tokens=False)["input_ids"]
        ids = tokenizer(completa, add_special_tokens=False)["input_ids"][:args.lunghezza_massima]
        etichette = [-100] * min(len(ids_domanda), len(ids)) + ids[len(ids_domanda):]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": etichette[:len(ids)]}

    dataset = Dataset.from_list([codifica(r) for r in addestramento])
    # Una risposta troncata insegnerebbe JSON incompleti: si scartano le righe senza risposta intera.
    dataset = dataset.filter(lambda r: any(x != -100 for x in r["labels"][-8:]))
    lunghezze = sorted(len(r) for r in dataset["input_ids"])
    print(f"Token per esempio: mediana {lunghezze[len(lunghezze) // 2]}, massimo {lunghezze[-1]}", flush=True)

    quantizzazione = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                        bnb_4bit_compute_dtype=torch.bfloat16)
    modello = AutoModelForCausalLM.from_pretrained(args.modello, quantization_config=quantizzazione, device_map="auto",
                                                   dtype=torch.bfloat16, trust_remote_code=args.codice_del_modello,
                                                   attn_implementation="sdpa")
    # Niente prepare_model_for_kbit_training: porterebbe in float32 il vocabolario (1,5 GB per Qwen, condiviso
    # con l'uscita) e con lui tutto il flusso residuo salvato dal checkpointing. Si resta in bfloat16.
    modello.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    modello.config.use_cache = False
    modello = get_peft_model(modello, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        # Tutti gli strati lineari: vale per Qwen e per Spark, che chiamano diversamente le proiezioni.
        target_modules="all-linear"))
    modello.print_trainable_parameters()

    class AllenatoreSullaRisposta(Trainer):
        """La perdita si calcola solo sulla risposta (il JSON del catalogo, poche decine di token).

        Il prefisso della domanda pesa da solo circa 2.500 token: proiettare sul vocabolario intero (152.000 voci
        per Qwen) ogni posizione della sequenza non sta nei 12 GB della RTX 3060. Si proiettano solo le ultime
        posizioni, quelle che predicono la risposta: la perdita è la stessa, la memoria scende di gigabyte.
        """

        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            etichette = inputs.pop("labels")
            k = int((etichette != -100).sum(dim=1).max()) + 1
            causale = model.get_base_model()
            nascosti = causale.get_decoder()(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"],
                                             use_cache=False).last_hidden_state
            logit = causale.get_output_embeddings()(nascosti[:, -k:-1, :]).float()
            # Il Trainer passa num_items_in_batch e allora NON divide per l'accumulo: la perdita va normalizzata
            # sui token di risposta dell'intero passo, altrimenti si somma sui micro-lotti (16 volte più grande).
            somma = num_items_in_batch is not None
            perdita = torch.nn.functional.cross_entropy(logit.reshape(-1, logit.size(-1)),
                                                        etichette[:, -k + 1:].reshape(-1), ignore_index=-100,
                                                        reduction="sum" if somma else "mean")
            if somma:
                perdita = perdita / torch.as_tensor(num_items_in_batch, device=perdita.device)
            return (perdita, None) if return_outputs else perdita

    class MemoriaGPU(TrainerCallback):
        """Memoria e tempo dei primi passi: se il picco si avvicina ai 12 GB, WSL riversa nella RAM e rallenta."""

        def on_step_end(self, args_, state, control, **kwargs):
            if state.global_step <= 5 or state.global_step % 50 == 0:
                print(f"passo {state.global_step}: picco GPU {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB, "
                      f"riservata {torch.cuda.memory_reserved() / 2**20:.0f} MiB", flush=True)

    allenatore = AllenatoreSullaRisposta(
        model=modello,
        args=TrainingArguments(
            output_dir=str(args.uscita / "passaggi"), per_device_train_batch_size=args.lotto,
            gradient_accumulation_steps=max(1, args.accumulo // args.lotto),
            num_train_epochs=args.epoche, learning_rate=args.passo,
            lr_scheduler_type="cosine", warmup_steps=0.03, bf16=True, logging_steps=10, save_steps=200,
            save_total_limit=2, gradient_checkpointing=True, optim="paged_adamw_8bit", report_to=[], seed=20261030,
            gradient_checkpointing_kwargs={"use_reentrant": False}),
        train_dataset=dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100),
        callbacks=[MemoriaGPU()],
    )
    allenatore.train()
    args.uscita.mkdir(parents=True, exist_ok=True)
    modello.save_pretrained(args.uscita)
    tokenizer.save_pretrained(args.uscita)
    (args.uscita / "addestramento.json").write_text(json.dumps({
        "modello_base": args.modello, "righe": len(dataset), "epoche": args.epoche, "domanda": args.domanda,
        "manifesto": manifesto,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Adattatore salvato in {args.uscita}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
