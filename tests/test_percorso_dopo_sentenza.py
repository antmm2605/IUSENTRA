"""Lettura del fascicolo: dopo la sentenza della causa, il percorso secondo l'esito per il cliente (caso Alessi)."""

from pct.fascicolo_lettura.percorso import identificativi, percorso_dopo_sentenza

INTESTAZIONE = {"tipo": "LAVORO", "cliente": "Alessi Giovanna", "rg": "2539/2025",
                "parti": {"ricorrente": ["Alessi Giovanna"], "resistente": ["Ministero dell'Istruzione e del Merito"]}}


def _documenti(esito):
    return {"sentenza": {"etichetta": "Sentenza", "data_it": "07/10/2026", "esito": esito}}


def test_vinta_contro_lo_stato_porta_alla_realizzazione():
    percorso = percorso_dopo_sentenza(INTESTAZIONE, _documenti({"esito_sentenza": "accoglimento", "spese_sentenza": "condanna;importo=250,00;distrazione"}))
    assert percorso["per_il_cliente"] == "favorevole" and percorso["strada"] == "realizzazione"
    assert percorso["spese"] == {"regolazione": "condanna", "importo": "250,00", "distrazione": True}
    norme = [n for passo in percorso["passi"] for n in passo["norme"]]
    assert "art. 14 D.L. 669/1996" in norme and "art. 93 c.p.c." in norme


def test_persa_dal_ricorrente_porta_all_appello_nel_rito_del_lavoro():
    percorso = percorso_dopo_sentenza(INTESTAZIONE, _documenti({"esito_sentenza": "rigetto"}))
    assert percorso["per_il_cliente"] == "sfavorevole" and percorso["strada"] == "impugnazione"
    assert "art. 434 c.p.c." in percorso["rimedi"][0]["norme"]


def test_senza_esito_letto_nessun_percorso():
    assert percorso_dopo_sentenza(INTESTAZIONE, _documenti({})) is None


def test_identificativi_del_registro():
    assert identificativi(["art. 285 c.p.c.", "art. 11 R.D. 1611/1933", "art. 14 D.L. 669/1996", "art. 112 c.p.a."]) == (
        "cpc_285", "rd1611_art11", "dl669_art14", "cpa_112")


def test_la_data_della_sentenza_non_e_quella_di_un_precedente_citato():
    from pct.fascicolo_lettura.documenti import documenti

    fonti = [{"oggetto_id": "S1", "categoria": "ruolo", "campo": "numero_ruolo", "valore": "2539/2025", "verifica": "verificata", "posizione": 300},
             {"oggetto_id": "S1", "campo": "provvedimento", "valore": "2020-04-08", "verifica": "verificata", "posizione": 15459},
             {"oggetto_id": "S1", "campo": "data_atto", "valore": "2026-10-07", "verifica": "verificata", "posizione": 25751},
             {"oggetto_id": "S1", "campo": "esito_sentenza", "valore": "accoglimento", "verifica": "verificata", "posizione": 25000}]
    letti = documenti([{"id": "S1", "nome": "sentenza.pdf"}], [{"document_id": "S1", "document_label": "Sentenza", "status": "proposed"}],
                      rg="2539/2025", fonti=fonti)
    assert letti["sentenza"]["data"] == "2026-10-07" and letti["sentenza"]["esito"] == {"esito_sentenza": "accoglimento"}


def test_ruolo_dal_ricorso_dello_studio_se_le_parti_non_lo_dicono():
    intestazione = {"tipo": "LAVORO", "cliente": "Alessi Giovanna", "parti": {"controparte": ["MINISTERO ISTRUZIONE E DEL MERITO"]}}
    documenti_letti = {"sentenza": {"etichetta": "Sentenza", "data_it": "07/10/2026", "esito": {"esito_sentenza": "accoglimento"}},
                       "atto_introduttivo": {"etichetta": "Ricorso in materia di lavoro (art. 414 c.p.c.)"}}
    percorso = percorso_dopo_sentenza(intestazione, documenti_letti)
    assert percorso["ruolo_cliente"] == "ricorrente" and percorso["per_il_cliente"] == "favorevole"
    assert percorso["fonte_ruolo"].startswith("atto introduttivo dello studio") and percorso["strada"] == "realizzazione"
