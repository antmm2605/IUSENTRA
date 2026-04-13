"""Binding tra modelli built-in del workspace atti e compilatore guidato."""
from __future__ import annotations

from typing import Any


def _binding(
    title: str,
    compiler_code: str,
    base_code: str,
    *,
    area: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "compiler_code": compiler_code,
        "base_code": base_code,
        "area": area,
    }


BUILTIN_COMPILER_BINDINGS: list[dict[str, Any]] = [
    # Procure, nomine e deleghe
    _binding("Procura alle liti", "CIV_PROC_001", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Procura generale alle liti", "CIV_PROC_002", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Procura speciale per ricorso monitorio", "CIV_PROC_003", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Procura speciale per appello", "CIV_PROC_004", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Procura speciale per ricorso per cassazione", "CIV_PROC_005", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Procura per fase esecutiva", "CIV_PROC_006", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Nomina domiciliatario", "CIV_PROC_007", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Revoca del mandato difensivo", "CIV_PROC_008", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Rinuncia al mandato", "CIV_PROC_009", "CIV_PROCBASE_001", area="CIVILE"),
    _binding("Elezione di domicilio", "CIV_PROC_010", "CIV_PROCBASE_001", area="CIVILE"),
    # UNEP e notificazioni
    _binding("Atto UNEP", "CIV_NOT_001", "CIV_NOTIFBASE_001", area="CIVILE"),
    _binding("Atto per notificazione in proprio", "CIV_NOT_002", "CIV_NOTIFBASE_001", area="CIVILE"),
    _binding("Relata di notifica PEC", "CIV_NOT_003", "CIV_NOTIFBASE_001", area="CIVILE"),
    _binding("Deposito telematico documenti", "CIV_NOT_004", "CIV_DEPDOC_001", area="CIVILE"),
    _binding("Visibilita fascicolo telematico", "CIV_NOT_005", "CIV_NOTIFBASE_001", area="CIVILE"),
    _binding("Fascicolo di parte", "CIV_NOT_006", "CIV_DEPDOC_001", area="CIVILE"),
    _binding("Attestazione di conformita", "CIV_NOT_007", "CIV_NOTIFBASE_001", area="CIVILE"),
    _binding("Indice allegati", "CIV_NOT_008", "CIV_DEPDOC_001", area="CIVILE"),
    _binding("Note iscrizione ruolo", "CIV_NOT_009", "CIV_DEPDOC_001", area="CIVILE"),
    # Stragiudiziale collegato
    _binding("Diffida stragiudiziale collegata al fascicolo", "STR_BLT_001", "STR_DIFF_001", area="STRAGIUDIZIALE"),
    _binding("Sollecito di pagamento", "STR_BLT_002", "STR_SOLL_001", area="STRAGIUDIZIALE"),
    _binding("Lettera adeguamento canone locazione", "STR_BLT_003", "STR_COM_001", area="STRAGIUDIZIALE"),
    _binding("Diffida ad adempiere", "STR_BLT_004", "STR_INVAD_001", area="STRAGIUDIZIALE"),
    _binding("Richiesta di documentazione", "STR_BLT_005", "STR_COM_001", area="STRAGIUDIZIALE"),
    _binding("Comunicazione di riserva diritti", "STR_BLT_006", "STR_COM_001", area="STRAGIUDIZIALE"),
    _binding("Invito a negoziazione assistita", "STR_BLT_007", "STR_COM_001", area="STRAGIUDIZIALE"),
    _binding("Atto di messa in mora", "STR_BLT_008", "STR_MM_001", area="STRAGIUDIZIALE"),
    # Civile introduttivo / cautelare
    _binding("Ricorso ex art. 702-bis / rito semplificato", "CIV_INT_001", "CIV_CIT_001", area="CIVILE"),
    _binding("Riassunzione del giudizio", "CIV_INT_002", "CIV_CIT_001", area="CIVILE"),
    _binding("Reclamo cautelare", "CIV_INT_003", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Ricorso per sequestro conservativo", "CIV_INT_004", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Ricorso per sequestro giudiziario", "CIV_INT_005", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Denuncia di nuova opera", "CIV_INT_006", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Denuncia di danno temuto", "CIV_INT_007", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Azione di manutenzione nel possesso", "CIV_INT_008", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Azione di reintegrazione nel possesso", "CIV_INT_009", "CIV_RCAUT_001", area="CIVILE"),
    _binding("Ricorso per accertamento tecnico preventivo", "CIV_INT_010", "CIV_RCAUT_001", area="CIVILE"),
    # Civile endoprocessuale
    _binding("Memoria n. 1", "CIV_SUC_001", "CIV_MEM_001", area="CIVILE"),
    _binding("Memoria n. 2", "CIV_SUC_002", "CIV_MEM_001", area="CIVILE"),
    _binding("Memoria n. 3", "CIV_SUC_003", "CIV_MEM_001", area="CIVILE"),
    _binding("Memoria istruttoria", "CIV_SUC_004", "CIV_MEM_001", area="CIVILE"),
    _binding("Istanza di rinvio", "CIV_SUC_005", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di trattazione scritta", "CIV_SUC_006", "CIV_IST_001", area="CIVILE"),
    _binding("Note d'udienza", "CIV_SUC_007", "CIV_MEM_001", area="CIVILE"),
    _binding("Note conclusive", "CIV_SUC_008", "CIV_CONCL_001", area="CIVILE"),
    _binding("Istanza di anticipazione udienza", "CIV_SUC_009", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di riunione procedimenti", "CIV_SUC_010", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di separazione procedimenti", "CIV_SUC_011", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di provvisoria esecuzione", "CIV_SUC_012", "CIV_IST_001", area="CIVILE"),
    # Impugnazioni civili
    _binding("Comparsa di costituzione in appello", "CIV_IMP_001", "CIV_COM_001", area="CIVILE"),
    _binding("Ricorso per cassazione", "CIV_IMP_002", "CIV_APP_001", area="CIVILE"),
    _binding("Controricorso", "CIV_IMP_003", "CIV_APP_001", area="CIVILE"),
    _binding("Ricorso per revocazione", "CIV_IMP_004", "CIV_APP_001", area="CIVILE"),
    _binding("Opposizione di terzo", "CIV_IMP_005", "CIV_APP_001", area="CIVILE"),
    _binding("Ricorso per regolamento di competenza", "CIV_IMP_006", "CIV_APP_001", area="CIVILE"),
    _binding("Ricorso per regolamento di giurisdizione", "CIV_IMP_007", "CIV_APP_001", area="CIVILE"),
    _binding("Istanza di sospensione dell'esecutivita della sentenza", "CIV_IMP_008", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di correzione errore materiale", "CIV_IMP_009", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di integrazione del contraddittorio", "CIV_IMP_010", "CIV_IST_001", area="CIVILE"),
    _binding("Reclamo", "CIV_IMP_011", "CIV_APP_001", area="CIVILE"),
    _binding("Ricorso ex legge Pinto", "CIV_IMP_012", "CIV_APP_001", area="CIVILE"),
    # Esecuzioni
    _binding("Pignoramento mobiliare", "CIV_ESE_001", "CIV_PIGBASE_001", area="CIVILE"),
    _binding("Pignoramento immobiliare", "CIV_ESE_002", "CIV_PIGBASE_001", area="CIVILE"),
    _binding("Istanza di ricerca telematica dei beni", "CIV_ESE_003", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di vendita", "CIV_ESE_004", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di assegnazione", "CIV_ESE_005", "CIV_IST_001", area="CIVILE"),
    _binding("Opposizione di terzo all'esecuzione", "CIV_ESE_006", "CIV_OPESE_001", area="CIVILE"),
    _binding("Istanza di conversione del pignoramento", "CIV_ESE_007", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di riduzione del pignoramento", "CIV_ESE_008", "CIV_IST_001", area="CIVILE"),
    _binding("Intervento del creditore", "CIV_ESE_009", "CIV_IST_001", area="CIVILE"),
    _binding("Istanza di sospensione della procedura esecutiva", "CIV_ESE_010", "CIV_IST_001", area="CIVILE"),
    _binding("Nota di precisazione del credito", "CIV_ESE_011", "CIV_MEM_001", area="CIVILE"),
    _binding("Dichiarazione 553 c.p.c.", "CIV_ESE_012", "CIV_IST_001", area="CIVILE"),
    # Famiglia e volontaria giurisdizione
    _binding("Ricorso per ordine di protezione contro gli abusi familiari", "FAM_VG_001", "FAM_AFF_001", area="FAMIGLIA"),
    _binding("Ricorso per autorizzazione ad atto di straordinaria amministrazione del minore", "FAM_VG_002", "FAM_TUT_001", area="FAMIGLIA"),
    _binding("Istanze al giudice tutelare", "FAM_VG_003", "FAM_TUT_001", area="FAMIGLIA"),
    _binding("Istanza al giudice tutelare", "FAM_VG_004", "FAM_TUT_001", area="FAMIGLIA"),
    _binding("Volontaria giurisdizione", "FAM_VG_005", "FAM_TUT_001", area="FAMIGLIA"),
    _binding("Ricorso per decreto tavolare", "FAM_VG_006", "CIV_IST_001", area="FAMIGLIA"),
    # Lavoro e previdenza
    _binding("Ricorso d'urgenza in materia di lavoro", "LAV_BLT_001", "CIV_RCAUT_001", area="LAVORO"),
    _binding("Ricorso per differenze retributive", "LAV_BLT_002", "LAV_RIC_001", area="LAVORO"),
    _binding("Ricorso monitorio in materia di lavoro", "LAV_BLT_003", "CIV_RDI_001", area="LAVORO"),
    _binding("Opposizione a decreto ingiuntivo in materia di lavoro", "LAV_BLT_004", "CIV_OPPDI_001", area="LAVORO"),
    _binding("Ricorso per condotta antisindacale", "LAV_BLT_005", "LAV_RIC_001", area="LAVORO"),
    # Penale
    _binding("Querela", "PEN_BLT_001", "PEN_SEGNBASE_001", area="PENALE"),
    _binding("Denuncia", "PEN_BLT_002", "PEN_SEGNBASE_001", area="PENALE"),
    _binding("Opposizione alla richiesta di archiviazione", "PEN_BLT_003", "PEN_IST_001", area="PENALE"),
    _binding("Istanza di riesame di misura cautelare", "PEN_BLT_004", "PEN_IMP_001", area="PENALE"),
    _binding("Appello cautelare penale", "PEN_BLT_005", "PEN_IMP_001", area="PENALE"),
    _binding("Ricorso per cassazione penale", "PEN_BLT_006", "PEN_IMP_001", area="PENALE"),
    _binding("Atto di costituzione di parte civile", "PEN_BLT_007", "PEN_PARTECIVBASE_001", area="PENALE"),
    _binding("Lista testi", "PEN_BLT_008", "PEN_LISTATESTI_001", area="PENALE"),
    _binding("Istanza di incidente probatorio", "PEN_BLT_009", "PEN_IST_001", area="PENALE"),
    _binding("Istanza di revoca o sostituzione della misura cautelare", "PEN_BLT_010", "PEN_IST_001", area="PENALE"),
]


def compiler_alias_specs() -> list[dict[str, Any]]:
    return [dict(item) for item in BUILTIN_COMPILER_BINDINGS]


def compiler_binding_map_by_title() -> dict[str, dict[str, Any]]:
    return {item["title"]: dict(item) for item in BUILTIN_COMPILER_BINDINGS}
