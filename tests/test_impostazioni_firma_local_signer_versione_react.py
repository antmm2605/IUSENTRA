from pathlib import Path


def test_impostazioni_firma_mostra_versione_e_pacchetto_windows_ufficiale():
    source = Path(
        "frontend/src/features/impostazioni/components/SettingsActions.tsx"
    ).read_text(encoding="utf-8")
    styles = Path(
        "frontend/src/features/impostazioni/ImpostazioniPage.css"
    ).read_text(encoding="utf-8")

    assert "const publishedSignerVersion = asText(data.local_signer.version)" in source
    assert "const publishedWindowsFilename = asText(data.local_signer.windows_filename)" in source
    assert "Versione disponibile ${publishedSignerVersion}" in source
    assert "Installa o aggiorna su Windows" in source
    assert "Il pulsante scarica il pacchetto ufficiale corrente" in source
    assert "href={data.local_signer.downloads.windows}" in source
    assert "if (!result.ok) return" in source
    assert "1.6.100" not in source

    assert ".iu-settings-local-signer__head" in styles
    assert ".iu-settings-local-signer__download-note" in styles
    assert "grid-template-columns: minmax(0, 1fr) auto" in styles
    assert "grid-template-columns: 1fr" in styles
