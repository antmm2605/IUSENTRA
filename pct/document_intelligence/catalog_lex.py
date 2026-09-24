"""La seconda lettura di Lex sulla catalogazione dei documenti.

Le regole del catalogo leggono intestazioni e formule: sono esatte quando il
documento dichiara che cosa e', ma possono scambiare una citazione nel corpo
per l'identita' dell'atto. Lex rilegge l'inizio del documento con un modello
locale (Ollama, sul server dello studio: i documenti non escono) e sceglie una
voce del catalogo.

Tre vincoli rendono la lettura professionale e verificabile:

1. Lex sceglie solo fra le voci del catalogo: la risposta e' vincolata da uno
   schema JSON con l'elenco chiuso delle etichette, non puo' inventarne.
2. Lex cita la frase del documento che giustifica la scelta, e la frase deve
   esserci davvero nel testo: senza citazione verificata la lettura non conta.
3. Lex propone, non decide: il suo esito resta una proposta che l'avvocato
   conferma, non diventa mai una catalogazione automatica.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from .models import DocumentCatalogAssignment, DocumentCatalogCandidate, DocumentCatalogEvidence, new_id, utc_now
from .titoli import REGOLE_TITOLO

VERSIONE_LETTURA = "lex-catalogo-v1"
MODELLO_PREDEFINITO = "qwen3:4b"
CONFIDENZA_LEX = 80
CONFIDENZA_REGOLA_SICURA = 90
CARATTERI_LETTI = 4000
LUNGHEZZA_MINIMA_CITAZIONE = 12
NESSUNA_VOCE = "Nessuna voce del catalogo"
LOCATORE_LEX = "seconda lettura Lex"


@dataclass(frozen=True)
class VoceCatalogo:
    label: str
    section: str
    nature: str
    deposit_role: str
    deposit_candidate: bool


# Le identita' riconosciute dal resolver fuori dalle regole di titolo.
_VOCI_DEL_RESOLVER = (
    VoceCatalogo("Sentenza", "provvedimenti", "provvedimento", "allegato", True),
    VoceCatalogo("Sentenza di altro procedimento — precedente", "allegati", "precedente_giurisprudenziale", "allegato", True),
    VoceCatalogo("Decreto di fissazione udienza", "provvedimenti", "provvedimento", "fuori_busta", False),
    VoceCatalogo("Decreto di rinvio d'ufficio dell'udienza", "provvedimenti", "provvedimento", "fuori_busta", False),
    VoceCatalogo("Verbale di udienza", "provvedimenti", "provvedimento", "fuori_busta", False),
    VoceCatalogo("Procura alle liti", "procure", "procura", "procura", True),
    VoceCatalogo("Contratto di lavoro", "contratti", "contratto", "allegato", True),
    VoceCatalogo("Memoria conclusionale", "atti", "atto_difensivo", "atto_principale", True),
    VoceCatalogo("Note di trattazione scritta", "atti", "atto_difensivo", "atto_principale", True),
    VoceCatalogo("Istanza di trattazione scritta", "atti", "atto_difensivo", "atto_principale", True),
    VoceCatalogo("Nota di deposito", "atti", "deposito", "fuori_busta", False),
    VoceCatalogo("Comunicazione di cancelleria", "comunicazioni", "comunicazione", "fuori_busta", False),
    VoceCatalogo("Richiesta stragiudiziale di pagamento", "comunicazioni", "comunicazione", "allegato", True),
    VoceCatalogo("Messaggio PEC", "comunicazioni", "comunicazione", "fuori_busta", False),
    VoceCatalogo("Documento d'identità", "identita", "documento_identita", "allegato", True),
    VoceCatalogo("Attestazione di conformità", "allegati", "attestazione", "allegato", True),
)


def voci_catalogo() -> list[VoceCatalogo]:
    """Le voci fra cui Lex sceglie: regole di titolo e identita' del resolver."""
    voci: dict[str, VoceCatalogo] = {}
    for regola in REGOLE_TITOLO:
        voci.setdefault(regola.label, VoceCatalogo(regola.label, regola.section, regola.role, regola.deposit_role, regola.deposit_candidate))
    for voce in _VOCI_DEL_RESOLVER:
        voci.setdefault(voce.label, voce)
    return sorted(voci.values(), key=lambda voce: (voce.section, voce.label))


def _normalizza(testo: str) -> str:
    grezzo = unicodedata.normalize("NFKD", str(testo or "").casefold())
    grezzo = "".join(car for car in grezzo if unicodedata.category(car) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", grezzo).strip()


def citazione_nel_testo(citazione: str, testo: str) -> bool:
    """La frase citata c'e' davvero nel documento (a meno di spazi e punteggiatura).

    L'OCR puo' inserire fra le parole di una frase righe estranee (la dicitura
    della firma digitale a margine, un numero di pagina): la citazione vale
    anche quando le sue parole compaiono tutte, nello stesso ordine, in un
    tratto di testo non piu' lungo del triplo della citazione.
    """
    cercata = _normalizza(citazione)
    if len(cercata) < LUNGHEZZA_MINIMA_CITAZIONE:
        return False
    normalizzato = _normalizza(testo)
    if cercata in normalizzato:
        return True
    parole = cercata.split()
    testo_parole = normalizzato.split()
    massimo = len(parole) * 3
    for inizio, parola in enumerate(testo_parole):
        if parola != parole[0]:
            continue
        indice = 1
        for posizione in range(inizio + 1, min(len(testo_parole), inizio + massimo)):
            if indice == len(parole):
                break
            if testo_parole[posizione] == parole[indice]:
                indice += 1
        if indice == len(parole):
            return True
    return False


def schema_risposta(voci: list[VoceCatalogo]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "etichetta": {"type": "string", "enum": [voce.label for voce in voci] + [NESSUNA_VOCE]},
            "citazione": {"type": "string"},
            "motivo": {"type": "string"},
        },
        "required": ["etichetta", "citazione", "motivo"],
    }


def domanda(testo: str, voci: list[VoceCatalogo], *, contesto: str = "", proposta: str = "") -> str:
    """La domanda a Lex. La parte fissa (istruzioni e voci) viene prima del
    documento: Ollama la tiene in memoria fra un documento e l'altro e rilegge
    solo il testo nuovo."""
    elenco = "\n".join(f"- {voce.label} [{voce.section}]" for voce in voci)
    riga_fascicolo = f"Fascicolo: {contesto.strip()}\n" if contesto.strip() else ""
    riga_proposta = (
        f"Le regole automatiche propongono: «{proposta.strip()}». Confermala solo se e' corretta.\n" if proposta.strip() else ""
    )
    return (
        "Sei un avvocato italiano che cataloga i documenti di un fascicolo.\n"
        "Scegli la voce del catalogo che dice CHE COSA E' il documento: chi lo ha scritto e a che cosa serve.\n"
        "Regole:\n"
        "1. Guarda prima l'intestazione e il titolo in cima al documento: il documento e' cio' che dichiara di essere li'.\n"
        "2. Gli atti citati nel corpo non cambiano la natura del documento: note che citano il ricorso o il "
        "decreto di fissazione udienza restano note; un decreto del giudice che chiede note «contenenti "
        "istanze e conclusioni» resta un decreto.\n"
        "3. Un atto di parte depositato per un'udienza sostituita (trattazione scritta, art. 127-ter c.p.c.) "
        "e' una nota scritta, non un ricorso.\n"
        "4. Una sentenza di un ufficio giudiziario diverso da quello del fascicolo e' un precedente prodotto.\n"
        f"Voci del catalogo (etichetta [sezione]):\n{elenco}\n"
        f"Se nessuna voce descrive il documento rispondi «{NESSUNA_VOCE}».\n"
        "In «citazione» copia ESATTAMENTE, parola per parola, la frase del documento (almeno quattro parole) "
        "che dimostra la scelta, preferibilmente dall'intestazione; in «motivo» spiega in una frase breve.\n"
        "Rispondi solo con il JSON richiesto.\n\n"
        f"{riga_fascicolo}{riga_proposta}"
        f"DOCUMENTO:\n{str(testo or '')[:CARATTERI_LETTI]}"
    )


@dataclass(frozen=True)
class EsitoLex:
    stato: str  # scelta | nessuna | non_verificata | errore
    etichetta: str = ""
    citazione: str = ""
    motivo: str = ""
    voce: VoceCatalogo | None = None

    def come_dict(self) -> dict[str, str]:
        return {"esito": self.stato, "etichetta": self.etichetta, "citazione": self.citazione[:300], "motivo": self.motivo[:300]}


def leggi_con_lex(
    testo: str,
    *,
    genera: Callable[[str, dict[str, Any]], str],
    voci: list[VoceCatalogo] | None = None,
    contesto: str = "",
    proposta: str = "",
) -> EsitoLex:
    """Chiede a Lex la voce del documento e verifica la risposta."""
    voci = voci or voci_catalogo()
    try:
        grezza = genera(domanda(testo, voci, contesto=contesto, proposta=proposta), schema_risposta(voci))
        risposta = json.loads(grezza or "{}")
    except Exception as exc:  # modello non raggiungibile, risposta non JSON
        return EsitoLex("errore", motivo=str(exc)[:200])
    etichetta = str(risposta.get("etichetta") or "").strip()
    citazione = str(risposta.get("citazione") or "").strip()
    motivo = str(risposta.get("motivo") or "").strip()
    per_etichetta = {voce.label: voce for voce in voci}
    if etichetta == NESSUNA_VOCE:
        return EsitoLex("nessuna", etichetta, citazione, motivo)
    voce = per_etichetta.get(etichetta)
    if voce is None:
        return EsitoLex("errore", etichetta, citazione, "etichetta fuori catalogo")
    if not citazione_nel_testo(citazione, testo):
        return EsitoLex("non_verificata", etichetta, citazione, motivo, voce)
    return EsitoLex("scelta", etichetta, citazione, motivo, voce)


def da_rileggere(assignment: DocumentCatalogAssignment, *, modello: str) -> bool:
    """Lex rilegge le proposte incerte, una volta per documento e modello.

    Solo dove le regole non hanno una risposta sicura (da verificare o sotto
    CONFIDENZA_REGOLA_SICURA): sulle distinzioni fini un modello da 4 miliardi
    di parametri sbaglia piu' delle regole di titolo (prova del 24/09/2026 sul
    fascicolo Affinito), quindi non le rimette in discussione. Le
    catalogazioni confermate o corrette a mano non si toccano.
    """
    if assignment.status not in {"proposed", "review_required"} or assignment.source_state == "manual_override":
        return False
    if assignment.status == "proposed" and int(assignment.confidence or 0) >= CONFIDENZA_REGOLA_SICURA:
        return False
    letta = (assignment.metadata or {}).get("lex_lettura") or {}
    return not (
        letta.get("versione") == VERSIONE_LETTURA
        and letta.get("modello") == modello
        and letta.get("sha256") == assignment.document_sha256
    )


def applica_esito(
    assignment: DocumentCatalogAssignment,
    candidati: list[DocumentCatalogCandidate],
    evidenze: list[DocumentCatalogEvidence],
    esito: EsitoLex,
    *,
    modello: str,
    durata_s: float = 0.0,
) -> tuple[DocumentCatalogAssignment, list[DocumentCatalogCandidate], list[DocumentCatalogEvidence]]:
    """La catalogazione dopo la lettura di Lex: mai automatica, sempre motivata."""
    adesso = utc_now()
    metadata = dict(assignment.metadata or {})
    metadata["lex_lettura"] = {
        **esito.come_dict(),
        "versione": VERSIONE_LETTURA,
        "modello": modello,
        "sha256": assignment.document_sha256,
        "letto_il": adesso,
        "durata_s": round(float(durata_s), 1),
    }
    # Il tipo resta fra quelli ammessi dallo schema (vincolo CHECK): la lettura
    # di Lex si riconosce dalla sua collocazione.
    evidenze = [evidenza for evidenza in evidenze if not str(evidenza.locator or "").startswith(LOCATORE_LEX)]
    if esito.stato != "scelta" or esito.voce is None:
        return replace(assignment, metadata=metadata), candidati, evidenze

    voce = esito.voce
    evidenza = DocumentCatalogEvidence(
        id=new_id("catalog-evidence"), tenant_id=assignment.tenant_id, fascicolo_id=assignment.fascicolo_id,
        assignment_id=assignment.id, evidence_type="document_identity", locator=f"{LOCATORE_LEX} ({modello})",
        excerpt=f"«{esito.citazione[:180]}» — {esito.motivo[:120]}"[:320], weight=70,
        content_sha256=assignment.document_sha256 or None, created_at=adesso,
    )
    evidenze = [*evidenze, evidenza]
    if voce.label == assignment.document_label:
        # Lex conferma la regola: una proposta dubbia diventa una proposta motivata.
        if assignment.status == "review_required":
            assignment = replace(assignment, status="proposed", confidence=max(int(assignment.confidence or 0), CONFIDENZA_LEX))
        return replace(assignment, metadata=metadata), candidati, evidenze

    candidato_lex = DocumentCatalogCandidate(
        id=new_id("catalog-candidate"), tenant_id=assignment.tenant_id, fascicolo_id=assignment.fascicolo_id,
        assignment_id=assignment.id, rank_number=1, profile_id=assignment.profile_id, document_nature=voce.nature,
        document_label=voce.label, document_section=voce.section, deposit_role=voce.deposit_role,
        confidence=CONFIDENZA_LEX, reason=f"seconda lettura Lex: {esito.motivo[:200]}", created_at=adesso,
    )
    metadata["automatic_classification"] = False
    regola_debole = assignment.status == "review_required" or int(assignment.confidence or 0) < 90
    if regola_debole:
        # La regola era incerta: la proposta diventa quella di Lex, motivata dalla citazione.
        precedenti = [replace(candidato, rank_number=indice + 2) for indice, candidato in enumerate(candidati)]
        assignment = replace(
            assignment,
            document_label=voce.label, document_section=voce.section, document_nature=voce.nature,
            deposit_role=voce.deposit_role, deposit_candidate=voce.deposit_candidate,
            status="proposed", confidence=CONFIDENZA_LEX, metadata=metadata,
            reason=f"Seconda lettura Lex: {esito.motivo[:200]} (la regola proponeva «{assignment.document_label}»).",
        )
        return assignment, [candidato_lex, *precedenti], evidenze

    # La regola era sicura ma Lex legge un'altra cosa: resta la regola, non piu'
    # automatica; se cambia perfino la sezione l'avvocato deve guardarla.
    altra_sezione = voce.section != assignment.document_section
    candidato_lex = replace(candidato_lex, rank_number=len(candidati) + 1)
    assignment = replace(
        assignment,
        status="review_required" if altra_sezione else "proposed",
        metadata=metadata,
        reason=f"{assignment.reason} Lex legge invece «{voce.label}»: {esito.motivo[:160]}".strip()[:600],
    )
    return assignment, [*candidati, candidato_lex], evidenze


__all__ = [
    "CONFIDENZA_LEX",
    "CONFIDENZA_REGOLA_SICURA",
    "LOCATORE_LEX",
    "MODELLO_PREDEFINITO",
    "NESSUNA_VOCE",
    "VERSIONE_LETTURA",
    "EsitoLex",
    "VoceCatalogo",
    "applica_esito",
    "citazione_nel_testo",
    "da_rileggere",
    "domanda",
    "leggi_con_lex",
    "schema_risposta",
    "voci_catalogo",
]
