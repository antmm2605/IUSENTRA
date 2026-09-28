"""Firma remota reale con i tre protocolli (ARSS di Aruba e Actalis, SWS di Namirial, CSC v1/v2).

I servizi sono simulati con una vera chiave RSA (tests/firma_remota_simulata.py): si verifica
l'XML/JSON inviato, che le buste CAdES e PAdES risultino crittograficamente valide e che
una firma sbagliata del prestatore non diventi un documento firmato.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pct.firma_remota import CredenzialiFirmaRemota, FirmaRemotaError, FirmaRemotaNonConfigurata
from pct.firma_remota.prestatori import configurazione_da_firma, provider_da_firma
from tests.firma_remota_simulata import ServizioSimulato


def _pdf() -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    tela = canvas.Canvas(buffer)
    tela.drawString(72, 720, "Atto di citazione")
    tela.save()
    return buffer.getvalue()


def _cfg(**campi):
    base = {"prestatore": "", "remota_protocollo": "", "remota_endpoint": "", "remota_utente": "avv.rossi",
            "remota_dominio": "firma", "remota_credenziale": "", "remota_tipo_otp": "app"}
    return SimpleNamespace(**{**base, **campi})


def _cred(**campi):
    return CredenzialiFirmaRemota(**{"username": "avv.rossi", "password": "Firma!2026", "otp": "123456", **campi})


def _verifica_cades(busta: bytes, contenuto_atteso: bytes | None = None) -> None:
    from pct.document_signature_state import cades_crittograficamente_valida
    from pct.firma import estrai_contenuto_cades, profilo_cades_bes_valido

    assert profilo_cades_bes_valido(busta)
    assert cades_crittograficamente_valida(busta)
    if contenuto_atteso is not None:
        assert estrai_contenuto_cades(busta) == contenuto_atteso


def _verifica_pades(pdf: bytes) -> None:
    from pct.firma import analizza_firma_documento

    firme = analizza_firma_documento(pdf, "atto.pdf")
    assert firme and all(f["content_digest_verified"] and f["cryptographic_signature_verified"] for f in firme)


# --- Aruba / Actalis (ARSS) --------------------------------------------------------------


def test_aruba_arss_indirizzo_pubblico_e_firma_cades_valida():
    servizio = ServizioSimulato()
    provider, conf = provider_da_firma(_cfg(prestatore="aruba"), sessione=servizio)
    assert conf.protocollo == "arss" and conf.endpoint == "https://arss.arubapec.it/ArubaSignService/ArubaSignService"
    esito = provider.firma_cades(b"contenuto dell'atto", _cred(dominio="firma"))
    _verifica_cades(esito.contenuto, b"contenuto dell'atto")
    assert esito.dettagli["intestatario"] == "ROSSI MARIO"
    richiesta = dict(servizio.chiamate)["signhash"].find("SignHashRequest")
    identita = richiesta.find("identity")
    assert [e.tag for e in identita] == ["otpPwd", "typeHSM", "typeOtpAuth", "user", "userPWD"]
    assert identita.findtext("typeOtpAuth") == "firma" and richiesta.findtext("hashtype") == "SHA256"
    assert richiesta.findtext("certID") == "AS0"


def test_actalis_arss_firma_pades_valida_con_timbro():
    servizio = ServizioSimulato()
    provider, conf = provider_da_firma(_cfg(prestatore="actalis"), sessione=servizio)
    assert conf.endpoint.startswith("https://arss.actalis.it/")
    esito = provider.firma_pades(_pdf(), _cred(), visible_signature_mode="basso_destra", visible_signature_place="Taurianova")
    _verifica_pades(esito.contenuto)
    assert esito.formato == "pades"


def test_arss_invio_otp_sms_e_otp_sbagliato():
    from pct.firma_remota.prestatori import configurazione_da_firma, firmatario

    servizio = ServizioSimulato()
    arss = firmatario(configurazione_da_firma(_cfg(prestatore="aruba")), sessione=servizio)
    assert arss.richiedi_otp(_cred(tipo_otp="sms")) == "Codice inviato per SMS."
    assert dict(servizio.chiamate)["sendCredential"].findtext("type") == "SMS"
    provider, _ = provider_da_firma(_cfg(prestatore="aruba"), sessione=servizio)
    with pytest.raises(FirmaRemotaError, match="Credenziali non valide"):
        provider.firma_cades(b"atto", _cred(otp="000000"))


def test_firma_sbagliata_del_prestatore_non_produce_documento():
    provider, _ = provider_da_firma(_cfg(prestatore="aruba"), sessione=ServizioSimulato(firma_sbagliata=True))
    with pytest.raises(FirmaRemotaError, match="non corrisponde al certificato"):
        provider.firma_cades(b"atto", _cred())


def test_cofirma_cades_parallela_con_firma_remota():
    servizio = ServizioSimulato()
    provider, _ = provider_da_firma(_cfg(prestatore="aruba"), sessione=servizio)
    prima = provider.firma_cades(b"atto condiviso", _cred()).contenuto
    seconda = provider.firma_cades(prima, _cred()).contenuto
    from asn1crypto import cms

    assert len(cms.ContentInfo.load(seconda)["content"]["signer_infos"]) == 2
    _verifica_cades(seconda, b"atto condiviso")


def test_certificato_scaduto_blocca_la_firma():
    from tests.firma_remota_simulata import chiave_e_certificato

    servizio = ServizioSimulato()
    servizio.chiave, servizio.cert_der = chiave_e_certificato(scaduto=True)
    provider, _ = provider_da_firma(_cfg(prestatore="aruba"), sessione=servizio)
    with pytest.raises(FirmaRemotaError, match="scaduto"):
        provider.firma_cades(b"atto", _cred())


# --- Namirial (SWS) ---------------------------------------------------------------------


def test_namirial_sws_pades_e_cades():
    servizio = ServizioSimulato()
    provider, conf = provider_da_firma(_cfg(prestatore="namirial", remota_utente="RHIP123"), sessione=servizio)
    assert conf.protocollo == "sws" and conf.endpoint == "https://sws.namirialtsp.com/SignEngineWeb/sign-services"
    _verifica_pades(provider.firma_pades(_pdf(), _cred(username="RHIP123")).contenuto)
    _verifica_cades(provider.firma_cades(b"atto", _cred(username="RHIP123")).contenuto, b"atto")
    firma = dict(servizio.chiamate)["signPkcs1"]
    assert [e.tag for e in firma.find("credentials")] == ["idOtp", "otp", "password", "username"]
    assert firma.findtext("credentials/idOtp") == "7" and firma.findtext("preferences/hashAlgorithm") == "SHA256"


def test_namirial_sws_otp_errato_diventa_messaggio():
    provider, _ = provider_da_firma(_cfg(prestatore="namirial"), sessione=ServizioSimulato())
    with pytest.raises(FirmaRemotaError, match="Invalid OTP"):
        provider.firma_cades(b"atto", _cred(otp="999999"))


# --- CSC v1 e v2 ------------------------------------------------------------------------


@pytest.mark.parametrize("versione", ["v1", "v2"])
def test_csc_firma_cades_e_pades(versione):
    servizio = ServizioSimulato()
    cfg = _cfg(prestatore="infocert", remota_endpoint=f"https://firma.prestatore.example/csc/{versione}")
    provider, conf = provider_da_firma(cfg, sessione=servizio)
    assert conf.protocollo == "csc"
    credenziali = _cred(password="Accesso!1", pin="Firma!2026")
    _verifica_cades(provider.firma_cades(b"atto", credenziali).contenuto, b"atto")
    _verifica_pades(provider.firma_pades(_pdf(), credenziali).contenuto)
    percorsi = [p for p, _ in servizio.chiamate]
    assert percorsi[:4] == ["auth/login", "credentials/list", "credentials/info", "credentials/authorize"]
    assert "signatures/signHash" in percorsi and "auth/revoke" in percorsi
    autorizza = dict(servizio.chiamate)["credentials/authorize"]
    assert ("authData" in autorizza) == (versione == "v2")


def test_csc_otp_online_richiesto_e_pin_errato():
    from pct.firma_remota.prestatori import firmatario

    servizio = ServizioSimulato()
    csc = firmatario(configurazione_da_firma(_cfg(prestatore="intesi", remota_endpoint="https://x.example/csc/v1")),
                     sessione=servizio)
    assert csc.richiedi_otp(_cred(password="Accesso!1")) == "Codice inviato dal prestatore."
    provider, _ = provider_da_firma(_cfg(prestatore="intesi", remota_endpoint="https://x.example/csc/v1"), sessione=servizio)
    with pytest.raises(FirmaRemotaError, match="PIN o OTP errati"):
        provider.firma_cades(b"atto", _cred(password="Accesso!1", pin="sbagliato"))


# --- Configurazione ---------------------------------------------------------------------


def test_prestatore_senza_api_pubblica_indica_la_firma_esterna():
    with pytest.raises(FirmaRemotaNonConfigurata, match="Firma esterna"):
        configurazione_da_firma(_cfg(prestatore="poste"))


def test_csc_senza_indirizzo_e_indirizzi_non_ammessi():
    with pytest.raises(FirmaRemotaNonConfigurata, match="contratto"):
        configurazione_da_firma(_cfg(prestatore="infocert"))
    for indirizzo, errore in (("http://x.example/csc/v1", "https"), ("https://localhost/csc/v1", "locale"),
                              ("https://x.example/api", "/csc/v1")):
        with pytest.raises(FirmaRemotaError, match=errore):
            provider_da_firma(_cfg(prestatore="infocert", remota_endpoint=indirizzo), sessione=ServizioSimulato())


def test_catalogo_elenco_agid_e_dispositivi():
    from pct import firma_catalogo

    ids = {p["id"] for p in firma_catalogo.prestatori()}
    assert {"aruba", "actalis", "infocert", "namirial", "intesi", "poste", "infocamere", "zucchetti"} <= ids
    assert len(ids) == 23
    assert firma_catalogo.protocolli_remoti("namirial") == ["sws", "csc"]
    candidati = firma_catalogo.librerie_candidate("athena", "windows")
    assert r"C:\Windows\System32\asepkcs.dll" in candidati
    assert "/usr/lib/libASEP11.so" in firma_catalogo.librerie_candidate("athena", "linux")
    assert all(p["librerie"].keys() == {"windows", "linux", "macos"} for p in firma_catalogo.produttori())
