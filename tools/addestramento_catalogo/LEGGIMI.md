# Addestramento del modello di catalogazione sul PC dello studio

Autorizzazione dell'avvocato del 30/10/2026: i testi dei documenti lasciano il server **solo pseudonimizzati**
(nomi, codici fiscali, indirizzi, contatti, numeri di ruolo sostituiti da segnaposto), viaggiano cifrati su
Tailscale e si **cancellano dal PC** a fine addestramento. Il modello base è Qwen 4B
(`Qwen/Qwen3-4B-Instruct-2507`), addestrato con QLoRA sulla RTX 3060.

## 1. Pacchetto sul server
Da GitHub → Actions → «Pacchetto di addestramento del catalogo» → *Run workflow*. Il riepilogo indica le righe
per gruppo e la cartella sul server (`/opt/iusentra/data/…/intelligence/addestramento_catalogo/pacchetto`).
Il file `corrispondenze.json` accanto al pacchetto **resta sul server**.

## 2. Copia sul PC (WSL Ubuntu)
```bash
mkdir -p ~/iusentra-addestramento && chmod 700 ~/iusentra-addestramento
scp -r root@IUSENTRA-SERVER:CARTELLA_DEL_PACCHETTO ~/iusentra-addestramento/pacchetto
```

## 3. Ambiente
```bash
python3 -m venv ~/iusentra-addestramento/venv && . ~/iusentra-addestramento/venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r tools/addestramento_catalogo/requirements.txt
```
Prima di addestrare fermare il servizio del modello grande sulla stessa GPU (es. `iusentra-llama35`) e
riavviarlo alla fine: la RTX 3060 non regge i due insieme.

## 4. Prova breve, poi addestramento completo
```bash
python tools/addestramento_catalogo/addestra.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --uscita ~/iusentra-addestramento/prova --massimo-righe 200
python tools/addestramento_catalogo/addestra.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --uscita ~/iusentra-addestramento/adattatore
```

## 5. Misura
```bash
python tools/addestramento_catalogo/valuta.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --senza-adattatore --uscita ~/iusentra-addestramento/misura-base
python tools/addestramento_catalogo/valuta.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --adattatore ~/iusentra-addestramento/adattatore --uscita ~/iusentra-addestramento/misura
```
`misura.json` contiene solo conteggi; `disaccordi.json` solo codici opachi e voci: sono i file da riportare.
Il modello si adotta nel catalogo solo se, sulle decisioni dell'avvocato, sbaglia meno delle regole e di Spark.

## 6. Cancellazione dei testi
```bash
shred -u ~/iusentra-addestramento/pacchetto/dataset.jsonl.gz && rm -rf ~/iusentra-addestramento/pacchetto
```
L'adattatore (pesi LoRA) non contiene i testi in chiaro e può restare.
