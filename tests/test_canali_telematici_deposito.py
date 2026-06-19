from pct.pst_cifratura import (
    CertificatoCifratura,
    PSTCifraturaError,
    PST_TLS_INTERMEDIATES,
    canali_telematici_cifratura_policy,
    certificato_cifratura_in_cache,
    certificati_cifratura_report_path,
    crea_certificato_cifratura_test,
    esegui_controllo_settimanale_certificati_cifratura,
    precarica_certificati_cifratura,
    report_path_certificati_mirato,
    salva_certificato_cifratura_ufficio,
    valida_canale_telematico_per_cifratura,
)
from pathlib import Path

import pct.pst_cifratura as pst_cifratura
import pct.uffici_giudiziari as uffici_giudiziari
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
    assert pat.max_files == 50
    assert pat.max_total_size_mb == 300
    assert pat.max_single_file_size_mb == 300
    assert pat.metadata["formweb_priority_from"] == "2026-02-01"
    assert pat.metadata["portal_upload_removed_at_regime"] is True
    assert {"PADES", "CADES_BES"} <= set(ptt.accepted_signature_formats)


def test_pat_siga_catalogo_moduli_e_formweb_da_fonti_ufficiali():
    from pct.pat_moduli import build_pat_siga_payload, suggest_pat_modules

    payload = build_pat_siga_payload()
    modules = {module["id"]: module for module in payload["modules"]}
    deposits = {deposit["id"]: deposit for deposit in payload["formwebDeposits"]}

    assert payload["portal"]["officialUrl"] == "https://pe.prod.cloud.giustizia-amministrativa.it"
    assert payload["portal"]["sessionMode"] == "sessione ufficiale assistita dal Local Connector del PC, senza iframe o proxy delle credenziali"
    assert payload["regime"]["formwebPriorityFrom"] == "2026-02-01"
    assert payload["regime"]["pecResidual"] is True
    assert payload["regime"]["portalUploadLegacyRemoved"] is True
    assert payload["limits"]["formweb"] == {
        "maxFiles": 50,
        "maxSingleFileSizeMb": 300,
        "maxTotalSizeMb": 300,
        "signature": "PADES",
        "requiresOfficialPortal": True,
    }
    assert {"deposito_ricorso", "deposito_atto", "richieste_segreteria", "foglio_excel_parti"} <= set(modules)
    assert modules["deposito_ricorso"]["version"] == "4.02"
    assert modules["deposito_atto"]["version"] == "4.02"
    assert modules["foglio_excel_parti"]["url"].endswith("t=1748183957377")
    assert deposits["ricorso"]["module_id"] == "deposito_ricorso"
    assert deposits["successivo_notifiche"]["module_id"] == "deposito_atto"
    assert suggest_pat_modules("rimborso contributo unificato")[0]["id"] == "rimborso_contributo_unificato"
    assert suggest_pat_modules("appalti cig pnrr")[0]["id"] == "deposito_ricorso"


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
    monkeypatch.setattr(pst_cifratura, "_iter_ministero_cert_target_rows", lambda: iter(()))
    monkeypatch.setattr(pst_cifratura, "risolvi_certificato_cifratura_ufficio", fake_resolver)

    report = precarica_certificati_cifratura(cache_dir=tmp_path, limit=1, force_refresh=True)

    assert report["ok"] is True
    assert report["totale"] == 1
    assert report["scaricati_o_validi"] == 1
    assert report["errori"] == 0
    assert report["saltati_non_pct_o_non_operativi"] == 2
    assert report["saltati_senza_certificato_pubblicato"] == 0
    assert report["scope_mode"] == "completo"
    assert report["catalogo_pct_operativi"] == 1
    assert report["cache_cer_presenti"] == 1
    assert chiamate == ["0241160092"]


def test_precarico_cer_scheduler_tratta_certificato_non_pubblicato_come_salto(
    monkeypatch, tmp_path
):
    rows = [
        {
            "codice_ufficio": "0800570152",
            "descrizione": "Giudice di Pace - Palmi",
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
    monkeypatch.setattr(pst_cifratura, "_iter_ministero_cert_target_rows", lambda: iter(()))
    monkeypatch.setattr(pst_cifratura, "risolvi_certificato_cifratura_ufficio", fake_resolver)

    report = precarica_certificati_cifratura(cache_dir=tmp_path, limit=1, force_refresh=True)

    assert report["ok"] is True
    assert report["scaricati_o_validi"] == 0
    assert report["errori"] == 0
    assert report["saltati_senza_certificato_pubblicato"] == 1
    assert report["risultati"][0]["saltato"] is True
    assert report["risultati"][0]["motivo"] == "certificato_cifratura_non_pubblicato"
    assert report["scope_mode"] == "completo"


def test_controllo_cer_mirato_non_sovrascrive_audit_completo(monkeypatch, tmp_path):
    rows = [
        {
            "codice_ufficio": "0800570152",
            "descrizione": "Giudice di Pace - Palmi",
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
    monkeypatch.setattr(pst_cifratura, "_iter_ministero_cert_target_rows", lambda: iter(()))
    monkeypatch.setattr(pst_cifratura, "risolvi_certificato_cifratura_ufficio", fake_resolver)

    full_report = certificati_cifratura_report_path(tmp_path)
    full_report.write_text('{"scope_mode":"completo"}', encoding="utf-8")
    report = esegui_controllo_settimanale_certificati_cifratura(
        cache_dir=tmp_path,
        force_refresh=True,
        codici_ufficio=["0800570152"],
    )

    assert report["scope_mode"] == "mirato"
    assert report["target_codes"] == ["0800570152"]
    assert report["report_principale_preservato"] == str(full_report)
    assert report["report_path"] != str(full_report)
    assert full_report.read_text(encoding="utf-8") == '{"scope_mode":"completo"}'


def test_salva_certificato_catalogo_servizi_in_cache_validata(tmp_path):
    generated = crea_certificato_cifratura_test(tmp_path / "origine.cer")

    info = salva_certificato_cifratura_ufficio(
        "0800570152",
        (tmp_path / "origine.cer").read_bytes(),
        source_url="https://ext.processotelematico.giustizia.it/servizi/CatalogoServizi",
        cache_dir=tmp_path / "cache",
    )
    cached = certificato_cifratura_in_cache("0800570152", cache_dir=tmp_path / "cache")

    assert cached is not None
    assert info.sha256 == generated.sha256
    assert cached.sha256 == info.sha256
    assert cached.source_url.endswith("/servizi/CatalogoServizi")
    assert (tmp_path / "cache" / "0800570152.cer").exists()


def test_cache_certificati_pst_normalizza_codici_senza_path_traversal(tmp_path):
    generated = crea_certificato_cifratura_test(tmp_path / "origine.cer")
    cache_dir = tmp_path / "cache"

    info = salva_certificato_cifratura_ufficio(
        "..\\..\\0800570152",
        (tmp_path / "origine.cer").read_bytes(),
        cache_dir=cache_dir,
    )
    report_path = report_path_certificati_mirato(
        ["../0800570152", "..\\..\\palmi"],
        cache_dir=cache_dir,
    )

    assert info.sha256 == generated.sha256
    assert Path(info.path).parent == cache_dir.resolve()
    assert Path(info.path).name == "0800570152.cer"
    assert report_path.parent == cache_dir.resolve()
    assert ".." not in report_path.name
    assert not (tmp_path / "0800570152.cer").exists()


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


def test_tribunali_payload_associa_pec_codice_ministeriale_e_cer(monkeypatch, tmp_path):
    from web.services.react_telematico_bridge import build_react_tribunali_payload

    rows = [
        {
            "codice": "0910011",
            "codice_ministero": "0800570094",
            "nome": "Tribunale di Palmi",
            "tipo": "TRIBUNALE",
            "distretto": "Reggio Calabria",
            "pec": "tribunale.palmi@civile.ptel.giustiziacert.it",
            "nome_certificato_cifra": "0800570094_Tribunale Ordinario - Palmi.cer",
            "certificato_mimetype": "application/octet-stream",
            "servizi_ministero": ["JPW_DEPOSITO"],
        },
        {
            "codice": "0910401",
            "codice_ministero": "0800570152",
            "nome": "Ufficio del Giudice di Pace di Palmi",
            "tipo": "GDP",
            "distretto": "Reggio Calabria",
            "pec": "gdp.palmi@civile.ptel.giustiziacert.it",
            "nome_certificato_cifra": "",
            "certificato_mimetype": "application/octet-stream",
            "servizi_ministero": ["JPW_DEPOSITO"],
        },
    ]

    class FakeGestore:
        def carica(self):
            return rows

        def stato(self):
            return {
                "sorgente": "test",
                "aggiornato_il": "2026-06-17T10:00:00+02:00",
                "cache_path": str(tmp_path / "uffici.json"),
                "scaduta": False,
            }

    def fake_certificato(codice_ufficio, *, cache_dir=None):
        if codice_ufficio == "0800570094":
            path = tmp_path / "0800570094.cer"
            path.write_bytes(b"cert")
            return CertificatoCifratura(
                codice_ufficio="0800570094",
                path=str(path),
                subject="CN=glrc_palmi_cifra",
                issuer="CN=Ministero Giustizia",
                serial_number="01",
                not_valid_after="2029-01-18T09:48:49+00:00",
                source_url="https://servizipst.giustizia.it/PST/do/ufficiepda/uffici/ricerca/download.action",
                sha256="E976D9227CD0B5150BB56B85EBAB1FFB3D9E0228385DE635B1261C2EE3418CF6",
            )
        if codice_ufficio == "0800570152":
            path = tmp_path / "0800570152.cer"
            path.write_bytes(b"cert")
            return CertificatoCifratura(
                codice_ufficio="0800570152",
                path=str(path),
                subject="CN=gdprc_cifra",
                issuer="CN=Ministero Giustizia",
                serial_number="02",
                not_valid_after="2027-01-16T14:05:08+00:00",
                source_url=(
                    "https://servizipst.giustizia.it/PST/do/ufficiepda/uffici/ricerca/download.action"
                    "?codiceUfficio=0800570152&fileName=0800570152_Giudice%20di%20Pace%20-%20Palmi.cer"
                    "&mimetype=application/octet-stream"
                ),
                sha256="7B25BF3F549F576266B12F56826E7096D4B6EBBB44B306D30C8E89C1BC717832",
            )
            return None
        return None

    monkeypatch.setattr(uffici_giudiziari, "get_gestore", lambda: FakeGestore())
    monkeypatch.setattr(uffici_giudiziari, "indirizzi_telematici_ufficio", lambda row, **kwargs: [])
    monkeypatch.setattr(pst_cifratura, "certificato_cifratura_in_cache", fake_certificato)

    payload = build_react_tribunali_payload()
    by_name = {office["nome"]: office for office in payload["offices"]}

    tribunale = by_name["Tribunale di Palmi"]
    gdp = by_name["Ufficio del Giudice di Pace di Palmi"]

    assert tribunale["pec"] == "tribunale.palmi@civile.ptel.giustiziacert.it"
    assert tribunale["codiceMinistero"] == "0800570094"
    assert tribunale["nomeCertificatoCifra"] == "0800570094_Tribunale Ordinario - Palmi.cer"
    assert tribunale["certificatoCifratura"]["verificato"] is True
    assert tribunale["certificatoCifratura"]["sha256"].startswith("E976D")

    assert gdp["pec"] == "gdp.palmi@civile.ptel.giustiziacert.it"
    assert gdp["codiceMinistero"] == "0800570152"
    assert gdp["certificatoCifratura"]["richiesto"] is True
    assert gdp["certificatoCifratura"]["verificato"] is True
    assert gdp["certificatoCifratura"]["sha256"].startswith("7B25B")
    assert payload["officeSummary"]["certificates"] == {
        "required": 2,
        "present": 2,
        "missing": 0,
        "notRequired": 0,
    }


def test_gdp_palmi_cer_si_recupera_da_download_diretto_quando_xml_non_espone_nome(monkeypatch, tmp_path):
    generated = crea_certificato_cifratura_test(tmp_path / "origine.cer")
    payload = Path(generated.path).read_bytes()
    calls: list[str] = []

    def fake_catalog():
        record = {
            "codice_download": "0800570152",
            "codice_interno": "0910401",
            "descrizione": "Giudice di Pace - Palmi",
            "tipo_ministero": "GP",
            "comune": "Palmi",
            "nome_certificato_cifra": "",
            "certificato_mimetype": "application/octet-stream",
        }
        return {"0910401": record, "0800570152": record}

    def fake_request(url, *, timeout=pst_cifratura.PST_DOWNLOAD_TIMEOUT_SECONDS):
        calls.append(url)
        return payload

    monkeypatch.setattr(pst_cifratura, "_ministero_cert_catalog", fake_catalog)
    monkeypatch.setattr(pst_cifratura, "_request_bytes", fake_request)

    info = pst_cifratura.scarica_certificato_cifratura_ufficio(
        "0910401",
        cache_dir=tmp_path / "cache",
        force_refresh=True,
    )

    assert info.codice_ufficio == "0800570152"
    assert calls
    assert "codiceUfficio=0800570152" in calls[0]
    assert "0800570152_Giudice%20di%20Pace%20-%20Palmi.cer" in calls[0]
    assert (tmp_path / "cache" / "0800570152.cer").exists()
