"""Mantenimento dei figli: bilancio del fabbisogno e riparto proporzionale di base (stima motivata).

Base normativa: art. 337-ter, comma 4, c.c. — ciascun genitore provvede al mantenimento dei figli in
misura proporzionale al proprio reddito; l'assegno periodico si determina considerando le attuali
esigenze del figlio, il tenore di vita goduto in costanza di convivenza, i tempi di permanenza presso
ciascun genitore, le risorse economiche di entrambi e la valenza economica dei compiti domestici e di
cura assunti da ciascun genitore. La norma non assegna coefficienti numerici a questi fattori.

Metodo (modello tecnico di stima, non formula di legge), versione 2026.10:
    quota A = reddito netto A / (reddito netto A + reddito netto B)
    contributo teorico A = fabbisogno ordinario × quota A
    trasferimento di base da A a B = contributo teorico A − spese ordinarie del bilancio sostenute da A
Il fabbisogno nasce dal bilancio per voci scritto dall'avvocato (importo singolo o intervallo); la
fascia è la sensibilità alle ipotesi inserite, non una probabilità di liquidazione. Le spese
straordinarie restano fuori dal trasferimento; l'assegno unico si registra a parte e non entra nel
fabbisogno. Gli altri criteri dell'art. 337-ter vanno valutati per iscritto: finché manca una
valutazione la stima resta «da verificare».
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from pct.calcolatori._base import clean_text, safe_bool, safe_float
from pct.calcolatori.stime.scheda import SchedaDiCalcolo, importo_o_intervallo, righe_testo

METODO = "Bilancio del fabbisogno e riparto proporzionale ai redditi (art. 337-ter c.c.)"
VERSIONE = "2026.10"
FONTI = [
    {"title": "Art. 337-ter c.c. (Normattiva)", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art337ter"},
]
# I criteri dell'art. 337-ter, comma 4, diversi dai redditi: vanno valutati per iscritto.
VALUTAZIONI = (
    ("mf_val_permanenza", "Tempi di permanenza presso ciascun genitore"),
    ("mf_val_abitazione", "Situazione abitativa (casa familiare, locazioni, mutui)"),
    ("mf_val_cura", "Compiti domestici e di cura assunti da ciascun genitore"),
    ("mf_val_esigenze", "Esigenze attuali e specifiche del figlio"),
    ("mf_val_tenore", "Tenore di vita goduto in costanza di convivenza"),
)
_PAGANTI = {"a": "A", "b": "B", "entrambi": "entrambi", "ab": "entrambi", "a+b": "entrambi"}


def _voci(testo: Any) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Righe «descrizione; importo o intervallo; ordinaria|straordinaria; A|B|entrambi; documento»."""
    voci: List[Dict[str, Any]] = []
    scartate: List[str] = []
    ipotesi: List[str] = []
    for descrizione, importo, natura, pagante, documento in righe_testo(testo, 5):
        intervallo = importo_o_intervallo(importo)
        if not descrizione or intervallo is None:
            scartate.append(f"«{descrizione or importo}»: importo non leggibile")
            continue
        natura_norm = "straordinaria" if natura.lower().startswith("straord") else "ordinaria"
        if not natura:
            ipotesi.append(f"«{descrizione}» considerata spesa ordinaria (natura non indicata).")
        chi = _PAGANTI.get(pagante.lower().replace(" ", ""), "")
        if not chi:
            chi = "B"
            ipotesi.append(f"«{descrizione}»: chi la sostiene non è indicato, attribuita a B.")
        voci.append({
            "voce": descrizione, "minimo": intervallo[0], "massimo": intervallo[1], "natura": natura_norm,
            "sostenuta_da": chi, "documento": documento or "non indicato",
        })
    return voci, scartate, ipotesi


def _trasferimento(fabbisogno: float, quota_a: float, spese_a: float) -> float:
    return round(fabbisogno * quota_a - spese_a, 2)


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    reddito_a = safe_float(payload.get("mf_reddito_a"))
    reddito_b = safe_float(payload.get("mf_reddito_b"))
    voci, scartate, ipotesi = _voci(payload.get("mf_voci"))
    scheda = SchedaDiCalcolo(
        metodo=METODO, versione=VERSIONE, fonti=list(FONTI),
        validata=safe_bool(payload.get("mf_validata")),
        motivazione_avvocato=clean_text(payload.get("mf_motivazione")),
        dati={"reddito_netto_mensile_A": round(reddito_a, 2), "reddito_netto_mensile_B": round(reddito_b, 2)},
        ipotesi=list(ipotesi),
    )
    for campo, etichetta in VALUTAZIONI:
        testo = clean_text(payload.get(campo))
        scheda.valutazioni.append({"criterio": etichetta, "valutazione": testo or "da valutare"})
        if not testo:
            scheda.mancanti.append(f"Valutazione: {etichetta.lower()}")
    patrimonio = clean_text(payload.get("mf_patrimonio"))
    if patrimonio:
        scheda.valutazioni.append({"criterio": "Patrimonio e disponibilità abitative", "valutazione": patrimonio})
    assegno_unico = safe_float(payload.get("mf_assegno_unico"))
    if assegno_unico > 0:
        percettore = clean_text(payload.get("mf_assegno_unico_percettore")) or "non indicato"
        scheda.dati["assegno_unico_mensile"] = {"importo": round(assegno_unico, 2), "percepito_da": percettore}

    ordinarie = [v for v in voci if v["natura"] == "ordinaria"]
    straordinarie = [v for v in voci if v["natura"] == "straordinaria"]
    calcolabile = reddito_a > 0 and reddito_b >= 0 and (reddito_a + reddito_b) > 0 and bool(ordinarie)
    if reddito_a <= 0:
        scheda.mancanti.append("Reddito netto mensile del genitore A")
    if not ordinarie:
        scheda.mancanti.append("Bilancio delle spese ordinarie del figlio")

    risultato: Dict[str, Any] = {"percorso": "figli", "label": "Mantenimento dei figli (stima motivata)"}
    righe_voci = [
        {
            "voce": v["voce"], "importo": v["minimo"] if v["minimo"] == v["massimo"] else f"{v['minimo']:.2f}-{v['massimo']:.2f}",
            "natura": v["natura"], "sostenuta_da": v["sostenuta_da"], "documento": v["documento"],
        }
        for v in voci
    ]
    note = [
        "I risultati derivano dal modello e dalle ipotesi inserite: non sono «quanto stabilisce la legge».",
        "La sottrazione delle spese già sostenute da A è una riconciliazione interna del bilancio: non autorizza a "
        "decurtare un assegno già stabilito.",
        "Le spese straordinarie restano fuori dal trasferimento e si ripartiscono secondo il provvedimento o "
        "l'accordo; la quota proporzionale indicata è solo il riferimento del modello.",
    ]
    avvisi: List[str] = []
    if scartate:
        avvisi.append("Righe del bilancio non usate: " + "; ".join(scartate) + ".")
    if assegno_unico > 0:
        note.append("L'assegno unico è registrato a parte e non è sommato al fabbisogno, per non contarlo due volte.")
    if calcolabile:
        quota_a = reddito_a / (reddito_a + reddito_b)

        def spese_a(chiave: str) -> float:
            totale = 0.0
            for v in ordinarie:
                if v["sostenuta_da"] == "A":
                    totale += v[chiave]
                elif v["sostenuta_da"] == "entrambi":
                    totale += v[chiave] / 2
            return totale

        if any(v["sostenuta_da"] == "entrambi" for v in ordinarie):
            scheda.ipotesi.append("Le voci sostenute da entrambi sono divise a metà fra A e B.")
        fabbisogno_min = sum(v["minimo"] for v in ordinarie)
        fabbisogno_max = sum(v["massimo"] for v in ordinarie)
        # Fascia: stesso dato, ipotesi estreme del bilancio (le spese di A seguono la stessa ipotesi).
        base_min = _trasferimento(fabbisogno_min, quota_a, spese_a("minimo"))
        base_max = _trasferimento(fabbisogno_max, quota_a, spese_a("massimo"))
        fabbisogno_medio = round((fabbisogno_min + fabbisogno_max) / 2, 2)
        base = round((base_min + base_max) / 2, 2)
        direzione = "da A a B" if base >= 0 else "da B ad A"
        risultato.update({
            "quota_reddituale_A_percentuale": round(quota_a * 100, 2),
            "fabbisogno_ordinario_mensile": fabbisogno_medio,
            "contributo_teorico_A": round(fabbisogno_medio * quota_a, 2),
            "spese_ordinarie_sostenute_da_A": round((spese_a("minimo") + spese_a("massimo")) / 2, 2),
            "trasferimento_di_base_mensile": abs(base),
            "direzione_trasferimento": direzione,
            "fascia_di_sensibilita": {
                "da": min(abs(base_min), abs(base_max)), "a": max(abs(base_min), abs(base_max)),
                "spiegazione": "variazione delle sole ipotesi del bilancio (importi a intervallo), non probabilità di liquidazione",
            } if fabbisogno_min != fabbisogno_max else None,
            "spese_straordinarie_mensili": round(sum((v["minimo"] + v["massimo"]) / 2 for v in straordinarie), 2),
            "quota_proporzionale_straordinarie_A_percentuale": round(quota_a * 100, 2),
        })
        if base < 0:
            avvisi.append("Con il bilancio inserito A sostiene già più della propria quota: il trasferimento va da B ad A.")
    if scheda.mancanti and calcolabile:
        avvisi.append("Proposta non completa: mancano " + ", ".join(m.lower() for m in scheda.mancanti) + ".")
    risultato.update(scheda.to_dict(calcolabile=calcolabile))
    risultato["bilancio"] = righe_voci
    risultato["notes"] = note
    risultato["warnings"] = avvisi + risultato.pop("avvisi_validazione")
    risultato["sources"] = list(FONTI)
    return risultato


__all__ = ["METODO", "VERSIONE", "VALUTAZIONI", "calcola"]
