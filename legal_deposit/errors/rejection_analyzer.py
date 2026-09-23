from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PST_CONTROL_ERRORS_SOURCE = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "Codifica_errori_controlli_1.0.pdf"
)
PST_CONTROL_ERRORS_SHA256 = "B20C0046FD0000166BC69CB8F1DAB8981A43CE94D913E803BA032D7CE09EBC6B"


@dataclass(slots=True)
class RejectionDiagnosis:
    category: str
    severity: str
    human_message: str
    technical_message: str = ""
    suggested_fix: str = ""
    auto_fix_available: bool = False
    can_resubmit: bool = False
    requires_lawyer_review: bool = True
    ministerial_level: str = ""
    ministerial_source: str = ""


# (categoria, livello, messaggio leggibile, azione, forme ufficiali presenti nella tabella PST)
PST_CONTROL_ERROR_RULES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("depositante_non_attivo", "ERROR", "Il depositante risulta radiato, sospeso o cancellato.", "Verifica lo stato professionale e ripeti il deposito.", ("depositante radiato sospeso o cancellato", "status della certificazione impostato a r", "status della certificazione impostato a s")),
    ("busta_non_elaborabile", "FATAL", "La busta non è stata elaborata dal server ricevente.", "Richiedi la verifica tecnica dell'ufficio e ripeti il deposito.", ("busta non elaborabile", "errore server busta non elaborata")),
    ("contenuti_non_elaborabili", "FATAL", "Il sistema non riesce a elaborare l'impronta dell'atto principale.", "Richiedi la verifica tecnica dell'ufficio e ripeti il deposito.", ("attestazione xml o certificazione xml non elaborabili", "impossibile elaborare impronta hash dell atto principale")),
    ("errore_imprevisto_controlli", "FATAL", "I controlli si sono conclusi con un errore imprevisto.", "Richiedi la verifica tecnica dell'ufficio e ripeti il deposito.", ("errore generico e imprevisto alla fine dei controlli", "errore imprevisto")),
    ("busta_non_decifrabile", "FATAL", "La busta non può essere decifrata.", "Ripeti il deposito usando il certificato di cifratura corretto.", ("impossibile decifrare la busta",)),
    ("indice_busta_assente", "FATAL", "L'indice della busta non è presente.", "Rigenera la busta completa e ripeti il deposito.", ("indicebusta xml non presente", "indice busta non trovato")),
    ("indice_busta_non_corretto", "FATAL", "L'indice della busta non è nel formato corretto.", "Rigenera la busta completa e ripeti il deposito.", ("indicebusta in formato non corretto", "indice busta non corretto")),
    ("allegato_indice_assente", "ERROR", "Manca un allegato dichiarato nell'indice della busta.", "Allinea indice e allegati, quindi ripeti il deposito.", ("assenza di allegati indicati nell indice della busta", "assente allegato definito in indice busta")),
    ("atto_principale_mancante", "FATAL", "Manca l'atto principale dichiarato nell'indice della busta.", "Inserisci l'atto principale, rigenera la busta e ripeti il deposito.", ("non e presente l atto giudiziario definito in indicebusta", "atto principale mancante")),
    ("certificato_firma_non_valido", "ERROR", "Il certificato di firma non è valido.", "Apponi una firma con certificato valido e ripeti il deposito.", ("certificato di firma non valido", "certificato firma non valido")),
    ("certificato_firma_scaduto", "ERROR", "Il certificato di firma è scaduto.", "Apponi una firma con certificato valido e ripeti il deposito.", ("certificato firma scaduto",)),
    ("atto_firma_non_integra", "ERROR", "L'atto non è integro rispetto alla firma elettronica.", "Rigenera e firma nuovamente l'atto, quindi ripeti il deposito.", ("atto non integro rispetto alla firma elettronica apposta sullo stesso", "atto non integro rispetto alla firma digitale")),
    ("mittente_non_firmatario", "ERROR", "Il mittente non è tra i firmatari dell'atto.", "Verifica mittente e firmatari, quindi ripeti il deposito.", ("il mittente non e tra i firmatari dell atto",)),
    ("xml_non_conforme_schema", "ERROR", "Il documento XML non è conforme allo schema di riferimento.", "Rigenera il documento XML conforme e ripeti il deposito.", ("documento non valido rispetto allo schema di riferimento", "documento xml non conforme rispetto agli schema di riferimento")),
    ("firmatario_non_parte", "ERROR", "Il firmatario non risulta costituito parte in causa.", "Verifica anagrafica e costituzione del firmatario, quindi ripeti il deposito.", ("firmatario dell atto non e costituito parte in causa", "firmatario non parte in causa")),
    ("numero_ruolo_mancante", "ERROR", "Il numero di ruolo non è indicato.", "Inserisci il numero di ruolo corretto e ripeti il deposito.", ("numero di ruolo non indicato",)),
    ("numero_ruolo_non_valido", "ERROR", "Il numero di ruolo non esiste nel registro di cancelleria.", "Verifica registro e numero di ruolo, quindi ripeti il deposito.", ("numero di ruolo non esistente nel registro di cancelleria", "numero di ruolo non valido")),
    ("firmatario_non_costituito_introduttivo", "ERROR", "Il firmatario non risulta costituito nell'atto introduttivo.", "Correggi i dati del firmatario e ripeti il deposito.", ("firmatario non e costituito nell atto introduttivo",)),
    ("deposito_fuori_termine", "WARN", "Il deposito risulta eseguito fuori termine.", "Attendi la valutazione della cancelleria: l'atto viene comunque accettato.", ("atto depositato fuori termine", "termini di deposito scaduti")),
    ("procura_assente", "WARN", "La procura alle liti risulta assente per un atto introduttivo.", "Attendi la valutazione della cancelleria: l'atto viene comunque accettato.", ("assente allegato procura alle liti", "allegato procura alle liti assente")),
    ("iscrizione_ruolo_assente", "ERROR", "Manca l'allegato di iscrizione a ruolo richiesto.", "Aggiungi l'iscrizione a ruolo e ripeti il deposito.", ("assente allegato iscrizione al ruolo", "allegato iscrizione a ruolo assente")),
    ("formato_file_non_ammesso", "ERROR", "Un allegato usa un formato di file non ammesso.", "Converti o sostituisci l'allegato e ripeti il deposito.", ("formato di file non ammesso",)),
    ("allegato_non_riconosciuto", "ERROR", "Un allegato non è stato riconosciuto.", "Rigenera o sostituisci l'allegato e ripeti il deposito.", ("allegato non riconosciuto",)),
    ("allegato_formato_non_conforme", "ERROR", "Un allegato non è conforme al formato richiesto.", "Converti o sostituisci l'allegato e ripeti il deposito.", ("allegato non conforme al formato del file richiesto dalle regole tecniche",)),
    ("allegato_firma_non_integra", "ERROR", "Un allegato non è integro rispetto alla firma elettronica.", "Rigenera e firma nuovamente l'allegato, quindi ripeti il deposito.", ("allegato non integro rispetto alla firma elettronica apposta sullo stesso", "allegato non integro rispetto alla firma digitale", "allegato non integro rispetto alla firma difgitale")),
    ("allegato_extra_indice", "ERROR", "La busta contiene allegati non dichiarati nell'indice.", "Allinea indice e allegati, quindi ripeti il deposito.", ("presenza di allegati non indicati nell indice della busta", "presenza di allegati non definiti in indice busta")),
)

_LEVEL_TO_SEVERITY = {"FATAL": "critical", "ERROR": "high", "WARN": "warning"}


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


class RejectionAnalyzer:
    def analyze(self, text: str) -> RejectionDiagnosis:
        raw = str(text or "")
        lower = raw.lower()
        normalised = _normalise(raw)
        for category, level, message, action, patterns in PST_CONTROL_ERROR_RULES:
            if any(_normalise(pattern) in normalised for pattern in patterns):
                return RejectionDiagnosis(
                    category,
                    _LEVEL_TO_SEVERITY[level],
                    message,
                    technical_message=raw[:500],
                    suggested_fix=action,
                    can_resubmit=level in {"FATAL", "ERROR"},
                    ministerial_level=level,
                    ministerial_source=PST_CONTROL_ERRORS_SOURCE,
                )

        explicit_level = next(
            (level for level in ("FATAL", "ERROR", "WARN") if re.search(rf"\b{level}\b", raw, re.I)),
            "",
        )
        if explicit_level:
            return RejectionDiagnosis(
                "messaggio_ministeriale_non_catalogato",
                _LEVEL_TO_SEVERITY[explicit_level],
                "Il livello ministeriale è stato rilevato, ma il messaggio non coincide con la tabella ufficiale acquisita.",
                technical_message=raw[:500],
                suggested_fix="Sottoponi il dettaglio tecnico alla revisione dell'avvocato prima di qualsiasi nuovo invio.",
                ministerial_level=explicit_level,
                ministerial_source=PST_CONTROL_ERRORS_SOURCE,
            )

        if "troppo grande" in lower or "dimensione" in lower or "50 mb" in lower:
            return RejectionDiagnosis(
                "file_troppo_grande",
                "high",
                "Il file supera i limiti dimensionali del canale.",
                suggested_fix="Comprimi o separa gli allegati e prepara un nuovo invio.",
                auto_fix_available=True,
                can_resubmit=True,
            )
        if "firma non valida" in lower or "firma digitale" in lower:
            return RejectionDiagnosis(
                "firma_non_valida",
                "critical",
                "La firma digitale non risulta valida.",
                suggested_fix="Rigenera la firma con certificato valido e ripeti la validazione.",
                can_resubmit=True,
            )
        if "certificato scaduto" in lower:
            return RejectionDiagnosis(
                "certificato_scaduto",
                "critical",
                "Il certificato di firma risulta scaduto.",
                suggested_fix="Usa un certificato valido prima di procedere.",
                can_resubmit=False,
            )
        if "pdf/a" in lower or "pdf non conforme" in lower:
            return RejectionDiagnosis(
                "pdf_non_conforme",
                "high",
                "Il PDF non risulta conforme.",
                suggested_fix="Converti o rigenera il PDF in formato conforme.",
                auto_fix_available=True,
                can_resubmit=True,
            )
        return RejectionDiagnosis(
            "errore_sconosciuto",
            "medium",
            "Errore non classificato automaticamente.",
            technical_message=raw[:500],
            suggested_fix="Verifica il dettaglio tecnico e chiedi revisione dell'avvocato.",
            can_resubmit=False,
        )
