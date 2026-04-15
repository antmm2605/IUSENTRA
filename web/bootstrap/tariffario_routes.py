"""Tariffario routes extracted from web.app."""

from __future__ import annotations

import json
from datetime import date

from flask import Flask, flash, render_template, request, url_for

from pct.tariffario import ComplessitaStimata, Fase, Grado, Materia, calcola_compenso, livello_compenso_da_complessita
from pct.tariffario_catalogo import (
    first_profile_for_materia,
    grade_catalog_by_materia,
    phase_catalog_by_materia,
    profile_lookup_by_labels,
    profile_lookup_by_rule,
    rule_catalog_by_materia,
    rule_lookup,
    tariffario_complessita_rows,
)
from web.services.tariffario_runtime import (
    esborsi_catalogo,
    maggiorazioni_adr_da_form,
    manual_rows_from_form,
    parse_float,
    preferred_grade,
    variazioni_fasi_da_form,
    variazioni_prefill_from_form,
)


def register_tariffario_routes(app: Flask) -> None:
    """Register tariffario route and keep its runtime isolated from web.app."""

    @app.route("/tariffario", methods=["GET", "POST"])
    def tariffario():
        from pct.economico_context import costruisci_contesto_economico, dump_log_calcolo
        from pct.motore_preventivo import catalogo_wizard, get_tipo_pratica, motore_calcola
        from web.helpers import get_normative_tables

        risultato = None
        materie = [m.value for m in Materia]
        phase_catalog = phase_catalog_by_materia()
        grade_catalog = grade_catalog_by_materia()
        rule_catalog = rule_catalog_by_materia()
        complessita_catalog = tariffario_complessita_rows()
        pratiche_catalogo = catalogo_wizard()
        pratiche_by_id = {
            item["id"]: item
            for items in pratiche_catalogo.values()
            for item in items
        }
        materia_sel = request.form.get("materia", "") or (materie[0] if materie else "")
        regola_tariffaria_sel = request.form.get("regola_tariffaria", "").strip()
        regola_attiva = rule_lookup(regola_tariffaria_sel) if regola_tariffaria_sel else None
        grade_defaults = grade_catalog.get(materia_sel) or [Grado.TRIBUNALE.value]
        grado_sel = (
            request.form.get("grado", "").strip()
            or (regola_attiva.get("grado_input_value", "") if regola_attiva else "")
            or preferred_grade(grade_defaults)
        )
        if grado_sel not in grade_defaults:
            grado_sel = preferred_grade(grade_defaults)
        complessita_sel = (
            request.form.get("complessita", ComplessitaStimata.MEDIA.value).strip()
            or ComplessitaStimata.MEDIA.value
        )
        livello_compenso_sel = livello_compenso_da_complessita(complessita_sel)
        valore_str = (request.form.get("valore", "0") or "0").strip()
        fasi_sel = request.form.getlist("fasi")
        bonus_tel = request.form.get("bonus_telematico") == "1"
        spese_gen = request.form.get("spese_generali", "1") == "1"
        perc_spese = parse_float(request.form.get("perc_spese_generali", "15"), 15.0)
        accessori_sel = request.form.getlist("accessori")
        esborsi_sel = request.form.getlist("esborsi")
        manual_rows_prefill = manual_rows_from_form(request.form)
        adr_accordo = request.form.get("adr_accordo") == "1"
        variazioni_prefill = variazioni_prefill_from_form(request.form)

        fasi_valide = phase_catalog.get(materia_sel) or []
        if not fasi_sel:
            fasi_sel = [item["value"] for item in fasi_valide]
        profilo_attivo = (
            profile_lookup_by_rule(regola_tariffaria_sel, grado_sel)
            or profile_lookup_by_labels(materia_sel, grado_sel)
            or first_profile_for_materia(materia_sel)
        )
        tipo_pratica_attiva = (
            get_tipo_pratica((regola_attiva or {}).get("suggested_practice_id", ""))
            if regola_attiva
            else None
        )
        if not tipo_pratica_attiva and profilo_attivo:
            tipo_pratica_attiva = get_tipo_pratica(profilo_attivo.get("suggested_practice_id", ""))
        esborsi_catalogo_rows = esborsi_catalogo(
            tipo_pratica_attiva,
            accessori_sel,
            get_tipo_pratica=get_tipo_pratica,
        )
        esborsi_sel_set = set(esborsi_sel)
        righe_calcolo: list[dict[str, object]] = []
        riepilogo_economico = None

        if request.method == "POST":
            try:
                materia = Materia(materia_sel)
                grade_defaults = grade_catalog.get(materia_sel) or [Grado.TRIBUNALE.value]
                if grado_sel not in grade_defaults:
                    grado_sel = preferred_grade(grade_defaults)
                grado = Grado(grado_sel)
                valore = parse_float(valore_str, 0.0)
                fasi = []
                for fase_val in fasi_sel:
                    try:
                        fasi.append(Fase(fase_val))
                    except ValueError:
                        continue
                if not fasi:
                    fasi = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]
                risultato = calcola_compenso(
                    materia,
                    grado,
                    valore,
                    fasi,
                    profile_code=(profilo_attivo or {}).get("profile_code", ""),
                    bonus_telematico=bonus_tel,
                    includi_spese_generali=spese_gen,
                    perc_spese_generali=max(0.0, perc_spese / 100.0),
                    variazioni_fasi=variazioni_fasi_da_form(request.form, tipo_pratica_attiva) or None,
                    maggiorazioni_fasi=maggiorazioni_adr_da_form(request.form, tipo_pratica_attiva) or None,
                    complessita=complessita_sel,
                )
                regola_attiva = rule_lookup(regola_tariffaria_sel) if regola_tariffaria_sel else None
                profilo_attivo = (
                    profile_lookup_by_rule(regola_tariffaria_sel, grado_sel)
                    or profile_lookup_by_labels(materia_sel, grado_sel)
                    or first_profile_for_materia(materia_sel)
                )
                tipo_pratica_attiva = (
                    get_tipo_pratica((regola_attiva or {}).get("suggested_practice_id", ""))
                    if regola_attiva
                    else None
                )
                if not tipo_pratica_attiva and profilo_attivo:
                    tipo_pratica_attiva = get_tipo_pratica(profilo_attivo.get("suggested_practice_id", ""))
                esborsi_catalogo_rows = esborsi_catalogo(
                    tipo_pratica_attiva,
                    accessori_sel,
                    get_tipo_pratica=get_tipo_pratica,
                )
                esborsi_sel_set = set(esborsi_sel)

                if risultato:
                    righe_calcolo.append(
                        {
                            "descrizione": (
                                f"Compenso professionale per "
                                f"{profilo_attivo.get('table_label', materia_sel)} - {risultato.scaglione}"
                            ),
                            "tipo": "Onorario",
                            "importo": risultato.totale_compenso_livello(livello_compenso_sel),
                            "fonte": "principale",
                        }
                    )

                accessori_map = {
                    item.get("id"): item for item in (tipo_pratica_attiva.accessori_calcolo or [])
                } if tipo_pratica_attiva else {}
                fase_key_map = {
                    "studio": Fase.STUDIO,
                    "introduttiva": Fase.INTRODUTTIVA,
                    "istruttoria": Fase.ISTRUTTORIA,
                    "decisionale": Fase.DECISIONALE,
                    "esecutiva": Fase.ESECUTIVA,
                    "attivazione": Fase.ATTIVAZIONE,
                    "rivitalizzazione": Fase.RIVITALIZZAZIONE,
                    "negoziazione": Fase.NEGOZIAZIONE_TRATTAZIONE,
                    "conciliazione": Fase.CONCILIAZIONE,
                }
                for accessorio_id in accessori_sel:
                    accessorio = accessori_map.get(accessorio_id)
                    if not accessorio:
                        continue
                    tp_accessorio = get_tipo_pratica(accessorio.get("tipo_pratica_id", ""))
                    fasi_accessorio = [
                        fase_key_map[key]
                        for key in accessorio.get("fasi_default_keys", [])
                        if key in fase_key_map
                    ] or None
                    ris_accessorio = motore_calcola(
                        id_pratica=accessorio.get("tipo_pratica_id", ""),
                        valore_controversia=valore,
                        livello_compenso=livello_compenso_sel,
                        complessita=complessita_sel,
                        bonus_telematico=bonus_tel,
                        includi_spese_generali=spese_gen,
                        perc_spese_generali=max(0.0, perc_spese / 100.0),
                        variazioni_fasi=variazioni_fasi_da_form(request.form, tp_accessorio) or None,
                        maggiorazioni_fasi=maggiorazioni_adr_da_form(request.form, tp_accessorio) or None,
                        fasi=fasi_accessorio,
                        applica_cpa=False,
                        applica_iva=False,
                    )
                    righe_calcolo.append(
                        {
                            "descrizione": (
                                accessorio.get("row_label")
                                or f"Compenso professionale per {ris_accessorio.tipo_pratica.label}"
                            ),
                            "tipo": "Onorario",
                            "importo": ris_accessorio.onorario_selezionato,
                            "fonte": f"accessorio:{accessorio_id}",
                        }
                    )

                for item in esborsi_catalogo_rows:
                    if item["key"] not in esborsi_sel_set:
                        continue
                    righe_calcolo.append(
                        {
                            "descrizione": item["descrizione"],
                            "tipo": "Spesa viva",
                            "importo": item["importo"],
                            "fonte": f"esborso:{item['key']}",
                        }
                    )

                for row in manual_rows_prefill:
                    righe_calcolo.append(
                        {
                            "descrizione": row["descrizione"],
                            "tipo": row["tipo"],
                            "importo": row["importo"],
                            "fonte": "manuale",
                        }
                    )

                imponibile = round(sum(float(row["importo"]) for row in righe_calcolo), 2)
                cassa = round(imponibile * 0.04, 2)
                base_iva = round(imponibile + cassa, 2)
                iva = round(base_iva * 0.22, 2)
                totale = round(base_iva + iva, 2)
                riepilogo_economico = {
                    "imponibile": imponibile,
                    "cassa": cassa,
                    "base_iva": base_iva,
                    "iva": iva,
                    "totale": totale,
                }
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        tabelle_normative = get_normative_tables()
        tariffario_tables = [
            row for row in tabelle_normative.catalogo_tabelle()
            if row["id"].startswith("tariffario_forense_")
        ]
        tariffario_profili = tabelle_normative.tariffario_profili()
        tariffario_regole = tabelle_normative.tariffario_regole()
        tariffario_audit = tabelle_normative.tariffario_audit()
        opzioni_tariffario = tabelle_normative.tariffario_opzioni()
        riferimenti_tariffario = tabelle_normative.tariffario_riferimenti()
        canali_fatturazione = tabelle_normative.tariffario_fatturazione()
        tariffario_audit = [
            {
                **row,
                "practice_label": (
                    pratiche_by_id.get(row.get("suggested_practice_id", ""), {}).get("label")
                    or row.get("suggested_practice_id", "")
                ),
            }
            for row in tariffario_audit
        ]
        tariffario_audit_summary = {
            "totale": len(tariffario_audit),
            "verificata_snapshot": sum(
                1 for row in tariffario_audit if row.get("compliance_status") == "verificata_snapshot"
            ),
            "verificata_seed": sum(
                1 for row in tariffario_audit if row.get("compliance_status") == "verificata_seed"
            ),
            "ricostruttiva": sum(
                1 for row in tariffario_audit if row.get("compliance_status") == "ricostruttiva"
            ),
            "da_verificare": sum(
                1 for row in tariffario_audit if row.get("compliance_status") == "da_verificare"
            ),
        }
        tariffario_audit_warning_rows = [
            row for row in tariffario_audit if row.get("compliance_status") != "verificata_snapshot"
        ][:10]

        url_wizard_precompilato = ""
        url_parcella_precompilata = ""
        if risultato and profilo_attivo:
            manual_voci_json = json.dumps(manual_rows_prefill, ensure_ascii=False)
            esborsi_json = json.dumps(esborsi_sel, ensure_ascii=False)
            accessori_json = json.dumps(accessori_sel, ensure_ascii=False)
            voci_parcella = [
                {
                    "descrizione": row["descrizione"],
                    "quantita": 1,
                    "prezzo_unitario": f"{float(row['importo']):.2f}",
                }
                for row in righe_calcolo
            ]
            wizard_params = {
                "id_pratica": profilo_attivo.get("suggested_practice_id", ""),
                "area": (tipo_pratica_attiva.area if tipo_pratica_attiva else materia_sel),
                "valore": valore_str or "0",
                "grado": grado_sel,
                "regola_tariffaria": regola_tariffaria_sel,
                "complessita": complessita_sel,
                "fasi": ",".join(fasi_sel),
                "bonus_telematico": "1" if bonus_tel else "0",
                "spese_generali": "1" if spese_gen else "0",
                "perc_spese_generali": str(int(round(perc_spese))),
                "applica_cpa": "1",
                "applica_iva": "1",
                "anticipazioni": "0",
                "adr_accordo": "1" if adr_accordo else "0",
                "accessori_json": accessori_json,
                "esborsi_json": esborsi_json,
                "manual_voci_json": manual_voci_json,
                "auto_calcola": "1",
                "entry": "tariffario",
            }
            for key, raw_value in variazioni_prefill.items():
                wizard_params[f"var_{key}"] = raw_value
            url_wizard_precompilato = url_for("preventivi.wizard", **wizard_params)
            log_parcella = dump_log_calcolo(
                costruisci_contesto_economico(
                    source="tariffario_forense",
                    source_label="Tariffario forense",
                    oggetto=tipo_pratica_attiva.label if tipo_pratica_attiva else "",
                    id_pratica=profilo_attivo.get("suggested_practice_id", ""),
                    pratica_label=(
                        tipo_pratica_attiva.label
                        if tipo_pratica_attiva
                        else profilo_attivo.get("label", "")
                    ),
                    area_pratica=tipo_pratica_attiva.area if tipo_pratica_attiva else materia_sel,
                    tipo_compenso=(
                        tipo_pratica_attiva.tipo_compenso_default
                        if tipo_pratica_attiva
                        else "Per fasi processuali (D.M. 55/2014)"
                    ),
                    tipo_procedimento=profilo_attivo.get("label", ""),
                    grado_sede=grado_sel,
                    regola_tariffaria=(
                        regola_attiva.get("rule_label", "") if regola_attiva else regola_tariffaria_sel
                    ),
                    regola_tariffaria_code=(
                        regola_attiva.get("rule_code", "") if regola_attiva else regola_tariffaria_sel
                    ),
                    complessita=complessita_sel,
                    valore_controversia=valore_str or "0",
                    bonus_telematico=bonus_tel,
                    spese_generali=spese_gen,
                    perc_spese_generali=perc_spese,
                    applica_cpa=True,
                    applica_iva=True,
                    adr_accordo=adr_accordo,
                    variazioni_fasi_pct=variazioni_prefill,
                    accessori=accessori_sel,
                    esborsi=esborsi_sel,
                    manual_voci=manual_rows_prefill,
                    risultato={
                        "scaglione": risultato.scaglione,
                        "onorario_base": risultato.totale_compenso_livello(livello_compenso_sel),
                        "cpa": riepilogo_economico.get("cpa", 0.0),
                        "iva": riepilogo_economico.get("iva", 0.0),
                        "totale": riepilogo_economico.get("totale", 0.0),
                        "nota": risultato.note,
                    },
                    audit_tariffario=regola_attiva,
                    riferimenti_normativi=[
                        row.get("title", "")
                        for row in (
                            tipo_pratica_attiva.normative_references
                            if tipo_pratica_attiva
                            else riferimenti_tariffario
                        )
                    ][:4],
                )
            )
            url_parcella_precompilata = url_for(
                "fatturazione.nuova",
                voci_json=json.dumps(voci_parcella, ensure_ascii=False),
                note=risultato.note,
                applica_cassa="1",
                applica_iva="1",
                origine="tariffario",
                id_pratica=profilo_attivo.get("suggested_practice_id", ""),
                area_pratica=tipo_pratica_attiva.area if tipo_pratica_attiva else materia_sel,
                tipo_compenso=(
                    tipo_pratica_attiva.tipo_compenso_default
                    if tipo_pratica_attiva
                    else "Per fasi processuali (D.M. 55/2014)"
                ),
                tipo_procedimento=profilo_attivo.get("label", ""),
                valore_controversia=valore_str or "0",
                complessita=complessita_sel,
                log_calcolo=log_parcella,
            )

        return render_template(
            "tariffario.html",
            materie=materie,
            grade_catalog=grade_catalog,
            rule_catalog=rule_catalog,
            complessita_catalog=complessita_catalog,
            phase_catalog=phase_catalog,
            risultato=risultato,
            profilo_attivo=profilo_attivo,
            regola_attiva=regola_attiva,
            tariffario_tables=tariffario_tables,
            tariffario_profili=tariffario_profili,
            tariffario_regole=tariffario_regole,
            tariffario_audit=tariffario_audit,
            tariffario_audit_summary=tariffario_audit_summary,
            tariffario_audit_warning_rows=tariffario_audit_warning_rows,
            opzioni_tariffario=opzioni_tariffario,
            riferimenti_tariffario=riferimenti_tariffario,
            canali_fatturazione=canali_fatturazione,
            pratiche_by_id=pratiche_by_id,
            tipo_pratica_attiva=tipo_pratica_attiva.to_dict() if tipo_pratica_attiva else None,
            materia_sel=materia_sel,
            grado_sel=grado_sel,
            regola_tariffaria_sel=regola_tariffaria_sel,
            complessita_sel=complessita_sel,
            valore_str=valore_str,
            fasi_sel=fasi_sel,
            bonus_tel=bonus_tel,
            spese_gen=spese_gen,
            perc_spese=perc_spese,
            accessori_sel=accessori_sel,
            esborsi_sel=esborsi_sel,
            adr_accordo=adr_accordo,
            variazioni_prefill=variazioni_prefill,
            esborsi_catalogo=esborsi_catalogo_rows,
            manual_rows_prefill=manual_rows_prefill,
            righe_calcolo=righe_calcolo,
            riepilogo_economico=riepilogo_economico,
            url_wizard_precompilato=url_wizard_precompilato,
            url_parcella_precompilata=url_parcella_precompilata,
            oggi=date.today(),
        )
