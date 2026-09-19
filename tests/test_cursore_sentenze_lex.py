"""Il giro automatico delle sentenze non deve ricominciare da capo per sei documenti guasti."""

from __future__ import annotations

from pathlib import Path

from pct import cursore_sentenze_lex as cursore


def _mtime_finto(mappa: dict[str, int]):
    def leggi(percorso) -> int:
        return int(mappa.get(str(percorso), 0))

    return leggi


def _percorsi(*nomi: str) -> list[Path]:
    return [Path(nome) for nome in nomi]


def test_primo_giro_senza_segnaposto_legge_tutto():
    percorsi = _percorsi("/a.json", "/b.json")
    mtime = _mtime_finto({"/a.json": 100, "/b.json": 200})

    scelti, dettaglio = cursore.documenti_da_esaminare(
        percorsi, cursore.StatoCursore(), mtime_di=mtime
    )

    assert scelti == percorsi
    assert dettaglio["modalita"] == "integrale"
    assert dettaglio["documenti_nuovi"] == 2


def test_il_cursore_avanza_solo_sui_documenti_letti_bene():
    mtime = _mtime_finto({"/a.json": 100, "/b.json": 200, "/c.json": 300})

    stato = cursore.aggiorna_stato(
        cursore.StatoCursore(),
        letti_senza_errore=_percorsi("/a.json", "/c.json"),
        falliti={"/b.json": "JSON illeggibile"},
        mtime_di=mtime,
    )

    assert stato.mtime_ns == 300
    assert "/b.json" in stato.in_errore
    assert stato.in_errore["/b.json"].tentativi == 1


def test_il_documento_fallito_torna_nel_giro_anche_se_il_cursore_lo_ha_superato():
    mtime = _mtime_finto({"/a.json": 100, "/b.json": 200, "/c.json": 300})
    stato = cursore.aggiorna_stato(
        cursore.StatoCursore(),
        letti_senza_errore=_percorsi("/a.json", "/c.json"),
        falliti={"/b.json": "JSON illeggibile"},
        mtime_di=mtime,
    )

    scelti, dettaglio = cursore.documenti_da_esaminare(
        _percorsi("/a.json", "/b.json", "/c.json"), stato, mtime_di=mtime
    )

    # Solo il guasto: gli altri due sono sotto il cursore e non si rileggono.
    assert scelti == _percorsi("/b.json")
    assert dettaglio["documenti_ripresi"] == 1
    assert dettaglio["saltati_dal_cursore"] == 2
    assert dettaglio["modalita"] == "incrementale"


def test_dopo_i_tentativi_massimi_il_documento_e_sospeso_ma_resta_dichiarato():
    mtime = _mtime_finto({"/b.json": 200})
    stato = cursore.StatoCursore()
    for _ in range(cursore.TENTATIVI_MASSIMI):
        stato = cursore.aggiorna_stato(
            stato,
            letti_senza_errore=[],
            falliti={"/b.json": "JSON illeggibile"},
            mtime_di=mtime,
        )

    scelti, dettaglio = cursore.documenti_da_esaminare(
        _percorsi("/b.json"), stato, mtime_di=mtime
    )

    assert scelti == []
    assert dettaglio["saltati_perche_sospesi"] == 1

    riepilogo = cursore.riepilogo(stato)
    assert riepilogo["sospesi"] == 1
    # Non si scarta nulla in silenzio: il documento e' nominato con il motivo.
    assert riepilogo["documenti_sospesi"][0]["percorso"] == "/b.json"
    assert riepilogo["documenti_sospesi"][0]["errore"] == "JSON illeggibile"


def test_un_documento_rigenerato_riparte_dai_tentativi():
    stato = cursore.StatoCursore()
    for _ in range(cursore.TENTATIVI_MASSIMI):
        stato = cursore.aggiorna_stato(
            stato,
            letti_senza_errore=[],
            falliti={"/b.json": "JSON illeggibile"},
            mtime_di=_mtime_finto({"/b.json": 200}),
        )
    assert cursore.riepilogo(stato)["sospesi"] == 1

    # Il file cambia: merita una lettura nuova.
    scelti, _ = cursore.documenti_da_esaminare(
        _percorsi("/b.json"), stato, mtime_di=_mtime_finto({"/b.json": 999})
    )

    assert scelti == _percorsi("/b.json")


def test_il_segnaposto_sopravvive_al_giro_su_disco(tmp_path: Path):
    stato = cursore.StatoCursore(mtime_ns=4242, percorso_piu_recente="/c.json")
    stato = cursore.aggiorna_stato(
        stato,
        letti_senza_errore=[],
        falliti={"/b.json": "JSON illeggibile"},
        mtime_di=_mtime_finto({"/b.json": 200}),
    )

    assert cursore.scrivi_stato(tmp_path, stato) is True
    riletto = cursore.leggi_stato(tmp_path)

    assert riletto.mtime_ns == 4242
    assert riletto.in_errore["/b.json"].tentativi == 1
    assert riletto.in_errore["/b.json"].errore == "JSON illeggibile"


def test_un_segnaposto_di_versione_sconosciuta_non_viene_creduto(tmp_path: Path):
    percorso = cursore.percorso_stato(tmp_path)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text('{"versione": "vecchia", "mtime_ns": 999}', encoding="utf-8")

    # Meglio una scansione integrale che fidarsi di un formato non riconosciuto.
    assert cursore.leggi_stato(tmp_path).mtime_ns == 0


def test_un_giro_con_errori_lascia_comunque_il_segnaposto_avanzato(tmp_path: Path):
    """La regressione vera: prima bastava un documento guasto e il giro
    successivo rileggeva l'intero archivio, ogni dieci minuti, per sempre."""

    mtime = _mtime_finto({"/a.json": 100, "/b.json": 200, "/c.json": 300})
    stato = cursore.aggiorna_stato(
        cursore.leggi_stato(tmp_path),
        letti_senza_errore=_percorsi("/a.json", "/c.json"),
        falliti={"/b.json": "JSON illeggibile"},
        mtime_di=mtime,
    )
    cursore.scrivi_stato(tmp_path, stato)

    scelti, dettaglio = cursore.documenti_da_esaminare(
        _percorsi("/a.json", "/b.json", "/c.json"),
        cursore.leggi_stato(tmp_path),
        mtime_di=mtime,
    )

    assert len(scelti) == 1
    assert dettaglio["documenti_catalogati"] == 3
    assert dettaglio["saltati_dal_cursore"] == 2
