from __future__ import annotations

import html
import math
from calendar import monthrange
from datetime import date, timedelta
from textwrap import dedent
from typing import Any, Dict, List, Mapping, Optional

from pct.normative_tables import (
    FONTI_OPERATIVE,
    GestioneTabelleNormative,
    InterestPeriod,
)
from pct.tariffario import (
    ComplessitaStimata,
    Fase,
    Grado,
    Materia,
    calcola_compenso,
    tutte_le_complessita,
    tutte_le_fasi,
    tutte_le_materie,
    tutti_i_gradi,
)


def _today() -> date:
    return date.today()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _fmt_money(value: float) -> str:
    amount = round(float(value or 0.0), 2)
    text = f"{amount:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_percent(value: float) -> str:
    return f"{round(value, 2):.2f}".replace(".", ",")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "on", "si", "s", "yes"}


def _getlist(payload: Mapping[str, Any], key: str) -> List[str]:
    if hasattr(payload, "getlist"):
        try:
            return [_clean_text(v) for v in payload.getlist(key) if _clean_text(v)]
        except TypeError:
            pass
    raw = payload.get(key)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [_clean_text(v) for v in raw if _clean_text(v)]
    value = _clean_text(raw)
    return [value] if value else []


def _days_inclusive(start: date, end: date) -> int:
    return (end - start).days + 1


def _year_denominator(day: date) -> int:
    year = day.year
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


def _fmt_date_it(value: Any) -> str:
    if isinstance(value, date):
        day = value
    else:
        day = _parse_date(value)
    return day.strftime("%d/%m/%Y") if day else "n/d"


def _add_months(day: date, months: int) -> date:
    total_month = (day.month - 1) + int(months)
    year = day.year + total_month // 12
    month = total_month % 12 + 1
    month_day = min(day.day, monthrange(year, month)[1])
    return date(year, month, month_day)


class GestioneStrumentiLegali:
    def __init__(self, normative_db_path: str = "./intelligence/tabelle_normative.json"):
        self.norme = GestioneTabelleNormative(db_path=normative_db_path)

    def _source(self, code: str) -> Dict[str, str]:
        return FONTI_OPERATIVE[code].to_dict()

    def _sources_for_codes(self, *codes: str) -> List[Dict[str, str]]:
        unique: Dict[str, Dict[str, str]] = {}
        for code in codes:
            if code and code in FONTI_OPERATIVE:
                source = FONTI_OPERATIVE[code].to_dict()
                unique[source["url"]] = source
        return list(unique.values())

    def catalogo_moduli(self) -> List[Dict[str, str]]:
        return [
            {"id": "contributo_unificato", "title": "Contributo unificato", "subtitle": "Civile, amministrativo e tributario con basi ufficiali e note operative.", "icon": "bi-bank", "categoria": "Fiscale"},
            {"id": "interessi", "title": "Interessi legali e moratori", "subtitle": "Art. 1284 c.c. e D.Lgs. 231/2002 con segmentazione per periodo.", "icon": "bi-percent", "categoria": "Credito"},
            {"id": "nota_credito", "title": "Nota di precisazione del credito", "subtitle": "Bozza professionale con capitale, interessi, spese, CPA, IVA e residuo.", "icon": "bi-file-earmark-ruled", "categoria": "Credito"},
            {"id": "pignoramento", "title": "Simulatore pignoramento stipendio / pensione", "subtitle": "Ordinario, esattoriale e alimentare con soglia pensione 2026 aggiornata.", "icon": "bi-cash-stack", "categoria": "Esecuzione"},
            {"id": "ctu", "title": "CTU, vacazioni e compensi ausiliari", "subtitle": "Vacazioni vigenti, spese documentate e accessori professionali.", "icon": "bi-journal-medical", "categoria": "Processo"},
            {"id": "rivalutazione_istat", "title": "Rivalutazione monetaria ISTAT", "subtitle": "Calcolo FOI / NIC per danni, assegni divorzili, liquidazioni e adeguamenti.", "icon": "bi-graph-up-arrow", "categoria": "Danni"},
            {"id": "canone_locazione", "title": "Adeguamento canone di locazione", "subtitle": "Aggiornamento annuale con indice ISTAT FOI ex L. 431/1998.", "icon": "bi-house-lock", "categoria": "Locazioni"},
            {"id": "usura", "title": "Verifica soglia usura", "subtitle": "Confronta il tasso con TEGM e soglia antiusura per categoria (L. 108/1996).", "icon": "bi-shield-exclamation", "categoria": "Credito"},
            {"id": "contributi_cassa_forense", "title": "Contributi Cassa Forense", "subtitle": "Soggettivo, integrativo e maternita: aliquote e minimali annuali aggiornati.", "icon": "bi-person-badge", "categoria": "Previdenza"},
            {"id": "tfr", "title": "TFR", "subtitle": "Quota maturata, rivalutazione annuale e residuo operativo del trattamento di fine rapporto.", "icon": "bi-wallet2", "categoria": "Lavoro"},
            {"id": "onorari_forensi", "title": "Onorari Forensi", "subtitle": "Parametri DM 55/2014 e DM 147/2022 con fasi, complessita e bonus telematico.", "icon": "bi-briefcase", "categoria": "Professione"},
            {"id": "custodia_cautelare", "title": "Custodia Cautelare", "subtitle": "Monitor di interrogatorio, riesame, decisione e deposito motivazione.", "icon": "bi-shield-lock", "categoria": "Penale"},
            {"id": "prescrizione_penale", "title": "Prescrizione Penale", "subtitle": "Decorrenza base, sospensioni e proiezione del termine massimo con assunzioni esplicite.", "icon": "bi-hourglass-split", "categoria": "Penale"},
            {"id": "successione_legittima", "title": "Successione Legittima", "subtitle": "Riparto quote tra coniuge, figli, ascendenti e fratelli sull'asse ereditario.", "icon": "bi-diagram-3", "categoria": "Patrimonio"},
            {"id": "cedolare_secca", "title": "Cedolare Secca", "subtitle": "Imposta annua, costo pluriennale e confronto operativo con il registro ordinario.", "icon": "bi-house-check", "categoria": "Fiscale"},
            {"id": "indennita_licenziamento", "title": "Indennita Licenziamento", "subtitle": "Tutele crescenti, piccole imprese e stima mensilita riconoscibili.", "icon": "bi-person-x", "categoria": "Lavoro"},
            {"id": "piano_ammortamento", "title": "Piano di Ammortamento", "subtitle": "Metodo francese o italiano, rata, interessi e sviluppo rateale completo.", "icon": "bi-table", "categoria": "Finanza"},
        ]

    def build_prefill(
        self,
        fascicolo: Any = None,
        cliente: Any = None,
        studio: Optional[Mapping[str, Any]] = None,
        utente: Any = None,
    ) -> Dict[str, str]:
        studio = dict(studio or {})
        lawyer = ""
        if utente is not None:
            lawyer = _clean_text(getattr(utente, "nome_completo", "") or getattr(utente, "username", ""))
        if not lawyer:
            lawyer = _clean_text(studio.get("avvocato", ""))
        if fascicolo is not None and not lawyer:
            lawyer = _clean_text(getattr(fascicolo, "avvocato_referente", ""))

        court = _clean_text(getattr(fascicolo, "tribunale", "")) if fascicolo is not None else ""
        rg = ""
        if fascicolo is not None:
            numero_rg = _clean_text(getattr(fascicolo, "numero_rg", ""))
            anno_rg = getattr(fascicolo, "anno_rg", 0) or ""
            if numero_rg and anno_rg:
                rg = f"{numero_rg}/{anno_rg}"
            elif numero_rg:
                rg = numero_rg

        cliente_nome = ""
        cliente_cf = ""
        cliente_indirizzo = ""
        if cliente is not None:
            cliente_nome = _clean_text(getattr(cliente, "nome_completo", ""))
            cliente_cf = _clean_text(getattr(cliente, "identificativo_fiscale", ""))
            if getattr(cliente, "tipo", None) and getattr(cliente.tipo, "value", "") == "PERSONA_GIURIDICA":
                cliente_indirizzo = _clean_text(str(getattr(cliente, "indirizzo_sede_legale", "")))
            else:
                cliente_indirizzo = _clean_text(str(getattr(cliente, "indirizzo_residenza", "")))

        debtor = _clean_text(getattr(fascicolo, "controparte", "")) if fascicolo is not None else ""
        case_value = _safe_float(getattr(fascicolo, "valore_causa", 0.0)) if fascicolo is not None else 0.0
        subject = _clean_text(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "")) if fascicolo is not None else ""

        return {
            "creditore": cliente_nome or _clean_text(getattr(fascicolo, "nome_cliente", "")),
            "creditore_cf": cliente_cf,
            "creditore_indirizzo": cliente_indirizzo,
            "debitore": debtor,
            "tribunale": court,
            "rg": rg,
            "valore_causa": f"{case_value:.2f}" if case_value else "",
            "oggetto": subject,
            "avvocato": lawyer,
            "studio_nome": _clean_text(studio.get("nome", "")),
            "studio_indirizzo": _clean_text(studio.get("indirizzo", "")),
            "studio_cf": _clean_text(studio.get("cf", "")),
            "studio_piva": _clean_text(studio.get("piva", "")),
            "studio_pec": _clean_text(studio.get("pec", "")),
            "studio_fax": _clean_text(studio.get("fax", "")),
            "luogo": _clean_text(studio.get("luogo", "")),
        }

    def build_form_state(self, prefill: Mapping[str, str], posted: Optional[Mapping[str, Any]] = None) -> Dict[str, str]:
        today = _today().isoformat()
        defaults = {
            "cu_categoria": "civile_ordinario",
            "cu_grado": "primo_grado",
            "cu_valore": prefill.get("valore_causa", ""),
            "cu_anticipazione_forfettaria": "1",
            "int_tipo": "legali",
            "int_capitale": prefill.get("valore_causa", ""),
            "int_data_inizio": today,
            "int_data_fine": today,
            "note_tribunale": prefill.get("tribunale", ""),
            "note_rg": prefill.get("rg", ""),
            "note_creditore": prefill.get("creditore", ""),
            "note_debitore": prefill.get("debitore", ""),
            "note_titolo": prefill.get("oggetto", "") or "Credito professionale",
            "note_capitale": prefill.get("valore_causa", ""),
            "note_interessi_tipo": "legali",
            "note_data_inizio": today,
            "note_data_fine": today,
            "note_interessi_manual": "",
            "note_spese_vive": "",
            "note_compensi": "",
            "note_cpa_perc": "4",
            "note_iva_perc": "22",
            "note_acconti": "",
            "note_luogo": prefill.get("luogo", ""),
            "note_data": today,
            "note_avvocato": prefill.get("avvocato", ""),
            "pig_tipo_reddito": "stipendio",
            "pig_tipo_credito": "ordinario",
            "pig_importo_netto": "",
            "pig_aliquota_alimentare": "33.33",
            "ctu_modalita": "vacazioni",
            "ctu_ore": "",
            "ctu_vacazioni": "",
            "ctu_onorario": "",
            "ctu_spese": "",
            "ctu_cpa_perc": "4",
            "ctu_iva_perc": "22",
            # Rivalutazione ISTAT
            "riv_importo": prefill.get("valore_causa", ""),
            "riv_tipo": "nic",
            "riv_anno_base": "",
            "riv_mese_base": "",
            "riv_anno_fine": "",
            "riv_mese_fine": "",
            # Adeguamento canone locazione
            "loc_canone": "",
            "loc_perc_adeguamento": "75",
            "loc_anno_base": "",
            "loc_mese_base": "",
            "loc_anno_fine": "",
            "loc_mese_fine": "",
            # Verifica usura
            "usura_tasso": "",
            "usura_categoria": "credito_personale",
            "usura_data": today,
            # Contributi Cassa Forense
            "cf_anno": str(_today().year),
            "cf_reddito": "",
            "cf_compensi": "",
            # TFR
            "tfr_retribuzione_annua": "",
            "tfr_anni_servizio": "",
            "tfr_mesi_servizio": "",
            "tfr_montante_pregresso": "",
            "tfr_inflazione_perc": "2.00",
            "tfr_anticipazioni": "",
            # Onorari forensi
            "onorari_materia": "CIVILE_COGN",
            "onorari_grado": "TRIBUNALE",
            "onorari_valore": prefill.get("valore_causa", ""),
            "onorari_complessita": "media",
            "onorari_bonus_telematico": "0",
            "onorari_includi_spese_generali": "1",
            # Custodia cautelare
            "custodia_tipo_misura": "carcere",
            "custodia_data_esecuzione": today,
            "custodia_data_istanza_riesame": "",
            "custodia_data_decisione_riesame": "",
            # Prescrizione penale
            "presc_data_fatto": today,
            "presc_massimo_edittale_anni": "6",
            "presc_massimo_edittale_mesi": "0",
            "presc_contravvenzione": "0",
            "presc_coeff_interruzione": "1.25",
            "presc_giorni_sospensione": "0",
            # Successione legittima
            "successione_asse": "",
            "successione_coniuge": "0",
            "successione_figli": "0",
            "successione_ascendenti": "0",
            "successione_fratelli": "0",
            # Cedolare secca
            "cedolare_canone_annuo": "",
            "cedolare_aliquota": "21",
            "cedolare_annualita": "1",
            # Indennita licenziamento
            "lic_retribuzione_mensile": "",
            "lic_anni_servizio": "",
            "lic_mesi_servizio": "",
            "lic_regime": "jobs_act",
            "lic_mensilita_preavviso": "0",
            # Piano di ammortamento
            "amm_capitale": "",
            "amm_tasso_annuo": "",
            "amm_durata_anni": "10",
            "amm_rate_anno": "12",
            "amm_tipo": "francese",
            "amm_data_prima_rata": today,
        }
        if posted:
            for key in defaults:
                if key in posted:
                    defaults[key] = str(posted.get(key, defaults[key]) or "")
        return defaults

    def opzioni_onorari_forensi(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "materie": [{"value": item.name, "label": item.value} for item in tutte_le_materie()],
            "gradi": [{"value": item.name, "label": item.value} for item in tutti_i_gradi()],
            "complessita": [{"value": item.value, "label": item.value.capitalize()} for item in tutte_le_complessita()],
            "fasi": [{"value": item.name, "label": item.value} for item in tutte_le_fasi()],
        }

    def opzioni_contributo_unificato(self) -> List[Dict[str, Any]]:
        return [
            {"value": "civile_ordinario", "label": "Civile ordinario", "needs_value": True},
            {"value": "decreto_ingiuntivo", "label": "Ricorso per decreto ingiuntivo", "needs_value": True},
            {"value": "volontaria_giurisdizione", "label": "Volontaria giurisdizione", "needs_value": False},
            {"value": "separazione_consensuale", "label": "Separazione / divorzio congiunto", "needs_value": False},
            {"value": "tributario", "label": "Ricorso tributario", "needs_value": True},
            {"value": "amministrativo_ordinario", "label": "Ricorso amministrativo ordinario", "needs_value": False},
            {"value": "amministrativo_rito_abbreviato", "label": "Rito abbreviato amministrativo", "needs_value": False},
            {"value": "amministrativo_appalti", "label": "Appalti pubblici (art. 119 c.p.a.)", "needs_value": True},
            {"value": "amministrativo_ottemperanza", "label": "Ottemperanza con contestuale risarcitoria", "needs_value": False},
        ]

    def calcola_contributo_unificato(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        categoria = _clean_text(payload.get("cu_categoria")) or "civile_ordinario"
        grado = _clean_text(payload.get("cu_grado")) or "primo_grado"
        valore = _safe_float(payload.get("cu_valore"))
        anticipazione_forfettaria = str(payload.get("cu_anticipazione_forfettaria", "")).lower() in {"1", "true", "on", "si"}

        base = 0.0
        warnings: List[str] = []
        notes: List[str] = []
        sources = self._sources_for_codes("dpr_115_2002")
        categoria_label = next((row["label"] for row in self.opzioni_contributo_unificato() if row["value"] == categoria), categoria)
        grado_label = {
            "primo_grado": "Primo grado",
            "appello": "Appello",
            "cassazione": "Cassazione",
        }.get(grado, "Primo grado")

        if categoria == "civile_ordinario":
            base = self._contributo_civile(valore)
            sources.extend(self._sources_for_codes("cu_viterbo"))
            if valore <= 0:
                notes.append("Valore non indicato: applicato il contributo previsto per causa di valore indeterminabile.")
        elif categoria == "decreto_ingiuntivo":
            base = round(self._contributo_civile(valore) / 2.0, 2)
            sources.extend(self._sources_for_codes("cu_viterbo"))
            notes.append("Per il decreto ingiuntivo il contributo e ridotto alla meta.")
        elif categoria == "volontaria_giurisdizione":
            base = self.norme.contributo_speciale("volontaria_giurisdizione", valore)
            notes.append("Importo fisso per volontaria giurisdizione, salvo ipotesi speciali o esenzioni.")
        elif categoria == "separazione_consensuale":
            base = self.norme.contributo_speciale("separazione_consensuale", valore)
            notes.append("Importo fisso per separazione consensuale o scioglimento congiunto, salvo casi esenti.")
        elif categoria == "tributario":
            base = self._contributo_tributario(valore)
            notes.append("Importo determinato per scaglione di valore del ricorso tributario.")
        elif categoria == "amministrativo_ordinario":
            base = self.norme.contributo_speciale("amministrativo_ordinario", valore)
            sources.extend(self._sources_for_codes("cu_admin"))
            notes.append("Ricorso amministrativo ordinario e risarcitorio per equivalente.")
        elif categoria == "amministrativo_rito_abbreviato":
            base = self.norme.contributo_speciale("amministrativo_rito_abbreviato", valore)
            sources.extend(self._sources_for_codes("cu_admin"))
        elif categoria == "amministrativo_appalti":
            sources.extend(self._sources_for_codes("cu_admin"))
            base = self.norme.contributo_speciale("amministrativo_appalti", valore)
        elif categoria == "amministrativo_ottemperanza":
            base = self.norme.contributo_speciale("amministrativo_ottemperanza", valore)
            sources.extend(self._sources_for_codes("cu_admin"))
        else:
            raise ValueError("Tipologia di contributo unificato non riconosciuta.")

        if grado == "appello" and categoria in {
            "civile_ordinario",
            "decreto_ingiuntivo",
            "volontaria_giurisdizione",
            "separazione_consensuale",
            "amministrativo_ordinario",
            "amministrativo_rito_abbreviato",
            "amministrativo_appalti",
            "amministrativo_ottemperanza",
        }:
            base = round(base * 1.5, 2)
            notes.append("Applicata la maggiorazione del 50% prevista per l'impugnazione.")
        elif grado == "cassazione" and categoria in {
            "civile_ordinario",
            "decreto_ingiuntivo",
            "volontaria_giurisdizione",
            "separazione_consensuale",
        }:
            base = round(base * 2.0, 2)
            notes.append("Applicato l'aumento del doppio previsto per il giudizio di legittimita.")
        elif grado == "cassazione":
            warnings.append("Per questa tipologia il calcolo automatico della Cassazione richiede una verifica puntuale dell'atto da iscrivere.")

        anticipazione = 27.0 if anticipazione_forfettaria and categoria in {
            "civile_ordinario",
            "decreto_ingiuntivo",
            "volontaria_giurisdizione",
            "separazione_consensuale",
        } else 0.0
        totale = round(base + anticipazione, 2)

        if categoria == "tributario":
            warnings.append("Verificare eventuali esenzioni o riduzioni processuali specifiche del caso tributario.")
        if categoria.startswith("amministrativo"):
            warnings.append("Nei ricorsi amministrativi speciali o nei riti super-speciali sono possibili importi diversi da quelli standard.")

        return {
            "categoria": categoria,
            "categoria_label": categoria_label,
            "grado": grado,
            "grado_label": grado_label,
            "valore": valore,
            "base": round(base, 2),
            "anticipazione_forfettaria": anticipazione,
            "totale": totale,
            "notes": notes,
            "warnings": warnings,
            "sources": list({source["url"]: source for source in sources}.values()),
        }

    def calcola_interessi(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        mode = _clean_text(payload.get("int_tipo") or payload.get("note_interessi_tipo")) or "legali"
        capitale = _safe_float(payload.get("int_capitale") or payload.get("note_capitale"))
        data_inizio = _parse_date(payload.get("int_data_inizio") or payload.get("note_data_inizio"))
        data_fine = _parse_date(payload.get("int_data_fine") or payload.get("note_data_fine"))

        if capitale <= 0:
            raise ValueError("Inserisci un capitale positivo.")
        if not data_inizio or not data_fine:
            raise ValueError("Inserisci una data iniziale e finale valide.")
        if data_fine < data_inizio:
            raise ValueError("La data finale deve essere successiva o uguale alla data iniziale.")

        periods: List[InterestPeriod] = self.norme.interest_periods(mode)
        label = "Interessi legali ex art. 1284 c.c." if mode == "legali" else "Interessi moratori ex D.Lgs. 231/2002"

        segments: List[Dict[str, Any]] = []
        warnings: List[str] = []
        sources: List[Dict[str, str]] = []
        total_interest = 0.0
        covered_days = 0

        for period in periods:
            overlap_start = max(data_inizio, period.start)
            overlap_end = min(data_fine, period.end)
            if overlap_start > overlap_end:
                continue
            days = _days_inclusive(overlap_start, overlap_end)
            denominator = _year_denominator(overlap_start)
            interest = round(capitale * (period.rate / 100.0) * (days / denominator), 2)
            total_interest += interest
            covered_days += days
            segments.append(
                {
                    "label": period.label,
                    "from": overlap_start.isoformat(),
                    "to": overlap_end.isoformat(),
                    "days": days,
                    "rate": period.rate,
                    "interest": interest,
                    "reference_rate": period.reference_rate,
                    "source": period.source.to_dict(),
                }
            )
            sources.append(period.source.to_dict())

        total_days = _days_inclusive(data_inizio, data_fine)
        if covered_days == 0:
            raise ValueError("Il periodo richiesto non e coperto dalle basi ufficiali attualmente indicate nel modulo.")
        if covered_days < total_days:
            warnings.append("Il periodo indicato e coperto solo parzialmente dalle tabelle ufficiali caricate: il risultato riguarda i giorni effettivamente mappati.")

        if mode == "mora_commerciale":
            warnings.append("Il tasso moratorio e calcolato come tasso BCE di riferimento maggiorato di 8 punti, salvo diverse pattuizioni valide nei limiti di legge.")

        return {
            "mode": mode,
            "label": label,
            "capital": round(capitale, 2),
            "start_date": data_inizio.isoformat(),
            "end_date": data_fine.isoformat(),
            "days": total_days,
            "covered_days": covered_days,
            "segments": segments,
            "total_interest": round(total_interest, 2),
            "total_amount": round(capitale + total_interest, 2),
            "notes": ["Calcolo pro-rata die su giorni effettivi con denominatore 365/366."],
            "warnings": warnings,
            "sources": list({source["url"]: source for source in sources}.values()),
        }

    def genera_nota_precisazione_credito(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        creditore = _clean_text(payload.get("note_creditore"))
        debitore = _clean_text(payload.get("note_debitore"))
        tribunale = _clean_text(payload.get("note_tribunale"))
        rg = _clean_text(payload.get("note_rg"))
        titolo = _clean_text(payload.get("note_titolo"))
        capitale = _safe_float(payload.get("note_capitale"))
        spese_vive = _safe_float(payload.get("note_spese_vive"))
        compensi = _safe_float(payload.get("note_compensi"))
        cpa_perc = _safe_float(payload.get("note_cpa_perc"), 4.0)
        iva_perc = _safe_float(payload.get("note_iva_perc"), 22.0)
        acconti = _safe_float(payload.get("note_acconti"))
        luogo = _clean_text(payload.get("note_luogo"))
        data_doc = _parse_date(payload.get("note_data")) or _today()
        avvocato = _clean_text(payload.get("note_avvocato"))
        tipo_interessi = _clean_text(payload.get("note_interessi_tipo")) or "manuale"
        interessi_manual = _safe_float(payload.get("note_interessi_manual"))

        if not creditore or not debitore:
            raise ValueError("Indica creditore e debitore per generare la nota.")
        if capitale <= 0:
            raise ValueError("Indica un capitale positivo.")

        interest_result = None
        interest_amount = interessi_manual
        sources: List[Dict[str, str]] = []
        warnings: List[str] = []
        if tipo_interessi in {"legali", "mora_commerciale"}:
            interest_result = self.calcola_interessi(
                {
                    "int_tipo": tipo_interessi,
                    "int_capitale": capitale,
                    "int_data_inizio": payload.get("note_data_inizio"),
                    "int_data_fine": payload.get("note_data_fine"),
                }
            )
            interest_amount = interest_result["total_interest"]
            sources.extend(interest_result["sources"])
            warnings.extend(interest_result["warnings"])
        elif interessi_manual < 0:
            raise ValueError("Gli interessi manuali non possono essere negativi.")

        cpa = round(compensi * (cpa_perc / 100.0), 2)
        iva = round((compensi + cpa) * (iva_perc / 100.0), 2)
        totale_lordo = round(capitale + interest_amount + spese_vive + compensi + cpa + iva, 2)
        residuo = round(totale_lordo - acconti, 2)

        breakdown = [
            ("Capitale", capitale),
            ("Interessi", interest_amount),
            ("Spese vive documentate", spese_vive),
            ("Compensi professionali", compensi),
            (f"CPA {_fmt_percent(cpa_perc)}%", cpa),
            (f"IVA {_fmt_percent(iva_perc)}%", iva),
            ("Totale maturato", totale_lordo),
            ("Acconti / pagamenti imputati", -acconti),
            ("Residuo richiesto", residuo),
        ]

        intro = "interessi legali ex art. 1284 c.c."
        if tipo_interessi == "mora_commerciale":
            intro = "interessi moratori ex D.Lgs. 231/2002"
        elif tipo_interessi == "manuale":
            intro = "interessi indicati manualmente"

        rendered_text = dedent(
            f"""
            {tribunale or 'TRIBUNALE COMPETENTE'}
            {f'R.G. n. {rg}' if rg else ''}
            NOTA DI PRECISAZIONE DEL CREDITO

            Per: {creditore}
            Contro: {debitore}

            Il sottoscritto difensore precisa il credito maturato in relazione a: {titolo or 'rapporto obbligatorio / credito azionato'}.

            1) Capitale: Euro {_fmt_money(capitale)}
            2) Interessi ({intro}): Euro {_fmt_money(interest_amount)}
            3) Spese vive documentate: Euro {_fmt_money(spese_vive)}
            4) Compensi professionali: Euro {_fmt_money(compensi)}
            5) CPA {_fmt_percent(cpa_perc)}%: Euro {_fmt_money(cpa)}
            6) IVA {_fmt_percent(iva_perc)}%: Euro {_fmt_money(iva)}
               Totale maturato: Euro {_fmt_money(totale_lordo)}
               Acconti / pagamenti imputati: Euro {_fmt_money(acconti)}
               Residuo richiesto: Euro {_fmt_money(residuo)}

            Si chiede che il credito venga ammesso / liquidato nella misura sopra precisata, oltre agli ulteriori accessori di legge maturandi sino al soddisfo.

            {luogo or 'Luogo'}, {data_doc.strftime('%d/%m/%Y')}
            {avvocato or 'Avv. ____________________'}
            """
        ).strip()

        def _line_html(label: str, amount: float, strong: bool = False) -> str:
            amount_html = html.escape(_fmt_money(amount))
            label_html = html.escape(label)
            tag = "strong" if strong else "span"
            return f"<div class='d-flex justify-content-between gap-3'><span>{label_html}</span><{tag}>Euro {amount_html}</{tag}></div>"

        rendered_html = (
            "<div class='document-prose'>"
            f"<p class='text-uppercase fw-semibold mb-1'>{html.escape(tribunale or 'Tribunale competente')}</p>"
            + (f"<p class='small text-muted mb-3'>R.G. n. {html.escape(rg)}</p>" if rg else "")
            + "<h3 class='h5 text-uppercase mb-3'>Nota di precisazione del credito</h3>"
            + f"<p><strong>Per:</strong> {html.escape(creditore)}<br><strong>Contro:</strong> {html.escape(debitore)}</p>"
            + f"<p>Il sottoscritto difensore precisa il credito maturato in relazione a <strong>{html.escape(titolo or 'rapporto obbligatorio / credito azionato')}</strong>.</p>"
            + "<div class='border rounded-4 p-3 bg-light-subtle'>"
            + _line_html("Capitale", capitale)
            + _line_html("Interessi", interest_amount)
            + _line_html("Spese vive documentate", spese_vive)
            + _line_html("Compensi professionali", compensi)
            + _line_html(f"CPA {_fmt_percent(cpa_perc)}%", cpa)
            + _line_html(f"IVA {_fmt_percent(iva_perc)}%", iva)
            + "<hr class='my-2'>"
            + _line_html("Totale maturato", totale_lordo, strong=True)
            + _line_html("Acconti / pagamenti imputati", -acconti)
            + _line_html("Residuo richiesto", residuo, strong=True)
            + "</div>"
            + "<p class='mt-3 mb-0'>Si chiede che il credito venga ammesso / liquidato nella misura sopra precisata, oltre agli ulteriori accessori di legge maturandi sino al soddisfo.</p>"
            + f"<p class='mt-4'>{html.escape(luogo or 'Luogo')}, {data_doc.strftime('%d/%m/%Y')}<br>{html.escape(avvocato or 'Avv. ____________________')}</p>"
            + "</div>"
        )

        return {
            "creditore": creditore,
            "debitore": debitore,
            "tribunale": tribunale,
            "rg": rg,
            "titolo": titolo,
            "breakdown": [{"label": label, "amount": amount} for label, amount in breakdown],
            "interest_mode": tipo_interessi,
            "interest_result": interest_result,
            "totale_lordo": totale_lordo,
            "acconti": acconti,
            "residuo": residuo,
            "warnings": warnings,
            "sources": list({source["url"]: source for source in sources}.values()),
            "rendered_text": rendered_text,
            "rendered_html": rendered_html,
        }

    def simula_pignoramento(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        tipo_reddito = _clean_text(payload.get("pig_tipo_reddito")) or "stipendio"
        tipo_credito = _clean_text(payload.get("pig_tipo_credito")) or "ordinario"
        importo = _safe_float(payload.get("pig_importo_netto"))
        aliquota_alimentare = _safe_float(payload.get("pig_aliquota_alimentare"), 33.33)

        if importo <= 0:
            raise ValueError("Indica un importo netto mensile positivo.")

        warnings: List[str] = []
        rules = self.norme.pignoramento_rules()
        assegno_sociale = self.norme.assegno_sociale(2026)
        sources = self._sources_for_codes("art_545_cpc", "assegno_sociale_2026")
        base_pignorabile = importo
        minimo_protetto = 0.0

        if tipo_reddito == "pensione":
            minimo_protetto = round(assegno_sociale * float(rules["pensione_minimo_multiplier"]["value"]), 2)
            base_pignorabile = max(0.0, importo - minimo_protetto)
            if base_pignorabile == 0:
                warnings.append("L'importo indicato e interamente assorbito dal minimo vitale pensionistico 2026.")

        if tipo_credito == "ordinario":
            aliquota = float(rules["ordinario_quota"]["value"])
        elif tipo_credito == "esattoriale":
            sources.extend(self._sources_for_codes("dpr_602_1973"))
            if importo <= 2500:
                aliquota = float(rules["esattoriale_fino_2500"]["value"])
            elif importo <= 5000:
                aliquota = float(rules["esattoriale_fino_5000"]["value"])
            else:
                aliquota = float(rules["esattoriale_oltre_5000"]["value"])
        elif tipo_credito == "alimentare":
            aliquota = aliquota_alimentare or float(rules["alimentare_default"]["value"])
            warnings.append("Per i crediti alimentari la misura concreta resta rimessa al provvedimento del giudice.")
        else:
            raise ValueError("Tipologia di credito non riconosciuta.")

        quota = round(base_pignorabile * (aliquota / 100.0), 2)
        residuo = round(importo - quota, 2)
        warnings.append("Il simulatore non considera cessioni del quinto, delegazioni di pagamento o pignoramenti concorrenti gia esistenti.")

        return {
            "tipo_reddito": tipo_reddito,
            "tipo_reddito_label": "Pensione" if tipo_reddito == "pensione" else "Stipendio",
            "tipo_credito": tipo_credito,
            "tipo_credito_label": {
                "ordinario": "Credito ordinario",
                "esattoriale": "Credito esattoriale",
                "alimentare": "Credito alimentare",
            }.get(tipo_credito, tipo_credito),
            "importo": round(importo, 2),
            "minimo_protetto": minimo_protetto,
            "base_pignorabile": round(base_pignorabile, 2),
            "aliquota": round(aliquota, 4),
            "quota_massima": quota,
            "residuo": residuo,
            "warnings": warnings,
            "sources": sources,
        }

    def calcola_ctu(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        modalita = _clean_text(payload.get("ctu_modalita")) or "vacazioni"
        ore = _safe_float(payload.get("ctu_ore"))
        vacazioni_input = _safe_int(payload.get("ctu_vacazioni"))
        onorario_manuale = _safe_float(payload.get("ctu_onorario"))
        spese = _safe_float(payload.get("ctu_spese"))
        cpa_perc = _safe_float(payload.get("ctu_cpa_perc"), 4.0)
        iva_perc = _safe_float(payload.get("ctu_iva_perc"), 22.0)

        warnings: List[str] = []
        sources = self._sources_for_codes("l_319_1980", "dm_30_05_2002")
        vacazioni_cfg = self.norme.ctu_vacazioni()

        vacazioni = vacazioni_input
        onorario_base = onorario_manuale
        notes: List[str] = []
        if modalita == "vacazioni":
            if vacazioni <= 0 and ore > 0:
                vacazioni = max(1, math.ceil(ore / 2.0))
                notes.append("Numero vacazioni ricavato arrotondando per eccesso ogni blocco di due ore.")
            if vacazioni <= 0:
                raise ValueError("Indica le ore o il numero di vacazioni da liquidare.")
            onorario_base = vacazioni_cfg["prima"] + max(vacazioni - 1, 0) * vacazioni_cfg["successiva"]
            onorario_base = round(onorario_base, 2)
            warnings.append("Molti incarichi CTU seguono criteri tabellari specifici del D.P.R. 115/2002: qui e automatizzata la sola logica a vacazione / liquidazione manuale.")
        elif modalita == "manuale":
            if onorario_base <= 0:
                raise ValueError("Indica un onorario base per il calcolo manuale.")
            warnings.append("Compenso manuale: verifica sempre il criterio di liquidazione fissato dal giudice o dalla norma speciale.")
        else:
            raise ValueError("Modalita CTU non riconosciuta.")

        cpa = round(onorario_base * (cpa_perc / 100.0), 2)
        iva = round((onorario_base + cpa) * (iva_perc / 100.0), 2)
        totale = round(onorario_base + spese + cpa + iva, 2)

        return {
            "modalita": modalita,
            "modalita_label": "Liquidazione a vacazioni" if modalita == "vacazioni" else "Liquidazione manuale",
            "ore": ore,
            "vacazioni": vacazioni,
            "onorario_base": round(onorario_base, 2),
            "spese": round(spese, 2),
            "cpa": cpa,
            "iva": iva,
            "totale": totale,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    # ── Nuovi strumenti intelligenti ─────────────────────────────────────────

    def calcola_rivalutazione_istat(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Rivalutazione monetaria con indici ISTAT FOI o NIC."""
        importo = _safe_float(payload.get("riv_importo"))
        tipo = _clean_text(payload.get("riv_tipo") or "nic").lower()
        if tipo not in ("foi", "nic"):
            tipo = "nic"
        anno_base = _safe_int(payload.get("riv_anno_base"))
        mese_base = _safe_int(payload.get("riv_mese_base"))
        anno_fine = _safe_int(payload.get("riv_anno_fine"))
        mese_fine = _safe_int(payload.get("riv_mese_fine"))

        if importo <= 0:
            raise ValueError("Inserisci un importo positivo.")
        if not (anno_base and mese_base):
            raise ValueError("Indica anno e mese di riferimento base.")
        if not (anno_fine and mese_fine):
            raise ValueError("Indica anno e mese di rivalutazione finale.")
        if not (1 <= mese_base <= 12) or not (1 <= mese_fine <= 12):
            raise ValueError("Il mese deve essere compreso tra 1 e 12.")

        indice_base = self.norme.istat_index(tipo, anno_base, mese_base)
        indice_fine = self.norme.istat_index(tipo, anno_fine, mese_fine)

        tipo_label = "FOI (famiglie di operai e impiegati)" if tipo == "foi" else "NIC (intera collettivita nazionale)"
        source_code = "istat_indici_prezzi"
        sources = self._sources_for_codes(source_code, "istat_portale")
        warnings: List[str] = []
        notes: List[str] = []

        if indice_base is None:
            last = self.norme.istat_last_available(tipo)
            raise ValueError(
                f"Indice ISTAT {tipo.upper()} non disponibile per {mese_base:02d}/{anno_base}. "
                f"Dati disponibili fino a {last.get('month', '?'):02d}/{last.get('year', '?') if last else '?'}. "
                f"Aggiorna la tabella normativa {tipo.upper()} da /legal-intelligence."
            )
        if indice_fine is None:
            last = self.norme.istat_last_available(tipo)
            raise ValueError(
                f"Indice ISTAT {tipo.upper()} non disponibile per {mese_fine:02d}/{anno_fine}. "
                f"Dati disponibili fino a {last.get('month', '?'):02d}/{last.get('year', '?') if last else '?'}. "
                f"Aggiorna la tabella normativa {tipo.upper()} da /legal-intelligence."
            )

        variazione_perc = round(((indice_fine / indice_base) - 1) * 100, 4)
        importo_rivalutato = round(importo * (indice_fine / indice_base), 2)
        differenza = round(importo_rivalutato - importo, 2)

        mesi = {1:"gennaio",2:"febbraio",3:"marzo",4:"aprile",5:"maggio",6:"giugno",
                7:"luglio",8:"agosto",9:"settembre",10:"ottobre",11:"novembre",12:"dicembre"}
        notes.append(
            f"Formula: {importo:,.2f} × ({indice_fine} / {indice_base}) = {importo_rivalutato:,.2f} EUR."
        )
        notes.append(
            f"Indici ISTAT {tipo.upper()} base 2015=100: "
            f"{mesi.get(mese_base,mese_base)}/{anno_base} = {indice_base}, "
            f"{mesi.get(mese_fine,mese_fine)}/{anno_fine} = {indice_fine}."
        )
        if tipo == "nic":
            notes.append("Indice NIC: rivalutazione monetaria generale, assegni divorzili (art. 9 L. 898/1970), liquidazioni.")
        else:
            notes.append("Indice FOI (al netto dei tabacchi): adeguamento canoni locazione (L. 431/1998 art. 24, L. 392/1978).")

        if variazione_perc < 0:
            warnings.append("La variazione e negativa (deflazione nel periodo): l'importo rivalutato e inferiore a quello originale.")

        return {
            "importo_originale": round(importo, 2),
            "importo_rivalutato": importo_rivalutato,
            "differenza": differenza,
            "variazione_perc": variazione_perc,
            "indice_base": indice_base,
            "indice_fine": indice_fine,
            "tipo": tipo,
            "tipo_label": tipo_label,
            "anno_base": anno_base,
            "mese_base": mese_base,
            "anno_fine": anno_fine,
            "mese_fine": mese_fine,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    def calcola_adeguamento_canone(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Adeguamento annuale del canone di locazione con indice ISTAT FOI (L. 431/1998)."""
        canone = _safe_float(payload.get("loc_canone"))
        perc_adeguamento = _safe_float(payload.get("loc_perc_adeguamento"), 75.0)
        anno_base = _safe_int(payload.get("loc_anno_base"))
        mese_base = _safe_int(payload.get("loc_mese_base"))
        anno_fine = _safe_int(payload.get("loc_anno_fine"))
        mese_fine = _safe_int(payload.get("loc_mese_fine"))

        if canone <= 0:
            raise ValueError("Inserisci un canone mensile positivo.")
        if not (anno_base and mese_base):
            raise ValueError("Indica anno e mese di stipula o ultimo aggiornamento.")
        if not (anno_fine and mese_fine):
            raise ValueError("Indica anno e mese di calcolo aggiornamento.")
        if not (1 <= mese_base <= 12) or not (1 <= mese_fine <= 12):
            raise ValueError("Il mese deve essere compreso tra 1 e 12.")
        if not (0 < perc_adeguamento <= 100):
            perc_adeguamento = 75.0

        indice_base = self.norme.istat_index("foi", anno_base, mese_base)
        indice_fine = self.norme.istat_index("foi", anno_fine, mese_fine)
        sources = self._sources_for_codes("istat_indici_prezzi", "legge_431_1998_locazioni")
        warnings: List[str] = []
        notes: List[str] = []

        if indice_base is None or indice_fine is None:
            last = self.norme.istat_last_available("foi")
            last_label = f"{last.get('month', '?'):02d}/{last.get('year', '?')}" if last else "n/d"
            raise ValueError(
                f"Indici ISTAT FOI non disponibili per il periodo indicato (dati fino a {last_label}). "
                "Aggiorna la tabella da /legal-intelligence."
            )

        variazione_foi = round(((indice_fine / indice_base) - 1) * 100, 4)
        variazione_applicata = round(variazione_foi * perc_adeguamento / 100.0, 4)
        incremento = round(canone * variazione_applicata / 100.0, 2)
        canone_aggiornato = round(canone + incremento, 2)
        canone_annuo = round(canone * 12, 2)
        canone_annuo_aggiornato = round(canone_aggiornato * 12, 2)

        mesi = {1:"gen",2:"feb",3:"mar",4:"apr",5:"mag",6:"giu",
                7:"lug",8:"ago",9:"set",10:"ott",11:"nov",12:"dic"}
        notes.append(
            f"Variazione FOI {mesi.get(mese_base)}/{anno_base}→{mesi.get(mese_fine)}/{anno_fine}: "
            f"{variazione_foi:+.2f}% × {perc_adeguamento:.0f}% = {variazione_applicata:+.2f}% applicato."
        )
        notes.append(
            f"Formula: {canone:.2f} + ({canone:.2f} × {variazione_applicata:.4f}/100) = {canone_aggiornato:.2f} EUR/mese."
        )
        if perc_adeguamento == 75.0:
            notes.append("Contratti liberi 4+4 (L. 431/1998 art. 1): aggiornamento al 75% della variazione FOI. Verificare il testo contrattuale.")
        elif perc_adeguamento == 100.0:
            notes.append("Applicato il 100% della variazione FOI (contratti ad uso transitorio o patto specifico).")

        if variazione_foi < 0:
            warnings.append("La variazione FOI e negativa: il canone non puo essere ridotto in applicazione dell'adeguamento (salvo patto contrario).")

        return {
            "canone_originale": round(canone, 2),
            "canone_aggiornato": canone_aggiornato,
            "incremento_mensile": incremento,
            "canone_annuo": canone_annuo,
            "canone_annuo_aggiornato": canone_annuo_aggiornato,
            "variazione_foi": variazione_foi,
            "variazione_applicata": variazione_applicata,
            "perc_adeguamento": perc_adeguamento,
            "indice_base": indice_base,
            "indice_fine": indice_fine,
            "anno_base": anno_base,
            "mese_base": mese_base,
            "anno_fine": anno_fine,
            "mese_fine": mese_fine,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    def verifica_soglia_usura(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Verifica se un tasso applicato supera la soglia antiusura (L. 108/1996)."""
        tasso_applicato = _safe_float(payload.get("usura_tasso"))
        categoria = _clean_text(payload.get("usura_categoria") or "credito_personale")
        data_operazione = _parse_date(payload.get("usura_data")) or _today()

        if tasso_applicato < 0:
            raise ValueError("Inserisci un tasso percentuale non negativo.")

        soglia_data = self.norme.usura_soglia_per_categoria(categoria, data_operazione)
        categorie_disponibili = self.norme.usura_categorie()
        sources = self._sources_for_codes("legge_108_1996_usura", "bancaditalia_tassi_usura", "mef_decreto_usura")
        warnings: List[str] = []
        notes: List[str] = []

        if not soglia_data:
            categorie_labels = [f"{c['category']} — {c['label']}" for c in categorie_disponibili]
            raise ValueError(
                f"Categoria '{categoria}' non trovata nella tabella usura. "
                f"Categorie disponibili: {', '.join(categorie_labels[:5])}."
            )

        tegm = float(soglia_data.get("tegm", 0.0))
        soglia = float(soglia_data.get("soglia", 0.0))
        categoria_label = soglia_data.get("label", categoria)
        quarter = soglia_data.get("quarter", "")

        supera_soglia = tasso_applicato > soglia
        margine = round(soglia - tasso_applicato, 4)
        esito = "USURARIO" if supera_soglia else "REGOLARE"
        esito_classe = "danger" if supera_soglia else "success"

        notes.append(
            f"TEGM {quarter}: {tegm:.2f}%. Soglia = {tegm:.2f}% × 1,25 + 4 = {soglia:.2f}%."
        )
        notes.append(
            f"Tasso applicato {tasso_applicato:.2f}% {'SUPERA' if supera_soglia else 'rispetta'} la soglia antiusura di {soglia:.2f}%."
        )

        if supera_soglia:
            eccesso = round(tasso_applicato - soglia, 4)
            warnings.append(
                f"Il tasso applicato ({tasso_applicato:.2f}%) supera la soglia usura ({soglia:.2f}%) "
                f"di {eccesso:.2f} punti. Rischio nullita della clausola ex art. 1815 c.c. e L. 108/1996."
            )
        else:
            notes.append(
                f"Margine rispetto alla soglia: {abs(margine):.2f} punti percentuali sotto il limite."
            )

        notes.append(
            "L. 108/1996 come mod. D.L. 70/2011: soglia = TEGM × 1,25 + 4 pp. "
            "Verificare sempre il TEGM vigente al momento della stipula del contratto."
        )

        # Tutte le categorie per confronto
        categorie_rows = [
            {
                "category": c["category"],
                "label": c["label"],
                "tegm": float(c.get("tegm", 0)),
                "soglia": float(c.get("soglia", 0)),
                "is_selected": c["category"] == categoria,
            }
            for c in categorie_disponibili
        ]

        return {
            "tasso_applicato": tasso_applicato,
            "categoria": categoria,
            "categoria_label": categoria_label,
            "tegm": tegm,
            "soglia": soglia,
            "quarter": quarter,
            "supera_soglia": supera_soglia,
            "margine": margine,
            "esito": esito,
            "esito_classe": esito_classe,
            "categorie": categorie_rows,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    def calcola_contributi_cassa_forense(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Calcola contributi Cassa Forense per l'anno e i dati reddituali indicati."""
        anno = _safe_int(payload.get("cf_anno")) or _today().year
        reddito = _safe_float(payload.get("cf_reddito"))
        compensi = _safe_float(payload.get("cf_compensi"))

        contributi = self.norme.contributi_cassa_forense_anno(anno)
        sources = self._sources_for_codes("cassa_forense_portale", "cassa_forense_contributi_2026", "cassa_forense_art11")
        warnings: List[str] = []
        notes: List[str] = []

        if not contributi:
            raise ValueError(
                f"Dati Cassa Forense non disponibili per il {anno}. "
                "Aggiorna la tabella da /legal-intelligence."
            )

        rows_anno = contributi
        result_rows: List[Dict[str, Any]] = []
        totale = 0.0

        for r in rows_anno:
            tipo = r.get("tipo", "")
            aliquota = float(r.get("aliquota", 0.0))
            minimo = float(r.get("minimo_eur", 0.0))
            label = r.get("label", tipo)
            note_row = r.get("note", "")
            base = r.get("base", "")
            calcolato = 0.0
            base_usata = 0.0

            if tipo == "soggettivo" and reddito > 0:
                base_usata = reddito
                calcolato = round(reddito * aliquota / 100.0, 2)
                if calcolato < minimo:
                    notes.append(f"{label}: calcolato {calcolato:.2f} EUR < minimo {minimo:.2f} EUR → applicato il minimo.")
                    calcolato = minimo
            elif tipo == "integrativo" and compensi > 0:
                base_usata = compensi
                calcolato = round(compensi * aliquota / 100.0, 2)
                if calcolato < minimo:
                    notes.append(f"{label}: calcolato {calcolato:.2f} EUR < minimo {minimo:.2f} EUR → applicato il minimo.")
                    calcolato = minimo
            elif tipo == "maternita_assistenza":
                calcolato = minimo
                base_usata = 0.0
            elif tipo == "soggettivo" and reddito <= 0:
                calcolato = minimo
                notes.append(f"{label}: reddito non indicato, applicato il minimo di iscrizione {minimo:.2f} EUR.")
            elif tipo == "integrativo" and compensi <= 0:
                calcolato = minimo
                notes.append(f"{label}: compensi non indicati, applicato il minimo {minimo:.2f} EUR.")

            totale += calcolato
            result_rows.append({
                "tipo": tipo,
                "label": label,
                "aliquota": aliquota,
                "minimo_eur": minimo,
                "base_usata": round(base_usata, 2),
                "calcolato": round(calcolato, 2),
                "base": base,
                "note": note_row,
            })

        # Nota su contributo integrativo (addebitabile al cliente)
        integrativo = next((r for r in result_rows if r["tipo"] == "integrativo"), None)
        if integrativo:
            notes.append(
                f"Il contributo integrativo ({integrativo['aliquota']:.0f}%) e addebitabile al cliente "
                "in aggiunta al compenso ex art. 11 L. 576/1980."
            )
        notes.append(
            "Scadenza dichiarazione e pagamento: 31 ottobre dell'anno successivo (Cassa Forense). "
            "Verificare eventuali rateizzazioni o esoneri previsti dal regolamento vigente."
        )

        return {
            "anno": anno,
            "reddito": round(reddito, 2),
            "compensi": round(compensi, 2),
            "contributi": result_rows,
            "totale": round(totale, 2),
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    # ------------------------------------------------------------------ #
    #  NUOVO — Calcolo termini di prescrizione                           #
    # ------------------------------------------------------------------ #
    _TIPI_PRESCRIZIONE: Dict[str, Dict] = {
        "ordinaria_10": {
            "label": "Ordinaria — 10 anni",
            "anni": 10,
            "norma": "Art. 2946 c.c.",
            "esempi": "Crediti contrattuali generici, risarcimento danni da reato (se non speciale), azioni reali.",
        },
        "quinquennale_5": {
            "label": "Quinquennale — 5 anni",
            "anni": 5,
            "norma": "Art. 2948 c.c.",
            "esempi": "Canoni di locazione, rate, stipendi, corrispettivi periodici.",
        },
        "extracontrattuale_5": {
            "label": "Extracontrattuale — 5 anni",
            "anni": 5,
            "norma": "Art. 2947 c.c.",
            "esempi": "Risarcimento del danno da fatto illecito (lesioni, danni a cose).",
        },
        "cambiari_3": {
            "label": "Cambiali e assegni — 3 anni",
            "anni": 3,
            "norma": "Art. 94 L.C. / Art. 52 L.A.",
            "esempi": "Azione cartolare del portatore vs traente cambiale; assegni bancari.",
        },
        "assicurazioni_2": {
            "label": "Assicurazioni — 2 anni",
            "anni": 2,
            "norma": "Art. 2952 c.c.",
            "esempi": "Diritti derivanti dal contratto di assicurazione (vita: 10 anni).",
        },
        "breve_1": {
            "label": "Breve — 1 anno",
            "anni": 1,
            "norma": "Art. 2951 c.c.",
            "esempi": "Diritti derivanti da contratto di spedizione, di trasporto, vettori.",
        },
    }

    def calcola_prescrizione(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Calcola termini di prescrizione con gestione atti interruttivi."""
        from datetime import date as _date, timedelta
        import calendar as _calendar

        tipo = str(payload.get("presc_tipo", "ordinaria_10")).strip()
        data_decorrenza_raw = payload.get("presc_data_decorrenza", "")
        data_atto_raw = payload.get("presc_atto_interruttivo", "")
        descrizione = _clean_text(payload.get("presc_descrizione", ""))

        tipo_info = self._TIPI_PRESCRIZIONE.get(tipo)
        if not tipo_info:
            raise ValueError(f"Tipo di prescrizione non riconosciuto: {tipo!r}.")

        data_decorrenza = _parse_date(data_decorrenza_raw)
        if not data_decorrenza:
            raise ValueError("Indica la data di decorrenza (dies a quo).")

        anni = tipo_info["anni"]
        oggi = _today()

        def _add_years(d: _date, n: int) -> _date:
            try:
                return d.replace(year=d.year + n)
            except ValueError:
                # 29 feb su anno non bisestile
                return d.replace(year=d.year + n, day=28)

        data_scadenza = _add_years(data_decorrenza, anni)
        giorni_residui = (data_scadenza - oggi).days
        scaduta = oggi > data_scadenza

        # Atto interruttivo
        data_atto = _parse_date(data_atto_raw)
        data_scadenza_post = None
        giorni_residui_post = None
        if data_atto:
            data_scadenza_post = _add_years(data_atto, anni)
            giorni_residui_post = (data_scadenza_post - oggi).days

        # Calcola scadenza effettiva (con o senza interruzione)
        scadenza_eff = data_scadenza_post if data_atto else data_scadenza
        giorni_eff = giorni_residui_post if data_atto else giorni_residui
        scaduta_eff = oggi > scadenza_eff if scadenza_eff else scaduta

        warnings: List[str] = []
        notes: List[str] = []

        if scaduta_eff:
            warnings.append("⚠ Il termine di prescrizione risulta SCADUTO in base ai dati inseriti.")
        elif giorni_eff is not None and giorni_eff < 90:
            warnings.append(f"⚠ URGENTE — il termine scade tra {giorni_eff} giorni ({scadenza_eff.strftime('%d/%m/%Y')}). Valuta tempestivamente atti interruttivi.")

        notes.append(tipo_info["esempi"])
        notes.append(
            "La prescrizione si interrompe con qualsiasi atto idoneo: notifica citazione, decreto ingiuntivo, "
            "diffida raccomandata AR, riconoscimento del debitore, PEC con valore legale. "
            "Dalla data dell'atto interruttivo ricomincia a decorrere un nuovo termine integrale."
        )
        if tipo == "extracontrattuale_5":
            notes.append(
                "Se il fatto illecito costituisce reato, la prescrizione è quella del reato se più lunga "
                "(art. 2947 co. 3 c.c.)."
            )

        sources = [
            {"title": tipo_info["norma"], "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262"},
        ]

        return {
            "tipo": tipo,
            "tipo_label": tipo_info["label"],
            "norma": tipo_info["norma"],
            "anni_prescrizione": anni,
            "data_decorrenza": data_decorrenza.isoformat(),
            "data_scadenza": data_scadenza.isoformat(),
            "giorni_residui": giorni_residui,
            "data_atto_interruttivo": data_atto.isoformat() if data_atto else None,
            "data_scadenza_post_interruzione": data_scadenza_post.isoformat() if data_scadenza_post else None,
            "giorni_residui_post_interruzione": giorni_residui_post,
            "scaduta": scaduta_eff,
            "urgente": (not scaduta_eff and giorni_eff is not None and giorni_eff < 90),
            "descrizione": descrizione,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    # ------------------------------------------------------------------ #
    #  NUOVO — Liquidazione danno biologico (Tabelle Milano 2024)         #
    # ------------------------------------------------------------------ #
    # Valore del punto per IP% (per fascia), età base 30 anni, anno 2024.
    # Fonte: Osservatorio per la giustizia civile di Milano, aggiornamento 2024.
    _PUNTI_IP_FASCIA: List[tuple] = [
        (5,   5_797),
        (10,  6_482),
        (20,  7_164),
        (30,  8_513),
        (40, 10_261),
        (50, 12_439),
        (60, 14_618),
        (70, 17_484),
        (80, 20_349),
        (90, 24_562),
        (100,29_462),
    ]
    _VALORE_GIORNO_ITT: float = 103.0    # € per giorno ITT (2024)
    _COEFF_ITP: Dict[int, float] = {75: 0.75, 50: 0.50, 25: 0.25}

    def _valore_punto_ip(self, percentuale: int) -> float:
        for limite, valore in self._PUNTI_IP_FASCIA:
            if percentuale <= limite:
                return float(valore)
        return float(self._PUNTI_IP_FASCIA[-1][1])

    def _coeff_eta(self, eta: int) -> float:
        """Coefficiente correttivo per età (±0,5% per anno rispetto a 30)."""
        if eta <= 20:
            return 1.30
        elif eta <= 25:
            return 1.20
        elif eta <= 30:
            return 1.10
        elif eta <= 35:
            return 1.00
        elif eta <= 40:
            return 0.95
        elif eta <= 45:
            return 0.90
        elif eta <= 50:
            return 0.85
        elif eta <= 55:
            return 0.80
        elif eta <= 60:
            return 0.75
        elif eta <= 65:
            return 0.70
        elif eta <= 70:
            return 0.65
        else:
            return 0.60

    def calcola_danno_biologico(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Liquidazione danno biologico con Tabelle Milano 2024."""
        eta = _safe_int(payload.get("db_eta"))
        perc_ip = _safe_int(payload.get("db_perc_ip"))
        giorni_itt = _safe_int(payload.get("db_giorni_itt"))
        giorni_itp = _safe_int(payload.get("db_giorni_itp"))
        perc_itp = _safe_int(payload.get("db_perc_itp", 50))
        personalizzazione = _safe_float(payload.get("db_personalizzazione", 0))
        includi_morale = str(payload.get("db_includi_morale", "1")).strip() == "1"

        warnings: List[str] = []
        notes: List[str] = []

        if eta <= 0 or eta > 120:
            raise ValueError("Indica l'età della vittima al momento del fatto.")
        if not (0 <= perc_ip <= 100):
            raise ValueError("La percentuale di invalidità permanente deve essere tra 0 e 100.")
        if perc_itp not in (25, 50, 75):
            perc_itp = 50

        coeff = self._coeff_eta(eta)

        # Danno biologico per IP
        danno_ip = 0.0
        if perc_ip > 0:
            for p in range(1, perc_ip + 1):
                danno_ip += self._valore_punto_ip(p) * coeff
        danno_ip = round(danno_ip, 2)

        # Danno biologico temporaneo
        valore_itt = round(giorni_itt * self._VALORE_GIORNO_ITT, 2)
        coeff_itp = self._COEFF_ITP.get(perc_itp, 0.50)
        valore_itp = round(giorni_itp * self._VALORE_GIORNO_ITT * coeff_itp, 2)

        subtotale = round(danno_ip + valore_itt + valore_itp, 2)

        # Personalizzazione (max +25% di norma)
        personalizzazione = max(0.0, min(personalizzazione, 50.0))
        importo_personalizzazione = round(subtotale * personalizzazione / 100.0, 2)

        totale_biologico = round(subtotale + importo_personalizzazione, 2)

        # Danno morale (liquidazione autonoma — c.d. Sezioni Unite 2008 + Cass. 2019)
        danno_morale = round(totale_biologico * 0.25, 2) if includi_morale else 0.0
        totale_comprensivo = round(totale_biologico + danno_morale, 2)

        if perc_ip >= 10:
            notes.append(
                "Per lesioni macro-permanenti (IP ≥ 10%) il danno morale si liquida autonomamente "
                "in misura orientativamente pari al 25-50% del danno biologico (Cass. SS.UU. 26972/2008; Cass. 7513/2018)."
            )
        notes.append(
            "Valori calcolati con le Tabelle di Milano 2024 (approssimazione operativa). "
            "Il coefficiente età è calcolato su base 30 anni (±0,5%/anno). "
            "La personalizzazione (0-25%) va giustificata con specifiche circostanze del caso concreto."
        )
        if personalizzazione > 25:
            warnings.append("La personalizzazione supera il 25%: le Tabelle di Milano la prevedono in via eccezionale e motivata.")

        sources = [
            {"title": "Tabelle Milano 2024", "url": "https://www.tribunale.milano.it/tabelle-di-liquidazione-del-danno"},
            {"title": "Cass. SS.UU. 26972/2008", "url": "https://www.normattiva.it"},
        ]

        return {
            "eta": eta,
            "perc_ip": perc_ip,
            "giorni_itt": giorni_itt,
            "giorni_itp": giorni_itp,
            "perc_itp": perc_itp,
            "coeff_eta": round(coeff, 2),
            "danno_ip": danno_ip,
            "valore_giorno_itt": self._VALORE_GIORNO_ITT,
            "valore_itt": valore_itt,
            "valore_itp": valore_itp,
            "subtotale": subtotale,
            "personalizzazione_pct": personalizzazione,
            "importo_personalizzazione": importo_personalizzazione,
            "totale_biologico": totale_biologico,
            "includi_morale": includi_morale,
            "danno_morale": danno_morale,
            "totale_comprensivo": totale_comprensivo,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    # ------------------------------------------------------------------ #
    #  NUOVO — Imposta di registro atti giudiziari (DPR 131/1986)         #
    # ------------------------------------------------------------------ #
    _TIPI_ATTO_REGISTRO: Dict[str, Dict] = {
        "sentenza_condanna": {
            "label": "Sentenza di condanna (civile/penale)",
            "aliquota": 0.03,
            "minimo": 200.0,
            "fisso": False,
            "norma": "Art. 8 co. 1 lett. a) Tariffa DPR 131/1986",
            "note": "Aliquota del 3% sul valore della condanna. Obbligo di registrazione entro 20 giorni dalla irrevocabilità.",
        },
        "sentenza_immobili": {
            "label": "Sentenza su trasferimento immobili",
            "aliquota": 0.09,
            "minimo": 1_000.0,
            "fisso": False,
            "norma": "Art. 1 Tariffa DPR 131/1986 (2ª parte), richiamo art. 8",
            "note": "Per sentenze costitutive di diritti reali su immobili l'aliquota è quella dell'atto (9% su abitazioni, 12% su terreni agricoli).",
        },
        "decreto_ingiuntivo": {
            "label": "Decreto ingiuntivo",
            "aliquota": 0.0,
            "minimo": 200.0,
            "fisso": True,
            "norma": "Art. 8 co. 1 lett. b) Tariffa DPR 131/1986",
            "note": "Il decreto ingiuntivo non ancora esecutivo sconta €200 fissi. Se diventa definitivo (non opposto) scatta il 3% sul valore.",
        },
        "decreto_ingiuntivo_definitivo": {
            "label": "Decreto ingiuntivo definitivo (non opposto)",
            "aliquota": 0.03,
            "minimo": 200.0,
            "fisso": False,
            "norma": "Art. 8 co. 1 lett. a) Tariffa DPR 131/1986",
            "note": "Decorsi i termini di opposizione senza impugnazione, il DI è assimilato a sentenza di condanna e sconta il 3%.",
        },
        "verbale_conciliazione": {
            "label": "Verbale di conciliazione (accordo)",
            "aliquota": 0.03,
            "minimo": 200.0,
            "fisso": False,
            "norma": "Art. 11 Tariffa DPR 131/1986",
            "note": "Se il verbale contiene condanna a pagamento: 3%. Se ha solo natura dichiarativa: €200 fissi.",
        },
        "lodo_arbitrale": {
            "label": "Lodo arbitrale",
            "aliquota": 0.03,
            "minimo": 200.0,
            "fisso": False,
            "norma": "Art. 8 co. 1 lett. c) Tariffa DPR 131/1986",
            "note": "Il lodo arbitrale (anche non omologato) è soggetto a imposta di registro entro 20 giorni dalla sottoscrizione.",
        },
        "sentenza_separazione": {
            "label": "Sentenza/provvedimento di separazione o divorzio",
            "aliquota": 0.0,
            "minimo": 200.0,
            "fisso": True,
            "norma": "Art. 19 L. 74/1987 — esenzione",
            "note": "Gli atti del procedimento di separazione e divorzio sono esenti da imposte di bollo e registro ex art. 19 L. 74/1987.",
        },
    }

    def calcola_imposta_registro(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Calcola l'imposta di registro per atti giudiziari (DPR 131/1986)."""
        tipo = str(payload.get("reg_tipo_atto", "sentenza_condanna")).strip()
        valore = _safe_float(payload.get("reg_valore", 0))
        parti = _safe_int(payload.get("reg_parti", 2))

        info = self._TIPI_ATTO_REGISTRO.get(tipo)
        if not info:
            raise ValueError(f"Tipo di atto non riconosciuto: {tipo!r}.")

        warnings: List[str] = []
        notes: List[str] = []

        if info.get("fisso"):
            imposta = info["minimo"]
            aliquota_eff = 0.0
        else:
            if valore <= 0 and not info.get("fisso"):
                warnings.append("Nessun valore indicato: verrà applicato il minimo di €200,00.")
                valore = 0.0
            calcolata = round(valore * info["aliquota"], 2) if valore > 0 else 0.0
            imposta = max(calcolata, info["minimo"])
            aliquota_eff = info["aliquota"] * 100

        # Ripartizione tra parti (solidale)
        quota_parte = round(imposta / max(parti, 1), 2)

        if tipo == "sentenza_separazione":
            notes.append("Esenzione totale ex art. 19 L. 74/1987. L'importo indicato (€200) è il bollo forfettario residuale in alcuni tribunali — verificare con la cancelleria.")
        else:
            notes.append(info["note"])
            notes.append(
                "L'imposta è dovuta in solido da tutte le parti. Il vincitore generalmente anticipa e recupera in esecuzione. "
                "Termine di registrazione: 20 giorni dalla data dell'atto definitivo."
            )

        if imposta > info["minimo"] and not info.get("fisso"):
            notes.append(f"Importo calcolato: {aliquota_eff:.1f}% × €{_fmt_money(valore)} = €{_fmt_money(imposta)}.")

        sources = [
            {"title": "DPR 131/1986 — Tariffa Parte I", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-04-26;131"},
            {"title": "Circolare AE n. 2/2014", "url": "https://www.agenziaentrate.gov.it"},
        ]

        return {
            "tipo": tipo,
            "tipo_label": info["label"],
            "norma": info["norma"],
            "valore": round(valore, 2),
            "aliquota_pct": aliquota_eff,
            "imposta": round(imposta, 2),
            "minimo_fisso": info["minimo"],
            "fisso": info.get("fisso", False),
            "parti": parti,
            "quota_parte": quota_parte,
            "notes": notes,
            "warnings": warnings,
            "sources": sources,
        }

    def calcola_tfr(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        retribuzione_annua = _safe_float(payload.get("tfr_retribuzione_annua"))
        anni_servizio = max(0, _safe_int(payload.get("tfr_anni_servizio")))
        mesi_servizio = max(0, _safe_int(payload.get("tfr_mesi_servizio")))
        montante_pregresso = _safe_float(payload.get("tfr_montante_pregresso"))
        inflazione_perc = _safe_float(payload.get("tfr_inflazione_perc"), 2.0)
        anticipazioni = _safe_float(payload.get("tfr_anticipazioni"))

        if retribuzione_annua <= 0:
            raise ValueError("Inserisci una retribuzione annua lorda positiva.")
        if mesi_servizio >= 12:
            anni_servizio += mesi_servizio // 12
            mesi_servizio = mesi_servizio % 12

        anni_equivalenti = round(anni_servizio + (mesi_servizio / 12.0), 4)
        quota_annua = round(retribuzione_annua / 13.5, 2)
        quota_periodo = round(quota_annua * anni_equivalenti, 2)
        coeff_rivalutazione = round(1.5 + (inflazione_perc * 0.75), 4)
        rivalutazione = round(montante_pregresso * (coeff_rivalutazione / 100.0), 2)
        totale_lordo = round(montante_pregresso + quota_periodo + rivalutazione - anticipazioni, 2)

        notes = [
            f"Quota annua TFR: retribuzione annua / 13,5 = {retribuzione_annua:.2f} / 13,5.",
            f"Rivalutazione del montante pregresso: 1,5% + 75% dell'inflazione ({inflazione_perc:.2f}%).",
        ]
        warnings: List[str] = []
        if anticipazioni > 0:
            notes.append(f"Anticipazioni detratte dal maturato complessivo: {anticipazioni:.2f} EUR.")
        if totale_lordo < 0:
            warnings.append("Il totale risulta negativo dopo le anticipazioni indicate: verificare i dati di partenza.")

        return {
            "retribuzione_annua": round(retribuzione_annua, 2),
            "anni_servizio": anni_servizio,
            "mesi_servizio": mesi_servizio,
            "anni_equivalenti": anni_equivalenti,
            "quota_annua": quota_annua,
            "quota_periodo": quota_periodo,
            "montante_pregresso": round(montante_pregresso, 2),
            "inflazione_perc": round(inflazione_perc, 2),
            "coeff_rivalutazione": coeff_rivalutazione,
            "rivalutazione": rivalutazione,
            "anticipazioni": round(anticipazioni, 2),
            "totale_lordo": totale_lordo,
            "notes": notes,
            "warnings": warnings,
            "sources": self._sources_for_codes("normattiva_portale", "ministero_lavoro_portale"),
        }

    def calcola_onorari_forensi(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        materia_key = _clean_text(payload.get("onorari_materia") or "CIVILE_COGN")
        grado_key = _clean_text(payload.get("onorari_grado") or "TRIBUNALE")
        complessita = _clean_text(payload.get("onorari_complessita") or "media").lower()
        valore = _safe_float(payload.get("onorari_valore"))
        bonus_telematico = _safe_bool(payload.get("onorari_bonus_telematico"))
        includi_spese_generali = _safe_bool(payload.get("onorari_includi_spese_generali"), True)
        fasi_keys = _getlist(payload, "onorari_fasi") or ["STUDIO", "INTRODUTTIVA", "ISTRUTTORIA", "DECISIONALE"]

        try:
            materia = Materia[materia_key]
        except KeyError as exc:
            raise ValueError("Materia forense non riconosciuta.") from exc
        try:
            grado = Grado[grado_key]
        except KeyError as exc:
            raise ValueError("Grado forense non riconosciuto.") from exc

        fasi: List[Fase] = []
        for fase_key in fasi_keys:
            if fase_key in Fase.__members__:
                fasi.append(Fase[fase_key])
        if not fasi:
            raise ValueError("Seleziona almeno una fase per il calcolo degli onorari.")

        risultato = calcola_compenso(
            materia=materia,
            grado=grado,
            valore=valore,
            fasi=fasi,
            bonus_telematico=bonus_telematico,
            includi_spese_generali=includi_spese_generali,
            complessita=complessita,
        )

        riepiloghi = {
            "minimo": risultato.riepilogo_livello("minimo"),
            "base": risultato.riepilogo_livello("base"),
            "massimo": risultato.riepilogo_livello("massimo"),
        }
        livello_suggerito = {
            "bassa": "minimo",
            "media": "base",
            "alta": "massimo",
        }.get(complessita, "base")
        fase_rows = [
            {
                "fase": fase,
                "minimo": valori[0],
                "base": valori[1],
                "massimo": valori[2],
            }
            for fase, valori in risultato.dettaglio.items()
        ]

        note_parts = [part.strip() for part in risultato.note.split(". ") if part.strip()]
        return {
            "materia": materia.name,
            "materia_label": risultato.materia,
            "grado": grado.name,
            "grado_label": risultato.grado,
            "complessita": complessita,
            "valore_input": round(valore, 2),
            "valore_calcolo": round(risultato.valore_calcolo, 2),
            "scaglione": risultato.scaglione,
            "bonus_telematico": bonus_telematico,
            "includi_spese_generali": includi_spese_generali,
            "fasi": [fase.value for fase in fasi],
            "fase_rows": fase_rows,
            "riepiloghi": riepiloghi,
            "livello_suggerito": livello_suggerito,
            "riepilogo_suggerito": riepiloghi[livello_suggerito],
            "notes": note_parts,
            "warnings": [],
            "sources": self._sources_for_codes(
                "legge_forense_247_2012",
                "dm_55_2014_parametri",
                "dm_147_2022_parametri",
                "equo_compenso_49_2023",
                "cnf_portale",
            ),
        }

    def calcola_custodia_cautelare(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        data_esecuzione = _parse_date(payload.get("custodia_data_esecuzione"))
        data_istanza_riesame = _parse_date(payload.get("custodia_data_istanza_riesame"))
        data_decisione_riesame = _parse_date(payload.get("custodia_data_decisione_riesame"))
        tipo_misura = _clean_text(payload.get("custodia_tipo_misura") or "carcere")

        if not data_esecuzione:
            raise ValueError("Inserisci una data di esecuzione valida della misura.")

        oggi = _today()
        interrogatorio_entra = data_esecuzione + timedelta(days=5)
        riesame_entra = data_esecuzione + timedelta(days=10)
        decisione_entra = data_istanza_riesame + timedelta(days=10) if data_istanza_riesame else None
        deposito_entra = data_decisione_riesame + timedelta(days=30) if data_decisione_riesame else None

        warnings: List[str] = []
        if oggi > interrogatorio_entra:
            warnings.append("Il termine ordinario per l'interrogatorio di garanzia risulta superato.")
        if oggi > riesame_entra and not data_istanza_riesame:
            warnings.append("La finestra ordinaria per l'istanza di riesame risulta decorso.")
        if decisione_entra and oggi > decisione_entra and not data_decisione_riesame:
            warnings.append("Il termine per la decisione sul riesame appare scaduto rispetto alla data indicata.")

        timeline = [
            {"label": "Esecuzione misura", "date": data_esecuzione.isoformat(), "date_it": _fmt_date_it(data_esecuzione)},
            {"label": "Interrogatorio di garanzia entro", "date": interrogatorio_entra.isoformat(), "date_it": _fmt_date_it(interrogatorio_entra)},
            {"label": "Istanza di riesame entro", "date": riesame_entra.isoformat(), "date_it": _fmt_date_it(riesame_entra)},
        ]
        if data_istanza_riesame:
            timeline.append({"label": "Istanza di riesame depositata", "date": data_istanza_riesame.isoformat(), "date_it": _fmt_date_it(data_istanza_riesame)})
        if decisione_entra:
            timeline.append({"label": "Decisione sul riesame entro", "date": decisione_entra.isoformat(), "date_it": _fmt_date_it(decisione_entra)})
        if data_decisione_riesame:
            timeline.append({"label": "Decisione sul riesame", "date": data_decisione_riesame.isoformat(), "date_it": _fmt_date_it(data_decisione_riesame)})
        if deposito_entra:
            timeline.append({"label": "Deposito motivazione entro", "date": deposito_entra.isoformat(), "date_it": _fmt_date_it(deposito_entra)})

        misura_label = {
            "carcere": "Custodia in carcere",
            "domiciliari": "Arresti domiciliari",
            "altro": "Altra misura custodiale",
        }.get(tipo_misura, "Misura custodiale")

        return {
            "tipo_misura": tipo_misura,
            "tipo_misura_label": misura_label,
            "data_esecuzione": data_esecuzione.isoformat(),
            "data_esecuzione_it": _fmt_date_it(data_esecuzione),
            "giorni_decorsi": max(0, (oggi - data_esecuzione).days),
            "interrogatorio_entra": interrogatorio_entra.isoformat(),
            "interrogatorio_entra_it": _fmt_date_it(interrogatorio_entra),
            "riesame_entra": riesame_entra.isoformat(),
            "riesame_entra_it": _fmt_date_it(riesame_entra),
            "decisione_entra": decisione_entra.isoformat() if decisione_entra else "",
            "decisione_entra_it": _fmt_date_it(decisione_entra) if decisione_entra else "n/d",
            "deposito_entra": deposito_entra.isoformat() if deposito_entra else "",
            "deposito_entra_it": _fmt_date_it(deposito_entra) if deposito_entra else "n/d",
            "timeline": timeline,
            "notes": [
                "Scansione operativa costruita sui termini essenziali di interrogatorio di garanzia, riesame e deposito motivazione.",
                "Il modulo non sostituisce il controllo sul titolo custodiale concreto, sui termini speciali e sulle eventuali sospensioni processuali.",
            ],
            "warnings": warnings,
            "sources": self._sources_for_codes("normattiva_portale", "cassazione_portale"),
        }

    def calcola_prescrizione_penale(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        data_fatto = _parse_date(payload.get("presc_data_fatto"))
        massimo_anni = max(0, _safe_int(payload.get("presc_massimo_edittale_anni")))
        massimo_mesi = max(0, _safe_int(payload.get("presc_massimo_edittale_mesi")))
        contravvenzione = _safe_bool(payload.get("presc_contravvenzione"))
        coeff_interruzione = max(1.0, _safe_float(payload.get("presc_coeff_interruzione"), 1.25))
        giorni_sospensione = max(0, _safe_int(payload.get("presc_giorni_sospensione")))

        if not data_fatto:
            raise ValueError("Inserisci una data del fatto valida.")

        massimo_edittale = massimo_anni + (massimo_mesi / 12.0)
        minimo_legale = 4.0 if contravvenzione else 6.0
        termine_base_anni = max(massimo_edittale, minimo_legale)
        base_core_days = round(termine_base_anni * 365.25)
        base_days = base_core_days + giorni_sospensione
        massimo_days = round(base_core_days * coeff_interruzione) + giorni_sospensione
        data_prescrizione_base = data_fatto + timedelta(days=base_days)
        data_prescrizione_massima = data_fatto + timedelta(days=massimo_days)

        return {
            "data_fatto": data_fatto.isoformat(),
            "data_fatto_it": _fmt_date_it(data_fatto),
            "contravvenzione": contravvenzione,
            "regime_label": "Contravvenzione" if contravvenzione else "Delitto",
            "massimo_edittale_anni": round(massimo_edittale, 2),
            "termine_base_anni": round(termine_base_anni, 2),
            "coeff_interruzione": round(coeff_interruzione, 2),
            "giorni_sospensione": giorni_sospensione,
            "data_prescrizione_base": data_prescrizione_base.isoformat(),
            "data_prescrizione_base_it": _fmt_date_it(data_prescrizione_base),
            "data_prescrizione_massima": data_prescrizione_massima.isoformat(),
            "data_prescrizione_massima_it": _fmt_date_it(data_prescrizione_massima),
            "notes": [
                "Termine base calcolato assumendo il massimo edittale indicato, con soglia minima di 6 anni per i delitti e 4 anni per le contravvenzioni.",
                "Il termine massimo applica il coefficiente di interruzione indicato e somma i giorni di sospensione segnalati.",
                "Verificare sempre discipline speciali, recidiva, atti interruttivi effettivi e sospensioni normativamente tipizzate.",
            ],
            "warnings": [],
            "sources": self._sources_for_codes("normattiva_portale", "cassazione_portale"),
        }

    def calcola_successione_legittima(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        asse = _safe_float(payload.get("successione_asse"))
        coniuge = _safe_bool(payload.get("successione_coniuge"))
        figli = max(0, _safe_int(payload.get("successione_figli")))
        ascendenti = max(0, _safe_int(payload.get("successione_ascendenti")))
        fratelli = max(0, _safe_int(payload.get("successione_fratelli")))

        if asse <= 0:
            raise ValueError("Inserisci un asse ereditario positivo.")
        if not any([coniuge, figli, ascendenti, fratelli]):
            raise ValueError("Indica almeno una categoria di eredi per il riparto.")

        rows: List[Dict[str, Any]] = []
        notes: List[str] = []

        def _append_row(label: str, quota: float, count: int = 1, detail: str = "") -> None:
            importo = round(asse * quota, 2)
            rows.append(
                {
                    "label": label,
                    "quota_percent": round(quota * 100, 2),
                    "importo": importo,
                    "count": count,
                    "per_testa": round(importo / count, 2) if count else importo,
                    "detail": detail,
                }
            )

        if coniuge and figli == 0 and ascendenti == 0 and fratelli == 0:
            _append_row("Coniuge", 1.0)
        elif figli > 0 and not coniuge:
            _append_row("Figli", 1.0, figli, "Riparto in parti uguali tra i figli.")
        elif coniuge and figli == 1:
            _append_row("Coniuge", 0.5)
            _append_row("Figlio", 0.5)
        elif coniuge and figli > 1:
            _append_row("Coniuge", 1 / 3)
            _append_row("Figli", 2 / 3, figli, "Quota dei figli ripartita in parti uguali.")
        elif coniuge and figli == 0 and (ascendenti > 0 or fratelli > 0):
            _append_row("Coniuge", 2 / 3)
            if ascendenti > 0 and fratelli == 0:
                _append_row("Ascendenti", 1 / 3, ascendenti, "Quota della linea ascendente.")
            elif fratelli > 0 and ascendenti == 0:
                _append_row("Fratelli", 1 / 3, fratelli, "Quota dei collaterali in parti uguali.")
            else:
                _append_row("Ascendenti e fratelli", 1 / 3, ascendenti + fratelli, "Riparto aggregato: il dettaglio interno va verificato caso per caso.")
                notes.append("Concorso tra ascendenti e fratelli trattato in forma aggregata: verificare il dettaglio interno del terzo residuo.")
        elif not coniuge and figli == 0 and ascendenti > 0 and fratelli == 0:
            _append_row("Ascendenti", 1.0, ascendenti, "Riparto in parti uguali nella linea ascendente indicata.")
        elif not coniuge and figli == 0 and fratelli > 0 and ascendenti == 0:
            _append_row("Fratelli", 1.0, fratelli, "Riparto in parti uguali tra i fratelli indicati.")
        else:
            _append_row("Ascendenti e fratelli", 1.0, max(1, ascendenti + fratelli), "Riparto aggregato per scenario misto da verificare puntualmente.")
            notes.append("Scenario misto collaterali/ascendenti trattato come quota aggregata per evitare semplificazioni scorrette.")

        quota_tot = round(sum(row["quota_percent"] for row in rows), 2)
        return {
            "asse": round(asse, 2),
            "rows": rows,
            "quota_totale_percent": quota_tot,
            "notes": notes + [
                "Modulo pensato per riparti legittimi standard. Non gestisce rappresentazione, collaterali ulteriori, quote di riserva o istituti successori speciali.",
            ],
            "warnings": [],
            "sources": self._sources_for_codes("normattiva_portale"),
        }

    def calcola_cedolare_secca(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        canone_annuo = _safe_float(payload.get("cedolare_canone_annuo"))
        aliquota = _safe_float(payload.get("cedolare_aliquota"), 21.0)
        annualita = max(1, _safe_int(payload.get("cedolare_annualita"), 1))

        if canone_annuo <= 0:
            raise ValueError("Inserisci un canone annuo positivo.")
        if aliquota <= 0:
            raise ValueError("Indica un'aliquota valida per la cedolare secca.")

        imposta_annua = round(canone_annuo * (aliquota / 100.0), 2)
        totale_periodo = round(imposta_annua * annualita, 2)
        registro_annuo = round(canone_annuo * 0.02, 2)
        registro_evitato = round(registro_annuo * annualita, 2)

        notes = [
            "Aliquota 21% tipica per contratti liberi; aliquota 10% normalmente riferita ai canoni concordati nei limiti di legge.",
            "Il confronto con il regime ordinario qui evidenzia il solo impatto dell'imposta di registro non dovuta.",
        ]

        return {
            "canone_annuo": round(canone_annuo, 2),
            "aliquota": round(aliquota, 2),
            "annualita": annualita,
            "imposta_annua": imposta_annua,
            "totale_periodo": totale_periodo,
            "registro_annuo": registro_annuo,
            "registro_evitato": registro_evitato,
            "notes": notes,
            "warnings": [],
            "sources": self._sources_for_codes("agenzia_entrate_fec", "normattiva_portale", "legge_431_1998_locazioni"),
        }

    def calcola_indennita_licenziamento(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        retribuzione_mensile = _safe_float(payload.get("lic_retribuzione_mensile"))
        anni_servizio = max(0, _safe_int(payload.get("lic_anni_servizio")))
        mesi_servizio = max(0, _safe_int(payload.get("lic_mesi_servizio")))
        regime = _clean_text(payload.get("lic_regime") or "jobs_act")
        mensilita_preavviso = max(0.0, _safe_float(payload.get("lic_mensilita_preavviso")))

        if retribuzione_mensile <= 0:
            raise ValueError("Inserisci una retribuzione mensile positiva.")
        if mesi_servizio >= 12:
            anni_servizio += mesi_servizio // 12
            mesi_servizio = mesi_servizio % 12
        anzianita = round(anni_servizio + (mesi_servizio / 12.0), 2)

        if regime == "jobs_act":
            mensilita = min(36.0, max(6.0, round(anzianita * 2.0, 2)))
            regime_label = "Tutele crescenti"
            notes = ["Calcolo parametrato a 2 mensilita per anno di servizio, con minimo 6 e massimo 36."]
        elif regime == "piccola_impresa":
            mensilita = min(6.0, max(3.0, round(anzianita * 1.0, 2)))
            regime_label = "Piccola impresa / tutela obbligatoria"
            notes = ["Stima operativa parametrata a 1 mensilita per anno, con minimo 3 e massimo 6."]
        else:
            mensilita = round(mensilita_preavviso, 2)
            regime_label = "Indennita sostitutiva del preavviso"
            notes = ["Importo calcolato sulla mensilita di preavviso inserita manualmente."]

        importo = round(retribuzione_mensile * mensilita, 2)
        return {
            "retribuzione_mensile": round(retribuzione_mensile, 2),
            "anni_servizio": anni_servizio,
            "mesi_servizio": mesi_servizio,
            "anzianita": anzianita,
            "regime": regime,
            "regime_label": regime_label,
            "mensilita": mensilita,
            "importo": importo,
            "notes": notes + ["Verificare sempre disciplina applicabile, causale del recesso e orientamenti giurisprudenziali attuali."],
            "warnings": [],
            "sources": self._sources_for_codes("ministero_lavoro_portale", "normattiva_portale"),
        }

    def calcola_piano_ammortamento(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        capitale = _safe_float(payload.get("amm_capitale"))
        tasso_annuo = _safe_float(payload.get("amm_tasso_annuo"))
        durata_anni = max(1, _safe_int(payload.get("amm_durata_anni"), 10))
        rate_anno = max(1, _safe_int(payload.get("amm_rate_anno"), 12))
        tipo = _clean_text(payload.get("amm_tipo") or "francese")
        data_prima_rata = _parse_date(payload.get("amm_data_prima_rata")) or _today()

        if capitale <= 0:
            raise ValueError("Inserisci un capitale finanziato positivo.")
        n_rate = durata_anni * rate_anno
        periodo = tasso_annuo / 100.0 / rate_anno
        schedule: List[Dict[str, Any]] = []
        residuo = round(capitale, 2)
        totale_interessi = 0.0
        mesi_step = 12 // rate_anno if rate_anno and 12 % rate_anno == 0 else 0

        if tipo == "francese":
            if periodo == 0:
                rata_costante = round(capitale / n_rate, 2)
            else:
                rata_costante = round(capitale * periodo / (1 - math.pow(1 + periodo, -n_rate)), 2)
        else:
            rata_costante = 0.0
            quota_capitale_costante = round(capitale / n_rate, 2)

        for numero in range(1, n_rate + 1):
            quota_interessi = round(residuo * periodo, 2)
            if tipo == "francese":
                quota_capitale = round(rata_costante - quota_interessi, 2)
                rata = rata_costante
            else:
                quota_capitale = quota_capitale_costante
                rata = round(quota_capitale + quota_interessi, 2)

            if numero == n_rate:
                quota_capitale = round(residuo, 2)
                rata = round(quota_capitale + quota_interessi, 2)

            residuo = round(max(0.0, residuo - quota_capitale), 2)
            totale_interessi = round(totale_interessi + quota_interessi, 2)
            scadenza = _add_months(data_prima_rata, (numero - 1) * mesi_step) if mesi_step else None

            schedule.append(
                {
                    "numero": numero,
                    "scadenza": scadenza.isoformat() if scadenza else "",
                    "scadenza_it": _fmt_date_it(scadenza) if scadenza else f"Rata {numero}",
                    "rata": round(rata, 2),
                    "quota_capitale": quota_capitale,
                    "quota_interessi": quota_interessi,
                    "residuo": residuo,
                }
            )

        return {
            "tipo": tipo,
            "tipo_label": "Piano alla francese" if tipo == "francese" else "Piano all'italiana",
            "capitale": round(capitale, 2),
            "tasso_annuo": round(tasso_annuo, 4),
            "durata_anni": durata_anni,
            "rate_anno": rate_anno,
            "numero_rate": n_rate,
            "data_prima_rata": data_prima_rata.isoformat(),
            "data_prima_rata_it": _fmt_date_it(data_prima_rata),
            "rata_iniziale": schedule[0]["rata"] if schedule else 0.0,
            "rata_finale": schedule[-1]["rata"] if schedule else 0.0,
            "totale_interessi": totale_interessi,
            "totale_pagato": round(capitale + totale_interessi, 2),
            "schedule": schedule,
            "preview_schedule": schedule[: min(12, len(schedule))],
            "notes": [
                "Il piano e calcolato con arrotondamento a centesimi per rata e chiusura del residuo sull'ultima scadenza.",
            ],
            "warnings": [],
            "sources": [],
        }

    def _contributo_civile(self, valore: float) -> float:
        if valore <= 0:
            return float(self.norme.contributo_defaults("civile").get("indeterminabile_amount", 518.0))
        for limite, importo in self.norme.contributo_tiers("civile"):
            if valore <= limite:
                return float(importo)
        return self.norme.contributo_tiers("civile")[-1][1]

    def _contributo_tributario(self, valore: float) -> float:
        if valore <= 0:
            raise ValueError("Per il ricorso tributario indica il valore della controversia.")
        for limite, importo in self.norme.contributo_tiers("tributario"):
            if valore <= limite:
                return float(importo)
        return self.norme.contributo_tiers("tributario")[-1][1]
