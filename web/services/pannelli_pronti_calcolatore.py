"""Processo di ricalcolo dei pannelli pronti, avviato dal lavoro dello scheduler quando serve.

Gira a bassa priorità (nice 10), uno solo per archivio condiviso (lock su file), con l'app web completa perché i
pannelli si calcolano con le stesse viste dell'avvocato. Lavora a lotti piccoli finché trova pannelli superati e
si chiude da solo dopo alcuni minuti senza lavoro, liberando la memoria.

Uso: ``python -m web.services.pannelli_pronti_calcolatore``.
"""

from __future__ import annotations

import fcntl
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)
LOTTO = 8
# Copertura di tutti i fascicoli: lotti piccoli, così una consultazione dell'avvocato passa avanti in pochi secondi.
LOTTO_COPERTURA = 4
PAUSA_SECONDI = 2.0
PAUSA_SENZA_SALVATAGGI = 30.0
CHIUSURA_DOPO_SECONDI = 600.0
# Il processo si chiude dopo mezz'ora anche con lavoro residuo: libera la memoria, lo scheduler lo riavvia al minuto
# successivo e la copertura riprende dal primo pannello non pronto.
DURATA_MASSIMA_SECONDI = 1800.0
FILE_LOCK = Path(os.getenv("PCT_DATA_ROOT") or tempfile.gettempdir()) / "iusentra-pannelli-pronti-calcolatore.lock"


def _prendi_lock():
    handle = open(FILE_LOCK, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def in_esecuzione() -> bool:
    handle = _prendi_lock()
    if handle is None:
        return True
    handle.close()
    return False


def sveglia_calcolatore(tenant: str = "", fascicolo_id: str = "") -> bool:
    """Avvia un solo processo anche se più pannelli arrivano durante il suo avvio."""
    with FILE_LOCK.with_suffix(".avvio").open("a+") as avvio:
        try:
            fcntl.flock(avvio, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        avvio.seek(0)
        precedente = avvio.read().strip()
        adesso = time.monotonic()
        if in_esecuzione() or (precedente and 0 <= adesso - float(precedente) < 5):
            return False
        radice = Path(__file__).resolve().parents[2]
        comando = [sys.executable, "-m", "web.services.pannelli_pronti_calcolatore"]
        if shutil.which("ionice"):
            # Disco solo quando nessun altro lo usa: la copertura non rallenta l'app né l'OCR.
            comando = ["ionice", "-c", "3", *comando]
        if tenant and fascicolo_id:
            comando.extend((tenant, fascicolo_id))
        subprocess.Popen(comando, cwd=str(radice),
                         stdout=subprocess.DEVNULL, stderr=None, start_new_session=True, close_fds=True)
        avvio.seek(0)
        avvio.truncate()
        avvio.write(str(adesso))
        return True


def giro(app, *, lotto: int = LOTTO, solo_pannelli_prioritari: bool = False, tenant: str = "", fascicolo_id: str = "",
         con_copertura: bool = True) -> dict[str, int]:
    """Un lotto per studio: le voci superate dei fascicoli aperti di recente; senza, la copertura di tutto lo studio."""
    from web.services.pannelli_pronti_runtime import archivio_per_percorsi, fonti_per_percorsi
    from web.services.pannelli_pronti_sfondo import copertura, da_ricalcolare, ricalcola, studi

    totale = {"trovati": 0, "calcolati": 0, "non_salvati": 0, "errori": 0}
    for owner, data_paths in studi(app):
        if tenant and str(getattr(owner, "slug", "") or "single-studio") != tenant:
            continue
        archivio, fonti = archivio_per_percorsi(data_paths), fonti_per_percorsi(data_paths)
        if archivio is None or fonti is None or not Path(archivio.percorso).exists():
            continue
        archivio.prepara_indici()
        interrompi = None
        if solo_pannelli_prioritari:
            voci = da_ricalcolare(archivio, fonti, limite=lotto, solo_pannelli_prioritari=True, fascicolo_richiesto=fascicolo_id)
        else:
            voci = da_ricalcolare(archivio, fonti, limite=lotto, fascicolo_richiesto=fascicolo_id)
            if not voci and not fascicolo_id and con_copertura:
                # Nessun pannello aperto di recente da aggiornare: si prepara il resto dello studio.
                voci = copertura(archivio, fonti, limite=LOTTO_COPERTURA)
                interrompi = lambda: pannello_prioritario_richiesto(app)  # noqa: E731
        totale["trovati"] += len(voci)
        if voci:
            for chiave, valore in ricalcola(app, archivio, voci, interrompi=interrompi).items():
                totale[chiave] += valore
            _prepara_bozze(app, owner, voci)
            _guardiano(app, owner, voci)
            if solo_pannelli_prioritari:
                break
    return totale


def _prepara_bozze(app, owner, voci) -> None:
    """Dopo la Lettura ricalcolata, le bozze dei prossimi passi (stesso processo a bassa priorità)."""
    fascicoli = {voce.fascicolo_id for voce in voci if voce.pannello in {"lettura", "conto-economico"}}
    if not fascicoli:
        return
    try:
        from web.services.bozze_passi_runtime import giro as giro_bozze

        esito = giro_bozze(app, fascicoli={str(getattr(owner, "slug", "") or "single-studio"): fascicoli})
        if esito.get("create") or esito.get("aggiornate"):
            logger.info("Bozze dei passi: %s", esito)
    except Exception as exc:  # le bozze non fermano i pannelli
        logger.warning("Bozze dei passi non preparate: %s", exc)


def _guardiano(app, owner, voci) -> None:
    """Dopo la Lettura ricalcolata (qualunque fonte l'abbia superata), il guardiano della catena sullo stesso fascicolo:
    riallinea scadenziario e agenda al modello, chiede i ricalcoli mancanti e registra gli avvisi (pct/catena)."""
    fascicoli = {voce.fascicolo_id for voce in voci if voce.pannello in {"lettura", "conto-economico", "quadro"}}
    if not fascicoli:
        return
    try:
        from web.services.catena_guardiano_runtime import giro as giro_guardiano

        esito = giro_guardiano(app, fascicoli={str(getattr(owner, "slug", "") or "single-studio"): fascicoli})
        if esito.get("incoerenze"):
            logger.info("Guardiano della catena: %s", esito)
    except Exception as exc:  # il guardiano non ferma i pannelli
        logger.warning("Guardiano della catena non eseguito: %s", exc)


def pannello_prioritario_richiesto(app) -> bool:
    """Controlla le consultazioni in attesa prima di chiedere il turno."""
    from web.services.pannelli_pronti_runtime import archivio_per_percorsi
    from web.services.pannelli_pronti_sfondo import MINUTI_ATTESA_LETTURA, PANNELLI_PRIORITARI, studi

    for _owner, percorsi in studi(app):
        archivio = archivio_per_percorsi(percorsi)
        if archivio is not None and Path(archivio.percorso).exists():
            if archivio.fascicoli_in_attesa_di_lettura(minuti=MINUTI_ATTESA_LETTURA, pannelli=PANNELLI_PRIORITARI):
                return True
    return False


def main(tenant: str = "", fascicolo_id: str = "") -> int:
    handle = _prendi_lock()
    if handle is None:
        return 0  # già in esecuzione
    try:
        os.nice(10)
    except OSError:
        pass
    os.environ["IUSENTRA_STARTUP_GOVERNANCE_CHILD"] = "1"
    from web.app import create_app

    from pct.semaforo_motori import PRIORITA_DIFFERIBILE, SemaforoOccupato, motore_pesante

    app = create_app()
    if tenant and fascicolo_id:
        from web.services.pannelli_pronti_sfondo import PANNELLI_PRIORITARI

        try:
            esito = giro(app, lotto=len(PANNELLI_PRIORITARI), solo_pannelli_prioritari=True,
                         tenant=tenant, fascicolo_id=fascicolo_id)
            if not esito["trovati"]:
                with motore_pesante("pannelli pronti", priorita=PRIORITA_DIFFERIBILE, attesa_massima=5.0):
                    esito = giro(app, tenant=tenant, fascicolo_id=fascicolo_id)
            logger.info("Pannelli pronti, richiesta %s: %s", fascicolo_id, esito)
        except SemaforoOccupato:
            logger.info("Pannelli del fascicolo %s affidati allo scheduler", fascicolo_id)
        finally:
            handle.close()
        return 0
    ultimo_lavoro = avvio = time.monotonic()
    while time.monotonic() - avvio < DURATA_MASSIMA_SECONDI:
        try:
            richiesta = pannello_prioritario_richiesto(app)
            esito = giro(app, lotto=1, solo_pannelli_prioritari=True) if richiesta else {"trovati": 0}
            if not esito["trovati"]:
                # La Lettura consultiva proietta dati già archiviati. Il lock del
                # calcolatore la serializza senza aspettare il turno di OCR e PEC.
                with motore_pesante("pannelli pronti", priorita=PRIORITA_DIFFERIBILE, attesa_massima=5.0):
                    esito = giro(app)
        except SemaforoOccupato:
            if time.monotonic() - ultimo_lavoro > CHIUSURA_DOPO_SECONDI:
                break
            time.sleep(PAUSA_SECONDI if richiesta else PAUSA_SENZA_SALVATAGGI)
            continue
        except Exception as exc:
            logger.exception("Ricalcolo dei pannelli pronti non riuscito: %s", exc)
            esito = {"trovati": 0}
        salvati = int(esito.get("calcolati") or 0)
        if esito.get("trovati"):
            logger.info("Pannelli pronti: %s", esito)
        if salvati:
            ultimo_lavoro = time.monotonic()
        elif time.monotonic() - ultimo_lavoro > CHIUSURA_DOPO_SECONDI:
            break
        time.sleep(PAUSA_SENZA_SALVATAGGI if esito.get("trovati") and not salvati else PAUSA_SECONDI)
    handle.close()
    return 0


def avvia_se_serve(app) -> dict[str, object]:
    """Lavoro dello scheduler: se qualche pannello è superato e il calcolatore non gira, lo avvia."""
    from web.services.pannelli_pronti_runtime import archivio_per_percorsi, fonti_per_percorsi
    from web.services.pannelli_pronti_sfondo import copertura, da_ricalcolare, studi

    if in_esecuzione():
        return {"ok": True, "avviato": False, "motivo": "calcolatore già in esecuzione"}
    superati = 0
    for _owner, data_paths in studi(app):
        archivio, fonti = archivio_per_percorsi(data_paths), fonti_per_percorsi(data_paths)
        if archivio is None or fonti is None or not Path(archivio.percorso).exists():
            continue
        archivio.prepara_indici()
        archivio.elimina_vecchie()
        superati += len(da_ricalcolare(archivio, fonti, limite=1)) or len(copertura(archivio, fonti, limite=1))
        if superati:
            break
    if not superati:
        return {"ok": True, "avviato": False, "motivo": "tutti i pannelli sono aggiornati"}
    return {"ok": True, "avviato": sveglia_calcolatore(), "motivo": "pannelli superati da ricalcolare"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    sys.exit(main(*sys.argv[1:]))
