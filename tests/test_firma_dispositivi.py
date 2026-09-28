"""Dispositivi di firma di tutti i produttori: catalogo unico, Local Signer e server.

Il catalogo (pct/data/cataloghi/firma_digitale.json) e la sua copia per il Local Signer
(local_signer_mod/dispositivi_firma.py) devono coincidere; dal browser arriva solo il
produttore, mai un percorso di libreria.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from local_signer_mod import dispositivi_firma
from pct import firma_catalogo

ROOT = Path(__file__).resolve().parents[1]


def _local_signer():
    spec = importlib.util.spec_from_file_location("local_signer_prova_dispositivi", ROOT / "tools" / "local_signer.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_copia_del_local_signer_uguale_al_catalogo():
    catalogo = firma_catalogo.catalogo()
    assert dispositivi_firma.CARTELLE == catalogo["cartelle_librerie"]
    assert dispositivi_firma.PRODUTTORI == {
        p["id"]: {"nome": p["nome"], "librerie": p["librerie"]} for p in catalogo["produttori_dispositivo"]}
    for sistema in ("windows", "linux", "macos"):
        for produttore in ["", *dispositivi_firma.PRODUTTORI]:
            assert dispositivi_firma.percorsi_candidati(produttore, sistema) == \
                firma_catalogo.librerie_candidate(produttore, sistema)
    assert (ROOT / "tools" / "dist" / "local_signer_mod" / "dispositivi_firma.py").read_bytes() == \
        (ROOT / "local_signer_mod" / "dispositivi_firma.py").read_bytes()


def test_produttori_principali_e_librerie():
    ids = set(dispositivi_firma.PRODUTTORI)
    assert {"bit4id", "athena", "incard", "oberthur", "cardos", "safenet", "idprime", "charismathics", "opensc"} <= ids
    nomi = dispositivi_firma.nomi_librerie("windows")
    assert {"bit4xpki.dll", "asepkcs.dll", "OCSCryptoki.dll", "IDPrimePKCS11.dll", "eTPKCS11.dll"} <= set(nomi)


def test_local_signer_accetta_solo_produttori_del_catalogo():
    modulo = _local_signer()
    assert modulo._produttore_richiesto("athena") == "athena"
    assert modulo._produttore_richiesto("ATHENA") == "athena"
    for valore in ("", "acme", r"C:\\Windows\\System32\\evil.dll", "../../lib.so", "athena;rm"):
        assert modulo._produttore_richiesto(valore) == ""


def test_local_signer_cerca_prima_le_librerie_del_produttore(monkeypatch):
    modulo = _local_signer()
    atteso = dispositivi_firma.percorsi_candidati("athena")[0]
    generica = modulo._DEFAULT_LIBS[0]
    esistenti = {atteso, generica}
    monkeypatch.setattr(modulo.os.path, "exists", lambda percorso: percorso in esistenti)
    candidati = modulo._candidate_pkcs11_libs(produttore="athena")
    assert candidati[0] == atteso and generica in candidati
    assert atteso in modulo._DEFAULT_LIBS  # anche senza produttore le librerie del catalogo si cercano


def test_server_cerca_anche_le_librerie_del_catalogo(monkeypatch):
    from pct import firma_pkcs11

    atteso = dispositivi_firma.percorsi_candidati("idprime")[0]
    monkeypatch.setattr(firma_pkcs11.Path, "exists", lambda self: str(self) == atteso)
    monkeypatch.setenv("PCT_PKCS11_PRODUTTORE", "idprime")
    monkeypatch.delenv("PCT_PKCS11_LIBRARY", raising=False)
    assert firma_pkcs11._candidate_libraries() == [atteso]
    assert os.environ["PCT_PKCS11_PRODUTTORE"] == "idprime"
