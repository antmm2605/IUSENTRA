"""Norme dell'harness di Lex: catalogo, testo vigente dall'archivio e controllo di ciò che si afferma.

Ogni regola dell'harness cita una norma con una «ancora»: le parole letterali del testo vigente su cui si fonda
l'affermazione (es. art. 1385 c.c. → «esigere il doppio della caparra»). Il controllore accetta l'affermazione solo se
l'ancora compare nel testo dell'articolo letto dall'archivio Normattiva del software (``PCT_NORMATTIVA_DB``):
niente norme a memoria, niente articoli inventati.

Il testo si legge una volta dall'archivio con ``scripts/lex_harness_norme.py`` e si conserva in
``dati/norme_vigenti.json`` con edizione, URN e impronta; a runtime l'harness legge quell'istantanea (millisecondi) e,
se un articolo manca, prova l'archivio dal vivo. Una norma che non si riesce a leggere non entra nella risposta:
il punto va fra i dubbi con il motivo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

CARTELLA_DATI = Path(__file__).with_name("dati")
ISTANTANEA = CARTELLA_DATI / "norme_vigenti.json"


@dataclass(frozen=True)
class Norma:
    chiave: str        # «cc:1385»
    estremi: str       # come li legge web.services.ricerca_legale_norma_citata.estremi
    citazione: str     # «art. 1385 c.c.»
    rubrica: str = ""


def _n(chiave: str, estremi: str, citazione: str, rubrica: str = "") -> Norma:
    return Norma(chiave, estremi, citazione, rubrica)


_CC, _CPC, _CP, _CPP = "r.d. 262/1942", "r.d. 1443/1940", "r.d. 1398/1930", "d.p.r. 447/1988"

NORME: dict[str, Norma] = {n.chiave: n for n in (
    # Codice civile
    _n("cc:151", f"art. 151 {_CC}", "art. 151 c.c.", "Separazione giudiziale"),
    _n("cc:337ter", f"art. 337-ter {_CC}", "art. 337-ter c.c.", "Provvedimenti riguardo ai figli"),
    _n("cc:337septies", f"art. 337-septies {_CC}", "art. 337-septies c.c.", "Figli maggiorenni"),
    _n("cc:1137", f"art. 1137 {_CC}", "art. 1137 c.c.", "Impugnazione delle deliberazioni dell'assemblea"),
    _n("cc:1182", f"art. 1182 {_CC}", "art. 1182 c.c.", "Luogo dell'adempimento"),
    _n("cc:1224", f"art. 1224 {_CC}", "art. 1224 c.c.", "Danni nelle obbligazioni pecuniarie"),
    _n("cc:1351", f"art. 1351 {_CC}", "art. 1351 c.c.", "Contratto preliminare"),
    _n("cc:1385", f"art. 1385 {_CC}", "art. 1385 c.c.", "Caparra confirmatoria"),
    _n("cc:1284", f"art. 1284 {_CC}", "art. 1284 c.c.", "Saggio degli interessi"),
    _n("cc:1453", f"art. 1453 {_CC}", "art. 1453 c.c.", "Risolubilità del contratto per inadempimento"),
    _n("cc:1455", f"art. 1455 {_CC}", "art. 1455 c.c.", "Importanza dell'inadempimento"),
    _n("cc:1454", f"art. 1454 {_CC}", "art. 1454 c.c.", "Diffida ad adempiere"),
    _n("cc:1587", f"art. 1587 {_CC}", "art. 1587 c.c.", "Obbligazioni principali del conduttore"),
    _n("cc:2932", f"art. 2932 {_CC}", "art. 2932 c.c.", "Esecuzione specifica dell'obbligo di concludere un contratto"),
    _n("cc:2948", f"art. 2948 {_CC}", "art. 2948 c.c.", "Prescrizione di cinque anni"),
    # Codice di procedura civile
    _n("cpc:7", f"art. 7 {_CPC}", "art. 7 c.p.c.", "Competenza del giudice di pace"),
    _n("cpc:9", f"art. 9 {_CPC}", "art. 9 c.p.c.", "Competenza del tribunale"),
    _n("cpc:10", f"art. 10 {_CPC}", "art. 10 c.p.c.", "Determinazione del valore"),
    _n("cpc:14", f"art. 14 {_CPC}", "art. 14 c.p.c.", "Cause relative a somme di danaro e a beni mobili"),
    _n("cpc:18", f"art. 18 {_CPC}", "art. 18 c.p.c.", "Foro generale delle persone fisiche"),
    _n("cpc:19", f"art. 19 {_CPC}", "art. 19 c.p.c.", "Foro generale delle persone giuridiche"),
    _n("cpc:20", f"art. 20 {_CPC}", "art. 20 c.p.c.", "Foro facoltativo per le cause relative a diritti di obbligazione"),
    _n("cpc:21", f"art. 21 {_CPC}", "art. 21 c.p.c.", "Foro per le cause relative a diritti reali e ad azioni possessorie"),
    _n("cpc:38", f"art. 38 {_CPC}", "art. 38 c.p.c.", "Incompetenza"),
    _n("cpc:86", f"art. 86 {_CPC}", "art. 86 c.p.c.", "Difesa personale della parte"),
    _n("cpc:83", f"art. 83 {_CPC}", "art. 83 c.p.c.", "Procura alle liti"),
    _n("cpc:155", f"art. 155 {_CPC}", "art. 155 c.p.c.", "Computo dei termini"),
    _n("cpc:163", f"art. 163 {_CPC}", "art. 163 c.p.c.", "Contenuto della citazione"),
    _n("cpc:163bis", f"art. 163-bis {_CPC}", "art. 163-bis c.p.c.", "Termini per comparire"),
    _n("cpc:165", f"art. 165 {_CPC}", "art. 165 c.p.c.", "Costituzione dell'attore"),
    _n("cpc:166", f"art. 166 {_CPC}", "art. 166 c.p.c.", "Costituzione del convenuto"),
    _n("cpc:167", f"art. 167 {_CPC}", "art. 167 c.p.c.", "Comparsa di risposta"),
    _n("cpc:168bis", f"art. 168-bis {_CPC}", "art. 168-bis c.p.c.", "Designazione del giudice istruttore"),
    _n("cpc:171ter", f"art. 171-ter {_CPC}", "art. 171-ter c.p.c.", "Memorie integrative"),
    _n("cpc:281decies", f"art. 281-decies {_CPC}", "art. 281-decies c.p.c.", "Procedimento semplificato di cognizione"),
    _n("cpc:281undecies", f"art. 281-undecies {_CPC}", "art. 281-undecies c.p.c.", "Forma della domanda"),
    _n("cpc:325", f"art. 325 {_CPC}", "art. 325 c.p.c.", "Termini per le impugnazioni"),
    _n("cpc:327", f"art. 327 {_CPC}", "art. 327 c.p.c.", "Decadenza dall'impugnazione"),
    _n("cpc:409", f"art. 409 {_CPC}", "art. 409 c.p.c.", "Controversie individuali di lavoro"),
    _n("cpc:410", f"art. 410 {_CPC}", "art. 410 c.p.c.", "Tentativo di conciliazione"),
    _n("cpc:413", f"art. 413 {_CPC}", "art. 413 c.p.c.", "Giudice competente"),
    _n("cpc:414", f"art. 414 {_CPC}", "art. 414 c.p.c.", "Forma della domanda"),
    _n("cpc:429", f"art. 429 {_CPC}", "art. 429 c.p.c.", "Pronuncia della sentenza"),
    _n("cpc:434", f"art. 434 {_CPC}", "art. 434 c.p.c.", "Deposito del ricorso in appello"),
    _n("cpc:447bis", f"art. 447-bis {_CPC}", "art. 447-bis c.p.c.", "Norme applicabili alle controversie in materia di locazione"),
    _n("cpc:473bis", f"art. 473-bis {_CPC}", "art. 473-bis c.p.c.", "Ambito di applicazione"),
    _n("cpc:473bis11", f"art. 473-bis.11 {_CPC}", "art. 473-bis.11 c.p.c.", "Competenza per territorio"),
    _n("cpc:473bis12", f"art. 473-bis.12 {_CPC}", "art. 473-bis.12 c.p.c.", "Forma della domanda"),
    _n("cpc:473bis49", f"art. 473-bis.49 {_CPC}", "art. 473-bis.49 c.p.c.", "Cumulo di domande di separazione e divorzio"),
    _n("cpc:479", f"art. 479 {_CPC}", "art. 479 c.p.c.", "Notificazione del titolo esecutivo e del precetto"),
    _n("cpc:480", f"art. 480 {_CPC}", "art. 480 c.p.c.", "Forma del precetto"),
    _n("cpc:481", f"art. 481 {_CPC}", "art. 481 c.p.c.", "Cessazione dell'efficacia del precetto"),
    _n("cpc:482", f"art. 482 {_CPC}", "art. 482 c.p.c.", "Termine ad adempiere"),
    _n("cpc:617", f"art. 617 {_CPC}", "art. 617 c.p.c.", "Forma dell'opposizione agli atti esecutivi"),
    _n("cpc:633", f"art. 633 {_CPC}", "art. 633 c.p.c.", "Condizioni di ammissibilità"),
    _n("cpc:634", f"art. 634 {_CPC}", "art. 634 c.p.c.", "Prova scritta"),
    _n("cpc:637", f"art. 637 {_CPC}", "art. 637 c.p.c.", "Giudice competente"),
    _n("cpc:641", f"art. 641 {_CPC}", "art. 641 c.p.c.", "Accoglimento della domanda"),
    _n("cpc:642", f"art. 642 {_CPC}", "art. 642 c.p.c.", "Esecuzione provvisoria"),
    _n("cpc:644", f"art. 644 {_CPC}", "art. 644 c.p.c.", "Mancata notificazione del decreto"),
    _n("cpc:645", f"art. 645 {_CPC}", "art. 645 c.p.c.", "Opposizione"),
    _n("cpc:657", f"art. 657 {_CPC}", "art. 657 c.p.c.", "Intimazione di licenza e di sfratto"),
    _n("cpc:658", f"art. 658 {_CPC}", "art. 658 c.p.c.", "Intimazione di sfratto per morosità"),
    _n("cpc:660", f"art. 660 {_CPC}", "art. 660 c.p.c.", "Forma dell'intimazione"),
    _n("cpc:661", f"art. 661 {_CPC}", "art. 661 c.p.c.", "Giudice competente"),
    # Codice penale e di procedura penale
    _n("cp:124", f"art. 124 {_CP}", "art. 124 c.p.", "Termine per proporre la querela"),
    _n("cpp:585", f"art. 585 {_CPP}", "art. 585 c.p.p.", "Termini per l'impugnazione"),
    # Leggi speciali
    _n("dl132:3", "art. 3 d.l. 132/2014", "art. 3 d.l. 132/2014", "Improcedibilità"),
    _n("dlgs28:5", "art. 5 d.lgs. 28/2010", "art. 5 d.lgs. 28/2010", "Condizione di procedibilità e rapporti con il processo"),
    _n("l742:1", "art. 1 l. 742/1969", "art. 1 l. 742/1969", "Sospensione dei termini nel periodo feriale"),
    _n("l742:3", "art. 3 l. 742/1969", "art. 3 l. 742/1969", "Esclusioni"),
    _n("l392:5", "art. 5 l. 392/1978", "art. 5 l. 392/1978", "Inadempimento del conduttore"),
    _n("l392:55", "art. 55 l. 392/1978", "art. 55 l. 392/1978", "Termine per il pagamento dei canoni scaduti"),
    _n("l604:6", "art. 6 l. 604/1966", "art. 6 l. 604/1966", "Impugnazione del licenziamento"),
    _n("l898:3", "art. 3 l. 898/1970", "art. 3 l. 898/1970", "Casi di scioglimento"),
    _n("dlgs206:66bis", "art. 66-bis d.lgs. 206/2005", "art. 66-bis d.lgs. 206/2005 (codice del consumo)", "Foro competente"),
    _n("cpa:29", "art. 29 d.lgs. 104/2010", "art. 29 c.p.a.", "Azione di annullamento"),
    _n("cpa:41", "art. 41 d.lgs. 104/2010", "art. 41 c.p.a.", "Notificazione del ricorso e suoi destinatari"),
    _n("dlgs546:21", "art. 21 d.lgs. 546/1992", "art. 21 d.lgs. 546/1992", "Termine per la proposizione del ricorso"),
    # Norme dei casi del banco di prova dell'avvocato (19/11/2026)
    _n("cc:243bis", f"art. 243-bis {_CC}", "art. 243-bis c.c.", "Disconoscimento di paternità"),
    _n("cc:244", f"art. 244 {_CC}", "art. 244 c.c.", "Termini dell'azione di disconoscimento"),
    _n("cc:480", f"art. 480 {_CC}", "art. 480 c.c.", "Prescrizione del diritto di accettare l'eredità"),
    _n("cc:485", f"art. 485 {_CC}", "art. 485 c.c.", "Chiamato all'eredità che è nel possesso di beni"),
    _n("cc:519", f"art. 519 {_CC}", "art. 519 c.c.", "Rinunzia all'eredità"),
    _n("cc:1193", f"art. 1193 {_CC}", "art. 1193 c.c.", "Imputazione del pagamento"),
    _n("cc:1194", f"art. 1194 {_CC}", "art. 1194 c.c.", "Imputazione del pagamento agli interessi"),
    _n("cc:1199", f"art. 1199 {_CC}", "art. 1199 c.c.", "Diritto del debitore alla quietanza"),
    _n("cc:1219", f"art. 1219 {_CC}", "art. 1219 c.c.", "Costituzione in mora"),
    _n("cc:1282", f"art. 1282 {_CC}", "art. 1282 c.c.", "Interessi nelle obbligazioni pecuniarie"),
    _n("cc:1457", f"art. 1457 {_CC}", "art. 1457 c.c.", "Termine essenziale per una delle parti"),
    _n("cc:1460", f"art. 1460 {_CC}", "art. 1460 c.c.", "Eccezione d'inadempimento"),
    _n("cc:1575", f"art. 1575 {_CC}", "art. 1575 c.c.", "Obbligazioni principali del locatore"),
    _n("cc:1576", f"art. 1576 {_CC}", "art. 1576 c.c.", "Mantenimento della cosa in buono stato locativo"),
    _n("cc:1578", f"art. 1578 {_CC}", "art. 1578 c.c.", "Vizi della cosa locata"),
    _n("cc:1655", f"art. 1655 {_CC}", "art. 1655 c.c.", "Nozione dell'appalto"),
    _n("cc:1667", f"art. 1667 {_CC}", "art. 1667 c.c.", "Difformità e vizi dell'opera"),
    _n("cc:1668", f"art. 1668 {_CC}", "art. 1668 c.c.", "Contenuto della garanzia per difetti dell'opera"),
    _n("cc:1669", f"art. 1669 {_CC}", "art. 1669 c.c.", "Rovina e difetti di cose immobili"),
    _n("cc:1965", f"art. 1965 {_CC}", "art. 1965 c.c.", "Nozione della transazione"),
    _n("cc:2120", f"art. 2120 {_CC}", "art. 2120 c.c.", "Disciplina del trattamento di fine rapporto"),
    _n("cc:2697", f"art. 2697 {_CC}", "art. 2697 c.c.", "Onere della prova"),
    _n("cc:2935", f"art. 2935 {_CC}", "art. 2935 c.c.", "Decorrenza della prescrizione"),
    _n("cc:2943", f"art. 2943 {_CC}", "art. 2943 c.c.", "Interruzione da parte del titolare"),
    _n("cc:2946", f"art. 2946 {_CC}", "art. 2946 c.c.", "Prescrizione ordinaria"),
    _n("cc:2947", f"art. 2947 {_CC}", "art. 2947 c.c.", "Prescrizione del diritto al risarcimento del danno"),
    _n("cc:2964", f"art. 2964 {_CC}", "art. 2964 c.c.", "Inapplicabilità di regole della prescrizione"),
    _n("cc:2966", f"art. 2966 {_CC}", "art. 2966 c.c.", "Cause che impediscono la decadenza"),
    _n("cpc:27", f"art. 27 {_CPC}", "art. 27 c.p.c.", "Competenza per le opposizioni all'esecuzione"),
    _n("cpc:96", f"art. 96 {_CPC}", "art. 96 c.p.c.", "Responsabilità aggravata"),
    _n("cpc:492bis", f"art. 492-bis {_CPC}", "art. 492-bis c.p.c.", "Ricerca con modalità telematiche dei beni da pignorare"),
    _n("cpc:521bis", f"art. 521-bis {_CPC}", "art. 521-bis c.p.c.", "Pignoramento di autoveicoli"),
    _n("cpc:543", f"art. 543 {_CPC}", "art. 543 c.p.c.", "Forma del pignoramento presso terzi"),
    _n("cpc:615", f"art. 615 {_CPC}", "art. 615 c.p.c.", "Forma dell'opposizione all'esecuzione"),
    _n("cpc:624", f"art. 624 {_CPC}", "art. 624 c.p.c.", "Sospensione per opposizione all'esecuzione"),
    _n("cpc:650", f"art. 650 {_CPC}", "art. 650 c.p.c.", "Opposizione tardiva"),
    _n("cpc:663", f"art. 663 {_CPC}", "art. 663 c.p.c.", "Mancata comparizione o mancata opposizione dell'intimato"),
    _n("cpc:665", f"art. 665 {_CPC}", "art. 665 c.p.c.", "Opposizione e provvedimenti del giudice"),
    _n("cpc:667", f"art. 667 {_CPC}", "art. 667 c.p.c.", "Mutamento del rito"),
    _n("cpc:669octies", f"art. 669-octies {_CPC}", "art. 669-octies c.p.c.", "Provvedimento di accoglimento"),
    _n("cpc:669novies", f"art. 669-novies {_CPC}", "art. 669-novies c.p.c.", "Inefficacia del provvedimento cautelare"),
    _n("cpc:671", f"art. 671 {_CPC}", "art. 671 c.p.c.", "Sequestro conservativo"),
    _n("cpc:675", f"art. 675 {_CPC}", "art. 675 c.p.c.", "Termine per l'esecuzione"),
    _n("cp:595", f"art. 595 {_CP}", "art. 595 c.p.", "Diffamazione"),
    _n("cp:597", f"art. 597 {_CP}", "art. 597 c.p.", "Querela della persona offesa"),
    _n("cpp:336", f"art. 336 {_CPP}", "art. 336 c.p.p.", "Querela"),
    _n("cpa:40", "art. 40 d.lgs. 104/2010", "art. 40 c.p.a.", "Contenuto del ricorso"),
    _n("dl132:2", "art. 2 d.l. 132/2014", "art. 2 d.l. 132/2014", "Convenzione di negoziazione assistita"),
    _n("dl132:4", "art. 4 d.l. 132/2014", "art. 4 d.l. 132/2014", "Non accettazione dell'invito"),
    _n("dlgs28:8", "art. 8 d.lgs. 28/2010", "art. 8 d.lgs. 28/2010", "Procedimento"),
    _n("l392:27", "art. 27 l. 392/1978", "art. 27 l. 392/1978", "Durata della locazione non abitativa"),
    _n("l431:13", "art. 13 l. 431/1998", "art. 13 l. 431/1998", "Patti contrari alla legge"),
    _n("l24:8", "art. 8 l. 24/2017", "art. 8 l. 24/2017", "Tentativo obbligatorio di conciliazione"),
    _n("l604:2", "art. 2 l. 604/1966", "art. 2 l. 604/1966", "Forma del licenziamento"),
    _n("l604:3", "art. 3 l. 604/1966", "art. 3 l. 604/1966", "Giustificato motivo"),
    _n("l604:5", "art. 5 l. 604/1966", "art. 5 l. 604/1966", "Onere della prova"),
    _n("l300:7", "art. 7 l. 300/1970", "art. 7 l. 300/1970", "Sanzioni disciplinari"),
    _n("l300:18", "art. 18 l. 300/1970", "art. 18 l. 300/1970", "Tutela del lavoratore in caso di licenziamento illegittimo"),
    _n("l183:32", "art. 32 l. 183/2010", "art. 32 l. 183/2010", "Decadenze e disposizioni in materia di contratto di lavoro a tempo determinato"),
    _n("dlgs23:1", "art. 1 d.lgs. 23/2015", "art. 1 d.lgs. 23/2015", "Campo di applicazione"),
    _n("dlgs23:3", "art. 3 d.lgs. 23/2015", "art. 3 d.lgs. 23/2015", "Licenziamento per giustificato motivo e giusta causa"),
    _n("dlgs23:6", "art. 6 d.lgs. 23/2015", "art. 6 d.lgs. 23/2015", "Offerta di conciliazione"),
    _n("dlgs23:9", "art. 9 d.lgs. 23/2015", "art. 9 d.lgs. 23/2015", "Piccole imprese e organizzazioni di tendenza"),
    _n("dlgs23:11", "art. 11 d.lgs. 23/2015", "art. 11 d.lgs. 23/2015", "Rito applicabile"),
    _n("dlgs209:139", "art. 139 d.lgs. 209/2005", "art. 139 d.lgs. 209/2005", "Danno non patrimoniale per lesioni di lieve entità"),
    _n("dlgs209:144", "art. 144 d.lgs. 209/2005", "art. 144 d.lgs. 209/2005", "Azione diretta del danneggiato"),
    _n("dlgs209:145", "art. 145 d.lgs. 209/2005", "art. 145 d.lgs. 209/2005", "Proponibilità dell'azione di risarcimento"),
    _n("dlgs209:148", "art. 148 d.lgs. 209/2005", "art. 148 d.lgs. 209/2005", "Procedura di risarcimento"),
    _n("dlgs209:149", "art. 149 d.lgs. 209/2005", "art. 149 d.lgs. 209/2005", "Procedura di risarcimento diretto"),
    _n("dlgs285:201", "art. 201 d.lgs. 285/1992", "art. 201 d.lgs. 285/1992 (codice della strada)", "Notificazione delle violazioni"),
    _n("dlgs285:204bis", "art. 204-bis d.lgs. 285/1992", "art. 204-bis d.lgs. 285/1992 (codice della strada)", "Ricorso al giudice di pace"),
    _n("dlgs150:7", "art. 7 d.lgs. 150/2011", "art. 7 d.lgs. 150/2011", "Opposizione al verbale di accertamento di violazione del codice della strada"),
    _n("dlgs231:2", "art. 2 d.lgs. 231/2002", "art. 2 d.lgs. 231/2002", "Definizioni"),
    _n("dlgs231:4", "art. 4 d.lgs. 231/2002", "art. 4 d.lgs. 231/2002", "Decorrenza degli interessi moratori"),
    _n("dlgs231:5", "art. 5 d.lgs. 231/2002", "art. 5 d.lgs. 231/2002", "Saggio degli interessi"),
    _n("dlgs231:6", "art. 6 d.lgs. 231/2002", "art. 6 d.lgs. 231/2002", "Risarcimento delle spese di recupero"),
    _n("dpr600:43", "art. 43 d.p.r. 600/1973", "art. 43 d.P.R. 600/1973", "Termine per l'accertamento"),
    _n("dlgs546:18", "art. 18 d.lgs. 546/1992", "art. 18 d.lgs. 546/1992", "Il ricorso"),
    _n("dlgs546:22", "art. 22 d.lgs. 546/1992", "art. 22 d.lgs. 546/1992", "Costituzione in giudizio del ricorrente"),
    _n("l241:21nonies", "art. 21-nonies l. 241/1990", "art. 21-nonies l. 241/1990", "Annullamento d'ufficio"),
    _n("dlgs206:33", "art. 33 d.lgs. 206/2005", "art. 33 d.lgs. 206/2005 (codice del consumo)", "Clausole vessatorie nel contratto tra professionista e consumatore"),
    _n("dlgs206:128", "art. 128 d.lgs. 206/2005", "art. 128 d.lgs. 206/2005 (codice del consumo)", "Ambito di applicazione e definizioni"),
    _n("dlgs206:133", "art. 133 d.lgs. 206/2005", "art. 133 d.lgs. 206/2005 (codice del consumo)", "Termini"),
    _n("dlgs206:135bis", "art. 135-bis d.lgs. 206/2005", "art. 135-bis d.lgs. 206/2005 (codice del consumo)", "Rimedi per il difetto di conformità"),
    _n("dpr1199:9", "art. 9 d.p.r. 1199/1971", "art. 9 d.P.R. 1199/1971", "Termine del ricorso straordinario"),
    _n("dpr115:30", "art. 30 d.p.r. 115/2002", "art. 30 d.P.R. 115/2002", "Anticipazione forfettaria"),
    _n("dpr115:13", "art. 13 d.p.r. 115/2002", "art. 13 d.P.R. 115/2002", "Contributo unificato"),
)}


def normalizza(testo: str) -> str:
    """Confronto robusto: minuscole, senza accenti né apostrofi tipografici, spazi singoli."""
    base = unicodedata.normalize("NFKD", str(testo or "").replace("’", "'").replace("`", "'").lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    # Normattiva scrive gli accenti finali con l'apostrofo («e'», «puo'»): l'apostrofo non conta nel confronto.
    return " ".join(base.replace("'", "").split())


def piano(testo: str) -> str:
    """Per riconoscere domande e fatti: come ``normalizza`` ma l'apostrofo separa le parole («l'art.» → «l art.»)."""
    return normalizza(str(testo or "").replace("'", " ").replace("’", " "))


@dataclass(frozen=True)
class TestoNorma:
    chiave: str
    citazione: str
    testo: str
    url: str
    aggiornamento: str    # data dell'aggiornamento Normattiva dell'archivio (gg/mm/aaaa), se nota
    vigente: bool
    origine: str          # «istantanea dell'archivio» | «archivio dal vivo»


@lru_cache(maxsize=1)
def _istantanea() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(ISTANTANEA.read_text(encoding="utf-8")).get("norme", {})
    except (OSError, ValueError):
        return {}


def _archivio_dal_vivo(norma: Norma) -> dict[str, Any] | None:
    percorso = os.environ.get("PCT_NORMATTIVA_DB", "")
    if not percorso or os.environ.get("LEX_HARNESS_ARCHIVIO_VIVO", "1") == "0":
        return None
    try:
        from web.services.ricerca_legale_norma_citata import estremi, norma_citata

        e = estremi(norma.estremi)
        scheda = norma_citata(Path(percorso), e) if e else None
    except Exception:
        return None
    if not scheda or not scheda.get("normaCitata"):
        return None
    return leggi_scheda(scheda)


def leggi_scheda(scheda: dict[str, Any]) -> dict[str, Any]:
    """Dalla scheda di ``norma_citata`` ai campi conservati nell'istantanea."""
    avvisi = " ".join(scheda.get("operationalChecks") or [])
    agg = re.search(r"aggiornamento del (\d{2}/\d{2}/\d{4})", avvisi)
    testo = str(scheda.get("officialContext") or "")
    return {"testo": testo, "url": str(scheda.get("sourceHref") or ""), "titolo": str(scheda.get("title") or ""),
            "aggiornamento": agg.group(1) if agg else "", "vigente": scheda.get("approvalTone") == "success",
            "sha256": hashlib.sha256(testo.encode()).hexdigest()}


_CACHE_VIVO: dict[str, dict[str, Any] | None] = {}


def testo_norma(chiave: str) -> TestoNorma | None:
    norma = NORME.get(chiave)
    if norma is None:
        return None
    riga = _istantanea().get(chiave)
    origine = "istantanea dell'archivio"
    if not riga or not riga.get("testo"):
        if chiave not in _CACHE_VIVO:
            _CACHE_VIVO[chiave] = _archivio_dal_vivo(norma)
        riga, origine = _CACHE_VIVO[chiave], "archivio dal vivo"
    if not riga or not riga.get("testo"):
        return None
    return TestoNorma(chiave, norma.citazione, str(riga["testo"]), str(riga.get("url") or ""),
                      str(riga.get("aggiornamento") or ""), bool(riga.get("vigente")), origine)


def contiene(chiave: str, ancora: str) -> bool:
    """L'ancora compare nel testo vigente dell'articolo? (spazi, accenti e apostrofi normalizzati)."""
    t = testo_norma(chiave)
    return bool(t and ancora and normalizza(ancora) in normalizza(t.testo))


_NUMERI = {"cinquemila": 5000, "diecimila": 10000, "quindicimila": 15000, "ventimila": 20000,
           "venticinquemila": 25000, "trentamila": 30000, "cinquantamila": 50000, "centomila": 100000}


def importo_in_lettere_dopo(chiave: str, prefisso: str) -> int | None:
    """Legge dal testo vigente un importo scritto in lettere dopo le parole indicate («non superiore a diecimila euro»)."""
    t = testo_norma(chiave)
    if t is None:
        return None
    m = re.search(re.escape(normalizza(prefisso)) + r"\s+(?:a\s+)?(?:euro\s+)?([a-z]+)\s+euro", normalizza(t.testo))
    if m and m.group(1) in _NUMERI:
        return _NUMERI[m.group(1)]
    m = re.search(re.escape(normalizza(prefisso)) + r"\s+(?:a\s+)?(?:euro\s+)?(\d{1,3}(?:\.\d{3})+|\d+)", normalizza(t.testo))
    return int(m.group(1).replace(".", "")) if m else None


def comma_con(chiave: str, ancora: str, *, massimo: int = 600) -> str:
    """Il periodo del testo vigente che contiene l'ancora, per riportarlo fra virgolette."""
    t = testo_norma(chiave)
    if t is None:
        return ""
    piano = " ".join(t.testo.split())
    pos = normalizza(piano).find(normalizza(ancora))
    if pos < 0:
        return ""
    inizio = max(piano.rfind(". ", 0, pos), piano.rfind("; ", 0, pos), piano.rfind(": ", 0, pos))
    inizio = 0 if inizio < 0 else inizio + 2
    fine = piano.find(".", pos + len(ancora))
    fine = len(piano) if fine < 0 else fine + 1
    estratto = piano[inizio:fine].strip()
    return estratto if len(estratto) <= massimo else estratto[: massimo - 1].rstrip() + "…"


def contiene_nel_comma(chiave: str, comma: str, ancora: str) -> tuple[bool, bool]:
    """(ancora trovata, comma individuato). Se il testo ha i commi numerati («1.», «2.») l'ancora deve stare nel comma
    indicato; se i commi non sono numerati (codici con capoversi) si controlla l'articolo e lo si dichiara."""
    t = testo_norma(chiave)
    if t is None or not ancora:
        return False, False
    try:
        from web.services.ricerca_legale_norma_citata import testo_del_comma

        parte = testo_del_comma(" ".join(t.testo.split()), comma) if comma else ""
    except Exception:
        parte = ""
    if parte:
        return normalizza(ancora) in normalizza(parte), True
    return normalizza(ancora) in normalizza(t.testo), False
