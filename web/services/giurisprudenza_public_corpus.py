"""Repository autonomo dei soli provvedimenti ufficiali pubblicabili."""
from contextlib import closing
from pathlib import Path
import os

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza

PUBLIC_CORPUS_PREFIX = "/giurisprudenza/corpus/pubblico"
PUBLIC_SOURCES = frozenset({"corte_costituzionale", "giustizia_tributaria", "curia", "hudoc", "corte_conti"})
PUBLIC_DATABASE_NAME = "giurisprudenza_pubblica.db"
PUBLIC_APPLICATION_ID = 0x49555047


def configured_public_corpus(config):
    setting = config.get("IUSENTRA_CORPUS_PUBBLICO_DIRECTORY") or os.getenv("IUSENTRA_CORPUS_PUBBLICO_DIRECTORY")
    if not setting:
        return None
    directory = Path(setting)
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError("Directory del corpus pubblico non valida.")
    database = directory / PUBLIC_DATABASE_NAME
    if database.is_symlink():
        raise ValueError("Il corpus pubblico deve essere autonomo.")
    owner = GestioneCorpusGiurisprudenza(str(database), read_only=True)
    with closing(owner._connect()) as connection:
        if connection.execute("PRAGMA application_id").fetchone()[0] != PUBLIC_APPLICATION_ID:
            raise ValueError("Il file non è un corpus pubblico IUSENTRA.")
    return owner


def require_public_corpus(config):
    owner = configured_public_corpus(config)
    if owner is None:
        raise FileNotFoundError("Corpus pubblico non configurato.")
    return owner
