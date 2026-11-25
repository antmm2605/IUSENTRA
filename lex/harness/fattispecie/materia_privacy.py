"""Protezione dei dati personali: reclamo al Garante e ricorso al giudice ordinario.

Base normativa (testo vigente): artt. 77, 79, 82 Reg. UE 2016/679; artt. 140-bis, 141, 142, 152 d.lgs. 196/2003;
art. 10 d.lgs. 150/2011.
"""
from __future__ import annotations

from .schede import R, Scheda, p

_DATI = (r"provvedimento del garante|(?:reclamo|segnalazione|ricorso) al garante|garante (?:della )?privacy|garante per la protezione|privacy|dati personali|\bgdpr\b|trattamento (?:dei|illecito)|"
         r"dati (?:sanitari|sensibili)|telecamer|videosorveglianz|telemarketing|chiamate pubblicitarie|diritto (?:di accesso|all oblio)")

RECLAMO_GARANTE = Scheda(
    regola="priv_reclamo_garante", materia="privacy", nome="reclamo al Garante per la protezione dei dati personali",
    segnali=(_DATI, r"garante|reclamo|segnalar"), esclusi=(r"risarciment|tribunale|opposizione al provvedimento|ricorr\w* al giudice|rigettat\w* il reclamo",),
    punteggio=6,
    capito="Interessato che lamenta un trattamento dei propri dati in violazione del GDPR.",
    rimedio="reclamo al Garante (in alternativa al ricorso al giudice per lo stesso oggetto)",
    conclusione=[
        p("L'interessato che ritenga violati i propri diritti può proporre reclamo al Garante o ricorso all'autorità "
          "giudiziaria: il reclamo non si propone se per lo stesso oggetto e fra le stesse parti è già adito il giudice, e lo "
          "rende poi improponibile.",
          R("privacy:140bis", "puo' proporre reclamo al Garante o ricorso dinanzi all'autorita' giudiziaria"),
          R("privacy:140bis", "rende improponibile un'ulteriore domanda dinanzi all'autorita' giudiziaria")),
        p("Il reclamo indica in modo dettagliato fatti, disposizioni violate, misure richieste e titolare del trattamento, ed "
          "è sottoscritto dall'interessato o da un ente del terzo settore su suo mandato.",
          R("privacy:142", "indicazione per quanto possibile dettagliata dei fatti e delle circostanze"),
          R("privacy:141", "mediante reclamo ai sensi dell'articolo 77 del Regolamento")),
    ],
    cosa_fare=["Esercitare prima i diritti verso il titolare (accesso, cancellazione, opposizione) e conservare la richiesta.",
               "Predisporre il reclamo con documenti e misure richieste."],
    dati=["titolare del trattamento", "fatti e date", "richieste già fatte al titolare e risposte"],
)

RICORSO_GIUDICE_PRIVACY = Scheda(
    regola="priv_ricorso_giudice", materia="privacy", nome="ricorso al giudice per violazione dei dati personali e opposizione ai provvedimenti del Garante",
    segnali=(_DATI, r"risarciment|giudice|tribunale|ricorso|opposizione al provvedimento|provvedimento del garante|danno"),
    punteggio=6,
    capito="Azione giudiziaria per violazione della normativa sui dati personali o contro un provvedimento del Garante.",
    rimedio="ricorso al tribunale (rito del lavoro) del luogo del titolare o dell'interessato",
    conclusione=[
        p("Chi subisce un danno materiale o immateriale da violazione del GDPR ha diritto al risarcimento dal titolare o dal "
          "responsabile del trattamento.", R("gdpr:82", "ha il diritto di ottenere il risarcimento del danno")),
        p("Le controversie sono del giudice ordinario e seguono il rito del lavoro; sono competenti in alternativa il tribunale "
          "del luogo del titolare o quello di residenza dell'interessato.",
          R("privacy:152", "sono attribuite all'autorita' giudiziaria ordinaria"),
          R("dlgs150:10", "sono regolate dal rito del lavoro"),
          R("dlgs150:10", "il tribunale del luogo di residenza dell'interessato")),
        p("Il ricorso contro i provvedimenti del Garante si propone, a pena di inammissibilità, entro trenta giorni dalla "
          "comunicazione (sessanta se il ricorrente risiede all'estero).",
          R("dlgs150:10", "entro trenta giorni dalla data di comunicazione del provvedimento")),
    ],
    dati=["titolare del trattamento e sua sede", "violazione e danno", "eventuale provvedimento del Garante e data di comunicazione"],
)

SCHEDE = (RECLAMO_GARANTE, RICORSO_GIUDICE_PRIVACY)
