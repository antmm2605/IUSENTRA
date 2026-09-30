"""Pertinenza dei campi per gli atti SICID verificati negli XSD in esercizio.

Parte.xsd v7 e base_v7/tipi-atti.xsd, pacchetto SICI 12/05/2026:
numeroCCI appartiene al riferimento concorsuale, sub è facoltativo;
le istanze aggiuntive sono facoltative o assenti. Gli eventi delle memorie
171-ter e dell'istanza 183-ter sono già determinati dal tipo di deposito.
"""

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
