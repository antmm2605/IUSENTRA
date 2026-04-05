from __future__ import annotations

import html
import math
from datetime import date
from textwrap import dedent
from typing import Any, Dict, List, Mapping, Optional

from pct.normative_tables import (
    FONTI_OPERATIVE,
    GestioneTabelleNormative,
    InterestPeriod,
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


def _days_inclusive(start: date, end: date) -> int:
    return (end - start).days + 1


def _year_denominator(day: date) -> int:
    year = day.year
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


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
            {"id": "contributo_unificato", "title": "Contributo unificato", "subtitle": "Civile, amministrativo e tributario con basi ufficiali e note operative.", "icon": "bi-bank"},
            {"id": "interessi", "title": "Interessi legali e moratori", "subtitle": "Art. 1284 c.c. e D.Lgs. 231/2002 con segmentazione per periodo.", "icon": "bi-percent"},
            {"id": "nota_credito", "title": "Nota di precisazione del credito", "subtitle": "Bozza professionale con capitale, interessi, spese, CPA, IVA e residuo.", "icon": "bi-file-earmark-ruled"},
            {"id": "pignoramento", "title": "Simulatore pignoramento stipendio / pensione", "subtitle": "Ordinario, esattoriale e alimentare con soglia pensione 2026 gia aggiornata.", "icon": "bi-cash-stack"},
            {"id": "ctu", "title": "CTU, vacazioni e compensi ausiliari", "subtitle": "Vacazioni vigenti, spese documentate e accessori professionali.", "icon": "bi-journal-medical"},
            {"id": "rivalutazione_istat", "title": "Rivalutazione monetaria ISTAT", "subtitle": "Calcolo FOI / NIC per danni, assegni divorzili, liquidazioni e adeguamenti.", "icon": "bi-graph-up-arrow"},
            {"id": "canone_locazione", "title": "Adeguamento canone di locazione", "subtitle": "Aggiornamento annuale con indice ISTAT FOI ex L. 431/1998.", "icon": "bi-house-lock"},
            {"id": "usura", "title": "Verifica soglia usura", "subtitle": "Confronta il tasso applicato con TEGM e soglia antiusura per categoria (L. 108/1996).", "icon": "bi-shield-exclamation"},
            {"id": "contributi_cassa_forense", "title": "Contributi Cassa Forense", "subtitle": "Soggettivo, integrativo e maternita: aliquote e minimali annuali aggiornati.", "icon": "bi-person-badge"},
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
        }
        if posted:
            for key in defaults:
                if key in posted:
                    defaults[key] = str(posted.get(key, defaults[key]) or "")
        return defaults

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
