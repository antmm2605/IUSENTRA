from pathlib import Path


def test_ui_react_espone_regia_operativa_e_payload_reale():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    data = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    assert "RegiaOperativaSection" in source
    assert "Regia Operativa" in source
    assert "Deposito non disponibile" not in source
    assert "RegiaActionCard" in source
    assert "preventivoHref" in source
    assert "conferimentoHref" in source
    assert "proformaHref" in source
    assert "paymentHref" in source
    assert "Contesto economico" in source
    assert "Evidence pack" in source
    assert "mock_fallback: false" in data
    assert "regia: normalizeRegia(payload.regia)" in data
    assert "href={item.href || '#'}" not in source


def test_ui_mostra_dati_regia_senza_placeholder_operativi():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    regia = source[source.index("function RegiaOperativaSection"):source.index("function fLabel")]
    assert "Rossi" not in regia
    assert "Bianchi" not in regia
    assert "Cliente demo" not in regia
    assert "Dati fittizi" not in regia
    assert "ACQUISITO" in regia
    assert "Checklist non ancora generata" not in regia
    assert "Nessuno slot documentale generato" not in regia
