
"""Rifa' i chunk che l'archivio RAG ha ereditato dallo splitter vecchio.

Fino alla 2.341.0 `_split_section` tagliava soltanto fra un paragrafo e
l'altro. Un testo senza righe vuote — un PDF letto come byte, l'uscita di un
OCR, un XML in blocco unico — diventava percio' un chunk solo, di qualunque
lunghezza: il limite in token non entrava mai in funzione. Dalla 2.342.0 il
taglio e' garantito da `_bounded_text_parts`.

La correzione vale pero' per quello che si indicizza da quel momento in poi.
I chunk gia' scritti sono rimasti come erano e sono ancora in attesa di
embedding. Mandarli al modello non serve: il validatore li scarta uno per uno
e li segna `invalid`. Il guaio e' cosa resta dopo. Un documento i cui chunk
finiscono tutti fra gli scarti non ha piu' niente di cercabile, e sparisce
dalla ricerca senza che nessuno se ne accorga: l'avvocato apre il fascicolo e
il documento c'e', ma la ricerca non lo trova piu'.

Qui si ripassa. `esamina` legge e basta: dice quali documenti hanno chunk che
il validatore di oggi scarterebbe, e quali di quelli si possono rifare.
`rispezza` li reindicizza davvero, con `force`, cosi' lo splitter nuovo li
taglia da capo.

La logica sta qui, non nella rotta: la console e la riga di comando devono
fare esattamente la stessa cosa.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pct.local_ai import _RAG_MAX_CHUNK_CHARS, _embedding_validation_reason

#: Quanti testi si leggono per volta quando serve guardarli davvero.
LOTTO_TESTI = 200

#: Quanti documenti al massimo si rifanno in una sola passata.
LOTTO_DOCUMENTI = 150

#: Secondi oltre i quali la passata si ferma da sola e dice quanto resta.
#: Il server chiude la richiesta a 120 secondi: meglio fermarsi prima e
#: rispondere, che farsi troncare a meta' senza dire niente.
BUDGET_SECONDI = 75.0


@dataclass
class EsitoArchivio:
    """Cosa succederebbe, o cos'e' successo, all'archivio di uno studio."""

    studio: str
    chunk_in_attesa: int = 0
    chunk_da_scartare: int = 0
    documenti_coinvolti: int = 0
    documenti_rifatti: int = 0
    documenti_verso_ocr: int = 0
    documenti_senza_file: int = 0
    documenti_in_errore: int = 0
    documenti_restanti: int = 0
    errore: str = ""
    esempi: list[dict[str, Any]] = field(default_factory=list)

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "studio": self.studio,
            "chunk_in_attesa": self.chunk_in_attesa,
            "chunk_da_scartare": self.chunk_da_scartare,
            "documenti_coinvolti": self.documenti_coinvolti,
            "documenti_rifatti": self.documenti_rifatti,
            "documenti_verso_ocr": self.documenti_verso_ocr,
            "documenti_senza_file": self.documenti_senza_file,
            "documenti_in_errore": self.documenti_in_errore,
            "documenti_restanti": self.documenti_restanti,
            "errore": self.errore,
            "esempi": self.esempi[:5],
        }


def _righe_in_attesa(conn) -> list[dict[str, Any]]:
    """Id, documento e lunghezza dei chunk in attesa. Il testo non si legge."""
    righe = conn.execute(
        """
        SELECT id, document_id, length(text) AS lunghezza
        FROM rag_chunks
        WHERE embedding_state = 'pending'
        ORDER BY lunghezza DESC
        """
    ).fetchall()
    return [dict(riga) for riga in righe]


def chunk_da_scartare(service: Any) -> tuple[list[dict[str, Any]], int]:
    """I chunk in attesa che il validatore di oggi rifiuterebbe.

    I fuori misura si riconoscono dalla sola lunghezza, senza caricare il
    testo: sono proprio quelli che occupano piu' memoria. Per gli altri il
    testo serve, e si legge a lotti.
    """
    with service._connect() as conn:
        righe = _righe_in_attesa(conn)
        totale = len(righe)
        scarti: list[dict[str, Any]] = []
        da_guardare: list[dict[str, Any]] = []
        for riga in righe:
            if int(riga.get("lunghezza") or 0) > _RAG_MAX_CHUNK_CHARS:
                scarti.append(
                    {
                        "chunk": riga["id"],
                        "documento": riga["document_id"],
                        "motivo": (
                            f"Chunk escluso: {riga['lunghezza']} caratteri oltre "
                            f"il limite di {_RAG_MAX_CHUNK_CHARS}."
                        ),
                    }
                )
            else:
                da_guardare.append(riga)

        for inizio in range(0, len(da_guardare), LOTTO_TESTI):
            lotto = da_guardare[inizio : inizio + LOTTO_TESTI]
            segnaposti = ",".join("?" for _ in lotto)
            testi = conn.execute(
                f"SELECT id, document_id, text FROM rag_chunks WHERE id IN ({segnaposti})",
                [riga["id"] for riga in lotto],
            ).fetchall()
            for testo in testi:
                motivo = _embedding_validation_reason(testo["text"])
                if motivo:
                    scarti.append(
                        {
                            "chunk": testo["id"],
                            "documento": testo["document_id"],
                            "motivo": motivo,
                        }
                    )
    return scarti, totale


def documenti_coinvolti(service: Any, scarti: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """I documenti a cui appartengono i chunk da scartare, senza doppioni."""
    identificativi = list(dict.fromkeys(str(scarto["documento"]) for scarto in scarti if scarto.get("documento")))
    if not identificativi:
        return []
    documenti: list[dict[str, Any]] = []
    with service._connect() as conn:
        for inizio in range(0, len(identificativi), LOTTO_TESTI):
            lotto = identificativi[inizio : inizio + LOTTO_TESTI]
            segnaposti = ",".join("?" for _ in lotto)
            righe = conn.execute(
                f"""
                SELECT id, source_type, source_id, practice_id, title, file_path, mime_type
                FROM rag_documents WHERE id IN ({segnaposti})
                """,
                lotto,
            ).fetchall()
            documenti.extend(dict(riga) for riga in righe)
    return documenti


def _file_presente(documento: dict[str, Any]) -> bool:
    percorso = str(documento.get("file_path") or "").strip()
    if not percorso:
        return False
    try:
        return Path(percorso).is_file()
    except OSError:
        return False


def documenti_fuori_misura(service: Any, *, massimo: int = 0) -> list[dict[str, Any]]:
    """I documenti con almeno un chunk in attesa oltre il limite, per SQL soltanto.

    Il censimento completo deve leggere il testo di ogni chunk sotto misura per
    passarlo al validatore, e su decine di migliaia di righe costa un minuto e
    mezzo. Qui non serve: un chunk oltre `_RAG_MAX_CHUNK_CHARS` si riconosce
    dalla sola lunghezza, e sono quelli il grosso del guaio. La rispezzatura
    parte da questi, cosi' ogni passata spende il suo tempo a rifare documenti
    invece che a ricontarli.
    """
    sql = """
        SELECT d.id, d.source_type, d.source_id, d.practice_id, d.title, d.file_path, d.mime_type
        FROM rag_documents AS d
        WHERE EXISTS (
            SELECT 1 FROM rag_chunks AS c
            WHERE c.document_id = d.id
              AND c.embedding_state = 'pending'
              AND length(c.text) > ?
        )
    """
    parametri: list[Any] = [_RAG_MAX_CHUNK_CHARS]
    if massimo > 0:
        sql += " LIMIT ?"
        parametri.append(massimo)
    with service._connect() as conn:
        return [dict(riga) for riga in conn.execute(sql, parametri).fetchall()]


def quanti_fuori_misura(service: Any) -> int:
    """Quanti documenti hanno ancora almeno un chunk oltre il limite."""
    with service._connect() as conn:
        riga = conn.execute(
            """
            SELECT COUNT(DISTINCT document_id) FROM rag_chunks
            WHERE embedding_state = 'pending' AND length(text) > ?
            """,
            (_RAG_MAX_CHUNK_CHARS,),
        ).fetchone()
    return int(riga[0] if riga else 0)


def esamina(service: Any, *, studio: str = "", limite: int = 0) -> EsitoArchivio:
    """Quanti chunk in attesa oggi verrebbero scartati, e da quali documenti.

    Non scrive niente.
    """
    esito = EsitoArchivio(studio=studio or "default")
    try:
        scarti, totale = chunk_da_scartare(service)
        esito.chunk_in_attesa = totale
        esito.chunk_da_scartare = len(scarti)
        documenti = documenti_coinvolti(service, scarti)
        if limite > 0:
            documenti = documenti[:limite]
        esito.documenti_coinvolti = len(documenti)
        for documento in documenti:
            if not _file_presente(documento):
                esito.documenti_senza_file += 1
        for scarto in scarti[:5]:
            esito.esempi.append(scarto)
    except Exception as exc:
        esito.errore = str(exc)
    return esito


def rispezza(
    service: Any,
    *,
    studio: str = "",
    limite: int = 0,
    massimo_documenti: int = LOTTO_DOCUMENTI,
    budget_secondi: float = BUDGET_SECONDI,
) -> EsitoArchivio:
    """Reindicizza con `force` i documenti che hanno chunk fuori misura.

    Parte dalla lista a sola SQL: il censimento completo legge il testo di
    ogni chunk e su questo archivio costa un minuto e mezzo, che e' piu' del
    tempo che il server concede a tutta la richiesta. Cosi' invece la passata
    spende il suo tempo a rifare documenti.

    Lavora a lotti: si ferma al tetto di documenti o allo scadere del tempo —
    contato da quando comincia a lavorare, non da quando comincia a guardare —
    e dice quanti ne restano. L'operazione e' ripetibile.

    Si tocca solo chi ha ancora il file di partenza: un documento indicizzato
    da testo gia' estratto non si puo' ricostruire da qui, e viene contato a
    parte invece di essere svuotato.
    """
    esito = EsitoArchivio(studio=studio or "default")
    try:
        massimo_lista = massimo_documenti if limite <= 0 else min(massimo_documenti, limite)
        candidati = documenti_fuori_misura(service, massimo=massimo_lista)
        esito.documenti_coinvolti = quanti_fuori_misura(service)
    except Exception as exc:
        esito.errore = str(exc)
        return esito

    rifattibili = [doc for doc in candidati if _file_presente(doc)]
    esito.documenti_senza_file = len(candidati) - len(rifattibili)
    partenza = time.monotonic()
    fatti = 0
    for documento in rifattibili:
        if fatti >= massimo_documenti or (time.monotonic() - partenza) >= budget_secondi:
            break
        fatti += 1
        try:
            risultato = service.index_file(
                source_type=str(documento.get("source_type") or ""),
                source_id=str(documento.get("source_id") or ""),
                practice_id=str(documento.get("practice_id") or "") or None,
                file_path=str(documento.get("file_path") or ""),
                title=str(documento.get("title") or "") or None,
                mime_type=str(documento.get("mime_type") or "") or None,
                force=True,
            )
        except Exception as exc:
            esito.documenti_in_errore += 1
            esito.esempi.append({"documento": documento.get("id"), "errore": str(exc)[:160]})
            continue
        stato = str((risultato or {}).get("status") or "")
        if stato == "indexed":
            esito.documenti_rifatti += 1
        elif stato == "needs_ocr":
            esito.documenti_verso_ocr += 1
        else:
            esito.documenti_in_errore += 1
            esito.esempi.append({"documento": documento.get("id"), "stato": stato})
    try:
        esito.documenti_restanti = quanti_fuori_misura(service)
    except Exception:
        esito.documenti_restanti = max(0, esito.documenti_coinvolti - fatti)
    return esito


def _riepilogo(esiti: list[EsitoArchivio], *, applicato: bool) -> dict[str, Any]:
    in_attesa = sum(e.chunk_in_attesa for e in esiti)
    da_scartare = sum(e.chunk_da_scartare for e in esiti)
    coinvolti = sum(e.documenti_coinvolti for e in esiti)
    rifatti = sum(e.documenti_rifatti for e in esiti)
    verso_ocr = sum(e.documenti_verso_ocr for e in esiti)
    senza_file = sum(e.documenti_senza_file for e in esiti)
    errori = [e.errore for e in esiti if e.errore]
    restanti = sum(e.documenti_restanti for e in esiti)
    if applicato:
        messaggio = (
            f"Rifatti {rifatti} documenti su {coinvolti} fuori misura; "
            f"{verso_ocr} passati all'OCR, {senza_file} senza file di partenza."
        )
        if restanti:
            messaggio += f" Restano {restanti} documenti da rifare: ripremere il bottone."
    else:
        messaggio = (
            f"{da_scartare} chunk su {in_attesa} in attesa verrebbero scartati, "
            f"da {coinvolti} documenti ({senza_file} senza file di partenza). "
            "Nessuna modifica eseguita."
        )
    return {
        "ok": not errori,
        "rispezzatura_eseguita": bool(applicato),
        "chunk_in_attesa": in_attesa,
        "chunk_da_scartare": da_scartare,
        "documenti_coinvolti": coinvolti,
        "documenti_rifatti": rifatti,
        "documenti_verso_ocr": verso_ocr,
        "documenti_senza_file": senza_file,
        "documenti_in_errore": sum(e.documenti_in_errore for e in esiti),
        "documenti_restanti": restanti,
        "errori": errori,
        "studi": [e.come_dizionario() for e in esiti],
        "messaggio": messaggio,
    }


__all__ = [
    "BUDGET_SECONDI",
    "LOTTO_DOCUMENTI",
    "LOTTO_TESTI",
    "EsitoArchivio",
    "chunk_da_scartare",
    "documenti_coinvolti",
    "documenti_fuori_misura",
    "esamina",
    "quanti_fuori_misura",
    "rispezza",
]
