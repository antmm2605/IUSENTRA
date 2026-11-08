"""Norme dei rimedi dopo la sentenza secondo giurisdizione e grado (pct/percorso_pratica/rimedi.py).

Estratti letterali del testo vigente letti l'08/11/2026 nell'archivio Normattiva del software (c.p.c. R.D. 1443/1940,
c.p.a. D.Lgs. 104/2010, D.Lgs. 546/1992). Il processo tributario resta regolato dal D.Lgs. 546/1992: il testo unico
D.Lgs. 175/2024 si applica dal 1° gennaio 2027 (art. 131, come modificato). Le voci già presenti nel registro non si ripetono.
"""

from __future__ import annotations

from typing import Any

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
_CPA = "urn:nir:stato:decreto.legislativo:2010-07-02;104"
_D546 = "urn:nir:stato:decreto.legislativo:1992-12-31;546"
_VERIFICA = "testo vigente letto dall'archivio Normattiva del software l'08/11/2026"


def _voce(norma: str, titolo: str, atto: str, art: str, estratto: str) -> dict[str, Any]:
    return {"norma": norma, "titolo": titolo, "url": f"{_NORMATTIVA}{atto}~art{art}", "verifica": _VERIFICA, "estratto": estratto}


FONTI_IMPUGNAZIONI: dict[str, dict[str, Any]] = {
    "cpc_391bis": _voce("art. 391-bis c.p.c.", "Correzione degli errori materiali e revocazione delle sentenze della Corte di cassazione", _CPC, "391bis",
                        "La correzione puo' essere chiesta, e puo' essere rilevata d'ufficio dalla Corte, in qualsiasi tempo. La revocazione "
                        "puo' essere chiesta entro il termine perentorio di sessanta giorni dalla notificazione ovvero di sei mesi dalla "
                        "pubblicazione del provvedimento."),
    "cpa_86": _voce("art. 86 c.p.a.", "Procedimento di correzione", _CPA, "86",
                    "Ove occorra correggere omissioni o errori materiali, la domanda per la correzione deve essere proposta al giudice che "
                    "ha emesso il provvedimento."),
    "cpa_94": _voce("art. 94 c.p.a.", "Deposito delle impugnazioni", _CPA, "94",
                    "Nei giudizi di appello, di revocazione e di opposizione di terzo il ricorso deve essere depositato nella segreteria del "
                    "giudice adito, a pena di decadenza, entro trenta giorni dall'ultima notificazione ai sensi dell'articolo 45."),
    "cpa_100": _voce("art. 100 c.p.a.", "Appellabilita' delle sentenze dei tribunali amministrativi regionali", _CPA, "100",
                     "Avverso le sentenze dei tribunali amministrativi regionali e' ammesso appello al Consiglio di Stato, ferma restando la "
                     "competenza del Consiglio di giustizia amministrativa per la Regione siciliana per gli appelli proposti contro le "
                     "sentenze del Tribunale amministrativo regionale per la Sicilia."),
    "cpa_106": _voce("art. 106 c.p.a.", "Casi di revocazione", _CPA, "106",
                     "Salvo quanto previsto dal comma 3, le sentenze dei tribunali amministrativi regionali e del Consiglio di Stato sono "
                     "impugnabili per revocazione, nei casi e nei modi previsti dagli articoli 395 e 396 del codice di procedura civile. [...] "
                     "3. Contro le sentenze dei tribunali amministrativi regionali la revocazione e' ammessa se i motivi non possono essere "
                     "dedotti con l'appello."),
    "cpa_110": _voce("art. 110 c.p.a.", "Motivi di ricorso", _CPA, "110",
                     "Il ricorso per cassazione e' ammesso contro le sentenze del Consiglio di Stato per i soli motivi inerenti alla giurisdizione."),
    "cpa_119": _voce("art. 119 c.p.a.", "Rito abbreviato comune a determinate materie", _CPA, "119",
                     "2. Tutti i termini processuali ordinari sono dimezzati salvo, nei giudizi di primo grado, quelli per la notificazione "
                     "del ricorso introduttivo, del ricorso incidentale e dei motivi aggiunti, nonche' quelli di cui all'articolo 62, comma 1, "
                     "e quelli espressamente disciplinati nel presente articolo."),
    "dlgs546_38": _voce("art. 38 D.Lgs. 546/1992", "Richiesta di copie e notificazione della sentenza", _D546, "38",
                        "3. Se nessuna delle parti provvede alla notificazione della sentenza, si applica l'art. 327, comma 1, del codice di "
                        "procedura civile."),
    "dlgs546_51": _voce("art. 51 D.Lgs. 546/1992", "Termini d'impugnazione", _D546, "51",
                        "Se la legge non dispone diversamente il termine per impugnare la sentenza della corte di giustizia tributaria di primo "
                        "e secondo grado e' di sessanta giorni, decorrente dalla sua notificazione ad istanza di parte, salvo quanto disposto "
                        "dall'art. 38, comma 3."),
    "dlgs546_52": _voce("art. 52 D.Lgs. 546/1992", "Giudice competente e provvedimenti sull'esecuzione provvisoria in appello", _D546, "52",
                        "La sentenza della corte di giustizia tributaria di primo grado puo' essere appellata alla corte di giustizia "
                        "tributaria di secondo grado competente a norma dell'articolo 4, comma 2."),
    "dlgs546_62": _voce("art. 62 D.Lgs. 546/1992", "Norme applicabili", _D546, "62",
                        "Avverso la sentenza della corte di giustizia tributaria di secondo grado puo' essere proposto ricorso per cassazione "
                        "per i motivi di cui ai numeri da 1 a 5 dell'art. 360, primo comma, del codice di procedura civile."),
    "dlgs546_64": _voce("art. 64 D.Lgs. 546/1992", "Sentenze revocabili e motivi di revocazione", _D546, "64",
                        "Le sentenze pronunciate in grado d'appello o in unico grado dalle corti di giustizia tributaria di primo e secondo "
                        "grado possono essere impugnate ai sensi dell'articolo 395 del codice di procedura civile."),
    "dlgs546_70": _voce("art. 70 D.Lgs. 546/1992", "Giudizio di ottemperanza", _D546, "70",
                        "La parte che vi ha interesse puo' richiedere l'ottemperanza agli obblighi derivanti dalla sentenza della corte di "
                        "giustizia tributaria di primo e secondo grado passata in giudicato mediante ricorso da depositare in doppio originale "
                        "alla segreteria della corte di giustizia tributaria di primo grado, qualora la sentenza passata in giudicato sia stata "
                        "da essa pronunciata, e in ogni altro caso alla segreteria della corte di giustizia tributaria di secondo grado."),
}

__all__ = ["FONTI_IMPUGNAZIONI"]
