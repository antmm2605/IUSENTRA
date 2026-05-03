# Regole UI/UX per Codex - IUSENTRA

## Regole generali

- Tutto il testo visibile deve essere in italiano.
- Le date devono usare formati italiani.
- La UI deve essere professionale, sobria e adatta a studi legali.
- Ogni pagina deve indicare chiaramente stato, prossima azione e dati mancanti.
- Ogni azione sensibile deve avere feedback chiaro.
- Ogni modifica UI deve rispettare permessi, tenant e audit quando applicabile.

## Prima di modificare una UI

Codex deve dichiarare:
- schermata interessata;
- obiettivo;
- utenti coinvolti;
- file modificabili;
- file vietati;
- rischio principale;
- test o smoke da eseguire;
- criterio keep/discard.

## Stati obbligatori

Per ogni nuova superficie UI valutare:

- stato normale;
- stato vuoto;
- stato loading;
- stato errore;
- stato successo/conferma;
- stato permesso negato;
- stato dato incompleto.

## Coerenza visiva

- usare componenti esistenti quando possibile;
- evitare CSS isolato non governabile;
- preferire classi Bootstrap/coerenti con il bundle esistente;
- se si aggiunge SCSS/CSS, deve essere collocato nel percorso governato;
- non creare stili inline sparsi salvo casi minimi e motivati.

## Accessibilita'

- label associate ai campi;
- contrasto sufficiente;
- focus visibile;
- bottoni con testo comprensibile;
- icone non usate da sole per azioni importanti;
- gerarchia heading coerente.

## Criteri di scarto

Scartare o rivedere una proposta UI se:
- sembra un template generico;
- usa testi inglesi;
- usa colori fuori palette;
- crea layout bello ma poco operativo;
- rompe responsive;
- nasconde azioni principali;
- non gestisce stati vuoti/errori;
- non rispetta navigazione esistente;
- richiede modifiche backend non autorizzate.
