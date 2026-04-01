"""
pct/compilatore_atti.py - Catalogo modelli atti e compilatore guidato.

Struttura pensata per il software:
- campi base comuni a tutti gli atti
- campi extra per ogni modello
- metadati centralizzati per il wizard frontend
- precompilazione dai dati di pratica / cliente / utente
- validazione coerente backend
- suggerimenti operativi (allegati e clausole)
"""
from __future__ import annotations

import copy
from datetime import date
from typing import Any, Dict, Iterable, List, Optional


def _fc(label: str, field_type: str = "text") -> dict[str, str]:
    return {"label": label, "type": field_type}


def _model(code: str, area: str, name: str, *required_extra_fields: str) -> dict[str, Any]:
    return {
        "code": code,
        "area": area,
        "name": name,
        "required_extra_fields": list(required_extra_fields),
    }


FIELD_CATALOG_RAW: dict[str, dict[str, str]] = {
    "model_code": _fc("Codice Modello"),
    "title": _fc("Titolo Atto"),
    "area": _fc("Area", "select"),
    "act_type": _fc("Tipologia Atto", "select"),
    "case_id": _fc("Pratica Collegata", "select"),
    "matter": _fc("Materia", "select"),
    "recipient_or_court": _fc("Destinatario / Ufficio Giudiziario"),
    "client_or_sender": _fc("Cliente / Mittente"),
    "counterparty_or_recipient": _fc("Controparte / Destinatario"),
    "lawyer": _fc("Difensore"),
    "subject": _fc("Oggetto"),
    "facts": _fc("Esposizione dei Fatti", "richtext"),
    "requests_or_conclusions": _fc("Richieste / Conclusioni", "richtext"),
    "place": _fc("Luogo"),
    "document_date": _fc("Data Atto", "date"),
    "signature": _fc("Firma"),
    "attachments_list": _fc("Elenco Allegati", "multiselect"),
    "author_user_id": _fc("Autore", "select"),
    "version": _fc("Versione"),
    "status": _fc("Stato", "select"),
    "sender": _fc("Mittente"),
    "recipient": _fc("Destinatario"),
    "breach_description": _fc("Descrizione Inadempimento", "richtext"),
    "specific_request": _fc("Richiesta Specifica", "richtext"),
    "deadline_assigned": _fc("Termine Assegnato", "date"),
    "final_warning": _fc("Avvertimento Finale", "richtext"),
    "legal_relationship_title": _fc("Titolo del Rapporto"),
    "requested_amount_or_performance": _fc("Importo o Prestazione Richiesta"),
    "formal_notice_to_perform": _fc("Intimazione ad Adempiere", "richtext"),
    "warning_of_further_actions": _fc("Avviso Ulteriori Azioni", "richtext"),
    "creditor": _fc("Creditore"),
    "debtor": _fc("Debitore"),
    "credit_reason": _fc("Causale del Credito"),
    "requested_amount": _fc("Importo Richiesto", "number"),
    "interest_requested": _fc("Interessi Richiesti"),
    "payment_deadline": _fc("Termine di Pagamento", "date"),
    "payment_method_details": _fc("Modalita di Pagamento", "textarea"),
    "previous_request_reference": _fc("Riferimento Richiesta Precedente"),
    "remaining_amount_or_obligation": _fc("Importo o Obbligo Residuo"),
    "new_deadline": _fc("Nuovo Termine", "date"),
    "communication_body": _fc("Contenuto Comunicazione", "richtext"),
    "final_request": _fc("Richiesta Finale", "richtext"),
    "contested_facts": _fc("Fatti Contestati", "richtext"),
    "facts_period_or_date": _fc("Periodo o Data dei Fatti"),
    "request_for_clarification_or_compliance": _fc("Richiesta di Chiarimenti o Adempimento", "richtext"),
    "reservation_of_rights": _fc("Riserva di Azioni", "richtext"),
    "received_notice_reference": _fc("Riferimento Diffida Ricevuta"),
    "client_position": _fc("Posizione del Cliente", "richtext"),
    "clarifications_or_objections": _fc("Chiarimenti o Contestazioni", "richtext"),
    "proposal": _fc("Proposta", "richtext"),
    "contract_or_relationship": _fc("Contratto o Rapporto"),
    "unfulfilled_obligation": _fc("Obbligo Inadempiuto", "richtext"),
    "final_deadline": _fc("Termine Finale", "date"),
    "legal_consequences_warning": _fc("Avviso Conseguenze Legali", "richtext"),
    "parties": _fc("Parti", "textarea"),
    "dispute_subject": _fc("Oggetto della Controversia"),
    "economic_or_performance_offer": _fc("Offerta Economica o Prestazione", "richtext"),
    "proposal_terms": _fc("Termini della Proposta", "richtext"),
    "acceptance_deadline": _fc("Termine per Accettazione", "date"),
    "without_prejudice_clause": _fc("Clausola Senza Pregiudizio", "richtext"),
    "dispute_background": _fc("Premessa della Controversia", "richtext"),
    "mutual_obligations": _fc("Obblighi Reciproci", "richtext"),
    "amounts_and_deadlines": _fc("Importi e Scadenze", "richtext"),
    "mutual_waivers": _fc("Rinunce Reciproche", "richtext"),
    "costs_allocation": _fc("Ripartizione Spese", "richtext"),
    "jurisdiction_clause": _fc("Clausola Foro Competente"),
    "parties_signatures": _fc("Firme delle Parti", "textarea"),
    "client": _fc("Cliente"),
    "legal_question": _fc("Quesito Giuridico", "richtext"),
    "relevant_facts": _fc("Fatti Rilevanti", "richtext"),
    "legal_analysis": _fc("Analisi Giuridica", "richtext"),
    "operational_conclusion": _fc("Conclusione Operativa", "richtext"),
    "professional": _fc("Professionista"),
    "assignment_object": _fc("Oggetto dell'Incarico"),
    "included_activities": _fc("Attivita Comprese", "richtext"),
    "fee_or_fee_criteria": _fc("Compenso o Criteri di Compenso", "richtext"),
    "expenses_terms": _fc("Termini Spese", "richtext"),
    "privacy_consents": _fc("Consensi Privacy", "textarea"),
    "payment_terms": _fc("Termini di Pagamento", "richtext"),
    "professional_activity_object": _fc("Oggetto Attivita Professionale"),
    "fee_items": _fc("Voci Compenso", "repeater"),
    "expenses": _fc("Spese", "number"),
    "cpa_amount": _fc("CPA", "number"),
    "vat_amount": _fc("IVA", "number"),
    "total_amount": _fc("Totale", "number"),
    "estimate_valid_until": _fc("Validita Preventivo", "date"),
    "court_name": _fc("Ufficio Giudiziario"),
    "plaintiff": _fc("Attore / Ricorrente"),
    "defendant": _fc("Convenuto / Resistente"),
    "lawyer_tax_code": _fc("Codice Fiscale Difensore"),
    "lawyer_pec": _fc("PEC Difensore", "email"),
    "claim_subject": _fc("Oggetto della Domanda"),
    "legal_arguments": _fc("Motivi in Diritto", "richtext"),
    "evidence_means": _fc("Mezzi di Prova", "richtext"),
    "documents_offered": _fc("Documenti Prodotti", "multiselect"),
    "hearing_date": _fc("Data Udienza", "date"),
    "appearance_notice": _fc("Invito a Comparire", "richtext"),
    "ritual_warnings": _fc("Avvertimenti di Rito", "richtext"),
    "case_value": _fc("Valore della Causa", "number"),
    "proceeding_number": _fc("Numero Procedimento"),
    "position_on_facts": _fc("Posizione sui Fatti", "richtext"),
    "procedural_exceptions": _fc("Eccezioni Processuali", "richtext"),
    "merit_exceptions": _fc("Eccezioni di Merito", "richtext"),
    "counterclaim": _fc("Domanda Riconvenzionale", "richtext"),
    "third_party_call": _fc("Chiamata di Terzo", "richtext"),
    "competent_court": _fc("Giudice Competente"),
    "claimant": _fc("Ricorrente / Creditore"),
    "credit_source": _fc("Fonte del Credito"),
    "credit_due_date": _fc("Scadenza / Esigibilita del Credito", "date"),
    "written_evidence": _fc("Prova Scritta", "richtext"),
    "requested_costs": _fc("Spese Richieste"),
    "provisional_enforceability_request": _fc("Richiesta Provvisoria Esecutorieta", "richtext"),
    "issuing_court": _fc("Ufficio Emittente"),
    "injunction_number": _fc("Numero Decreto"),
    "injunction_date": _fc("Data Decreto", "date"),
    "injunction_service_date": _fc("Data Notifica Decreto", "date"),
    "opponent": _fc("Opponente"),
    "opposed_party": _fc("Opposto"),
    "grounds_of_opposition": _fc("Motivi di Opposizione", "richtext"),
    "credit_or_amount_or_procedure_objections": _fc("Contestazioni su Credito / Importo / Procedura", "richtext"),
    "request_for_stay_of_enforceability": _fc("Richiesta Sospensione Esecutorieta", "richtext"),
    "linked_proceeding": _fc("Procedimento Collegato"),
    "filing_party": _fc("Parte Depositante"),
    "memo_subject": _fc("Oggetto della Memoria"),
    "clarifications_or_arguments": _fc("Chiarimenti o Argomentazioni", "richtext"),
    "applicant": _fc("Istante"),
    "request_content": _fc("Contenuto Richiesta", "richtext"),
    "request_reason": _fc("Motivo della Richiesta", "richtext"),
    "documents_list_detailed": _fc("Elenco Documenti Dettagliato", "repeater"),
    "attachments_numbering": _fc("Numerazione Allegati", "textarea"),
    "purpose_of_filing": _fc("Finalita del Deposito", "richtext"),
    "party": _fc("Parte"),
    "relevant_facts_summary": _fc("Sintesi Fatti Rilevanti", "richtext"),
    "legal_summary": _fc("Sintesi in Diritto", "richtext"),
    "evidence_assessment": _fc("Valutazione Prove", "richtext"),
    "final_conclusions": _fc("Conclusioni Definitive", "richtext"),
    "opponent_conclusion_reference": _fc("Riferimento Atto Avversario"),
    "specific_reply_points": _fc("Punti Specifici di Replica", "richtext"),
    "appeal_court": _fc("Giudice d'Appello"),
    "appellant": _fc("Appellante"),
    "appellee": _fc("Appellato"),
    "appealed_judgment": _fc("Sentenza Impugnata"),
    "judgment_publication_or_service_date": _fc("Data Pubblicazione o Notifica Sentenza", "date"),
    "challenged_parts": _fc("Capi Impugnati", "richtext"),
    "specific_grounds_of_appeal": _fc("Motivi Specifici di Appello", "richtext"),
    "request_for_reform_or_annulment": _fc("Richiesta di Riforma o Annullamento", "richtext"),
    "admissible_evidence_or_documents": _fc("Prove o Documenti Ammissibili", "richtext"),
}


BASE_REQUIRED_FIELDS: list[str] = [
    "model_code",
    "title",
    "area",
    "act_type",
    "case_id",
    "matter",
    "recipient_or_court",
    "client_or_sender",
    "counterparty_or_recipient",
    "lawyer",
    "subject",
    "facts",
    "requests_or_conclusions",
    "place",
    "document_date",
    "signature",
    "attachments_list",
    "author_user_id",
    "version",
    "status",
]


FIELD_CATALOG_RAW.update(
    {
        "enforcement_title": _fc("Titolo Esecutivo"),
        "title_service_date": _fc("Data Notifica Titolo", "date"),
        "principal_amount": _fc("Capitale", "number"),
        "interest_amount": _fc("Interessi", "number"),
        "costs_amount": _fc("Spese", "number"),
        "formal_intimation_to_pay": _fc("Intimazione ad Adempiere", "richtext"),
        "legal_warnings": _fc("Avvertimenti di Legge", "richtext"),
        "proceeding_creditor": _fc("Creditore Procedente"),
        "enforced_debtor": _fc("Debitore Esecutato"),
        "third_party_garnishee": _fc("Terzo Pignorato"),
        "precetto_reference": _fc("Riferimento Precetto"),
        "attached_credits_or_amounts": _fc("Crediti o Somme Pignorate", "richtext"),
        "injunctions_to_debtor_and_third_party": _fc("Intimazioni a Debitore e Terzo", "richtext"),
        "competent_judge": _fc("Giudice Competente"),
        "parties_addresses_or_pec": _fc("Indirizzi / PEC Parti", "textarea"),
        "essential_attachments": _fc("Allegati Essenziali", "multiselect"),
        "contested_enforcement_title": _fc("Titolo Esecutivo Contestato"),
        "enforcement_stage": _fc("Stato della Procedura Esecutiva"),
        "stay_request": _fc("Richiesta di Sospensione", "richtext"),
        "challenged_enforcement_act": _fc("Atto Esecutivo Impugnato"),
        "knowledge_or_service_date": _fc("Data Conoscenza o Notifica", "date"),
        "procedural_defects_alleged": _fc("Vizi Procedurali Denunciati", "richtext"),
        "respondent": _fc("Resistente"),
        "fumus_boni_iuris": _fc("Fumus Boni Iuris", "richtext"),
        "periculum_in_mora": _fc("Periculum in Mora", "richtext"),
        "requested_interim_measure": _fc("Misura Cautelare Richiesta", "richtext"),
        "main_proceeding": _fc("Procedimento Principale"),
        "applicant_party": _fc("Parte Istante"),
        "urgency_reason": _fc("Motivo d'Urgenza", "richtext"),
        "imminent_prejudice": _fc("Pregiudizio Imminente", "richtext"),
        "requested_measure": _fc("Misura Richiesta", "richtext"),
        "supporting_attachments": _fc("Allegati di Supporto", "multiselect"),
        "respondent_party": _fc("Parte Resistente"),
        "defence_on_facts": _fc("Difese sui Fatti", "richtext"),
        "exceptions": _fc("Eccezioni", "richtext"),
        "landlord": _fc("Locatore"),
        "tenant": _fc("Conduttore"),
        "lease_agreement": _fc("Contratto di Locazione"),
        "property_address": _fc("Immobile"),
        "grounds_for_eviction": _fc("Motivo dello Sfratto", "richtext"),
        "rent_or_charges_due": _fc("Canoni / Oneri Dovuti"),
        "order_to_release_property": _fc("Intimazione di Rilascio", "richtext"),
        "grounds_for_validation": _fc("Motivo della Convalida", "richtext"),
        "unpaid_rents_or_contract_expiry": _fc("Canoni Insoluti o Scadenza Contratto"),
        "request_for_validation": _fc("Richiesta di Convalida", "richtext"),
        "proceeding_authority": _fc("Autorita Procedente"),
        "assisted_person": _fc("Assistito / Indagato / Imputato"),
        "criminal_proceeding_reference": _fc("Riferimento Procedimento Penale"),
        "appointed_defender": _fc("Difensore Nominato"),
        "defender_bar_association": _fc("Foro Difensore"),
        "defender_pec": _fc("PEC Difensore", "email"),
        "elected_domicile": _fc("Domicilio Eletto"),
        "assisted_person_signature": _fc("Firma Assistito"),
        "defensive_arguments": _fc("Argomentazioni Difensive", "richtext"),
        "specific_requests": _fc("Richieste Specifiche", "richtext"),
        "requesting_party": _fc("Parte Richiedente"),
        "postponement_reason": _fc("Motivo del Rinvio", "richtext"),
        "supporting_documents": _fc("Documenti Giustificativi", "multiselect"),
        "office_name": _fc("Ufficio"),
        "requested_documents_or_records": _fc("Atti o Documenti Richiesti", "textarea"),
        "legal_entitlement_title": _fc("Titolo Legittimante"),
        "defendant_person": _fc("Imputato"),
        "penal_decree_reference": _fc("Riferimento Decreto Penale"),
        "service_date": _fc("Data Notifica", "date"),
        "grounds_or_declaration_of_opposition": _fc("Motivi o Dichiarazione di Opposizione", "richtext"),
        "specific_procedural_requests": _fc("Richieste Processuali Specifiche", "richtext"),
        "competent_authority": _fc("Autorita Competente"),
        "appealing_party": _fc("Parte Impugnante"),
        "challenged_measure": _fc("Provvedimento Impugnato"),
        "measure_or_service_date": _fc("Data Provvedimento o Notifica", "date"),
        "grounds_of_appeal": _fc("Motivi di Impugnazione / Appello", "richtext"),
        "competent_prosecutor_office": _fc("Procura Competente"),
        "seized_asset": _fc("Bene Sequestrato"),
        "seizure_report_reference": _fc("Riferimento Verbale di Sequestro"),
        "grounds_for_release": _fc("Motivi del Dissequestro", "richtext"),
        "hearing_authority": _fc("Autorita Udienza"),
        "defensive_position_summary": _fc("Sintesi Posizione Difensiva", "richtext"),
        "competent_tar": _fc("TAR Competente"),
        "respondent_administration": _fc("Amministrazione Resistente"),
        "interested_third_parties": _fc("Controinteressati", "textarea"),
        "challenged_administrative_act": _fc("Atto Amministrativo Impugnato"),
        "request_for_annulment_or_other_relief": _fc("Richiesta di Annullamento o Altra Tutela", "richtext"),
        "interim_relief_request": _fc("Domanda Cautelare", "richtext"),
        "main_case_reference": _fc("Riferimento Giudizio Principale"),
        "new_act_or_new_grounds": _fc("Nuovo Atto o Nuovi Motivi", "richtext"),
        "knowledge_date": _fc("Data di Conoscenza", "date"),
        "supervening_facts": _fc("Fatti Sopravvenuti", "richtext"),
        "additional_grounds": _fc("Motivi Aggiunti", "richtext"),
        "linked_case_reference": _fc("Riferimento Giudizio Collegato"),
        "serious_and_irreparable_harm": _fc("Pregiudizio Grave e Irreparabile", "richtext"),
        "case_reference": _fc("Riferimento Giudizio"),
        "facts_summary": _fc("Sintesi dei Fatti", "richtext"),
        "legal_defence": _fc("Difese in Diritto", "richtext"),
        "reply_to_counterpart": _fc("Replica alla Controparte", "richtext"),
        "appeal_tax_court": _fc("Giudice Tributario d'Appello"),
        "appellees": _fc("Appellati", "textarea"),
        "challenged_interim_measure": _fc("Provvedimento Cautelare Impugnato"),
        "urgency_reasons": _fc("Ragioni di Urgenza", "richtext"),
        "grounds_of_interim_appeal": _fc("Motivi Appello Cautelare", "richtext"),
        "competent_tax_court": _fc("Corte di Giustizia Tributaria Competente"),
        "tax_authority_or_resistant_party": _fc("Ente Impositore / Resistente"),
        "challenged_tax_act": _fc("Atto Tributario Impugnato"),
        "dispute_value": _fc("Valore Controversia", "number"),
        "digital_domicile_or_pec": _fc("Domicilio Digitale / PEC"),
        "tax_case_reference": _fc("Riferimento Giudizio Tributario"),
        "resistant_party": _fc("Parte Resistente"),
        "preliminary_exceptions": _fc("Eccezioni Preliminari", "richtext"),
        "defences_on_merits": _fc("Difese nel Merito", "richtext"),
        "linked_tax_case": _fc("Ricorso Tributario Collegato"),
        "request_for_suspension": _fc("Richiesta di Sospensione", "richtext"),
        "factual_clarifications": _fc("Chiarimenti in Fatto", "richtext"),
        "legal_clarifications": _fc("Chiarimenti in Diritto", "richtext"),
        "appeal_case_reference": _fc("Riferimento Giudizio d'Appello"),
        "defences_against_appeal_grounds": _fc("Difese contro i Motivi di Appello", "richtext"),
        "request_subject": _fc("Oggetto dell'Istanza"),
    }
)


MODELS: list[dict[str, Any]] = [
    _model("STR_DIFF_001", "STRAGIUDIZIALE", "Diffida", "sender", "recipient", "breach_description", "specific_request", "deadline_assigned", "final_warning"),
    _model("STR_MM_001", "STRAGIUDIZIALE", "Messa in Mora", "sender", "recipient", "legal_relationship_title", "breach_description", "requested_amount_or_performance", "formal_notice_to_perform", "deadline_assigned", "warning_of_further_actions"),
    _model("STR_RDP_001", "STRAGIUDIZIALE", "Richiesta di Pagamento", "creditor", "debtor", "credit_reason", "requested_amount", "interest_requested", "payment_deadline", "payment_method_details"),
    _model("STR_SOLL_001", "STRAGIUDIZIALE", "Sollecito Formale", "sender", "recipient", "previous_request_reference", "remaining_amount_or_obligation", "new_deadline", "final_warning"),
    _model("STR_COM_001", "STRAGIUDIZIALE", "Comunicazione Professionale", "sender", "recipient", "communication_body", "final_request"),
    _model("STR_CONTEST_001", "STRAGIUDIZIALE", "Lettera di Contestazione", "sender", "recipient", "contested_facts", "facts_period_or_date", "request_for_clarification_or_compliance", "deadline_assigned", "reservation_of_rights"),
    _model("STR_RISDIFF_001", "STRAGIUDIZIALE", "Riscontro a Diffida", "sender", "recipient", "received_notice_reference", "client_position", "clarifications_or_objections", "proposal"),
    _model("STR_INVAD_001", "STRAGIUDIZIALE", "Invito ad Adempiere", "sender", "recipient", "contract_or_relationship", "unfulfilled_obligation", "final_deadline", "legal_consequences_warning"),
    _model("STR_PTR_001", "STRAGIUDIZIALE", "Proposta Transattiva", "parties", "dispute_subject", "economic_or_performance_offer", "proposal_terms", "acceptance_deadline", "without_prejudice_clause"),
    _model("STR_ATR_001", "STRAGIUDIZIALE", "Accordo Transattivo", "parties", "dispute_background", "mutual_obligations", "amounts_and_deadlines", "mutual_waivers", "costs_allocation", "jurisdiction_clause", "parties_signatures"),
    _model("STR_PAR_001", "STRAGIUDIZIALE", "Parere Sintetico", "client", "legal_question", "relevant_facts", "legal_analysis", "operational_conclusion"),
    _model("STR_INC_001", "STRAGIUDIZIALE", "Incarico Professionale", "client", "professional", "assignment_object", "included_activities", "fee_or_fee_criteria", "expenses_terms", "payment_terms", "privacy_consents", "parties_signatures"),
    _model("STR_PREV_001", "STRAGIUDIZIALE", "Preventivo Professionale", "client", "professional_activity_object", "fee_items", "expenses", "cpa_amount", "vat_amount", "total_amount", "estimate_valid_until", "payment_terms"),
    _model("CIV_CIT_001", "CIVILE", "Atto di Citazione", "court_name", "plaintiff", "defendant", "lawyer_tax_code", "lawyer_pec", "claim_subject", "legal_arguments", "evidence_means", "documents_offered", "hearing_date", "appearance_notice", "ritual_warnings", "case_value"),
    _model("CIV_COM_001", "CIVILE", "Comparsa di Costituzione e Risposta", "court_name", "proceeding_number", "defendant", "plaintiff", "lawyer_tax_code", "lawyer_pec", "position_on_facts", "procedural_exceptions", "merit_exceptions", "counterclaim", "third_party_call", "evidence_means", "documents_offered"),
    _model("CIV_RDI_001", "CIVILE", "Ricorso per Decreto Ingiuntivo", "competent_court", "claimant", "debtor", "credit_source", "requested_amount", "credit_due_date", "written_evidence", "interest_requested", "requested_costs", "provisional_enforceability_request"),
    _model("CIV_OPPDI_001", "CIVILE", "Opposizione a Decreto Ingiuntivo", "issuing_court", "injunction_number", "injunction_date", "injunction_service_date", "opponent", "opposed_party", "grounds_of_opposition", "credit_or_amount_or_procedure_objections", "request_for_stay_of_enforceability", "evidence_means", "documents_offered"),
    _model("CIV_MEM_001", "CIVILE", "Memoria Generica", "linked_proceeding", "filing_party", "memo_subject", "clarifications_or_arguments"),
    _model("CIV_IST_001", "CIVILE", "Istanza Generica", "court_name", "proceeding_number", "applicant", "request_content", "request_reason"),
    _model("CIV_DEPDOC_001", "CIVILE", "Deposito Documenti", "court_name", "proceeding_number", "filing_party", "documents_list_detailed", "attachments_numbering", "purpose_of_filing"),
    _model("CIV_CONCL_001", "CIVILE", "Comparsa Conclusionale", "proceeding_number", "party", "relevant_facts_summary", "legal_summary", "evidence_assessment", "final_conclusions"),
    _model("CIV_REPL_001", "CIVILE", "Memoria di Replica", "proceeding_number", "party", "opponent_conclusion_reference", "specific_reply_points", "final_conclusions"),
    _model("CIV_APP_001", "CIVILE", "Appello Civile", "appeal_court", "appellant", "appellee", "appealed_judgment", "judgment_publication_or_service_date", "challenged_parts", "specific_grounds_of_appeal", "request_for_reform_or_annulment", "admissible_evidence_or_documents"),
    _model("CIV_PREC_001", "CIVILE", "Atto di Precetto", "creditor", "debtor", "enforcement_title", "title_service_date", "principal_amount", "interest_amount", "costs_amount", "formal_intimation_to_pay", "payment_deadline", "legal_warnings"),
    _model("CIV_PPT_001", "CIVILE", "Pignoramento Presso Terzi", "proceeding_creditor", "enforced_debtor", "third_party_garnishee", "enforcement_title", "precetto_reference", "attached_credits_or_amounts", "injunctions_to_debtor_and_third_party", "hearing_date", "competent_judge", "parties_addresses_or_pec", "essential_attachments"),
    _model("CIV_OPESE_001", "CIVILE", "Opposizione all'Esecuzione", "competent_judge", "opponent", "opposed_party", "contested_enforcement_title", "enforcement_stage", "grounds_of_opposition", "stay_request", "documents_offered"),
    _model("CIV_OPATTESE_001", "CIVILE", "Opposizione agli Atti Esecutivi", "competent_judge", "opponent", "challenged_enforcement_act", "knowledge_or_service_date", "procedural_defects_alleged", "stay_request", "documents_offered"),
    _model("CIV_RCAUT_001", "CIVILE", "Ricorso Cautelare", "competent_judge", "claimant", "respondent", "fumus_boni_iuris", "periculum_in_mora", "requested_interim_measure", "legal_arguments", "documents_offered"),
    _model("CIV_ICAUT_001", "CIVILE", "Istanza Cautelare", "main_proceeding", "applicant_party", "urgency_reason", "imminent_prejudice", "requested_measure", "supporting_attachments"),
    _model("CIV_LAVRIC_001", "CIVILE", "Ricorso in Materia di Lavoro", "court_name", "claimant", "defendant", "claim_subject", "legal_arguments", "evidence_means", "documents_offered"),
    _model("CIV_LAVMEM_001", "CIVILE", "Memoria Difensiva Lavoro", "court_name", "proceeding_number", "respondent_party", "defence_on_facts", "exceptions", "evidence_means", "documents_offered"),
    _model("CIV_SFRINT_001", "CIVILE", "Intimazione di Sfratto", "competent_court", "landlord", "tenant", "lease_agreement", "property_address", "grounds_for_eviction", "rent_or_charges_due", "order_to_release_property", "hearing_date"),
    _model("CIV_CONVSFR_001", "CIVILE", "Citazione per Convalida di Sfratto", "competent_court", "landlord", "tenant", "lease_agreement", "property_address", "grounds_for_validation", "unpaid_rents_or_contract_expiry", "hearing_date", "request_for_validation"),
    _model("PEN_NOM_001", "PENALE", "Nomina Difensore", "proceeding_authority", "assisted_person", "criminal_proceeding_reference", "appointed_defender", "defender_bar_association", "defender_pec", "elected_domicile", "assisted_person_signature"),
    _model("PEN_MEM_001", "PENALE", "Memoria Difensiva", "proceeding_authority", "assisted_person", "criminal_proceeding_reference", "defensive_arguments", "specific_requests", "documents_offered"),
    _model("PEN_IST_001", "PENALE", "Istanza Generica Penale", "proceeding_authority", "assisted_person", "criminal_proceeding_reference", "request_content", "request_reason"),
    _model("PEN_RINV_001", "PENALE", "Istanza di Rinvio", "proceeding_authority", "criminal_proceeding_reference", "hearing_date", "requesting_party", "postponement_reason", "supporting_documents"),
    _model("PEN_COPIE_001", "PENALE", "Richiesta Copie", "office_name", "criminal_proceeding_reference", "requesting_party", "requested_documents_or_records", "legal_entitlement_title"),
    _model("PEN_DEPDOC_001", "PENALE", "Deposito Documenti Penale", "criminal_proceeding_reference", "filing_party", "documents_list_detailed", "purpose_of_filing"),
    _model("PEN_OPPDP_001", "PENALE", "Opposizione a Decreto Penale", "competent_judge", "defendant_person", "penal_decree_reference", "service_date", "grounds_or_declaration_of_opposition", "specific_procedural_requests"),
    _model("PEN_IMP_001", "PENALE", "Atto di Impugnazione", "competent_authority", "appealing_party", "challenged_measure", "measure_or_service_date", "challenged_parts", "grounds_of_appeal"),
    _model("PEN_PM_001", "PENALE", "Istanza al Pubblico Ministero", "competent_prosecutor_office", "assisted_person", "criminal_proceeding_reference", "request_content", "request_reason"),
    _model("PEN_DISSEQ_001", "PENALE", "Istanza di Dissequestro", "competent_authority", "seized_asset", "seizure_report_reference", "applicant", "grounds_for_release", "supporting_documents"),
    _model("PEN_NOTEUD_001", "PENALE", "Note d'Udienza Penale", "hearing_authority", "criminal_proceeding_reference", "party", "defensive_position_summary", "final_conclusions"),
    _model("AMM_RIC_001", "AMMINISTRATIVO", "Ricorso al TAR", "competent_tar", "claimant", "respondent_administration", "interested_third_parties", "challenged_administrative_act", "knowledge_or_service_date", "legal_arguments", "request_for_annulment_or_other_relief", "interim_relief_request", "documents_offered", "case_value"),
    _model("AMM_MOTAGG_001", "AMMINISTRATIVO", "Motivi Aggiunti", "main_case_reference", "claimant", "new_act_or_new_grounds", "knowledge_date", "supervening_facts", "additional_grounds", "specific_requests", "documents_offered"),
    _model("AMM_ICAUT_001", "AMMINISTRATIVO", "Istanza Cautelare Amministrativa", "linked_case_reference", "applicant_party", "serious_and_irreparable_harm", "fumus_boni_iuris", "requested_interim_measure", "documents_offered"),
    _model("AMM_MEM_001", "AMMINISTRATIVO", "Memoria Difensiva Amministrativa", "case_reference", "party", "facts_summary", "legal_defence", "reply_to_counterpart", "final_conclusions"),
    _model("AMM_DEPDOC_001", "AMMINISTRATIVO", "Deposito Documenti Amministrativo", "case_reference", "filing_party", "documents_list_detailed", "attachments_numbering", "purpose_of_filing"),
    _model("AMM_NOTEUD_001", "AMMINISTRATIVO", "Note d'Udienza Amministrative", "case_reference", "party", "hearing_date", "defensive_position_summary", "specific_requests"),
    _model("AMM_APPCDS_001", "AMMINISTRATIVO", "Appello al Consiglio di Stato", "appeal_court", "appellant", "appellees", "interested_third_parties", "appealed_judgment", "grounds_of_appeal", "interim_relief_request", "final_conclusions", "documents_offered"),
    _model("AMM_APPCAUT_001", "AMMINISTRATIVO", "Appello Cautelare", "challenged_interim_measure", "appellant", "urgency_reasons", "grounds_of_interim_appeal", "requested_measure", "documents_offered"),
    _model("AMM_SEG_001", "AMMINISTRATIVO", "Istanza di Segreteria", "case_reference", "requesting_party", "request_subject", "request_reason", "supporting_documents"),
    _model("TRIB_RIC_001", "TRIBUTARIO", "Ricorso Tributario", "competent_tax_court", "claimant", "tax_authority_or_resistant_party", "challenged_tax_act", "service_date", "dispute_value", "grounds_of_appeal", "final_request", "interim_relief_request", "documents_offered", "digital_domicile_or_pec"),
    _model("TRIB_CONTRO_001", "TRIBUTARIO", "Controdeduzioni", "tax_case_reference", "resistant_party", "challenged_tax_act", "preliminary_exceptions", "defences_on_merits", "documents_offered", "final_conclusions"),
    _model("TRIB_SOSP_001", "TRIBUTARIO", "Istanza di Sospensione", "linked_tax_case", "applicant_party", "serious_and_irreparable_harm", "fumus_boni_iuris", "request_for_suspension", "supporting_documents"),
    _model("TRIB_MEMILL_001", "TRIBUTARIO", "Memoria Illustrativa", "tax_case_reference", "party", "factual_clarifications", "legal_clarifications", "reply_to_counterpart", "final_conclusions"),
    _model("TRIB_DEPDOC_001", "TRIBUTARIO", "Deposito Documenti Tributario", "tax_case_reference", "filing_party", "documents_list_detailed", "purpose_of_filing", "attachments_numbering"),
    _model("TRIB_APP_001", "TRIBUTARIO", "Appello Tributario", "appeal_tax_court", "appellant", "appellee", "appealed_judgment", "grounds_of_appeal", "specific_requests", "interim_relief_request", "documents_offered"),
    _model("TRIB_CONTROAPP_001", "TRIBUTARIO", "Controdeduzioni in Appello", "appeal_case_reference", "appellee", "preliminary_exceptions", "defences_against_appeal_grounds", "documents_offered", "final_conclusions"),
    _model("TRIB_IST_001", "TRIBUTARIO", "Istanza Generica Tributaria", "tax_case_reference", "applicant_party", "request_subject", "request_reason", "supporting_documents"),
]


AREA_ORDINE = ["STRAGIUDIZIALE", "CIVILE", "PENALE", "AMMINISTRATIVO", "TRIBUTARIO"]
AREA_LABELS = {
    "STRAGIUDIZIALE": "Stragiudiziale",
    "CIVILE": "Civile",
    "PENALE": "Penale",
    "AMMINISTRATIVO": "Amministrativo",
    "TRIBUTARIO": "Tributario",
}

STATUS_OPTIONS = [("BOZZA", "Bozza"), ("IN_REVISIONE", "In revisione"), ("PRONTO", "Pronto")]
MODEL_INDEX = {model["code"]: model for model in MODELS}
HIDDEN_BASE_FIELDS = {"model_code", "area", "act_type", "case_id", "author_user_id", "version", "status"}
FIELD_ALIASES_BY_ROLE = {
    "cliente": {
        "sender", "client", "client_or_sender", "creditor", "claimant", "plaintiff", "applicant", "applicant_party",
        "filing_party", "party", "requesting_party", "proceeding_creditor", "landlord", "appellant", "appealing_party",
        "assisted_person", "defendant_person", "opponent",
    },
    "controparte": {
        "recipient", "counterparty_or_recipient", "debtor", "defendant", "opposed_party", "respondent", "respondent_party",
        "resistant_party", "tax_authority_or_resistant_party", "tenant", "appellee", "appellees", "third_party_garnishee",
        "respondent_administration", "interested_third_parties",
    },
    "ufficio": {
        "court_name", "competent_court", "issuing_court", "appeal_court", "competent_judge", "competent_authority",
        "competent_prosecutor_office", "proceeding_authority", "hearing_authority", "office_name", "competent_tar",
        "competent_tax_court", "appeal_tax_court",
    },
    "riferimento": {
        "proceeding_number", "linked_proceeding", "criminal_proceeding_reference", "main_case_reference", "case_reference",
        "linked_case_reference", "tax_case_reference", "linked_tax_case", "appeal_case_reference",
    },
}

AREA_PRO_GUIDANCE: dict[str, dict[str, Any]] = {
    "STRAGIUDIZIALE": {
        "summary": "Atto stragiudiziale impostato per diffide, messe in mora, richieste di pagamento e comunicazioni professionali con tono formale e tracciabile.",
        "when_to_use": [
            "Prima dell'azione giudiziale, per fissare una posizione chiara e creare prova documentale.",
            "Quando serve assegnare un termine, costituire in mora o formalizzare una proposta o contestazione.",
        ],
        "structure": [
            "Intestazione del mittente e del destinatario.",
            "Oggetto sintetico e immediatamente leggibile.",
            "Ricostruzione dei fatti o dell'inadempimento.",
            "Richiesta finale con termine e avvertimento conclusivo.",
        ],
        "technical_notes": [
            "Verifica che destinatario, PEC e allegati coincidano con quanto andra effettivamente notificato o inviato.",
            "Mantieni una formula conclusiva coerente con l'effetto voluto: diffida, messa in mora, contestazione o proposta.",
        ],
        "references": [
            "Codice civile: regole generali su adempimento, mora e responsabilita.",
            "Prassi di studio: preferire allegati nominati in modo coerente con la lettera.",
        ],
    },
    "CIVILE": {
        "summary": "Atto giudiziale civile impostato per una redazione ordinata, leggibile e gia pronta per revisione e deposito.",
        "when_to_use": [
            "Per introdurre o coltivare un giudizio civile con una struttura chiara su fatti, diritto e richieste.",
            "Quando occorre allineare il testo dell'atto alla pratica, ai documenti gia presenti e ai dati del fascicolo.",
        ],
        "structure": [
            "Intestazione dell'ufficio giudiziario o dell'autorita competente.",
            "Indicazione delle parti assistite e della controparte.",
            "Esposizione dei fatti, motivi in diritto, mezzi istruttori e conclusioni.",
            "Chiusura con valore, allegati, luogo, data e sottoscrizione.",
        ],
        "technical_notes": [
            "Controlla sempre competenza, rito, termini processuali e prova documentale prima del deposito.",
            "Per il PCT conserva un PDF nativo ben formattato e firma secondo il flusso del redattore atti.",
        ],
        "references": [
            "Codice di procedura civile.",
            "D.M. 44/2011 per il deposito telematico civile.",
        ],
    },
    "PENALE": {
        "summary": "Atto penale guidato per richieste difensive, memorie, nomine e istanze verso l'autorita procedente.",
        "when_to_use": [
            "Per definire in modo sintetico ma completo la posizione dell'assistito e le richieste alla Procura o al giudice.",
            "Quando serve un atto chiaro, depositabile e immediatamente verificabile sul fascicolo penale.",
        ],
        "structure": [
            "Autorita procedente, riferimento del procedimento e parte assistita.",
            "Argomentazioni difensive e richieste specifiche.",
            "Documenti prodotti o allegati richiamati nel testo.",
        ],
        "technical_notes": [
            "Nel penale telematico verifica sempre formato di firma, canale di deposito e termini perentori.",
            "Le richieste devono essere collegate a un potere difensivo o a una base normativa chiara.",
        ],
        "references": [
            "Codice di procedura penale.",
            "Regole tecniche del portale PDP Penale.",
        ],
    },
    "AMMINISTRATIVO": {
        "summary": "Atto amministrativo costruito per ricorsi, memorie e istanze con attenzione a termini, cautelare e documenti amministrativi.",
        "when_to_use": [
            "Per impugnare atti amministrativi o sviluppare il giudizio davanti al TAR o al Consiglio di Stato.",
            "Quando occorre coordinare motivi, domanda cautelare e documenti gia raccolti in pratica.",
        ],
        "structure": [
            "Autorita adita, parti e atto impugnato.",
            "Fatti, motivi di ricorso o difesa, domanda cautelare, conclusioni.",
            "Elenco allegati e chiusura del documento.",
        ],
        "technical_notes": [
            "Controlla sempre il termine decadenziale e la prova della piena conoscenza o notifica dell'atto impugnato.",
            "Adegua il documento alle regole del deposito telematico amministrativo e ai protocolli locali.",
        ],
        "references": [
            "Codice del processo amministrativo.",
            "Regole tecniche PAT.",
        ],
    },
    "TRIBUTARIO": {
        "summary": "Atto tributario predisposto per ricorsi, controdeduzioni e istanze con attenzione a valore, notifica e mediazione tributaria.",
        "when_to_use": [
            "Per impugnare un atto tributario o sviluppare il contraddittorio davanti alla giustizia tributaria.",
            "Quando serve una bozza completa di riferimenti a atto impugnato, valore, motivi e allegati fiscali.",
        ],
        "structure": [
            "Corte tributaria competente, parti e atto impugnato.",
            "Motivi del ricorso o delle difese.",
            "Richiesta cautelare, conclusioni e documenti prodotti.",
        ],
        "technical_notes": [
            "Verifica sempre notifica dell'atto impugnato, valore della controversia e condizioni di procedibilita eventualmente applicabili.",
            "Nel deposito telematico tributario rispetta il flusso NIR e la firma richiesta dal portale.",
        ],
        "references": [
            "D.Lgs. 546/1992.",
            "Regole tecniche del processo tributario telematico.",
        ],
    },
}

MODEL_GUIDANCE_OVERRIDES: dict[str, dict[str, Any]] = {
    "STR_DIFF_001": {
        "summary": "Diffida formale gia impostata per sollecitare l'adempimento, fissare un termine e mettere in chiaro le conseguenze del mancato riscontro.",
        "when_to_use": [
            "Quando vuoi una lettera netta, tracciabile e immediatamente utilizzabile come antecedente del contenzioso.",
            "Quando serve una richiesta formale con termine preciso e riserva di azioni ulteriori.",
        ],
        "structure": [
            "Mittente, destinatario e oggetto della diffida.",
            "Descrizione dell'inadempimento e richiesta specifica.",
            "Termine con avvertimento finale e richiamo agli allegati.",
        ],
    },
    "CIV_CIT_001": {
        "summary": "Atto di Citazione per il giudizio ordinario di cognizione, redatto con schema gia allineato a intestazione, parti, fatto, diritto, vocatio in ius e conclusioni.",
        "when_to_use": [
            "Quando il diritto va fatto valere con giudizio ordinario e non e sufficiente o opportuno il monitorio.",
            "Quando la controversia richiede piena istruttoria, accertamento del fatto o valutazioni non sostenute da sola prova scritta liquida.",
        ],
        "structure": [
            "Intestazione del Tribunale competente e titolo dell'atto.",
            "Parte attrice, difensore, domicilio professionale e controparte.",
            "Sezioni FATTO e DIRITTO con esposizione chiara e specifica.",
            "Vocatio in ius con udienza, termine a comparire e avvertimenti di rito.",
            "Conclusioni, mezzi istruttori, documenti prodotti e dichiarazione di valore.",
        ],
        "technical_notes": [
            "Riforma Cartabia: il termine minimo tra notifica e udienza e di 120 giorni in Italia ai sensi dell'art. 163-bis c.p.c.",
            "Il convenuto deve costituirsi almeno 70 giorni prima dell'udienza indicata, ai sensi dell'art. 166 c.p.c.",
            "Per il deposito telematico prepara un PDF nativo ben formattato e firma PAdES o CAdES secondo il flusso del redattore atti.",
        ],
        "references": [
            "Art. 163 c.p.c.",
            "Art. 163-bis c.p.c.",
            "Art. 166 c.p.c.",
            "D.M. 44/2011.",
        ],
    },
    "CIV_RDI_001": {
        "summary": "Ricorso monitorio strutturato per crediti da prova scritta, con attenzione a importi, scadenza e documentazione a supporto.",
        "when_to_use": [
            "Quando il credito e certo, liquido, esigibile e assistito da prova scritta idonea.",
            "Quando si vuole ottenere un titolo monitorio prima dell'eventuale fase di opposizione.",
        ],
    },
    "CIV_COM_001": {
        "summary": "Comparsa di costituzione e risposta impostata per contestare fatti, proporre eccezioni, riconvenzionale o chiamata di terzo in modo ordinato.",
        "when_to_use": [
            "Quando il convenuto si costituisce e deve prendere posizione su domanda, fatti, eccezioni e prova.",
            "Quando occorre impostare una difesa completa gia pronta per deposito telematico.",
        ],
    },
}


def _field_meta(name: str) -> dict[str, Any]:
    raw = FIELD_CATALOG_RAW.get(name)
    if not raw:
        label = name.replace("_", " ").strip().title()
        raw = {"label": label, "type": _infer_field_type(name)}
    field_type = raw["type"]
    label = raw["label"]
    return {
        "name": name,
        "label": label,
        "type": field_type,
        "required": True,
        "placeholder": _placeholder_for(label, field_type),
    }


def _infer_field_type(name: str) -> str:
    lowered = name.lower()
    if lowered in {"area", "act_type", "case_id", "matter", "author_user_id", "status"}:
        return "select"
    if any(token in lowered for token in ("date", "deadline", "until")):
        return "date"
    if any(token in lowered for token in ("amount", "value", "expenses", "vat", "cpa", "total")):
        return "number"
    if any(token in lowered for token in ("pec", "email")):
        return "email"
    if lowered in {"documents_offered", "supporting_documents", "supporting_attachments", "essential_attachments", "attachments_list"}:
        return "multiselect"
    if lowered in {"documents_list_detailed", "fee_items"}:
        return "repeater"
    if any(token in lowered for token in ("facts", "warning", "request", "arguments", "analysis", "conclusions", "summary", "grounds", "reply", "proposal", "objections", "defence", "defences", "content", "reason", "measure", "harm", "prejudice")):
        return "richtext"
    if lowered in {"parties", "parties_signatures", "payment_method_details", "requested_documents_or_records", "privacy_consents", "attachments_numbering", "parties_addresses_or_pec", "interested_third_parties", "appellees"}:
        return "textarea"
    return "text"


def _placeholder_for(label: str, field_type: str) -> str:
    lowered = _placeholder_label(label)
    if field_type in {"select", "date"}:
        return f"Seleziona {lowered}"
    if field_type in {"multiselect", "repeater"}:
        return f"Indica {lowered}, uno per riga"
    return f"Inserisci {lowered}"


def _placeholder_label(label: str) -> str:
    if not label:
        return "valore"
    words: list[str] = []
    for word in label.split():
        normalized = word.replace(".", "").replace("/", "")
        if normalized and normalized.isupper():
            words.append(word)
        else:
            words.append(word.lower())
    return " ".join(words) if words else "valore"


AREA_DEFAULT_SECTIONS: dict[str, list[str]] = {
    "STRAGIUDIZIALE": ["intestazione", "parti", "oggetto", "premessa", "richiesta_finale", "allegati", "firma"],
    "CIVILE": ["intestazione", "parti", "fatto", "diritto", "conclusioni", "allegati", "firma"],
    "PENALE": ["intestazione", "autorita", "posizione_difensiva", "richieste", "allegati", "firma"],
    "AMMINISTRATIVO": ["intestazione", "parti", "fatti", "motivi", "domanda_cautelare", "conclusioni", "allegati", "firma"],
    "TRIBUTARIO": ["intestazione", "parti", "atto_impugnato", "motivi", "domanda_cautelare", "conclusioni", "allegati", "firma"],
}

MODEL_SECTION_OVERRIDES: dict[str, list[str]] = {
    "STR_DIFF_001": ["intestazione", "parti", "oggetto", "premessa", "diffida", "avvertimento_finale", "allegati", "firma"],
    "CIV_CIT_001": ["intestazione", "parti", "fatto", "diritto", "vocatio_in_ius", "avvertimenti_rito", "conclusioni", "fase_istruttoria", "dichiarazione_valore", "firma"],
    "CIV_RDI_001": ["intestazione", "ricorrente", "debitore", "credito", "prova_scritta", "richieste", "provvisoria_esecutorieta", "allegati", "firma"],
    "CIV_COM_001": ["intestazione", "parti", "posizione_sui_fatti", "eccezioni_processuali", "eccezioni_di_merito", "domande", "mezzi_istruttori", "conclusioni", "firma"],
}

MODEL_RENDERER_OVERRIDES: dict[str, str] = {
    "STR_DIFF_001": "extrajudicial_notice_v1",
    "CIV_CIT_001": "civil_citation_v1",
}

MODEL_PREFILL_MAP_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "STR_DIFF_001": {
        "sender": ["cliente.nome_completo", "fascicolo.nome_cliente"],
        "recipient": ["fascicolo.controparte"],
        "subject": ["fascicolo.oggetto", "fascicolo.titolo"],
        "breach_description": ["fascicolo.note"],
        "attachments_list": ["fascicolo.documenti[].nome"],
        "signature": ["utente.nome_completo", "config.STUDIO_AVVOCATO"],
    },
    "CIV_CIT_001": {
        "court_name": ["fascicolo.tribunale"],
        "plaintiff": ["cliente.nome_completo", "fascicolo.nome_cliente"],
        "defendant": ["fascicolo.controparte"],
        "lawyer": ["utente.nome_completo", "config.STUDIO_AVVOCATO"],
        "lawyer_tax_code": ["config.STUDIO_CF"],
        "lawyer_pec": ["config.SMTP_FROM", "config.PCT_STUDIO_PEC"],
        "claim_subject": ["fascicolo.oggetto", "fascicolo.titolo"],
        "facts": ["fascicolo.note"],
        "documents_offered": ["fascicolo.documenti[].nome"],
        "hearing_date": ["fascicolo.data_prossima_udienza", "fascicolo.data_prima_udienza"],
    },
    "CIV_RDI_001": {
        "competent_court": ["fascicolo.tribunale"],
        "claimant": ["cliente.nome_completo", "fascicolo.nome_cliente"],
        "debtor": ["fascicolo.controparte"],
        "credit_source": ["fascicolo.oggetto", "fascicolo.titolo"],
        "requested_amount": ["fascicolo.valore_causa"],
        "written_evidence": ["fascicolo.note"],
        "requested_costs": ["config.SPESE_MONITORIO"],
    },
    "CIV_COM_001": {
        "court_name": ["fascicolo.tribunale"],
        "proceeding_number": ["fascicolo.rg_completo", "fascicolo.numero"],
        "defendant": ["cliente.nome_completo", "fascicolo.nome_cliente"],
        "plaintiff": ["fascicolo.controparte"],
        "lawyer_tax_code": ["config.STUDIO_CF"],
        "lawyer_pec": ["config.SMTP_FROM", "config.PCT_STUDIO_PEC"],
        "documents_offered": ["fascicolo.documenti[].nome"],
    },
}

MODEL_SUGGESTED_ATTACHMENTS_OVERRIDES: dict[str, list[str]] = {
    "STR_DIFF_001": [
        "Contratto, ordine, incarico o rapporto da cui nasce l'obbligazione.",
        "Diffide o solleciti precedenti e prova della loro trasmissione.",
    ],
    "CIV_CIT_001": [
        "Procura alle liti firmata e documento di identita del cliente, se previsto dal flusso di studio.",
        "Titolo o rapporto contrattuale, fatture, estratti conto, corrispondenza e diffide stragiudiziali richiamate nell'atto.",
    ],
    "CIV_RDI_001": [
        "Prova scritta del credito: contratto, fatture, DDT, estratto autentico o riconoscimento del debito.",
        "Documentazione sulla scadenza del credito e sugli interessi richiesti.",
    ],
}

MODEL_SUGGESTED_CLAUSES_OVERRIDES: dict[str, list[str]] = {
    "STR_DIFF_001": [
        "Formula conclusiva di riserva di ogni diritto, azione ed eccezione in caso di mancato adempimento.",
    ],
    "CIV_CIT_001": [
        "Vocatio in ius coerente con il termine a comparire e con la data effettivamente fissata.",
        "Avvertimenti di rito coordinati con artt. 163-bis e 166 c.p.c. e con il tipo di giudizio instaurato.",
    ],
    "CIV_RDI_001": [
        "Richiesta espressa di emissione del decreto ingiuntivo e, se del caso, di concessione della provvisoria esecutorieta.",
    ],
}


def _build_validation_rules_for_fields(field_names: Iterable[str]) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for name in field_names:
        field = _field_meta(name)
        rules.append({"field": field["name"], "rule": "required", "message": f"{field['label']} obbligatorio."})
        if field["type"] == "email":
            rules.append({"field": field["name"], "rule": "email", "message": f"{field['label']} deve essere un indirizzo valido."})
        elif field["type"] == "date":
            rules.append({"field": field["name"], "rule": "date", "message": f"{field['label']} deve essere una data valida."})
        elif field["type"] == "number":
            rules.append({"field": field["name"], "rule": "number", "message": f"{field['label']} deve essere numerico."})
    return rules


def _base_suggested_attachments(area: str, required_extra_fields: list[str]) -> list[str]:
    base = [
        "Procura alle liti o incarico, se rilevante per l'atto.",
        "Documenti richiamati nei fatti e nelle conclusioni.",
        "Corrispondenza o ricevute PEC utili a provare notifiche, diffide o comunicazioni.",
    ]
    area_specific = {
        "STRAGIUDIZIALE": [
            "Contratti, ordini, preventivi o lettere di incarico collegati al rapporto.",
            "Prova dell'inadempimento o del credito: fatture, estratti conto, solleciti precedenti.",
        ],
        "CIVILE": [
            "Documenti prodotti in giudizio o da produrre con l'atto.",
            "Ricevute di notifica, relata, attestazioni di conformita e prova del contributo unificato se dovuti.",
        ],
        "PENALE": [
            "Nomina, elezione di domicilio, verbali o provvedimenti richiamati.",
            "Documentazione difensiva e allegati a sostegno delle richieste.",
        ],
        "AMMINISTRATIVO": [
            "Provvedimento impugnato e prova della sua comunicazione o piena conoscenza.",
            "Documentazione amministrativa e allegati richiamati a fondamento della domanda cautelare o di merito.",
        ],
        "TRIBUTARIO": [
            "Atto tributario impugnato e prova della notifica.",
            "Documentazione contabile, fiscale e amministrativa richiamata nel ricorso o nelle difese.",
        ],
    }
    extra = list(area_specific.get(area, []))
    if "documents_offered" in required_extra_fields or "documents_list_detailed" in required_extra_fields:
        extra.append("Indice allegati con numerazione coerente tra atto e fascicolo.")
    return _dedupe_preserve(base + extra)


def _base_suggested_clauses(model_code: str, area: str) -> list[str]:
    base = [
        "Formula finale su luogo, data e sottoscrizione.",
        "Richiamo coerente agli allegati effettivamente indicati nell'atto.",
    ]
    area_specific = {
        "STRAGIUDIZIALE": ["Riserva di ogni diritto, azione ed eccezione.", "Termine finale espresso e conseguenze del mancato adempimento."],
        "CIVILE": ["Conclusioni finali allineate ai fatti e ai motivi in diritto.", "Indicazione dei mezzi di prova e dei documenti prodotti."],
        "PENALE": ["Richiamo alla qualita del difensore e alla posizione dell'assistito.", "Formula di deposito o istanza rivolta all'autorita procedente competente."],
        "AMMINISTRATIVO": ["Indicazione della misura cautelare, se richiesta.", "Conclusioni con annullamento, riforma o altra tutela richiesta."],
        "TRIBUTARIO": ["Indicazione del valore della controversia e del domicilio digitale, ove rilevanti.", "Conclusioni finali su annullamento, sospensione e spese."],
    }
    extra = list(area_specific.get(area, []))
    if model_code.endswith("DEPDOC_001"):
        base.append("Numerazione allegati e finalita del deposito in forma sintetica e coerente.")
    return _dedupe_preserve(base + extra)


def _guidance_from_sources(model: dict[str, Any]) -> dict[str, Any]:
    area_guidance = AREA_PRO_GUIDANCE.get(model["area"], {})
    specific = MODEL_GUIDANCE_OVERRIDES.get(model["code"], {})
    return {
        "summary": specific.get("summary") or area_guidance.get("summary") or model["name"],
        "when_to_use": list(specific.get("when_to_use") or area_guidance.get("when_to_use") or []),
        "structure": list(specific.get("structure") or area_guidance.get("structure") or []),
        "technical_notes": list(specific.get("technical_notes") or area_guidance.get("technical_notes") or []),
        "references": list(specific.get("references") or area_guidance.get("references") or []),
    }


def _build_model_schema(model: dict[str, Any]) -> dict[str, Any]:
    guidance = _guidance_from_sources(model)
    required_extra_fields = list(model["required_extra_fields"])
    field_names = BASE_REQUIRED_FIELDS + required_extra_fields
    return {
        **model,
        "summary": guidance["summary"],
        "when_to_use": list(guidance["when_to_use"]),
        "structure": list(guidance["structure"]),
        "technical_notes": list(guidance["technical_notes"]),
        "legal_references": list(guidance["references"]),
        "sections": list(MODEL_SECTION_OVERRIDES.get(model["code"], AREA_DEFAULT_SECTIONS.get(model["area"], []))),
        "renderer": MODEL_RENDERER_OVERRIDES.get(model["code"], "generic_professional_v1"),
        "prefill_map": copy.deepcopy(MODEL_PREFILL_MAP_OVERRIDES.get(model["code"], {})),
        "validation_rules": _build_validation_rules_for_fields(field_names),
        "suggested_attachments": _dedupe_preserve(
            _base_suggested_attachments(model["area"], required_extra_fields)
            + MODEL_SUGGESTED_ATTACHMENTS_OVERRIDES.get(model["code"], [])
        ),
        "suggested_clauses": _dedupe_preserve(
            _base_suggested_clauses(model["code"], model["area"])
            + MODEL_SUGGESTED_CLAUSES_OVERRIDES.get(model["code"], [])
        ),
    }


def _build_compiler_schema() -> dict[str, Any]:
    names = set(BASE_REQUIRED_FIELDS)
    for model in MODELS:
        names.update(model["required_extra_fields"])
    field_catalog = {name: _field_meta(name) for name in sorted(names)}
    models = [_build_model_schema(model) for model in MODELS]
    return {
        "field_catalog": field_catalog,
        "base_required_fields": list(BASE_REQUIRED_FIELDS),
        "models": models,
    }


def _field_schema(name: str) -> dict[str, Any]:
    return copy.deepcopy(FIELD_CATALOG.get(name) or _field_meta(name))


def elenco_modelli() -> list[dict[str, Any]]:
    return [copy.deepcopy(model) for model in MODELS]


def modelli_per_area() -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    for area in AREA_ORDINE:
        models = [copy.deepcopy(m) for m in MODELS if m["area"] == area]
        if models:
            grouped.append({"area": area, "label": AREA_LABELS.get(area, area.title()), "models": models})
    return grouped


def get_modello(model_code: str) -> Optional[dict[str, Any]]:
    model = MODEL_INDEX.get(model_code)
    return copy.deepcopy(model) if model else None


def campi_catalogo() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(FIELD_CATALOG)


def campi_modello(model_code: str) -> list[dict[str, Any]]:
    model = _require_model(model_code)
    fields = BASE_REQUIRED_FIELDS + model["required_extra_fields"]
    return [_field_schema(name) for name in fields]


def campi_base_visibili() -> list[dict[str, Any]]:
    return [_field_schema(name) for name in BASE_REQUIRED_FIELDS if name not in HIDDEN_BASE_FIELDS]


def campi_extra_modello(model_code: str) -> list[dict[str, Any]]:
    model = _require_model(model_code)
    return [_field_schema(name) for name in model["required_extra_fields"]]


def model_options() -> list[tuple[str, str]]:
    return [(m["code"], m["name"]) for m in MODELS]


def area_options() -> list[tuple[str, str]]:
    return [(key, AREA_LABELS[key]) for key in AREA_ORDINE]


def catalogo_compilatore() -> dict[str, Any]:
    return copy.deepcopy(COMPILER_SCHEMA)


def wizard_schema_modello(model_code: str) -> dict[str, Any]:
    model = _require_model(model_code)
    return {
        "model": copy.deepcopy(model),
        "field_catalog": copy.deepcopy(FIELD_CATALOG),
        "base_required_fields": list(BASE_REQUIRED_FIELDS),
        "base_fields": campi_base_visibili(),
        "extra_fields": campi_extra_modello(model_code),
        "guidance": professional_guidance_for_model(model_code),
        "validation_rules": validation_rules_for_model(model_code),
        "suggested_attachments": suggested_attachments_for_model(model_code),
        "suggested_clauses": suggested_clauses_for_model(model_code),
        "sections": list(model.get("sections", [])),
        "renderer": model.get("renderer", "generic_professional_v1"),
        "prefill_map": copy.deepcopy(model.get("prefill_map", {})),
    }


def professional_guidance_for_model(model_code: str) -> dict[str, Any]:
    model = _require_model(model_code)
    return {
        "summary": model.get("summary") or _guidance_from_sources(model)["summary"] or model["name"],
        "when_to_use": list(model.get("when_to_use", _guidance_from_sources(model)["when_to_use"])),
        "structure": list(model.get("structure", _guidance_from_sources(model)["structure"])),
        "technical_notes": list(model.get("technical_notes", _guidance_from_sources(model)["technical_notes"])),
        "references": list(model.get("legal_references", _guidance_from_sources(model)["references"])),
    }


def validation_rules_for_model(model_code: str) -> list[dict[str, str]]:
    model = _require_model(model_code)
    return copy.deepcopy(model.get("validation_rules", []))


def suggested_attachments_for_model(model_code: str) -> list[str]:
    model = _require_model(model_code)
    return list(model.get("suggested_attachments", []))


def suggested_clauses_for_model(model_code: str) -> list[str]:
    model = _require_model(model_code)
    return list(model.get("suggested_clauses", []))


def opzioni_campo(
    field_name: str,
    *,
    fascicoli: Optional[Iterable[Any]] = None,
    utenti: Optional[Iterable[Any]] = None,
    model: Optional[dict[str, Any]] = None,
) -> list[tuple[str, str]]:
    if field_name == "area":
        return area_options()
    if field_name == "act_type":
        return [(model["name"], model["name"])] if model else model_options()
    if field_name == "case_id":
        result = [("", "- Nessuna pratica -")]
        for fascicolo in fascicoli or []:
            label = getattr(fascicolo, "titolo", "") or getattr(fascicolo, "numero", "")
            rg = getattr(fascicolo, "rg_completo", "")
            if rg:
                label = f"{label} - {rg}"
            result.append((getattr(fascicolo, "id", ""), label))
        return result
    if field_name == "matter":
        return [("STRAGIUDIZIALE", "Stragiudiziale"), ("CIVILE", "Civile"), ("PENALE", "Penale"), ("AMMINISTRATIVO", "Amministrativo"), ("TRIBUTARIO", "Tributario"), ("ALTRO", "Altro")]
    if field_name == "author_user_id":
        return [(getattr(utente, "id", ""), getattr(utente, "nome_completo", "") or getattr(utente, "username", "")) for utente in utenti or []]
    if field_name == "status":
        return STATUS_OPTIONS
    return []


def prefill_payload(
    model_code: str,
    *,
    fascicolo: Any = None,
    cliente: Any = None,
    utente: Any = None,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    model = _require_model(model_code)
    config = config or {}
    documenti = getattr(fascicolo, "documenti", []) if fascicolo else []
    allegati = [getattr(doc, "nome", "") for doc in documenti if getattr(doc, "nome", "")]
    lawyer_name = _first_non_empty(getattr(utente, "nome_completo", ""), getattr(utente, "username", ""), config.get("STUDIO_AVVOCATO", ""), config.get("STUDIO_NOME", ""))
    lawyer_id = _first_non_empty(getattr(utente, "id", ""), getattr(utente, "username", ""))
    lawyer_pec = _first_non_empty(config.get("SMTP_FROM", ""), config.get("PCT_STUDIO_PEC", ""))
    lawyer_cf = _first_non_empty(config.get("STUDIO_CF", ""))
    payload: dict[str, Any] = {
        "model_code": model["code"],
        "title": model["name"],
        "area": model["area"],
        "act_type": model["name"],
        "case_id": getattr(fascicolo, "id", ""),
        "case_reference_display": _first_non_empty(getattr(fascicolo, "rg_completo", ""), getattr(fascicolo, "titolo", ""), getattr(fascicolo, "numero", "")),
        "matter": _first_non_empty(getattr(getattr(fascicolo, "tipo", None), "value", ""), model["area"]),
        "recipient_or_court": _first_non_empty(getattr(fascicolo, "tribunale", ""), ""),
        "client_or_sender": _resolve_cliente_label(cliente, fascicolo),
        "counterparty_or_recipient": _first_non_empty(getattr(fascicolo, "controparte", ""), ""),
        "lawyer": lawyer_name,
        "subject": _first_non_empty(getattr(fascicolo, "oggetto", ""), getattr(fascicolo, "titolo", ""), model["name"]),
        "facts": _first_non_empty(getattr(fascicolo, "note", ""), ""),
        "requests_or_conclusions": "",
        "place": config.get("STUDIO_INDIRIZZO", ""),
        "document_date": date.today().isoformat(),
        "signature": lawyer_name,
        "attachments_list": allegati,
        "author_user_id": lawyer_id,
        "version": "1.0",
        "status": "BOZZA",
        "_client_tax_id": _resolve_cliente_tax_id(cliente),
        "_client_address": _resolve_cliente_address(cliente),
        "_counterparty_tax_id": _resolve_controparte_tax_id(fascicolo),
        "_counterparty_address": _resolve_controparte_address(fascicolo),
        "_lawyer_tax_id": lawyer_cf,
        "_lawyer_pec": lawyer_pec,
        "_studio_address": _first_non_empty(config.get("STUDIO_INDIRIZZO", "")),
        "_court_heading": _resolve_court_heading(fascicolo),
    }
    for field_name in model["required_extra_fields"]:
        payload[field_name] = _prefill_extra_field(field_name, fascicolo=fascicolo, cliente=cliente, utente=utente, config=config, allegati=allegati)
    return payload


def merge_payload_with_form(model_code: str, *, initial_payload: dict[str, Any], form_data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(initial_payload)
    for field in campi_modello(model_code):
        name = field["name"]
        if name in form_data:
            payload[name] = _normalize_form_value(form_data[name], field["type"])
    return payload


def validate_payload(model_code: str, payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field in campi_modello(model_code):
        name = field["name"]
        value = payload.get(name)
        if _is_empty_value(value):
            errors[name] = f"{field['label']} obbligatorio."
            continue
        if field["type"] == "email" and "@" not in str(value):
            errors[name] = f"{field['label']} deve essere un indirizzo valido."
        elif field["type"] == "number":
            try:
                float(str(value).replace(",", "."))
            except ValueError:
                errors[name] = f"{field['label']} deve essere numerico."
        elif field["type"] == "date":
            try:
                date.fromisoformat(str(value))
            except ValueError:
                errors[name] = f"{field['label']} deve essere una data valida."
    return errors


def render_compiled_act(model_code: str, payload: dict[str, Any]) -> str:
    model = _require_model(model_code)
    renderers = {
        "civil_citation_v1": _render_civ_cit_001,
        "extrajudicial_notice_v1": _render_str_diff_001,
        "generic_professional_v1": _render_generic_professional_act,
    }
    renderer = renderers.get(model.get("renderer", "generic_professional_v1"), _render_generic_professional_act)
    return renderer(model, payload).strip()


def _prefill_extra_field(field_name: str, *, fascicolo: Any = None, cliente: Any = None, utente: Any = None, config: Optional[dict[str, Any]] = None, allegati: Optional[list[str]] = None) -> Any:
    config = config or {}
    lawyer_name = _first_non_empty(getattr(utente, "nome_completo", ""), getattr(utente, "username", ""), config.get("STUDIO_AVVOCATO", ""))
    lawyer_pec = _first_non_empty(config.get("SMTP_FROM", ""), config.get("PCT_STUDIO_PEC", ""))
    if field_name == "court_name":
        return _resolve_court_heading(fascicolo)
    if field_name in FIELD_ALIASES_BY_ROLE["cliente"]:
        return _resolve_cliente_label(cliente, fascicolo)
    if field_name in FIELD_ALIASES_BY_ROLE["controparte"]:
        return _resolve_controparte_label(fascicolo)
    if field_name in FIELD_ALIASES_BY_ROLE["ufficio"]:
        return _resolve_ufficio_label(fascicolo)
    if field_name in FIELD_ALIASES_BY_ROLE["riferimento"]:
        return _resolve_riferimento_procedimento(fascicolo)
    if field_name == "lawyer_tax_code":
        return _first_non_empty(config.get("STUDIO_CF", ""), "")
    if field_name in {"lawyer_pec", "defender_pec", "digital_domicile_or_pec"}:
        return lawyer_pec
    if field_name in {"appointed_defender", "professional"}:
        return lawyer_name
    if field_name == "defender_bar_association":
        return config.get("STUDIO_NOME", "")
    if field_name == "appearance_notice":
        return (
            "con l'invito a costituirsi nel termine di settanta giorni prima dell'udienza indicata, "
            "ai sensi e nelle forme dell'art. 166 c.p.c., e a comparire nell'udienza fissata dinanzi al giudice designato"
        )
    if field_name == "ritual_warnings":
        return (
            "La costituzione oltre i suddetti termini implica le decadenze di cui agli artt. 38 e 167 c.p.c.\n"
            "La difesa tecnica mediante avvocato e obbligatoria nei giudizi davanti al tribunale, salvo i casi previsti dall'art. 86 c.p.c. o da leggi speciali.\n"
            "La parte, sussistendone i presupposti di legge, puo presentare istanza per l'ammissione al patrocinio a spese dello Stato."
        )
    if field_name in {"case_value", "dispute_value", "requested_amount", "principal_amount", "interest_amount", "costs_amount", "expenses", "cpa_amount", "vat_amount", "total_amount"}:
        value = getattr(fascicolo, "valore_causa", 0) if fascicolo else 0
        return value or ""
    if field_name in {"claim_subject", "dispute_subject", "request_subject", "memo_subject", "assignment_object", "professional_activity_object", "credit_reason", "challenged_tax_act", "challenged_administrative_act", "challenged_measure", "appealed_judgment", "seized_asset"}:
        return _first_non_empty(getattr(fascicolo, "oggetto", ""), getattr(fascicolo, "titolo", ""))
    if field_name == "hearing_date":
        return _first_non_empty(getattr(fascicolo, "data_prossima_udienza", ""), getattr(fascicolo, "data_prima_udienza", ""))
    if field_name in {"documents_offered", "supporting_documents", "supporting_attachments", "essential_attachments", "attachments_list", "documents_list_detailed"}:
        return list(allegati or [])
    return ""


def _resolve_cliente_label(cliente: Any, fascicolo: Any) -> str:
    if cliente is not None:
        return _first_non_empty(getattr(cliente, "nome_completo", ""), "")
    return _first_non_empty(getattr(fascicolo, "nome_cliente", ""), "")


def _resolve_controparte_label(fascicolo: Any) -> str:
    return _first_non_empty(getattr(fascicolo, "controparte", ""), "")


def _resolve_ufficio_label(fascicolo: Any) -> str:
    parts = [getattr(fascicolo, "tribunale", ""), getattr(fascicolo, "sezione", ""), getattr(fascicolo, "giudice", "")]
    return " - ".join([part for part in parts if part])


def _resolve_riferimento_procedimento(fascicolo: Any) -> str:
    return _first_non_empty(getattr(fascicolo, "rg_completo", ""), getattr(fascicolo, "numero", ""))


def _normalize_form_value(value: Any, field_type: str) -> Any:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if field_type in {"multiselect", "repeater"}:
        return [line.strip() for line in str(value).replace("\r", "").split("\n") if line.strip()]
    return str(value).strip()


def _render_field_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [f"- {item}" for item in value] if value else ["-"]
    if _is_empty_value(value):
        return ["-"]
    return str(value).splitlines() or ["-"]


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join([str(item) for item in value if str(item).strip()]) or "-"
    if _is_empty_value(value):
        return "-"
    return str(value)


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    return str(value).strip() == ""


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if hasattr(value, "value"):
            value = getattr(value, "value")
        text = str(value).strip()
        if text:
            return text
    return ""


def _dedupe_preserve(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


COMPILER_SCHEMA = _build_compiler_schema()
FIELD_CATALOG = COMPILER_SCHEMA["field_catalog"]
MODELS = COMPILER_SCHEMA["models"]
MODEL_INDEX = {model["code"]: model for model in MODELS}


def _render_generic_professional_act(model: dict[str, Any], payload: dict[str, Any]) -> str:
    heading = _first_non_empty(payload.get("_court_heading"), payload.get("recipient_or_court"), payload.get("court_name"))
    title = payload.get("title") or model["name"]
    lines: list[str] = []

    if heading:
        lines.append(heading.upper())
    lines.append(title)
    lines.append("")

    if model["area"] == "STRAGIUDIZIALE":
        lines.extend(
            [
                f"Mittente: {_display_value(payload.get('client_or_sender'))}",
                f"Destinatario: {_display_value(payload.get('counterparty_or_recipient') or payload.get('recipient_or_court'))}",
            ]
        )
    elif model["area"] == "PENALE":
        lines.extend(
            [
                f"Assistito: {_display_value(payload.get('client_or_sender'))}",
                f"Autorita procedente: {_display_value(payload.get('recipient_or_court'))}",
                f"Difensore: {_display_value(payload.get('lawyer'))}",
            ]
        )
    else:
        lines.extend(
            [
                f"Parte assistita: {_display_value(payload.get('client_or_sender'))}",
                f"Controparte: {_display_value(payload.get('counterparty_or_recipient'))}",
                f"Difensore: {_display_value(payload.get('lawyer'))}",
            ]
        )

    if payload.get("case_reference_display"):
        lines.append(f"Riferimento pratica: {payload.get('case_reference_display')}")

    _append_section(lines, "OGGETTO", _render_text_block_lines(payload.get("subject")))
    _append_section(lines, "PREMESSA IN FATTO", _render_text_block_lines(payload.get("facts")))
    _append_section(lines, "RICHIESTE / CONCLUSIONI", _render_text_block_lines(payload.get("requests_or_conclusions")))

    extra_fields = campi_extra_modello(model["code"])
    if extra_fields:
        lines.append("")
        lines.append("ELEMENTI SPECIFICI DEL MODELLO")
        for field in extra_fields:
            lines.append("")
            lines.append(field["label"].upper())
            lines.extend(_render_field_value(payload.get(field["name"])))

    if payload.get("attachments_list"):
        _append_section(lines, "ALLEGATI RICHIAMATI", _render_numbered_list(_to_string_list(payload.get("attachments_list"))))

    lines.extend(
        [
            "",
            _render_footer_line(payload),
            "",
            _normalize_lawyer_name(payload.get("signature") or payload.get("lawyer")),
        ]
    )
    return _clean_rendered_lines(lines)


def _render_civ_cit_001(model: dict[str, Any], payload: dict[str, Any]) -> str:
    court_heading = _normalize_court_heading(
        payload.get("court_name") or payload.get("_court_heading") or payload.get("recipient_or_court")
    )
    court_display = _first_non_empty(payload.get("court_name"), payload.get("_court_heading"), payload.get("recipient_or_court"))
    plaintiff = _first_non_empty(payload.get("plaintiff"), payload.get("client_or_sender"))
    defendant = _first_non_empty(payload.get("defendant"), payload.get("counterparty_or_recipient"))
    lawyer = _normalize_lawyer_name(payload.get("lawyer") or payload.get("signature"))
    lawyer_cf = _first_non_empty(payload.get("lawyer_tax_code"), payload.get("_lawyer_tax_id"))
    lawyer_pec = _first_non_empty(payload.get("lawyer_pec"), payload.get("_lawyer_pec"))
    plaintiff_text = _render_citation_actor_block(
        plaintiff,
        payload.get("_client_tax_id"),
        payload.get("_client_address"),
        lawyer,
        lawyer_cf,
        lawyer_pec,
        _first_non_empty(payload.get("_studio_address"), payload.get("place")),
    )
    defendant_text = _render_citation_defendant_block(
        defendant,
        payload.get("_counterparty_tax_id"),
        payload.get("_counterparty_address"),
    )
    evidence_lines: list[str] = []
    evidence_means = _render_text_block_lines(payload.get("evidence_means"))
    evidence_docs = _dedupe_preserve(
        _to_string_list(payload.get("documents_offered")) + _to_string_list(payload.get("attachments_list"))
    )
    if evidence_means and evidence_means != ["-"]:
        evidence_lines.extend(evidence_means)
    if evidence_docs:
        if evidence_lines:
            evidence_lines.append("")
        evidence_lines.append("Si offrono in comunicazione i seguenti documenti:")
        evidence_lines.extend(_render_numbered_list(evidence_docs))

    lines: list[str] = [
        court_heading or _normalize_court_heading(court_display or "Tribunale"),
        "Atto di Citazione",
        "",
        "Per:",
        plaintiff_text,
        "",
        "Contro:",
        defendant_text,
    ]
    _append_section(lines, "FATTO", _render_citation_facts(payload))
    _append_section(lines, "DIRITTO", _render_text_block_lines(payload.get("legal_arguments")))
    lines.extend(
        [
            "",
            "Tutto cio premesso, l'attore come sopra rappresentato e difeso",
            "",
            "CITA",
            (
                f"{defendant} a comparire dinanzi al {court_display or court_heading}, locali di rito, "
                f"all'udienza del {_format_italian_date(payload.get('hearing_date'))}, ore di rito, "
                f"{_normalize_sentence(payload.get('appearance_notice') or '')}."
            ),
        ]
    )
    _append_section(lines, "AVVERTIMENTI DI RITO", _render_bullet_lines(payload.get("ritual_warnings")))
    _append_section(lines, "CONCLUSIONI", _render_text_block_lines(payload.get("requests_or_conclusions")))
    if evidence_lines:
        _append_section(lines, "IN VIA ISTRUTTORIA", evidence_lines)
    case_value = _format_currency(payload.get("case_value"))
    if case_value:
        lines.extend(
            [
                "",
                f"Dichiarazione di valore: ai fini del contributo unificato, il valore della causa e di {case_value}.",
            ]
        )
    lines.extend(["", _render_footer_line(payload), "", lawyer])
    return _clean_rendered_lines(lines)


def _render_str_diff_001(model: dict[str, Any], payload: dict[str, Any]) -> str:
    recipient = _first_non_empty(payload.get("recipient"), payload.get("counterparty_or_recipient"), payload.get("recipient_or_court"))
    sender = _first_non_empty(payload.get("sender"), payload.get("client_or_sender"))
    lawyer = _normalize_lawyer_name(payload.get("lawyer") or payload.get("signature"))
    lines: list[str] = [
        _first_non_empty(payload.get("_studio_address"), payload.get("place")).upper(),
        "Diffida",
        "",
        f"Mittente: {sender}",
        f"Destinatario: {recipient}",
    ]
    _append_section(lines, "OGGETTO", _render_text_block_lines(payload.get("subject")))
    lines.extend(
        [
            "",
            f"Il sottoscritto {lawyer}, nell'interesse di {sender}, espone quanto segue.",
        ]
    )
    _append_section(lines, "PREMESSA", _render_text_block_lines(payload.get("breach_description") or payload.get("facts")))
    deadline = _format_italian_date(payload.get("deadline_assigned"))
    request_lines = _render_text_block_lines(payload.get("specific_request") or payload.get("requests_or_conclusions"))
    if deadline:
        request_lines.append("")
        request_lines.append(f"Si assegna termine fino al {deadline} per l'integrale adempimento.")
    _append_section(lines, "DIFFIDA E INVITO AD ADEMPIERE", request_lines)
    _append_section(lines, "AVVERTIMENTO FINALE", _render_text_block_lines(payload.get("final_warning")))
    if payload.get("attachments_list"):
        _append_section(lines, "ALLEGATI RICHIAMATI", _render_numbered_list(_to_string_list(payload.get("attachments_list"))))
    lines.extend(["", _render_footer_line(payload), "", lawyer])
    return _clean_rendered_lines(lines)


def _append_section(lines: list[str], title: str, body_lines: list[str]) -> None:
    if not body_lines:
        return
    lines.extend(["", title])
    lines.extend(body_lines)


def _render_citation_facts(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if payload.get("claim_subject"):
        claim_subject = str(payload.get("claim_subject")).strip()
        if claim_subject.endswith("."):
            lines.append(f"La presente domanda ha ad oggetto: {claim_subject}")
        else:
            lines.append(f"La presente domanda ha ad oggetto: {claim_subject}.")
        lines.append("")
    lines.extend(_render_text_block_lines(payload.get("facts")))
    return lines


def _render_citation_actor_block(
    plaintiff: str,
    plaintiff_tax_id: Any,
    plaintiff_address: Any,
    lawyer: str,
    lawyer_cf: str,
    lawyer_pec: str,
    studio_address: str,
) -> str:
    parts = [plaintiff]
    if _first_non_empty(plaintiff_tax_id):
        parts.append(f"(C.F. {_first_non_empty(plaintiff_tax_id)})")
    if _first_non_empty(plaintiff_address):
        parts.append(f"residente/con sede in {_first_non_empty(plaintiff_address)}")
    base = ", ".join(parts)
    difesa = f"rappresentato e difeso da {lawyer}"
    if lawyer_cf:
        difesa += f" (C.F. {lawyer_cf})"
    if studio_address:
        difesa += f", ed elettivamente domiciliato presso il suo studio in {studio_address}"
    difesa += ", come da procura alle liti."
    if lawyer_pec:
        difesa += f" Dichiara domicilio digitale all'indirizzo PEC {lawyer_pec}."
    return f"{base}, {difesa}"


def _render_citation_defendant_block(defendant: str, defendant_tax_id: Any, defendant_address: Any) -> str:
    parts = [defendant]
    if _first_non_empty(defendant_tax_id):
        parts.append(f"(C.F./P.IVA {_first_non_empty(defendant_tax_id)})")
    if _first_non_empty(defendant_address):
        parts.append(f"residente/con sede in {_first_non_empty(defendant_address)}")
    return ", ".join(parts) + "."


def _render_footer_line(payload: dict[str, Any]) -> str:
    place = _first_non_empty(payload.get("place"), payload.get("_studio_address"), "Luogo da completare")
    return f"{place}, {_format_italian_date(payload.get('document_date'))}"


def _render_text_block_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if _is_empty_value(value):
        return ["-"]
    return [line.strip() for line in str(value).replace("\r", "").split("\n") if line.strip()] or ["-"]


def _render_bullet_lines(value: Any) -> list[str]:
    return [f"- {line}" for line in _render_text_block_lines(value) if line != "-"] or ["-"]


def _render_numbered_list(items: list[str]) -> list[str]:
    return [f"{idx}. {item}" for idx, item in enumerate(items, start=1)]


def _to_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if _is_empty_value(value):
        return []
    return [str(value).strip()]


def _clean_rendered_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        current = str(line).rstrip()
        is_blank = current.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(current)
        prev_blank = is_blank
    return "\n".join(cleaned).strip()


def _format_italian_date(value: Any) -> str:
    if _is_empty_value(value):
        return date.today().strftime("%d/%m/%Y")
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return text


def _format_currency(value: Any) -> str:
    if _is_empty_value(value):
        return ""
    try:
        text = str(value).strip()
        if "," in text and "." in text:
            normalized = text.replace(".", "").replace(",", ".")
        elif "," in text:
            normalized = text.replace(",", ".")
        else:
            normalized = text
        amount = float(normalized)
    except ValueError:
        return str(value)
    formatted = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"Euro {formatted}"


def _normalize_lawyer_name(value: Any) -> str:
    text = _first_non_empty(value)
    if not text:
        return "Avv. __________________"
    lowered = text.lower()
    if lowered.startswith("avv.") or lowered.startswith("avv "):
        return text
    return f"Avv. {text}"


def _normalize_sentence(value: Any) -> str:
    text = _first_non_empty(value)
    if not text:
        return "con l'invito a costituirsi nel termine di legge"
    return text[:-1] if text.endswith(".") else text


def _normalize_court_heading(value: Any) -> str:
    text = _first_non_empty(value)
    if not text:
        return "TRIBUNALE"
    return text.split(" - ")[0].strip().upper()


def _resolve_cliente_tax_id(cliente: Any) -> str:
    return _first_non_empty(
        getattr(cliente, "codice_fiscale", ""),
        getattr(cliente, "partita_iva", ""),
        getattr(cliente, "identificativo_fiscale", ""),
    )


def _resolve_cliente_address(cliente: Any) -> str:
    if not cliente:
        return ""
    for attr in ("indirizzo_domicilio", "indirizzo_residenza", "indirizzo_sede_legale", "indirizzo"):
        value = getattr(cliente, attr, None)
        text = _first_non_empty(value)
        if text:
            return text
    return ""


def _resolve_controparte_tax_id(fascicolo: Any) -> str:
    if not fascicolo:
        return ""
    return _first_non_empty(
        getattr(fascicolo, "codice_fiscale_controparte", ""),
        getattr(fascicolo, "cf_controparte", ""),
        getattr(fascicolo, "controparte_codice_fiscale", ""),
    )


def _resolve_controparte_address(fascicolo: Any) -> str:
    if not fascicolo:
        return ""
    return _first_non_empty(
        getattr(fascicolo, "indirizzo_controparte", ""),
        getattr(fascicolo, "controparte_indirizzo", ""),
    )


def _resolve_court_heading(fascicolo: Any) -> str:
    if not fascicolo:
        return ""
    return _first_non_empty(getattr(fascicolo, "tribunale", "")).split(" - ")[0].strip()


def _require_model(model_code: str) -> dict[str, Any]:
    model = get_modello(model_code)
    if not model:
        raise ValueError(f"Modello '{model_code}' non trovato.")
    return model
