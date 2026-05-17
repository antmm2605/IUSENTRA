from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_ai_locale_react_usa_local_signer_del_pc_e_non_solo_server():
    actions = read("frontend/src/features/impostazioni/components/SettingsActions.tsx")
    local_ai = read("frontend/src/features/impostazioni/localAi.ts")
    guard = read("web/static/js/react-ai-local-guard.js")
    shell = read("web/templates/react_shell.html")

    assert "checkLocalAiViaLocalSigner" in actions
    assert "prepareLocalAiViaLocalSigner" in actions
    assert "void onRefreshAi()" not in actions
    assert "void onPrepareAi(false)" not in actions
    assert "/ai/status" in local_ai
    assert "/ai/bootstrap" in local_ai
    assert "/api/v1/ui/impostazioni/ai/status" in guard
    assert "/api/v1/ui/impostazioni/ai/bootstrap" in guard
    assert "react-ai-local-guard.js" in shell


def test_ai_locale_spiega_ollama_mancante_e_modelli_automatici():
    constants = read("frontend/src/features/impostazioni/constants.ts")
    actions = read("frontend/src/features/impostazioni/components/SettingsActions.tsx")
    local_ai = read("frontend/src/features/impostazioni/localAi.ts")
    guard = read("web/static/js/react-ai-local-guard.js")
    ui_text = "\n".join([constants, actions, local_ai, guard])

    assert "prepara Ollama" in constants
    assert "sceglie i modelli" in constants
    assert "Verifica PC e modelli" in actions
    assert "Prepara AI locale" in actions
    assert "Ollama non risulta pronto su questo PC" in ui_text
    assert "EmbeddingGemma 300M" in ui_text
    assert "embeddinggemma:300m" in ui_text
    assert "Qwen 3.5 minimo" in constants
    assert "Lascia Automatico" in constants
    assert "Modello conversazione" not in ui_text
    assert "Modello ricerca documenti" not in ui_text


def test_ai_locale_mobile_rileva_dispositivo_e_non_finge_installer_ollama():
    actions = read("frontend/src/features/impostazioni/components/SettingsActions.tsx")
    local_ai = read("frontend/src/features/impostazioni/localAi.ts")
    css = read("frontend/src/features/impostazioni/ImpostazioniPage.css")

    assert "detectMobileAiInstallPlan" in actions
    assert "MobileAiSetupPanel" in actions
    assert "AI su telefono e tablet" in actions
    assert "Apri Lex AI" in actions
    assert "Prepara su questo dispositivo" in actions
    assert "Scarica Ollama ufficiale" in actions
    assert "installazione locale solo con app mobile compatibile e autorizzata" in local_ai
    assert "userAgentData" in local_ai
    assert "deviceMemory" in local_ai
    assert "hardwareConcurrency" in local_ai
    assert "navigator.storage?.estimate" in local_ai
    assert "Risorse non dichiarate dal dispositivo" in local_ai
    assert "canPrepareOnThisDevice = !isPortable" in local_ai
    assert ".iu-settings-mobile-ai" in css
    assert ".iu-settings-mobile-ai__grid" in css


def test_ai_locale_bridge_locale_verifica_prestazioni_pc_e_setup_ollama():
    bridge = read("tools/local_ai_host_bridge.py")
    local_ai = read("frontend/src/features/impostazioni/localAi.ts")
    agents = read("AGENTS.md")

    assert "def detect_hardware" in bridge
    assert "def resolve_models" in bridge
    assert "ram_gb" in bridge
    assert "disk_free_gb" in bridge
    assert "gpu_name" in bridge
    assert "asset_download_url" in bridge
    assert "OllamaSetup.exe" in bridge
    assert "hardware_profile" in local_ai
    assert "AI Locale da Impostazioni sempre governata dal PC dello studio" in agents
