"""
web/blueprints/wizard_pro.py — Preparazione Udienza Guidata.

URL base: /wizard-pro/

Route:
    GET  /wizard-pro/                        → index (cruscotto selezione fascicolo)
    GET  /wizard-pro/nuovo                   → redirect al cruscotto di selezione
    POST /wizard-pro/nuovo                   → crea nuova sessione
    GET  /wizard-pro/<id>/step/<n>           → mostra step n
    POST /wizard-pro/<id>/step/<n>           → salva step n
    GET  /wizard-pro/<id>/completo           → riepilogo post-completamento
    POST /wizard-pro/<id>/elimina            → elimina sessione
    POST /wizard-pro/<id>/archivia           → archivia sessione
    GET  /wizard-pro/fascicolo/<id_fasc>     → avvia o elenca per fascicolo
"""
from __future__ import annotations

from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pct.wizard_pro import (
    GestioneWizardPro,
    SessioneWizardPro,
    DocumentoChecklist,
    STEP_LABELS,
    STEP_ICONS,
    ESITI,
)
from web.helpers import get_agenda, get_fascicoli, get_wizard_pro
from web.services.hearing_preparation_dashboard import build_hearing_preparation_dashboard

wizard_pro_bp = Blueprint("wizard_pro", __name__, url_prefix="/wizard-pro")

N_STEP = 5


# ─────────────────────────────────────────────────── helpers interni

def _richiedi_login(f):
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def _get_or_404(id_sessione: str) -> SessioneWizardPro:
    wiz = get_wizard_pro()
    sessione = wiz.carica(id_sessione)
    if not sessione:
        flash("Preparazione udienza non trovata.", "danger")
    return sessione


def _steps_stato(sessione: SessioneWizardPro) -> list:
    """Restituisce la lista degli stati per il progress stepper."""
    confermati = [
        sessione.step1_confermato,
        sessione.step2_confermato,
        sessione.step3_confermato,
        sessione.step4_confermato,
        sessione.step5_confermato,
    ]
    return [
        {
            "n": i + 1,
            "label": STEP_LABELS[i + 1],
            "icon": STEP_ICONS[i + 1],
            "confermato": confermati[i],
        }
        for i in range(N_STEP)
    ]


def _checklist_da_fascicolo(fascicolo) -> list:
    """Crea la checklist documenti pre-popolata dai documenti del fascicolo."""
    items = []
    for doc in getattr(fascicolo, "documenti", []):
        items.append(DocumentoChecklist(
            id_documento=doc.id,
            label=doc.nome,
            tipo=getattr(doc, "tipo", ""),
            obbligatorio=False,
            stato="da_portare",
            note="",
            nome_file=doc.nome,
            firmato=getattr(doc, "firmato_digitalmente", False),
        ).to_dict())
    return items


# ─────────────────────────────────────────────────── ROUTE: INDEX

@wizard_pro_bp.route("/", methods=["GET"])
@_richiedi_login
def index():
    return render_template(
        "wizard_pro/index.html",
        dashboard=build_hearing_preparation_dashboard(
            selected_fascicolo_id=request.args.get("id_fascicolo", "").strip()
        ),
    )


# ─────────────────────────────────────────────────── ROUTE: NUOVO

@wizard_pro_bp.route("/nuovo", methods=["GET", "POST"])
@_richiedi_login
def nuovo():
    gf = get_fascicoli()
    ga = get_agenda()

    if request.method == "POST":
        id_fascicolo = request.form.get("id_fascicolo", "").strip()
        id_appuntamento = request.form.get("id_appuntamento", "").strip()
        titolo_custom = request.form.get("titolo", "").strip()

        if not id_fascicolo:
            flash("Seleziona un fascicolo.", "warning")
            return redirect(url_for("wizard_pro.nuovo"))

        fasc = gf.get(id_fascicolo)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("wizard_pro.nuovo"))

        # Titolo automatico se non specificato
        if not titolo_custom:
            rg = getattr(fasc, "rg_completo", None) or getattr(fasc, "numero_rg", "") or fasc.numero
            titolo_custom = f"Udienza {fasc.titolo}"
            if rg:
                titolo_custom = f"Udienza RG {rg} — {fasc.titolo}"

        avvocato = ""
        u = g.get("utente_corrente")
        if u:
            avvocato = getattr(u, "nome_completo", "") or getattr(u, "username", "")

        sessione = SessioneWizardPro.nuova(
            id_fascicolo=id_fascicolo,
            titolo=titolo_custom,
            id_appuntamento=id_appuntamento,
            avvocato=avvocato,
        )

        # Pre-popola checklist documenti dal fascicolo
        sessione.checklist_documenti = _checklist_da_fascicolo(fasc)

        wiz = get_wizard_pro()
        wiz.salva(sessione)

        flash(f"Preparazione udienza avviata: «{sessione.titolo}»", "success")
        return redirect(url_for("wizard_pro.step", id_sessione=sessione.id, n=1))

    # GET — form selezione fascicolo
    fascicoli = sorted(
        gf.tutti(),
        key=lambda f: (f.data_prossima_udienza or f.modificato_il or f.data_apertura or ""),
        reverse=True,
    )

    # Fascicolo e appuntamento pre-selezionati dai querystring
    id_fascicolo_pre = request.args.get("id_fascicolo", "")
    id_appuntamento_pre = request.args.get("id_appuntamento", "")

    # Appuntamenti UDIENZA prossimi
    from pct.agenda import TipoAppuntamento
    appuntamenti_udienza = [
        a for a in ga.tutti()
        if getattr(a, "tipo", None) == TipoAppuntamento.UDIENZA
        and (a.data_ora or "") >= datetime.now().strftime("%Y-%m-%d")
    ]
    appuntamenti_udienza.sort(key=lambda a: a.data_ora or "")

    redirect_args = {}
    if id_fascicolo_pre:
        redirect_args["id_fascicolo"] = id_fascicolo_pre
    return redirect(url_for("wizard_pro.index", **redirect_args))


# ─────────────────────────────────────────────────── ROUTE: STEP

@wizard_pro_bp.route("/<id_sessione>/step/<int:n>", methods=["GET", "POST"])
@_richiedi_login
def step(id_sessione: str, n: int):
    if n < 1 or n > N_STEP:
        flash("Step non valido.", "danger")
        return redirect(url_for("wizard_pro.index"))

    sessione = _get_or_404(id_sessione)
    if not sessione:
        return redirect(url_for("wizard_pro.index"))

    gf = get_fascicoli()
    fascicolo = gf.get(sessione.id_fascicolo) if sessione.id_fascicolo else None

    appuntamento = None
    if sessione.id_appuntamento:
        try:
            ga = get_agenda()
            appuntamento = ga.get(sessione.id_appuntamento)
        except Exception:
            pass

    wiz = get_wizard_pro()

    # ── POST: salva dati step ──────────────────────────────────────────
    if request.method == "POST":
        f = request.form

        if n == 1:
            sessione.step1_note = f.get("step1_note", "")
            sessione.step1_confermato = True
            sessione.step_corrente = max(sessione.step_corrente, 2)

        elif n == 2:
            # Aggiorna stati documenti checklist (chiave = indice posizionale)
            nuova_checklist = []
            for i, doc_dict in enumerate(sessione.checklist_documenti):
                doc = DocumentoChecklist.from_dict(doc_dict)
                doc.stato = f.get(f"doc_stato_{i}", doc.stato)
                doc.note = f.get(f"doc_note_{i}", doc.note)
                nuova_checklist.append(doc.to_dict())

            # Documenti aggiuntivi (virtuali) aggiunti manualmente
            label_extra = f.get("doc_extra_label", "").strip()
            if label_extra:
                nuova_checklist.append(DocumentoChecklist(
                    id_documento="",
                    label=label_extra,
                    tipo="ALTRO",
                    obbligatorio=False,
                    stato="da_portare",
                ).to_dict())

            sessione.checklist_documenti = nuova_checklist
            sessione.step2_confermato = True
            sessione.step_corrente = max(sessione.step_corrente, 3)

        elif n == 3:
            sessione.note_preparazione = f.get("note_preparazione", "")
            sessione.argomenti_principali = f.get("argomenti_principali", "")
            sessione.richieste_giudice = f.get("richieste_giudice", "")
            sessione.eccezioni_da_sollevare = f.get("eccezioni_da_sollevare", "")
            sessione.step3_confermato = True
            sessione.step_corrente = max(sessione.step_corrente, 4)

        elif n == 4:
            sessione.precheck_firma_ok = bool(f.get("precheck_firma_ok"))
            sessione.precheck_docs_pronti = bool(f.get("precheck_docs_pronti"))
            sessione.precheck_cliente_notificato = bool(f.get("precheck_cliente_notificato"))
            sessione.precheck_trasporto_ok = bool(f.get("precheck_trasporto_ok"))
            sessione.precheck_note = f.get("precheck_note", "")
            sessione.step4_confermato = True
            sessione.step_corrente = max(sessione.step_corrente, 5)

        elif n == 5:
            sessione.esito = f.get("esito", "")
            sessione.esito_rinvio_data = f.get("esito_rinvio_data", "")
            sessione.esito_note_verbale = f.get("esito_note_verbale", "")
            sessione.esito_azioni = f.get("esito_azioni", "")
            sessione.esito_aggiorna_fascicolo = bool(f.get("esito_aggiorna_fascicolo"))
            sessione.step5_confermato = True
            sessione.stato = "completato"
            sessione.completato_il = datetime.now().isoformat()

            # Aggiorna il fascicolo se richiesto
            if sessione.esito_aggiorna_fascicolo and fascicolo:
                _aggiorna_fascicolo_da_esito(sessione, fascicolo, gf)

            wiz.salva(sessione)
            flash("Preparazione udienza completata.", "success")
            return redirect(url_for("wizard_pro.completo", id_sessione=id_sessione))

        wiz.salva(sessione)

        # Vai al prossimo step
        if n < N_STEP:
            return redirect(url_for("wizard_pro.step", id_sessione=id_sessione, n=n + 1))
        return redirect(url_for("wizard_pro.completo", id_sessione=id_sessione))

    # ── GET: mostra step ──────────────────────────────────────────────
    return render_template(
        "wizard_pro/step.html",
        sessione=sessione,
        fascicolo=fascicolo,
        appuntamento=appuntamento,
        step_n=n,
        n_step=N_STEP,
        steps_stato=_steps_stato(sessione),
        step_labels=STEP_LABELS,
        step_icons=STEP_ICONS,
        esiti=ESITI,
        docs_checklist=sessione.docs_checklist,
        oggi=datetime.now().date(),
    )


# ─────────────────────────────────────────────────── ROUTE: COMPLETO

@wizard_pro_bp.route("/<id_sessione>/completo", methods=["GET"])
@_richiedi_login
def completo(id_sessione: str):
    sessione = _get_or_404(id_sessione)
    if not sessione:
        return redirect(url_for("wizard_pro.index"))

    gf = get_fascicoli()
    fascicolo = gf.get(sessione.id_fascicolo) if sessione.id_fascicolo else None

    appuntamento = None
    if sessione.id_appuntamento:
        try:
            ga = get_agenda()
            appuntamento = ga.get(sessione.id_appuntamento)
        except Exception:
            pass

    return render_template(
        "wizard_pro/completo.html",
        sessione=sessione,
        fascicolo=fascicolo,
        appuntamento=appuntamento,
        steps_stato=_steps_stato(sessione),
        step_labels=STEP_LABELS,
        step_icons=STEP_ICONS,
        esiti=ESITI,
    )


# ─────────────────────────────────────────────────── ROUTE: ELIMINA

@wizard_pro_bp.route("/<id_sessione>/elimina", methods=["POST"])
@_richiedi_login
def elimina(id_sessione: str):
    wiz = get_wizard_pro()
    if wiz.elimina(id_sessione):
        flash("Sessione di preparazione eliminata.", "success")
    else:
        flash("Sessione non trovata.", "danger")
    return redirect(url_for("wizard_pro.index"))


# ─────────────────────────────────────────────────── ROUTE: ARCHIVIA

@wizard_pro_bp.route("/<id_sessione>/archivia", methods=["POST"])
@_richiedi_login
def archivia(id_sessione: str):
    wiz = get_wizard_pro()
    sessione = wiz.carica(id_sessione)
    if sessione:
        sessione.stato = "archiviato"
        wiz.salva(sessione)
        flash("Sessione archiviata.", "success")
    else:
        flash("Sessione non trovata.", "danger")
    return redirect(url_for("wizard_pro.index"))


# ─────────────────────────────────────────────────── ROUTE: PER FASCICOLO

@wizard_pro_bp.route("/fascicolo/<id_fasc>", methods=["GET"])
@_richiedi_login
def per_fascicolo(id_fasc: str):
    """Elenca o avvia il wizard per un fascicolo specifico."""
    wiz = get_wizard_pro()
    sessioni = wiz.lista_per_fascicolo(id_fasc)
    # Se c'è una sessione in corso, vai direttamente
    in_corso = [s for s in sessioni if s.stato == "in_corso"]
    if len(in_corso) == 1:
        return redirect(url_for("wizard_pro.step", id_sessione=in_corso[0].id, n=in_corso[0].step_corrente))
    # Altrimenti vai al nuovo con fascicolo pre-selezionato
    if not sessioni:
        return redirect(url_for("wizard_pro.index", id_fascicolo=id_fasc))
    # Più sessioni: vai all'index
    return redirect(url_for("wizard_pro.index"))


# ─────────────────────────────────────────────────── HELPERS INTERNI

def _safe_key(s: str) -> str:
    """Trasforma una stringa in una chiave CSS/form sicura."""
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)[:40]


def _aggiorna_fascicolo_da_esito(
    sessione: SessioneWizardPro,
    fascicolo,
    gf,
) -> None:
    """Aggiunge AttivitaProcessuale e aggiorna dati udienza nel fascicolo."""
    try:
        from pct.fascicoli import TipoAttivita, EsitoAttivita

        # Mappa esito → EsitoAttivita
        esito_map = {
            "favorevole":  EsitoAttivita.FAVOREVOLE,
            "parziale":    EsitoAttivita.PARZIALE,
            "sfavorevole": EsitoAttivita.SFAVOREVOLE,
            "rinvio":      EsitoAttivita.IN_ATTESA,
            "sospeso":     EsitoAttivita.IN_ATTESA,
        }
        esito_att = esito_map.get(sessione.esito, EsitoAttivita.IN_ATTESA)

        descrizione = (
            f"Esito: {sessione.label_esito}.\n"
            + (f"Note verbale: {sessione.esito_note_verbale}\n" if sessione.esito_note_verbale else "")
            + (f"Azioni: {sessione.esito_azioni}" if sessione.esito_azioni else "")
        ).strip()

        gf.aggiungi_attivita(
            fascicolo.id,
            tipo=TipoAttivita.UDIENZA,
            data=datetime.now().strftime("%Y-%m-%d"),
            titolo=sessione.titolo,
            descrizione=descrizione,
            esito=esito_att,
            note=f"[Preparazione Udienza: {sessione.id}]",
            id_appuntamento=sessione.id_appuntamento,
            avvocato=sessione.avvocato,
        )

        # Aggiorna data prossima udienza se rinvio
        if sessione.esito == "rinvio" and sessione.esito_rinvio_data:
            gf.aggiorna(fascicolo.id, data_prossima_udienza=sessione.esito_rinvio_data)

    except Exception as e:
        current_app.logger.warning("Preparazione Udienza: impossibile aggiornare fascicolo: %s", e)
