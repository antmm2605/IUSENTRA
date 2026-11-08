"""Catalogo dei canali ufficiali delle Notizie utili.

Ogni canale è stato interrogato dal PC dello studio l'08/11/2026 e ha risposto con
un feed valido e voci datate (vedi `verificato_il`). I canali delle pagine
istituzionali già lette da `pct.notizie_utili` (Ministero della Giustizia, PST,
CNF, Cassa Forense, Corte di cassazione) sono censiti qui con formato «html» e
restano letti da quel modulo.

Fonti valutate e non inserite (verifica 08/11/2026):
- Corte costituzionale (sito): risponde con una pagina di verifica anti-robot
  (Radware). Le pronunce arrivano comunque dalla Gazzetta Ufficiale, 1a Serie
  speciale «Corte costituzionale» (feed ufficiale S1), insieme agli atti di
  promovimento (ricorsi e ordinanze di rimessione).
- Normattiva: nessun feed delle novità; gli atti nuovi sono gli stessi della
  Gazzetta Ufficiale Serie generale, già acquisita.
- Giustizia amministrativa (Consiglio di Stato, Adunanza plenaria): la pagina dei
  provvedimenti si compone nel browser, non c'è un feed pubblico.
- Senato: risponde 202 senza contenuto (protezione anti-robot).
- Camera dei deputati: nessun feed pubblico raggiungibile (404).
- Corte dei conti: nessun feed (reindirizza alla home); resta nella pipeline
  degli aggiornamenti legali con il suo lettore dedicato.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lex.normativa import materie as m

# Tipi di notizia mostrati all'avvocato.
NORMA = "norma"
PRONUNCIA = "pronuncia"
PRASSI = "prassi"
AVVISO_PCT = "avviso_pct"
NOTIZIA = "notizia"

ETICHETTE_TIPO: dict[str, str] = {
    NORMA: "Norme e atti ufficiali",
    PRONUNCIA: "Pronunce",
    PRASSI: "Prassi e circolari",
    AVVISO_PCT: "Avvisi del processo telematico",
    NOTIZIA: "Notizie istituzionali",
}

VERIFICA_20261108 = "2026-11-08"

_HUDOC_ITALIA = (
    "https://hudoc.echr.coe.int/app/transform/rss?library=echreng&query=contentsitename%3AECHR%20AND%20"
    "(NOT%20(doctype%3DPR%20OR%20doctype%3DHFCOMOLD%20OR%20doctype%3DHECOMOLD))%20AND%20"
    "((respondent%3D%22ITA%22))%20AND%20((documentcollectionid2%3D%22JUDGMENTS%22))"
    "&sort=kpdate%20Descending&start=0&length=20"
)


@dataclass(frozen=True)
class Fonte:
    id: str
    etichetta: str
    ente: str
    url: str
    formato: str  # "rss" (lettore di questo pacchetto) o "html" (pct.notizie_utili)
    tipo: str
    frequenza_minuti: int
    verificato_il: str
    materia: str = ""  # materia di ripiego quando il testo non ne indica una
    # True quando l'ente ha competenza in una sola materia (INPS, Agenzia delle Entrate, Garante, UE, CNF)
    materia_certa: bool = False
    host_ammessi: tuple[str, ...] = field(default_factory=tuple)
    max_voci: int = 20
    # codice della fonte nella pipeline degli aggiornamenti legali (revisione)
    codice_aggiornamenti: str = ""


FONTI: tuple[Fonte, ...] = (
    Fonte(
        "gu_serie_generale", "Gazzetta Ufficiale", "Istituto Poligrafico e Zecca dello Stato — Gazzetta Ufficiale, Serie generale",
        "https://www.gazzettaufficiale.it/rss/SG", "rss", NORMA, 120, VERIFICA_20261108,
        host_ammessi=("www.gazzettaufficiale.it", "gazzettaufficiale.it"), max_voci=30,
        codice_aggiornamenti="gazzetta_ufficiale",
    ),
    Fonte(
        "gu_corte_costituzionale", "Corte costituzionale", "Corte costituzionale — Gazzetta Ufficiale, 1a Serie speciale",
        "https://www.gazzettaufficiale.it/rss/S1", "rss", PRONUNCIA, 360, VERIFICA_20261108,
        materia=m.COSTITUZIONE, host_ammessi=("www.gazzettaufficiale.it", "gazzettaufficiale.it"),
        codice_aggiornamenti="corte_costituzionale",
    ),
    Fonte(
        "eurlex_gu_l", "Gazzetta ufficiale UE", "Ufficio delle pubblicazioni dell'Unione europea — EUR-Lex, GU serie L",
        "https://eur-lex.europa.eu/IT/display-feed.rss?rssId=222", "rss", NORMA, 360, VERIFICA_20261108,
        materia=m.UE, materia_certa=True, host_ammessi=("eur-lex.europa.eu",), max_voci=15, codice_aggiornamenti="eur_lex",
    ),
    Fonte(
        "curia", "Corte di giustizia UE", "Corte di giustizia dell'Unione europea — comunicati stampa",
        "https://curia.europa.eu/site/rss.jsp?lang=it&secondLang=en", "rss", PRONUNCIA, 240, VERIFICA_20261108,
        materia=m.UE, materia_certa=True, host_ammessi=("curia.europa.eu",), codice_aggiornamenti="curia_cgue_rss",
    ),
    Fonte(
        "cedu_italia", "Corte EDU", "Corte europea dei diritti dell'uomo — HUDOC, sentenze nei confronti dell'Italia",
        _HUDOC_ITALIA, "rss", PRONUNCIA, 720, VERIFICA_20261108,
        materia=m.COSTITUZIONE, host_ammessi=("hudoc.echr.coe.int",),
    ),
    Fonte(
        "entrate_prassi", "Agenzia delle Entrate", "Agenzia delle Entrate — normativa e prassi",
        "https://www.agenziaentrate.gov.it/portale/c/portal/rss/entrate?idrss=0753fcb1-1a42-4f8c-f40d-02793c6aefb4",
        "rss", PRASSI, 240, VERIFICA_20261108,
        materia=m.TRIBUTARIO, materia_certa=True, host_ammessi=("www.agenziaentrate.gov.it",), codice_aggiornamenti="agenzia_entrate",
    ),
    Fonte(
        "inps_circolari", "INPS circolari", "Istituto nazionale della previdenza sociale — circolari",
        "https://www.inps.it/it/it.rss.circolari.xml", "rss", PRASSI, 360, VERIFICA_20261108,
        materia=m.LAVORO, materia_certa=True, host_ammessi=("www.inps.it",), max_voci=15, codice_aggiornamenti="inps_circolari",
    ),
    Fonte(
        "inps_messaggi", "INPS messaggi", "Istituto nazionale della previdenza sociale — messaggi",
        "https://www.inps.it/it/it.rss.messaggi.xml", "rss", PRASSI, 360, VERIFICA_20261108,
        materia=m.LAVORO, materia_certa=True, host_ammessi=("www.inps.it",), max_voci=15, codice_aggiornamenti="inps_messaggi",
    ),
    Fonte(
        "garante_privacy", "Garante privacy", "Garante per la protezione dei dati personali — notizie",
        "https://www.garanteprivacy.it/o/gpdp-rss/rss?t=news", "rss", NOTIZIA, 360, VERIFICA_20261108,
        materia=m.DIGITALE, materia_certa=True, host_ammessi=("www.garanteprivacy.it", "www.gpdp.it"),
        codice_aggiornamenti="garante_privacy",
    ),
    # Pagine istituzionali lette da pct.notizie_utili (già in uso prima del 08/11/2026).
    Fonte(
        "cassazione", "Corte di Cassazione", "Corte suprema di cassazione — ultime dalla Corte",
        "https://www.cortedicassazione.it/it/ultime_dalla_corte.page", "html", PRONUNCIA, 120, VERIFICA_20261108,
        host_ammessi=("www.cortedicassazione.it", "cortedicassazione.it"),
        codice_aggiornamenti="cassazione_ultime_sent_ord_questioni",
    ),
    Fonte(
        "pst_giustizia", "PST Giustizia", "Ministero della Giustizia — Portale dei servizi telematici, avvisi",
        "https://pst.giustizia.it/PST/it/news.page?metadata_category_frame6=avvisi", "html", AVVISO_PCT, 180,
        VERIFICA_20261108, materia=m.GIUSTIZIA, host_ammessi=("pst.giustizia.it",),
    ),
    Fonte(
        "giustizia", "Ministero della Giustizia", "Ministero della Giustizia — decreti, circolari, direttive e provvedimenti",
        "https://www.giustizia.it/giustizia/page/it/decreti_circolari_direttive_provvedimenti_note", "html", PRASSI, 720,
        VERIFICA_20261108, materia=m.GIUSTIZIA, host_ammessi=("www.giustizia.it", "giustizia.it"),
    ),
    Fonte(
        "cnf", "CNF", "Consiglio nazionale forense — notizie", "https://www.consiglionazionaleforense.it/", "html",
        NOTIZIA, 360, VERIFICA_20261108, materia=m.FORENSE, materia_certa=True,
        host_ammessi=("www.consiglionazionaleforense.it", "consiglionazionaleforense.it"),
    ),
    Fonte(
        "cassa_forense", "Cassa Forense", "Cassa nazionale di previdenza e assistenza forense — CF News",
        "https://www.cfnews.it/", "html", NOTIZIA, 720, VERIFICA_20261108, materia=m.FORENSE, materia_certa=True,
        host_ammessi=("www.cfnews.it", "cfnews.it"),
    ),
)

PER_ID: dict[str, Fonte] = {fonte.id: fonte for fonte in FONTI}


def fonte(fonte_id: str) -> Fonte | None:
    return PER_ID.get(str(fonte_id or "").strip())


__all__ = [
    "AVVISO_PCT", "ETICHETTE_TIPO", "FONTI", "Fonte", "NORMA", "NOTIZIA", "PER_ID", "PRASSI", "PRONUNCIA", "fonte",
]
