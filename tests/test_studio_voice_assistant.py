from __future__ import annotations

import json
import re
from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value.lower(), flags=re.UNICODE)).strip().removeprefix("studio ")


def test_studio_voice_assistant_catalogo_copre_comandi_base_e_aggiunte():
    catalog = json.loads(Path("frontend/src/studioVoiceCommands.json").read_text(encoding="utf-8"))
    commands = [
        *catalog["routeCommands"],
        *catalog["specialCommands"],
    ]
    phrases = [phrase for command in commands for phrase in command["phrases"]]
    normalized_phrases = {_norm(phrase) for phrase in phrases}
    base = catalog["baseUserCommands"]
    added = [phrase for phrase in phrases if _norm(phrase) not in {_norm(item) for item in base}]

    assert not [phrase for phrase in phrases if re.match(r"^(Studio|IUSENTRA)[\s,.;:-]+", phrase, re.IGNORECASE)]
    assert not [phrase for phrase in phrases if re.search(r"\bStudio\b", phrase, re.IGNORECASE)]
    assert len(base) >= 40
    assert len(added) >= 100
    assert len(catalog["routeCommands"]) >= 45
    for phrase in base:
        assert _norm(phrase) in normalized_phrases

    required = {
        "panoramica",
        "regia-operativa",
        "ricerca-studio",
        "calendario",
        "fascicoli",
        "pec",
        "servizi-telematici",
        "polisweb",
        "pdp",
        "pat",
        "ptt",
        "redazione-atti",
        "ricerca-legale",
        "sito-studio",
        "impostazioni",
        "amministrazione",
        "registro-gdpr",
    }
    assert required <= {command["id"] for command in catalog["routeCommands"]}
    assert any(command["kind"] == "new-client-flow" for command in catalog["specialCommands"])
    assert any(command["kind"] == "edit-current-record" for command in catalog["specialCommands"])
    assert any(command["kind"] == "note-flow" for command in catalog["specialCommands"])
    assert any(command["kind"] == "dictation" for command in catalog["specialCommands"])
    assert any(command["kind"] == "search" for command in catalog["specialCommands"])
    assert any(command["kind"] == "lex" for command in catalog["specialCommands"])
    dictation = next(command for command in catalog["specialCommands"] if command["kind"] == "dictation")
    clienti = next(command for command in catalog["routeCommands"] if command["id"] == "clienti")
    assert "apri i clienti" in clienti["phrases"]
    for phrase in [
        "modifica cliente",
        "modifica clienti",
        "modifica soggetto",
        "modifica soggetti e parti",
    ]:
        assert any(phrase in command["phrases"] for command in catalog["specialCommands"])
    for phrase in [
        "detta cliente",
        "detta soggetto",
        "detta scadenziario",
        "detta agenda",
        "detta Ricerca",
        "Scrivi",
        "Scrivi qui",
    ]:
        assert phrase in dictation["phrases"]


def test_studio_voice_assistant_file_senza_mojibake_e_collegato():
    files = [
        Path("frontend/src/components/StudioVoiceAssistant.tsx"),
        Path("frontend/src/components/layout/TopBar.css"),
        Path("frontend/src/studioVoiceAssistant.ts"),
        Path("frontend/src/studioVoiceCommands.json"),
        Path("frontend/src/components/layout/TopBar.tsx"),
        Path("web/static/js/pct-lex-assistant-voice.js"),
    ]
    mojibake_markers = "".join(chr(code) for code in (0x00C3, 0x00C2, 0xFFFD))
    mojibake_after_a_circumflex = "".join(chr(code) for code in (0x20AC, 0x2122, 0x0153))
    bad = re.compile(f"[{re.escape(mojibake_markers)}]|{re.escape(chr(0x00E2))}[{re.escape(mojibake_after_a_circumflex)}]")
    for file in files:
        content = file.read_text(encoding="utf-8")
        assert not bad.search(content), file

    component = files[0].read_text(encoding="utf-8")
    assert "/api/v1/ui/clienti/voce/crea" in component
    assert "captureVoiceSignature" in component
    assert "extractSpokenPin" in component
    assert "data-voice-command-count" in component
    assert "VOICE_CALIBRATION_SECONDS = 30" in component
    assert "ACTIVATION_PHRASE_STORAGE_KEY" in component
    assert "normalizeActivationPhrase" in component
    assert "onBlur={() => setActivationPhrase" in component
    assert "VoicePanelTab" in component
    assert "Comandi autorizzati" in component
    assert "Richieste operative" in component
    assert "calibrationRemaining" in component
    assert "Testo rilevato durante la lettura" in component
    assert "scoreCalibrationTranscript" in component
    assert "CALIBRATION_KEYWORD_GROUPS" in component
    assert "ios centro" in component
    assert "VOICE_CALIBRATION_MIN_TEXT_MATCH" in component
    assert "calibrationQualityMessage" in component
    assert "Registrazione da ripetere" in component
    assert "Qualità lettura" in component
    assert "acceptedWakePhrases" in component
    assert "`lo ${normalizedPhrase}`" in component
    assert "Voce registrata" in component
    assert "Voce non registrata" in component
    assert "data-microphone-permission" in component
    assert "Microfono: {microphoneStateLabel}" in component
    assert "Verifica microfono" in component
    assert "readMicrophonePermission" in component
    assert "hasNamedAudioInputDevice" in component
    assert "enumerateDevices" in component
    assert "requestMicrophoneStream" in component
    assert "microphoneGrantedButStreamBlockedMessage" in component
    assert "detectBrowserRuntime" in component
    assert "browser incorporato" in component
    assert "Copia pagina" in component
    assert "Verifica di nuovo" in component
    assert "showMicrophoneHelp && !microphoneBlocked" in component
    assert "permissionStatus.onchange" in component
    assert "visibilitychange" in component
    assert "devicechange" in component
    assert "verifyMicrophoneAccess" in component
    assert "microphoneLastCheckedAt" in component
    assert "Ultimo controllo:" in component
    assert "Ultimo tentativo reale:" in component
    assert "Nessun profilo vocale viene salvato finché il permesso non risulta consentito." in component
    assert "data-microphone-unlock" in component
    assert "Sblocca microfono in Chrome" in component
    assert "Copia indirizzo sblocco" in component
    assert "copyTextToClipboard" in component
    assert "Se Chrome non apre la scheda" in component
    assert "Ho sbloccato, verifica" in component
    assert "Riprova indirizzo locale" in component
    assert "microphoneRegistrationBlocked" in component
    assert "chrome://settings/content/siteDetails" in component
    assert "Richiamo vocale pronto" in component
    assert "Sessione operativa attiva" in component
    assert "Studio non in ascolto" in component
    assert "Stop sessione" in component
    assert "Disattiva ascolto" in component
    assert "LISTENING_SESSION_STORAGE_KEY" in component
    assert "OPERATIVE_SESSION_STORAGE_KEY" in component
    assert "loadListeningSessionActive" in component
    assert "loadOperativeSessionActive" in component
    assert "saveListeningSessionActive(false)" in component
    assert "saveOperativeSessionActive(false)" in component
    assert "if (!options.restarted && !options.restored)" in component
    assert "return { wakeOnly: false, commandText: '' }" in component
    assert "return { wakeOnly: false, commandText: transcript }" not in component
    activation_block = component.split("const activateOperativeSession", 1)[1].split("const pauseOperativeSession", 1)[0]
    stop_block = component.split("const pauseOperativeSession", 1)[1].split("const openLex", 1)[0]
    pending_dictation_block = component.split("const preparePendingFieldDictation", 1)[1].split("const startActiveFieldDictation", 1)[0]
    assert "setOpen(true)" not in activation_block
    assert "setOpen(true)" not in stop_block
    assert "setOpen(true)" not in pending_dictation_block
    assert "pauseOperativeSession" in component
    assert "Comandi sospesi. ${voiceRecallReadyMessage()}" in component
    assert "Riprendo il richiamo vocale" in component
    assert "Pronuncia direttamente i comandi; di’ “stop” quando hai finito." in component
    assert "voiceRecallReadyMessage" in component
    assert "Di’ “stop” per bloccare la sessione operativa e tornare al richiamo." in component
    assert "Con il richiamo vocale pronto, attiva la sessione" in component
    assert "resolveCurrentRecordEditRoute" in component
    assert "PIN_LISTENING_PROMPT" in component
    assert "MAX_PIN_VOICE_ATTEMPTS = 3" in component
    assert "VOICE_MATCH_MIN_SCORE = 0.08" in component
    assert "VOICE_MIN_AUDIBLE_ENERGY" in component
    assert "voiceActivationAccepted" in component
    assert "speakItalianAndWait" in component
    assert "Controllo il tono di voce. Pronuncia" in component
    assert "captureVoiceSignature(VOICE_ACTIVATION_SAMPLE_MS)" in component
    assert "speakItalianThen(PIN_LISTENING_PROMPT" in component
    assert "ma il codice non è corretto. Ripeti solo le cifre." in component
    assert "Non ho letto un codice valido. Ripeti solo le cifre." in component
    assert "Non ho ricevuto il PIN. Ripeti solo le cifre." in component
    assert "Ho letto ${digits.split" in component
    assert "repeatPinListening" in component
    assert "showManualPinEntry" in component
    assert "Sto ascoltando automaticamente" in component
    assert "fino a tre tentativi" in component
    assert "pinVoiceCheckActive" in component
    assert "Verifica PIN vocale" in component
    assert "PIN in ascolto" in component
    assert "PIN corretto. ${voiceRecallReadyMessage()}" in component
    assert "lastCommandAction" in component
    assert "COMMAND_FEEDBACK_STORAGE_KEY" in component
    assert "startActiveFieldDictation" in component
    assert "insertDictationIntoActiveField" in component
    assert "tryPassiveFieldDictation" in component
    assert "if (tryPassiveFieldDictation(commandTranscript))" in component
    assert "pendingFieldDictationRef" in component
    assert "selectInserted" in component
    assert "Dettatura pronta: dimmi ora il testo da inserire nel campo selezionato." in component
    assert "stripPendingDictationActivationText" in component
    assert "IusentraVoiceInput" in component
    assert "insertTextIntoTarget" in component
    assert "Dettatura attiva nel campo selezionato" in component
    assert "NOTE_TRIGGER_STORAGE_KEY" in component
    assert "NOTES_STORAGE_KEY" in component
    assert "Comando note personalizzato" in component
    assert "Note vocali" in component
    assert "Consenti promemoria" in component
    assert "VOICE_NOTE_TIME_ZONE" in component
    assert "parseVoiceNoteReminder" in component
    assert "MAX_VOICE_NOTE_TIMEOUT_MS" in component
    assert "fine note" in component
    assert "Cosa ho ascoltato" in component
    assert "Frase consigliata per registrare bene il tono" in component
    assert "setClientMessage(message)" in component
    assert "| 'review' |" in component
    assert "askClientReviewChoice" in component
    assert "Vuoi annullare tutto oppure modificare nome, cognome o codice fiscale?" in component
    assert "parseClientCorrectionField" in component
    assert "isVoiceNegativeConfirmation" in component
    assert "Inserimento cliente annullato. Nessun cliente è stato aggiunto." in component
    assert "speakItalian('Calibrazione voce avviata" not in component
    assert "Microfono non concesso dal browser" in component
    assert component.count('type="password"') >= 2
    assert "Nome" in component
    assert "Cognome" in component
    assert "Codice fiscale" in component
    assert "Conferma PIN" in component
    styles = files[1].read_text(encoding="utf-8")
    assert "data-iusentra-voice-preview" in styles

    engine = files[2].read_text(encoding="utf-8")
    assert "| 'dictation'" in engine
    assert "| 'edit-current-record'" in engine
    assert "note-flow" in engine
    assert "voiceDictationPrefixMatch" in engine
    assert "stripVoiceDictationCommand(input: string)" in engine
    assert "'cerca'," in engine
    assert "'trova'," in engine
    assert "'ricerca'," in engine
    assert "COMMAND_OPTIONAL_WORDS" not in engine
    assert "commandComparableSignature" not in engine
    assert "VOICE_NOTE_TIME_ZONE = 'Europe/Rome'" in engine
    assert "parseVoiceNoteReminder" in engine
    assert "isVoiceNoteStartCommand(input: string, customPhrase?: string)" in engine
    assert "stripVoiceNoteStartCommand(input: string, customPhrase?: string)" in engine
    assert "looseVoiceToken" in engine
    assert "loosePhraseSignature" in engine
    assert "NEGATIVE_CONFIRMATION_WORDS" in engine
    assert "parseClientCorrectionField" in engine
    assert "modifica codice fiscale" in engine
    assert "MAX_VOICE_NOTE_TIMEOUT_MS = 2_147_000_000" in engine
    assert "NOTE_REMINDER_OFFSET_MS = 10 * 60 * 1000" in engine

    topbar = Path("frontend/src/components/layout/TopBar.tsx").read_text(encoding="utf-8")
    assert "lazy(() => import('../StudioVoiceAssistant'))" in topbar
    assert "<StudioVoiceAssistant activePath={activePath} />" in topbar

    lex_voice = Path("web/static/js/pct-lex-assistant-voice.js").read_text(encoding="utf-8")
    assert "window.IusentraVoiceInput" in lex_voice
    assert "startDictationForActiveField" in lex_voice
    assert "lastVoiceInputTarget" in lex_voice
    assert "microphoneGrantedButBlockedMessage" in lex_voice
    assert "formatDictationText" in lex_voice
    assert "createInlineDictationPreview" in lex_voice
    assert "data-iusentra-voice-preview" in lex_voice
    assert "selectInsertedText" in lex_voice
    assert "uppercaseFirstFieldLetter" in lex_voice
    assert "normalizeFieldValueAfterDictation" in lex_voice
    assert "compactNumericFieldText" in lex_voice
    assert "isCompactNumericVoiceField" in lex_voice
    assert "(?<=\\d)\\s+(?=\\d)" in lex_voice
    assert "replaceSpokenNumberWords" in lex_voice
    assert "compactDocumentCodeFieldText" in lex_voice
    assert "isDocumentNumberVoiceField" in lex_voice
    assert "doc[_\\s-]*numero" in lex_voice
    assert "numero[_\\s-]*doc" in lex_voice
    assert "doppio zero" in lex_voice
    assert "triplo zero" in lex_voice
    assert "normalizeEmailDictationText" in lex_voice
    assert "^([a-z]{2,})-([a-z]{1,5}\\d+@)" in lex_voice
    assert "normalizeUrlDictationText" in lex_voice
    assert "replace(/^Www\\./i, 'www.')" in lex_voice
    assert "parseItalianVoiceDate" in lex_voice
    assert "replaceItalianDateNumberWords" in lex_voice
    assert "isDateVoiceField" in lex_voice
    assert "nascita|rilascio|scadenza|decorrenza|udienza|termine" in lex_voice
    assert "type === 'date'" in lex_voice
    assert "isSelectVoiceElement" in lex_voice
    assert "selectOptionFromVoiceText" in lex_voice
    assert "sesso|genere" in lex_voice
    assert "maschile" in lex_voice
    assert "femminile" in lex_voice
    assert "codice[_\\s-]*fiscale" in lex_voice
    assert "type === 'email'" in lex_voice
    assert "type === 'tel'" in lex_voice
    assert "type === 'number'" in lex_voice

    lex_assistant = Path("web/static/js/pct-lex-assistant.js").read_text(encoding="utf-8")
    assert "Controllo microfono Lex" in lex_assistant
    assert "onStart" in lex_assistant


def test_studio_voice_assistant_api_crea_cliente_minimo_obbligatorio(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/clienti/voce/crea",
            json={
                "nome": "Mario",
                "cognome": "Rossi",
                "codice_fiscale": "RSSMRA80A01H501U",
            },
        )
        duplicate = client.post(
            "/api/v1/ui/clienti/voce/crea",
            json={
                "nome": "Mario",
                "cognome": "Rossi",
                "codice_fiscale": "RSSMRA80A01H501U",
            },
        )
        list_response = client.get("/api/v1/ui/clienti")

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["redirect"] == f"/clienti/{payload['id']}"
    assert "Rossi Mario" in payload["message"]
    mojibake_prefix = chr(0x00C3)
    assert mojibake_prefix not in payload["message"]

    assert list_response.status_code == 200
    items = list_response.get_json()["items"]
    created = next(item for item in items if item["id"] == payload["id"])
    assert created["name"] == "Rossi Mario"
    assert created["fiscalId"] == "RSSMRA80A01H501U"

    assert duplicate.status_code == 400
    duplicate_payload = duplicate.get_json()
    assert duplicate_payload["ok"] is False
    assert "già presente" in duplicate_payload["message"]
    assert mojibake_prefix not in duplicate_payload["message"]


def test_studio_voice_assistant_api_richiede_tutti_i_campi_obbligatori(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/clienti/voce/crea",
            json={"nome": "Mario", "cognome": "", "codice_fiscale": "RSSMRA80A01H501U"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["errors"]["cognome"] == "Inserisci il cognome."
