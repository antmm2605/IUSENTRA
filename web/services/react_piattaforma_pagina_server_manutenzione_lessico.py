"""Lessico italiano della pagina «Server e manutenzione» (React).

`build_server_maintenance_surface()` e i servizi di manutenzione restituiscono
etichette e note pensate per la vista storica, con termini tecnici inglesi
(«mirror», «retention», «snapshot», «cache», «Docker», «chunk», «VACUUM»...).
La pagina React mostra lo stesso contenuto in italiano: qui stanno le
traduzioni, in un solo punto, senza toccare i servizi (che restano la fonte dei
dati anche per l'API JSON storica `/admin/server-manutenzione/api`).

Le frasi note si traducono per intero; quelle composte dal servizio (note con
suffisso di scansione, avvisi con il nome dell'archivio) per prefisso; per il
resto si sostituiscono i soli frammenti tecnici. I codici tecnici (`code`)
non passano di qui: restano nei dettagli.
"""

from __future__ import annotations

import re
from typing import Any

from web.services.react_piattaforma_sezioni import _t

FRASI: dict[str, str] = {
    # Console del server: aree e composizione fuori dagli studi.
    "Dati piattaforma": "Dati della piattaforma",
    "Dati operativi, tenant, fonti ufficiali e indici di ricerca.": "Dati operativi, studi, fonti ufficiali e indici di ricerca.",
    "Archivi backup esterni": "Archivi di backup esterni",
    "Copie gia' presenti fuori dagli studi, governate da retention.": "Copie già presenti fuori dagli studi, governate dalla politica di conservazione.",
    "Snapshot temporaneo residuo": "Istantanea temporanea residua",
    "Area temporanea da verificare: se non collegata ai container puo' essere rimossa.": "Area temporanea da verificare: se non è collegata ai servizi in esecuzione può essere rimossa.",
    "Sorgenti di deploy e asset compilati.": "Sorgenti di rilascio e risorse compilate.",
    "Proxy HTTPS": "Instradamento HTTPS pubblico",
    "Certificati e dati del proxy pubblico.": "Certificati e dati dell'instradamento pubblico.",
    "Log server": "Registri del server",
    "Log di sistema e servizi.": "Registri di sistema e dei servizi.",
    "Docker e servizi": "Servizi e contenitori",
    "Immagini, container, volumi e cache. La cache costruzione e' pulibile dalla console.": "Immagini, contenitori, volumi e memoria temporanea. La memoria temporanea di costruzione si pulisce dalla console.",
    "Altri dati piattaforma fuori studi": "Altri dati della piattaforma fuori dagli studi",
    "Residuo delle aree globali sotto data dopo le voci principali.": "Residuo delle aree globali nella cartella dati, dopo le voci principali.",
    "Quota residua del disco: sistema operativo, librerie, journald, pacchetti e file non sotto IUSENTRA.": "Quota residua del disco: sistema operativo, librerie, registri di sistema, pacchetti e file esterni a IUSENTRA.",
    "Area dati piattaforma fuori dagli storage tenant attivi.": "Area dati della piattaforma fuori dagli archivi degli studi attivi.",
    "Archivio Normattiva globale usato da Ricerca Legale e Lex: DB, indice e sorgenti restano vivi.": "Archivio Normattiva globale usato da Ricerca legale e Lex: archivio, indice e sorgenti restano attivi.",
    "Repository globale di ricerca e aggiornamenti legali condivisi dal prodotto.": "Archivio globale di ricerca e aggiornamenti legali condivisi dal prodotto.",
    "Sistema operativo, Docker, codice deploy, backup esterni e dati globali non appartenenti agli studi attivi.": "Sistema operativo, servizi e contenitori, codice di rilascio, backup esterni e dati globali non appartenenti agli studi attivi.",
    # Voci di recupero.
    "Cache costruzione servizi": "Memoria temporanea di costruzione dei servizi",
    "Recupero sicuro: non tocca dati studio e rende solo piu' lenta la prossima ricostruzione.": "Recupero sicuro: non tocca i dati degli studi e rende solo più lenta la prossima ricostruzione.",
    "Pulizia cache servizi": "Pulizia della memoria temporanea dei servizi",
    "Recupero sicuro: lascia vivi DB, indice e sorgenti usati da Ricerca Legale e Lex.": "Recupero sicuro: lascia attivi archivio, indice e sorgenti usati da Ricerca legale e Lex.",
    "Da rimuovere solo dopo controllo che non sia montato o usato dai container.": "Da rimuovere solo dopo aver controllato che non sia collegata o usata dai servizi in esecuzione.",
    "Retention backup": "Conservazione dei backup",
    "La console continuera' a misurare cache, snapshot e archivi esterni.": "La console continuerà a misurare memoria temporanea, istantanee e archivi esterni.",
    # Aree di archiviazione principali.
    "Backup e mirror studi": "Backup e copie speculari degli studi",
    "Snapshot, mirror e copie interne rilevate negli studi.": "Istantanee, copie speculari e copie interne rilevate negli studi.",
    "Archivi email fuori studio: da mantenere solo in scenari mono-studio o migrazione.": "Archivi di posta fuori dagli studi: da mantenere solo con uno studio unico o durante una migrazione.",
    "Copie backup fuori studio da governare con retention.": "Copie di backup fuori dagli studi, da governare con la politica di conservazione.",
    "Allegati email globali": "Allegati di posta globali",
    "Allegati globali deduplicabili.": "Allegati globali con copie identiche riducibili.",
    "Import portali": "Importazioni dai portali",
    "Staging import autorizzati.": "Area di preparazione delle importazioni autorizzate.",
    "Redis persistente": "Archivio Redis persistente",
    "Append-only file e snapshot Redis.": "File di registrazione e istantanee di Redis.",
    # Raccomandazioni generali.
    "Scansione storage rapida: la console resta reattiva e mostra le aree principali; usare le analisi mirate quando serve il dettaglio completo.": "Scansione rapida dello spazio: la console resta reattiva e mostra le aree principali; usare le analisi mirate quando serve il dettaglio completo.",
    "Disco oltre l'80%: liberare cache servizi, snapshot residui e aree non operative.": "Disco oltre l'80%: liberare la memoria temporanea dei servizi, le istantanee residue e le aree non operative.",
    "Cache costruzione servizi molto alta: pulirla libera spazio senza toccare dati di studio.": "Memoria temporanea di costruzione dei servizi molto alta: pulirla libera spazio senza toccare i dati degli studi.",
    "Sono presenti aree da verificare fuori dagli studi: controllare snapshot temporanei e retention prima di rimuovere.": "Sono presenti aree da verificare fuori dagli studi: controllare le istantanee temporanee e la conservazione dei backup prima di rimuovere.",
    "Backup esterni oltre il tetto configurato: applicare retention e compressione alta.": "Backup esterni oltre il tetto configurato: applicare la politica di conservazione e la compressione alta.",
    "Backup mirror interni sopra 512 MiB: verificare retention; la compattazione e' utile solo se l'analisi segnala file da compattare.": "Copie speculari interne sopra 512 MiB: verificare la conservazione; la compattazione è utile solo se l'analisi segnala file da compattare.",
    # Raccomandazioni per studio.
    "Backup e mirror sopra 256 MiB: analizzare retention e compattazione prima di creare nuove copie.": "Backup e copie speculari sopra 256 MiB: analizzare conservazione e compattazione prima di creare nuove copie.",
    "Posta e allegati sopra 256 MiB: deduplicare allegati e valutare archiviazione caselle chiuse.": "Posta e allegati sopra 256 MiB: ridurre gli allegati identici e valutare l'archiviazione delle caselle chiuse.",
    "Database sopra 128 MiB: pianificare verifica integrita e VACUUM in manutenzione.": "Database sopra 128 MiB: pianificare la verifica di integrità e la compattazione in manutenzione.",
    "Lex e intelligence sopra 1 GiB: verificare indici, cache e fonti rigenerabili.": "Lex e ricerca sopra 1 GiB: verificare indici, memoria temporanea e fonti rigenerabili.",
    # Stato delle cartelle degli studi.
    "Cartella legacy non attiva": "Cartella storica non attiva",
    "Cartella presente su disco ma assente dalla registry tenant: non e' conteggiata come studio attivo.": "Cartella presente su disco ma assente dal registro degli studi: non è conteggiata come studio attivo.",
}

#: Frammenti tecnici residui nelle frasi composte dal servizio.
FRAMMENTI: tuple[tuple[str, str], ...] = (
    ("Cartella storica collegata allo slug dello studio: lo storage attivo e' ", "Cartella storica collegata all'indirizzo dello studio: l'archivio attivo è "),
    ("Backup e mirror", "Backup e copie speculari"),
    ("Lex e intelligence", "Lex e ricerca"),
    ("Cache e code", "Memoria temporanea e code"),
    ("Portali e import", "Portali e importazioni"),
    ("con un VACUUM", "con una compattazione"),
    ("il VACUUM", "la compattazione"),
    ("e' ", "è "),
    ("piu'", "più"),
    ("puo'", "può"),
    ("gia'", "già"),
)

_CHUNK = re.compile(r"\bchunk\b")


def it(valore: Any) -> str:
    """La frase del servizio in italiano professionale (se è nota) o ripulita dai termini tecnici."""
    testo = _t(valore)
    if not testo:
        return ""
    if testo in FRASI:
        return FRASI[testo]
    for origine, traduzione in FRASI.items():
        if len(origine) > 20 and testo.startswith(origine):
            testo = traduzione + testo[len(origine):]
            break
    for origine, traduzione in FRAMMENTI:
        testo = testo.replace(origine, traduzione)
    return _CHUNK.sub("frammenti", testo)


def percorso(valore: Any) -> str:
    """Un percorso del server come lo mostra il pannello di piattaforma.

    Le risposte del pannello lasciano passare i percorsi (il superamministratore
    li vedeva nella vista storica); un testo con tracce tecniche resta nascosto e
    si dichiara come riservato, invece di diventare «Operazione non completata.».
    """
    from web.services.security_redaction import redact_exception_details

    testo = _t(valore)
    if testo and redact_exception_details(testo, consenti_percorsi=True) != testo:
        return "percorso interno del server (riservato)"
    return testo


__all__ = ["FRASI", "it", "percorso"]
