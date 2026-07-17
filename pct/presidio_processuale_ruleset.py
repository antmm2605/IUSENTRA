"""Ruleset deterministico per il presidio documentale processuale.

Le regole non sostituiscono la valutazione dell'avvocato: servono a
classificare i documenti e ad avviare parser mirati quando il nome del file e'
generico o errato.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable


RULESET_VERSION = "presidio_processuale_ruleset_v1_2026_07_07"


@dataclass(frozen=True, slots=True)
class PresidioRule:
    code: str
    sector: str
    label: str
    legal_basis: tuple[str, ...]
    patterns: tuple[str, ...]
    negative_patterns: tuple[str, ...] = ()
    classification: str = ""
    parser_fields: tuple[str, ...] = ()


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_presidio_text(value: Any) -> str:
    raw = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", _text(value))
    raw = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", raw)
    folded = unicodedata.normalize("NFKD", raw.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def metadata_probe(metadata: dict[str, Any] | None) -> str:
    if not metadata:
        return ""
    chunks: list[str] = []
    for value in metadata.values():
        if isinstance(value, (str, int, float)):
            chunks.append(str(value))
        elif isinstance(value, (list, tuple, set)):
            chunks.extend(str(item) for item in value if isinstance(item, (str, int, float)))
        elif isinstance(value, dict):
            chunks.extend(str(item) for item in value.values() if isinstance(item, (str, int, float)))
    return " ".join(chunks)


RG_RE = re.compile(
    r"\b(?:r\.?\s*g\.?|n\.?\s*r\.?\s*g\.?|ruolo\s+generale|registro\s+generale|"
    r"numero\s+ruolo)\s*(?:n\.?)?\s*(?P<number>\d{1,7})\s*/\s*(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)

PLAIN_RG_RE = re.compile(r"\b(?P<number>\d{1,7})\s*/\s*(?P<year>(?:19|20)\d{2})\b", re.IGNORECASE)

DATE_RE = re.compile(r"\b(?P<day>[0-3]?\d)[./-](?P<month>[01]?\d)[./-](?P<year>(?:19|20)\d{2})\b")

MONEY_AMOUNT_PATTERN = r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[,.]\d{2})"
MONEY_RE = re.compile(
    r"(?:(?:€|euro|eur)\s*(?P<amount1>" + MONEY_AMOUNT_PATTERN + r")|"
    r"(?P<amount2>" + MONEY_AMOUNT_PATTERN + r")\s*(?:€|euro|eur))",
    re.IGNORECASE,
)

PAGOPA_RT_XML_RE = re.compile(
    r"<\s*(?:[A-Za-z0-9_:-]+:)?RT\b|"
    r"<[^>]*(?:identificativoMessaggioRicevuta|datiPagamento|codiceEsitoPagamento|"
    r"importoTotalePagato|singoloImportoPagato|datiSpecificiRiscossione)[^>]*>",
    re.IGNORECASE,
)

PAGOPA_RT_CU_RE = re.compile(
    r"<[^>]*(?:causaleVersamento|datiSpecificiRiscossione)[^>]*>[^<]*"
    r"(?:contribut|CONTRIB|0702100TS|Ministero\s+della\s+Giustizia)",
    re.IGNORECASE | re.DOTALL,
)


PRESIDIO_RULES: tuple[PresidioRule, ...] = (
    PresidioRule(
        code="identita_rg",
        sector="identita_fascicolo",
        label="Numero di ruolo generale",
        legal_basis=("Identificazione fascicolo",),
        patterns=(r"\br\s*g\b", r"\bn\s*r\s*g\b", r"\bruolo\s+generale\b", r"\bregistro\s+generale\b"),
        classification="identity",
        parser_fields=("rg_number", "rg_year"),
    ),
    PresidioRule(
        code="sentenza_strutturale",
        sector="provvedimenti",
        label="Sentenza o provvedimento decisorio",
        legal_basis=("art. 133 c.p.c.", "artt. 91-93 c.p.c."),
        patterns=(
            r"\bsentenza\b",
            r"\bdeposito\s+sentenza\b",
            r"\bpubblicazione\s+sentenza\b",
            r"\brepubblica\s+italiana\b",
            r"\bin\s+nome\s+del\s+popolo\s+italiano\b",
            r"\bp\s*q\s*m\b",
            r"\bdefinitivamente\s+pronunciando\b",
            r"\bdispositivo\b",
            r"\blettura\s+del\s+dispositivo\b",
        ),
        negative_patterns=(r"\bbozza\s+sentenza\b", r"\bcita\s+la\s+sentenza\b"),
        classification="sentenza",
        parser_fields=("sentence_number", "sentence_date", "rg", "pqm"),
    ),
    PresidioRule(
        code="spese_liquidazione",
        sector="economico",
        label="Liquidazione spese e compensi",
        legal_basis=("art. 91 c.p.c.", "D.M. 55/2014 art. 2"),
        patterns=(
            r"\bcondanna\s+(?:.+\s+)?alle\s+spese\b",
            r"\brifusione\s+delle\s+spese\b",
            r"\bliquida\b",
            r"\bliquidando\b",
            r"\bliquidazione\b",
            r"\bcompensi\b",
            r"\bonorari\b",
            r"\besborsi\b",
            r"\bspese\s+vive\b",
            r"\bspese\s+generali\b",
            r"\b15\s*%\b",
            r"\biva\b",
            r"\bcpa\b",
            r"\baccessori\s+di\s+legge\b",
        ),
        classification="sentenza_economica",
        parser_fields=("liquidazione", "compensi", "esborsi", "spese_generali", "iva", "cpa"),
    ),
    PresidioRule(
        code="spese_distrazione",
        sector="economico",
        label="Distrazione spese in favore del difensore",
        legal_basis=("art. 93 c.p.c.",),
        patterns=(
            r"\bdistrae\b",
            r"\bdistrazione\b",
            r"\bantistatari[oa]\b",
            r"\bprocuratore\s+antistatari[oa]\b",
            r"\bdifensore\s+antistatari[oa]\b",
            r"\bin\s+favore\s+dell\s+avv\b",
            r"\bin\s+favore\s+del\s+difensore\b",
        ),
        classification="credito_avvocato",
        parser_fields=("beneficiario_credito",),
    ),
    PresidioRule(
        code="spese_compensazione",
        sector="economico",
        label="Compensazione delle spese",
        legal_basis=("art. 92 c.p.c.",),
        patterns=(
            r"\bcompensa\s+le\s+spese\b",
            r"\bspese\s+compensate\b",
            r"\bcompensa\s+integralmente\b",
            r"\bcompensa\s+parzialmente\b",
            r"\bcompensa\s+per\s+meta\b",
            r"\bsoccombenza\s+reciproca\b",
        ),
        classification="spese_compensate",
        parser_fields=("quota_compensazione",),
    ),
    PresidioRule(
        code="gratuito_patrocinio",
        sector="economico",
        label="Patrocinio a spese dello Stato",
        legal_basis=("D.P.R. 115/2002 artt. 82-85", "D.P.R. 115/2002 art. 170"),
        patterns=(
            r"\bpatrocinio\s+a\s+spese\s+dello\s+stato\b",
            r"\bgratuito\s+patrocinio\b",
            r"\bammess[aoie]\s+al\s+patrocinio\b",
            r"\bistanza\s+di\s+liquidazione\b.{0,180}\bpatrocinio\b",
            r"\bdecreto\s+di\s+pagamento\b.{0,180}\bpatrocinio\b",
            r"\bopposizione\s+al\s+decreto\s+di\s+pagamento\b.{0,180}\bpatrocinio\b",
            r"\bdivieto\s+di\s+percepire\s+compensi\b",
        ),
        classification="patrocinio_spese_stato",
        parser_fields=("ammesso", "decreto_pagamento", "opposizione", "divieto_compensi_assistito"),
    ),
    PresidioRule(
        code="siamm_lsg_liquidazione",
        sector="economico",
        label="Liquidazione spese di giustizia / SIAMM",
        legal_basis=("D.P.R. 115/2002 artt. 82-84 e 170", "Portale LSG/SIAMM Ministero Giustizia"),
        patterns=(
            r"\bsiamm\b",
            r"\blsg\b",
            r"\bliquidazione\s+spese\s+di\s+giustizia\b",
            r"\bsistema\s+liquidazioni\s+spese\s+di\s+giustizia\b",
            r"\bistanza\s+web\b.{0,160}\bliquidazione\b",
            r"\bistanza\s+di\s+liquidazione\b",
            r"\bdecreto\s+di\s+pagamento\b",
            r"\bopposizione\s+al\s+decreto\s+di\s+pagamento\b",
            r"\bart\s*170\b.{0,100}\bd\s*p\s*r\s*115\b",
            r"\bdifensore\s+d\s+ufficio\b",
            r"\bimputat[oi]\s+assolt[oi]\b",
            r"\bistanze\s+pinto\b",
        ),
        classification="liquidazione_spese_giustizia",
        parser_fields=("istanza", "decreto_pagamento", "opposizione", "ufficio_spese", "qualifica_beneficiario"),
    ),
    PresidioRule(
        code="contributo_unificato_pagamento",
        sector="economico",
        label="Contributo unificato pagato",
        legal_basis=("D.P.R. 115/2002 artt. 9, 14, 15, 16", "D.P.R. 115/2002 art. 248"),
        patterns=(
            r"\bcontributo\s+unificat[oi]\b",
            r"\bc\s*u\b",
            r"\bcu\b",
            r"\biuv\b",
            r"\bpagopa\b",
            r"\bpago\s+pa\b",
            r"\bricevuta\s+telematica\b",
            r"\brt\s+xml\b",
            r"\bidentificativo\s+univoco\s+versamento\b",
            r"\bimporto\s+totale\s+pagato\b",
            r"\bsingolo\s+importo\s+pagato\b",
            r"\bdati\s+specifici\s+riscossione\b",
            r"\b0702100ts\b",
            r"\bcontrib\b",
        ),
        negative_patterns=(
            r"\bcarta\s+docente\b",
            r"\baggiornamento\s+e\s+formazione\s+del\s+docente\b",
            r"\bimporto\s+nominale\b",
        ),
        classification="contributo_unificato",
        parser_fields=("amount", "iuv", "payment_date", "esito", "causale", "rt_xml"),
    ),
    PresidioRule(
        code="contributo_unificato_esenzione",
        sector="economico",
        label="Contributo unificato esente o prenotato a debito",
        legal_basis=("D.P.R. 115/2002 art. 9", "D.P.R. 115/2002 art. 76"),
        patterns=(
            r"\bcontributo\s+unificat[oi]\s*(?:[:\-]\s*)?esent[eo]\b",
            r"\besente\s+dal\s+pagamento\s+(?:del\s+)?contributo\s+unificato\b",
            r"\besenzione\s+(?:dal\s+)?contributo\s+unificato\b",
            r"\bcontributo\s+unificato\s+non\s+dovut[oaie]\b",
            r"\bprenotazione\s+a\s+debito\b",
            r"\bautocertificazion[ei]\b.{0,240}\breddito\b",
            r"\bdichiarazione\s+sostitutiva\b.{0,240}\bart\s*9\b",
            r"\bart\s*9\b.{0,80}\bcomma\s*1\s*bis\b",
            r"\bart\s*76\b.{0,120}\bd\s*p\s*r\s*115\b",
        ),
        negative_patterns=(r"\bnon\s+esente\b", r"\besenzione\s+non\s+(?:riconosciuta|ammessa)\b"),
        classification="contributo_unificato_esente",
        parser_fields=("reddito", "soglia", "base_normativa"),
    ),
    PresidioRule(
        code="contributo_unificato_invito",
        sector="economico",
        label="Invito o richiesta pagamento contributo unificato",
        legal_basis=("D.P.R. 115/2002 artt. 16 e 248",),
        patterns=(
            r"\bomesso\s+(?:o\s+insufficiente\s+)?pagamento\s+del\s+contributo\s+unificato\b",
            r"\binsufficiente\s+pagamento\s+del\s+contributo\s+unificato\b",
            r"\binvito\s+al\s+pagamento\b",
            r"\brichiesta\s+di\s+versamento\b",
            r"\bintegrazione\s+del\s+contributo\b",
            r"\bdepositare\s+la\s+ricevuta\s+di\s+versamento\b",
            r"\biscrizione\s+a\s+ruolo\b.{0,120}\binteressi\b",
        ),
        classification="contributo_unificato_da_regolarizzare",
        parser_fields=("amount_due", "deadline", "receipt_required"),
    ),
    PresidioRule(
        code="udienza_127_bis",
        sector="udienze_scadenze",
        label="Udienza mediante collegamenti audiovisivi",
        legal_basis=("art. 127-bis c.p.c.",),
        patterns=(
            r"\b127\s+bis\b",
            r"\bcollegament[oi]\s+audiovisiv[oi]\b",
            r"\budienza\s+da\s+remoto\b",
            r"\bstanza\s+virtuale\b",
            r"\blink\s+(?:teams|meet|webex|udienza)\b",
            r"\budienza\s+in\s+presenza\b.{0,120}\b5\s+giorni\b",
        ),
        classification="udienza_remota",
        parser_fields=("hearing_date", "hearing_time", "remote_link", "presence_request_deadline"),
    ),
    PresidioRule(
        code="udienza_127_ter",
        sector="udienze_scadenze",
        label="Note scritte in sostituzione udienza",
        legal_basis=("art. 127-ter c.p.c.",),
        patterns=(
            r"\b127\s+ter\b",
            r"\bdeposito\s+di\s+note\s+scritte\b",
            r"\bnote\s+scritte\s+in\s+sostituzione\s+dell\s+udienza\b",
            r"\bsole\s+istanze\s+e\s+conclusioni\b",
            r"\btermine\s+perentorio\b",
            r"\bnon\s+inferiore\s+a\s+quindici\s+giorni\b",
            r"\bopposizione\b.{0,120}\b5\s+giorni\b",
        ),
        classification="termine_note_scritte",
        parser_fields=("notes_deadline", "communication_date", "opposition_deadline"),
    ),
    PresidioRule(
        code="decreto_fissazione_udienza",
        sector="udienze_scadenze",
        label="Decreto di fissazione udienza",
        legal_basis=("c.p.c. / rito applicabile",),
        patterns=(
            r"\bdecreto\s+di\s+fissazione\s+dell\s+udienza\b",
            r"\bfissa\s+l\s+udienza\b",
            r"\budienza\s+di\s+comparizione\b",
            r"\budienza\s+di\s+discussione\b",
            r"\bcomparizione\s+delle\s+parti\b",
            r"\bcostituzione\s+del\s+convenuto\b",
            r"\bnotifica\s+del\s+ricorso\s+e\s+del\s+decreto\b",
        ),
        classification="decreto_udienza",
        parser_fields=("hearing_date", "hearing_time", "service_deadline", "constitution_deadline"),
    ),
    PresidioRule(
        code="memorie_171_ter",
        sector="udienze_scadenze",
        label="Memorie integrative ex art. 171-ter c.p.c.",
        legal_basis=("art. 171-bis c.p.c.", "art. 171-ter c.p.c."),
        patterns=(
            r"\b171\s+bis\b",
            r"\b171\s+ter\b",
            r"\bverifiche\s+preliminari\b",
            r"\bmemorie\s+integrative\b",
            r"\bquaranta\s+giorni\s+prima\s+dell\s+udienza\b",
            r"\bventi\s+giorni\s+prima\s+dell\s+udienza\b",
            r"\bdieci\s+giorni\s+prima\s+dell\s+udienza\b",
        ),
        classification="memorie_pre_udienza",
        parser_fields=("deadline_40", "deadline_20", "deadline_10"),
    ),
    PresidioRule(
        code="rito_lavoro_415_420",
        sector="udienze_scadenze",
        label="Rito lavoro: ricorso, decreto e udienza discussione",
        legal_basis=("artt. 415, 416, 420, 429 c.p.c.",),
        patterns=(
            r"\bart\s*415\b",
            r"\bart\s*416\b",
            r"\bart\s*420\b",
            r"\bart\s*429\b",
            r"\brito\s+del\s+lavoro\b",
            r"\budienza\s+di\s+discussione\b",
            r"\bentro\s+dieci\s+giorni\b.{0,120}\bdecreto\b",
            r"\bmemoria\s+difensiva\b",
            r"\blettura\s+del\s+dispositivo\b",
        ),
        classification="rito_lavoro",
        parser_fields=("service_deadline", "hearing_date", "defence_deadline", "sentence_device"),
    ),
    PresidioRule(
        code="amministrativo_termini",
        sector="udienze_scadenze",
        label="Processo amministrativo: notifiche, deposito e termini udienza",
        legal_basis=("artt. 45, 55, 73, 87 c.p.a.",),
        patterns=(
            r"\bcodice\s+del\s+processo\s+amministrativo\b",
            r"\bart\s*45\b.{0,120}\btrenta\s+giorni\b",
            r"\bart\s*55\b",
            r"\bdomanda\s+cautelare\b",
            r"\bcamera\s+di\s+consiglio\b",
            r"\bart\s*73\b",
            r"\bquaranta\s+giorni\s+liberi\b",
            r"\btrenta\s+giorni\s+liberi\b",
            r"\bventi\s+giorni\s+liberi\b",
            r"\bart\s*87\b",
            r"\btermini\s+processuali\s+sono\s+dimezzati\b",
        ),
        classification="processo_amministrativo",
        parser_fields=("deposit_deadline", "documents_deadline", "memories_deadline", "reply_deadline"),
    ),
    PresidioRule(
        code="penale_atti_udienza",
        sector="udienze_scadenze",
        label="Processo penale: avvisi, citazioni e termini difensivi",
        legal_basis=("artt. 415-bis, 419, 429, 552 c.p.p.",),
        patterns=(
            r"\b415\s+bis\b",
            r"\bconclusione\s+delle\s+indagini\s+preliminari\b",
            r"\bventi\s+giorni\b.{0,160}\bpresentare\s+memorie\b",
            r"\bart\s*419\b",
            r"\budienza\s+preliminare\b",
            r"\brichiesta\s+di\s+rinvio\s+a\s+giudizio\b",
            r"\bart\s*429\b",
            r"\bdecreto\s+che\s+dispone\s+il\s+giudizio\b",
            r"\bart\s*552\b",
            r"\bdecreto\s+di\s+citazione\s+diretta\s+a\s+giudizio\b",
            r"\bsessanta\s+giorni\s+prima\b",
            r"\bquarantacinque\s+giorni\b",
        ),
        classification="processo_penale",
        parser_fields=("defence_deadline", "hearing_date", "service_deadline"),
    ),
    PresidioRule(
        code="decreto_ingiuntivo_opposizione",
        sector="procedimenti_speciali",
        label="Decreto ingiuntivo e opposizione",
        legal_basis=("artt. 633, 645, 648 c.p.c.",),
        patterns=(
            r"\bdecreto\s+ingiuntivo\b",
            r"\bingiunzione\s+di\s+pagamento\b",
            r"\bricorso\s+per\s+decreto\s+ingiuntivo\b",
            r"\bopposizione\s+a\s+decreto\s+ingiuntivo\b",
            r"\batto\s+di\s+citazione\s+in\s+opposizione\b",
            r"\bprovvisoria\s+esecuzione\b",
            r"\besecuzione\s+provvisoria\b",
            r"\bsospensione\s+dell\s+esecuzione\b",
            r"\bsomme\s+non\s+contestate\b",
        ),
        classification="decreto_ingiuntivo",
        parser_fields=("amount_claimed", "service_date", "opposition_deadline", "provisional_enforcement"),
    ),
    PresidioRule(
        code="sfratto_convalida",
        sector="procedimenti_speciali",
        label="Sfratto, locazione e convalida",
        legal_basis=("artt. 657, 658, 660, 664 c.p.c.",),
        patterns=(
            r"\bintimazione\s+di\s+sfratto\b",
            r"\blicenza\s+per\s+finita\s+locazione\b",
            r"\bsfratto\s+per\s+morosita\b",
            r"\bcitazione\s+per\s+la\s+convalida\b",
            r"\bconvalida\s+di\s+sfratto\b",
            r"\bingiunzione\s+di\s+pagamento\s+per\s+i\s+canoni\b",
            r"\bcanoni\s+scaduti\b",
            r"\bordinanza\s+di\s+rilascio\b",
            r"\bmutamento\s+del\s+rito\b",
            r"\btermine\s+di\s+grazia\b",
        ),
        classification="sfratto_convalida",
        parser_fields=("hearing_date", "service_date", "rent_due", "release_order", "opposition"),
    ),
    PresidioRule(
        code="esecuzione_pignoramento",
        sector="esecuzione",
        label="Esecuzione, pignoramento e vendita",
        legal_basis=("artt. 492-bis, 543, 547, 569 c.p.c.",),
        patterns=(
            r"\btitolo\s+esecutivo\b",
            r"\batto\s+di\s+precetto\b",
            r"\bpignoramento\b",
            r"\bpignoramento\s+presso\s+terzi\b",
            r"\bterzo\s+pignorato\b",
            r"\bdichiarazione\s+del\s+terzo\b",
            r"\bricerca\s+con\s+modalita\s+telematiche\s+dei\s+beni\b",
            r"\b492\s+bis\b",
            r"\bunep\b",
            r"\bunpig\b",
            r"\bunnot\b",
            r"\bcontrbeni\b",
            r"\bistanza\s+di\s+vendita\b",
            r"\bdocumentazione\s+ipocatastale\b",
            r"\bordine\s+di\s+vendita\b",
            r"\budienza\s+ex\s+art\s*569\b",
            r"\bprogetto\s+di\s+distribuzione\b",
        ),
        classification="esecuzione_pignoramento",
        parser_fields=("credit_amount", "service_date", "filing_deadline", "third_party", "sale_hearing"),
    ),
    PresidioRule(
        code="atp_previdenziale_ctu",
        sector="udienze_scadenze",
        label="ATP previdenziale e consulenza tecnica",
        legal_basis=("art. 445-bis c.p.c.", "artt. 193, 195 c.p.c."),
        patterns=(
            r"\b445\s+bis\b",
            r"\baccertamento\s+tecnico\s+preventivo\b",
            r"\bcondizione\s+di\s+procedibilita\b",
            r"\binvalidita\s+civile\b",
            r"\bhandicap\b",
            r"\bdisabilita\b",
            r"\binps\b",
            r"\bomologa\b",
            r"\bdissenso\b",
            r"\bconsulente\s+tecnico\s+d\s+ufficio\b",
            r"\bctu\b",
            r"\bgiuramento\s+del\s+consulente\b",
            r"\bbozza\s+peritale\b",
            r"\bosservazioni\s+alla\s+ctu\b",
            r"\brelazione\s+definitiva\b",
        ),
        classification="atp_ctu",
        parser_fields=("atp_deadline", "ctu_observations_deadline", "dissent_deadline", "homologation"),
    ),
    PresidioRule(
        code="mediazione_negoziazione",
        sector="adr_procedibilita",
        label="Mediazione o negoziazione assistita",
        legal_basis=("D.Lgs. 28/2010", "D.L. 132/2014"),
        patterns=(
            r"\bmediazione\b",
            r"\bdomanda\s+di\s+mediazione\b",
            r"\borganismo\s+di\s+mediazione\b",
            r"\bprimo\s+incontro\b",
            r"\bmediazione\s+demandata\b",
            r"\bverbale\s+(?:negativo|positivo)\b",
            r"\baccordo\s+di\s+conciliazione\b",
            r"\bcondizione\s+di\s+procedibilita\b",
            r"\bimprocedibilita\b",
            r"\bnegoziazione\s+assistita\b",
            r"\binvito\s+alla\s+stipula\b",
            r"\bconvenzione\s+di\s+negoziazione\b",
            r"\bmancata\s+adesione\b",
            r"\brifiuto\s+entro\s+trenta\s+giorni\b",
        ),
        classification="adr_procedibilita",
        parser_fields=("invitation_date", "response_deadline", "first_meeting", "outcome"),
    ),
    PresidioRule(
        code="notifica_digitale_pa",
        sector="pec_notifiche",
        label="Notifica digitale PA / piattaforma SEND",
        legal_basis=("art. 26 D.L. 76/2020", "D.M. 58/2022"),
        patterns=(
            r"\bpiattaforma\s+notificazione\s+digitale\b",
            r"\bnotifiche\s+digitali\b",
            r"\bsend\b",
            r"\bpnd\b",
            r"\bavviso\s+di\s+avvenuta\s+ricezione\b",
            r"\bavviso\s+di\s+cortesia\b",
            r"\bdeposito\s+in\s+piattaforma\b",
            r"\bperfezionamento\b",
            r"\bdecimo\s+giorno\b",
            r"\brimessione\s+in\s+termini\b",
            r"\bspese\s+di\s+notifica\b",
        ),
        classification="notifica_digitale_pa",
        parser_fields=("platform_deposit_date", "perfection_date", "notice_costs", "payment_due"),
    ),
    PresidioRule(
        code="crisi_impresa_concorsuale",
        sector="concorsuale",
        label="Crisi d'impresa e procedure concorsuali",
        legal_basis=("D.Lgs. 14/2019",),
        patterns=(
            r"\bcodice\s+della\s+crisi\b",
            r"\bliquidazione\s+giudiziale\b",
            r"\bliquidazione\s+controllata\b",
            r"\bconcordato\b",
            r"\bdomanda\s+di\s+accesso\b",
            r"\bstrumenti\s+di\s+regolazione\s+della\s+crisi\b",
            r"\bcuratore\b",
            r"\bcommissario\s+giudiziale\b",
            r"\bstato\s+passivo\b",
            r"\bdomanda\s+di\s+ammissione\s+al\s+passivo\b",
            r"\binsinuazione\s+al\s+passivo\b",
            r"\bopposizione\s+allo\s+stato\s+passivo\b",
            r"\bpec\s+curatore\b",
        ),
        classification="concorsuale",
        parser_fields=("procedure_date", "claim_amount", "privilege", "opposition_deadline"),
    ),
    PresidioRule(
        code="cassazione_civile",
        sector="impugnazioni",
        label="Cassazione civile",
        legal_basis=("artt. 369, 370, 380-bis, 380-ter c.p.c.", "PST/Corte di Cassazione"),
        patterns=(
            r"\bcorte\s+suprema\s+di\s+cassazione\b",
            r"\bcorte\s+di\s+cassazione\b",
            r"\bricorso\s+per\s+cassazione\b",
            r"\bcontroricorso\b",
            r"\bcontroricorso\s+con\s+ricorso\s+incidentale\b",
            r"\bdeposito\s+del\s+ricorso\b.{0,120}\bventi\s+giorni\b",
            r"\bart\s*369\b",
            r"\bart\s*370\b",
            r"\b380\s+bis\b",
            r"\b380\s+ter\b",
            r"\badunanza\s+camerale\b",
            r"\bpubblica\s+udienza\b.{0,120}\bcassazione\b",
            r"\bproposta\s+di\s+definizione\s+accelerata\b",
        ),
        classification="cassazione_civile",
        parser_fields=("service_date", "filing_deadline", "counter_appeal_deadline", "chamber_hearing", "public_hearing"),
    ),
    PresidioRule(
        code="giudice_pace_sigp",
        sector="udienze_scadenze",
        label="Giudice di Pace / SIGP",
        legal_basis=("artt. 316-320 c.p.c.", "D.Lgs. 150/2011 art. 6", "SIGP/PST"),
        patterns=(
            r"\bgiudice\s+di\s+pace\b",
            r"\bsigp\b",
            r"\bservizi\s+online\s+giudici\s+di\s+pace\b",
            r"\bopposizione\s+a\s+sanzione\s+amministrativa\b",
            r"\bverbale\s+di\s+accertamento\b",
            r"\bart\s*204\s+bis\b",
            r"\blegge\s+689\s+1981\b",
            r"\bd\s*lgs\s*150\s*2011\b",
            r"\bart\s*316\b",
            r"\bart\s*320\b",
            r"\btrattazione\s+della\s+causa\b.{0,160}\bgiudice\s+di\s+pace\b",
        ),
        classification="giudice_pace_sigp",
        parser_fields=("hearing_date", "opposition_deadline", "fine_amount", "office", "sigp_status"),
    ),
    PresidioRule(
        code="volontaria_giurisdizione",
        sector="volontaria_giurisdizione",
        label="Volontaria giurisdizione / Tribunale Online",
        legal_basis=("artt. 737-739 c.p.c.", "Tribunale Online/PST"),
        patterns=(
            r"\bvolontaria\s+giurisdizione\b",
            r"\btribunale\s+online\b",
            r"\bricorso\s+al\s+giudice\s+tutelare\b",
            r"\bgiudice\s+tutelare\b",
            r"\bamministrazione\s+di\s+sostegno\b",
            r"\bamministratore\s+di\s+sostegno\b",
            r"\bads\b",
            r"\bbeneficiari[oa]\b",
            r"\brendiconto\b",
            r"\beredita\s+giacente\b",
            r"\bnomina\s+del\s+curatore\b",
            r"\bdecreto\s+motivat[oa]\b.{0,120}\bcamera\s+di\s+consiglio\b",
            r"\breclamo\b.{0,120}\bart\s*739\b",
        ),
        classification="volontaria_giurisdizione",
        parser_fields=("petition_date", "decree_date", "hearing_date", "report_deadline", "appeal_deadline"),
    ),
    PresidioRule(
        code="famiglia_minori_ascolto",
        sector="famiglia_minori",
        label="Famiglia, minori e ascolto del minore",
        legal_basis=("artt. 473-bis e seguenti c.p.c.", "PST regole tecniche ascolto minore"),
        patterns=(
            r"\b473\s+bis\b",
            r"\bpersone\s+minorenni\s+e\s+famiglie\b",
            r"\bascolto\s+del\s+minore\b",
            r"\bregistrazione\s+audiovisiva\b.{0,160}\bminore\b",
            r"\bpiano\s+genitoriale\b",
            r"\bprovvedimenti\s+temporanei\s+e\s+urgenti\b",
            r"\bordini\s+di\s+protezione\b",
            r"\baffidamento\b",
            r"\bcollocamento\b",
            r"\bassegno\s+di\s+mantenimento\b",
            r"\bspese\s+straordinarie\b",
            r"\brelazione\s+servizi\s+sociali\b",
        ),
        classification="famiglia_minori",
        parser_fields=("hearing_date", "service_deadline", "maintenance_amount", "minor_hearing", "protective_order"),
    ),
    PresidioRule(
        code="appello_civile_lavoro",
        sector="impugnazioni",
        label="Appello civile o lavoro",
        legal_basis=("artt. 342-352 c.p.c.", "artt. 433-438 c.p.c."),
        patterns=(
            r"\batto\s+di\s+appello\b",
            r"\bricorso\s+in\s+appello\b",
            r"\bappello\s+incidentale\b",
            r"\binibitoria\b",
            r"\bsospensione\s+dell\s+efficacia\s+esecutiva\b",
            r"\bart\s*342\b",
            r"\bart\s*343\b",
            r"\bart\s*347\b",
            r"\bart\s*351\b",
            r"\bart\s*352\b",
            r"\bart\s*433\b",
            r"\bart\s*434\b",
            r"\bart\s*435\b",
            r"\bart\s*436\b",
            r"\budienza\s+di\s+discussione\b.{0,160}\bappello\b",
        ),
        classification="appello_civile_lavoro",
        parser_fields=("appeal_date", "appearance_deadline", "inhibition_hearing", "counter_appeal_deadline"),
    ),
    PresidioRule(
        code="impugnazione_amministrativa",
        sector="impugnazioni",
        label="Appello amministrativo / Consiglio di Stato",
        legal_basis=("artt. 92, 98, 101, 104, 119 c.p.a.", "PAT/SIGA"),
        patterns=(
            r"\bconsiglio\s+di\s+stato\b",
            r"\bappello\s+amministrativo\b",
            r"\bappello\s+cautelare\b",
            r"\bricorso\s+incidentale\b.{0,160}\bconsiglio\s+di\s+stato\b",
            r"\bmotivi\s+aggiunti\b.{0,160}\bappello\b",
            r"\bart\s*92\b.{0,120}\bcodice\s+del\s+processo\s+amministrativo\b",
            r"\bart\s*98\b",
            r"\bart\s*101\b",
            r"\bart\s*104\b",
            r"\bart\s*119\b.{0,120}\btermini\s+dimezzati\b",
        ),
        classification="impugnazione_amministrativa",
        parser_fields=("appeal_deadline", "cautionary_hearing", "incidental_appeal", "pat_receipt"),
    ),
    PresidioRule(
        code="impugnazione_tributaria",
        sector="impugnazioni",
        label="Appello tributario",
        legal_basis=("D.Lgs. 546/1992 artt. 51, 53, 54, 61, 62", "PTT/SIGIT"),
        patterns=(
            r"\bappello\s+tributario\b",
            r"\bcorte\s+di\s+giustizia\s+tributaria\s+di\s+secondo\s+grado\b",
            r"\bforma\s+dell\s+appello\b",
            r"\bcontrodeduzioni\s+dell\s+appellato\b",
            r"\bappello\s+incidentale\b.{0,160}\btributari[oa]\b",
            r"\bart\s*53\b.{0,120}\bd\s*lgs\s*546\b",
            r"\bart\s*54\b.{0,120}\bd\s*lgs\s*546\b",
            r"\bart\s*61\b.{0,120}\bd\s*lgs\s*546\b",
            r"\bptt\b.{0,120}\bappello\b",
            r"\bsigit\b.{0,120}\bappello\b",
        ),
        classification="impugnazione_tributaria",
        parser_fields=("appeal_deadline", "counter_deductions_deadline", "incidental_appeal", "ptt_receipt"),
    ),
    PresidioRule(
        code="pec_ricevute",
        sector="pec_notifiche",
        label="Ricevute PEC e messaggi certificati",
        legal_basis=("Linee guida PEC AgID", "DM 44/2011"),
        patterns=(
            r"\bpostacert\b",
            r"\bdaticert\s+xml\b",
            r"\bricevuta\s+di\s+accettazione\b",
            r"\bricevuta\s+di\s+avvenuta\s+consegna\b",
            r"\bavvenuta\s+consegna\b",
            r"\berrore\s+consegna\b",
            r"\bx\s+ricevuta\b",
            r"\bidentificativo\s+messaggio\b",
            r"\bmessage\s+id\b",
        ),
        classification="pec_ricevuta",
        parser_fields=("receipt_type", "message_id", "sender", "recipient", "timestamp"),
    ),
    PresidioRule(
        code="notifica_53_1994",
        sector="pec_notifiche",
        label="Notificazione in proprio a mezzo PEC",
        legal_basis=("L. 53/1994 art. 3-bis", "DM 44/2011 art. 18"),
        patterns=(
            r"\blegge\s+53\s+1994\b",
            r"\bl\s*53\s*94\b",
            r"\bart\s*3\s+bis\b",
            r"\brelata\s+di\s+notifica\b",
            r"\brelazione\s+di\s+notificazione\b",
            r"\bnotificazione\s+a\s+mezzo\s+pec\b",
            r"\bpubblici\s+elenchi\b",
            r"\breginde\b",
            r"\bini\s+pec\b",
            r"\bipa\b",
            r"\bprocura\s+alle\s+liti\b.{0,160}\bnotifica\b",
        ),
        classification="relata_notifica",
        parser_fields=("notifier", "recipient", "recipient_pec", "public_registry", "attachments"),
    ),
    PresidioRule(
        code="deposito_pct",
        sector="pct_deposito",
        label="Deposito telematico PCT",
        legal_basis=("DM 44/2011", "Specifiche tecniche PCT"),
        patterns=(
            r"\bdeposito\s+telematico\b",
            r"\batto\s+enc\b",
            r"\bdatiatto\s+xml\b",
            r"\bindicebusta\b",
            r"\besito\s+controlli\s+automatici\b",
            r"\baccettazione\s+deposito\b",
            r"\bricevuta\s+di\s+accettazione\b",
            r"\bricevuta\s+di\s+avvenuta\s+consegna\b",
            r"\brdac\b",
            r"\bwarn\b",
            r"\berror\b",
            r"\bfatal\b",
        ),
        classification="deposito_pct",
        parser_fields=("deposit_status", "receipt_chain", "errors", "warnings"),
    ),
)


RULES_BY_CODE = {rule.code: rule for rule in PRESIDIO_RULES}


def _matches(rule: PresidioRule, raw: str, normalised: str) -> bool:
    if rule.negative_patterns and any(re.search(pattern, normalised, re.IGNORECASE | re.DOTALL) for pattern in rule.negative_patterns):
        return False
    return any(
        re.search(pattern, normalised, re.IGNORECASE | re.DOTALL)
        or re.search(pattern, raw, re.IGNORECASE | re.DOTALL)
        for pattern in rule.patterns
    )


def presidio_rule_hits(
    text: Any,
    metadata: dict[str, Any] | None = None,
    *,
    sectors: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    raw = " ".join(part for part in (_text(text), metadata_probe(metadata)) if part)
    normalised = normalize_presidio_text(raw)
    allowed = {str(sector) for sector in sectors or []}
    hits: list[dict[str, Any]] = []
    for rule in PRESIDIO_RULES:
        if allowed and rule.sector not in allowed:
            continue
        if _matches(rule, raw, normalised):
            hits.append(
                {
                    "code": rule.code,
                    "sector": rule.sector,
                    "label": rule.label,
                    "classification": rule.classification,
                    "legalBasis": list(rule.legal_basis),
                    "parserFields": list(rule.parser_fields),
                }
            )
    if is_pagopa_rt_contributo_xml(raw):
        code = "contributo_unificato_pagamento"
        if not any(item["code"] == code for item in hits):
            rule = RULES_BY_CODE[code]
            hits.append(
                {
                    "code": rule.code,
                    "sector": rule.sector,
                    "label": rule.label,
                    "classification": rule.classification,
                    "legalBasis": list(rule.legal_basis),
                    "parserFields": list(rule.parser_fields),
                }
            )
    return hits


def has_presidio_rule(text: Any, code: str, metadata: dict[str, Any] | None = None) -> bool:
    return any(hit["code"] == code for hit in presidio_rule_hits(text, metadata))


def has_presidio_classification(text: Any, classification: str, metadata: dict[str, Any] | None = None) -> bool:
    return any(hit["classification"] == classification for hit in presidio_rule_hits(text, metadata))


def is_pagopa_rt_xml(text: Any) -> bool:
    return bool(PAGOPA_RT_XML_RE.search(_text(text)))


def is_pagopa_rt_contributo_xml(text: Any) -> bool:
    raw = _text(text)
    return bool(PAGOPA_RT_XML_RE.search(raw) and PAGOPA_RT_CU_RE.search(raw))


def extract_rg_references(text: Any) -> list[dict[str, str]]:
    raw = _text(text)
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for regex in (RG_RE, PLAIN_RG_RE):
        for match in regex.finditer(raw):
            number = str(int(match.group("number")))
            year = match.group("year")
            key = (number, year)
            if key in seen:
                continue
            seen.add(key)
            refs.append({"number": number, "year": year, "label": f"RG {number}/{year}"})
    return refs


def extract_dates_it(text: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for match in DATE_RE.finditer(_text(text)):
        try:
            day = int(match.group("day"))
            month = int(match.group("month"))
            year = int(match.group("year"))
        except ValueError:
            continue
        if not (1 <= day <= 31 and 1 <= month <= 12):
            continue
        label = f"{day:02d}/{month:02d}/{year:04d}"
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def parse_money_amount(value: Any) -> float | None:
    raw = _text(value).replace("\xa0", " ")
    raw = re.sub(r"\s+", "", raw)
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def extract_money_amounts(text: Any) -> list[float]:
    out: list[float] = []
    seen: set[float] = set()
    for match in MONEY_RE.finditer(_text(text)):
        amount = parse_money_amount(match.group("amount1") or match.group("amount2"))
        if amount is None or amount in seen:
            continue
        seen.add(amount)
        out.append(amount)
    return out


__all__ = [
    "PRESIDIO_RULES",
    "RULESET_VERSION",
    "PresidioRule",
    "extract_dates_it",
    "extract_money_amounts",
    "extract_rg_references",
    "has_presidio_classification",
    "has_presidio_rule",
    "is_pagopa_rt_contributo_xml",
    "is_pagopa_rt_xml",
    "normalize_presidio_text",
    "parse_money_amount",
    "presidio_rule_hits",
]
