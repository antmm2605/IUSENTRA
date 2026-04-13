(function () {
  'use strict';

  var RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var synth = window.speechSynthesis || null;
  var recognition = null;
  var listening = false;

  function supportsRecognition() {
    return Boolean(RecognitionCtor);
  }

  function supportsSpeech() {
    return Boolean(synth);
  }

  function pickItalianVoice() {
    if (!supportsSpeech()) {
      return null;
    }
    var voices = synth.getVoices ? synth.getVoices() : [];
    if (!voices || !voices.length) {
      return null;
    }
    return voices.find(function (voice) {
      return String(voice.lang || '').toLowerCase().indexOf('it') === 0;
    }) || voices[0] || null;
  }

  function stopListening() {
    if (recognition) {
      recognition.onend = null;
      recognition.onerror = null;
      recognition.onresult = null;
      try {
        recognition.stop();
      } catch (error) {
        return;
      } finally {
        recognition = null;
        listening = false;
      }
    }
  }

  function startListening(options) {
    if (!supportsRecognition()) {
      return Promise.reject(new Error('Dettatura vocale non supportata su questo browser.'));
    }
    if (listening) {
      stopListening();
    }

    listening = true;
    recognition = new RecognitionCtor();
    recognition.lang = (options && options.lang) || 'it-IT';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    return new Promise(function (resolve, reject) {
      var finalText = '';
      recognition.onresult = function (event) {
        var interim = '';
        for (var i = event.resultIndex; i < event.results.length; i += 1) {
          var transcript = String(event.results[i][0].transcript || '').trim();
          if (event.results[i].isFinal) {
            finalText += (finalText ? ' ' : '') + transcript;
          } else {
            interim += transcript;
          }
        }
        if (options && typeof options.onTranscript === 'function') {
          options.onTranscript((finalText + ' ' + interim).trim(), Boolean(interim));
        }
      };
      recognition.onerror = function (event) {
        listening = false;
        recognition = null;
        reject(new Error('Riconoscimento vocale non disponibile: ' + String((event && event.error) || 'errore sconosciuto')));
      };
      recognition.onend = function () {
        listening = false;
        recognition = null;
        resolve(finalText.trim());
      };
      recognition.start();
    });
  }

  function cancelSpeech() {
    if (supportsSpeech()) {
      synth.cancel();
    }
  }

  function speak(text, options) {
    if (!supportsSpeech() || !text) {
      return false;
    }
    cancelSpeech();
    var utterance = new SpeechSynthesisUtterance(String(text));
    utterance.lang = (options && options.lang) || 'it-IT';
    utterance.rate = (options && options.rate) || 1;
    utterance.pitch = (options && options.pitch) || 1;
    var voice = pickItalianVoice();
    if (voice) {
      utterance.voice = voice;
    }
    synth.speak(utterance);
    return true;
  }

  if (supportsSpeech() && synth.onvoiceschanged !== undefined) {
    synth.onvoiceschanged = pickItalianVoice;
  }

  window.PctLexVoice = {
    cancelSpeech: cancelSpeech,
    speak: speak,
    startListening: startListening,
    stopListening: stopListening,
    supportsRecognition: supportsRecognition,
    supportsSpeech: supportsSpeech,
  };
})();
