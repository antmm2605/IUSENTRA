# Workspace Applicazioni

Aggiornato al **20 aprile 2026**.

## Obiettivo

`/applicazioni` non e' piu' un catalogo di scorciatoie o schede descrittive: e' una **cabina applicativa unificata** che apre i moduli veri nello stesso workspace, con grammatica visiva coerente, contesto fascicolo e risultati leggibili.

## Regola di prodotto

Ogni voce del catalogo deve ricadere in uno di questi comportamenti espliciti:

- `tool`
  calcolo o motore reale eseguito inline dentro il workspace
- `template_atti`
  pannello operativo con template e checklist compatibili
- `economico`
  pannello reale con parcelle, preventivi e conferimenti
- `telematico`
  pannello reale con portali e fascicoli collegati
- `lookup`
  ricerca uffici / PEC o verifica formale con esito leggibile
- `rassegna`
  fonti presidiate, alert e monitor giuridico
- `giurisprudenza`
  archivio, corpus e ricerca coerente con il tema
- `utility`
  utility inline reale, non solo reindirizzamento
- `patrimonio` e `catalogo_operativo`
  raccordo vero con moduli, template e percorsi professionali

Non e' ammesso lasciare una voce come semplice link se il dominio esiste gia' nel gestionale.

## Architettura governabile

La filiera e' divisa in moduli piccoli:

- [pct/applicazioni_catalogo.py](../pct/applicazioni_catalogo.py)
  catalogo professionale, metadati, tassonomia e mapping delle entry
- [pct/applicazioni_runtime.py](../pct/applicazioni_runtime.py)
  risoluzione del runtime per ogni voce e normalizzazione dei risultati dei tool
- [web/services/applicazioni_runtime.py](../web/services/applicazioni_runtime.py)
  costruzione dei pannelli reali del workspace
- [web/blueprints/applicazioni.py](../web/blueprints/applicazioni.py)
  blueprint leggero: filtri, selezione voce e rendering
- [web/templates/applicazioni/index.html](../web/templates/applicazioni/index.html)
  interfaccia unica e coerente
- [web/static/scss/pages/_operational-workspaces.scss](../web/static/scss/pages/_operational-workspaces.scss)
  grammatica visiva condivisa dei workspace operativi

## Esperienza utente attesa

La pagina deve offrire sempre:

- hero e KPI coerenti con gli altri workspace professionali
- filtri per area, stato, tipologia e modalita'
- selezione del fascicolo di contesto
- modulo attivo sopra la griglia catalogo
- CTA doppia:
  - `Apri nel workspace`
  - `Apri dominio`
- stessi pattern di card, badge, pannelli e tabelle di `/strumenti-legali`

## Copertura minima verificata

La suite ufficiale copre almeno questi comportamenti:

- render del workspace operativo
- filtro per area e query
- redirect della vecchia scheda dettaglio verso il workspace attivo
- esecuzione reale di un tool inline
- pannello template/checklist
- pannello telematico ed economico

Test principali:

- [tests/test_applicazioni.py](../tests/test_applicazioni.py)
- [tests/test_applicazioni_repository.py](../tests/test_applicazioni_repository.py)

## Regola finale

Una voce di `/applicazioni` e' considerata chiusa solo se:

- apre davvero un modulo reale o un pannello operativo reale
- usa la stessa grammatica visiva del resto della piattaforma
- e' coperta da test di route e di comportamento
- non introduce fallback nascosti o scorciatoie fittizie
