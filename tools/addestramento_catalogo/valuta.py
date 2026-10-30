"""Misura del modello di catalogazione addestrato, sul PC dell'avvocato.

Uso:
    python valuta.py --pacchetto ~/iusentra-addestramento/pacchetto --adattatore ~/iusentra-addestramento/adattatore \
        --uscita ~/iusentra-addestramento/misura
    python valuta.py ... --senza-adattatore   # lo stesso Qwen senza addestramento, per confronto

Gruppi misurati: `verifica` (quasi certe mai viste in addestramento), `verifica_avvocato` (decisioni dell'avvocato:
il confronto che conta), `banco_inventati` (tutte le voci, documenti inventati mai visti) e `da_rivedere` (proposte
incerte: solo i disaccordi con le regole). Escono:
- `misura.json`: soli conteggi, da riportare;
- `disaccordi.json`: codici opachi e voci, da riportare sul server per la revisione dell'avvocato;
- `predizioni.jsonl`: la voce scelta per ogni codice, per il confronto di `banco.py`.
Il modello si adotta nel catalogo solo se sulle decisioni dell'avvocato sbaglia meno delle regole e di Spark.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from addestra import MODELLO_BASE
from dati import conversazione, disaccordi, gruppo, leggi_pacchetto, leggi_risposta, misura, voci_del_prefisso


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pacchetto", type=Path, required=True)
    parser.add_argument("--adattatore", type=Path)
    parser.add_argument("--senza-adattatore", action="store_true")
    parser.add_argument("--modello", default=MODELLO_BASE)
    parser.add_argument("--codice-del-modello", action="store_true", help="trust_remote_code (Spark-X2.5)")
    parser.add_argument("--uscita", type=Path, required=True)
    parser.add_argument("--massimo-per-gruppo", type=int, default=0, help="0 = tutte")
    args = parser.parse_args()
    if not args.senza_adattatore and not args.adattatore:
        parser.error("Indicare --adattatore oppure --senza-adattatore")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    prefisso, righe, manifesto = leggi_pacchetto(args.pacchetto)
    voci = voci_del_prefisso(prefisso)
    tokenizer = AutoTokenizer.from_pretrained(args.adattatore or args.modello, trust_remote_code=args.codice_del_modello)
    modello = AutoModelForCausalLM.from_pretrained(
        args.modello, device_map="auto", dtype=torch.bfloat16, trust_remote_code=args.codice_del_modello,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_compute_dtype=torch.bfloat16))
    if not args.senza_adattatore:
        from peft import PeftModel

        modello = PeftModel.from_pretrained(modello, args.adattatore)
    modello.eval()

    def rispondi(riga: dict) -> dict[str, str]:
        testo = tokenizer.apply_chat_template(conversazione(prefisso, riga, con_risposta=False), tokenize=False,
                                              add_generation_prompt=True)
        ingresso = tokenizer(testo, return_tensors="pt").to(modello.device)
        with torch.no_grad():
            uscita = modello.generate(**ingresso, max_new_tokens=220, do_sample=False,
                                      pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
        return leggi_risposta(tokenizer.decode(uscita[0][ingresso["input_ids"].shape[1]:], skip_special_tokens=True), voci)

    args.uscita.mkdir(parents=True, exist_ok=True)
    risultato: dict = {"modello": args.modello, "adattatore": None if args.senza_adattatore else str(args.adattatore),
                       "pacchetto": manifesto}
    tutti_disaccordi: list[dict] = []
    predizioni: list[dict] = []
    for nome in ("verifica_avvocato", "verifica", "banco_inventati", "da_rivedere"):
        scelte = gruppo(righe, nome)
        if args.massimo_per_gruppo:
            scelte = scelte[:args.massimo_per_gruppo]
        risposte = {}
        for n, riga in enumerate(scelte, start=1):
            risposte[riga["id"]] = rispondi(riga)
            if n % 50 == 0:
                print(f"{nome}: {n}/{len(scelte)}", flush=True)
        predizioni.extend({"id": codice, "gruppo": nome, "etichetta": r["etichetta"]} for codice, r in risposte.items())
        if nome == "da_rivedere":
            tutti_disaccordi = list(disaccordi(scelte, risposte))
            risultato[nome] = {"documenti": len(scelte), "disaccordi_con_le_regole": len(tutti_disaccordi)}
        else:
            risultato[nome] = misura(scelte, risposte)
        print(nome, json.dumps(risultato[nome], ensure_ascii=False), flush=True)
    (args.uscita / "misura.json").write_text(json.dumps(risultato, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.uscita / "predizioni.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in predizioni),
                                                 encoding="utf-8")
    (args.uscita / "disaccordi.json").write_text(json.dumps(tutti_disaccordi, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print(f"Misura in {args.uscita / 'misura.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
