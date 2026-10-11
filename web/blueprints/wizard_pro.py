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
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from pct.wizard_pro import (
    SessioneWizardPro,
    DocumentoChecklist,
    STEP_LABELS,
    STEP_ICONS,
    ESITI,
)
from web.blueprints.react_shell import render_react_shell_response
from web.helpers import get_agenda, get_fascicoli, get_wizard_pro
from web.services.hearing_preparation_dashboard import build_hearing_preparation_dashboard
from web.services.preparazione_udienza_http_commands import persistent, governed_write

wizard_pro_bp = Blueprint("wizard_pro", __name__, url_prefix="/wizard-pro")

N_STEP = 5


def _richiede_vista_classica() -> bool:
    return str(request.args.get("_legacy", "")).strip().lower() in {"1", "true", "si", "sì", "yes"}


# ─────────────────────────────────────────────────── helpers interni

def _richiedi_login(f):
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        permissions = ["agenda.scrivi"] if request.method == "POST" else ["agenda.leggi"]
        if request.method == "POST" and kw.get("n") == 5:
            permissions.extend(["scadenziario.scrivi", "fascicoli.scrivi"])
        if not all(g.utente_corrente.ha_permesso(permission) for permission in permissions):
            return "Permesso insufficiente.", 403
        return f(*a, **kw)
    return w


def _governed_form(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        response = make_response(governed_write(current_app)(function)(*args, **kwargs))
        if response.status_code >= 400 and response.is_json:
            g._preparazioni_form_error = True
            error = response.get_json() or {}
            fields = list(request.form.items(multi=True))
            return render_template("wizard_pro/command_error.html", command_error=error,
                submitted_fields=fields, retry_href=request.full_path.rstrip("?"),
                can_retry=response.status_code == 503), response.status_code
        return response
    return wrapped


@wizard_pro_bp.context_processor
def _form_context():
    from uuid import uuid4
    if g.get("_preparazioni_form_error"):
        return {"preparazione_sql": False}
    manager = get_wizard_pro()
    return {"preparazione_sql": persistent(manager), "preparazione_command_key": str(uuid4())}


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
    if not _richiede_vista_classica():
        return render_react_shell_response("wizard-pro")
    return render_template(
        "wizard_pro/index.html",
        dashboard=build_hearing_preparation_dashboard(
            selected_fascicolo_id=request.args.get("id_fascicolo", "").strip()
        ),
    )


# ─────────────────────────────────────────────────── ROUTE: NUOVO

@wizard_pro_bp.route("/nuovo", methods=["GET", "POST"])
@_richiedi_login
@_governed_form
def nuovo():
    if request.method == "POST":
        id_fascicolo = request.form.get("id_fascicolo", "").strip()
        id_appuntamento = request.form.get("id_appuntamento", "").strip()
        titolo_custom = request.form.get("titolo", "").strip()

        wiz = get_wizard_pro()
        if persistent(wiz):
            from web.services.preparazione_udienza_form_commands import form_command
            from web.services.preparazione_udienza_http_commands import confirm
            command, _ = form_command(request.form, start=True)
            user = g.utente_corrente
            result = wiz.start(fascicolo_id=id_fascicolo, appuntamento_id=id_appuntamento, command_key=command,
                               avvocato=getattr(user, "nome_completo", "") or user.username, titolo=titolo_custom)
            sessione = confirm(wiz, result, command)
            if wiz.carica(sessione.id) is None:
                flash("Il precedente avvio era confermato; la preparazione è stata successivamente eliminata.", "warning")
                return redirect(url_for("wizard_pro.index"))
            flash("Preparazione udienza aperta.", "success")
            return redirect(url_for("wizard_pro.step", id_sessione=sessione.id, n=sessione.step_corrente))

        gf = get_fascicoli()

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

    # Il cruscotto esistente governa selezione e prossime udienze.
    id_fascicolo_pre = request.args.get("id_fascicolo", "")

    redirect_args = {}
    if id_fascicolo_pre:
        redirect_args["id_fascicolo"] = id_fascicolo_pre
    return redirect(url_for("wizard_pro.index", **redirect_args))


# ─────────────────────────────────────────────────── ROUTE: STEP

@wizard_pro_bp.route("/<id_sessione>/step/<int:n>", methods=["GET", "POST"])
@_richiedi_login
@_governed_form
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
        if persistent(wiz):
            from web.services.preparazione_udienza_form_commands import save_form
            save_form(wiz, sessione, n, f)
            if n == 5:
                flash("Esito e seguiti registrati.", "success")
                return redirect(url_for("wizard_pro.completo", id_sessione=id_sessione))
            return redirect(url_for("wizard_pro.step", id_sessione=id_sessione, n=min(n + 1, 5)))

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
    if not _richiede_vista_classica():
        return render_react_shell_response(f"wizard-pro/{id_sessione}/step/{n}")

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

    if not _richiede_vista_classica():
        return render_react_shell_response(f"wizard-pro/{id_sessione}/completo")

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
@_governed_form
def elimina(id_sessione: str):
    wiz = get_wizard_pro()
    if persistent(wiz):
        from web.services.preparazione_udienza_form_commands import form_command
        command, revision = form_command(request.form)
        from zoneinfo import ZoneInfo
        wiz.execute(id_sessione, "elimina", {}, command_key=command, expected_revision=revision,
                    today=datetime.now(ZoneInfo("Europe/Rome")).date())
        flash("Preparazione eliminata; attività e termini già registrati preservati.", "success")
        return redirect(url_for("wizard_pro.index"))
    if wiz.elimina(id_sessione):
        flash("Sessione di preparazione eliminata.", "success")
    else:
        flash("Sessione non trovata.", "danger")
    return redirect(url_for("wizard_pro.index"))


# ─────────────────────────────────────────────────── ROUTE: ARCHIVIA

@wizard_pro_bp.route("/<id_sessione>/archivia", methods=["POST"])
@_richiedi_login
@_governed_form
def archivia(id_sessione: str):
    wiz = get_wizard_pro()
    if persistent(wiz):
        from web.services.preparazione_udienza_form_commands import form_command
        command, revision = form_command(request.form)
        from zoneinfo import ZoneInfo
        wiz.execute(id_sessione, "archivia", {}, command_key=command, expected_revision=revision,
                    today=datetime.now(ZoneInfo("Europe/Rome")).date())
        flash("Preparazione archiviata.", "success")
        return redirect(url_for("wizard_pro.index"))
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
