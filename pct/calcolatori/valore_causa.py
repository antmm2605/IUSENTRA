"""Valore della causa ai fini della competenza — artt. 10-17 c.p.c.

Il valore della causa non è «quanto chiedo»: è il risultato di regole precise
che cambiano con l'oggetto della domanda. Sbagliarlo significa sbagliare il
giudice competente e lo scaglione del contributo unificato, e l'errore emerge
quando è tardi.

Base normativa (testi verificati su Normattiva):

- **Art. 10 c.p.c.**: il valore si determina dalla domanda; le domande proposte
  nello stesso processo contro la medesima persona si sommano tra loro, e gli
  interessi scaduti, le spese e i danni anteriori alla proposizione si sommano
  col capitale.
- **Art. 11 c.p.c.**: se è chiesto l'adempimento per quote di un'obbligazione,
  il valore si determina dall'intera obbligazione.
- **Art. 12 c.p.c.**: nelle cause sull'esistenza, validità o risoluzione di un
  rapporto obbligatorio il valore è quello della parte del rapporto in
  contestazione; nelle cause di divisione, il valore della massa attiva.
- **Art. 13 c.p.c.**: prestazioni alimentari periodiche con titolo controverso,
  due annualità; rendite perpetue, venti annualità; rendite temporanee o
  vitalizie, le annualità domandate fino a un massimo di dieci.
- **Art. 14 c.p.c.**: nelle cause relative a somme di danaro o a beni mobili il
  valore è quello indicato o dichiarato dall'attore.
- **Art. 15 c.p.c.**: il valore delle cause su beni immobili si determina
  moltiplicando il reddito dominicale del terreno e la rendita catastale del
  fabbricato alla data della proposizione della domanda: per duecento per la
  proprietà; per cento per usufrutto, uso, abitazione, nuda proprietà e diritto
  dell'enfiteuta; per cinquanta, con riferimento al fondo servente, per le
  servitù. Se la rendita non risulta, la causa è di valore indeterminabile
  quando gli atti non offrono elementi per la stima.
- **Art. 17 c.p.c.**: opposizione all'esecuzione, dal credito per cui si
  procede; opposizione di terzo ex art. 619 c.p.c., dal valore dei beni
  controversi; controversie in sede di distribuzione, dal maggiore dei crediti
  contestati.

Perimetro dichiarato: il modulo calcola il valore secondo la regola scelta e le
addizioni dell'art. 10, secondo comma. Non decide la competenza per materia né
quella funzionale, che prevalgono sul valore, e non sostituisce la valutazione
sul petitum quando la domanda cumula titoli eterogenei.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, fmt_eur, safe_float, safe_int

# Moltiplicatori dell'art. 15, primo comma, c.p.c. sulla rendita catastale o sul
# reddito dominicale, per tipo di diritto fatto valere.
MOLTIPLICATORI_IMMOBILE: Dict[str, Dict[str, Any]] = {
    "proprieta": {"label": "Proprietà", "moltiplicatore": 200},
    "usufrutto": {"label": "Usufrutto, uso, abitazione, nuda proprietà, enfiteusi", "moltiplicatore": 100},
    "servitu": {"label": "Servitù (sul fondo servente)", "moltiplicatore": 50},
}

# Art. 13 c.p.c.: annualità da cumulare per tipo di prestazione periodica.
ANNUALITA_ALIMENTI = 2
ANNUALITA_RENDITA_PERPETUA = 20
ANNUALITA_RENDITA_TEMPORANEA_MAX = 10

CRITERI: Dict[str, Dict[str, str]] = {
    "somma_mobili": {
        "label": "Somma di danaro o beni mobili",
        "norma": "Art. 14 c.p.c.",
        "descrizione": "Valore indicato o dichiarato dall'attore.",
    },
    "quote_obbligazione": {
        "label": "Adempimento per quote di un'obbligazione",
        "norma": "Art. 11 c.p.c.",
        "descrizione": "Il valore si determina dall'intera obbligazione, non dalla quota chiesta.",
    },
    "rapporto_obbligatorio": {
        "label": "Esistenza, validità o risoluzione di un rapporto obbligatorio",
        "norma": "Art. 12, primo comma, c.p.c.",
        "descrizione": "Valore della parte del rapporto in contestazione.",
    },
    "divisione": {
        "label": "Divisione",
        "norma": "Art. 12, terzo comma, c.p.c.",
        "descrizione": "Valore della massa attiva da dividersi.",
    },
    "alimenti": {
        "label": "Prestazioni alimentari periodiche con titolo controverso",
        "norma": "Art. 13, primo comma, c.p.c.",
        "descrizione": "Somme dovute per due anni.",
    },
    "rendita_perpetua": {
        "label": "Rendita perpetua con titolo controverso",
        "norma": "Art. 13, secondo comma, c.p.c.",
        "descrizione": "Cumulo di venti annualità.",
    },
    "rendita_temporanea": {
        "label": "Rendita temporanea o vitalizia",
        "norma": "Art. 13, secondo comma, c.p.c.",
        "descrizione": "Cumulo delle annualità domandate, fino a un massimo di dieci.",
    },
    "immobile": {
        "label": "Causa relativa a beni immobili",
        "norma": "Art. 15, primo comma, c.p.c.",
        "descrizione": "Rendita catastale o reddito dominicale per il moltiplicatore del diritto azionato.",
    },
    "opposizione_esecuzione": {
        "label": "Opposizione all'esecuzione forzata",
        "norma": "Art. 17 c.p.c.",
        "descrizione": "Credito per cui si procede.",
    },
    "opposizione_terzo": {
        "label": "Opposizione di terzo all'esecuzione (art. 619 c.p.c.)",
        "norma": "Art. 17 c.p.c.",
        "descrizione": "Valore dei beni controversi.",
    },
    "distribuzione": {
        "label": "Controversia sorta in sede di distribuzione",
        "norma": "Art. 17 c.p.c.",
        "descrizione": "Valore del maggiore dei crediti contestati.",
    },
}

FONTI: tuple[Dict[str, str], ...] = (
    {
        "title": "Art. 10 c.p.c. — Determinazione del valore",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art10",
    },
    {
        "title": "Artt. 11-15 c.p.c. — Regole speciali di determinazione del valore",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art11",
    },
    {
        "title": "Art. 17 c.p.c. — Cause relative all'esecuzione forzata",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art17",
    },
)


def _base_criterio(criterio: str, payload: Mapping[str, Any]) -> tuple[float, List[Dict[str, Any]], List[str]]:
    """Valore base secondo la regola scelta, con il dettaglio che lo spiega."""
    importo = safe_float(payload.get("val_importo"))
    dettaglio: List[Dict[str, Any]] = []
    note: List[str] = []

    if criterio in {"somma_mobili", "quote_obbligazione", "rapporto_obbligatorio", "divisione",
                    "opposizione_esecuzione", "opposizione_terzo", "distribuzione"}:
        if importo <= 0:
            raise ValueError(f"Indica l'importo su cui si determina il valore ({CRITERI[criterio]['descrizione']}).")
        dettaglio.append({"voce": CRITERI[criterio]["label"], "importo": round(importo, 2), "riferimento": CRITERI[criterio]["norma"]})
        if criterio == "quote_obbligazione":
            note.append(
                "Indica l'intera obbligazione, non la quota domandata: l'art. 11 c.p.c. determina "
                "il valore dall'obbligazione nel suo complesso."
            )
        return importo, dettaglio, note

    if criterio in {"alimenti", "rendita_perpetua", "rendita_temporanea"}:
        annualita = safe_float(payload.get("val_importo"))
        if annualita <= 0:
            raise ValueError("Indica l'importo di una annualità della prestazione periodica.")
        if criterio == "alimenti":
            numero = ANNUALITA_ALIMENTI
        elif criterio == "rendita_perpetua":
            numero = ANNUALITA_RENDITA_PERPETUA
        else:
            richieste = safe_int(payload.get("val_annualita"), 0)
            if richieste <= 0:
                raise ValueError("Indica quante annualità sono domandate (art. 13, secondo comma, c.p.c.).")
            numero = min(richieste, ANNUALITA_RENDITA_TEMPORANEA_MAX)
            if richieste > ANNUALITA_RENDITA_TEMPORANEA_MAX:
                note.append(
                    f"Annualità domandate: {richieste}. L'art. 13, secondo comma, c.p.c. le cumula "
                    f"fino a un massimo di {ANNUALITA_RENDITA_TEMPORANEA_MAX}."
                )
        valore = annualita * numero
        dettaglio.append(
            {
                "voce": f"{CRITERI[criterio]['label']}: {numero} annualità da {fmt_eur(annualita)} €",
                "importo": round(valore, 2),
                "riferimento": CRITERI[criterio]["norma"],
            }
        )
        return valore, dettaglio, note

    if criterio == "immobile":
        diritto = clean_text(payload.get("val_diritto")).lower() or "proprieta"
        if diritto not in MOLTIPLICATORI_IMMOBILE:
            raise ValueError("Diritto sull'immobile non riconosciuto.")
        rendita = safe_float(payload.get("val_importo"))
        if rendita <= 0:
            raise ValueError(
                "Indica la rendita catastale del fabbricato o il reddito dominicale del terreno "
                "alla data della proposizione della domanda. Se non risulta e gli atti non offrono "
                "elementi per la stima, la causa è di valore indeterminabile (art. 15, terzo comma, c.p.c.)."
            )
        moltiplicatore = MOLTIPLICATORI_IMMOBILE[diritto]["moltiplicatore"]
        valore = rendita * moltiplicatore
        dettaglio.append(
            {
                "voce": f"{MOLTIPLICATORI_IMMOBILE[diritto]['label']}: rendita × {moltiplicatore}",
                "importo": round(valore, 2),
                "riferimento": "Art. 15, primo comma, c.p.c.",
            }
        )
        note.append(
            "L'art. 15 c.p.c. usa la rendita catastale e il reddito dominicale non rivalutati: la "
            "rivalutazione dell'art. 3, comma 48, L. 662/1996 vale ai fini fiscali, non per la "
            "competenza."
        )
        return valore, dettaglio, note

    raise ValueError("Criterio di determinazione del valore non riconosciuto.")


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    criterio = clean_text(payload.get("val_criterio")).lower() or "somma_mobili"
    if criterio not in CRITERI:
        raise ValueError("Criterio di determinazione del valore non riconosciuto.")

    valore, dettaglio, note = _base_criterio(criterio, payload)

    # Art. 10, secondo comma, c.p.c.: le altre domande contro la medesima
    # persona e gli accessori anteriori alla proposizione si sommano al capitale.
    altre_domande = safe_float(payload.get("val_altre_domande"))
    interessi_scaduti = safe_float(payload.get("val_interessi_scaduti"))
    spese_danni = safe_float(payload.get("val_spese_danni"))
    for etichetta, importo in (
        ("Altre domande contro la medesima persona nello stesso processo", altre_domande),
        ("Interessi scaduti anteriori alla proposizione", interessi_scaduti),
        ("Spese e danni anteriori alla proposizione", spese_danni),
    ):
        if importo > 0:
            valore += importo
            dettaglio.append({"voce": etichetta, "importo": round(importo, 2), "riferimento": "Art. 10, secondo comma, c.p.c."})

    if altre_domande > 0 or interessi_scaduti > 0 or spese_danni > 0:
        note.append(
            "Sommati al capitale, ai sensi dell'art. 10, secondo comma, c.p.c., le altre domande "
            "contro la medesima persona e gli accessori maturati prima della proposizione."
        )
    note.append(
        "Gli interessi e i danni maturati dopo la proposizione della domanda non entrano nel "
        "valore: l'art. 10, secondo comma, c.p.c. somma soltanto quelli anteriori."
    )

    avvisi = [
        "Il valore così determinato vale ai fini della competenza e, di regola, come base dello "
        "scaglione del contributo unificato: le due grandezze vanno comunque riscontrate sulla "
        "domanda effettivamente proposta.",
        "La competenza per materia e quella funzionale prevalgono sul valore: il modulo non le "
        "valuta.",
        "Quando la domanda cumula titoli eterogenei, la regola applicabile va scelta sul petitum "
        "prevalente: qui è applicata quella indicata dall'utente.",
    ]
    if criterio == "somma_mobili":
        avvisi.append(
            "Art. 14 c.p.c.: il convenuto può contestare il valore dichiarato, ma soltanto nella "
            "prima difesa; in mancanza di contestazione il valore resta fissato nei limiti della "
            "competenza del giudice adito."
        )

    return {
        "criterio": criterio,
        "criterio_label": CRITERI[criterio]["label"],
        "riferimento_normativo": CRITERI[criterio]["norma"],
        "regola": CRITERI[criterio]["descrizione"],
        "valore": round(valore, 2),
        "valore_indeterminabile": False,
        "dettaglio": dettaglio,
        "notes": note,
        "warnings": avvisi,
        "sources": list(FONTI),
    }
