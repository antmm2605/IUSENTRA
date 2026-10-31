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
Il workflow copia il pacchetto (senza corrispondenze) nella cartella dell'utente `claude-iusentra` sul server.
```bash
mkdir -p ~/iusentra-addestramento && chmod 700 ~/iusentra-addestramento
scp -r iusentra-claude:addestramento_catalogo/pacchetto_studio_1 ~/iusentra-addestramento/pacchetto
```

## 2-bis. Decisioni sui disaccordi
Le righe «da rivedere» con `voce_lineare` sono i disaccordi sicuri fra regole e classificatore piccolo. Le
decisioni (dell'avvocato o, su sua autorizzazione del 30/10/2026, di Claude sui testi pseudonimizzati) vanno in
`~/iusentra-addestramento/decisioni.jsonl`, una riga per documento: `{"id": codice, "voce": voce del catalogo,
"fonte": "avvocato" | "claude"}`. `valuta.py` e `banco.py` le usano con `--decisioni` come verifica decisiva.

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

## 6. Spark-X2.5 con gli stessi esempi, per il confronto
```bash
python tools/addestramento_catalogo/addestra.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --modello XHToken/Spark-X2.5-4B --codice-del-modello --uscita ~/iusentra-addestramento/adattatore-spark
python tools/addestramento_catalogo/valuta.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --modello XHToken/Spark-X2.5-4B --codice-del-modello --senza-adattatore --uscita ~/iusentra-addestramento/misura-spark-base
python tools/addestramento_catalogo/valuta.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --modello XHToken/Spark-X2.5-4B --codice-del-modello --adattatore ~/iusentra-addestramento/adattatore-spark \
  --uscita ~/iusentra-addestramento/misura-spark
```

## 7. Banco di prova
```bash
python tools/addestramento_catalogo/banco.py --pacchetto ~/iusentra-addestramento/pacchetto \
  --risultati qwen_base=~/iusentra-addestramento/misura-base --risultati qwen_addestrato=~/iusentra-addestramento/misura \
  --risultati spark_base=~/iusentra-addestramento/misura-spark-base --risultati spark_addestrato=~/iusentra-addestramento/misura-spark \
  --uscita ~/iusentra-addestramento/banco
```
Confronta regole, Spark del catalogo, classificatore lineare, Qwen e Spark (prima e dopo l'addestramento) sugli
stessi documenti mai visti. Il banco inventato verifica che ogni modello conosca tutte le voci; il confronto che
decide è sui documenti reali, soprattutto sulle decisioni dell'avvocato.

## 8. Cancellazione dei testi
```bash
shred -u ~/iusentra-addestramento/pacchetto/dataset.jsonl.gz && rm -rf ~/iusentra-addestramento/pacchetto
```
L'adattatore (pesi LoRA) non contiene i testi in chiaro e può restare.

## 9. Piano del 31/10/2026: misure corrette e nuovo addestramento di Qwen e Spark

Esito del primo ciclo (Qwen addestrato sul pacchetto del 30/10): 86% sui 271 disaccordi (regole 13%),
95% in verifica (regole 100%), 100% sul banco inventato; 37 risposte illeggibili (JSON troncato). Il Qwen
di partenza risultava allo 0% per un difetto di lettura della voce, non del modello: `dati.leggi_risposta`
ora riconosce la voce anche con la sezione «[…]», maiuscole o accenti diversi (solo corrispondenza
esatta dopo la normalizzazione) e i JSON troncati; `valuta.py` salva `risposte_grezze.jsonl`.

Errori principali del modello: sentenza citata come precedente letta come sentenza della causa (6),
note 127-ter lette come decreto di fissazione udienza (4); 36 note d'iscrizione a ruolo etichettate
«Nota di deposito» nelle decisioni perché la voce mancava nell'elenco del 30/10.

Passi:
1. Misure di partenza con gli strumenti corretti: Qwen di partenza, Qwen addestrato (riferimento),
   Spark-X2.5 di partenza; `banco.py` sulle tre misure. Servono da punto zero, non per scegliere.
2. Dopo il deploy della 2.467.0: nuovo pacchetto sul server con il catalogo aggiornato (voce «Nota di
   iscrizione a ruolo», precedenti, 297 voci), le 36 etichette corrette e esempi mirati sugli errori
   (sentenza della causa contro precedente citato; note 127-ter contro decreto di fissazione; messaggio
   PEC contro lettera; decreto di rinvio contro decreto di fissazione). Le decisioni dell'avvocato restano
   solo insieme di misura, mai di addestramento. Risposta corta e vincolata (voce e citazione).
3. Addestramento di **Qwen e Spark** sullo stesso pacchetto con gli stessi parametri, poi misura di
   entrambi sugli stessi documenti mai visti e `banco.py` con regole, lineare, Spark e i quattro modelli.
4. Adozione solo se il modello batte le regole sui casi decisi dall'avvocato, come seconda lettura dei
   soli casi incerti, in sottofondo; sui precedenti giurisprudenziali comanda la regola.
5. Cancellazione dei testi (sezione 8) solo a misure complete, con la conferma dell'avvocato.
