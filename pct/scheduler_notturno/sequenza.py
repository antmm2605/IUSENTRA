"""Ordine dei lavori notturni, per dipendenza: chi produce i dati viene prima di chi li legge."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Passo:
    lavoro: str
    # Giorni della settimana (0 = lunedì) della sera di partenza in cui il passo si esegue; vuoto = tutti.
    giorni: tuple[int, ...] = ()
    # Passo che si ripete finché c'è lavoro, entro questo tempo (minuti); 0 = una sola esecuzione.
    ripeti_minuti: int = 0
    # Lavoro dello scheduler da eseguire quando il nome del passo è diverso (stesso lavoro due volte nella notte).
    esegue: str = ""


@dataclass(frozen=True)
class Fase:
    numero: int
    nome: str
    motivo: str
    passi: tuple[Passo, ...]
    usa_ai_locale: bool = False
    attendi_ocr: bool = False
    # Memoria libera minima (MB) prima di avviare un passo della fase.
    memoria_minima_mb: int = 1200
    note: tuple[str, ...] = field(default_factory=tuple)


ATTESA_OCR_LETTURE = "__attesa_ocr_letture"

# Giorno della sera di partenza: il lavoro della notte fra venerdì e sabato ha la sera di venerdì.
VENERDI, SABATO = 4, 5

FASI: tuple[Fase, ...] = (
    Fase(1, "Caselle PEC e presidio PEC",
         "Prima si scaricano e classificano le PEC: tutto il resto della notte lavora su questi dati.",
         (Passo("mailbox_sync_runtime"), Passo("pec_audit_pipeline_workers"), Passo("poll_pec_cancelleria"),
          Passo("polling_esiti_deposito"))),
    Fase(2, "PEC nel fascicolo e notifiche",
         "Le PEC classificate si collegano ai fascicoli e le notifiche L. 53/1994 alle relate: servono documenti già scaricati.",
         (Passo("pec_fascicolo_documenti_recupero", ripeti_minuti=40), Passo("legal_notification_relata_presidio"))),
    Fase(3, "OCR dei documenti nuovi",
         "Il worker OCR legge i documenti arrivati nelle fasi 1-2; la catena aspetta che la coda si svuoti (AI locale scaricata).",
         (), attendi_ocr=True),
    Fase(4, "Letture dell'archivio e sentenze",
         "I motori documenti e PEC leggono i testi OCR; la sentenza si legge dopo l'OCR.",
         (Passo("archivio_letture_automatico", ripeti_minuti=60),
          # I documenti senza testo arrivati stanotte vanno all'OCR solo dopo che il motore documenti li ha letti
          # (qui sopra): si aspetta la coda OCR e si rilegge, così la sentenza scansionata è letta nella stessa notte.
          Passo(ATTESA_OCR_LETTURE), Passo("archivio_letture_dopo_ocr", ripeti_minuti=30, esegue="archivio_letture_automatico"),
          Passo("letture_recupero_completo", giorni=(SABATO,)),
          Passo("lex_sentenza_economia_auto"), Passo("collaudo_lettore"))),
    Fase(5, "Scadenze, notifiche ed economia",
         "Scadenze, avvisi e presidio economico usano i fatti appena letti; il piano del giorno chiude la fase.",
         (Passo("aggiorna_scadute"), Passo("aggiorna_parcelle_scadute"), Passo("agenda_scadenziario_notifications"),
          Passo("fascicoli_document_economic_presidio"), Passo("profili_procedurali_riconvalida"),
          Passo("patrocinio_adeguamento_bimestrale"))),
    Fase(6, "Indici e Lex (AI locale)",
         "Catalogo, RAG, embedding e apprendimento di Lex: l'AI locale si carica solo qui e si scarica alla fine.",
         (Passo("catalogo_seconda_lettura_lex", ripeti_minuti=45), Passo("lex_operational_agents_nightly"),
          Passo("lex_dataset_nightly"), Passo("rag_rispezzatura_notturna", ripeti_minuti=60),
          Passo("lex_autonomous_learning_nightly"), Passo("local_ai_maintenance"),
          Passo("workspace_intelligence_snapshot")),
         usa_ai_locale=True, memoria_minima_mb=2000),
    Fase(7, "Aggiornamenti normativi e fonti ufficiali",
         "Fonti pubbliche: non dipendono dai fascicoli, quindi vengono dopo i lavori dello studio.",
         (Passo("legal_official_archives_daily"), Passo("legal_updates_batch"), Passo("cassazione_sentenzeweb_nightly"),
          Passo("corte_costituzionale_opendata_weekly", giorni=(VENERDI,)), Passo("mediazione_sources_refresh"),
          Passo("sync_tabelle_normative_daily"), Passo("sync_uffici"),
          Passo("pst_certificati_cifratura_weekly", giorni=(SABATO,)), Passo("legal_monitor_daily"),
          Passo("legal_sources_daily_check"))),
    Fase(8, "Manutenzione e backup",
         "Controlli dello spazio e della codifica, backup per ultimo (se abilitato). Il piano del giorno resta alle 05:30 nella stessa corsia lunga, quindi non si sovrappone.",
         (Passo("censimento_spazio_notturno"), Passo("utf8_integrity_nightly"),
          Passo("operational_backup_nightly"), Passo("backup_giornaliero"))),
)

# Lavori leggeri o diurni che restano anche di giorno con il loro orario (la catena li esegue una volta in più).
LAVORI_ANCHE_DI_GIORNO = frozenset({
    "mailbox_sync_runtime", "pec_audit_pipeline_workers", "poll_pec_cancelleria", "polling_esiti_deposito",
    "legal_notification_relata_presidio", "agenda_scadenziario_notifications",
})
# Lavori frequenti e pesanti: di giorno con il loro orario, di notte solo nella catena.
LAVORI_FREQUENTI_PESANTI = frozenset({
    "pec_fascicolo_documenti_recupero", "archivio_letture_automatico", "fascicoli_document_economic_presidio",
    "workspace_intelligence_snapshot", "local_ai_maintenance", "daily_plan_incremental_refresh",
})
# Lavori che usano l'AI locale: solo nella fase 6 (mai insieme all'OCR pesante).
LAVORI_SOLO_NOTTURNI_AI = frozenset({"catalogo_seconda_lettura_lex"})


def passi_in_ordine() -> list[tuple[Fase, Passo]]:
    return [(fase, passo) for fase in FASI for passo in (fase.passi or (Passo(f"__fase_{fase.numero}"),))]


def lavori_della_sequenza() -> frozenset[str]:
    """I lavori dello scheduler eseguiti dalla catena (un passo con ``esegue`` usa il lavoro indicato)."""
    return frozenset(p.esegue or p.lavoro for _f, p in passi_in_ordine() if not p.lavoro.startswith("__"))


def lavori_solo_notturni() -> frozenset[str]:
    """Lavori che di notte non partono più a orario fisso ma solo nella catena (e di giorno restano spenti)."""
    return lavori_della_sequenza() - LAVORI_ANCHE_DI_GIORNO - LAVORI_FREQUENTI_PESANTI
