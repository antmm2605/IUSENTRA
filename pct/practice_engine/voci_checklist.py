"""Ogni voce del presidio ha i suoi controlli: così si completa davvero.

Una voce della checklist («Codice oggetto PST ufficiale», «Firma digitale e
busta ministeriale», «Verifica dati cliente e parti») non è una spunta da
mettere a mano: corrisponde a controlli che il software esegue già. Finché la
voce non è collegata ai propri controlli non diventa mai «completata» e il
completamento del fascicolo resta basso anche quando tutto è a posto.

Qui il collegamento è dichiarato: per chiave della voce e, quando la voce
viene dal catalogo delle procedure con un'etichetta libera, per le parole
dell'etichetta. Una voce che riguarda la busta telematica è pertinente solo
quando c'è un deposito da preparare (vedi `fase_deposito.py`): fuori da quella
fase si dichiara rinviata, non «da completare».
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from .models import ValidatorStatus

# Controlli che riguardano la busta telematica: pertinenti solo in fase di deposito.
CONTROLLI_DI_DEPOSITO = frozenset({
    "codice_oggetto_pst_valido", "atto_principale_presente", "procura_presente", "file_presente", "file_apribile",
    "hash_calcolato", "pdfa_valido", "pdf_non_cifrato", "dimensione_file_ok", "firma_digitale_presente",
    "dati_atto_xml_generabile", "busta_generabile", "busta_sotto_limite", "dimensione_busta_ok",
    "pec_destinatario_ufficio_valida", "oggetto_pec_conforme", "schema_xsd_presente", "documento_non_vuoto",
    "documento_non_corrotto", "documento_non_cifrato", "documento_versione_corrente", "tipo_documento_classificato",
})

# (chiave o parole dell'etichetta) → controlli che la voce riassume.
CONTROLLI_PER_VOCE: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("codice_oggetto", "oggetto_pst", "codice oggetto"), ("codice_oggetto_pst_valido",)),
    (("classificazione", "classificazione_atti"), ("atto_principale_presente", "tipo_documento_classificato")),
    (("firma_e_busta", "firma digitale", "busta"), ("firma_digitale_presente", "busta_generabile", "busta_sotto_limite", "dati_atto_xml_generabile")),
    (("xsd", "schema"), ("schema_xsd_presente",)),
    (("atto_principale", "atto principale"), ("atto_principale_presente", "pdfa_valido", "firma_digitale_presente")),
    (("procura", "mandato"), ("procura_presente",)),
    (("verifica_dati", "dati cliente", "cliente e parti", "anagrafic"), ("cliente_presente", "cliente_cf_valido", "ufficio_giudiziario_presente", "registro_presente")),
    (("contributo", "contributo_unificato"), ("contributo_unificato_definito",)),
    (("preventivo",), ("preventivo_accettato",)),
    (("conferimento", "incarico", "mandato professionale"), ("conferimento_firmato",)),
    (("acconto", "pagamento"), ("pagamento_acconto_registrato",)),
    (("pec", "destinatario"), ("pec_destinatario_ufficio_valida", "oggetto_pec_conforme")),
)


def _piatto(valore: Any) -> str:
    testo = unicodedata.normalize("NFD", str(valore or "").casefold())
    testo = "".join(carattere for carattere in testo if unicodedata.category(carattere) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", testo).strip()


def controlli_della_voce(voce: Any) -> tuple[str, ...]:
    """I controlli che la voce riassume, dalla chiave o dalle parole dell'etichetta."""
    chiave = _piatto(getattr(voce, "key", ""))
    etichetta = _piatto(getattr(voce, "label", ""))
    for parole, controlli in CONTROLLI_PER_VOCE:
        for parola in parole:
            piatta = _piatto(parola)
            if piatta and (piatta in chiave or piatta in etichetta):
                return controlli
    return ()


def e_voce_di_deposito(voce: Any) -> bool:
    controlli = controlli_della_voce(voce)
    return bool(controlli) and all(controllo in CONTROLLI_DI_DEPOSITO for controllo in controlli)


def stato_voce(voce: Any, risultati: Iterable[Any], *, in_deposito: bool = True, motivo_rinvio: str = "") -> dict[str, Any]:
    """Lo stato della voce: completata, bloccata, da completare o rinviata, con il perché."""
    controlli = controlli_della_voce(voce)
    per_chiave: dict[str, list[Any]] = {}
    for risultato in risultati:
        per_chiave.setdefault(str(getattr(risultato, "key", "")), []).append(risultato)
    pertinenti = [voce_risultato for controllo in controlli for voce_risultato in per_chiave.get(controllo, [])]
    if not in_deposito and e_voce_di_deposito(voce):
        return {
            "stato": "NON_PERTINENTE", "misurabile": False,
            "messaggio": motivo_rinvio or "Controllo della busta: si esegue quando prepari il deposito.",
            "azione": "Prepara il deposito per eseguire questo controllo.",
        }
    bloccanti = [risultato for risultato in pertinenti if getattr(risultato, "blocking", False)]
    if bloccanti:
        return {
            "stato": "BLOCCATO", "misurabile": True,
            "messaggio": str(getattr(bloccanti[0], "message", "")),
            "azione": str(getattr(bloccanti[0], "suggested_action", "")),
        }
    if not pertinenti:
        # Nessun controllo automatico: resta una verifica dell'avvocato e non entra nel conteggio.
        return {
            "stato": "DA_COMPLETARE", "misurabile": False,
            "messaggio": str(getattr(voce, "message", "")) or "Verifica affidata all'avvocato: il software non ha un controllo automatico per questa voce.",
            "azione": str(getattr(voce, "suggested_action", "")) or "Completa il requisito quando applicabile.",
        }
    in_sospeso = [risultato for risultato in pertinenti if str(getattr(risultato, "status", "")) == ValidatorStatus.PENDING.value]
    if in_sospeso:
        return {
            "stato": "DA_COMPLETARE", "misurabile": True,
            "messaggio": str(getattr(in_sospeso[0], "message", "")),
            "azione": str(getattr(in_sospeso[0], "suggested_action", "")),
        }
    avvisi = [risultato for risultato in pertinenti if str(getattr(risultato, "status", "")) == ValidatorStatus.WARNING.value]
    if avvisi:
        return {
            "stato": "COMPLETATO", "misurabile": True,
            "messaggio": str(getattr(avvisi[0], "message", "")),
            "azione": str(getattr(avvisi[0], "suggested_action", "")),
        }
    if all(str(getattr(risultato, "status", "")) == ValidatorStatus.NOT_APPLICABLE.value for risultato in pertinenti):
        return {"stato": "NON_PERTINENTE", "misurabile": False, "messaggio": str(getattr(pertinenti[0], "message", "")), "azione": ""}
    return {
        "stato": "COMPLETATO", "misurabile": True,
        "messaggio": "Controlli superati: " + ", ".join(dict.fromkeys(controlli)),
        "azione": "",
    }


__all__ = ["CONTROLLI_DI_DEPOSITO", "CONTROLLI_PER_VOCE", "controlli_della_voce", "e_voce_di_deposito", "stato_voce"]
