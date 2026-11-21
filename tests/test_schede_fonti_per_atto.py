"""Norme dei modelli d'atto: proposte dall'atto specifico, ritiro delle proposte nate dal solo prefisso,
collegamenti con base certa e materie senza doppioni (collaudo a vista del 21/11/2026)."""
from __future__ import annotations

from pct.schede_fonti.proposte import AUTORE_RITIRO, _suggerimenti, fonti_suggerite, ritira_suggerimenti_superati
from pct.schede_fonti.repository import RepositorySchedeFonti
from pct.template_atti_legal_sources import template_atti_sources_for_model


def _articoli(code, name):
    return {row["article"] for row in template_atti_sources_for_model(model_code=code, model_name=name)}


def test_art_700_non_si_propone_ai_cautelari_tipici():
    for code, name in [("CAU_005", "Ricorso per sequestro conservativo"), ("CAU_007", "Ricorso per accertamento tecnico preventivo"),
                       ("CAU_010", "Ricorso possessorio di reintegrazione o manutenzione"),
                       ("CAU_012", "Denuncia di nuova opera o di danno temuto"), ("CAU_002", "Reclamo cautelare"),
                       ("CAU_014", "Istanza di sospensione della delibera impugnata")]:
        assert "art. 700 c.p.c." not in _articoli(code, name), code
        assert "artt. 669-bis e ss. c.p.c." in _articoli(code, name), code  # procedimento cautelare uniforme sì
    assert "art. 700 c.p.c." in _articoli("TMP-CAUT-004", "Ricorso cautelare d'urgenza ex art. 700")


def test_norma_tipica_di_ogni_cautelare():
    assert "art. 671 c.p.c." in _articoli("CAU_005", "Ricorso per sequestro conservativo")
    assert "art. 696 c.p.c." in _articoli("CAU_007", "Ricorso per accertamento tecnico preventivo")
    possessorio = _articoli("CAU_010", "Ricorso possessorio di reintegrazione o manutenzione")
    assert {"art. 703 c.p.c.", "art. 1168 c.c.", "art. 1170 c.c."} <= possessorio
    assert {"art. 1171 c.c.", "art. 1172 c.c.", "art. 688 c.p.c."} <= _articoli("CAU_012", "Denuncia di nuova opera o di danno temuto")
    assert "art. 669-terdecies c.p.c." in _articoli("CAU_002", "Reclamo cautelare")
    assert {"art. 1137 c.c.", "art. 2378 c.c."} <= _articoli("CAU_014", "Istanza di sospensione della delibera impugnata")
    assert "art. 1137 c.c." in _articoli("LOC_010", "Impugnazione di delibera condominiale")
    assert "art. 2378 c.c." not in _articoli("LOC_010", "Impugnazione di delibera condominiale")


def test_prefisso_non_basta_per_le_norme_d_articolo():
    assert "art. 703 c.p.c." not in _articoli("CIV_ORD_001", "Atto di citazione ordinario")
    assert "art. 163 c.p.c." in _articoli("CIV_ORD_001", "Atto di citazione ordinario")
    assert "art. 163 c.p.c." not in _articoli("BAN_001", "Richiesta di documentazione e diffide all’intermediario")
    assert "art. 167 c.p.c." not in _articoli("PEN_012", "Costituzione di parte civile")
    assert "art. 167 c.p.c." not in _articoli("STR_013", "Costituzione in mora del fideiussore")
    assert "art. 163 c.p.c." not in _articoli("PEN_006", "Lista testimoni e citazione dei testi")
    assert "art. 1168 c.c." not in _articoli("LAV_003", "Ricorso per impugnazione del licenziamento e reintegrazione")
    # le fonti generali restano per prefisso: il codice di rito per ogni atto civile, il rito del lavoro per i ricorsi
    assert "codice di procedura civile" in _articoli("CIV_ORD_031", "Nota spese")
    assert any("414" in a for a in _articoli("LAV_010", "Ricorso per mobbing o demansionamento"))
    assert not any("414" in a for a in _articoli("LAV_020", "Lettera di contestazione disciplinare"))


def test_suggerimenti_reali_solo_dal_nome_dell_atto():
    attese = _suggerimenti()
    assert len(attese) < 20  # erano 153, quasi tutti nati dal prefisso
    assert ("CAU_005", "codice_procedura_civile", "700") not in attese
    assert ("CIV_ORD_001", "codice_procedura_civile", "703") not in attese
    assert ("BAN_001", "codice_procedura_civile", "163") not in attese


def test_ritiro_idempotente_senza_toccare_le_decisioni(tmp_path):
    repo = RepositorySchedeFonti(tmp_path / "schede_fonti.sqlite")
    sbagliata = repo.apri_proposta("CAU_005", "codice_procedura_civile", "700", tipo="fonte_suggerita", motivo="vecchia")
    decisa = repo.apri_proposta("CAU_006", "codice_procedura_civile", "700", tipo="fonte_suggerita", motivo="vecchia")
    repo.decidi_proposta(decisa, "respinta", avvocato="Avv. Prova", nota="non pertinente")
    altra = repo.apri_proposta("CAU_007", "codice_procedura_civile", "999", tipo="norma_assente", motivo="assente")
    fonti_suggerite(repo)
    giusta = next(p for p in repo.proposte() if (p["scheda"], p["atto"], p["articolo"]) in _suggerimenti())

    simulate = ritira_suggerimenti_superati(repo, simula=True)
    assert [p["id"] for p in simulate] == [sbagliata] and len(repo.proposte()) >= 3
    ritirate = ritira_suggerimenti_superati(repo)
    assert [p["id"] for p in ritirate] == [sbagliata] and "prefisso" in ritirate[0]["motivo"]
    assert ritira_suggerimenti_superati(repo) == []
    righe = {p["id"]: p for stato in ("aperta", "respinta", "ritirata") for p in repo.proposte(stato=stato)}
    assert righe[sbagliata]["stato"] == "ritirata" and righe[sbagliata]["decisa_da"] == AUTORE_RITIRO and righe[sbagliata]["nota"]
    assert righe[decisa]["stato"] == "respinta" and righe[decisa]["decisa_da"] == "Avv. Prova"
    assert righe[altra]["stato"] == "aperta" and righe[giusta["id"]]["stato"] == "aperta"


def test_coda_nasconde_ritirate_e_superate_ma_non_le_decisioni_dello_studio(tmp_path):
    from pct.storage import StudioDB
    from pct.schede_fonti.decisioni import DecisioniStudio
    from web.services import schede_fonti_runtime as runtime

    db = tmp_path / "codici_leggi.sqlite"
    repo = RepositorySchedeFonti(db.with_name("schede_fonti.sqlite"))
    superata = repo.apri_proposta("CAU_005", "codice_procedura_civile", "700", tipo="fonte_suggerita", motivo="vecchia")
    fonti_suggerite(repo)
    studio = StudioDB(tmp_path / "studio.sqlite")
    righe = runtime._elenco(db, studio)
    assert str(superata) not in {p["id"] for p in righe}
    assert righe and all((p["scheda"], p["atto"], p["articolo"]) in _suggerimenti() for p in righe)
    ritira_suggerimenti_superati(repo)
    assert str(superata) not in {p["id"] for p in runtime._elenco(db, studio)}
    # una proposta già decisa dallo studio resta nella sua storia anche se poi il software la ritira
    giusta = next(p for p in righe)
    DecisioniStudio(studio).registra("proposta", [(giusta["id"], giusta["impronta"], {"esito": "respinta", "nota": "prova"})], "Avv. Prova")
    repo.ritira_proposta(int(giusta["id"]), autore=AUTORE_RITIRO, motivo="prova")
    decise = {p["id"]: p for p in runtime._elenco(db, studio)}
    assert decise[giusta["id"]]["stato"] == "respinta"


def test_atto_di_citazione_tmp_civ_001_ha_le_norme_della_citazione():
    from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE, riferimenti_schede
    from web.services.schede_fonti_catalogo import catalogo_modelli

    row = next(r for r in catalogo_modelli(CARTELLA_SCHEDE) if r["codice"] == "TMP-CIV-001")
    assert row["stato_norme"] == "associate" and row["schede_normative"] == ["CIV_ORD_001"]
    assert row["collegamento"].startswith("compilatore CIV_CIT_001")
    refs = riferimenti_schede(CARTELLA_SCHEDE, solo_scheda="CIV_ORD_001")
    articoli = {r.articolo for r in refs if r.atto == "codice_procedura_civile"}
    assert {"163", "163bis", "164", "165"} <= articoli
    assert any(r.articolo == "163" and "n. 7" in r.perche for r in refs)


def test_collegamenti_derivati_solo_con_base_certa():
    from web.services.schede_fonti_catalogo import catalog_from_records

    schede = {"CAU_005": {"titolo": "Ricorso per sequestro conservativo", "base_normativa": [{"atto": "codice_procedura_civile", "articolo": "671"}]},
              "CIV_ORD_001": {"titolo": "Atto di citazione ordinario", "modelli_compilatore": ["CIV_CIT_001"],
                              "base_normativa": [{"atto": "codice_procedura_civile", "articolo": "163"}]},
              "TRI_005": {"titolo": "Memorie, documenti e istanze in corso di causa tributaria", "base_normativa": [{"atto": "x", "articolo": "1"}]}}
    def rec(i, code, title, **kw):
        return {"global_template_id": "tpl_" + i * 20, "codice": code, "titolo": title, "source": "builtin_workspace", **kw}
    rows = [rec("a", "TMP-CAUT-006", "Ricorso per Sequestro Conservativo"),
            rec("b", "TMP-CIV-001", "Atto di citazione", link_compilatore_code="CIV_CIT_001", compiler_binding_source="link_compilatore_code"),
            rec("c", "PROVA-CIT-002", "Atto di citazione", link_compilatore_code="CIV_CIT_001", compiler_binding_source="link_compilatore_code", link_compilatore_tipo="fallback"),
            rec("d", "CIV_SUC_005", "Istanza di rinvio")]
    out = {r["codice"]: r for r in catalog_from_records(rows, schede)}
    assert out["TMP-CAUT-006"]["schede_normative"] == ["CAU_005"] and out["TMP-CAUT-006"]["collegamento"] == "stesso titolo della scheda"
    assert out["TMP-CIV-001"]["schede_normative"] == ["CIV_ORD_001"]
    assert out["PROVA-CIT-002"]["stato_norme"] == "da_associare"  # compilatore di ripiego: nessuna certezza
    assert out["CIV_SUC_005"]["stato_norme"] == "da_associare"  # un'istanza di rinvio civile non è la scheda tributaria


def test_materie_senza_doppioni():
    from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE
    from web.services.schede_fonti_catalogo import catalogo_modelli, materia_canonica

    assert materia_canonica("Diritto di famiglia") == materia_canonica("Famiglia e Persone") == "Famiglia e persone"
    materie = {r["materia"] for r in catalogo_modelli(CARTELLA_SCHEDE)}
    assert "Diritto di famiglia" not in materie and "Famiglia e Persone" not in materie and "Civile" not in materie


def test_tabelle_verificate_coerenti_con_catalogo_e_schede():
    from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE
    from web.services.schede_fonti_catalogo import catalogo_modelli, collegamenti_verificati, norme_atti, schede_index

    schede = schede_index(CARTELLA_SCHEDE)
    righe = catalogo_modelli(CARTELLA_SCHEDE)
    codici = {r["codice"].upper() for r in righe}
    assert set(collegamenti_verificati()) <= codici and set(collegamenti_verificati().values()) <= set(schede)
    in_tabella = [c for a in norme_atti().values() for c in a["modelli"]]
    assert len(in_tabella) == len(set(in_tabella)) and set(in_tabella) <= codici
    assert not set(in_tabella) & set(collegamenti_verificati())
    assert all(a["norme"] and all(n["atto"] and n["articolo"] and n["perche"] for n in a["norme"]) for a in norme_atti().values())
    da_associare = {r["codice"] for r in righe if r["stato_norme"] == "da_associare"}
    assert len(da_associare) < 90  # erano 282 codici (473 voci) il 21/11/2026
    # collegamenti dubbi esclusi: opposizione di terzo ex art. 404 e cassazione civile non vanno alle schede omonime
    assert collegamenti_verificati().get("TMP-IMP-006") is None and collegamenti_verificati().get("CIV_IMP_002") is None
    assert next(r for r in righe if r["codice"] == "TMP-IMP-006")["schede_normative"] == ["ATTO_OPPOSIZIONE_TERZO"]


def test_pannello_di_un_atto_senza_scheda_legge_le_norme_in_biblioteca(tmp_path):
    from pct.storage import StudioDB
    from tests.test_api_schede_fonti import _biblioteca
    from web.services import schede_fonti_runtime as runtime

    db = _biblioteca(tmp_path)
    riga = next(r for r in runtime._modelli() if r["codice"] == "TMP-IMP-001")
    dati = runtime.scheda(db, riga["id"], studio_db=StudioDB(tmp_path / "s.sqlite"))
    assert dati["codice"] == "TMP-IMP-001" and dati["schede_collegate"] == ["ATTO_APPELLO_CIVILE"]
    assert {n["articolo"] for n in dati["norme"]} == {"339", "342", "343", "345", "325", "327"}
    assert all(n["stato"] in {"presente", "articolo_assente", "atto_assente"} for n in dati["norme"])
    assert not dati["id"].startswith("tpl_") or dati["codice"] != dati["id"]


def test_atti_residui_con_fonti_integrate(tmp_path):
    from lex.normativa.biblioteca.acquisizione import acquisisci
    from web.services.schede_fonti_catalogo import norme_atti
    from web.services.schede_fonti_runtime import riferimenti_atti_senza_scheda

    atti = norme_atti()
    # «Dichiarazione 553»: è la dichiarazione del creditore assegnatario (art. 553 c.p.c. e art. 169-septies disp. att.),
    # non quella del terzo pignorato (art. 547 c.p.c.).
    assert {(n["atto"], n["articolo"]) for n in atti["ATTO_DICHIARAZIONE_553"]["norme"]} == {
        ("codice_procedura_civile", "553"), ("1368/1941", "169septies")}
    assert {n["articolo"] for n in atti["ATTO_ATTESTAZIONE_CONFORMITA"]["norme"]} == {"196octies", "196novies", "196undecies"}
    assert atti["ATTO_DEPOSITO_TELEMATICO"]["norme"][0]["articolo"] == "196quater"
    # Il R.D. 499/1929 manca dalla biblioteca locale: il passaggio notturno lo acquisisce da Normattiva per URN.
    esiti = {e.chiave: e for e in acquisisci(tmp_path / "vuota.sqlite", tmp_path / "pacchetti", simula=True,
                                              riferimenti=riferimenti_atti_senza_scheda()).esiti}
    assert esiti["rd_499_1929"].stato == "simulato"
