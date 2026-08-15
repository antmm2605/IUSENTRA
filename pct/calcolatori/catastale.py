"""Valore catastale, IMU e catalogo delle categorie catastali.

Base normativa:
- Valore catastale (art. 52, cc. 4-5, D.P.R. 131/1986; art. 34, c. 5,
  D.Lgs. 346/1990 per successioni e donazioni): rendita rivalutata del 5%
  (art. 3, c. 48, L. 662/1996) per il moltiplicatore. Catena delle
  rivalutazioni dei moltiplicatori: art. 2, c. 63, L. 350/2003 (+10%,
  tutti gli immobili); art. 1-bis, c. 7, D.L. 168/2004 (+20% complessivo
  per gli immobili diversi dalla prima casa); art. 2, c. 45, D.L.
  262/2006 (gruppo B +40%, ai soli fini di registro e ipocatastali):
  * 110 abitazione «prima casa»; 120 gruppi A e C (escl. A/10 e C/1);
  * gruppo B: 168 per registro/ipocatastali su atti a titolo oneroso,
    140 per successioni e donazioni (la rivalutazione del 40% ex D.L.
    262/2006 non opera sull'imposta di successione);
  * 60 A/10 e gruppo D; 40,8 C/1 e gruppo E.
- Dall'art. 35, c. 23-ter, D.L. 223/2006 la valutazione automatica ai
  fini del registro opera solo nelle cessioni col prezzo-valore
  (abitazioni a persone fisiche): per gli immobili non abitativi il
  valore catastale non preclude l'accertamento di maggior valore, ma
  resta pienamente rilevante per successioni e donazioni.
- IMU (art. 1, commi 739-783, L. 160/2019): base imponibile = rendita
  rivalutata 5% × moltiplicatore (art. 1, c. 745): 160 gruppo A (escl.
  A/10) e C/2, C/6, C/7; 140 gruppo B e C/3, C/4, C/5; 80 A/10 e D/5;
  65 gruppo D (escl. D/5); 55 C/1. Aliquota deliberata dal Comune
  (base 0,86%, riducibile/aumentabile nei limiti di legge); abitazione
  principale non di lusso esente, A/1-A/8-A/9 con aliquota ridotta
  (base 0,5%) e detrazione 200 euro (c. 740 e 748-749).
- Categorie catastali: quadro generale delle categorie (gruppi A-F)
  secondo la classificazione dell'Agenzia delle Entrate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int

_RIVALUTAZIONE_RENDITA = 1.05

_FONTE_TUR = {
    "code": "dpr_131_1986_art52",
    "title": "Art. 52 D.P.R. 131/1986 e moltiplicatori (D.L. 168/2004, D.L. 262/2006)",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-04-26;131",
}
_FONTE_IMU = {
    "code": "l_160_2019_imu",
    "title": "Art. 1, commi 739-783, L. 160/2019 — disciplina IMU",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2019-12-27;160",
}
_FONTE_CATEGORIE = {
    "code": "ade_categorie_catastali",
    "title": "Agenzia delle Entrate — categorie catastali",
    "url": "https://www.agenziaentrate.gov.it/portale/web/guest/schede/fabbricatiterreni/consultazione-rendita-catastale",
}

# Gruppi ai fini dei moltiplicatori registro/successioni. Per il gruppo B
# il moltiplicatore differisce per ambito: 168 registro (D.L. 262/2006),
# 140 successioni e donazioni.
_MOLTIPLICATORI_REGISTRO: Dict[str, float] = {
    "abitazione_prima_casa": 110.0,
    "abitazione_altri": 120.0,   # gruppo A (escl. A/10) e C (escl. C/1)
    "gruppo_b": 168.0,
    "a10_gruppo_d": 60.0,
    "c1_gruppo_e": 40.8,
}
_MOLTIPLICATORE_B_SUCCESSIONI = 140.0

_GRUPPI_REGISTRO: List[Dict[str, str]] = [
    {"value": "abitazione_prima_casa", "label": "Abitazione con agevolazione prima casa (gruppo A escl. A/10, pertinenze C/2-C/6-C/7)"},
    {"value": "abitazione_altri", "label": "Gruppo A (escl. A/10) e gruppo C (escl. C/1) — senza agevolazione"},
    {"value": "gruppo_b", "label": "Gruppo B (collegi, scuole, uffici pubblici...)"},
    {"value": "a10_gruppo_d", "label": "A/10 (uffici) e gruppo D (opifici, alberghi...)"},
    {"value": "c1_gruppo_e", "label": "C/1 (negozi) e gruppo E"},
]

# Moltiplicatori IMU per categoria (art. 1, c. 745, L. 160/2019).
_MOLTIPLICATORI_IMU: Dict[str, float] = {
    "a_non_a10": 160.0,
    "c2_c6_c7": 160.0,
    "gruppo_b": 140.0,
    "c3_c4_c5": 140.0,
    "a10": 80.0,
    "d5": 80.0,
    "gruppo_d": 65.0,
    "c1": 55.0,
}

_GRUPPI_IMU: List[Dict[str, str]] = [
    {"value": "a_non_a10", "label": "Gruppo A escluso A/10 (abitazioni)"},
    {"value": "c2_c6_c7", "label": "C/2, C/6, C/7 (cantine, box, tettoie)"},
    {"value": "gruppo_b", "label": "Gruppo B"},
    {"value": "c3_c4_c5", "label": "C/3, C/4, C/5 (laboratori, palestre...)"},
    {"value": "a10", "label": "A/10 (uffici e studi privati)"},
    {"value": "d5", "label": "D/5 (istituti di credito e assicurativi)"},
    {"value": "gruppo_d", "label": "Gruppo D escluso D/5 (opifici, alberghi...)"},
    {"value": "c1", "label": "C/1 (negozi e botteghe)"},
]

_CATEGORIE: List[Dict[str, str]] = [
    {"categoria": "A/1", "descrizione": "Abitazioni di tipo signorile"},
    {"categoria": "A/2", "descrizione": "Abitazioni di tipo civile"},
    {"categoria": "A/3", "descrizione": "Abitazioni di tipo economico"},
    {"categoria": "A/4", "descrizione": "Abitazioni di tipo popolare"},
    {"categoria": "A/5", "descrizione": "Abitazioni di tipo ultrapopolare"},
    {"categoria": "A/6", "descrizione": "Abitazioni di tipo rurale"},
    {"categoria": "A/7", "descrizione": "Abitazioni in villini"},
    {"categoria": "A/8", "descrizione": "Abitazioni in ville"},
    {"categoria": "A/9", "descrizione": "Castelli, palazzi di eminenti pregi artistici o storici"},
    {"categoria": "A/10", "descrizione": "Uffici e studi privati"},
    {"categoria": "A/11", "descrizione": "Abitazioni ed alloggi tipici dei luoghi"},
    {"categoria": "B/1", "descrizione": "Collegi e convitti, educandati, ricoveri, orfanotrofi, ospizi, conventi, seminari, caserme"},
    {"categoria": "B/2", "descrizione": "Case di cura ed ospedali (senza fine di lucro)"},
    {"categoria": "B/3", "descrizione": "Prigioni e riformatori"},
    {"categoria": "B/4", "descrizione": "Uffici pubblici"},
    {"categoria": "B/5", "descrizione": "Scuole e laboratori scientifici"},
    {"categoria": "B/6", "descrizione": "Biblioteche, pinacoteche, musei, gallerie, accademie, circoli"},
    {"categoria": "B/7", "descrizione": "Cappelle ed oratori non destinati all'esercizio pubblico del culto"},
    {"categoria": "B/8", "descrizione": "Magazzini sotterranei per depositi di derrate"},
    {"categoria": "C/1", "descrizione": "Negozi e botteghe"},
    {"categoria": "C/2", "descrizione": "Magazzini e locali di deposito, cantine e soffitte"},
    {"categoria": "C/3", "descrizione": "Laboratori per arti e mestieri"},
    {"categoria": "C/4", "descrizione": "Fabbricati e locali per esercizi sportivi (senza fine di lucro)"},
    {"categoria": "C/5", "descrizione": "Stabilimenti balneari e di acque curative (senza fine di lucro)"},
    {"categoria": "C/6", "descrizione": "Stalle, scuderie, rimesse, autorimesse (box e posti auto)"},
    {"categoria": "C/7", "descrizione": "Tettoie chiuse od aperte"},
    {"categoria": "D/1", "descrizione": "Opifici"},
    {"categoria": "D/2", "descrizione": "Alberghi e pensioni (con fine di lucro)"},
    {"categoria": "D/3", "descrizione": "Teatri, cinematografi, sale per concerti e spettacoli (con fine di lucro)"},
    {"categoria": "D/4", "descrizione": "Case di cura ed ospedali (con fine di lucro)"},
    {"categoria": "D/5", "descrizione": "Istituti di credito, cambio e assicurazione (con fine di lucro)"},
    {"categoria": "D/6", "descrizione": "Fabbricati e locali per esercizi sportivi (con fine di lucro)"},
    {"categoria": "D/7", "descrizione": "Fabbricati per attività industriali"},
    {"categoria": "D/8", "descrizione": "Fabbricati per attività commerciali"},
    {"categoria": "D/9", "descrizione": "Edifici galleggianti o sospesi, ponti privati soggetti a pedaggio"},
    {"categoria": "D/10", "descrizione": "Fabbricati per funzioni produttive connesse alle attività agricole"},
    {"categoria": "E/1", "descrizione": "Stazioni per servizi di trasporto terrestri, marittimi ed aerei"},
    {"categoria": "E/2", "descrizione": "Ponti comunali e provinciali soggetti a pedaggio"},
    {"categoria": "E/3", "descrizione": "Costruzioni e fabbricati per speciali esigenze pubbliche"},
    {"categoria": "E/4", "descrizione": "Recinti chiusi per speciali esigenze pubbliche"},
    {"categoria": "E/5", "descrizione": "Fabbricati costituenti fortificazioni e loro dipendenze"},
    {"categoria": "E/6", "descrizione": "Fari, semafori, torri per orologio pubblico"},
    {"categoria": "E/7", "descrizione": "Fabbricati destinati all'esercizio pubblico dei culti"},
    {"categoria": "E/8", "descrizione": "Fabbricati e costruzioni nei cimiteri"},
    {"categoria": "E/9", "descrizione": "Edifici a destinazione particolare non compresi nelle categorie precedenti"},
    {"categoria": "F/1", "descrizione": "Area urbana"},
    {"categoria": "F/2", "descrizione": "Unità collabenti"},
    {"categoria": "F/3", "descrizione": "Unità in corso di costruzione"},
    {"categoria": "F/4", "descrizione": "Unità in corso di definizione"},
    {"categoria": "F/5", "descrizione": "Lastrici solari"},
    {"categoria": "F/6", "descrizione": "Fabbricato in attesa di dichiarazione"},
]


def calcola_valore_catastale(payload: Mapping[str, Any]) -> Dict[str, Any]:
    rendita = safe_float(payload.get("cat_rendita"))
    gruppo = clean_text(payload.get("cat_gruppo")) or "abitazione_altri"
    ambito = clean_text(payload.get("cat_ambito")) or "registro"

    if rendita <= 0:
        raise ValueError("Inserisci la rendita catastale non rivalutata (dalla visura).")
    if gruppo not in _MOLTIPLICATORI_REGISTRO:
        raise ValueError("Gruppo catastale non riconosciuto.")
    if ambito not in ("registro", "successione"):
        raise ValueError("Ambito ammesso: registro oppure successione/donazione.")

    moltiplicatore = _MOLTIPLICATORI_REGISTRO[gruppo]
    if gruppo == "gruppo_b" and ambito == "successione":
        moltiplicatore = _MOLTIPLICATORE_B_SUCCESSIONI
    rendita_rivalutata = rendita * _RIVALUTAZIONE_RENDITA
    valore = round(rendita_rivalutata * moltiplicatore, 2)
    label = next(v["label"] for v in _GRUPPI_REGISTRO if v["value"] == gruppo)

    notes = [
        "Valore = rendita × 1,05 × moltiplicatore. Il «prezzo-valore» (art. 1, "
        "c. 497, L. 266/2005) si applica alle sole cessioni di abitazioni verso "
        "persone fisiche che lo richiedono in atto.",
    ]
    if ambito == "registro":
        notes.append(
            "Per i trasferimenti onerosi di immobili non abitativi il valore "
            "catastale non preclude l'accertamento di maggior valore (art. 35, "
            "c. 23-ter, D.L. 223/2006)."
        )
    if gruppo == "gruppo_b":
        notes.append(
            "Gruppo B: moltiplicatore 168 per registro e ipocatastali su atti "
            "onerosi (D.L. 262/2006), 140 per successioni e donazioni."
        )

    return {
        "rendita": round(rendita, 2),
        "rendita_rivalutata": round(rendita_rivalutata, 2),
        "gruppo": label,
        "ambito": "Registro / atti onerosi" if ambito == "registro" else "Successioni e donazioni",
        "moltiplicatore": moltiplicatore,
        "valore_catastale": valore,
        "notes": notes,
        "warnings": [
            "Per i terreni agricoli vale un computo diverso (reddito dominicale "
            "rivalutato 25% × 90): non gestito da questo tool.",
        ],
        "sources": [_FONTE_TUR],
    }


def calcola_imu(payload: Mapping[str, Any]) -> Dict[str, Any]:
    rendita = safe_float(payload.get("imu_rendita"))
    gruppo = clean_text(payload.get("imu_gruppo")) or "a_non_a10"
    aliquota = safe_float(payload.get("imu_aliquota"))
    abitazione_principale = clean_text(payload.get("imu_abitazione_principale")) == "1"
    lusso = clean_text(payload.get("imu_lusso")) == "1"
    mesi = safe_int(payload.get("imu_mesi"), 12)
    quota_percent = safe_float(payload.get("imu_quota"), 100.0)
    residenti_contitolari = safe_int(payload.get("imu_residenti"), 1) or 1

    if rendita <= 0:
        raise ValueError("Inserisci la rendita catastale non rivalutata (dalla visura).")
    if gruppo not in _MOLTIPLICATORI_IMU:
        raise ValueError("Gruppo catastale IMU non riconosciuto.")
    if aliquota < 0 or aliquota > 1.14:
        raise ValueError(
            "Aliquota IMU espressa in percento (es. 0,86): il massimo di legge è "
            "1,06%, elevabile a 1,14% nei soli comuni con maggiorazione ex art. 1, "
            "c. 755, L. 160/2019."
        )
    if residenti_contitolari < 1 or residenti_contitolari > 20:
        raise ValueError("I contitolari residenti vanno da 1 a 20.")
    if mesi < 1 or mesi > 12:
        raise ValueError("I mesi di possesso vanno da 1 a 12.")
    if quota_percent <= 0 or quota_percent > 100:
        raise ValueError("La quota di possesso va da 1 a 100.")

    if abitazione_principale and not lusso:
        return {
            "esito": "Esente",
            "base_imponibile": 0.0,
            "imposta_annua": 0.0,
            "notes": [
                "Abitazione principale non di lusso (categorie diverse da A/1, A/8, A/9): "
                "esente da IMU (art. 1, c. 740, L. 160/2019).",
            ],
            "warnings": [],
            "sources": [_FONTE_IMU],
        }

    moltiplicatore = _MOLTIPLICATORI_IMU[gruppo]
    base = rendita * _RIVALUTAZIONE_RENDITA * moltiplicatore
    imposta_piena = base * aliquota / 100.0
    imposta = imposta_piena * (mesi / 12.0) * (quota_percent / 100.0)

    detrazione = 0.0
    notes: List[str] = [
        "Base imponibile = rendita × 1,05 × moltiplicatore (art. 1, c. 745, L. 160/2019).",
        "L'aliquota effettiva è quella deliberata dal Comune per l'anno e la fattispecie: "
        "verificarla sul sito del Dipartimento Finanze (aliquota base 0,86%).",
    ]
    if abitazione_principale and lusso:
        detrazione = 200.0 * (mesi / 12.0) / residenti_contitolari
        imposta = max(imposta - detrazione, 0.0)
        notes.append(
            "Abitazione principale di lusso (A/1, A/8, A/9): detrazione 200 euro "
            "rapportata ai mesi e ripartita in parti uguali tra i contitolari che "
            "vi risiedono, indipendentemente dalla quota di possesso (art. 1, "
            "c. 749, L. 160/2019; aliquota base 0,5%)."
        )

    label = next(v["label"] for v in _GRUPPI_IMU if v["value"] == gruppo)
    return {
        "gruppo": label,
        "moltiplicatore": moltiplicatore,
        "base_imponibile": round(base, 2),
        "aliquota": aliquota,
        "mesi_possesso": mesi,
        "quota_possesso": quota_percent,
        "detrazione": round(detrazione, 2),
        "imposta_annua": round(imposta, 2),
        "notes": notes,
        "warnings": [
            "Riduzioni e regimi speciali non gestiti qui: fabbricati rurali "
            "strumentali, immobili merce, comodati a parenti, canone concordato, "
            "riduzione 50% della base per immobili storico-artistici o inagibili "
            "(art. 1, c. 747, L. 160/2019), regime dei pensionati esteri; i "
            "fabbricati del gruppo E sono esenti (c. 759, lett. b); per i gruppi D "
            "con rendita non aggiornata vale il criterio contabile.",
        ],
        "sources": [_FONTE_IMU],
    }


def tabella_categorie(payload: Mapping[str, Any]) -> Dict[str, Any]:
    gruppo = clean_text(payload.get("catcat_gruppo")).upper() or "TUTTI"
    if gruppo not in ("TUTTI", "A", "B", "C", "D", "E", "F"):
        raise ValueError("Gruppo ammesso: A, B, C, D, E, F oppure TUTTI.")
    righe = [
        voce for voce in _CATEGORIE
        if gruppo == "TUTTI" or voce["categoria"].startswith(gruppo + "/")
    ]
    return {
        "gruppo": gruppo,
        "totale": len(righe),
        "categorie": righe,
        "notes": [
            "Classificazione delle unità immobiliari urbane secondo il quadro "
            "generale delle categorie dell'Agenzia delle Entrate.",
        ],
        "sources": [_FONTE_CATEGORIE],
    }


def opzioni_gruppi_registro() -> list[dict]:
    return list(_GRUPPI_REGISTRO)


def opzioni_gruppi_imu() -> list[dict]:
    return list(_GRUPPI_IMU)
