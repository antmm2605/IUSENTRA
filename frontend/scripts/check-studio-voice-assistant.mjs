import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')
const catalog = JSON.parse(read('frontend/src/studioVoiceCommands.json'))

function fail(message) {
  console.error(`[studio-voice-assistant] ${message}`)
  process.exit(1)
}

const apostrophePattern = new RegExp(`[${String.fromCharCode(0x2019)}']`, 'g')
const mojibakeMarkers = `${String.fromCharCode(0x00c3)}${String.fromCharCode(0x00c2)}${String.fromCharCode(0xfffd)}`
const mojibakeAfterACircumflex = `${String.fromCharCode(0x20ac)}${String.fromCharCode(0x2122)}${String.fromCharCode(0x0153)}`
const mojibakePattern = new RegExp(`[${mojibakeMarkers}]|${String.fromCharCode(0x00e2)}[${mojibakeAfterACircumflex}]`)

function normalize(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(apostrophePattern, ' ')
    .toLocaleLowerCase('it-IT')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^studio\s+/, '')
    .replace(/^iusentra\s+/, '')
}

const routeCommands = catalog.routeCommands || []
const specialCommands = catalog.specialCommands || []
const commands = [...routeCommands.map((command) => ({ ...command, kind: 'route' })), ...specialCommands]
const allPhrases = commands.flatMap((command) => command.phrases || [])
const phraseSet = new Set(allPhrases.map(normalize))
const baseSet = new Set((catalog.baseUserCommands || []).map(normalize))
const added = allPhrases.filter((phrase) => !baseSet.has(normalize(phrase)))
const activationPrefixedPhrases = allPhrases.filter((phrase) => /^(Studio|IUSENTRA)[\s,.;:-]+/iu.test(String(phrase || '')))
const studioWordPhrases = allPhrases.filter((phrase) => /\bStudio\b/iu.test(String(phrase || '')))

if ((catalog.baseUserCommands || []).length < 40) fail('comandi vocali iniziali non completi')
if (activationPrefixedPhrases.length) fail(`frasi con prefisso di attivazione ancora visibile: ${activationPrefixedPhrases.slice(0, 5).join(', ')}`)
if (studioWordPhrases.length) fail(`frasi comando con parola Studio ancora visibile: ${studioWordPhrases.slice(0, 5).join(', ')}`)
for (const phrase of catalog.baseUserCommands || []) {
  if (!phraseSet.has(normalize(phrase))) fail(`comando iniziale non coperto: ${phrase}`)
}
if (added.length < 100) fail(`frasi aggiunte insufficienti: ${added.length}`)
if (routeCommands.length < 45) fail(`destinazioni insufficienti: ${routeCommands.length}`)
if (!specialCommands.some((command) => command.kind === 'new-client-flow')) fail('flusso nuovo cliente assente')
if (!specialCommands.some((command) => command.kind === 'edit-current-record')) fail('comandi modifica cliente/soggetto assenti')
if (!specialCommands.some((command) => command.kind === 'note-flow')) fail('flusso note vocali assente')
if (!specialCommands.some((command) => command.kind === 'dictation')) fail('dettatura unica sul campo attivo assente')
if (!specialCommands.some((command) => command.kind === 'search')) fail('ricerca vocale assente')
if (!specialCommands.some((command) => command.kind === 'lex')) fail('apertura Lex assente')
const stopCommand = specialCommands.find((command) => command.kind === 'stop')
if (!stopCommand?.phrases?.includes('stop')) fail('comando vocale "stop" assente per sospendere la sessione operativa')
const clientiCommand = routeCommands.find((command) => command.id === 'clienti')
if (!clientiCommand?.phrases?.includes('apri i clienti')) fail('variante reale "apri i clienti" assente dal catalogo esplicito')
const dictationCommand = specialCommands.find((command) => command.kind === 'dictation')
if (!dictationCommand?.phrases?.includes('Scrivi')) fail('variante operativa "Scrivi" assente dal catalogo')
if (!dictationCommand?.phrases?.includes('Scrivi qui')) fail('variante operativa "Scrivi qui" assente dal catalogo')
if (dictationCommand?.phrases?.some((phrase) => /\bStudio\b/iu.test(String(phrase || '')))) fail('la dettatura non deve riproporre Studio nei comandi autorizzati')

const requiredIds = [
  'panoramica',
  'regia-operativa',
  'ricerca-studio',
  'calendario',
  'fascicoli',
  'pec',
  'servizi-telematici',
  'polisweb',
  'pdp',
  'pat',
  'ptt',
  'redazione-atti',
  'ricerca-legale',
  'sito-studio',
  'impostazioni',
  'amministrazione',
  'registro-gdpr',
]
const ids = new Set(routeCommands.map((command) => command.id))
for (const id of requiredIds) {
  if (!ids.has(id)) fail(`destinazione obbligatoria assente: ${id}`)
}

const filesToCheck = [
  'frontend/src/components/StudioVoiceAssistant.tsx',
  'frontend/src/components/layout/TopBar.css',
  'frontend/src/studioVoiceAssistant.ts',
  'frontend/src/studioVoiceCommands.json',
]
for (const relativePath of filesToCheck) {
  const content = read(relativePath)
  if (mojibakePattern.test(content)) fail(`testo non UTF-8 leggibile in ${relativePath}`)
}

const component = read('frontend/src/components/StudioVoiceAssistant.tsx')
if (!component.includes('/api/v1/ui/clienti/voce/crea')) fail('endpoint cliente vocale non collegato')
if (!component.includes('captureVoiceSignature')) fail('registrazione tono voce non presente')
if (!component.includes('extractSpokenPin')) fail('lettura PIN vocale non presente')
if (!component.includes('data-voice-command-count')) fail('metrica comandi non esposta per verifica browser')
if (!component.includes('VOICE_CALIBRATION_SECONDS = 30')) fail('calibrazione tono voce inferiore a 30 secondi')
if (!component.includes('ACTIVATION_PHRASE_STORAGE_KEY')) fail('frase di attivazione personalizzabile assente')
if (!component.includes('normalizeActivationPhrase')) fail('frase di attivazione vuota non normalizzata')
if (!component.includes('VoicePanelTab')) fail('sezioni a tab dell’assistente assenti')
if (!component.includes('Comandi autorizzati')) fail('sezione comandi autorizzati assente')
if (!component.includes('Richieste operative')) fail('sezione richieste operative assente')
if (!component.includes('calibrationRemaining')) fail('timer registrazione voce assente')
if (!component.includes('Testo rilevato durante la lettura')) fail('trascrizione live della registrazione assente')
if (!component.includes('scoreCalibrationTranscript')) fail('controllo corrispondenza frase assente')
if (!component.includes('CALIBRATION_KEYWORD_GROUPS')) fail('controllo qualità lettura a parole chiave assente')
if (!component.includes('ios centro')) fail('alias realistici per IUSENTRA assenti nella calibrazione')
if (!component.includes('VOICE_CALIBRATION_MIN_TEXT_MATCH')) fail('soglia qualità calibrazione voce assente')
if (!component.includes('calibrationQualityMessage')) fail('messaggio qualità calibrazione voce assente')
if (!component.includes('Registrazione da ripetere')) fail('blocco salvataggio con lettura scarsa assente')
if (!component.includes('Qualità lettura')) fail('qualità lettura non visibile nel pannello')
if (!component.includes('acceptedWakePhrases')) fail('varianti controllate della frase di attivazione assenti')
if (!component.includes('Voce registrata')) fail('stato profilo registrato assente')
if (!component.includes('Voce non registrata')) fail('stato profilo mancante assente')
if (!component.includes('data-microphone-permission')) fail('stato permesso microfono non esposto per verifica browser')
if (!component.includes('Microfono: {microphoneStateLabel}')) fail('stato microfono leggibile assente')
if (!component.includes('Verifica microfono')) fail('pulsante verifica microfono assente')
if (!component.includes('readMicrophonePermission')) fail('lettura permesso microfono reale assente')
if (!component.includes('verifyMicrophoneAccess')) fail('verifica microfono prima della registrazione assente')
if (!component.includes('microphoneLastCheckedAt')) fail('esito ultimo controllo microfono non memorizzato')
if (!component.includes('Ultimo controllo:')) fail('ultimo controllo microfono non visibile')
if (!component.includes('Ultimo tentativo reale:')) fail('tentativo reale microfono non visibile quando Chrome blocca')
if (!component.includes('Nessun profilo vocale viene salvato finché il permesso non risulta consentito.')) fail('avviso profilo non salvato senza microfono assente')
if (!component.includes('data-microphone-unlock')) fail('flusso di sblocco microfono Chrome assente')
if (!component.includes('Sblocca microfono in Chrome')) fail('azione sblocco microfono Chrome assente')
if (!component.includes('Copia indirizzo sblocco')) fail('azione copia indirizzo sblocco Chrome assente')
if (!component.includes('copyTextToClipboard')) fail('fallback copia indirizzo sblocco Chrome assente')
if (!component.includes('Se Chrome non apre la scheda')) fail('istruzione pratica quando Chrome blocca la scheda assente')
if (!component.includes('Ho sbloccato, verifica')) fail('azione verifica dopo sblocco assente')
if (!component.includes('Riprova indirizzo locale')) fail('riprova su indirizzo locale alternativo assente')
if (!component.includes('microphoneRegistrationBlocked')) fail('registrazione voce non bloccata quando Chrome nega il microfono')
if (!component.includes('chrome://settings/content/siteDetails')) fail('indirizzo sblocco Chrome specifico per sito assente')
if (!component.includes('Richiamo vocale pronto')) fail('stato richiamo vocale pronto assente')
if (!component.includes('Sessione operativa attiva')) fail('stato sessione operativa attiva assente')
if (!component.includes('Studio non in ascolto')) fail('stato ascolto inattivo assente')
if (!component.includes('Stop sessione')) fail('pulsante stop sessione assente')
if (!component.includes('Disattiva ascolto')) fail('pulsante disattiva ascolto assente')
if (!component.includes('LISTENING_SESSION_STORAGE_KEY')) fail('ascolto persistente tra pagine assente')
if (!component.includes('OPERATIVE_SESSION_STORAGE_KEY')) fail('sessione operativa persistente tra pagine assente')
if (!component.includes('loadListeningSessionActive')) fail('ripresa ascolto dopo cambio pagina assente')
if (!component.includes('loadOperativeSessionActive')) fail('ripresa sessione operativa dopo cambio pagina assente')
if (!component.includes('saveListeningSessionActive(false)')) fail('disattivazione ascolto non cancella la sessione')
if (!component.includes('saveOperativeSessionActive(false)')) fail('stop/disattivazione non cancellano la sessione operativa')
if (!component.includes('if (!options.restarted && !options.restored)')) fail('ripristino ascolto/cambio pagina non deve aprire il pannello')
if (!component.includes("return { wakeOnly: false, commandText: '' }")) fail('frasi senza richiamo non devono attivare la sessione operativa')
if (component.includes('return { wakeOnly: false, commandText: transcript }')) fail('una frase qualunque attiverebbe la sessione senza richiamo')
if (/const activateOperativeSession[\s\S]*?setOpen\(true\)[\s\S]*?const pauseOperativeSession/.test(component)) fail('il richiamo vocale non deve aprire automaticamente il pannello')
if (/const pauseOperativeSession[\s\S]*?setOpen\(true\)[\s\S]*?const openLex/.test(component)) fail('il comando stop non deve aprire automaticamente il pannello')
if (/const preparePendingFieldDictation[\s\S]*?setOpen\(true\)[\s\S]*?const startActiveFieldDictation/.test(component)) fail('la dettatura in ascolto continuo non deve aprire automaticamente il pannello')
if (!component.includes('pauseOperativeSession')) fail('stop sessione operativa assente')
if (!component.includes('Comandi sospesi. ${voiceRecallReadyMessage()}')) fail('stato comandi sospesi assente')
if (!component.includes('Pronuncia direttamente i comandi; di’ “stop” quando hai finito.')) fail('testo sessione operativa non chiarisce lo stop')
if (!component.includes('voiceRecallReadyMessage')) fail('messaggio richiamo vocale centralizzato assente')
if (!component.includes('Di’ “stop” per bloccare la sessione operativa e tornare al richiamo.')) fail('messaggio richiamo non spiega il comando stop')
if (!component.includes('Con il richiamo vocale pronto, attiva la sessione')) fail('pannello comandi non chiarisce sessione senza frase di attivazione')
if (!component.includes('PIN_LISTENING_PROMPT')) fail('messaggio PIN vocale centralizzato assente')
if (!component.includes('MAX_PIN_VOICE_ATTEMPTS = 3')) fail('ripetizione automatica PIN vocale assente')
if (!component.includes('VOICE_MATCH_MIN_SCORE = 0.08')) fail('soglia tono voce ancora troppo rigida')
if (!component.includes('VOICE_MIN_AUDIBLE_ENERGY')) fail('controllo presenza voce udibile assente')
if (!component.includes('voiceActivationAccepted')) fail('accettazione tono voce prudente ma non bloccante assente')
if (!component.includes('speakItalianAndWait')) fail('guida vocale prima del controllo tono assente')
if (!component.includes('Controllo il tono di voce. Pronuncia')) fail('attivazione ascolto non avvisa a voce prima del campionamento')
if (!component.includes('captureVoiceSignature(VOICE_ACTIVATION_SAMPLE_MS)')) fail('campione tono voce di attivazione non usa durata dedicata')
if (!component.includes('speakItalianThen(PIN_LISTENING_PROMPT')) fail('PIN vocale non viene pronunciato prima dell’ascolto')
if (!component.includes('ma il codice non è corretto. Ripeti solo le cifre.')) fail('PIN errato non guida la ripetizione automatica')
if (!component.includes('Non ho letto un codice valido. Ripeti solo le cifre.')) fail('PIN non capito non viene spiegato e ripetuto')
if (!component.includes('Non ho ricevuto il PIN. Ripeti solo le cifre.')) fail('PIN non ricevuto non riapre l’ascolto automaticamente')
if (!component.includes('Ho letto ${digits.split')) fail('PIN errato non ripete il codice letto')
if (!component.includes('repeatPinListening')) fail('riapertura automatica ascolto PIN assente')
if (!component.includes('showManualPinEntry')) fail('PIN manuale non separato dal flusso vocale automatico')
if (!component.includes('Sto ascoltando automaticamente')) fail('stato PIN vocale automatico non visibile')
if (!component.includes('fino a tre tentativi')) fail('tentativi PIN automatici non spiegati')
if (!component.includes('pinVoiceCheckActive')) fail('stato visivo dedicato alla verifica PIN vocale assente')
if (!component.includes('Verifica PIN vocale')) fail('PIN vocale non visibile come stato principale durante la verifica')
if (!component.includes('PIN in ascolto')) fail('pulsante attivazione non viene disambiguato durante il PIN vocale')
if (!component.includes('resolveCurrentRecordEditRoute')) fail('comandi modifica cliente/soggetto non risolvono il record corrente')
if (!component.includes('COMMAND_FEEDBACK_STORAGE_KEY')) fail('memoria ultimo comando eseguito assente')
if (!component.includes('startActiveFieldDictation')) fail('comando di dettatura non collegato al campo attivo')
if (!component.includes('insertDictationIntoActiveField')) fail('dettatura inline non inserisce direttamente nel campo selezionato')
if (!component.includes('tryPassiveFieldDictation')) fail('dettatura libera sul campo attivo assente')
if (!component.includes('if (tryPassiveFieldDictation(commandTranscript))')) fail('frase libera non viene scritta nel campo attivo prima del messaggio comando non riconosciuto')
if (!component.includes('pendingFieldDictationRef')) fail('attesa testo dopo comando di scrittura assente')
if (!component.includes('Dettatura pronta: dimmi ora il testo da inserire nel campo selezionato.')) fail('feedback attesa dettatura non visibile')
if (!component.includes('stripPendingDictationActivationText')) fail('pulizia frase di attivazione nella dettatura pendente assente')
if (!component.includes('IusentraVoiceInput')) fail('servizio dettatura unico non usato dall’assistente')
if (!component.includes('insertTextIntoTarget')) fail('inserimento diretto nel campo tramite servizio unico assente')
if (!component.includes('selectInserted')) fail('testo dettato non evidenziato direttamente nel campo compilato')
if (!component.includes('Dettatura attiva nel campo selezionato')) fail('feedback dettatura campo attivo assente')
if (!component.includes('NOTE_TRIGGER_STORAGE_KEY')) fail('comando note personalizzabile assente')
if (!component.includes('NOTES_STORAGE_KEY')) fail('salvataggio note locali assente')
if (!component.includes('Comando note personalizzato')) fail('campo comando note personalizzato assente')
if (!component.includes('Note vocali')) fail('tab note vocali assente')
if (!component.includes('Consenti promemoria')) fail('pulsante permesso promemoria assente')
if (!component.includes('Europe/Rome') && !component.includes('VOICE_NOTE_TIME_ZONE')) fail('fuso orario Roma assente dalle note')
if (!component.includes('parseVoiceNoteReminder')) fail('estrazione data e ora note assente')
if (!component.includes('MAX_VOICE_NOTE_TIMEOUT_MS')) fail('protezione timer lunghi assente')
if (!component.includes('fine note')) fail('comando chiusura fine note assente')
if (!component.includes('Cosa ho ascoltato')) fail('registro ascolti visibile assente')
if (!component.includes('Frase consigliata per registrare bene il tono')) fail('frase consigliata per calibrazione assente')
if (!component.includes("| 'review' |")) fail('stato revisione conferma cliente assente')
if (!component.includes('askClientReviewChoice')) fail('scelta annulla/modifica cliente assente dopo risposta negativa')
if (!component.includes('Vuoi annullare tutto oppure modificare nome, cognome o codice fiscale?')) fail('messaggio revisione cliente non guidato')
if (!component.includes('parseClientCorrectionField')) fail('scelta campo cliente da modificare assente')
if (!component.includes('isVoiceNegativeConfirmation')) fail('negazione conferma cliente non gestita')
if (component.includes("speakItalian('Calibrazione voce avviata")) fail('la calibrazione vocale non deve riprodurre audio sopra la registrazione')
if (!component.includes('blocco è ancora memorizzato in Chrome')) fail('messaggio microfono bloccato non spiega il blocco salvato da Chrome')
if ((component.match(/type="password"/g) || []).length < 2) fail('PIN vocale non mascherato nei campi di registrazione/verifica')

const topbar = read('frontend/src/components/layout/TopBar.tsx')
if (!topbar.includes("lazy(() => import('../StudioVoiceAssistant'))")) fail('assistente vocale non caricato in modo pigro')
if (!topbar.includes('<StudioVoiceAssistant activePath={activePath} />')) fail('assistente vocale non montato nella barra')

const voiceInput = read('web/static/js/pct-lex-assistant-voice.js')
if (!voiceInput.includes('createInlineDictationPreview')) fail('anteprima della dettatura direttamente nel campo assente')
if (!voiceInput.includes('data-iusentra-voice-preview')) fail('stato visivo del campo in dettatura assente')
if (!voiceInput.includes('selectInsertedText')) fail('testo finale dettato non resta selezionato nel campo')
if (!voiceInput.includes('uppercaseFirstFieldLetter')) fail('iniziale maiuscola del campo dettato assente')
if (!voiceInput.includes('normalizeFieldValueAfterDictation')) fail('normalizzazione finale valore campo dettato assente')
if (!voiceInput.includes('compactNumericFieldText')) fail('compattazione numeri dettati nei campi numerici/telefono assente')
if (!voiceInput.includes('isCompactNumericVoiceField')) fail('riconoscimento campi numerici/telefono per dettatura assente')
if (!voiceInput.includes('replaceSpokenNumberWords')) fail('conversione parole numeriche dettate assente')
if (!voiceInput.includes('compactDocumentCodeFieldText')) fail('compattazione codice documento alfanumerico assente')
if (!voiceInput.includes('isDocumentNumberVoiceField')) fail('riconoscimento campo numero documento assente')
if (!voiceInput.includes('doc[_\\s-]*numero') || !voiceInput.includes('numero[_\\s-]*doc')) fail('alias reali doc_numero/numero_doc per numero documento assenti')
if (!voiceInput.includes('doppio zero') || !voiceInput.includes('triplo zero') || !voiceInput.includes('cento')) fail('zeri e cento dettati non gestiti nei campi numerici')
if (!voiceInput.includes('(?<=\\d)\\s+(?=\\d)')) fail('spazi tra cifre dettate non rimossi senza perdere zeri iniziali')
if (!voiceInput.includes('normalizeEmailDictationText')) fail('normalizzazione email/PEC dettata assente')
if (!voiceInput.includes('^([a-z]{2,})-([a-z]{1,5}\\d+@)') || !voiceInput.includes('gmail.com')) fail('caso email con falso trattino prima dei numeri non protetto')
if (!voiceInput.includes('normalizeUrlDictationText')) fail('normalizzazione URL/sito web dettato assente')
if (!voiceInput.includes("replace(/^Www\\./i, 'www.')")) fail('sito web dettato con Www maiuscolo non normalizzato')
if (!voiceInput.includes('parseItalianVoiceDate')) fail('conversione data italiana per input data assente')
if (!voiceInput.includes('replaceItalianDateNumberWords')) fail('numeri italiani dettati nelle date non gestiti')
if (!voiceInput.includes('isDateVoiceField')) fail('riconoscimento automatico campi data assente')
if (!voiceInput.includes('nascita|rilascio|scadenza|decorrenza|udienza|termine')) fail('campi data non riconosciuti da descrizione italiana')
if (!voiceInput.includes("type === 'date'")) fail('campi data non intercettati dalla dettatura')
if (!voiceInput.includes('isSelectVoiceElement')) fail('campi a scelta/select non supportati dalla dettatura')
if (!voiceInput.includes('selectOptionFromVoiceText')) fail('selezione opzioni da voce assente')
if (!voiceInput.includes('sesso|genere') || !voiceInput.includes('maschile') || !voiceInput.includes('femminile')) fail('campo sesso/genere maschile-femminile non normalizzato')
if (!voiceInput.includes('codice[_\\s-]*fiscale')) fail('codice fiscale dettato non viene uniformato in maiuscolo')
if (!voiceInput.includes("type === 'email'") || !voiceInput.includes("type === 'tel'") || !voiceInput.includes("type === 'number'")) fail('eccezioni email/telefono/numeri nella normalizzazione dettatura assenti')

const topbarCss = read('frontend/src/components/layout/TopBar.css')
if (!topbarCss.includes('data-iusentra-voice-preview')) fail('evidenza visiva del campo in dettatura assente nel CSS')

const engine = read('frontend/src/studioVoiceAssistant.ts')
if (!engine.includes('looseVoiceToken')) fail('normalizzazione singolare/plurale comandi assente')
if (!engine.includes('loosePhraseSignature')) fail('firma comandi tollerante assente')
if (engine.includes('COMMAND_OPTIONAL_WORDS') || engine.includes('commandComparableSignature')) fail('normalizzazione generica degli articoli non consentita: usare frasi esplicite nel catalogo')
if (!engine.includes('NEGATIVE_CONFIRMATION_WORDS')) fail('negazione conferma cliente assente')
if (!engine.includes('parseClientCorrectionField')) fail('riconoscimento campo cliente da correggere assente')
if (!engine.includes('modifica codice fiscale')) fail('correzione codice fiscale da voce assente')
if (!engine.includes("| 'dictation'")) fail('tipo comando dettatura assente dal motore comandi')
if (!engine.includes('voiceDictationPrefixMatch')) fail('riconoscimento testo dopo comando di scrittura assente')
if (!engine.includes('stripVoiceDictationCommand(input: string)')) fail('estrazione testo dettato inline assente')
if (!engine.includes("| 'edit-current-record'")) fail('tipo comando modifica record assente dal motore comandi')
if (!engine.includes("'cerca',") || !engine.includes("'trova',") || !engine.includes("'ricerca',")) fail('ricerca vocale senza ripetere Studio assente')

const lexVoice = read('web/static/js/pct-lex-assistant-voice.js')
if (!lexVoice.includes('window.IusentraVoiceInput')) fail('servizio vocale unico non esportato')
if (!lexVoice.includes('startDictationForActiveField')) fail('dettatura sul campo attivo non esportata')
if (!lexVoice.includes('lastVoiceInputTarget')) fail('memoria ultimo campo selezionato assente')
if (!lexVoice.includes('microphoneGrantedButBlockedMessage')) fail('messaggio Chrome consentito ma riconoscimento bloccato assente')
if (!lexVoice.includes('formatDictationText')) fail('normalizzazione dettatura centralizzata assente')

const lexAssistant = read('web/static/js/pct-lex-assistant.js')
if (!lexAssistant.includes('Controllo microfono Lex')) fail('Lex non usa il controllo microfono comune prima dell’ascolto')
if (!lexAssistant.includes('onStart')) fail('Lex passa ad ascolto prima dell’avvio reale del riconoscimento')

function createDomHarness() {
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
  }
  sandbox.Event = function Event(type, options = {}) {
    this.type = type
    this.bubbles = Boolean(options.bubbles)
  }
  sandbox.CustomEvent = function CustomEvent(type, options = {}) {
    this.type = type
    this.detail = options.detail
  }
  sandbox.document = {
    activeElement: null,
    addEventListener() {},
    contains() {
      return true
    },
    execCommand() {
      return false
    },
  }
  sandbox.window = {
    document: sandbox.document,
    navigator: {},
    setTimeout,
    clearTimeout,
    dispatchEvent() {},
  }
  vm.createContext(sandbox)
  vm.runInContext(voiceInput, sandbox, { filename: 'pct-lex-assistant-voice.js' })
  return sandbox
}

function makeField(sandbox, attrs = {}) {
  const attributes = new Map(Object.entries(attrs.attributes || {}))
  const element = {
    tagName: attrs.tagName || 'INPUT',
    name: attrs.name || '',
    id: attrs.id || '',
    value: attrs.value || '',
    disabled: false,
    readOnly: false,
    isContentEditable: false,
    selectionStart: String(attrs.value || '').length,
    selectionEnd: String(attrs.value || '').length,
    options: attrs.options || [],
    closest() {
      return null
    },
    dispatchEvent() {},
    focus() {
      sandbox.document.activeElement = element
    },
    getAttribute(name) {
      const key = String(name || '')
      if (key === 'type') return attrs.type || ''
      if (key === 'name') return element.name
      if (key === 'id') return element.id
      return attributes.get(key) || ''
    },
    removeAttribute(name) {
      attributes.delete(String(name || ''))
    },
    setAttribute(name, value) {
      attributes.set(String(name || ''), String(value))
    },
    setSelectionRange(start, end) {
      element.selectionStart = start
      element.selectionEnd = end
    },
  }
  return element
}

function assertInsertedValue(label, field, spokenText, expected) {
  voiceHarness.window.IusentraVoiceInput.insertTextIntoTarget(field, spokenText, { selectInserted: true })
  if (field.value !== expected) {
    fail(`${label}: atteso "${expected}", ottenuto "${field.value}"`)
  }
}

const voiceHarness = createDomHarness()
assertInsertedValue('telefono con zeri iniziali', makeField(voiceHarness, { type: 'tel', name: 'telefono' }), 'zero zero cento', '00100')
assertInsertedValue('numero documento alfanumerico', makeField(voiceHarness, { type: 'text', name: 'numero_documento' }), 'CA 61 007 P', 'CA61007P')
assertInsertedValue('numero documento doc_numero reale', makeField(voiceHarness, { type: 'text', name: 'doc_numero' }), 'CA 61 007 P', 'CA61007P')
assertInsertedValue('email dettata con falso trattino', makeField(voiceHarness, { type: 'email', name: 'email' }), 'ant-mm 2605@gmail.com', 'antmm2605@gmail.com')
assertInsertedValue('email con trattino legittimo', makeField(voiceHarness, { type: 'email', name: 'email' }), 'studio-legale@example.com', 'studio-legale@example.com')
assertInsertedValue('sito web dettato', makeField(voiceHarness, { type: 'url', name: 'sito_web' }), 'Www.Marco.rossi.it', 'www.marco.rossi.it')
assertInsertedValue('data italiana dettata', makeField(voiceHarness, { type: 'date', name: 'data_nascita' }), 'tredici giugno duemila ventisei', '2026-06-13')
const genderField = makeField(voiceHarness, {
  tagName: 'SELECT',
  name: 'sesso',
  options: [
    { value: '', text: '' },
    { value: 'M', text: 'Maschile' },
    { value: 'F', text: 'Femminile' },
  ],
})
voiceHarness.window.IusentraVoiceInput.insertTextIntoTarget(genderField, 'femminile', { selectInserted: true })
if (genderField.value !== 'F') fail(`campo sesso/genere: atteso "F", ottenuto "${genderField.value}"`)

console.log(`[studio-voice-assistant] ${allPhrases.length} frasi, ${added.length} aggiunte, ${routeCommands.length} destinazioni`)
