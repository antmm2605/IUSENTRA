from pct.pst_cifratura import (
    CertificatoCifratura,
    PSTCifraturaError,
    PST_TLS_INTERMEDIATES,
    canali_telematici_cifratura_policy,
    precarica_certificati_cifratura,
    valida_canale_telematico_per_cifratura,
)
import pct.pst_cifratura as pst_cifratura
from legal_deposit.policies import channel_profile_for
from web.services.deposito_route_helpers import ufficio_deposito_destinatario


def test_policy_canali_telematici_copre_pct_pat_ptt_pdp():
    policy = canali_telematici_cifratura_policy()

    assert {"pct_civile_dm44", "pdp_penale", "pat_amministrativo", "ptt_tributario"} <= set(policy)
    assert policy["pct_civile_dm44"]["usa_certificati_pst_cer"] is True
    assert policy["pdp_penale"]["usa_certificati_pst_cer"] is False
    assert policy["pat_amministrativo"]["usa_certificati_pst_cer"] is False
    assert policy["ptt_tributario"]["usa_certificati_pst_cer"] is False


def test_canali_non_pct_non_possono_usare_cer_atto_enc():
    for canale in ("pdp_penale", "pat_amministrativo", "ptt_tributario"):
        audit = valida_canale_telematico_per_cifratura(canale)

        assert audit["ok"] is True
        assert audit["usa_certificati_pst_cer"] is False
        assert audit["procedura"] == "procedura_dedicata_non_pst"
        assert any("non usare .cer PST" in item for item in audit["controlli_software"])


def test_profili_pdp_pat_ptt_non_ereditano_busta_pct_o_pec_diretta():
    pdp = channel_profile_for("pdp_penale")
    pat = channel_profile_for("pat_siga")
    ptt = channel_profile_for("ptt_sigit")

    assert pdp.package_kind == "pdp_upload"
    assert pdp.allows_portal_upload is True
    assert pdp.allows_direct_pec is False
    assert pdp.requires_encryption is False
    assert pdp.xml_filename == ""
    assert {"PADES", "CADES_BES"} <= set(pdp.accepted_signature_formats)

    for profile in (pat, ptt):
        assert profile.package_kind == "portal_upload"
        assert profile.allows_portal_upload is True
        assert profile.requires_manual_final_upload is True
        assert profile.allows_direct_pec is False
        assert profile.requires_encryption is False
        assert profile.package_kind != "pct_busta_enc"

    assert pat.signature_policy.format == "PADES"
    assert pat.accepted_signature_formats == ("PADES",)
    assert {"PADES", "CADES_BES"} <= set(ptt.accepted_signature_formats)


def test_canale_pct_richiede_cer_e_atto_enc_aes256():
    audit = valida_canale_telematico_per_cifratura("pct_civile_dm44")

    assert audit["ok"] is True
    assert audit["usa_certificati_pst_cer"] is True
    assert audit["procedura"] == "cifratura_pst_atto_enc"
    assert "Atto.enc AES256" in " ".join(audit["controlli_software"])


def test_precarico_cer_scheduler_limita_perimetro_a_pct_civile_operativo(monkeypatch, tmp_path):
    rows = [
        {
            "codice_ufficio": "0630491155",
            "descrizione": "GIUDICE DI PACE - Barra non attivo",
            "sezione_catalogo": "civili",
            "stato_prudenziale": "storico_o_non_operativo",
            "deposito_prudenziale": False,
        },
        {
            "codice_ufficio": "05200101501",
            "descrizione": "GIUDICE DI PACE PENALE",
            "sezione_catalogo": "penali",
            "stato_prudenziale": "pst_visibile",
            "deposito_prudenziale": True,
        },
        {
            "codice_ufficio": "0241160092",
            "descrizione": "Tribunale Ordinario - Vicenza",
            "sezione_catalogo": "civili",
            "stato_prudenziale": "pst_visibile",
            "deposito_prudenziale": True,
        },
    ]
    chiamate: list[str] = []

    def fake_catalogo():
        return iter(rows)

    def fake_resolver(codice_ufficio, *, cache_dir=None, force_refresh=False):
        chiamate.append(codice_ufficio)
        path = tmp_path / f"{codice_ufficio}.cer"
        path.write_bytes(b"cert")
        return CertificatoCifratura(
            codice_ufficio=codice_ufficio,
            path=str(path),
            subject="CN=test",
            issuer="CN=test",
            serial_number="01",
            not_valid_after="2030-01-01T00:00:00+00:00",
            source_url="test",
            sha256="ABC",
        )

    monkeypatch.setattr(pst_cifratura, "iter_uffici_pst_catalogo", fake_catalogo)
    monkeypatch.setattr(pst_cifratura, "risolvi_certificato_cifratura_ufficio", fake_resolver)

    report = precarica_certificati_cifratura(cache_dir=tmp_path, limit=1, force_refresh=True)

    assert report["ok"] is True
    assert report["totale"] == 1
    assert report["scaricati_o_validi"] == 1
    assert report["errori"] == 0
    assert report["saltati_non_pct_o_non_operativi"] == 2
    assert report["saltati_senza_certificato_pubblicato"] == 0
    assert chiamate == ["0241160092"]


def test_precarico_cer_scheduler_tratta_certificato_non_pubblicato_come_salto(
    monkeypatch, tmp_path
):
    rows = [
        {
            "codice_ufficio": "0560210157",
            "descrizione": "GIUDICE DI PACE-VITERBO EX GIUDICE DI PACE - Civita Castellana",
            "sezione_catalogo": "civili",
            "stato_prudenziale": "pst_visibile",
            "deposito_prudenziale": True,
        }
    ]

    def fake_catalogo():
        return iter(rows)

    def fake_resolver(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError(
            f"Certificato di cifratura PST non trovato per l'ufficio {codice_ufficio}."
        )

    monkeypatch.setattr(pst_cifratura, "iter_uffici_pst_catalogo", fake_catalogo)
    monkeypatch.setattr(pst_cifratura, "risolvi_certificato_cifratura_ufficio", fake_resolver)

    report = precarica_certificati_cifratura(cache_dir=tmp_path, limit=1, force_refresh=True)

    assert report["ok"] is True
    assert report["scaricati_o_validi"] == 0
    assert report["errori"] == 0
    assert report["saltati_senza_certificato_pubblicato"] == 1
    assert report["risultati"][0]["saltato"] is True
    assert report["risultati"][0]["motivo"] == "certificato_cifratura_non_pubblicato"


def test_downloader_pst_usa_intermedio_tls_pinnato_senza_disabilitare_ssl():
    intermediate = PST_TLS_INTERMEDIATES[0]

    assert intermediate["url"] == "http://tiTrust.crt.sectigo.com/TITrustTechnologiesOVCA.crt"
    assert intermediate["sha256"] == "1BFD8702D8F9BB340F353820330C0BBA7E522C63164C91F295414DAC797F0863"


def test_busta_usa_codice_pst_ministeriale_non_codice_catalogo_interno():
    class Fascicolo:
        tribunale = "Tribunale di Vicenza"
        profilo_deposito = {}

    payload = ufficio_deposito_destinatario(Fascicolo())

    assert payload["codice_catalogo"] == "0640011"
    assert payload["codice_ufficio"] == "0241160092"
    assert payload["pec_dest"] == "tribunale.vicenza@civile.ptel.giustiziacert.it"
