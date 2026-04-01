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
