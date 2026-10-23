# 04F Browser dictation: disclosure audit (review-ready, NOT a legal review)

Package 04F, branch `feat/04f-dictation-disclosure`. Scope: the BROWSER dictation path only (Web Speech API through `window.SpeechRecognition` / `webkitSpeechRecognition`). Server speech (Whisper, Kyutai) is out of scope and stays gated for R1.4.

**Status: engineering audit and proposal only.** No legal, privacy or native-language review has been done or is recorded here. The wording in section 5 is a PROPOSAL and has NOT been applied to the product copy. The live browser speech-to-text check and the correction-burden measurement are NOT RUN (section 7). Nothing in this document is legal advice or a compliance statement.

## 1. Where the feature, its permission prompt, its data flow and its disclosure appear

| # | Place | File | What happens |
|---|---|---|---|
| 1 | Prepare first-message form | `frontend/components/agent/AgentPrepareWorkspace.tsx` -> `DictationControl` | Mic button, language select, disclosure paragraph under the goal field |
| 2 | Prepare conversation composer | `frontend/components/agent/AgentComposer.tsx` -> `components/ui/Composer.tsx` -> `DictationControl` | Same control in the composer footer |
| 3 | Interview Practice answer composer | `frontend/components/interview/InterviewAnswerComposer.tsx` -> `Composer` -> `DictationControl` | Same control, answer field |
| 4 | The control itself | `frontend/components/ui/DictationControl.tsx` | Renders the mic toggle, the language select, an `aria-live` status line and the disclosure paragraph (`data-testid="dictation-browser-notice"`, key `dictation.browserNotice`). The paragraph is now also the accessible description of the mic button (04F) |
| 5 | Recognition lifecycle | `frontend/lib/speech/useDictation.ts` | Starts and stops the adapter, commits ONLY final segments to the field, shows interim text as a transient preview, aborts on unmount |
| 6 | Browser adapter | `frontend/lib/speech/browserAdapter.ts` | The only code that touches `SpeechRecognition`. Sets `lang` to the selected tag, `continuous` and `interimResults` true. Maps the engine's error codes to safe kinds (04F adds `language-not-supported`) |
| 7 | Language list and choice | `DICTATION_LANGUAGES` in `DictationControl.tsx` (seven: en-US, de-DE, fr-FR, es-ES, it-IT, pt-PT, nl-NL; Russian is not offered; `src/speech/policy.py` `PRODUCT_SPEECH_LANGUAGES` is the backend copy) and `lib/speech/useDictationLanguage.ts` (remembers the tag in `localStorage` key `ask4mo.dictationLang`; the tag is a device convenience, not content) | Endonym labels from the locale registry |
| 8 | Settings | `frontend/components/settings/LanguageSettings.tsx` | A dictation language select with help text (`settings.dictationLanguageHelp`). **No disclosure is shown here** (see 4.6) |
| 9 | Admin policy | `frontend/lib/speech/useSpeechPolicy.ts` -> `GET /api/v1/speech/capabilities` | Reads two booleans. An explicit `browser_stt_allowed = false` replaces the control with the note `dictation.disabledByPolicy`. No audio, language or transcript is sent |
| 10 | Help Center | `help.dict1q..dict8a` (`frontend/lib/i18n/messages/w96/help/<locale>.ts`) | Eight Q and A pairs about dictation |
| 11 | Voice help | `voice.hSpeakA`, `voice.hPrivacyA` (`lib/i18n/messages/<locale>.ts`) | Speaking an answer; what voice is not used for |
| 12 | Privacy page | `privacy.voiceTurnBased` (`lib/i18n/messages/w96/legal.ts`) | One sentence about turn-based voice and browser engines |
| 13 | Trust page, onboarding, marketing | `trust.noAudioDesc`, `onboarding.privacyAudio`, `marketing.why3Body` | Short "no audio stored" statements |
| 14 | Microphone permission prompt | Owned by the BROWSER, not Ask4Mo | The page never calls `getUserMedia` (asserted by a vitest source check and by `e2e/dictation.spec.ts` and `e2e/dictation-disclosure-04f.spec.ts`); the browser asks when `SpeechRecognition.start()` runs. Ask4Mo cannot change the prompt wording. The disclosure (4) is on screen BEFORE the first click, so it precedes the prompt |

## 2. What is true in code (data flow on the browser path)

Verified by reading the code and by tests (`frontend/tests/dictation-disclosure-04f.test.tsx`, section "browser dictation sends no audio to Ask4Mo servers"):

1. **Ask4Mo sends no audio to its own servers on this path.** `browserAdapter.ts`, `useDictation.ts`, `types.ts` and `DictationControl.tsx` contain no `fetch`, `XMLHttpRequest`, `WebSocket`, `sendBeacon`, `MediaRecorder`, `getUserMedia`, `AudioContext`, `Blob`, `FormData` or `RTCPeerConnection` (comments stripped; the test fails if one appears). The frontend API client has no call to `/speech/transcriptions` or `/speech/synthesis`; its only speech call is `GET /speech/capabilities`. The Playwright test records every request made during a dictation interaction: none targets a speech endpoint, none has an audio or multipart body, no WebSocket opens, `getUserMedia` is never called.
2. **What the browser engine receives from Ask4Mo:** the recognition language tag only (one of seven fixed BCP-47 tags). Whether the engine runs on the device or sends the audio to the browser vendor is decided by the browser and is NOT visible to Ask4Mo.
3. **What Ask4Mo receives:** only text, and only when the candidate presses Send or Submit. Dictation never submits (existing tests `dictation-no-autosubmit`, `e2e/dictation.spec.ts`). Final transcript segments are appended to the editable field; interim text is a preview and is never written to the field.
4. **Storage:** no audio, no transcript and no interim text is written to `localStorage`, `sessionStorage` or any server by the dictation code (existing test `does not write transcripts to localStorage`). The only stored value is the language tag.
5. **No inference from voice:** the adapter reads transcript text only; nothing analyses voice characteristics.
6. **Server speech is not reachable from this path.** `src/speech/policy.py` keeps `SERVER_SPEECH_PROVIDERS_AUTHORIZED = False`; the backend routes `POST /speech/transcriptions` and `/synthesis` exist but the browser UI never calls them. This package changes nothing there.
7. **Admin governance:** the control is hidden when Admin disables browser STT. While the policy is unknown (loading, signed out, offline) the control stays available, as before W12.4E.

## 3. Unambiguous engineering defects found and fixed in this package

| Defect | Fix | Tests |
|---|---|---|
| The browser's `language-not-supported` error fell into the generic bucket: the candidate saw "Dictation stopped unexpectedly" with no hint to change the dictation language | New safe kind `language-not-supported`, new key `dictation.languageNotSupported` in all eight catalogues (engineering translations, NOT native-reviewed), shown through the existing status line | vitest: `mapError`, production adapter with a mocked `SpeechRecognition`, control message; Playwright: message shown and typing still works |
| The disclosure paragraph was visible but not associated with the microphone button, so a screen-reader user pressing the button did not hear it | `aria-describedby` from the mic button to the disclosure paragraph | vitest `toHaveAccessibleDescription`; Playwright accessible-description check |

Checked and found already correct (no change): the disclosure is shown before the first microphone use (it is rendered whenever the control is, independent of any click), it stays visible while listening, after stop and after an error (re-readable), every dictation string exists in all eight locales (new parity test), permission denied, no microphone, no speech and network failures each show a localised message, the mic button and language select are labelled, unsupported browsers get an explicit note (not silence), and the language list is the bounded seven.

Found but NOT changed here, because the fix is copy and needs the reviewer (see 4 and 5): stale Help text (4.1), the `service-not-allowed` message (4.4), no disclosure on Settings (4.6).

## 4. NOT stated in the product, or inaccurate, for a qualified legal reviewer to consider

1. **Stale Help copy.** `help.dict6a` says that where speech recognition is unavailable "the microphone simply isn't shown"; `help.dict1a` says "If it isn't shown, your browser doesn't support it". In code the control is replaced by a visible note (`dictation.unsupported`) since P10B Wave 1. Present in all eight locales.
2. **Which providers.** The notice says "its provider" without naming who. In practice Chromium-based browsers generally send audio to a Google speech service and Safari to Apple's; Firefox does not offer the API by default. This is browser behaviour that changes by version and platform and was NOT verified here. The reviewer should decide whether naming vendors is accurate and maintainable or whether the generic wording must stay.
3. **On-device versus cloud.** Some browsers can recognise on the device for some languages. Ask4Mo cannot tell which applies, so "may send" is the honest hedge; the reviewer should confirm the hedge is sufficient.
4. **Permission-denied wording.** `permissionDenied` ("Microphone access was blocked") is also shown for the engine error `service-not-allowed`, which can mean the browser or an administrator policy blocks the speech SERVICE rather than the microphone. The text is slightly inaccurate in that case.
5. **Vendor retention and terms.** Nothing says that the vendor's retention, purpose limitation, human review, transfer outside the EEA, and any use of audio to improve its models are governed by the vendor's own terms, which Ask4Mo does not control or see. The Help text says "that processing is your browser's, not Ask4Mo's" but does not tell the candidate where to read those terms.
6. **Not shown where the language is chosen.** The Settings dictation language select (and the onboarding language step) carry no disclosure; only the control does. A candidate who chooses a dictation language never sees the notice until they open Prepare or Practice.
7. **No recorded acknowledgement.** The notice is information, not a consent capture: nothing records that the candidate saw it. Whether consent, or a recorded acknowledgement, or neither, is required for a feature the candidate starts explicitly is a legal question; this package changes no behaviour.
8. **Special-category and sensitive speech content.** Candidates may speak about health, disability, family or other sensitive facts. The audio goes to the vendor, not Ask4Mo, but the resulting text, once sent, is processed by Ask4Mo like typed text. Whether the notice should say so is for the reviewer.
9. **Minors and workplace use.** No age statement and no employer/shared-device statement near the control.
10. **Consistency of claims.** Several public statements say "Ask4Mo never stores audio" (`onboarding.privacyAudio`, `trust.noAudioDesc`). That is true for Ask4Mo; none of them mentions the browser vendor in the same sentence, while `dictation.browserNotice` and `help.dict8a` do. The reviewer should check that the shorter statements cannot be read as "audio never leaves your device".
11. **Em dash in `help.dict8a`** (all catalogues use it in some form): the marketing rules forbid em dashes in customer-facing marketing copy; Help is not marketing, so this is a style note only.
12. **Native-language review.** All seven non-English texts, including the new `languageNotSupported`, are engineering translations. `docs/production/MULTILINGUAL_RELEASE_QUALIFICATION.md` governs when they may be treated as reviewed.
13. **Russian.** Russian interface text exists but Russian is excluded from R1.0 and from speech; Russian speakers who set the interface to Russian see English (display fallback), and dictation offers no Russian. Out of scope here; recorded for completeness.

## 5. Proposed wording changes (NOT applied)

The proposal is a diff against the English catalogues in `docs/production/dictation/PROPOSED_COPY_CHANGES_04F.patch` (checked with `git apply --check` against this branch; it is NOT applied and must not be applied before the legal reviewer approves wording). Preview of the English strings:

```diff
--- dictation.browserNotice (en)
- Dictation uses your browser’s speech service, which may send your voice to its provider. Ask4Mo does not store your audio.
+ Dictation uses your browser’s speech service. Depending on your browser, your voice may be sent to the company that makes it and handled under its own privacy terms. Ask4Mo does not receive or store your audio. The text you dictate is treated like typed text once you send it.

--- help.dict1a (en), clause
- If it isn't shown, your browser doesn't support it — you can always type.
+ If it isn't available, a short note says so and you can always type.

--- help.dict6a (en), clause
- Where it isn't available, the microphone simply isn't shown and typing works as normal.
+ Where it isn't available, a short note replaces the microphone button and typing works as normal.

--- help.dict8a (en), clause
- Only the text you explicitly submit is sent — exactly like typing. Note that browser speech recognition may send audio to your browser/vendor's speech service to produce the transcript; that processing is your browser's, not Ask4Mo's.
+ Only the text you explicitly submit is sent to Ask4Mo, exactly like typing. Browser speech recognition may send your audio to the company that makes your browser to produce the transcript; that processing is done by your browser and its provider under its own privacy terms, not by Ask4Mo. Ask4Mo does not control or see it.

--- privacy.voiceTurnBased (en)
- Turn-based voice uses your browser or operating-system speech engines. Ask4Mo does not record or store your microphone audio.
+ Turn-based voice and dictation use your browser or operating-system speech engines, which may send your voice to their provider under its own privacy terms. Ask4Mo does not receive, record or store your microphone audio.
```

Not proposed because they need the reviewer's decision first: naming vendors (4.2), a pointer to vendor terms (4.5), a disclosure on the Settings select (4.6), any acknowledgement capture (4.7), sensitive-content wording (4.8). Translations of the proposal into the other seven locales are deliberately NOT drafted: they should follow the approved English wording.

## 6. Exact current disclosure text per language

Reproduced mechanically from the merged catalogues (`CATALOGS`, including the W9.6 fragments) at the time of this audit. `dictation.languageNotSupported` is the new 04F key.


### en (English)

- `dictation.start`: Start dictation
- `dictation.stop`: Stop dictation
- `dictation.listening`: Listening… speak, then review before sending.
- `dictation.heard`: Heard: {text}
- `dictation.languageLabel`: Dictation language
- `dictation.unsupported`: Dictation isn’t available in this browser. You can type instead.
- `dictation.permissionDenied`: Microphone access was blocked. You can still type.
- `dictation.noMicrophone`: No microphone was found. You can still type.
- `dictation.noSpeech`: I didn’t catch that - try again, or type.
- `dictation.network`: Dictation is temporarily unavailable. You can still type.
- `dictation.languageNotSupported`: Your browser can’t recognise speech in the selected dictation language. Choose another dictation language, or type.
- `dictation.error`: Dictation stopped unexpectedly. You can still type.
- `dictation.disabledByPolicy`: Dictation is switched off for your account. You can type instead.
- `dictation.browserNotice`: Dictation uses your browser’s speech service, which may send your voice to its provider. Ask4Mo does not store your audio.
- `settings.dictationLanguageHelp`: The language used for speech-to-text input. Independent of the interface and conversation languages; it does not translate your words.
- `help.dict1a`: Where your browser supports speech recognition, a microphone button appears next to text inputs on Prepare (talking to Mo) and in Interview Practice (your answer). If it isn't shown, your browser doesn't support it — you can always type.
- `help.dict4a`: A small selector offers Ask4Mo's supported dictation languages: English, German, French, Spanish, Italian, Portuguese and Dutch. This sets the speech-recognition language only — it does not translate your words and does not change the app's language.
- `help.dict5a`: The languages above are configured and offered, but which ones your device can actually transcribe is browser- and engine-dependent. If a language isn't recognised well in your browser, type instead or try another supported browser.
- `help.dict6a`: Dictation uses your browser's built-in speech recognition (best supported in Chrome-based browsers). Where it isn't available, the microphone simply isn't shown and typing works as normal.
- `help.dict7a`: Your browser asks for microphone permission the first time. If you decline, dictation won't run and Ask4Mo shows a short note — you can still type. You can re-enable the microphone in your browser's site settings.
- `help.dict8a`: Ask4Mo does not analyse your emotions, voice characteristics, or identity. It does not record or store audio. Only the text you explicitly submit is sent — exactly like typing. Note that browser speech recognition may send audio to your browser/vendor's speech service to produce the transcript; that processing is your browser's, not Ask4Mo's.
- `voice.hSpeakA`: Use the microphone to speak your answer or message. Your words appear as an editable transcript; you review and edit them, then press Send or Submit yourself. Speaking never submits on its own, and starting to speak stops playback (and vice-versa) so the two are never active at once.
- `voice.hPrivacyA`: Ask4Mo hands the visible text to your browser/OS speech engine and stores no audio. Ask4Mo never uses your voice to infer emotions, personality, intelligence, honesty, deception, accent or hiring suitability - voice is only a way to listen and to enter text. There is no voice score of any kind.
- `privacy.voiceTurnBased`: Turn-based voice uses your browser or operating-system speech engines. Ask4Mo does not record or store your microphone audio.
- `trust.noAudioDesc`: Ask4Mo does not record or store your microphone audio. Realtime voice streams to a provider to power the conversation, under that provider's own policy.
- `onboarding.privacyAudio`: Ask4Mo never stores audio and never analyses your voice.
- `marketing.why3Body`: Your data is private by default. No automatic microphone, no silent submission, and your interface language never changes your target job market.

### de (Deutsch)

- `dictation.start`: Diktat starten
- `dictation.stop`: Diktat stoppen
- `dictation.listening`: Höre zu… sprechen Sie, dann vor dem Senden prüfen.
- `dictation.heard`: Gehört: {text}
- `dictation.languageLabel`: Diktiersprache
- `dictation.unsupported`: Diktat ist in diesem Browser nicht verfügbar. Sie können stattdessen tippen.
- `dictation.permissionDenied`: Mikrofonzugriff wurde blockiert. Sie können weiterhin tippen.
- `dictation.noMicrophone`: Kein Mikrofon gefunden. Sie können weiterhin tippen.
- `dictation.noSpeech`: Nicht verstanden - bitte erneut versuchen oder tippen.
- `dictation.network`: Diktat ist vorübergehend nicht verfügbar. Sie können weiterhin tippen.
- `dictation.languageNotSupported`: Ihr Browser kann die gewählte Diktatsprache nicht erkennen. Wählen Sie eine andere Diktatsprache oder tippen Sie.
- `dictation.error`: Diktat unerwartet beendet. Sie können weiterhin tippen.
- `dictation.disabledByPolicy`: Das Diktat ist für Ihr Konto ausgeschaltet. Sie können stattdessen tippen.
- `dictation.browserNotice`: Das Diktat nutzt den Sprachdienst Ihres Browsers, der Ihre Stimme an seinen Anbieter senden kann. Ask4Mo speichert Ihr Audio nicht.
- `settings.dictationLanguageHelp`: Die Sprache für die Spracheingabe. Unabhängig von Oberflächen- und Gesprächssprache; Ihre Worte werden nicht übersetzt.
- `help.dict1a`: Wo Ihr Browser Spracherkennung unterstützt, erscheint ein Mikrofon-Button neben Texteingaben in Vorbereiten (im Gespräch mit Mo) und in der Interview-Übung (Ihre Antwort). Wird es nicht angezeigt, unterstützt Ihr Browser dies nicht; Sie können jederzeit tippen.
- `help.dict4a`: Eine kleine Auswahl bietet die von Ask4Mo unterstützten Diktiersprachen: Englisch, Deutsch, Französisch, Spanisch, Italienisch, Portugiesisch und Niederländisch. Das legt nur die Spracherkennungssprache fest; es übersetzt Ihre Worte nicht und ändert nicht die Sprache der App.
- `help.dict5a`: Die oben genannten Sprachen sind eingerichtet und werden angeboten, aber welche Ihr Gerät tatsächlich transkribieren kann, hängt von Browser und Engine ab. Wird eine Sprache in Ihrem Browser schlecht erkannt, tippen Sie stattdessen oder probieren Sie einen anderen unterstützten Browser.
- `help.dict6a`: Diktat nutzt die in Ihrem Browser eingebaute Spracherkennung (am besten unterstützt in Chrome-basierten Browsern). Wo sie nicht verfügbar ist, wird das Mikrofon einfach nicht angezeigt, und Tippen funktioniert wie gewohnt.
- `help.dict7a`: Ihr Browser fragt beim ersten Mal nach Mikrofonzugriff. Lehnen Sie ab, läuft kein Diktat, und Ask4Mo zeigt einen kurzen Hinweis; Sie können weiterhin tippen. Sie können das Mikrofon in den Website-Einstellungen Ihres Browsers wieder aktivieren.
- `help.dict8a`: Ask4Mo analysiert nicht Ihre Emotionen, Stimmmerkmale oder Identität. Es zeichnet kein Audio auf und speichert keines. Nur der Text, den Sie ausdrücklich absenden, wird übertragen, genau wie beim Tippen. Beachten Sie, dass die Spracherkennung des Browsers Audio an den Sprachdienst Ihres Browsers/Anbieters senden kann, um das Transkript zu erstellen; diese Verarbeitung liegt bei Ihrem Browser, nicht bei Ask4Mo.
- `voice.hSpeakA`: Nutzen Sie das Mikrofon, um Ihre Antwort zu sprechen. Ihre Worte erscheinen als bearbeitbares Transkript; Sie prüfen und bearbeiten sie und drücken dann selbst Senden oder Absenden. Sprechen sendet nie von selbst, und das Sprechen stoppt die Wiedergabe (und umgekehrt) - beide sind nie gleichzeitig aktiv.
- `voice.hPrivacyA`: Ask4Mo übergibt den sichtbaren Text an die Sprach-Engine Ihres Browsers/Betriebssystems und speichert kein Audio. Ask4Mo nutzt Ihre Stimme niemals, um Emotionen, Persönlichkeit, Intelligenz, Ehrlichkeit, Täuschung, Akzent oder Eignung abzuleiten - Stimme dient nur zum Zuhören und zur Texteingabe. Es gibt keinerlei Stimm-Bewertung.
- `privacy.voiceTurnBased`: Wechselseitige Sprachausgabe nutzt die Sprach-Engines Ihres Browsers oder Betriebssystems. Ask4Mo nimmt Ihr Mikrofon-Audio nicht auf und speichert es nicht.
- `trust.noAudioDesc`: Ask4Mo nimmt Ihr Mikrofon-Audio nicht auf und speichert es nicht. Echtzeit-Sprache überträgt an einen Anbieter, um das Gespräch zu ermöglichen, gemäß dessen Richtlinie.
- `onboarding.privacyAudio`: Ask4Mo speichert niemals Audio und analysiert niemals Ihre Stimme.
- `marketing.why3Body`: Ihre Daten sind standardmäßig privat. Kein automatisches Mikrofon, kein stilles Absenden, und Ihre Oberflächensprache ändert nie Ihren Zielarbeitsmarkt.

### fr (Francais)

- `dictation.start`: Démarrer la dictée
- `dictation.stop`: Arrêter la dictée
- `dictation.listening`: Écoute… parlez, puis vérifiez avant d’envoyer.
- `dictation.heard`: Entendu : {text}
- `dictation.languageLabel`: Langue de dictée
- `dictation.unsupported`: La dictée n’est pas disponible dans ce navigateur. Vous pouvez taper à la place.
- `dictation.permissionDenied`: L’accès au microphone a été bloqué. Vous pouvez toujours taper.
- `dictation.noMicrophone`: Aucun microphone détecté. Vous pouvez toujours taper.
- `dictation.noSpeech`: Je n’ai pas compris - réessayez ou tapez.
- `dictation.network`: La dictée est temporairement indisponible. Vous pouvez toujours taper.
- `dictation.languageNotSupported`: Votre navigateur ne peut pas reconnaître la langue de dictée choisie. Choisissez une autre langue de dictée ou tapez.
- `dictation.error`: La dictée s’est arrêtée de façon inattendue. Vous pouvez toujours taper.
- `dictation.disabledByPolicy`: La dictée est désactivée pour votre compte. Vous pouvez taper à la place.
- `dictation.browserNotice`: La dictée utilise le service vocal de votre navigateur, qui peut envoyer votre voix à son fournisseur. Ask4Mo ne stocke pas votre audio.
- `settings.dictationLanguageHelp`: La langue de la saisie vocale. Indépendante des langues d’interface et de conversation ; elle ne traduit pas vos mots.
- `help.dict1a`: Lorsque votre navigateur prend en charge la reconnaissance vocale, un bouton microphone apparaît à côté des champs de texte dans Préparer (pour parler à Mo) et dans l’entraînement à l’entretien (pour votre réponse). S’il n’apparaît pas, votre navigateur ne le prend pas en charge : vous pouvez toujours taper.
- `help.dict4a`: Un petit sélecteur propose les langues de dictée prises en charge par Ask4Mo : anglais, allemand, français, espagnol, italien, portugais et néerlandais. Cela définit uniquement la langue de reconnaissance vocale : cela ne traduit pas vos mots et ne change pas la langue de l’application.
- `help.dict5a`: Les langues ci-dessus sont configurées et proposées, mais celles que votre appareil peut réellement transcrire dépendent du navigateur et du moteur utilisés. Si une langue n’est pas bien reconnue par votre navigateur, tapez votre réponse ou essayez un autre navigateur pris en charge.
- `help.dict6a`: La dictée utilise la reconnaissance vocale intégrée à votre navigateur (mieux prise en charge par les navigateurs basés sur Chrome). Lorsqu’elle n’est pas disponible, le microphone n’apparaît simplement pas et la saisie fonctionne normalement.
- `help.dict7a`: Votre navigateur demande l’autorisation d’accéder au microphone la première fois. Si vous refusez, la dictée ne fonctionnera pas et Ask4Mo affiche une brève note : vous pouvez toujours taper. Vous pouvez réactiver le microphone dans les paramètres du site de votre navigateur.
- `help.dict8a`: Ask4Mo n’analyse ni vos émotions, ni vos caractéristiques vocales, ni votre identité. Il n’enregistre ni ne stocke d’audio. Seul le texte que vous envoyez explicitement est transmis, exactement comme en tapant. Notez que la reconnaissance vocale du navigateur peut envoyer l’audio au service vocal de votre navigateur ou de son éditeur pour produire la transcription ; ce traitement relève de votre navigateur, pas d’Ask4Mo.
- `voice.hSpeakA`: Utilisez le microphone pour dicter votre réponse. Vos mots apparaissent sous forme de transcription modifiable ; vous les relisez et les corrigez, puis vous appuyez vous-même sur Envoyer ou Soumettre. Parler n’envoie jamais tout seul, et parler arrête la lecture (et inversement) - les deux ne sont jamais actifs en même temps.
- `voice.hPrivacyA`: Ask4Mo transmet le texte visible au moteur vocal de votre navigateur/système et ne stocke aucun audio. Ask4Mo n’utilise jamais votre voix pour déduire des émotions, la personnalité, l’intelligence, l’honnêteté, la tromperie, l’accent ou l’aptitude à l’embauche - la voix sert uniquement à écouter et à saisir du texte. Il n’existe aucun score vocal.
- `privacy.voiceTurnBased`: La voix au tour par tour utilise les moteurs vocaux de votre navigateur ou de votre système d'exploitation. Ask4Mo n'enregistre ni ne conserve l'audio de votre microphone.
- `trust.noAudioDesc`: Ask4Mo n'enregistre ni ne conserve l'audio de votre microphone. La voix en temps réel est transmise à un fournisseur pour alimenter la conversation, selon la politique propre à ce fournisseur.
- `onboarding.privacyAudio`: Ask4Mo ne stocke jamais d’audio et n’analyse jamais votre voix.
- `marketing.why3Body`: Vos données sont privées par défaut. Pas de micro automatique, pas d'envoi silencieux, et la langue de l'interface ne change jamais votre marché de l'emploi cible.

### es (Espanol)

- `dictation.start`: Iniciar dictado
- `dictation.stop`: Detener dictado
- `dictation.listening`: Escuchando… habla y luego revisa antes de enviar.
- `dictation.heard`: Escuchado: {text}
- `dictation.languageLabel`: Idioma de dictado
- `dictation.unsupported`: El dictado no está disponible en este navegador. Puedes escribir en su lugar.
- `dictation.permissionDenied`: Se bloqueó el acceso al micrófono. Aún puedes escribir.
- `dictation.noMicrophone`: No se encontró micrófono. Aún puedes escribir.
- `dictation.noSpeech`: No lo he captado - inténtalo de nuevo o escribe.
- `dictation.network`: El dictado no está disponible temporalmente. Aún puedes escribir.
- `dictation.languageNotSupported`: Tu navegador no puede reconocer el idioma de dictado seleccionado. Elige otro idioma de dictado o escribe.
- `dictation.error`: El dictado se detuvo inesperadamente. Aún puedes escribir.
- `dictation.disabledByPolicy`: El dictado está desactivado para tu cuenta. Puedes escribir en su lugar.
- `dictation.browserNotice`: El dictado usa el servicio de voz de tu navegador, que puede enviar tu voz a su proveedor. Ask4Mo no guarda tu audio.
- `settings.dictationLanguageHelp`: El idioma de la entrada por voz. Independiente de los idiomas de interfaz y conversación; no traduce tus palabras.
- `help.dict1a`: Cuando tu navegador admite reconocimiento de voz, aparece un botón de micrófono junto a los campos de texto en Preparar (al hablar con Mo) y en Interview Practice (tu respuesta). Si no aparece, tu navegador no lo admite: siempre puedes escribir.
- `help.dict4a`: Un pequeño selector ofrece los idiomas de dictado admitidos por Ask4Mo: inglés, alemán, francés, español, italiano, portugués y neerlandés. Esto solo establece el idioma de reconocimiento de voz: no traduce tus palabras ni cambia el idioma de la aplicación.
- `help.dict5a`: Los idiomas anteriores están configurados y disponibles, pero cuáles puede transcribir realmente tu dispositivo depende del navegador y del motor. Si un idioma no se reconoce bien en tu navegador, escribe en su lugar o prueba con otro navegador compatible.
- `help.dict6a`: El dictado usa el reconocimiento de voz integrado de tu navegador (mejor compatibilidad en navegadores basados en Chrome). Donde no esté disponible, el micrófono simplemente no se muestra y escribir funciona con normalidad.
- `help.dict7a`: Tu navegador pide permiso para el micrófono la primera vez. Si lo rechazas, el dictado no funcionará y Ask4Mo mostrará una breve nota: aun así puedes escribir. Puedes volver a habilitar el micrófono en la configuración del sitio de tu navegador.
- `help.dict8a`: Ask4Mo no analiza tus emociones, características de voz ni identidad. No graba ni almacena audio. Solo se envía el texto que envías explícitamente, exactamente igual que al escribir. Ten en cuenta que el reconocimiento de voz del navegador puede enviar audio al servicio de voz de tu navegador o proveedor para producir la transcripción; ese procesamiento es de tu navegador, no de Ask4Mo.
- `voice.hSpeakA`: Usa el micrófono para hablar tu respuesta. Tus palabras aparecen como una transcripción editable; las revisas y corriges, y luego pulsas Enviar tú mismo. Hablar nunca envía solo, y empezar a hablar detiene la reproducción (y viceversa) - nunca están activos a la vez.
- `voice.hPrivacyA`: Ask4Mo entrega el texto visible al motor de voz de tu navegador/sistema y no almacena audio. Ask4Mo nunca usa tu voz para inferir emociones, personalidad, inteligencia, honestidad, engaño, acento o idoneidad para un empleo - la voz solo sirve para escuchar e introducir texto. No existe ninguna puntuación de voz.
- `privacy.voiceTurnBased`: La voz por turnos usa los motores de voz de su navegador o sistema operativo. Ask4Mo no graba ni almacena el audio de su micrófono.
- `trust.noAudioDesc`: Ask4Mo no graba ni almacena el audio de su micrófono. La voz en tiempo real se transmite a un proveedor para impulsar la conversación, bajo la política propia de ese proveedor.
- `onboarding.privacyAudio`: Ask4Mo nunca almacena audio ni analiza tu voz.
- `marketing.why3Body`: Tus datos son privados por defecto. Sin micrófono automático, sin envío silencioso, y el idioma de la interfaz nunca cambia tu mercado laboral objetivo.

### it (Italiano)

- `dictation.start`: Avvia dettatura
- `dictation.stop`: Ferma dettatura
- `dictation.listening`: In ascolto… parla, poi rivedi prima di inviare.
- `dictation.heard`: Sentito: {text}
- `dictation.languageLabel`: Lingua di dettatura
- `dictation.unsupported`: La dettatura non è disponibile in questo browser. Puoi digitare invece.
- `dictation.permissionDenied`: Accesso al microfono bloccato. Puoi comunque digitare.
- `dictation.noMicrophone`: Nessun microfono trovato. Puoi comunque digitare.
- `dictation.noSpeech`: Non ho capito - riprova o digita.
- `dictation.network`: Dettatura temporaneamente non disponibile. Puoi comunque digitare.
- `dictation.languageNotSupported`: Il tuo browser non riesce a riconoscere la lingua di dettatura selezionata. Scegli un’altra lingua di dettatura o digita.
- `dictation.error`: La dettatura si è interrotta inaspettatamente. Puoi comunque digitare.
- `dictation.disabledByPolicy`: La dettatura è disattivata per il tuo account. Puoi digitare invece.
- `dictation.browserNotice`: La dettatura usa il servizio vocale del tuo browser, che può inviare la tua voce al suo fornitore. Ask4Mo non conserva il tuo audio.
- `settings.dictationLanguageHelp`: La lingua per l’inserimento vocale. Indipendente dalle lingue di interfaccia e conversazione; non traduce le tue parole.
- `help.dict1a`: Se il tuo browser supporta il riconoscimento vocale, un pulsante del microfono compare accanto ai campi di testo in Prepara (quando parli con Mo) e nell'Esercitazione al colloquio (la tua risposta). Se non lo vedi, il tuo browser non lo supporta: puoi comunque digitare.
- `help.dict4a`: Un piccolo selettore offre le lingue di dettatura supportate da Ask4Mo: inglese, tedesco, francese, spagnolo, italiano, portoghese e olandese. Questo imposta solo la lingua del riconoscimento vocale: non traduce le tue parole e non cambia la lingua dell'app.
- `help.dict5a`: Le lingue elencate sopra sono configurate e disponibili, ma quelle che il tuo dispositivo riesce effettivamente a trascrivere dipendono dal browser e dal motore di riconoscimento. Se una lingua non viene riconosciuta bene nel tuo browser, digita invece o prova un altro browser supportato.
- `help.dict6a`: La dettatura usa il riconoscimento vocale integrato nel tuo browser (supportato al meglio nei browser basati su Chrome). Dove non è disponibile, il microfono semplicemente non compare e puoi digitare normalmente.
- `help.dict7a`: Il tuo browser chiede il permesso per il microfono la prima volta. Se lo rifiuti, la dettatura non funzionerà e Ask4Mo mostrerà una breve nota: potrai comunque digitare. Puoi riattivare il microfono nelle impostazioni del sito del tuo browser.
- `help.dict8a`: Ask4Mo non analizza le tue emozioni, le caratteristiche della voce o la tua identità. Non registra né conserva alcun audio. Viene inviato solo il testo che invii esplicitamente, esattamente come quando digiti. Nota che il riconoscimento vocale del browser potrebbe inviare l'audio al servizio vocale del tuo browser o fornitore per produrre la trascrizione: quell'elaborazione è del tuo browser, non di Ask4Mo.
- `voice.hSpeakA`: Usa il microfono per dettare la tua risposta. Le tue parole appaiono come trascrizione modificabile; le rileggi e le correggi, poi premi tu stesso Invia. Parlare non invia mai da solo, e iniziare a parlare ferma la riproduzione (e viceversa) - i due non sono mai attivi insieme.
- `voice.hPrivacyA`: Ask4Mo passa il testo visibile al motore vocale del browser/sistema e non memorizza audio. Ask4Mo non usa mai la tua voce per dedurre emozioni, personalità, intelligenza, onestà, inganno, accento o idoneità all’assunzione - la voce serve solo ad ascoltare e a inserire testo. Non esiste alcun punteggio vocale.
- `privacy.voiceTurnBased`: La voce a turni usa i motori vocali del tuo browser o sistema operativo. Ask4Mo non registra né conserva l'audio del tuo microfono.
- `trust.noAudioDesc`: Ask4Mo non registra né conserva l'audio del tuo microfono. La voce in tempo reale viene trasmessa a un provider per alimentare la conversazione, secondo la policy propria di tale provider.
- `onboarding.privacyAudio`: Ask4Mo non memorizza mai l’audio e non analizza mai la tua voce.
- `marketing.why3Body`: I tuoi dati sono privati per impostazione predefinita. Nessun microfono automatico, nessun invio silenzioso, e la lingua dell'interfaccia non cambia mai il tuo mercato del lavoro di riferimento.

### pt (Portugues)

- `dictation.start`: Iniciar ditado
- `dictation.stop`: Parar ditado
- `dictation.listening`: A ouvir… fale e depois reveja antes de enviar.
- `dictation.heard`: Ouvido: {text}
- `dictation.languageLabel`: Idioma de ditado
- `dictation.unsupported`: O ditado não está disponível neste navegador. Pode escrever em alternativa.
- `dictation.permissionDenied`: O acesso ao microfone foi bloqueado. Pode continuar a escrever.
- `dictation.noMicrophone`: Nenhum microfone encontrado. Pode continuar a escrever.
- `dictation.noSpeech`: Não percebi - tente novamente ou escreva.
- `dictation.network`: O ditado está temporariamente indisponível. Pode continuar a escrever.
- `dictation.languageNotSupported`: O seu navegador não consegue reconhecer o idioma de ditado selecionado. Escolha outro idioma de ditado ou escreva.
- `dictation.error`: O ditado parou inesperadamente. Pode continuar a escrever.
- `dictation.disabledByPolicy`: O ditado está desativado para a sua conta. Pode escrever em vez disso.
- `dictation.browserNotice`: O ditado usa o serviço de voz do seu navegador, que pode enviar a sua voz ao respetivo fornecedor. O Ask4Mo não guarda o seu áudio.
- `settings.dictationLanguageHelp`: O idioma da entrada por voz. Independente dos idiomas de interface e de conversa; não traduz as suas palavras.
- `help.dict1a`: Onde o seu navegador suporta reconhecimento de voz, aparece um botão de microfone junto aos campos de texto em Preparar (ao falar com o Mo) e na Prática de Entrevista (a sua resposta). Se não aparecer, o seu navegador não o suporta - pode sempre escrever.
- `help.dict4a`: Um pequeno seletor oferece os idiomas de ditado suportados pelo Ask4Mo: inglês, alemão, francês, espanhol, italiano, português e neerlandês. Isto define apenas o idioma de reconhecimento de voz - não traduz as suas palavras nem muda o idioma da aplicação.
- `help.dict5a`: Os idiomas acima estão configurados e disponíveis, mas quais o seu dispositivo consegue efetivamente transcrever depende do navegador e do motor usado. Se um idioma não for bem reconhecido no seu navegador, escreva em alternativa ou experimente outro navegador suportado.
- `help.dict6a`: O ditado usa o reconhecimento de voz integrado do seu navegador (com melhor suporte em navegadores baseados em Chrome). Onde não está disponível, o microfone simplesmente não aparece e a escrita funciona normalmente.
- `help.dict7a`: O seu navegador pede permissão de microfone na primeira vez. Se recusar, o ditado não funciona e o Ask4Mo mostra uma breve nota - pode continuar a escrever. Pode voltar a ativar o microfone nas definições do seu navegador para o site.
- `help.dict8a`: O Ask4Mo não analisa as suas emoções, características de voz ou identidade. Não grava nem armazena áudio. Só é enviado o texto que envia explicitamente - exatamente como ao escrever. Note que o reconhecimento de voz do navegador pode enviar áudio para o serviço de voz do seu navegador/fornecedor para produzir a transcrição; esse processamento é do seu navegador, não do Ask4Mo.
- `voice.hSpeakA`: Use o microfone para falar a sua resposta. As suas palavras aparecem como uma transcrição editável; revê-as e corrige-as e depois carrega em Enviar você mesmo. Falar nunca envia sozinho, e começar a falar para a reprodução (e vice-versa) - os dois nunca estão ativos ao mesmo tempo.
- `voice.hPrivacyA`: O Ask4Mo entrega o texto visível ao motor de voz do seu navegador/sistema e não armazena áudio. O Ask4Mo nunca usa a sua voz para inferir emoções, personalidade, inteligência, honestidade, engano, sotaque ou adequação para contratação - a voz serve apenas para ouvir e introduzir texto. Não existe qualquer pontuação de voz.
- `privacy.voiceTurnBased`: A voz por turnos usa os motores de fala do seu navegador ou sistema operativo. O Ask4Mo não grava nem armazena o áudio do seu microfone.
- `trust.noAudioDesc`: O Ask4Mo não grava nem armazena o áudio do seu microfone. A voz em tempo real é transmitida a um fornecedor para suportar a conversa, sob a política do próprio fornecedor.
- `onboarding.privacyAudio`: O Ask4Mo nunca armazena áudio e nunca analisa a sua voz.
- `marketing.why3Body`: Os seus dados são privados por predefinição. Sem microfone automático, sem envio silencioso, e o idioma da interface nunca muda o seu mercado de trabalho alvo.

### nl (Nederlands)

- `dictation.start`: Dicteren starten
- `dictation.stop`: Dicteren stoppen
- `dictation.listening`: Aan het luisteren… spreek, controleer daarna voordat u verstuurt.
- `dictation.heard`: Gehoord: {text}
- `dictation.languageLabel`: Dicteertaal
- `dictation.unsupported`: Dicteren is niet beschikbaar in deze browser. U kunt in plaats daarvan typen.
- `dictation.permissionDenied`: Microfoontoegang is geblokkeerd. U kunt nog steeds typen.
- `dictation.noMicrophone`: Geen microfoon gevonden. U kunt nog steeds typen.
- `dictation.noSpeech`: Niet verstaan - probeer opnieuw of typ.
- `dictation.network`: Dicteren is tijdelijk niet beschikbaar. U kunt nog steeds typen.
- `dictation.languageNotSupported`: Uw browser kan de gekozen dicteertaal niet herkennen. Kies een andere dicteertaal of typ.
- `dictation.error`: Dicteren is onverwacht gestopt. U kunt nog steeds typen.
- `dictation.disabledByPolicy`: Dicteren staat uit voor uw account. U kunt in plaats daarvan typen.
- `dictation.browserNotice`: Dicteren gebruikt de spraakservice van uw browser, die uw stem naar de aanbieder kan sturen. Ask4Mo slaat uw audio niet op.
- `settings.dictationLanguageHelp`: De taal voor spraakinvoer. Onafhankelijk van de interface- en gesprekstaal; het vertaalt uw woorden niet.
- `help.dict1a`: Waar uw browser spraakherkenning ondersteunt, verschijnt een microfoonknop naast tekstvelden bij Voorbereiden (in gesprek met Mo) en in Interview Practice (uw antwoord). Als deze niet verschijnt, ondersteunt uw browser dit niet: u kunt altijd typen.
- `help.dict4a`: Een kleine keuzelijst biedt de dicteertalen die Ask4Mo ondersteunt: Engels, Duits, Frans, Spaans, Italiaans, Portugees en Nederlands. Dit stelt alleen de taal voor spraakherkenning in: het vertaalt uw woorden niet en verandert de taal van de app niet.
- `help.dict5a`: De talen hierboven zijn geconfigureerd en beschikbaar, maar welke uw apparaat daadwerkelijk kan transcriberen hangt af van de browser en de engine. Wordt een taal niet goed herkend in uw browser, typ dan in plaats daarvan of probeer een andere ondersteunde browser.
- `help.dict6a`: Dicteren gebruikt de ingebouwde spraakherkenning van uw browser (het best ondersteund in op Chrome gebaseerde browsers). Waar dit niet beschikbaar is, wordt de microfoon simpelweg niet getoond en werkt typen gewoon zoals altijd.
- `help.dict7a`: Uw browser vraagt de eerste keer om microfoontoegang. Weigert u dit, dan werkt dicteren niet en toont Ask4Mo een korte melding: u kunt nog steeds typen. U kunt de microfoon opnieuw inschakelen in de sitinstellingen van uw browser.
- `help.dict8a`: Ask4Mo analyseert uw emoties, stemkenmerken of identiteit niet. Audio wordt niet opgenomen of opgeslagen. Alleen de tekst die u expliciet verstuurt, wordt verzonden: precies zoals bij typen. Let op: de spraakherkenning van uw browser kan audio naar de spraakdienst van uw browser/leverancier sturen om het transcript te maken; die verwerking is van uw browser, niet van Ask4Mo.
- `voice.hSpeakA`: Gebruik de microfoon om uw antwoord in te spreken. Uw woorden verschijnen als een bewerkbaar transcript; u leest en corrigeert ze en drukt daarna zelf op Verzenden. Spreken verzendt nooit vanzelf, en beginnen met spreken stopt het afspelen (en omgekeerd) - de twee zijn nooit tegelijk actief.
- `voice.hPrivacyA`: Ask4Mo geeft de zichtbare tekst door aan de spraak-engine van uw browser/systeem en slaat geen audio op. Ask4Mo gebruikt uw stem nooit om emoties, persoonlijkheid, intelligentie, eerlijkheid, misleiding, accent of geschiktheid voor werk af te leiden - stem dient alleen om te luisteren en tekst in te voeren. Er is geen enkele stemscore.
- `privacy.voiceTurnBased`: Spraak om beurten gebruikt de spraakengines van uw browser of besturingssysteem. Ask4Mo neemt uw microfoonaudio niet op en slaat deze niet op.
- `trust.noAudioDesc`: Ask4Mo neemt uw microfoonaudio niet op en slaat deze niet op. Realtime spraak wordt naar een provider gestuurd om het gesprek mogelijk te maken, onder het eigen beleid van die provider.
- `onboarding.privacyAudio`: Ask4Mo slaat nooit audio op en analyseert nooit uw stem.
- `marketing.why3Body`: Je gegevens zijn standaard privé. Geen automatische microfoon, geen stille verzending, en je interfacetaal verandert nooit je beoogde arbeidsmarkt.

### ru (Russkiy (preserved, excluded from R1.0))

- `dictation.start`: Начать диктовку
- `dictation.stop`: Остановить диктовку
- `dictation.listening`: Слушаю… говорите, затем проверьте текст перед отправкой.
- `dictation.heard`: Распознано: {text}
- `dictation.languageLabel`: Язык диктовки
- `dictation.unsupported`: Диктовка недоступна в этом браузере. Вы можете печатать.
- `dictation.permissionDenied`: Доступ к микрофону заблокирован. Вы по-прежнему можете печатать.
- `dictation.noMicrophone`: Микрофон не найден. Вы по-прежнему можете печатать.
- `dictation.noSpeech`: Я не расслышал: попробуйте ещё раз или напечатайте.
- `dictation.network`: Диктовка временно недоступна. Вы по-прежнему можете печатать.
- `dictation.languageNotSupported`: Ваш браузер не может распознавать речь на выбранном языке диктовки. Выберите другой язык диктовки или печатайте.
- `dictation.error`: Диктовка неожиданно остановилась. Вы по-прежнему можете печатать.
- `dictation.disabledByPolicy`: Диктовка отключена для вашей учётной записи. Вы можете печатать.
- `dictation.browserNotice`: Диктовка использует речевой сервис вашего браузера, который может отправлять ваш голос его поставщику. Ask4Mo не сохраняет ваше аудио.
- `settings.dictationLanguageHelp`: Язык, используемый для голосового ввода текста. Не зависит от языка интерфейса и языка общения; ваши слова не переводятся.
- `help.dict1a`: Если ваш браузер поддерживает распознавание речи, рядом с полями ввода текста в Подготовке (разговор с Mo) и в тренировочном собеседовании (ваш ответ) появляется кнопка микрофона. Если её нет, ваш браузер диктовку не поддерживает; печатать можно всегда.
- `help.dict4a`: Небольшой переключатель предлагает поддерживаемые Ask4Mo языки диктовки: английский, немецкий, французский, испанский, итальянский, португальский и нидерландский. Он задаёт только язык распознавания речи: он не переводит ваши слова и не меняет язык приложения.
- `help.dict5a`: Перечисленные выше языки настроены и предлагаются, но то, какие из них ваше устройство действительно может расшифровать, зависит от браузера и движка. Если язык плохо распознаётся в вашем браузере, печатайте или попробуйте другой поддерживаемый браузер.
- `help.dict6a`: Диктовка использует встроенное распознавание речи вашего браузера (лучше всего оно поддерживается в браузерах на основе Chrome). Если оно недоступно, микрофон просто не показывается, а печатать можно как обычно.
- `help.dict7a`: Браузер запрашивает разрешение на микрофон при первом использовании. Если вы откажете, диктовка не запустится, и Ask4Mo покажет короткое сообщение; печатать вы по-прежнему сможете. Микрофон можно снова включить в настройках сайта в вашем браузере.
- `help.dict8a`: Ask4Mo не анализирует ваши эмоции, особенности голоса или личность. Он не записывает и не хранит аудио. Отправляется только тот текст, который вы явно подтверждаете, точно так же, как при наборе на клавиатуре. Учтите, что распознавание речи в браузере может отправлять аудио в службу распознавания речи вашего браузера или его разработчика для получения расшифровки; эта обработка выполняется браузером, а не Ask4Mo.
- `voice.hSpeakA`: Используйте микрофон, чтобы продиктовать ответ или сообщение. Ваши слова появляются в виде редактируемой расшифровки: вы проверяете и редактируете её, а затем сами нажимаете «Отправить». Диктовка никогда не отправляет ничего сама, а начало диктовки останавливает воспроизведение (и наоборот), так что они никогда не работают одновременно.
- `voice.hPrivacyA`: Ask4Mo передаёт видимый текст речевому движку вашего браузера или операционной системы и не хранит аудио. Ask4Mo никогда не использует ваш голос, чтобы делать выводы об эмоциях, личности, интеллекте, честности, обмане, акценте или пригодности к найму: голос нужен только для того, чтобы слушать и вводить текст. Никакой оценки голоса не существует.
- `privacy.voiceTurnBased`: Голосовой режим по очереди использует речевые механизмы вашего браузера или операционной системы. Ask4Mo не записывает и не хранит звук с вашего микрофона.
- `trust.noAudioDesc`: Ask4Mo не записывает и не хранит звук с вашего микрофона. Голос в реальном времени передаётся поставщику для проведения разговора, в соответствии с политикой этого поставщика.
- `onboarding.privacyAudio`: Ask4Mo никогда не хранит аудио и никогда не анализирует ваш голос.
- `marketing.why3Body`: Ваши данные конфиденциальны по умолчанию. Никакого автоматического включения микрофона, никакой скрытой отправки, а язык интерфейса никогда не меняет рынок вашей целевой работы.

## 7. Verification status

| Item | Status |
|---|---|
| Code audit of the browser data flow (section 2) | DONE (engineering), covered by automated tests |
| Disclosure shown before first use and re-readable | DONE and tested (vitest, Playwright with a mocked SpeechRecognition) |
| Live browser speech-to-text check with real microphones and engines (Chrome, Safari, Edge, per language) | **OPEN, NOT RUN.** Needs appointed test participants and real browsers |
| Legal and privacy review of the disclosure wording and section 4 questions | **OPEN, NOT RUN.** Needs the owner's appointed legal reviewer. Nothing here is recorded as reviewed |
| Native-language review of the seven translations | **OPEN, NOT RUN** |
| Correction-burden measurement | **OPEN, NOT RUN.** The harness (`scripts/dictation_burden.py`, `docs/production/dictation/CORRECTION_BURDEN_PROTOCOL_04F.md`) exists and is tested on fake data only; it makes no measurement claim |
| Server speech | Untouched, gated for R1.4 |
