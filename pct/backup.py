"""
Sistema di backup professionale per lo studio legale.

Funzionalità:
  - Backup completo / incrementale di tutti i dati dello studio
  - Cifratura AES-256 con password (opzionale)
  - Rotazione automatica: conserva N backup più recenti
  - Ripristino selettivo per componente (agenda, clienti, fascicoli, messaggi)
  - Verifica integrità tramite hash SHA-256
  - Automazione via APScheduler (giornaliera, settimanale, mensile)
  - Manifest JSON con metadati di ogni backup
"""

import json
import uuid
import zipfile
import hashlib
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Mapping
from dataclasses import dataclass, field, asdict
from enum import Enum


def backup_operations_disabled(config: Mapping[str, Any] | None = None) -> bool:
    """Restituisce ``True`` finché lo studio non abilita esplicitamente le copie.

    La politica è fail-closed per evitare che un job, una UI o una CLI generino
    archivi non richiesti. Un valore configurato esplicitamente prevale
    sull'ambiente; valori assenti o vuoti restano disabilitati.
    """
    configured = None
    if config is not None and "IUSENTRA_DISABLE_BACKUP_JOBS" in config:
        configured = config.get("IUSENTRA_DISABLE_BACKUP_JOBS")
    raw = configured if configured is not None else os.getenv("IUSENTRA_DISABLE_BACKUP_JOBS", "1")
    normalized = str(raw if raw is not None else "1").strip().lower()
    if not normalized:
        normalized = "1"
    return normalized in {"1", "true", "yes", "on"}


# ------------------------------------------------------------------ Enums

class TipoBackup(str, Enum):
    COMPLETO     = "COMPLETO"
    INCREMENTALE = "INCREMENTALE"


class StatoBackup(str, Enum):
    OK       = "OK"
    FALLITO  = "FALLITO"
    CORROTTO = "CORROTTO"


class FrequenzaBackup(str, Enum):
    GIORNALIERA  = "GIORNALIERA"
    SETTIMANALE  = "SETTIMANALE"
    MENSILE      = "MENSILE"
    MANUALE      = "MANUALE"


# ------------------------------------------------------------------ Dataclasses

@dataclass
class EntryBackup:
    """Metadati di un singolo file incluso nel backup."""
    percorso_relativo: str
    dimensione_bytes: int
    hash_sha256: str
    timestamp_modifica: str


@dataclass
class RecordBackup:
    """Registro di un backup effettuato."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tipo: TipoBackup = TipoBackup.COMPLETO
    stato: StatoBackup = StatoBackup.OK
    percorso_file: str = ""
    hash_file: str = ""
    dimensione_bytes: int = 0
    num_file: int = 0
    componenti: List[str] = field(default_factory=list)
    cifrato: bool = False
    nota: str = ""
    errore: str = ""
    # For incremental: reference to previous full backup
    backup_base_id: str = ""

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["stato"] = self.stato.value
        return d

    @staticmethod
    def from_dict(d: Dict) -> "RecordBackup":
        d = dict(d)
        d["tipo"] = TipoBackup(d.get("tipo", "COMPLETO"))
        d["stato"] = StatoBackup(d.get("stato", "OK"))
        return RecordBackup(**d)


@dataclass
class ConfigBackup:
    """Configurazione del sistema di backup."""
    directory_backup: str = "./backup"
    # Percorsi dei dati da includere (relativi o assoluti)
    percorsi_dati: List[str] = field(default_factory=list)
    # Rotazione: numero massimo di backup da conservare (0 = nessun limite)
    max_backup: int = 10
    # Cifratura
    password: str = ""
    # Automazione
    frequenza: FrequenzaBackup = FrequenzaBackup.GIORNALIERA
    ora_esecuzione: str = "02:00"   # HH:MM
    backup_abilitato: bool = False
    # Componenti inclusi per default
    includi_agenda: bool = True
    includi_clienti: bool = True
    includi_fascicoli: bool = True
    includi_messaggi: bool = True
    includi_documenti: bool = True

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["frequenza"] = self.frequenza.value
        return d

    @staticmethod
    def from_dict(d: Dict) -> "ConfigBackup":
        d = dict(d)
        d["frequenza"] = FrequenzaBackup(d.get("frequenza", "GIORNALIERA"))
        return ConfigBackup(**d)


# ------------------------------------------------------------------ Helpers

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encrypt_zip(zip_path: Path, password: str) -> Path:
    """
    Cifra il file ZIP con AES-256 usando la libreria cryptography.
    Restituisce il percorso del file cifrato (.enc).
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError:
        raise RuntimeError("cryptography non installata. Eseguire: pip install cryptography")

    import os
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(password.encode())
    aesgcm = AESGCM(key)
    data = zip_path.read_bytes()
    ct = aesgcm.encrypt(nonce, data, None)
    enc_path = zip_path.with_suffix(".zip.enc")
    # Format: salt(16) + nonce(12) + ciphertext
    enc_path.write_bytes(salt + nonce + ct)
    return enc_path


def _decrypt_zip(enc_path: Path, password: str) -> bytes:
    """Decifra un file .zip.enc e restituisce i bytes dello ZIP originale."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError:
        raise RuntimeError("cryptography non installata. Eseguire: pip install cryptography")

    data = enc_path.read_bytes()
    salt = data[:16]
    nonce = data[16:28]
    ct = data[28:]
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(password.encode())
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


# ------------------------------------------------------------------ Core

class GestioneBackup:
    """
    Gestisce backup, ripristino e rotazione dei dati dello studio.

    Struttura directory backup:
        <directory_backup>/
            registro.json          ← elenco di tutti i backup
            config.json            ← configurazione
            <id_backup>.zip        ← archivio dati
            <id_backup>.zip.enc    ← archivio cifrato (se password impostata)
    """

    REGISTRO = "registro.json"
    CONFIG   = "config.json"

    def __init__(
        self,
        directory_backup: str = "./backup",
        percorsi_dati: Optional[Dict[str, str]] = None,
        config: Optional[ConfigBackup] = None,
    ):
        """
        Args:
            directory_backup: cartella dove salvare i backup.
            percorsi_dati: dict {nome_componente: percorso_file_o_cartella}.
                Es. {"agenda": "/data/agenda.json", "fascicoli": "/data/fascicoli/"}
            config: ConfigBackup opzionale; se fornita sovrascrive i default.
        """
        self.dir = Path(directory_backup)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._percorsi: Dict[str, str] = percorsi_dati or {}
        self._config = config or self._carica_config()
        self._registro: List[RecordBackup] = self._carica_registro()

    # ---- persistenza

    def _carica_registro(self) -> List[RecordBackup]:
        p = self.dir / self.REGISTRO
        if p.exists():
            try:
                return [RecordBackup.from_dict(d) for d in json.loads(p.read_text("utf-8"))]
            except Exception:
                return []
        return []

    def _salva_registro(self):
        p = self.dir / self.REGISTRO
        p.write_text(
            json.dumps([r.to_dict() for r in self._registro], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _carica_config(self) -> ConfigBackup:
        p = self.dir / self.CONFIG
        if p.exists():
            try:
                return ConfigBackup.from_dict(json.loads(p.read_text("utf-8")))
            except Exception:
                pass
        return ConfigBackup(directory_backup=str(self.dir))

    def salva_config(self, config: ConfigBackup):
        """Persiste la configurazione."""
        self._config = config
        p = self.dir / self.CONFIG
        p.write_text(
            json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def config(self) -> ConfigBackup:
        return self._config

    # ---- backup

    def esegui_backup(
        self,
        tipo: TipoBackup = TipoBackup.COMPLETO,
        componenti: Optional[List[str]] = None,
        password: str = "",
        nota: str = "",
    ) -> RecordBackup:
        """
        Esegue un backup.

        Args:
            tipo: COMPLETO o INCREMENTALE.
            componenti: lista di chiavi da self._percorsi da includere.
                        None = tutti i percorsi registrati.
            password: cifra con AES-256 se fornita (sovrascrive config).
            nota: nota libera allegata al record.
        Returns:
            RecordBackup con i metadati del backup.
        """
        record = RecordBackup(tipo=tipo, nota=nota)
        usa_password = password or self._config.password

        try:
            sorgenti = self._risolvi_componenti(componenti)
            record.componenti = list(sorgenti.keys())

            # Determina backup di riferimento per incrementale
            if tipo == TipoBackup.INCREMENTALE:
                base = self._ultimo_backup_completo()
                if base:
                    record.backup_base_id = base.id

            # Crea ZIP temporaneo
            zip_tmp = self.dir / f"{record.id}_tmp.zip"
            manifest: List[Dict] = []
            n_file = 0

            with zipfile.ZipFile(zip_tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for nome_comp, percorso in sorgenti.items():
                    p = Path(percorso)
                    if not p.exists():
                        continue
                    if p.is_file():
                        entries = [p]
                        base_dir = p.parent
                    else:
                        entries = sorted(p.rglob("*"))
                        base_dir = p.parent

                    for entry in entries:
                        if not entry.is_file():
                            continue
                        # Percorso relativo nell'archivio
                        rel = nome_comp + "/" + str(entry.relative_to(base_dir))
                        # Per incrementale salta file non modificati dall'ultimo backup
                        if tipo == TipoBackup.INCREMENTALE and base:
                            if not self._file_modificato_dopo(entry, base.timestamp):
                                continue
                        zf.write(entry, rel)
                        h = _sha256_file(entry)
                        manifest.append({
                            "percorso": rel,
                            "dimensione": entry.stat().st_size,
                            "hash": h,
                            "mtime": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
                        })
                        n_file += 1

                # Includi manifest
                manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
                zf.writestr("_manifest.json", manifest_bytes)
                # Includi metadati del record (senza percorso finale)
                meta = {
                    "id": record.id,
                    "timestamp": record.timestamp,
                    "tipo": record.tipo.value,
                    "componenti": record.componenti,
                    "nota": nota,
                }
                zf.writestr("_meta.json", json.dumps(meta, indent=2, ensure_ascii=False))

            record.num_file = n_file

            # Cifra se richiesto
            if usa_password:
                enc_path = _encrypt_zip(zip_tmp, usa_password)
                zip_tmp.unlink()
                final_path = enc_path
                record.cifrato = True
            else:
                final_path = self.dir / f"{record.id}.zip"
                zip_tmp.rename(final_path)
                record.cifrato = False

            record.percorso_file = str(final_path)
            record.hash_file = _sha256_file(final_path)
            record.dimensione_bytes = final_path.stat().st_size
            record.stato = StatoBackup.OK

        except Exception as exc:
            record.stato = StatoBackup.FALLITO
            record.errore = str(exc)
            # pulizia
            tmp = self.dir / f"{record.id}_tmp.zip"
            if tmp.exists():
                tmp.unlink()

        self._registro.append(record)
        self._salva_registro()

        # Rotazione automatica
        if self._config.max_backup > 0:
            self._ruota()

        return record

    # ---- ripristino

    def ripristina(
        self,
        id_backup: str,
        destinazione: str,
        componenti: Optional[List[str]] = None,
        password: str = "",
        sovrascrivi: bool = False,
    ) -> Dict[str, Any]:
        """
        Ripristina un backup.

        Args:
            id_backup: ID del RecordBackup da ripristinare.
            destinazione: cartella di destinazione.
            componenti: lista di componenti da ripristinare (None = tutti).
            password: password per decifrare (se cifrato).
            sovrascrivi: se True sovrascrive i file esistenti.
        Returns:
            Dict con "file_ripristinati", "file_saltati", "errori".
        """
        record = self.get(id_backup)
        if not record:
            raise ValueError(f"Backup {id_backup!r} non trovato")
        if record.stato == StatoBackup.FALLITO:
            raise ValueError("Impossibile ripristinare un backup fallito")

        dest = Path(destinazione)
        dest.mkdir(parents=True, exist_ok=True)

        usa_password = password or self._config.password
        file_path = Path(record.percorso_file)

        if not file_path.exists():
            raise FileNotFoundError(f"File backup non trovato: {file_path}")

        # Verifica integrità
        hash_attuale = _sha256_file(file_path)
        if hash_attuale != record.hash_file:
            record.stato = StatoBackup.CORROTTO
            self._salva_registro()
            raise ValueError("Integrità del backup compromessa (hash mismatch)")

        # Leggi ZIP (decifrando se necessario)
        if record.cifrato:
            if not usa_password:
                raise ValueError("Il backup è cifrato: fornire la password")
            zip_bytes = _decrypt_zip(file_path, usa_password)
            import io
            zf_source = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        else:
            zf_source = zipfile.ZipFile(file_path, "r")

        ripristinati = []
        saltati = []
        errori = []

        with zf_source as zf:
            for nome in zf.namelist():
                if nome.startswith("_"):
                    continue  # salta manifest e meta
                if componenti:
                    comp = nome.split("/")[0]
                    if comp not in componenti:
                        continue
                out = dest / nome
                if out.exists() and not sovrascrivi:
                    saltati.append(nome)
                    continue
                try:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(zf.read(nome))
                    ripristinati.append(nome)
                except Exception as e:
                    errori.append({"file": nome, "errore": str(e)})

        return {
            "file_ripristinati": len(ripristinati),
            "file_saltati": len(saltati),
            "errori": errori,
            "destinazione": str(dest),
        }

    # ---- verifica integrità

    def verifica_integrita(self, id_backup: str) -> Dict[str, Any]:
        """Verifica l'hash del file di backup."""
        record = self.get(id_backup)
        if not record:
            raise ValueError(f"Backup {id_backup!r} non trovato")

        file_path = Path(record.percorso_file)
        if not file_path.exists():
            return {"ok": False, "errore": "File non trovato", "id": id_backup}

        hash_attuale = _sha256_file(file_path)
        ok = hash_attuale == record.hash_file
        if not ok:
            record.stato = StatoBackup.CORROTTO
            self._salva_registro()

        return {
            "ok": ok,
            "id": id_backup,
            "hash_atteso": record.hash_file,
            "hash_attuale": hash_attuale,
            "file": str(file_path),
        }

    # ---- eliminazione e rotazione

    def elimina(self, id_backup: str):
        """Elimina un backup dal registro e dal filesystem."""
        record = self.get(id_backup)
        if not record:
            raise ValueError(f"Backup {id_backup!r} non trovato")
        p = Path(record.percorso_file)
        if p.exists():
            p.unlink()
        self._registro = [r for r in self._registro if r.id != id_backup]
        self._salva_registro()

    def _ruota(self):
        """Conserva solo i max_backup più recenti."""
        max_b = self._config.max_backup
        if max_b <= 0:
            return
        # Ordina per timestamp decrescente
        completati = [r for r in self._registro if r.stato == StatoBackup.OK]
        completati.sort(key=lambda r: r.timestamp, reverse=True)
        da_eliminare = completati[max_b:]
        for r in da_eliminare:
            p = Path(r.percorso_file)
            if p.exists():
                p.unlink()
            self._registro = [rec for rec in self._registro if rec.id != r.id]
        if da_eliminare:
            self._salva_registro()

    # ---- query

    def tutti(self, stato: Optional[StatoBackup] = None) -> List[RecordBackup]:
        risultati = list(self._registro)
        if stato:
            risultati = [r for r in risultati if r.stato == stato]
        risultati.sort(key=lambda r: r.timestamp, reverse=True)
        return risultati

    def get(self, id_backup: str) -> Optional[RecordBackup]:
        for r in self._registro:
            if r.id == id_backup:
                return r
        return None

    def ultimo(self) -> Optional[RecordBackup]:
        ok = [r for r in self._registro if r.stato == StatoBackup.OK]
        if not ok:
            return None
        return max(ok, key=lambda r: r.timestamp)

    def statistiche(self) -> Dict[str, Any]:
        tutti = self._registro
        ok = [r for r in tutti if r.stato == StatoBackup.OK]
        totale_bytes = sum(r.dimensione_bytes for r in ok)
        return {
            "totale": len(tutti),
            "ok": len(ok),
            "falliti": sum(1 for r in tutti if r.stato == StatoBackup.FALLITO),
            "corrotti": sum(1 for r in tutti if r.stato == StatoBackup.CORROTTO),
            "dimensione_totale_bytes": totale_bytes,
            "dimensione_totale_mb": round(totale_bytes / (1024 * 1024), 2),
            "ultimo": self.ultimo().timestamp if self.ultimo() else None,
        }

    # ---- helpers interni

    def _risolvi_componenti(self, componenti: Optional[List[str]]) -> Dict[str, str]:
        """Restituisce il sotto-dizionario di percorsi da includere."""
        if not componenti:
            return dict(self._percorsi)
        return {k: v for k, v in self._percorsi.items() if k in componenti}

    def _ultimo_backup_completo(self) -> Optional[RecordBackup]:
        completi = [
            r for r in self._registro
            if r.tipo == TipoBackup.COMPLETO and r.stato == StatoBackup.OK
        ]
        if not completi:
            return None
        return max(completi, key=lambda r: r.timestamp)

    @staticmethod
    def _file_modificato_dopo(path: Path, timestamp_iso: str) -> bool:
        try:
            ts = datetime.fromisoformat(timestamp_iso)
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            return mtime > ts
        except Exception:
            return True


# ------------------------------------------------------------------ Scheduler

def avvia_scheduler_backup(
    gb: GestioneBackup,
    frequenza: FrequenzaBackup = FrequenzaBackup.GIORNALIERA,
    ora: str = "02:00",
    **kwargs_backup,
) -> Any:
    """
    Avvia APScheduler per backup automatici.

    Args:
        gb: istanza GestioneBackup.
        frequenza: GIORNALIERA, SETTIMANALE o MENSILE.
        ora: orario di esecuzione "HH:MM".
        **kwargs_backup: argomenti passati a gb.esegui_backup().
    Returns:
        Lo scheduler avviato.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        raise RuntimeError("apscheduler non installato. Eseguire: pip install apscheduler")

    ora_h, ora_m = (int(x) for x in ora.split(":"))
    scheduler = BackgroundScheduler(timezone="Europe/Rome")

    if frequenza == FrequenzaBackup.GIORNALIERA:
        trigger = CronTrigger(hour=ora_h, minute=ora_m)
    elif frequenza == FrequenzaBackup.SETTIMANALE:
        trigger = CronTrigger(day_of_week="mon", hour=ora_h, minute=ora_m)
    elif frequenza == FrequenzaBackup.MENSILE:
        trigger = CronTrigger(day=1, hour=ora_h, minute=ora_m)
    else:
        raise ValueError(f"Frequenza non schedulabile: {frequenza}")

    scheduler.add_job(
        lambda: gb.esegui_backup(**kwargs_backup),
        trigger,
        id="backup_automatico",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
