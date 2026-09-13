"""Liquidazione del danno biologico sulle tabelle vigenti.

Il modulo orchestra soltanto: sceglie la tabella con ``regime``, chiede i
valori ai moduli ``art139``, ``tun`` e ``milano`` e compone il risultato con le
fonti. Nessun valore monetario nasce qui.

Regola sulla data usata per gli importi: il debito risarcitorio e' debito di
valore, quindi gli importi dell'art. 139 sono quelli del decreto vigente alla
data di liquidazione, mentre la data del sinistro serve solo a individuare la
tabella applicabile.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Mapping
from zoneinfo import ZoneInfo

from pct.calcolatori._base import clean_text, safe_float, safe_int
from pct.calcolatori.danno_biologico import art139, milano, regime, tabelle, tun

ROME_TZ = ZoneInfo("Europe/Rome")

LIVELLI_MORALE = {
    "nessuno": ("Nessun incremento", 0.0),
    "minimo": ("Minimo", float(tun.MORALE_TEMPORANEO_MINIMO_PCT)),
    "medio": ("Medio", 45.0),
    "massimo": ("Massimo", float(tun.MORALE_TEMPORANEO_MASSIMO_PCT)),
}

_PERCENTUALI_ITP = (25, 50, 75)


def _oggi() -> date:
    return datetime.now(ROME_TZ).date()


def _arrotonda(valore: float) -> float:
    return round(float(valore), 2)


def _riga(voce: str, importo: float, criterio: str) -> Dict[str, Any]:
    return {"voce": voce, "importo": _arrotonda(importo), "criterio": criterio}


def _leggi_input(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data_sinistro = regime.leggi_data(payload.get("db_data_sinistro"))
    if data_sinistro is None:
        raise ValueError(
            "Indica la data del sinistro: determina quale tabella e' applicabile "
            "(la tabella unica nazionale vale solo per i sinistri dal 5 marzo 2025)."
        )
    if data_sinistro > _oggi():
        raise ValueError("La data del sinistro non puo' essere futura.")
    data_liquidazione = regime.leggi_data(payload.get("db_data_liquidazione")) or _oggi()
    if data_liquidazione < data_sinistro:
        raise ValueError("La data di liquidazione non puo' precedere la data del sinistro.")

    eta = safe_int(payload.get("db_eta"), -1)
    if eta < 0 or eta > 120:
        raise ValueError("Indica l'eta' della persona lesa alla data del sinistro (0-120 anni).")

    punti = safe_int(payload.get("db_perc_ip"))
    if not 0 <= punti <= 100:
        raise ValueError("La percentuale di invalidita' permanente deve essere compresa tra 0 e 100.")

    percentuale_itp = safe_int(payload.get("db_perc_itp"), 50)
    if percentuale_itp not in _PERCENTUALI_ITP:
        percentuale_itp = 50

    livello_morale = clean_text(payload.get("db_morale_livello")).lower() or "medio"
    if livello_morale not in LIVELLI_MORALE:
        livello_morale = "medio"

    return {
        "ambito": regime.ambito_valido(clean_text(payload.get("db_ambito")).lower()),
        "data_sinistro": data_sinistro,
        "data_liquidazione": data_liquidazione,
        "eta": eta,
        "punti": punti,
        "giorni_itt": max(0, safe_int(payload.get("db_giorni_itt"))),
        "giorni_itp": max(0, safe_int(payload.get("db_giorni_itp"))),
        "percentuale_itp": percentuale_itp,
        "personalizzazione": max(0.0, safe_float(payload.get("db_personalizzazione"))),
        "livello_morale": livello_morale,
    }


def _blocco_art139(dati: Dict[str, Any], righe: List[Dict[str, Any]], note: List[str]) -> Dict[str, float]:
    decreto = art139.decreto_vigente(dati["data_liquidazione"])
    primo_punto = float(decreto["primo_punto"])
    valore_giorno = float(decreto["giorno_inabilita_assoluta"])
    dati["decreto"] = decreto

    permanente = art139.danno_permanente(dati["punti"], dati["eta"], primo_punto)
    if permanente:
        righe.append(_riga(
            f"Danno biologico permanente — {dati['punti']} punti",
            permanente,
            f"{primo_punto:.2f} € x coefficiente {art139.coefficiente_punto(dati['punti'])} "
            f"x {dati['punti']} punti x riduzione eta' {art139.coefficiente_eta(dati['eta']):.3f}",
        ))
    temporanea = _temporanea_legge(dati, righe, valore_giorno)
    note.append(
        f"Importi del {decreto['decreto']} ({decreto['gazzetta']}), in vigore dal "
        f"{decreto['decorrenza'][8:10]}/{decreto['decorrenza'][5:7]}/{decreto['decorrenza'][0:4]}: "
        f"primo punto {primo_punto:.2f} €, inabilita' assoluta {valore_giorno:.2f} € al giorno."
    )
    note.append(
        "Art. 139 comma 3: l'ammontare complessivo e' esaustivo del risarcimento del danno "
        "non patrimoniale conseguente a lesioni fisiche, quindi il danno morale non si "
        "liquida in aggiunta ma rientra nell'aumento fino al 20 per cento."
    )
    return {
        "permanente": permanente,
        "temporanea": temporanea,
        "morale": 0.0,
        "tetto_permanente": art139.personalizzazione_massima(),
        "tetto_temporanea": art139.personalizzazione_massima(),
    }


def _temporanea_legge(dati: Dict[str, Any], righe: List[Dict[str, Any]], valore_giorno: float) -> float:
    """Danno biologico temporaneo secondo l'art. 139 comma 1 lettera b)."""
    totale = 0.0
    if dati["giorni_itt"]:
        importo = art139.danno_temporaneo(dati["giorni_itt"], 100.0, valore_giorno)
        totale += importo
        righe.append(_riga(
            f"Inabilita' temporanea assoluta — {dati['giorni_itt']} giorni",
            importo,
            f"{dati['giorni_itt']} giorni x {valore_giorno:.2f} €",
        ))
    if dati["giorni_itp"]:
        importo = art139.danno_temporaneo(dati["giorni_itp"], float(dati["percentuale_itp"]), valore_giorno)
        totale += importo
        righe.append(_riga(
            f"Inabilita' temporanea parziale al {dati['percentuale_itp']}% — {dati['giorni_itp']} giorni",
            importo,
            f"{dati['giorni_itp']} giorni x {valore_giorno:.2f} € x {dati['percentuale_itp']}%",
        ))
    return _arrotonda(totale)


def _blocco_tun(dati: Dict[str, Any], righe: List[Dict[str, Any]], note: List[str]) -> Dict[str, float]:
    decreto = art139.decreto_vigente(dati["data_liquidazione"])
    primo_punto = float(decreto["primo_punto"])
    valore_giorno = float(decreto["giorno_inabilita_assoluta"])
    dati["decreto"] = decreto

    punti, eta = dati["punti"], dati["eta"]
    permanente = tun.danno_biologico(punti, eta, primo_punto)
    righe.append(_riga(
        f"Danno biologico permanente — {punti} punti",
        permanente,
        f"{primo_punto:.2f} € x coefficiente {tun.coefficiente_biologico(punti)} "
        f"x {punti} punti x riduzione eta' {tun.coefficiente_eta(eta):.3f}",
    ))

    livello = dati["livello_morale"]
    morale = 0.0
    if livello != "nessuno":
        morale = tun.danno_morale(punti, eta, primo_punto, livello)
        righe.append(_riga(
            f"Danno morale — incremento {LIVELLI_MORALE[livello][0].lower()}",
            morale,
            f"{tun.coefficiente_morale(punti, livello) * 100:.1f}% del danno biologico "
            "(tavola 2 dell'allegato I)",
        ))

    temporanea = _temporanea_legge(dati, righe, valore_giorno)
    morale_temporanea = 0.0
    percentuale_morale_temporanea = LIVELLI_MORALE[livello][1]
    if temporanea and percentuale_morale_temporanea:
        morale_temporanea = _arrotonda(temporanea * percentuale_morale_temporanea / 100.0)
        righe.append(_riga(
            "Danno morale sull'inabilita' temporanea",
            morale_temporanea,
            f"{percentuale_morale_temporanea:.0f}% del danno biologico temporaneo "
            "(art. 3 comma 2 D.P.R. 12/2025)",
        ))

    note.append(
        f"Valore del primo punto dal {decreto['decreto']} ({decreto['gazzetta']}): "
        f"{primo_punto:.2f} €, per rinvio dell'art. 2 del D.P.R. 12/2025 all'art. 139."
    )
    note.append(
        "Il danno morale sull'inabilita' temporanea e' compreso fra il 30 e il 60 per cento "
        "del danno biologico temporaneo (art. 3 comma 2 D.P.R. 12/2025)."
    )
    note.append(
        "Art. 138 comma 4: l'ammontare complessivo e' esaustivo del risarcimento del danno "
        "conseguente alle lesioni fisiche."
    )
    return {
        "permanente": permanente,
        "temporanea": temporanea,
        "morale": _arrotonda(morale + morale_temporanea),
        "morale_temporanea": morale_temporanea,
        "tetto_permanente": tun.PERSONALIZZAZIONE_MASSIMA_PCT,
        "tetto_temporanea": art139.personalizzazione_massima(),
    }


def _blocco_milano(dati: Dict[str, Any], righe: List[Dict[str, Any]], note: List[str]) -> Dict[str, float]:
    punti, eta = dati["punti"], dati["eta"]
    permanente = 0.0
    if punti:
        cella = milano.danno_permanente(punti, eta)
        permanente = cella["totale"]
        righe.append(_riga(
            f"Danno biologico/dinamico-relazionale — {punti} punti",
            cella["biologico"],
            f"{milano.riga_punto(punti)['biologico']:.2f} € x {punti} punti "
            f"x demoltiplicatore eta' {milano.demoltiplicatore_eta(eta):.3f}",
        ))
        righe.append(_riga(
            "Sofferenza soggettiva interiore",
            cella["sofferenza"],
            f"{milano.riga_punto(punti)['sofferenza_pct']:.0f}% della componente biologica "
            "(colonna B della tabella)",
        ))

    valore_giorno = milano.valore_giorno_inabilita_totale()
    temporanea = 0.0
    if dati["giorni_itt"]:
        importo = milano.danno_temporaneo(dati["giorni_itt"], 100.0)
        temporanea += importo
        righe.append(_riga(
            f"Inabilita' temporanea assoluta — {dati['giorni_itt']} giorni",
            importo,
            f"{dati['giorni_itt']} giorni x {valore_giorno:.2f} €",
        ))
    if dati["giorni_itp"]:
        importo = milano.danno_temporaneo(dati["giorni_itp"], float(dati["percentuale_itp"]))
        temporanea += importo
        righe.append(_riga(
            f"Inabilita' temporanea parziale al {dati['percentuale_itp']}% — {dati['giorni_itp']} giorni",
            importo,
            f"{dati['giorni_itp']} giorni x {valore_giorno:.2f} € x {dati['percentuale_itp']}%",
        ))

    note.append(
        f"Valore pro die dell'inabilita' temporanea assoluta {valore_giorno:.2f} €, gia' "
        "comprensivo della componente di sofferenza soggettiva (edizione 2024)."
    )
    note.append(
        "Nelle tabelle milanesi la sofferenza soggettiva interiore e' liquidata insieme al "
        "danno biologico: non va aggiunta una voce ulteriore di danno morale."
    )
    return {
        "permanente": _arrotonda(permanente),
        "temporanea": _arrotonda(temporanea),
        "morale": 0.0,
        "tetto_permanente": milano.personalizzazione_massima(punti) if punti else 0,
        "tetto_temporanea": int(_dati_milano()["personalizzazione_massima_temporanea_pct"]),
    }


def _dati_milano() -> Dict[str, Any]:
    return tabelle.carica(tabelle.MILANO_2024)


def _fonti(codice: str) -> List[str]:
    if codice == regime.REGIME_ART_139:
        return [tabelle.ART_139]
    if codice == regime.REGIME_TUN:
        return [tabelle.TUN_2025, tabelle.ART_139]
    return [tabelle.MILANO_2024]


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Liquida il danno biologico con la tabella imposta dall'ambito e dalla data."""
    dati = _leggi_input(payload)
    scelta = regime.scegli(dati["ambito"], dati["punti"], dati["data_sinistro"])

    righe: List[Dict[str, Any]] = []
    note: List[str] = [scelta.motivazione]
    avvisi: List[str] = []

    if scelta.codice == regime.REGIME_ART_139:
        importi = _blocco_art139(dati, righe, note)
    elif scelta.codice == regime.REGIME_TUN:
        importi = _blocco_tun(dati, righe, note)
    else:
        importi = _blocco_milano(dati, righe, note)

    permanente_totale = _arrotonda(importi["permanente"] + importi["morale"] - importi.get("morale_temporanea", 0.0))
    temporanea_totale = _arrotonda(importi["temporanea"] + importi.get("morale_temporanea", 0.0))
    subtotale = _arrotonda(permanente_totale + temporanea_totale)

    richiesta = dati["personalizzazione"]
    tetto_permanente = int(importi["tetto_permanente"])
    tetto_temporanea = int(importi["tetto_temporanea"])
    massimo = max(tetto_permanente, tetto_temporanea)
    if richiesta > massimo:
        avvisi.append(
            f"La personalizzazione richiesta ({richiesta:.0f}%) supera il limite del "
            f"{massimo}% previsto dalla tabella applicata: e' stata ridotta al massimo consentito."
        )
        richiesta = float(massimo)
    personalizzazione = richiesta
    quota_permanente = min(richiesta, float(tetto_permanente))
    quota_temporanea = min(richiesta, float(tetto_temporanea))
    importo_personalizzazione = _arrotonda(
        permanente_totale * quota_permanente / 100.0 + temporanea_totale * quota_temporanea / 100.0
    )
    if importo_personalizzazione:
        if quota_permanente != quota_temporanea:
            criterio = (
                f"aumento motivato fino al {tetto_permanente}% sul danno permanente e al "
                f"{tetto_temporanea}% sull'inabilita' temporanea"
            )
        else:
            criterio = f"aumento motivato fino al {massimo}% sul risarcimento tabellare"
        righe.append(_riga(f"Personalizzazione {personalizzazione:.0f}%", importo_personalizzazione, criterio))

    totale = _arrotonda(subtotale + importo_personalizzazione)

    if dati["punti"] == 0 and not dati["giorni_itt"] and not dati["giorni_itp"]:
        avvisi.append("Nessuna invalidita' permanente e nessun giorno di inabilita' temporanea indicati.")
    if regime.soggetto_al_codice_assicurazioni(dati["ambito"]) and 1 <= dati["punti"] <= 9:
        note.append(
            "Art. 139 comma 2: le lesioni di lieve entita' non suscettibili di accertamento "
            "clinico strumentale obiettivo, o visivo per le lesioni oggettivamente "
            "riscontrabili, non danno luogo a risarcimento del danno biologico permanente."
        )
    if scelta.codice == regime.REGIME_MILANO and regime.soggetto_al_codice_assicurazioni(dati["ambito"]):
        avvisi.append(
            "Per i sinistri anteriori al 5 marzo 2025 non esiste una tabella di legge per le "
            "macrolesioni: la liquidazione resta equitativa e va motivata sul caso concreto."
        )
    if dati["data_liquidazione"] != _oggi():
        note.append(
            "Importi riferiti alla data di liquidazione indicata "
            f"({dati['data_liquidazione'].strftime('%d/%m/%Y')})."
        )

    fonti = [tabelle.fonte(identificativo) for identificativo in _fonti(scelta.codice)]
    return {
        "ambito": dati["ambito"],
        "ambito_label": regime.AMBITI[dati["ambito"]],
        "regime": scelta.codice,
        "regime_label": scelta.etichetta,
        "data_sinistro": dati["data_sinistro"].isoformat(),
        "data_liquidazione": dati["data_liquidazione"].isoformat(),
        "eta": dati["eta"],
        "perc_ip": dati["punti"],
        "giorni_itt": dati["giorni_itt"],
        "giorni_itp": dati["giorni_itp"],
        "perc_itp": dati["percentuale_itp"],
        "livello_morale": dati["livello_morale"],
        "danno_permanente": importi["permanente"],
        "danno_temporaneo": importi["temporanea"],
        "danno_morale": importi["morale"],
        "subtotale": subtotale,
        "personalizzazione_pct": personalizzazione,
        "personalizzazione_massima_pct": massimo,
        "personalizzazione_massima_permanente_pct": tetto_permanente,
        "personalizzazione_massima_temporanea_pct": tetto_temporanea,
        "importo_personalizzazione": importo_personalizzazione,
        "totale": totale,
        "totale_comprensivo": totale,
        "dettaglio": righe,
        "tabelle_applicate": [fonte.come_dizionario() for fonte in fonti],
        "notes": note,
        "warnings": avvisi,
        "sources": [fonte.come_sorgente() for fonte in fonti],
    }
