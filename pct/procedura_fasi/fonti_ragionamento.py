"""Norme del motore del ragionamento processuale (pct/ragionamento) che completano il registro ``fonti.py``.

Testo vigente dall'archivio Normattiva del software, letto il 10/11/2026: artt. 91, 93, 127-ter (testo completo),
324, 415 commi 4–6, 474, 641 terzo comma c.p.c.; artt. 2697 e 2909 c.c.; art. 13 D.P.R. 115/2002 (gli artt. 631 c.p.c. e
30 D.P.R. 115/2002 erano già nel registro).
Il registro le carica una volta sola all'import di ``fonti.py``: nessun modulo lo modifica dopo, così ogni vista
cita le stesse voci in qualunque processo.
"""

from __future__ import annotations

from typing import Any

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
_CC = "urn:nir:stato:regio.decreto:1942-03-16;262"
_DPR115 = "urn:nir:presidente.repubblica:decreto:2002-05-30;115"
_LETTA = "testo vigente nell'archivio Normattiva del software, letto il 10/11/2026"


def _voce(norma: str, titolo: str, atto: str, art: str, estratto: str) -> dict[str, Any]:
    return {"norma": norma, "titolo": titolo, "url": f"{_NORMATTIVA}{atto}~art{art}", "verifica": _LETTA, "estratto": estratto}


FONTI_RAGIONAMENTO: dict[str, dict[str, Any]] = {
    "cpc_324": _voce("art. 324 c.p.c.", "Cosa giudicata formale", _CPC, "324",
        "S'intende passata in giudicato la sentenza che non è più soggetta né a regolamento di competenza, né ad appello, né a "
        "ricorso per cassazione, né a revocazione per i motivi di cui ai numeri 4 e 5 dell'articolo 395."),
    "cc_2909": _voce("art. 2909 c.c.", "Cosa giudicata", _CC, "2909",
        "L'accertamento contenuto nella sentenza passata in giudicato fa stato a ogni effetto tra le parti, i loro eredi o "
        "aventi causa."),
    "cc_2697": _voce("art. 2697 c.c.", "Onere della prova", _CC, "2697",
        "Chi vuol far valere un diritto in giudizio deve provare i fatti che ne costituiscono il fondamento. Chi eccepisce che il "
        "diritto si è modificato o estinto deve provare i fatti su cui l'eccezione si fonda."),
    "cpc_474": _voce("art. 474 c.p.c.", "Titolo esecutivo", _CPC, "474",
        "L'esecuzione forzata non può avere luogo che in virtù di un titolo esecutivo per un diritto certo, liquido ed esigibile. "
        "Sono titoli esecutivi le sentenze, i provvedimenti e gli altri atti ai quali la legge attribuisce espressamente "
        "efficacia esecutiva."),
    "cpc_475": {
        **_voce("art. 475 c.p.c.", "Forma del titolo esecutivo", _CPC, "475",
            "Salvo diversa previsione, il titolo è rilasciato in copia attestata conforme all’originale o in duplicato informatico."),
        "verifica": "Testo confrontato con il D.Lgs. 164/2024 in Gazzetta Ufficiale il 14/11/2026.",
    },
    "cpc_415_notifica": {
        **_voce("art. 415, commi 4–6, c.p.c.", "Rito del lavoro: notifica del ricorso e del decreto", _CPC, "415",
            "Salvo l'art. 417, l'attore notifica ricorso e decreto entro dieci giorni dalla pronuncia del decreto. "
            "Dalla notifica all'udienza devono intercorrere almeno 30 giorni. Dal deposito del ricorso all'udienza "
            "possono trascorrere al massimo 60 giorni (comma 3). Per la notifica all'estero i due intervalli "
            "diventano rispettivamente almeno 40 e al massimo 80 giorni (comma 6)."),
        "verifica": "Testo confrontato con la Gazzetta Ufficiale n. 264 dell’11/11/2024 il 14/11/2026.",
    },
    "cpc_127ter_testo": _voce("art. 127-ter c.p.c.", "Deposito di note scritte in sostituzione dell'udienza", _CPC, "127ter",
        "Con il provvedimento con cui sostituisce l'udienza il giudice assegna un termine perentorio non inferiore a quindici "
        "giorni per il deposito delle note. Se nessuna delle parti deposita le note nel termine assegnato il giudice assegna un "
        "nuovo termine perentorio o fissa udienza; se nessuna deposita nel nuovo termine, ordina la cancellazione della causa "
        "dal ruolo e dichiara l'estinzione del processo. Il giorno di scadenza del termine assegnato per il deposito delle note "
        "è considerato data di udienza a tutti gli effetti."),
    "dpr115_art13": _voce("art. 13 D.P.R. 115/2002", "Contributo unificato: importi", _DPR115, "13",
        "Euro 43 fino a 1.100 euro e per previdenza e assistenza obbligatorie; euro 98 oltre 1.100 e fino a 5.200 euro e per i "
        "processi di volontaria giurisdizione; euro 237 fino a 26.000; euro 518 fino a 52.000 e per i processi di valore "
        "indeterminabile; euro 759 fino a 260.000; euro 1.214 fino a 520.000; euro 1.686 oltre. Esecuzione immobiliare euro 278, "
        "altri processi esecutivi la metà (139), esecuzione mobiliare sotto 2.500 euro euro 43, opposizione agli atti esecutivi "
        "euro 168 (comma 2). Metà per i processi speciali del libro IV, titolo I, c.p.c. e per le controversie di lavoro "
        "(comma 3); aumento della metà per le impugnazioni (comma 1-bis)."),
    "cpc_91": _voce("art. 91 c.p.c.", "Condanna alle spese", _CPC, "91",
        "Il giudice, con la sentenza che chiude il processo davanti a lui, condanna la parte soccombente al rimborso delle "
        "spese a favore dell'altra parte e ne liquida l'ammontare insieme con gli onorari di difesa."),
    "cpc_93": _voce("art. 93 c.p.c.", "Distrazione delle spese", _CPC, "93",
        "Il difensore con procura può chiedere che il giudice, nella stessa sentenza in cui condanna alle spese, distragga in "
        "favore suo gli onorari non riscossi e le spese che dichiara di avere anticipate."),
    "cpc_641_spese": _voce("art. 641, terzo comma, c.p.c.", "Decreto ingiuntivo: liquidazione delle spese", _CPC, "641",
        "Con lo stesso decreto il giudice liquida le spese e le competenze e ne ingiunge il pagamento."),
    # Aggiunte del 18/11/2026: testo vigente nell'archivio Normattiva del software (c.p.c. aggiornato al 05/03/2026,
    # D.P.R. 115/2002 al 12/11/2026), letto il 18/11/2026.
    "cpc_154": {**_voce("art. 154 c.p.c.", "Prorogabilità del termine ordinatorio", _CPC, "154",
        "Il giudice, prima della scadenza, può abbreviare o prorogare, anche d'ufficio, il termine che non sia stabilito a pena "
        "di decadenza. La proroga non può avere una durata superiore al termine originario. Non può essere consentita proroga "
        "ulteriore, se non per motivi particolarmente gravi e con provvedimento motivato."),
        "verifica": "testo vigente nell'archivio Normattiva del software, letto il 18/11/2026"},
    "dpr115_art16": {**_voce("art. 16 D.P.R. 115/2002", "Omesso o insufficiente pagamento del contributo unificato", _DPR115, "16",
        "In caso di omesso o insufficiente pagamento del contributo unificato si applicano le disposizioni della parte VII, "
        "titolo VII, e nell'importo iscritto a ruolo sono calcolati gli interessi al saggio legale, decorrenti dal deposito "
        "dell'atto cui si collega il pagamento o l'integrazione del contributo (comma 1). In caso di omesso o parziale "
        "pagamento si applica la sanzione dell'art. 71 del D.P.R. 131/1986 (comma 1-bis)."),
        "verifica": "testo vigente nell'archivio Normattiva del software, letto il 18/11/2026"},
    "dpr115_art248": {**_voce("art. 248 D.P.R. 115/2002", "Invito al pagamento del contributo unificato", _DPR115, "248",
        "Entro trenta giorni dal deposito dell'atto cui si collega il pagamento o l'integrazione del contributo, l'ufficio "
        "notifica alla parte l'invito al pagamento dell'importo dovuto, con l'avvertenza che in caso di mancato pagamento "
        "entro un mese si procederà a iscrizione a ruolo con interessi e sanzione (comma 1). Nei procedimenti civili, in caso "
        "di mancato pagamento entro trenta giorni dall'iscrizione a ruolo, l'ufficio procede all'iscrizione a ruolo "
        "dell'importo dovuto con interessi e sanzione (comma 3-bis)."),
        "verifica": "testo vigente nell'archivio Normattiva del software, letto il 18/11/2026"},
    "dpr115_art10": {**_voce("art. 10 D.P.R. 115/2002", "Esenzioni dal contributo unificato", _DPR115, "10",
        "Non è soggetto al contributo unificato il processo già esente, secondo previsione legislativa, dall'imposta di bollo o "
        "da ogni spesa, tassa o diritto (comma 1). Non è soggetto al contributo il processo in materia di assegni per il "
        "mantenimento della prole e quello comunque riguardante la stessa (comma 2). Non sono soggetti al contributo i processi "
        "di cui al libro II, titolo IV-bis, capo III, sezioni III, IV e V, del codice di procedura civile (comma 3). La ragione "
        "dell'esenzione deve risultare da apposita dichiarazione resa dalla parte nelle conclusioni dell'atto introduttivo "
        "(comma 6)."),
        "verifica": "testo vigente nell'archivio Normattiva del software (aggiornamento del 12/11/2026), letto il 18/11/2026"},
    "dispattcc_46bis": {**_voce("art. 46-bis disp. att. c.c.", "Misure di protezione: esenzione dal contributo unificato",
        "urn:nir:stato:regio.decreto:1942-03-30;318", "46bis",
        "Gli atti e i provvedimenti relativi ai procedimenti previsti dal titolo XII del libro primo del codice non sono "
        "soggetti all'obbligo di registrazione e sono esenti dal contributo unificato previsto dall'articolo 9 del D.P.R. "
        "30 maggio 2002, n. 115."),
        "verifica": "testo vigente nell'archivio Normattiva del software, letto il 18/11/2026"},
}

__all__ = ["FONTI_RAGIONAMENTO"]
