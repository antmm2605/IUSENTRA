"""Pertinenza dei campi per gli atti SICID verificati negli XSD in esercizio.

Parte.xsd v7 e base_v7/tipi-atti.xsd, pacchetto SICI 12/05/2026:
numeroCCI appartiene al riferimento concorsuale, sub è facoltativo;
le istanze aggiuntive sono facoltative o assenti. Gli eventi delle memorie
171-ter e dell'istanza 183-ter sono già determinati dal tipo di deposito.
"""

# Introduttivi.xsd v7, Citazione: istanze minOccurs=0 e un solo
# Datacitazione richiesto. Il generatore consolidato lo riceve tramite
# data_notifica_citazione: il controllo WinForms DataAtto non è un secondo
# attributo XML da chiedere all'avvocato.
SICID_CITAZIONE_DATA_UNICA = frozenset(
    f'Introduttivi_SICID::{suffix}'
    for suffix in ('Citazione', 'CitazioneAppello', 'CitazioneSfratto',
                   'CitazioneInRiassunzioneAppello', 'CitazioneInRiassunzione')
)

SICID_ATTI_SENZA_ISTANZA_MANUALE = frozenset(
    f"Parte_SICID::{suffix}"
    for suffix in (
        "ComparsaConclusionaleReplica190",
        "Comparsa180",
        "IstanzaAccoglimentoDomanda183ter",
        "Memoria171ter1",
        "Repliche171ter2",
        "Controrepliche171ter3",
        "Memoria183",
        "MemoriaReplica183",
        "MemoriaReplicaProvaContraria183",
        "MemorieCartabia",
        "PrecisazioneConclusioni",
        "Preverbale",
    )
)

# Queste chiavi selezionano già il relativo evento ministeriale. L'input
# generico WinForms "istanza" non è consumato dal generatore. L'audit XML
# verifica che la sua assenza conservi esattamente il documento prodotto.
SICID_ATTI_SENZA_ISTANZA_MANUALE |= SICID_CITAZIONE_DATA_UNICA | frozenset({
    'Introduttivi_SICID::RicorsoCAInibitoria',
    'Introduttivi_SICID::RicorsoAppello',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamConsegnaBeni',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamAssistenzaObbligatoria',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamMateriaLavoro',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamPrevidenzaObbligatoria',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoIntermediazioneFinanziaria',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamOneriCondominiali',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamPagamentoSommaAndConsegnaBeni',
    'Introduttivi_SICID::RicorsoDecretoIngiuntivoAnteCausamPagamentoSomma',
    'Parte_SICID::ComparsaCostituzioneAppelloIncidentale',
    'Parte_SICID::CostituzioneConRiconvenzionale',
    'Parte_SICID::CostituzioneSemplice',
    'Parte_SICID::ComparsaCostituzioneAppello',
    'Parte_SICID::IstanzaRigettoDomanda183quater',
})
