// P10B-W9.6 localization fragment (legal/trust/marketing/help). Merged by w96/index.ts.
//
// Engineering-draft translations: these are professional engineering drafts, NOT certified legal
// translations. They preserve the exact meaning of the English source (no legal claim is added,
// strengthened or weakened) pending legal review. Proper nouns (Ask4Mo, Mo, Story Bank, CV, JD,
// OCR, Glassdoor, Kununu, Premium, Basic) are intentionally left untranslated. No em dash is used.
//
// Every locale object is typed `typeof en`, so TypeScript enforces identical keys across all seven
// locales (missing or extra keys fail `tsc --noEmit`). Namespaces: privacy, terms, aiTransparency,
// about, help, marketing, trust.

const en = {
  privacy: {
    pageTitle: "Privacy",
    intro:
      "This page describes how Ask4Mo handles your data, based on the product's actual technical data inventory. It is an engineering draft and requires legal review; it is not a certification of compliance with any regulation.",
    storeHeading: "What we store",
    storeAccountTerm: "Account data",
    storeAccountDesc:
      "email, display name, verification status, sign-in method, plan tier and platform role.",
    storePrepTerm: "Preparation data",
    storePrepDesc: "your goals, conversations with Mo and generated preparation context.",
    storeDocsTerm: "Private documents",
    storeDocsDesc:
      "files you upload (for example a CV) stored privately under a random key, never a public URL. OCR-extracted text and detected claims.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "your answers, evaluations and reports.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "long-term preparation facts you have explicitly approved.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "reusable evidence-backed stories you create.",
    storeWorkspacesTerm: "Workspaces and sharing",
    storeWorkspacesDesc:
      "workspaces you own or join, and the specific items you explicitly share.",
    storeFeedbackTerm: "Feedback",
    storeFeedbackDesc: "ratings and comments you submit on responses.",
    storeMetadataTerm: "Operational metadata",
    storeMetadataDesc:
      "request identifiers, timestamps, coarse event categories and audit records of privileged or security-relevant actions.",
    voiceHeading: "Voice, speech and realtime",
    voiceTurnBased:
      "Turn-based voice uses your browser or operating-system speech engines. Ask4Mo does not record or store your microphone audio.",
    voiceRealtime:
      "Realtime voice (where enabled) streams audio to a realtime provider to power the live conversation; that processing follows the provider's own policy. Ask4Mo still stores no audio.",
    voiceNoInference:
      "Ask4Mo never uses your voice to infer emotion, personality, confidence, accent or hiring suitability. There is no voice score.",
    externalHeading: "External processing",
    externalAi:
      "AI features send necessary text (not secrets) to a model provider to generate responses.",
    externalResearch: "Current-market research (optional) may query external job-market sources.",
    externalEmail: "Email delivery uses a transactional email provider for verification and recovery.",
    externalKeys: "Long-lived provider keys stay server-side and are never sent to your browser.",
    retentionHeading: "Retention, export and deletion",
    retentionExport:
      "You can export your data and permanently delete your account and its application-controlled data (documents, private files, Practice history, Memory, Story Bank, sessions and agent checkpoints).",
    retentionAudit:
      "Security and audit records are retained and anonymized (the link to your account is removed) rather than deleted, for security review.",
    retentionBackups:
      "Historical infrastructure backups follow the hosting provider's retention schedule and are not erased instantly on deletion; they age out on that schedule.",
    retentionRights: "Privacy, security and your data rights are always available, on every plan.",
    contactHeading: "Contact",
    contactBody:
      "For privacy requests, contact the support address configured for your deployment. This draft will be replaced by legally-reviewed copy before public launch.",
  },
  terms: {
    pageTitle: "Terms of use",
    intro:
      "These terms are an engineering draft and require legal review before public launch. They set expectations for using Ask4Mo during staging and product review.",
    whatHeading: "What Ask4Mo is",
    whatBody:
      "Ask4Mo provides AI-assisted interview preparation guidance. It is a preparation aid, not professional, legal, financial or employment advice, and not a substitute for your own judgement.",
    aiHeading: "AI limitations",
    aiWrong: "AI can be wrong or incomplete. Verify anything important against the cited sources.",
    aiSources:
      "Sources may be partial; some datasets ship with an explicit engineering-draft or unvalidated status.",
    aiScores:
      "Practice scores are preparation guidance, not an objective measure of ability or a prediction of interview outcomes.",
    aiNoHiring:
      "Ask4Mo does not make hiring decisions, rank candidates for recruiters, or evaluate you by your voice.",
    respHeading: "Your responsibilities",
    respAccurate: "Provide accurate information and keep your credentials secure.",
    respUpload: "Only upload content you have the right to use.",
    respLawful: "Use the service lawfully and do not attempt to abuse or overload it.",
    accountsHeading: "Accounts, plans and availability",
    accountsPlans:
      "Basic is free. Premium is presented as a preview; no online payment is processed by this product.",
    accountsProviders:
      "Some features depend on external providers and may be unavailable, rate-limited or paused by the operator.",
    accountsAsIs:
      "The service is provided as is during this pre-launch phase, without warranties; liability is limited to the maximum extent permitted by applicable law (subject to legal review).",
    changesHeading: "Changes",
    changesBody: "These terms will be revised and legally reviewed before any public launch.",
  },
  aiTransparency: {
    pageTitle: "AI transparency and responsible use",
    intro:
      "We aim to be clear about how AI is used in Ask4Mo, in plain language. This page is an engineering draft; the underlying behaviour is described honestly.",
    whatMoHeading: "What Mo is",
    whatMoBody:
      "Mo is an AI coaching assistant that helps you prepare. Mo uses a bounded set of tools and follows a governed workflow; it does not act autonomously beyond preparing with you.",
    whenHeading: "When AI is used versus deterministic logic",
    whenAi:
      "AI (a model) is used for conversational coaching, grounded synthesis, question generation and answer and report evaluation.",
    whenDeterministic:
      "Deterministic logic (no model) is used for things that must be exact and injection-safe, for example selecting and ranking your already-approved evidence.",
    whenPolicy:
      "The choice of model per operation is governed by a central server-side policy; your browser can never choose a raw model.",
    specialistsHeading: "Specialists, evidence and sources",
    specialistsBounded:
      "Mo may consult bounded specialists (role and opportunity, evidence, coaching) through allow-listed tools with server-side revalidation.",
    specialistsGrounded:
      "Grounded answers cite their sources. When evidence is missing, Mo abstains rather than inventing facts.",
    approvalsHeading: "Human approvals and control",
    approvalsMemory: "Saving long-term Memory and important handoffs require your explicit approval.",
    approvalsFeedback:
      "Your feedback helps us improve; it never automatically modifies the running product.",
    limitsHeading: "Limitations",
    limitsModels: "Models can be wrong; Practice scores are guidance, not a verdict.",
    limitsRealtime:
      "Realtime voice is available only where configured; otherwise turn-based voice and typing are used.",
    neverHeading: "What Ask4Mo never does",
    neverInference:
      "No inference of emotion, mood, stress, confidence, accent, personality, intelligence, honesty or hiring suitability, from your voice or otherwise.",
    neverHiring: "No hiring decisions and no recruiter-facing candidate ranking.",
    neverPrompts: "No exposure of system prompts, developer prompts, chain-of-thought or secrets.",
  },
  about: {
    pageTitle: "About Ask4Mo",
    lead:
      "Ask4Mo, the Intelligent Interview Coach, helps candidates prepare for interviews that matter. Its guiding idea is simple: Ask More. Be More. Better questions, grounded answers and honest practice lead to better outcomes.",
    trust:
      "Ask4Mo is built to be trustworthy first. Preparation is grounded in sources you can check, your data is private by default, AI decisions that matter require your approval, and the product is honest about what it can and cannot do. It does not make hiring decisions, rank candidates for recruiters, or judge you by your voice.",
    capstone:
      "This is a Capstone product. Some capabilities (for example live realtime voice and certain knowledge datasets) ship with an honest, clearly-stated validation status rather than overclaiming.",
    seeAlso: "See also",
    imageAlt: "Two people having a thoughtful coaching conversation in a quiet library.",
    contact:
      "Questions or privacy requests? Contact support at the address configured for your deployment (see the Help centre once signed in).",
  },
  help: {
    heading: "Help",
    eyebrow: "How Ask4Mo works",
    description:
      "A searchable guide to every part of Ask4Mo, the ideas behind it, and a replayable guided tour.",
    journeyImageAlt:
      "An illustrated journey from understanding a role through conversation and practice to reflection.",
    tourTitle: "New here?",
    tourBody: "Take a 2-minute guided tour of the whole journey.",
    searchLabel: "Search help",
    searchExamples: "Search help, for example progress, sources, memory, report",
    noMatch: "No help topics match “{query}”. Try a different word.",
  },
  marketing: {
    heroImageAlt:
      "A professional preparing interview notes at a dining table in soft morning light.",
    problemImageAlt:
      "Hands organising job research, notes and interview materials into one opportunity folder.",
    productImageAlt:
      "A hand-drawn opportunity folder connecting company research, evidence, conversation, practice and feedback.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (mobile)",
  },
  trust: {
    imageAlt:
      "A person placing private evidence into a controlled document folio beside source material.",
    moreDetail: "More detail",
    isolationTerm: "Account isolation",
    isolationDesc:
      "Your data is scoped to your account. Platform admins operate a bounded operations console with metadata only; there is no view-as-user and no private-data search.",
    privateTerm: "Private by default",
    privateDesc:
      "Your CV, answers, reports, Memory and Story Bank are private. Nothing is shared with anyone unless you take an explicit sharing action.",
    oppPrivateTerm: "Your Opportunity is private",
    oppPrivateDesc:
      "An Opportunity is your own preparation space for one job. It is private to you and separate from a collaboration workspace. Opportunities are never shared automatically.",
    workspaceShareTerm: "Explicit workspace sharing",
    workspaceShareDesc:
      "Sharing into a workspace is view-only and always initiated by you. Removing a share or leaving revokes access.",
    sourcesTerm: "Sources you can check",
    sourcesDesc:
      "Grounded answers cite the sources behind them. When evidence is missing, Mo abstains rather than inventing facts.",
    factsSeparateTerm: "Company facts stay separate from opinion",
    factsSeparateDesc:
      "Company research keeps facts, employee-review context and AI suggestions clearly separate, from sources you can check. Employee-review platforms such as Glassdoor and Kununu are not integrated; Ask4Mo links out rather than copying or inventing reviews.",
    suggestionsTerm: "AI suggestions are not facts",
    suggestionsDesc:
      "Model-generated suggestions and interview feedback are coaching guidance. They are clearly separated from evidence and are never presented as verified facts.",
    evidenceGovernedTerm: "Your evidence is governed",
    evidenceGovernedDesc:
      "Only career evidence you have approved is used in preparation. Rejected or unreviewed evidence is excluded, and deleting a source removes it from use.",
    layeredContextTerm: "Layered context, not one memory",
    layeredContextDesc:
      "Your account preferences, an Opportunity's context, your per-session choices and your documents are distinct. Ask4Mo does not merge them into one uncontrolled memory store, and long-term Memory is saved only when you approve it.",
    languageMarketTerm: "Your language, your market",
    languageMarketDesc:
      "Your interface language is separate from your interview language, your dictation language and your target job market. Changing one never changes the others.",
    approvalsTerm: "Human approvals",
    approvalsDesc: "Saving long-term Memory and important handoffs require your explicit approval.",
    noHiringTerm: "No hiring decisions",
    noHiringDesc:
      "Ask4Mo does not make or recommend hiring decisions and does not rank candidates for recruiters.",
    noVoiceTraitTerm: "No voice-trait inference",
    noVoiceTraitDesc:
      "Your voice is never used to infer emotion, personality, confidence, accent or hiring suitability. There is no voice score of any kind.",
    noAudioTerm: "No audio storage",
    noAudioDesc:
      "Ask4Mo does not record or store your microphone audio. Realtime voice streams to a provider to power the conversation, under that provider's own policy.",
    boundedAgentsTerm: "Bounded AI agents",
    boundedAgentsDesc:
      "Mo uses a small, allow-listed set of tools with server-side revalidation. There is no autonomous production self-modification.",
    exportDeleteTerm: "Export and delete",
    exportDeleteDesc:
      "You can export your data and permanently delete your account and its application-controlled data at any time.",
    providerBoundariesTerm: "Provider boundaries",
    providerBoundariesDesc:
      "Long-lived provider keys stay server-side and are never sent to your browser. Costly features have server-side usage limits and an operator pause switch.",
  },
} as const;

/** The fragment shape. Each locale below is typed against it, so `tsc` enforces key parity. */
export type LegalFragment = { [N in keyof typeof en]: { [K in keyof (typeof en)[N]]: string } };

const de: LegalFragment = {
  privacy: {
    pageTitle: "Datenschutz",
    intro:
      "Diese Seite beschreibt, wie Ask4Mo mit Ihren Daten umgeht, basierend auf dem tatsächlichen technischen Dateninventar des Produkts. Sie ist ein Engineering-Entwurf und erfordert eine rechtliche Prüfung; sie ist keine Bestätigung der Konformität mit einer Vorschrift.",
    storeHeading: "Was wir speichern",
    storeAccountTerm: "Kontodaten",
    storeAccountDesc:
      "E-Mail, Anzeigename, Verifizierungsstatus, Anmeldemethode, Tarifstufe und Plattformrolle.",
    storePrepTerm: "Vorbereitungsdaten",
    storePrepDesc: "Ihre Ziele, Gespräche mit Mo und generierter Vorbereitungskontext.",
    storeDocsTerm: "Private Dokumente",
    storeDocsDesc:
      "Dateien, die Sie hochladen (zum Beispiel einen Lebenslauf), privat unter einem zufälligen Schlüssel gespeichert, nie unter einer öffentlichen URL. Per OCR extrahierter Text und erkannte Angaben.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "Ihre Antworten, Bewertungen und Berichte.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "langfristige Vorbereitungsfakten, die Sie ausdrücklich freigegeben haben.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "wiederverwendbare, belegbasierte Geschichten, die Sie erstellen.",
    storeWorkspacesTerm: "Workspaces und Teilen",
    storeWorkspacesDesc:
      "Workspaces, die Sie besitzen oder denen Sie beitreten, und die konkreten Elemente, die Sie ausdrücklich teilen.",
    storeFeedbackTerm: "Feedback",
    storeFeedbackDesc: "Bewertungen und Kommentare, die Sie zu Antworten abgeben.",
    storeMetadataTerm: "Betriebs-Metadaten",
    storeMetadataDesc:
      "Anfragekennungen, Zeitstempel, grobe Ereigniskategorien und Prüfprotokolle privilegierter oder sicherheitsrelevanter Aktionen.",
    voiceHeading: "Stimme, Sprache und Echtzeit",
    voiceTurnBased:
      "Wechselseitige Sprachausgabe nutzt die Sprach-Engines Ihres Browsers oder Betriebssystems. Ask4Mo nimmt Ihr Mikrofon-Audio nicht auf und speichert es nicht.",
    voiceRealtime:
      "Echtzeit-Sprache (wo aktiviert) überträgt Audio an einen Echtzeit-Anbieter, um das Live-Gespräch zu ermöglichen; diese Verarbeitung folgt der Richtlinie des Anbieters. Ask4Mo speichert weiterhin kein Audio.",
    voiceNoInference:
      "Ask4Mo nutzt Ihre Stimme niemals, um Emotion, Persönlichkeit, Selbstsicherheit, Akzent oder Eignung für eine Einstellung abzuleiten. Es gibt keine Stimmbewertung.",
    externalHeading: "Externe Verarbeitung",
    externalAi:
      "KI-Funktionen senden den nötigen Text (keine Geheimnisse) an einen Modellanbieter, um Antworten zu erzeugen.",
    externalResearch:
      "Aktuelle Marktrecherche (optional) kann externe Arbeitsmarktquellen abfragen.",
    externalEmail:
      "Die E-Mail-Zustellung nutzt einen Anbieter für Transaktions-E-Mails zur Verifizierung und Wiederherstellung.",
    externalKeys:
      "Langlebige Anbieterschlüssel bleiben serverseitig und werden niemals an Ihren Browser gesendet.",
    retentionHeading: "Aufbewahrung, Export und Löschung",
    retentionExport:
      "Sie können Ihre Daten exportieren und Ihr Konto sowie seine von der Anwendung kontrollierten Daten dauerhaft löschen (Dokumente, private Dateien, Practice-Verlauf, Memory, Story Bank, Sitzungen und Agenten-Checkpoints).",
    retentionAudit:
      "Sicherheits- und Prüfprotokolle werden zur Sicherheitsüberprüfung aufbewahrt und anonymisiert (die Verknüpfung mit Ihrem Konto wird entfernt), statt gelöscht zu werden.",
    retentionBackups:
      "Historische Infrastruktur-Backups folgen dem Aufbewahrungsplan des Hosting-Anbieters und werden bei der Löschung nicht sofort entfernt; sie laufen gemäß diesem Plan aus.",
    retentionRights:
      "Datenschutz, Sicherheit und Ihre Datenrechte sind in jedem Tarif stets verfügbar.",
    contactHeading: "Kontakt",
    contactBody:
      "Für Datenschutzanfragen wenden Sie sich an die für Ihre Bereitstellung konfigurierte Support-Adresse. Dieser Entwurf wird vor dem öffentlichen Start durch rechtlich geprüfte Texte ersetzt.",
  },
  terms: {
    pageTitle: "Nutzungsbedingungen",
    intro:
      "Diese Bedingungen sind ein Engineering-Entwurf und erfordern vor dem öffentlichen Start eine rechtliche Prüfung. Sie setzen Erwartungen an die Nutzung von Ask4Mo während der Staging- und Produktprüfung.",
    whatHeading: "Was Ask4Mo ist",
    whatBody:
      "Ask4Mo bietet KI-gestützte Hilfe zur Interviewvorbereitung. Es ist eine Vorbereitungshilfe, keine professionelle, rechtliche, finanzielle oder arbeitsrechtliche Beratung und kein Ersatz für Ihr eigenes Urteilsvermögen.",
    aiHeading: "Grenzen der KI",
    aiWrong:
      "KI kann falsch oder unvollständig sein. Prüfen Sie alles Wichtige anhand der zitierten Quellen.",
    aiSources:
      "Quellen können unvollständig sein; einige Datensätze haben ausdrücklich den Status Engineering-Entwurf oder nicht validiert.",
    aiScores:
      "Practice-Bewertungen sind Vorbereitungshinweise, kein objektives Maß für Fähigkeit und keine Vorhersage von Interviewergebnissen.",
    aiNoHiring:
      "Ask4Mo trifft keine Einstellungsentscheidungen, erstellt kein Ranking von Kandidaten für Recruiter und bewertet Sie nicht anhand Ihrer Stimme.",
    respHeading: "Ihre Verantwortlichkeiten",
    respAccurate: "Geben Sie korrekte Informationen an und halten Sie Ihre Zugangsdaten sicher.",
    respUpload: "Laden Sie nur Inhalte hoch, zu deren Nutzung Sie berechtigt sind.",
    respLawful:
      "Nutzen Sie den Dienst rechtmäßig und versuchen Sie nicht, ihn zu missbrauchen oder zu überlasten.",
    accountsHeading: "Konten, Tarife und Verfügbarkeit",
    accountsPlans:
      "Basic ist kostenlos. Premium wird als Vorschau dargestellt; über dieses Produkt wird keine Online-Zahlung verarbeitet.",
    accountsProviders:
      "Einige Funktionen hängen von externen Anbietern ab und können nicht verfügbar, ratenbegrenzt oder vom Betreiber pausiert sein.",
    accountsAsIs:
      "Der Dienst wird in dieser Phase vor dem Start wie besehen und ohne Gewährleistung bereitgestellt; die Haftung ist im größtmöglichen gesetzlich zulässigen Umfang beschränkt (vorbehaltlich rechtlicher Prüfung).",
    changesHeading: "Änderungen",
    changesBody:
      "Diese Bedingungen werden vor jedem öffentlichen Start überarbeitet und rechtlich geprüft.",
  },
  aiTransparency: {
    pageTitle: "KI-Transparenz und verantwortungsvolle Nutzung",
    intro:
      "Wir möchten in klarer Sprache darlegen, wie KI in Ask4Mo genutzt wird. Diese Seite ist ein Engineering-Entwurf; das zugrunde liegende Verhalten wird ehrlich beschrieben.",
    whatMoHeading: "Was Mo ist",
    whatMoBody:
      "Mo ist ein KI-Coaching-Assistent, der Sie bei der Vorbereitung unterstützt. Mo nutzt einen begrenzten Satz von Werkzeugen und folgt einem geregelten Ablauf; es handelt über die Vorbereitung mit Ihnen hinaus nicht eigenständig.",
    whenHeading: "Wann KI genutzt wird und wann deterministische Logik",
    whenAi:
      "KI (ein Modell) wird für dialogorientiertes Coaching, belegbasierte Synthese, Fragengenerierung sowie die Bewertung von Antworten und Berichten genutzt.",
    whenDeterministic:
      "Deterministische Logik (kein Modell) wird für Dinge genutzt, die exakt und injektionssicher sein müssen, zum Beispiel die Auswahl und Reihung Ihrer bereits freigegebenen Nachweise.",
    whenPolicy:
      "Die Wahl des Modells je Vorgang wird durch eine zentrale serverseitige Richtlinie gesteuert; Ihr Browser kann niemals ein rohes Modell wählen.",
    specialistsHeading: "Spezialisten, Nachweise und Quellen",
    specialistsBounded:
      "Mo kann begrenzte Spezialisten (Rolle und Opportunity, Nachweise, Coaching) über zugelassene Werkzeuge mit serverseitiger Neuprüfung heranziehen.",
    specialistsGrounded:
      "Belegbasierte Antworten nennen ihre Quellen. Wenn Nachweise fehlen, enthält sich Mo, statt Fakten zu erfinden.",
    approvalsHeading: "Menschliche Freigaben und Kontrolle",
    approvalsMemory:
      "Das Speichern von langfristigem Memory und wichtige Übergaben erfordern Ihre ausdrückliche Freigabe.",
    approvalsFeedback:
      "Ihr Feedback hilft uns, besser zu werden; es verändert niemals automatisch das laufende Produkt.",
    limitsHeading: "Einschränkungen",
    limitsModels: "Modelle können falsch liegen; Practice-Bewertungen sind Hinweise, kein Urteil.",
    limitsRealtime:
      "Echtzeit-Sprache ist nur dort verfügbar, wo sie konfiguriert ist; andernfalls werden wechselseitige Sprache und Tippen genutzt.",
    neverHeading: "Was Ask4Mo niemals tut",
    neverInference:
      "Keine Ableitung von Emotion, Stimmung, Stress, Selbstsicherheit, Akzent, Persönlichkeit, Intelligenz, Ehrlichkeit oder Eignung für eine Einstellung, weder aus Ihrer Stimme noch anderweitig.",
    neverHiring: "Keine Einstellungsentscheidungen und kein für Recruiter bestimmtes Kandidaten-Ranking.",
    neverPrompts:
      "Keine Offenlegung von System-Prompts, Entwickler-Prompts, Gedankenketten oder Geheimnissen.",
  },
  about: {
    pageTitle: "Über Ask4Mo",
    lead:
      "Ask4Mo, der Intelligent Interview Coach, hilft Kandidaten, sich auf Interviews vorzubereiten, die zählen. Die Leitidee ist einfach: Ask More. Be More. Bessere Fragen, belegbasierte Antworten und ehrliches Üben führen zu besseren Ergebnissen.",
    trust:
      "Ask4Mo ist so gebaut, dass Vertrauenswürdigkeit an erster Stelle steht. Die Vorbereitung beruht auf überprüfbaren Quellen, Ihre Daten sind standardmäßig privat, wichtige KI-Entscheidungen erfordern Ihre Freigabe, und das Produkt ist ehrlich darüber, was es kann und was nicht. Es trifft keine Einstellungsentscheidungen, erstellt kein Kandidaten-Ranking für Recruiter und bewertet Sie nicht anhand Ihrer Stimme.",
    capstone:
      "Dies ist ein Capstone-Produkt. Einige Funktionen (zum Beispiel Live-Echtzeit-Sprache und bestimmte Wissensdatensätze) erscheinen mit einem ehrlichen, klar angegebenen Validierungsstatus, statt zu viel zu versprechen.",
    seeAlso: "Siehe auch",
    imageAlt:
      "Zwei Menschen in einem nachdenklichen Coaching-Gespräch in einer ruhigen Bibliothek.",
    contact:
      "Fragen oder Datenschutzanfragen? Wenden Sie sich an den Support unter der für Ihre Bereitstellung konfigurierten Adresse (siehe das Help-Center nach der Anmeldung).",
  },
  help: {
    heading: "Hilfe",
    eyebrow: "Wie Ask4Mo funktioniert",
    description:
      "Ein durchsuchbarer Leitfaden zu jedem Teil von Ask4Mo, den Ideen dahinter und einer wiederholbaren geführten Tour.",
    journeyImageAlt:
      "Eine illustrierte Reise vom Verstehen einer Rolle über Gespräch und Übung bis zur Reflexion.",
    tourTitle: "Neu hier?",
    tourBody: "Machen Sie eine zweiminütige geführte Tour durch den gesamten Ablauf.",
    searchLabel: "Hilfe durchsuchen",
    searchExamples: "Hilfe durchsuchen, zum Beispiel Fortschritt, Quellen, Memory, Bericht",
    noMatch: "Keine Hilfethemen passen zu “{query}”. Versuchen Sie ein anderes Wort.",
  },
  marketing: {
    heroImageAlt:
      "Eine Fachkraft bereitet am Esstisch im sanften Morgenlicht Interviewnotizen vor.",
    problemImageAlt:
      "Hände, die Jobrecherche, Notizen und Interviewmaterialien in einem Opportunity-Ordner ordnen.",
    productImageAlt:
      "Ein handgezeichneter Opportunity-Ordner, der Unternehmensrecherche, Nachweise, Gespräch, Übung und Feedback verbindet.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (mobil)",
  },
  trust: {
    imageAlt:
      "Eine Person legt private Nachweise in ein kontrolliertes Dokumentenfolio neben Quellmaterial.",
    moreDetail: "Mehr Details",
    isolationTerm: "Konto-Isolation",
    isolationDesc:
      "Ihre Daten sind auf Ihr Konto beschränkt. Plattform-Admins betreiben eine begrenzte Betriebskonsole mit nur Metadaten; es gibt kein Anzeigen als Nutzer und keine Suche in privaten Daten.",
    privateTerm: "Standardmäßig privat",
    privateDesc:
      "Ihr Lebenslauf, Ihre Antworten, Berichte, Memory und Story Bank sind privat. Nichts wird mit anderen geteilt, es sei denn, Sie führen eine ausdrückliche Teilen-Aktion aus.",
    oppPrivateTerm: "Ihre Opportunity ist privat",
    oppPrivateDesc:
      "Eine Opportunity ist Ihr eigener Vorbereitungsraum für eine Stelle. Sie ist privat für Sie und von einem Kollaborations-Workspace getrennt. Opportunities werden niemals automatisch geteilt.",
    workspaceShareTerm: "Ausdrückliches Teilen im Workspace",
    workspaceShareDesc:
      "Das Teilen in einem Workspace ist nur zur Ansicht und wird stets von Ihnen ausgelöst. Das Entfernen einer Freigabe oder ein Austritt entzieht den Zugriff.",
    sourcesTerm: "Quellen, die Sie überprüfen können",
    sourcesDesc:
      "Belegbasierte Antworten nennen die Quellen dahinter. Wenn Nachweise fehlen, enthält sich Mo, statt Fakten zu erfinden.",
    factsSeparateTerm: "Unternehmensfakten bleiben von Meinungen getrennt",
    factsSeparateDesc:
      "Die Unternehmensrecherche hält Fakten, Kontext aus Mitarbeiterbewertungen und KI-Vorschläge klar getrennt, aus überprüfbaren Quellen. Plattformen für Mitarbeiterbewertungen wie Glassdoor und Kununu sind nicht integriert; Ask4Mo verlinkt dorthin, statt Bewertungen zu kopieren oder zu erfinden.",
    suggestionsTerm: "KI-Vorschläge sind keine Fakten",
    suggestionsDesc:
      "Modellgenerierte Vorschläge und Interview-Feedback sind Coaching-Hinweise. Sie sind klar von Nachweisen getrennt und werden niemals als gesicherte Fakten dargestellt.",
    evidenceGovernedTerm: "Ihre Nachweise sind geregelt",
    evidenceGovernedDesc:
      "In der Vorbereitung werden nur von Ihnen freigegebene Karrierenachweise verwendet. Abgelehnte oder ungeprüfte Nachweise sind ausgeschlossen, und das Löschen einer Quelle entfernt sie aus der Nutzung.",
    layeredContextTerm: "Mehrschichtiger Kontext, kein einzelnes Gedächtnis",
    layeredContextDesc:
      "Ihre Kontoeinstellungen, der Kontext einer Opportunity, Ihre Entscheidungen je Sitzung und Ihre Dokumente sind getrennt. Ask4Mo führt sie nicht zu einem unkontrollierten Gedächtnisspeicher zusammen, und langfristiges Memory wird nur gespeichert, wenn Sie es freigeben.",
    languageMarketTerm: "Ihre Sprache, Ihr Markt",
    languageMarketDesc:
      "Ihre Oberflächensprache ist getrennt von Ihrer Interviewsprache, Ihrer Diktiersprache und Ihrem Zielarbeitsmarkt. Das Ändern einer Einstellung ändert niemals die anderen.",
    approvalsTerm: "Menschliche Freigaben",
    approvalsDesc:
      "Das Speichern von langfristigem Memory und wichtige Übergaben erfordern Ihre ausdrückliche Freigabe.",
    noHiringTerm: "Keine Einstellungsentscheidungen",
    noHiringDesc:
      "Ask4Mo trifft oder empfiehlt keine Einstellungsentscheidungen und erstellt kein Kandidaten-Ranking für Recruiter.",
    noVoiceTraitTerm: "Keine Ableitung von Stimmmerkmalen",
    noVoiceTraitDesc:
      "Ihre Stimme wird niemals genutzt, um Emotion, Persönlichkeit, Selbstsicherheit, Akzent oder Eignung für eine Einstellung abzuleiten. Es gibt keinerlei Stimmbewertung.",
    noAudioTerm: "Keine Audiospeicherung",
    noAudioDesc:
      "Ask4Mo nimmt Ihr Mikrofon-Audio nicht auf und speichert es nicht. Echtzeit-Sprache überträgt an einen Anbieter, um das Gespräch zu ermöglichen, gemäß dessen Richtlinie.",
    boundedAgentsTerm: "Begrenzte KI-Agenten",
    boundedAgentsDesc:
      "Mo nutzt einen kleinen, zugelassenen Satz von Werkzeugen mit serverseitiger Neuprüfung. Es gibt keine autonome Selbstveränderung in der Produktion.",
    exportDeleteTerm: "Exportieren und löschen",
    exportDeleteDesc:
      "Sie können Ihre Daten exportieren und Ihr Konto sowie seine von der Anwendung kontrollierten Daten jederzeit dauerhaft löschen.",
    providerBoundariesTerm: "Anbietergrenzen",
    providerBoundariesDesc:
      "Langlebige Anbieterschlüssel bleiben serverseitig und werden niemals an Ihren Browser gesendet. Kostenintensive Funktionen haben serverseitige Nutzungslimits und einen Pausenschalter für den Betreiber.",
  },
};

const fr: LegalFragment = {
  privacy: {
    pageTitle: "Confidentialité",
    intro:
      "Cette page décrit comment Ask4Mo traite vos données, à partir de l'inventaire technique réel des données du produit. Il s'agit d'un brouillon d'ingénierie qui nécessite une revue juridique; ce n'est pas une certification de conformité à une quelconque réglementation.",
    storeHeading: "Ce que nous conservons",
    storeAccountTerm: "Données de compte",
    storeAccountDesc:
      "e-mail, nom affiché, statut de vérification, méthode de connexion, niveau d'offre et rôle sur la plateforme.",
    storePrepTerm: "Données de préparation",
    storePrepDesc: "vos objectifs, vos conversations avec Mo et le contexte de préparation généré.",
    storeDocsTerm: "Documents privés",
    storeDocsDesc:
      "les fichiers que vous téléversez (par exemple un CV), stockés de manière privée sous une clé aléatoire, jamais sous une URL publique. Texte extrait par OCR et éléments détectés.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "vos réponses, évaluations et rapports.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "les faits de préparation à long terme que vous avez explicitement approuvés.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "des récits réutilisables et étayés par des preuves que vous créez.",
    storeWorkspacesTerm: "Workspaces et partage",
    storeWorkspacesDesc:
      "les workspaces que vous possédez ou rejoignez, et les éléments précis que vous partagez explicitement.",
    storeFeedbackTerm: "Retours",
    storeFeedbackDesc: "les notes et commentaires que vous donnez sur des réponses.",
    storeMetadataTerm: "Métadonnées opérationnelles",
    storeMetadataDesc:
      "identifiants de requête, horodatages, catégories d'événements générales et enregistrements d'audit des actions privilégiées ou pertinentes pour la sécurité.",
    voiceHeading: "Voix, parole et temps réel",
    voiceTurnBased:
      "La voix au tour par tour utilise les moteurs vocaux de votre navigateur ou de votre système d'exploitation. Ask4Mo n'enregistre ni ne conserve l'audio de votre microphone.",
    voiceRealtime:
      "La voix en temps réel (lorsqu'elle est activée) transmet l'audio à un fournisseur de temps réel pour alimenter la conversation en direct; ce traitement suit la politique propre au fournisseur. Ask4Mo ne conserve toujours aucun audio.",
    voiceNoInference:
      "Ask4Mo n'utilise jamais votre voix pour déduire l'émotion, la personnalité, la confiance, l'accent ou l'aptitude à l'embauche. Il n'y a aucun score de voix.",
    externalHeading: "Traitement externe",
    externalAi:
      "Les fonctions d'IA envoient le texte nécessaire (pas de secrets) à un fournisseur de modèle pour générer des réponses.",
    externalResearch:
      "La recherche sur le marché actuel (optionnelle) peut interroger des sources externes du marché de l'emploi.",
    externalEmail:
      "La distribution des e-mails utilise un fournisseur d'e-mails transactionnels pour la vérification et la récupération.",
    externalKeys:
      "Les clés de fournisseur à longue durée restent côté serveur et ne sont jamais envoyées à votre navigateur.",
    retentionHeading: "Conservation, export et suppression",
    retentionExport:
      "Vous pouvez exporter vos données et supprimer définitivement votre compte et les données contrôlées par l'application (documents, fichiers privés, historique de Practice, Memory, Story Bank, sessions et points de contrôle de l'agent).",
    retentionAudit:
      "Les enregistrements de sécurité et d'audit sont conservés et anonymisés (le lien avec votre compte est retiré) plutôt que supprimés, à des fins de revue de sécurité.",
    retentionBackups:
      "Les sauvegardes d'infrastructure historiques suivent le calendrier de conservation de l'hébergeur et ne sont pas effacées instantanément lors de la suppression; elles expirent selon ce calendrier.",
    retentionRights:
      "La confidentialité, la sécurité et vos droits sur les données sont toujours disponibles, dans chaque offre.",
    contactHeading: "Contact",
    contactBody:
      "Pour les demandes de confidentialité, contactez l'adresse de support configurée pour votre déploiement. Ce brouillon sera remplacé par un texte révisé juridiquement avant le lancement public.",
  },
  terms: {
    pageTitle: "Conditions d'utilisation",
    intro:
      "Ces conditions sont un brouillon d'ingénierie et nécessitent une revue juridique avant le lancement public. Elles définissent les attentes concernant l'utilisation d'Ask4Mo pendant la phase de préproduction et de revue du produit.",
    whatHeading: "Ce qu'est Ask4Mo",
    whatBody:
      "Ask4Mo fournit une aide à la préparation aux entretiens assistée par l'IA. C'est une aide à la préparation, pas un conseil professionnel, juridique, financier ou en matière d'emploi, et ce n'est pas un substitut à votre propre jugement.",
    aiHeading: "Limites de l'IA",
    aiWrong:
      "L'IA peut se tromper ou être incomplète. Vérifiez tout élément important à l'aide des sources citées.",
    aiSources:
      "Les sources peuvent être partielles; certains jeux de données portent un statut explicite de brouillon d'ingénierie ou non validé.",
    aiScores:
      "Les scores de Practice sont des indications de préparation, pas une mesure objective de la capacité ni une prédiction des résultats d'entretien.",
    aiNoHiring:
      "Ask4Mo ne prend pas de décisions d'embauche, ne classe pas les candidats pour les recruteurs et ne vous évalue pas d'après votre voix.",
    respHeading: "Vos responsabilités",
    respAccurate: "Fournissez des informations exactes et gardez vos identifiants en sécurité.",
    respUpload: "Ne téléversez que du contenu que vous avez le droit d'utiliser.",
    respLawful:
      "Utilisez le service de manière légale et ne tentez pas d'en abuser ni de le surcharger.",
    accountsHeading: "Comptes, offres et disponibilité",
    accountsPlans:
      "Basic est gratuit. Premium est présenté comme un aperçu; aucun paiement en ligne n'est traité par ce produit.",
    accountsProviders:
      "Certaines fonctions dépendent de fournisseurs externes et peuvent être indisponibles, limitées en débit ou mises en pause par l'exploitant.",
    accountsAsIs:
      "Le service est fourni en l'état durant cette phase de pré-lancement, sans garanties; la responsabilité est limitée dans la mesure maximale permise par la loi applicable (sous réserve de revue juridique).",
    changesHeading: "Modifications",
    changesBody:
      "Ces conditions seront révisées et examinées juridiquement avant tout lancement public.",
  },
  aiTransparency: {
    pageTitle: "Transparence de l'IA et usage responsable",
    intro:
      "Nous voulons expliquer clairement, en langage simple, comment l'IA est utilisée dans Ask4Mo. Cette page est un brouillon d'ingénierie; le comportement sous-jacent est décrit honnêtement.",
    whatMoHeading: "Ce qu'est Mo",
    whatMoBody:
      "Mo est un assistant de coaching par IA qui vous aide à vous préparer. Mo utilise un ensemble borné d'outils et suit un flux encadré; il n'agit pas de façon autonome au-delà de la préparation avec vous.",
    whenHeading: "Quand l'IA est utilisée par rapport à la logique déterministe",
    whenAi:
      "L'IA (un modèle) est utilisée pour le coaching conversationnel, la synthèse étayée, la génération de questions et l'évaluation des réponses et des rapports.",
    whenDeterministic:
      "La logique déterministe (pas de modèle) est utilisée pour ce qui doit être exact et à l'épreuve des injections, par exemple la sélection et le classement de vos preuves déjà approuvées.",
    whenPolicy:
      "Le choix du modèle par opération est régi par une politique centrale côté serveur; votre navigateur ne peut jamais choisir un modèle brut.",
    specialistsHeading: "Spécialistes, preuves et sources",
    specialistsBounded:
      "Mo peut consulter des spécialistes bornés (rôle et opportunity, preuves, coaching) via des outils autorisés avec une revalidation côté serveur.",
    specialistsGrounded:
      "Les réponses étayées citent leurs sources. Lorsque les preuves manquent, Mo s'abstient plutôt que d'inventer des faits.",
    approvalsHeading: "Approbations humaines et contrôle",
    approvalsMemory:
      "L'enregistrement de Memory à long terme et les transferts importants nécessitent votre approbation explicite.",
    approvalsFeedback:
      "Vos retours nous aident à nous améliorer; ils ne modifient jamais automatiquement le produit en fonctionnement.",
    limitsHeading: "Limites",
    limitsModels:
      "Les modèles peuvent se tromper; les scores de Practice sont des indications, pas un verdict.",
    limitsRealtime:
      "La voix en temps réel n'est disponible que là où elle est configurée; sinon, la voix au tour par tour et la saisie sont utilisées.",
    neverHeading: "Ce qu'Ask4Mo ne fait jamais",
    neverInference:
      "Aucune déduction d'émotion, d'humeur, de stress, de confiance, d'accent, de personnalité, d'intelligence, d'honnêteté ou d'aptitude à l'embauche, que ce soit à partir de votre voix ou autrement.",
    neverHiring:
      "Aucune décision d'embauche et aucun classement de candidats destiné aux recruteurs.",
    neverPrompts:
      "Aucune divulgation des invites système, des invites de développeur, du raisonnement interne ou de secrets.",
  },
  about: {
    pageTitle: "À propos d'Ask4Mo",
    lead:
      "Ask4Mo, l'Intelligent Interview Coach, aide les candidats à se préparer aux entretiens qui comptent. Son idée directrice est simple: Ask More. Be More. De meilleures questions, des réponses étayées et un entraînement honnête mènent à de meilleurs résultats.",
    trust:
      "Ask4Mo est conçu pour être digne de confiance avant tout. La préparation s'appuie sur des sources que vous pouvez vérifier, vos données sont privées par défaut, les décisions d'IA qui comptent requièrent votre approbation, et le produit est honnête sur ce qu'il peut et ne peut pas faire. Il ne prend pas de décisions d'embauche, ne classe pas les candidats pour les recruteurs et ne vous juge pas d'après votre voix.",
    capstone:
      "Ceci est un produit Capstone. Certaines capacités (par exemple la voix en temps réel en direct et certains jeux de données de connaissances) sont livrées avec un statut de validation honnête et clairement indiqué, plutôt qu'avec des promesses excessives.",
    seeAlso: "Voir aussi",
    imageAlt:
      "Deux personnes ayant une conversation de coaching réfléchie dans une bibliothèque calme.",
    contact:
      "Des questions ou des demandes de confidentialité? Contactez le support à l'adresse configurée pour votre déploiement (voir le Help Center une fois connecté).",
  },
  help: {
    heading: "Aide",
    eyebrow: "Comment fonctionne Ask4Mo",
    description:
      "Un guide consultable de chaque partie d'Ask4Mo, des idées qui le sous-tendent et d'une visite guidée rejouable.",
    journeyImageAlt:
      "Un parcours illustré, de la compréhension d'un rôle à la réflexion en passant par la conversation et l'entraînement.",
    tourTitle: "Nouveau ici?",
    tourBody: "Faites une visite guidée de deux minutes de tout le parcours.",
    searchLabel: "Rechercher dans l'aide",
    searchExamples: "Rechercher dans l'aide, par exemple progrès, sources, memory, rapport",
    noMatch: "Aucun sujet d'aide ne correspond à “{query}”. Essayez un autre mot.",
  },
  marketing: {
    heroImageAlt:
      "Un professionnel prépare des notes d'entretien à une table de salle à manger dans une douce lumière matinale.",
    problemImageAlt:
      "Des mains organisent recherches d'emploi, notes et documents d'entretien dans un dossier d'opportunity.",
    productImageAlt:
      "Un dossier d'opportunity dessiné à la main reliant recherche d'entreprise, preuves, conversation, entraînement et retours.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (mobile)",
  },
  trust: {
    imageAlt:
      "Une personne place des preuves privées dans un portfolio de documents contrôlé, à côté de documents sources.",
    moreDetail: "Plus de détails",
    isolationTerm: "Isolation du compte",
    isolationDesc:
      "Vos données sont limitées à votre compte. Les administrateurs de la plateforme utilisent une console d'exploitation bornée, avec des métadonnées uniquement; il n'y a pas d'affichage en tant qu'utilisateur ni de recherche dans les données privées.",
    privateTerm: "Privé par défaut",
    privateDesc:
      "Votre CV, vos réponses, rapports, Memory et Story Bank sont privés. Rien n'est partagé avec qui que ce soit, sauf si vous effectuez une action de partage explicite.",
    oppPrivateTerm: "Votre Opportunity est privée",
    oppPrivateDesc:
      "Une Opportunity est votre propre espace de préparation pour un poste. Elle vous est privée et distincte d'un workspace de collaboration. Les Opportunities ne sont jamais partagées automatiquement.",
    workspaceShareTerm: "Partage explicite dans un workspace",
    workspaceShareDesc:
      "Le partage dans un workspace est en lecture seule et toujours déclenché par vous. Retirer un partage ou quitter révoque l'accès.",
    sourcesTerm: "Des sources que vous pouvez vérifier",
    sourcesDesc:
      "Les réponses étayées citent les sources qui les sous-tendent. Lorsque les preuves manquent, Mo s'abstient plutôt que d'inventer des faits.",
    factsSeparateTerm: "Les faits sur l'entreprise restent séparés de l'opinion",
    factsSeparateDesc:
      "La recherche sur l'entreprise garde clairement séparés les faits, le contexte des avis de salariés et les suggestions d'IA, à partir de sources que vous pouvez vérifier. Les plateformes d'avis de salariés telles que Glassdoor et Kununu ne sont pas intégrées; Ask4Mo renvoie vers elles plutôt que de copier ou d'inventer des avis.",
    suggestionsTerm: "Les suggestions d'IA ne sont pas des faits",
    suggestionsDesc:
      "Les suggestions générées par le modèle et les retours d'entretien sont des conseils de coaching. Ils sont clairement séparés des preuves et ne sont jamais présentés comme des faits vérifiés.",
    evidenceGovernedTerm: "Vos preuves sont encadrées",
    evidenceGovernedDesc:
      "Seules les preuves de carrière que vous avez approuvées sont utilisées dans la préparation. Les preuves rejetées ou non examinées sont exclues, et supprimer une source la retire de l'usage.",
    layeredContextTerm: "Un contexte en couches, pas une seule mémoire",
    layeredContextDesc:
      "Vos préférences de compte, le contexte d'une Opportunity, vos choix par session et vos documents sont distincts. Ask4Mo ne les fusionne pas en un espace mémoire non contrôlé, et le Memory à long terme n'est enregistré que lorsque vous l'approuvez.",
    languageMarketTerm: "Votre langue, votre marché",
    languageMarketDesc:
      "Votre langue d'interface est distincte de votre langue d'entretien, de votre langue de dictée et de votre marché de l'emploi cible. Changer l'une ne change jamais les autres.",
    approvalsTerm: "Approbations humaines",
    approvalsDesc:
      "L'enregistrement de Memory à long terme et les transferts importants nécessitent votre approbation explicite.",
    noHiringTerm: "Aucune décision d'embauche",
    noHiringDesc:
      "Ask4Mo ne prend ni ne recommande de décisions d'embauche et ne classe pas les candidats pour les recruteurs.",
    noVoiceTraitTerm: "Aucune déduction de traits à partir de la voix",
    noVoiceTraitDesc:
      "Votre voix n'est jamais utilisée pour déduire l'émotion, la personnalité, la confiance, l'accent ou l'aptitude à l'embauche. Il n'existe aucun score de voix d'aucune sorte.",
    noAudioTerm: "Aucun stockage audio",
    noAudioDesc:
      "Ask4Mo n'enregistre ni ne conserve l'audio de votre microphone. La voix en temps réel est transmise à un fournisseur pour alimenter la conversation, selon la politique propre à ce fournisseur.",
    boundedAgentsTerm: "Des agents d'IA bornés",
    boundedAgentsDesc:
      "Mo utilise un petit ensemble d'outils autorisés avec une revalidation côté serveur. Il n'y a pas d'auto-modification autonome en production.",
    exportDeleteTerm: "Exporter et supprimer",
    exportDeleteDesc:
      "Vous pouvez exporter vos données et supprimer définitivement votre compte et les données contrôlées par l'application à tout moment.",
    providerBoundariesTerm: "Limites des fournisseurs",
    providerBoundariesDesc:
      "Les clés de fournisseur à longue durée restent côté serveur et ne sont jamais envoyées à votre navigateur. Les fonctions coûteuses ont des limites d'usage côté serveur et un interrupteur de pause pour l'exploitant.",
  },
};

const es: LegalFragment = {
  privacy: {
    pageTitle: "Privacidad",
    intro:
      "Esta página describe cómo Ask4Mo trata sus datos, a partir del inventario técnico real de datos del producto. Es un borrador de ingeniería y requiere revisión legal; no es una certificación de cumplimiento de ninguna normativa.",
    storeHeading: "Qué almacenamos",
    storeAccountTerm: "Datos de la cuenta",
    storeAccountDesc:
      "correo electrónico, nombre visible, estado de verificación, método de inicio de sesión, nivel de plan y rol en la plataforma.",
    storePrepTerm: "Datos de preparación",
    storePrepDesc: "sus objetivos, sus conversaciones con Mo y el contexto de preparación generado.",
    storeDocsTerm: "Documentos privados",
    storeDocsDesc:
      "los archivos que sube (por ejemplo un CV), almacenados de forma privada bajo una clave aleatoria, nunca en una URL pública. Texto extraído por OCR y datos detectados.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "sus respuestas, evaluaciones e informes.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "datos de preparación a largo plazo que ha aprobado explícitamente.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "historias reutilizables y respaldadas por evidencia que usted crea.",
    storeWorkspacesTerm: "Workspaces y uso compartido",
    storeWorkspacesDesc:
      "los workspaces que posee o a los que se une, y los elementos concretos que comparte de forma explícita.",
    storeFeedbackTerm: "Comentarios",
    storeFeedbackDesc: "valoraciones y comentarios que envía sobre las respuestas.",
    storeMetadataTerm: "Metadatos operativos",
    storeMetadataDesc:
      "identificadores de solicitud, marcas de tiempo, categorías generales de eventos y registros de auditoría de acciones privilegiadas o relevantes para la seguridad.",
    voiceHeading: "Voz, habla y tiempo real",
    voiceTurnBased:
      "La voz por turnos usa los motores de voz de su navegador o sistema operativo. Ask4Mo no graba ni almacena el audio de su micrófono.",
    voiceRealtime:
      "La voz en tiempo real (donde está habilitada) transmite audio a un proveedor de tiempo real para impulsar la conversación en vivo; ese tratamiento sigue la política propia del proveedor. Ask4Mo sigue sin almacenar audio.",
    voiceNoInference:
      "Ask4Mo nunca usa su voz para inferir emoción, personalidad, confianza, acento o idoneidad para la contratación. No hay ninguna puntuación de voz.",
    externalHeading: "Procesamiento externo",
    externalAi:
      "Las funciones de IA envían el texto necesario (no secretos) a un proveedor de modelos para generar respuestas.",
    externalResearch:
      "La investigación del mercado actual (opcional) puede consultar fuentes externas del mercado laboral.",
    externalEmail:
      "La entrega de correo usa un proveedor de correo transaccional para la verificación y la recuperación.",
    externalKeys:
      "Las claves de proveedor de larga duración permanecen en el servidor y nunca se envían a su navegador.",
    retentionHeading: "Conservación, exportación y eliminación",
    retentionExport:
      "Puede exportar sus datos y eliminar de forma permanente su cuenta y los datos controlados por la aplicación (documentos, archivos privados, historial de Practice, Memory, Story Bank, sesiones y puntos de control del agente).",
    retentionAudit:
      "Los registros de seguridad y auditoría se conservan y se anonimizan (se elimina el vínculo con su cuenta) en lugar de borrarse, para la revisión de seguridad.",
    retentionBackups:
      "Las copias de seguridad históricas de la infraestructura siguen el calendario de conservación del proveedor de alojamiento y no se borran al instante al eliminar; caducan según ese calendario.",
    retentionRights:
      "La privacidad, la seguridad y sus derechos sobre los datos están siempre disponibles, en todos los planes.",
    contactHeading: "Contacto",
    contactBody:
      "Para solicitudes de privacidad, contacte con la dirección de soporte configurada para su implementación. Este borrador se sustituirá por un texto revisado legalmente antes del lanzamiento público.",
  },
  terms: {
    pageTitle: "Condiciones de uso",
    intro:
      "Estas condiciones son un borrador de ingeniería y requieren revisión legal antes del lanzamiento público. Establecen las expectativas sobre el uso de Ask4Mo durante la fase de preproducción y revisión del producto.",
    whatHeading: "Qué es Ask4Mo",
    whatBody:
      "Ask4Mo ofrece orientación de preparación de entrevistas asistida por IA. Es una ayuda a la preparación, no un asesoramiento profesional, legal, financiero o laboral, y no sustituye su propio criterio.",
    aiHeading: "Límites de la IA",
    aiWrong:
      "La IA puede equivocarse o ser incompleta. Verifique todo lo importante con las fuentes citadas.",
    aiSources:
      "Las fuentes pueden ser parciales; algunos conjuntos de datos se publican con un estado explícito de borrador de ingeniería o no validado.",
    aiScores:
      "Las puntuaciones de Practice son orientación de preparación, no una medida objetiva de capacidad ni una predicción de los resultados de la entrevista.",
    aiNoHiring:
      "Ask4Mo no toma decisiones de contratación, no clasifica a los candidatos para los reclutadores ni le evalúa por su voz.",
    respHeading: "Sus responsabilidades",
    respAccurate: "Proporcione información exacta y mantenga seguras sus credenciales.",
    respUpload: "Suba únicamente contenido que tenga derecho a usar.",
    respLawful:
      "Use el servicio de forma lícita y no intente abusar de él ni sobrecargarlo.",
    accountsHeading: "Cuentas, planes y disponibilidad",
    accountsPlans:
      "Basic es gratuito. Premium se presenta como una vista previa; este producto no procesa ningún pago en línea.",
    accountsProviders:
      "Algunas funciones dependen de proveedores externos y pueden no estar disponibles, estar limitadas en frecuencia o pausadas por el operador.",
    accountsAsIs:
      "El servicio se proporciona tal cual durante esta fase previa al lanzamiento, sin garantías; la responsabilidad se limita en la máxima medida permitida por la ley aplicable (sujeto a revisión legal).",
    changesHeading: "Cambios",
    changesBody:
      "Estas condiciones se revisarán y se examinarán legalmente antes de cualquier lanzamiento público.",
  },
  aiTransparency: {
    pageTitle: "Transparencia de la IA y uso responsable",
    intro:
      "Queremos explicar con claridad, en lenguaje sencillo, cómo se usa la IA en Ask4Mo. Esta página es un borrador de ingeniería; el comportamiento subyacente se describe con honestidad.",
    whatMoHeading: "Qué es Mo",
    whatMoBody:
      "Mo es un asistente de coaching con IA que le ayuda a prepararse. Mo usa un conjunto acotado de herramientas y sigue un flujo gobernado; no actúa de forma autónoma más allá de prepararse con usted.",
    whenHeading: "Cuándo se usa la IA frente a la lógica determinista",
    whenAi:
      "La IA (un modelo) se usa para el coaching conversacional, la síntesis fundamentada, la generación de preguntas y la evaluación de respuestas e informes.",
    whenDeterministic:
      "La lógica determinista (sin modelo) se usa para lo que debe ser exacto y a prueba de inyecciones, por ejemplo seleccionar y ordenar su evidencia ya aprobada.",
    whenPolicy:
      "La elección del modelo por operación se rige por una política central del lado del servidor; su navegador nunca puede elegir un modelo en bruto.",
    specialistsHeading: "Especialistas, evidencia y fuentes",
    specialistsBounded:
      "Mo puede consultar especialistas acotados (rol y opportunity, evidencia, coaching) mediante herramientas autorizadas con revalidación del lado del servidor.",
    specialistsGrounded:
      "Las respuestas fundamentadas citan sus fuentes. Cuando falta evidencia, Mo se abstiene en lugar de inventar datos.",
    approvalsHeading: "Aprobaciones humanas y control",
    approvalsMemory:
      "Guardar Memory a largo plazo y las transferencias importantes requieren su aprobación explícita.",
    approvalsFeedback:
      "Sus comentarios nos ayudan a mejorar; nunca modifican automáticamente el producto en funcionamiento.",
    limitsHeading: "Limitaciones",
    limitsModels:
      "Los modelos pueden equivocarse; las puntuaciones de Practice son orientación, no un veredicto.",
    limitsRealtime:
      "La voz en tiempo real solo está disponible donde está configurada; de lo contrario se usan la voz por turnos y la escritura.",
    neverHeading: "Lo que Ask4Mo nunca hace",
    neverInference:
      "Ninguna inferencia de emoción, estado de ánimo, estrés, confianza, acento, personalidad, inteligencia, honestidad o idoneidad para la contratación, ni a partir de su voz ni de otro modo.",
    neverHiring:
      "Ninguna decisión de contratación ni clasificación de candidatos dirigida a reclutadores.",
    neverPrompts:
      "Ninguna exposición de instrucciones del sistema, instrucciones de desarrollador, razonamiento interno o secretos.",
  },
  about: {
    pageTitle: "Acerca de Ask4Mo",
    lead:
      "Ask4Mo, el Intelligent Interview Coach, ayuda a los candidatos a prepararse para las entrevistas que importan. Su idea rectora es simple: Ask More. Be More. Mejores preguntas, respuestas fundamentadas y práctica honesta conducen a mejores resultados.",
    trust:
      "Ask4Mo está construido para ser digno de confianza ante todo. La preparación se apoya en fuentes que puede verificar, sus datos son privados de forma predeterminada, las decisiones de IA que importan requieren su aprobación, y el producto es honesto sobre lo que puede y no puede hacer. No toma decisiones de contratación, no clasifica a los candidatos para los reclutadores ni le juzga por su voz.",
    capstone:
      "Este es un producto Capstone. Algunas capacidades (por ejemplo la voz en tiempo real en vivo y ciertos conjuntos de datos de conocimiento) se publican con un estado de validación honesto y claramente indicado, en lugar de prometer de más.",
    seeAlso: "Ver también",
    imageAlt:
      "Dos personas manteniendo una conversación de coaching reflexiva en una biblioteca tranquila.",
    contact:
      "¿Preguntas o solicitudes de privacidad? Contacte con el soporte en la dirección configurada para su implementación (consulte el Help Center una vez que inicie sesión).",
  },
  help: {
    heading: "Ayuda",
    eyebrow: "Cómo funciona Ask4Mo",
    description:
      "Una guía consultable de cada parte de Ask4Mo, las ideas que lo sustentan y una visita guiada que puede repetir.",
    journeyImageAlt:
      "Un recorrido ilustrado, desde comprender un rol hasta la reflexión, pasando por la conversación y la práctica.",
    tourTitle: "¿Nuevo por aquí?",
    tourBody: "Haga una visita guiada de dos minutos por todo el recorrido.",
    searchLabel: "Buscar en la ayuda",
    searchExamples: "Buscar en la ayuda, por ejemplo progreso, fuentes, memory, informe",
    noMatch: "Ningún tema de ayuda coincide con “{query}”. Pruebe con otra palabra.",
  },
  marketing: {
    heroImageAlt:
      "Un profesional prepara notas de entrevista en la mesa del comedor con una suave luz matinal.",
    problemImageAlt:
      "Unas manos organizan la investigación de empleo, las notas y los materiales de entrevista en una carpeta de opportunity.",
    productImageAlt:
      "Una carpeta de opportunity dibujada a mano que conecta la investigación de empresa, la evidencia, la conversación, la práctica y los comentarios.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (móvil)",
  },
  trust: {
    imageAlt:
      "Una persona coloca evidencia privada en un portafolio de documentos controlado, junto a material de origen.",
    moreDetail: "Más detalles",
    isolationTerm: "Aislamiento de la cuenta",
    isolationDesc:
      "Sus datos están acotados a su cuenta. Los administradores de la plataforma operan una consola de operaciones acotada, solo con metadatos; no hay ver como usuario ni búsqueda en datos privados.",
    privateTerm: "Privado de forma predeterminada",
    privateDesc:
      "Su CV, respuestas, informes, Memory y Story Bank son privados. No se comparte nada con nadie a menos que realice una acción de uso compartido explícita.",
    oppPrivateTerm: "Su Opportunity es privada",
    oppPrivateDesc:
      "Una Opportunity es su propio espacio de preparación para un empleo. Es privada para usted y está separada de un workspace de colaboración. Las Opportunities nunca se comparten automáticamente.",
    workspaceShareTerm: "Uso compartido explícito en el workspace",
    workspaceShareDesc:
      "Compartir en un workspace es solo de lectura y siempre lo inicia usted. Retirar un elemento compartido o salir revoca el acceso.",
    sourcesTerm: "Fuentes que puede verificar",
    sourcesDesc:
      "Las respuestas fundamentadas citan las fuentes que las respaldan. Cuando falta evidencia, Mo se abstiene en lugar de inventar datos.",
    factsSeparateTerm: "Los hechos de la empresa se mantienen separados de la opinión",
    factsSeparateDesc:
      "La investigación de empresa mantiene claramente separados los hechos, el contexto de las opiniones de empleados y las sugerencias de IA, a partir de fuentes que puede verificar. Las plataformas de opiniones de empleados como Glassdoor y Kununu no están integradas; Ask4Mo enlaza a ellas en lugar de copiar o inventar opiniones.",
    suggestionsTerm: "Las sugerencias de IA no son hechos",
    suggestionsDesc:
      "Las sugerencias generadas por el modelo y los comentarios de entrevista son orientación de coaching. Están claramente separados de la evidencia y nunca se presentan como hechos verificados.",
    evidenceGovernedTerm: "Su evidencia está gobernada",
    evidenceGovernedDesc:
      "En la preparación solo se usa la evidencia profesional que usted ha aprobado. La evidencia rechazada o sin revisar queda excluida, y eliminar una fuente la retira del uso.",
    layeredContextTerm: "Contexto por capas, no una sola memoria",
    layeredContextDesc:
      "Sus preferencias de cuenta, el contexto de una Opportunity, sus elecciones por sesión y sus documentos son distintos. Ask4Mo no los fusiona en un único almacén de memoria sin control, y el Memory a largo plazo solo se guarda cuando usted lo aprueba.",
    languageMarketTerm: "Su idioma, su mercado",
    languageMarketDesc:
      "Su idioma de interfaz es distinto de su idioma de entrevista, su idioma de dictado y su mercado laboral objetivo. Cambiar uno nunca cambia los demás.",
    approvalsTerm: "Aprobaciones humanas",
    approvalsDesc:
      "Guardar Memory a largo plazo y las transferencias importantes requieren su aprobación explícita.",
    noHiringTerm: "Ninguna decisión de contratación",
    noHiringDesc:
      "Ask4Mo no toma ni recomienda decisiones de contratación y no clasifica a los candidatos para los reclutadores.",
    noVoiceTraitTerm: "Ninguna inferencia de rasgos a partir de la voz",
    noVoiceTraitDesc:
      "Su voz nunca se usa para inferir emoción, personalidad, confianza, acento o idoneidad para la contratación. No existe puntuación de voz de ningún tipo.",
    noAudioTerm: "Sin almacenamiento de audio",
    noAudioDesc:
      "Ask4Mo no graba ni almacena el audio de su micrófono. La voz en tiempo real se transmite a un proveedor para impulsar la conversación, bajo la política propia de ese proveedor.",
    boundedAgentsTerm: "Agentes de IA acotados",
    boundedAgentsDesc:
      "Mo usa un conjunto pequeño y autorizado de herramientas con revalidación del lado del servidor. No hay automodificación autónoma en producción.",
    exportDeleteTerm: "Exportar y eliminar",
    exportDeleteDesc:
      "Puede exportar sus datos y eliminar de forma permanente su cuenta y los datos controlados por la aplicación en cualquier momento.",
    providerBoundariesTerm: "Límites de los proveedores",
    providerBoundariesDesc:
      "Las claves de proveedor de larga duración permanecen en el servidor y nunca se envían a su navegador. Las funciones costosas tienen límites de uso del lado del servidor y un interruptor de pausa para el operador.",
  },
};

const it: LegalFragment = {
  privacy: {
    pageTitle: "Privacy",
    intro:
      "Questa pagina descrive come Ask4Mo tratta i tuoi dati, in base all'inventario tecnico reale dei dati del prodotto. È una bozza di ingegneria e richiede una revisione legale; non è una certificazione di conformità ad alcuna normativa.",
    storeHeading: "Cosa conserviamo",
    storeAccountTerm: "Dati dell'account",
    storeAccountDesc:
      "email, nome visualizzato, stato di verifica, metodo di accesso, livello del piano e ruolo nella piattaforma.",
    storePrepTerm: "Dati di preparazione",
    storePrepDesc: "i tuoi obiettivi, le conversazioni con Mo e il contesto di preparazione generato.",
    storeDocsTerm: "Documenti privati",
    storeDocsDesc:
      "i file che carichi (per esempio un CV), conservati in modo privato con una chiave casuale, mai con un URL pubblico. Testo estratto tramite OCR ed elementi rilevati.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "le tue risposte, valutazioni e report.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "informazioni di preparazione a lungo termine che hai approvato esplicitamente.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "storie riutilizzabili e supportate da evidenze che crei tu.",
    storeWorkspacesTerm: "Workspace e condivisione",
    storeWorkspacesDesc:
      "i workspace che possiedi o a cui ti unisci e gli elementi specifici che condividi esplicitamente.",
    storeFeedbackTerm: "Feedback",
    storeFeedbackDesc: "valutazioni e commenti che invii sulle risposte.",
    storeMetadataTerm: "Metadati operativi",
    storeMetadataDesc:
      "identificatori di richiesta, marche temporali, categorie generiche di eventi e registri di audit di azioni privilegiate o rilevanti per la sicurezza.",
    voiceHeading: "Voce, parlato e tempo reale",
    voiceTurnBased:
      "La voce a turni usa i motori vocali del tuo browser o sistema operativo. Ask4Mo non registra né conserva l'audio del tuo microfono.",
    voiceRealtime:
      "La voce in tempo reale (dove abilitata) trasmette l'audio a un provider in tempo reale per alimentare la conversazione dal vivo; tale trattamento segue la policy propria del provider. Ask4Mo continua a non conservare alcun audio.",
    voiceNoInference:
      "Ask4Mo non usa mai la tua voce per dedurre emozione, personalità, sicurezza, accento o idoneità all'assunzione. Non esiste alcun punteggio della voce.",
    externalHeading: "Trattamento esterno",
    externalAi:
      "Le funzioni di IA inviano il testo necessario (non segreti) a un provider di modelli per generare risposte.",
    externalResearch:
      "La ricerca sul mercato attuale (opzionale) può interrogare fonti esterne del mercato del lavoro.",
    externalEmail:
      "La consegna delle email usa un provider di email transazionali per la verifica e il recupero.",
    externalKeys:
      "Le chiavi dei provider a lunga durata restano lato server e non vengono mai inviate al tuo browser.",
    retentionHeading: "Conservazione, esportazione ed eliminazione",
    retentionExport:
      "Puoi esportare i tuoi dati ed eliminare in modo permanente il tuo account e i dati controllati dall'applicazione (documenti, file privati, cronologia di Practice, Memory, Story Bank, sessioni e checkpoint dell'agente).",
    retentionAudit:
      "I registri di sicurezza e di audit vengono conservati e anonimizzati (il collegamento al tuo account viene rimosso) anziché eliminati, per la revisione di sicurezza.",
    retentionBackups:
      "I backup storici dell'infrastruttura seguono il calendario di conservazione del provider di hosting e non vengono cancellati immediatamente all'eliminazione; scadono in base a tale calendario.",
    retentionRights:
      "Privacy, sicurezza e i tuoi diritti sui dati sono sempre disponibili, in ogni piano.",
    contactHeading: "Contatto",
    contactBody:
      "Per le richieste relative alla privacy, contatta l'indirizzo di supporto configurato per il tuo deployment. Questa bozza sarà sostituita da testi rivisti legalmente prima del lancio pubblico.",
  },
  terms: {
    pageTitle: "Condizioni d'uso",
    intro:
      "Queste condizioni sono una bozza di ingegneria e richiedono una revisione legale prima del lancio pubblico. Stabiliscono le aspettative sull'uso di Ask4Mo durante le fasi di staging e revisione del prodotto.",
    whatHeading: "Cos'è Ask4Mo",
    whatBody:
      "Ask4Mo fornisce orientamento alla preparazione dei colloqui assistito dall'IA. È un aiuto alla preparazione, non una consulenza professionale, legale, finanziaria o in materia di lavoro, e non sostituisce il tuo giudizio.",
    aiHeading: "Limiti dell'IA",
    aiWrong:
      "L'IA può sbagliare o essere incompleta. Verifica qualsiasi cosa importante con le fonti citate.",
    aiSources:
      "Le fonti possono essere parziali; alcuni set di dati vengono rilasciati con uno stato esplicito di bozza di ingegneria o non convalidato.",
    aiScores:
      "I punteggi di Practice sono orientamento alla preparazione, non una misura oggettiva della capacità né una previsione dell'esito del colloquio.",
    aiNoHiring:
      "Ask4Mo non prende decisioni di assunzione, non classifica i candidati per i selezionatori e non ti valuta in base alla tua voce.",
    respHeading: "Le tue responsabilità",
    respAccurate: "Fornisci informazioni accurate e mantieni al sicuro le tue credenziali.",
    respUpload: "Carica solo contenuti che hai il diritto di usare.",
    respLawful:
      "Usa il servizio in modo lecito e non tentare di abusarne o di sovraccaricarlo.",
    accountsHeading: "Account, piani e disponibilità",
    accountsPlans:
      "Basic è gratuito. Premium è presentato come anteprima; questo prodotto non elabora alcun pagamento online.",
    accountsProviders:
      "Alcune funzioni dipendono da provider esterni e possono essere non disponibili, limitate nella frequenza o messe in pausa dall'operatore.",
    accountsAsIs:
      "Il servizio è fornito così com'è durante questa fase di pre-lancio, senza garanzie; la responsabilità è limitata nella misura massima consentita dalla legge applicabile (soggetto a revisione legale).",
    changesHeading: "Modifiche",
    changesBody:
      "Queste condizioni saranno riviste ed esaminate legalmente prima di qualsiasi lancio pubblico.",
  },
  aiTransparency: {
    pageTitle: "Trasparenza dell'IA e uso responsabile",
    intro:
      "Vogliamo spiegare con chiarezza, in un linguaggio semplice, come viene usata l'IA in Ask4Mo. Questa pagina è una bozza di ingegneria; il comportamento sottostante è descritto in modo onesto.",
    whatMoHeading: "Cos'è Mo",
    whatMoBody:
      "Mo è un assistente di coaching con IA che ti aiuta a prepararti. Mo usa un insieme limitato di strumenti e segue un flusso regolato; non agisce in modo autonomo oltre alla preparazione con te.",
    whenHeading: "Quando si usa l'IA rispetto alla logica deterministica",
    whenAi:
      "L'IA (un modello) viene usata per il coaching conversazionale, la sintesi fondata sulle evidenze, la generazione di domande e la valutazione di risposte e report.",
    whenDeterministic:
      "La logica deterministica (nessun modello) viene usata per ciò che deve essere esatto e a prova di injection, per esempio selezionare e ordinare le tue evidenze già approvate.",
    whenPolicy:
      "La scelta del modello per operazione è regolata da una policy centrale lato server; il tuo browser non può mai scegliere un modello grezzo.",
    specialistsHeading: "Specialisti, evidenze e fonti",
    specialistsBounded:
      "Mo può consultare specialisti limitati (ruolo e opportunity, evidenze, coaching) tramite strumenti autorizzati con riconvalida lato server.",
    specialistsGrounded:
      "Le risposte fondate citano le loro fonti. Quando mancano le evidenze, Mo si astiene anziché inventare fatti.",
    approvalsHeading: "Approvazioni umane e controllo",
    approvalsMemory:
      "Il salvataggio di Memory a lungo termine e i passaggi di consegne importanti richiedono la tua approvazione esplicita.",
    approvalsFeedback:
      "Il tuo feedback ci aiuta a migliorare; non modifica mai automaticamente il prodotto in funzione.",
    limitsHeading: "Limitazioni",
    limitsModels:
      "I modelli possono sbagliare; i punteggi di Practice sono orientamento, non un verdetto.",
    limitsRealtime:
      "La voce in tempo reale è disponibile solo dove è configurata; altrimenti si usano la voce a turni e la digitazione.",
    neverHeading: "Cosa Ask4Mo non fa mai",
    neverInference:
      "Nessuna deduzione di emozione, umore, stress, sicurezza, accento, personalità, intelligenza, onestà o idoneità all'assunzione, né dalla tua voce né in altro modo.",
    neverHiring:
      "Nessuna decisione di assunzione e nessuna classifica di candidati destinata ai selezionatori.",
    neverPrompts:
      "Nessuna divulgazione di prompt di sistema, prompt dello sviluppatore, ragionamento interno o segreti.",
  },
  about: {
    pageTitle: "Informazioni su Ask4Mo",
    lead:
      "Ask4Mo, l'Intelligent Interview Coach, aiuta i candidati a prepararsi per i colloqui che contano. La sua idea guida è semplice: Ask More. Be More. Domande migliori, risposte fondate e una pratica onesta portano a risultati migliori.",
    trust:
      "Ask4Mo è costruito per essere affidabile prima di tutto. La preparazione si basa su fonti che puoi verificare, i tuoi dati sono privati per impostazione predefinita, le decisioni di IA che contano richiedono la tua approvazione e il prodotto è onesto su ciò che può e non può fare. Non prende decisioni di assunzione, non classifica i candidati per i selezionatori e non ti giudica in base alla tua voce.",
    capstone:
      "Questo è un prodotto Capstone. Alcune funzionalità (per esempio la voce in tempo reale dal vivo e alcuni set di dati di conoscenza) vengono rilasciate con uno stato di convalida onesto e chiaramente indicato, anziché con promesse eccessive.",
    seeAlso: "Vedi anche",
    imageAlt:
      "Due persone in una conversazione di coaching riflessiva in una biblioteca tranquilla.",
    contact:
      "Domande o richieste relative alla privacy? Contatta il supporto all'indirizzo configurato per il tuo deployment (vedi l'Help Center una volta effettuato l'accesso).",
  },
  help: {
    heading: "Aiuto",
    eyebrow: "Come funziona Ask4Mo",
    description:
      "Una guida consultabile di ogni parte di Ask4Mo, delle idee alla base e di un tour guidato ripetibile.",
    journeyImageAlt:
      "Un percorso illustrato, dalla comprensione di un ruolo alla riflessione, passando per conversazione e pratica.",
    tourTitle: "Nuovo qui?",
    tourBody: "Fai un tour guidato di due minuti dell'intero percorso.",
    searchLabel: "Cerca nell'aiuto",
    searchExamples: "Cerca nell'aiuto, per esempio progressi, fonti, memory, report",
    noMatch: "Nessun argomento di aiuto corrisponde a “{query}”. Prova con un'altra parola.",
  },
  marketing: {
    heroImageAlt:
      "Un professionista prepara appunti per il colloquio al tavolo da pranzo nella morbida luce del mattino.",
    problemImageAlt:
      "Mani che organizzano ricerca di lavoro, appunti e materiali per il colloquio in una cartella opportunity.",
    productImageAlt:
      "Una cartella opportunity disegnata a mano che collega ricerca sull'azienda, evidenze, conversazione, pratica e feedback.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (mobile)",
  },
  trust: {
    imageAlt:
      "Una persona ripone evidenze private in una cartella di documenti controllata, accanto a materiale di origine.",
    moreDetail: "Maggiori dettagli",
    isolationTerm: "Isolamento dell'account",
    isolationDesc:
      "I tuoi dati sono circoscritti al tuo account. Gli amministratori della piattaforma usano una console operativa limitata, solo con metadati; non c'è alcuna visualizzazione come utente né ricerca nei dati privati.",
    privateTerm: "Privato per impostazione predefinita",
    privateDesc:
      "Il tuo CV, le risposte, i report, Memory e Story Bank sono privati. Nulla viene condiviso con nessuno a meno che tu non compia un'azione di condivisione esplicita.",
    oppPrivateTerm: "La tua Opportunity è privata",
    oppPrivateDesc:
      "Una Opportunity è il tuo spazio di preparazione per un lavoro. È privata per te e separata da un workspace di collaborazione. Le Opportunity non vengono mai condivise automaticamente.",
    workspaceShareTerm: "Condivisione esplicita nel workspace",
    workspaceShareDesc:
      "La condivisione in un workspace è in sola lettura ed è sempre avviata da te. Rimuovere una condivisione o uscire revoca l'accesso.",
    sourcesTerm: "Fonti che puoi verificare",
    sourcesDesc:
      "Le risposte fondate citano le fonti che le supportano. Quando mancano le evidenze, Mo si astiene anziché inventare fatti.",
    factsSeparateTerm: "I fatti sull'azienda restano separati dall'opinione",
    factsSeparateDesc:
      "La ricerca sull'azienda mantiene chiaramente separati i fatti, il contesto delle recensioni dei dipendenti e i suggerimenti dell'IA, da fonti che puoi verificare. Le piattaforme di recensioni dei dipendenti come Glassdoor e Kununu non sono integrate; Ask4Mo rimanda ad esse anziché copiare o inventare recensioni.",
    suggestionsTerm: "I suggerimenti dell'IA non sono fatti",
    suggestionsDesc:
      "I suggerimenti generati dal modello e il feedback sul colloquio sono orientamento di coaching. Sono chiaramente separati dalle evidenze e non vengono mai presentati come fatti verificati.",
    evidenceGovernedTerm: "Le tue evidenze sono governate",
    evidenceGovernedDesc:
      "Nella preparazione vengono usate solo le evidenze di carriera che hai approvato. Le evidenze rifiutate o non esaminate sono escluse, ed eliminare una fonte la rimuove dall'uso.",
    layeredContextTerm: "Contesto a livelli, non un'unica memoria",
    layeredContextDesc:
      "Le tue preferenze dell'account, il contesto di una Opportunity, le tue scelte per sessione e i tuoi documenti sono distinti. Ask4Mo non li unisce in un unico archivio di memoria non controllato, e il Memory a lungo termine viene salvato solo quando lo approvi.",
    languageMarketTerm: "La tua lingua, il tuo mercato",
    languageMarketDesc:
      "La lingua dell'interfaccia è distinta dalla lingua del colloquio, dalla lingua di dettatura e dal tuo mercato del lavoro di riferimento. Cambiarne una non cambia mai le altre.",
    approvalsTerm: "Approvazioni umane",
    approvalsDesc:
      "Il salvataggio di Memory a lungo termine e i passaggi di consegne importanti richiedono la tua approvazione esplicita.",
    noHiringTerm: "Nessuna decisione di assunzione",
    noHiringDesc:
      "Ask4Mo non prende né raccomanda decisioni di assunzione e non classifica i candidati per i selezionatori.",
    noVoiceTraitTerm: "Nessuna deduzione di tratti dalla voce",
    noVoiceTraitDesc:
      "La tua voce non viene mai usata per dedurre emozione, personalità, sicurezza, accento o idoneità all'assunzione. Non esiste alcun punteggio della voce di alcun tipo.",
    noAudioTerm: "Nessuna conservazione dell'audio",
    noAudioDesc:
      "Ask4Mo non registra né conserva l'audio del tuo microfono. La voce in tempo reale viene trasmessa a un provider per alimentare la conversazione, secondo la policy propria di tale provider.",
    boundedAgentsTerm: "Agenti di IA limitati",
    boundedAgentsDesc:
      "Mo usa un piccolo insieme autorizzato di strumenti con riconvalida lato server. Non c'è alcuna automodifica autonoma in produzione.",
    exportDeleteTerm: "Esporta ed elimina",
    exportDeleteDesc:
      "Puoi esportare i tuoi dati ed eliminare in modo permanente il tuo account e i dati controllati dall'applicazione in qualsiasi momento.",
    providerBoundariesTerm: "Limiti dei provider",
    providerBoundariesDesc:
      "Le chiavi dei provider a lunga durata restano lato server e non vengono mai inviate al tuo browser. Le funzioni costose hanno limiti d'uso lato server e un interruttore di pausa per l'operatore.",
  },
};

const pt: LegalFragment = {
  privacy: {
    pageTitle: "Privacidade",
    intro:
      "Esta página descreve como o Ask4Mo trata os seus dados, com base no inventário técnico real de dados do produto. É um rascunho de engenharia e requer revisão jurídica; não é uma certificação de conformidade com qualquer regulamentação.",
    storeHeading: "O que armazenamos",
    storeAccountTerm: "Dados da conta",
    storeAccountDesc:
      "e-mail, nome de exibição, estado de verificação, método de início de sessão, nível do plano e função na plataforma.",
    storePrepTerm: "Dados de preparação",
    storePrepDesc: "os seus objetivos, as conversas com o Mo e o contexto de preparação gerado.",
    storeDocsTerm: "Documentos privados",
    storeDocsDesc:
      "os ficheiros que carrega (por exemplo um CV), armazenados de forma privada sob uma chave aleatória, nunca num URL público. Texto extraído por OCR e dados detetados.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "as suas respostas, avaliações e relatórios.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "factos de preparação de longo prazo que aprovou explicitamente.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "histórias reutilizáveis e apoiadas em evidências que você cria.",
    storeWorkspacesTerm: "Workspaces e partilha",
    storeWorkspacesDesc:
      "os workspaces que possui ou a que adere, e os itens específicos que partilha explicitamente.",
    storeFeedbackTerm: "Comentários",
    storeFeedbackDesc: "classificações e comentários que envia sobre as respostas.",
    storeMetadataTerm: "Metadados operacionais",
    storeMetadataDesc:
      "identificadores de pedido, marcas temporais, categorias gerais de eventos e registos de auditoria de ações privilegiadas ou relevantes para a segurança.",
    voiceHeading: "Voz, fala e tempo real",
    voiceTurnBased:
      "A voz por turnos usa os motores de fala do seu navegador ou sistema operativo. O Ask4Mo não grava nem armazena o áudio do seu microfone.",
    voiceRealtime:
      "A voz em tempo real (onde está ativada) transmite áudio a um fornecedor de tempo real para suportar a conversa em direto; esse tratamento segue a política do próprio fornecedor. O Ask4Mo continua sem armazenar áudio.",
    voiceNoInference:
      "O Ask4Mo nunca usa a sua voz para inferir emoção, personalidade, confiança, sotaque ou adequação para contratação. Não existe pontuação de voz.",
    externalHeading: "Processamento externo",
    externalAi:
      "As funcionalidades de IA enviam o texto necessário (não segredos) a um fornecedor de modelos para gerar respostas.",
    externalResearch:
      "A pesquisa do mercado atual (opcional) pode consultar fontes externas do mercado de trabalho.",
    externalEmail:
      "A entrega de e-mail usa um fornecedor de e-mail transacional para verificação e recuperação.",
    externalKeys:
      "As chaves de fornecedor de longa duração permanecem no servidor e nunca são enviadas para o seu navegador.",
    retentionHeading: "Retenção, exportação e eliminação",
    retentionExport:
      "Pode exportar os seus dados e eliminar de forma permanente a sua conta e os dados controlados pela aplicação (documentos, ficheiros privados, histórico de Practice, Memory, Story Bank, sessões e checkpoints do agente).",
    retentionAudit:
      "Os registos de segurança e auditoria são retidos e anonimizados (a ligação à sua conta é removida) em vez de eliminados, para revisão de segurança.",
    retentionBackups:
      "As cópias de segurança históricas da infraestrutura seguem o calendário de retenção do fornecedor de alojamento e não são apagadas de imediato na eliminação; expiram de acordo com esse calendário.",
    retentionRights:
      "A privacidade, a segurança e os seus direitos sobre os dados estão sempre disponíveis, em todos os planos.",
    contactHeading: "Contacto",
    contactBody:
      "Para pedidos de privacidade, contacte o endereço de suporte configurado para a sua implementação. Este rascunho será substituído por texto revisto juridicamente antes do lançamento público.",
  },
  terms: {
    pageTitle: "Termos de utilização",
    intro:
      "Estes termos são um rascunho de engenharia e requerem revisão jurídica antes do lançamento público. Definem as expectativas quanto à utilização do Ask4Mo durante as fases de staging e revisão do produto.",
    whatHeading: "O que é o Ask4Mo",
    whatBody:
      "O Ask4Mo fornece orientação de preparação para entrevistas assistida por IA. É um apoio à preparação, não um aconselhamento profissional, jurídico, financeiro ou laboral, e não substitui o seu próprio julgamento.",
    aiHeading: "Limites da IA",
    aiWrong:
      "A IA pode estar errada ou incompleta. Verifique tudo o que for importante com as fontes citadas.",
    aiSources:
      "As fontes podem ser parciais; alguns conjuntos de dados são disponibilizados com um estado explícito de rascunho de engenharia ou não validado.",
    aiScores:
      "As pontuações de Practice são orientação de preparação, não uma medida objetiva de capacidade nem uma previsão dos resultados da entrevista.",
    aiNoHiring:
      "O Ask4Mo não toma decisões de contratação, não classifica candidatos para recrutadores nem o avalia pela sua voz.",
    respHeading: "As suas responsabilidades",
    respAccurate: "Forneça informações exatas e mantenha as suas credenciais seguras.",
    respUpload: "Carregue apenas conteúdo que tenha o direito de usar.",
    respLawful:
      "Use o serviço de forma lícita e não tente abusar dele nem sobrecarregá-lo.",
    accountsHeading: "Contas, planos e disponibilidade",
    accountsPlans:
      "O Basic é gratuito. O Premium é apresentado como uma pré-visualização; este produto não processa qualquer pagamento online.",
    accountsProviders:
      "Algumas funcionalidades dependem de fornecedores externos e podem estar indisponíveis, limitadas na frequência ou pausadas pelo operador.",
    accountsAsIs:
      "O serviço é fornecido no estado em que se encontra durante esta fase anterior ao lançamento, sem garantias; a responsabilidade é limitada na medida máxima permitida pela lei aplicável (sujeito a revisão jurídica).",
    changesHeading: "Alterações",
    changesBody:
      "Estes termos serão revistos e analisados juridicamente antes de qualquer lançamento público.",
  },
  aiTransparency: {
    pageTitle: "Transparência da IA e uso responsável",
    intro:
      "Queremos explicar com clareza, em linguagem simples, como a IA é usada no Ask4Mo. Esta página é um rascunho de engenharia; o comportamento subjacente é descrito de forma honesta.",
    whatMoHeading: "O que é o Mo",
    whatMoBody:
      "O Mo é um assistente de coaching com IA que o ajuda a preparar-se. O Mo usa um conjunto limitado de ferramentas e segue um fluxo governado; não age de forma autónoma para além de se preparar consigo.",
    whenHeading: "Quando se usa a IA face à lógica determinista",
    whenAi:
      "A IA (um modelo) é usada para o coaching conversacional, a síntese fundamentada, a geração de perguntas e a avaliação de respostas e relatórios.",
    whenDeterministic:
      "A lógica determinista (sem modelo) é usada para o que tem de ser exato e à prova de injeção, por exemplo selecionar e ordenar as suas evidências já aprovadas.",
    whenPolicy:
      "A escolha do modelo por operação é regida por uma política central do lado do servidor; o seu navegador nunca pode escolher um modelo em bruto.",
    specialistsHeading: "Especialistas, evidências e fontes",
    specialistsBounded:
      "O Mo pode consultar especialistas limitados (função e opportunity, evidências, coaching) através de ferramentas autorizadas com revalidação do lado do servidor.",
    specialistsGrounded:
      "As respostas fundamentadas citam as suas fontes. Quando faltam evidências, o Mo abstém-se em vez de inventar factos.",
    approvalsHeading: "Aprovações humanas e controlo",
    approvalsMemory:
      "Guardar Memory de longo prazo e as transferências importantes requerem a sua aprovação explícita.",
    approvalsFeedback:
      "Os seus comentários ajudam-nos a melhorar; nunca modificam automaticamente o produto em funcionamento.",
    limitsHeading: "Limitações",
    limitsModels:
      "Os modelos podem errar; as pontuações de Practice são orientação, não um veredicto.",
    limitsRealtime:
      "A voz em tempo real só está disponível onde estiver configurada; caso contrário, usam-se a voz por turnos e a escrita.",
    neverHeading: "O que o Ask4Mo nunca faz",
    neverInference:
      "Nenhuma inferência de emoção, humor, stress, confiança, sotaque, personalidade, inteligência, honestidade ou adequação para contratação, seja a partir da sua voz ou de outra forma.",
    neverHiring:
      "Nenhuma decisão de contratação e nenhuma classificação de candidatos dirigida a recrutadores.",
    neverPrompts:
      "Nenhuma exposição de prompts de sistema, prompts de programador, raciocínio interno ou segredos.",
  },
  about: {
    pageTitle: "Sobre o Ask4Mo",
    lead:
      "O Ask4Mo, o Intelligent Interview Coach, ajuda os candidatos a prepararem-se para as entrevistas que contam. A sua ideia orientadora é simples: Ask More. Be More. Melhores perguntas, respostas fundamentadas e uma prática honesta levam a melhores resultados.",
    trust:
      "O Ask4Mo é construído para ser digno de confiança acima de tudo. A preparação apoia-se em fontes que pode verificar, os seus dados são privados por predefinição, as decisões de IA que importam requerem a sua aprovação, e o produto é honesto sobre o que pode e não pode fazer. Não toma decisões de contratação, não classifica candidatos para recrutadores nem o julga pela sua voz.",
    capstone:
      "Este é um produto Capstone. Algumas capacidades (por exemplo a voz em tempo real em direto e certos conjuntos de dados de conhecimento) são disponibilizadas com um estado de validação honesto e claramente indicado, em vez de prometer demais.",
    seeAlso: "Ver também",
    imageAlt:
      "Duas pessoas numa conversa de coaching ponderada numa biblioteca tranquila.",
    contact:
      "Dúvidas ou pedidos de privacidade? Contacte o suporte no endereço configurado para a sua implementação (consulte o Help Center depois de iniciar sessão).",
  },
  help: {
    heading: "Ajuda",
    eyebrow: "Como funciona o Ask4Mo",
    description:
      "Um guia pesquisável de cada parte do Ask4Mo, das ideias por trás dele e de uma visita guiada que pode repetir.",
    journeyImageAlt:
      "Um percurso ilustrado, da compreensão de uma função até à reflexão, passando por conversa e prática.",
    tourTitle: "É novo por aqui?",
    tourBody: "Faça uma visita guiada de dois minutos por todo o percurso.",
    searchLabel: "Pesquisar na ajuda",
    searchExamples: "Pesquisar na ajuda, por exemplo progresso, fontes, memory, relatório",
    noMatch: "Nenhum tópico de ajuda corresponde a “{query}”. Tente outra palavra.",
  },
  marketing: {
    heroImageAlt:
      "Um profissional prepara notas de entrevista à mesa de jantar sob uma luz suave da manhã.",
    problemImageAlt:
      "Mãos a organizar pesquisa de emprego, notas e materiais de entrevista numa pasta de opportunity.",
    productImageAlt:
      "Uma pasta de opportunity desenhada à mão que liga pesquisa de empresa, evidências, conversa, prática e comentários.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (móvel)",
  },
  trust: {
    imageAlt:
      "Uma pessoa coloca evidências privadas numa pasta de documentos controlada, ao lado de material de origem.",
    moreDetail: "Mais detalhes",
    isolationTerm: "Isolamento da conta",
    isolationDesc:
      "Os seus dados estão circunscritos à sua conta. Os administradores da plataforma operam uma consola de operações limitada, apenas com metadados; não há visualização como utilizador nem pesquisa em dados privados.",
    privateTerm: "Privado por predefinição",
    privateDesc:
      "O seu CV, respostas, relatórios, Memory e Story Bank são privados. Nada é partilhado com ninguém a menos que efetue uma ação de partilha explícita.",
    oppPrivateTerm: "A sua Opportunity é privada",
    oppPrivateDesc:
      "Uma Opportunity é o seu próprio espaço de preparação para um emprego. É privada para si e separada de um workspace de colaboração. As Opportunities nunca são partilhadas automaticamente.",
    workspaceShareTerm: "Partilha explícita no workspace",
    workspaceShareDesc:
      "A partilha num workspace é apenas de leitura e é sempre iniciada por si. Remover uma partilha ou sair revoga o acesso.",
    sourcesTerm: "Fontes que pode verificar",
    sourcesDesc:
      "As respostas fundamentadas citam as fontes que as apoiam. Quando faltam evidências, o Mo abstém-se em vez de inventar factos.",
    factsSeparateTerm: "Os factos sobre a empresa mantêm-se separados da opinião",
    factsSeparateDesc:
      "A pesquisa de empresa mantém claramente separados os factos, o contexto das avaliações de colaboradores e as sugestões de IA, a partir de fontes que pode verificar. As plataformas de avaliações de colaboradores como o Glassdoor e o Kununu não estão integradas; o Ask4Mo remete para elas em vez de copiar ou inventar avaliações.",
    suggestionsTerm: "As sugestões de IA não são factos",
    suggestionsDesc:
      "As sugestões geradas pelo modelo e os comentários de entrevista são orientação de coaching. Estão claramente separados das evidências e nunca são apresentados como factos verificados.",
    evidenceGovernedTerm: "As suas evidências são governadas",
    evidenceGovernedDesc:
      "Na preparação só são usadas as evidências de carreira que aprovou. As evidências rejeitadas ou não revistas são excluídas, e eliminar uma fonte retira-a do uso.",
    layeredContextTerm: "Contexto em camadas, não uma única memória",
    layeredContextDesc:
      "As suas preferências de conta, o contexto de uma Opportunity, as suas escolhas por sessão e os seus documentos são distintos. O Ask4Mo não os funde num único armazenamento de memória não controlado, e o Memory de longo prazo só é guardado quando o aprova.",
    languageMarketTerm: "O seu idioma, o seu mercado",
    languageMarketDesc:
      "O seu idioma de interface é distinto do seu idioma de entrevista, do seu idioma de ditado e do seu mercado de trabalho alvo. Alterar um nunca altera os outros.",
    approvalsTerm: "Aprovações humanas",
    approvalsDesc:
      "Guardar Memory de longo prazo e as transferências importantes requerem a sua aprovação explícita.",
    noHiringTerm: "Nenhuma decisão de contratação",
    noHiringDesc:
      "O Ask4Mo não toma nem recomenda decisões de contratação e não classifica candidatos para recrutadores.",
    noVoiceTraitTerm: "Nenhuma inferência de traços a partir da voz",
    noVoiceTraitDesc:
      "A sua voz nunca é usada para inferir emoção, personalidade, confiança, sotaque ou adequação para contratação. Não existe pontuação de voz de qualquer tipo.",
    noAudioTerm: "Sem armazenamento de áudio",
    noAudioDesc:
      "O Ask4Mo não grava nem armazena o áudio do seu microfone. A voz em tempo real é transmitida a um fornecedor para suportar a conversa, sob a política do próprio fornecedor.",
    boundedAgentsTerm: "Agentes de IA limitados",
    boundedAgentsDesc:
      "O Mo usa um pequeno conjunto autorizado de ferramentas com revalidação do lado do servidor. Não há automodificação autónoma em produção.",
    exportDeleteTerm: "Exportar e eliminar",
    exportDeleteDesc:
      "Pode exportar os seus dados e eliminar de forma permanente a sua conta e os dados controlados pela aplicação a qualquer momento.",
    providerBoundariesTerm: "Limites dos fornecedores",
    providerBoundariesDesc:
      "As chaves de fornecedor de longa duração permanecem no servidor e nunca são enviadas para o seu navegador. As funcionalidades dispendiosas têm limites de uso do lado do servidor e um interruptor de pausa para o operador.",
  },
};

const nl: LegalFragment = {
  privacy: {
    pageTitle: "Privacy",
    intro:
      "Deze pagina beschrijft hoe Ask4Mo met uw gegevens omgaat, op basis van de werkelijke technische gegevensinventaris van het product. Het is een engineering-concept en vereist een juridische beoordeling; het is geen certificering van naleving van enige regelgeving.",
    storeHeading: "Wat we opslaan",
    storeAccountTerm: "Accountgegevens",
    storeAccountDesc:
      "e-mail, weergavenaam, verificatiestatus, aanmeldmethode, abonnementsniveau en platformrol.",
    storePrepTerm: "Voorbereidingsgegevens",
    storePrepDesc: "uw doelen, uw gesprekken met Mo en de gegenereerde voorbereidingscontext.",
    storeDocsTerm: "Privédocumenten",
    storeDocsDesc:
      "bestanden die u uploadt (bijvoorbeeld een cv), privé opgeslagen onder een willekeurige sleutel, nooit onder een openbare URL. Door OCR geëxtraheerde tekst en gedetecteerde gegevens.",
    storePracticeTerm: "Interview Practice",
    storePracticeDesc: "uw antwoorden, evaluaties en rapporten.",
    storeMemoryTerm: "Memory",
    storeMemoryDesc: "voorbereidingsfeiten op lange termijn die u uitdrukkelijk hebt goedgekeurd.",
    storeStoryTerm: "Story Bank",
    storeStoryDesc: "herbruikbare, op bewijs gebaseerde verhalen die u maakt.",
    storeWorkspacesTerm: "Workspaces en delen",
    storeWorkspacesDesc:
      "de workspaces die u bezit of waaraan u deelneemt, en de specifieke items die u uitdrukkelijk deelt.",
    storeFeedbackTerm: "Feedback",
    storeFeedbackDesc: "beoordelingen en opmerkingen die u over antwoorden indient.",
    storeMetadataTerm: "Operationele metadata",
    storeMetadataDesc:
      "aanvraag-identificatoren, tijdstempels, grove gebeurteniscategorieën en auditregistraties van bevoorrechte of beveiligingsrelevante acties.",
    voiceHeading: "Stem, spraak en realtime",
    voiceTurnBased:
      "Spraak om beurten gebruikt de spraakengines van uw browser of besturingssysteem. Ask4Mo neemt uw microfoonaudio niet op en slaat deze niet op.",
    voiceRealtime:
      "Realtime spraak (waar ingeschakeld) stuurt audio naar een realtime provider om het live gesprek mogelijk te maken; die verwerking volgt het eigen beleid van de provider. Ask4Mo slaat nog steeds geen audio op.",
    voiceNoInference:
      "Ask4Mo gebruikt uw stem nooit om emotie, persoonlijkheid, zelfvertrouwen, accent of geschiktheid voor aanname af te leiden. Er is geen stemscore.",
    externalHeading: "Externe verwerking",
    externalAi:
      "AI-functies sturen de benodigde tekst (geen geheimen) naar een modelprovider om antwoorden te genereren.",
    externalResearch:
      "Onderzoek naar de huidige markt (optioneel) kan externe arbeidsmarktbronnen bevragen.",
    externalEmail:
      "E-mailbezorging gebruikt een provider voor transactionele e-mail voor verificatie en herstel.",
    externalKeys:
      "Langlevende providersleutels blijven aan de serverzijde en worden nooit naar uw browser gestuurd.",
    retentionHeading: "Bewaring, export en verwijdering",
    retentionExport:
      "U kunt uw gegevens exporteren en uw account en de door de applicatie beheerde gegevens permanent verwijderen (documenten, privébestanden, Practice-geschiedenis, Memory, Story Bank, sessies en agent-checkpoints).",
    retentionAudit:
      "Beveiligings- en auditregistraties worden bewaard en geanonimiseerd (de koppeling met uw account wordt verwijderd) in plaats van verwijderd, voor beveiligingsbeoordeling.",
    retentionBackups:
      "Historische infrastructuurback-ups volgen het bewaarschema van de hostingprovider en worden bij verwijdering niet onmiddellijk gewist; ze verlopen volgens dat schema.",
    retentionRights:
      "Privacy, beveiliging en uw gegevensrechten zijn altijd beschikbaar, in elk abonnement.",
    contactHeading: "Contact",
    contactBody:
      "Neem voor privacyverzoeken contact op met het ondersteuningsadres dat voor uw implementatie is geconfigureerd. Dit concept wordt vóór de openbare lancering vervangen door juridisch beoordeelde tekst.",
  },
  terms: {
    pageTitle: "Gebruiksvoorwaarden",
    intro:
      "Deze voorwaarden zijn een engineering-concept en vereisen een juridische beoordeling vóór de openbare lancering. Ze stellen verwachtingen vast voor het gebruik van Ask4Mo tijdens de staging- en productbeoordelingsfase.",
    whatHeading: "Wat Ask4Mo is",
    whatBody:
      "Ask4Mo biedt AI-ondersteunde begeleiding bij de voorbereiding op sollicitatiegesprekken. Het is een hulpmiddel bij de voorbereiding, geen professioneel, juridisch, financieel of arbeidsrechtelijk advies, en geen vervanging van uw eigen oordeel.",
    aiHeading: "Beperkingen van AI",
    aiWrong:
      "AI kan onjuist of onvolledig zijn. Controleer alles wat belangrijk is aan de hand van de genoemde bronnen.",
    aiSources:
      "Bronnen kunnen onvolledig zijn; sommige datasets worden geleverd met een uitdrukkelijke status engineering-concept of niet gevalideerd.",
    aiScores:
      "Practice-scores zijn begeleiding bij de voorbereiding, geen objectieve maat voor bekwaamheid en geen voorspelling van de uitkomst van het gesprek.",
    aiNoHiring:
      "Ask4Mo neemt geen aannamebeslissingen, rangschikt geen kandidaten voor recruiters en beoordeelt u niet op basis van uw stem.",
    respHeading: "Uw verantwoordelijkheden",
    respAccurate: "Verstrek juiste informatie en houd uw inloggegevens veilig.",
    respUpload: "Upload alleen inhoud die u het recht hebt te gebruiken.",
    respLawful:
      "Gebruik de dienst op een wettige manier en probeer deze niet te misbruiken of te overbelasten.",
    accountsHeading: "Accounts, abonnementen en beschikbaarheid",
    accountsPlans:
      "Basic is gratis. Premium wordt als voorbeeld gepresenteerd; dit product verwerkt geen online betaling.",
    accountsProviders:
      "Sommige functies zijn afhankelijk van externe providers en kunnen onbeschikbaar, in frequentie beperkt of door de operator gepauzeerd zijn.",
    accountsAsIs:
      "De dienst wordt tijdens deze fase vóór de lancering as is geleverd, zonder garanties; de aansprakelijkheid is beperkt tot de maximale mate die het toepasselijke recht toestaat (onder voorbehoud van juridische beoordeling).",
    changesHeading: "Wijzigingen",
    changesBody:
      "Deze voorwaarden worden vóór elke openbare lancering herzien en juridisch beoordeeld.",
  },
  aiTransparency: {
    pageTitle: "AI-transparantie en verantwoord gebruik",
    intro:
      "We willen in duidelijke, eenvoudige taal uitleggen hoe AI in Ask4Mo wordt gebruikt. Deze pagina is een engineering-concept; het onderliggende gedrag wordt eerlijk beschreven.",
    whatMoHeading: "Wat Mo is",
    whatMoBody:
      "Mo is een AI-coachingassistent die u helpt bij de voorbereiding. Mo gebruikt een begrensde set hulpmiddelen en volgt een beheerde werkstroom; het handelt niet autonoom buiten het samen voorbereiden met u.",
    whenHeading: "Wanneer AI wordt gebruikt versus deterministische logica",
    whenAi:
      "AI (een model) wordt gebruikt voor conversationele coaching, onderbouwde synthese, het genereren van vragen en het evalueren van antwoorden en rapporten.",
    whenDeterministic:
      "Deterministische logica (geen model) wordt gebruikt voor wat exact en injectiebestendig moet zijn, bijvoorbeeld het selecteren en rangschikken van uw reeds goedgekeurde bewijs.",
    whenPolicy:
      "De keuze van het model per bewerking wordt bepaald door een centraal serverbeleid; uw browser kan nooit een ruw model kiezen.",
    specialistsHeading: "Specialisten, bewijs en bronnen",
    specialistsBounded:
      "Mo kan begrensde specialisten (rol en opportunity, bewijs, coaching) raadplegen via toegestane hulpmiddelen met hervalidatie aan de serverzijde.",
    specialistsGrounded:
      "Onderbouwde antwoorden noemen hun bronnen. Wanneer bewijs ontbreekt, onthoudt Mo zich in plaats van feiten te verzinnen.",
    approvalsHeading: "Menselijke goedkeuringen en controle",
    approvalsMemory:
      "Het opslaan van langetermijn-Memory en belangrijke overdrachten vereisen uw uitdrukkelijke goedkeuring.",
    approvalsFeedback:
      "Uw feedback helpt ons te verbeteren; deze wijzigt nooit automatisch het draaiende product.",
    limitsHeading: "Beperkingen",
    limitsModels:
      "Modellen kunnen het mis hebben; Practice-scores zijn begeleiding, geen oordeel.",
    limitsRealtime:
      "Realtime spraak is alleen beschikbaar waar deze is geconfigureerd; anders worden spraak om beurten en typen gebruikt.",
    neverHeading: "Wat Ask4Mo nooit doet",
    neverInference:
      "Geen afleiding van emotie, stemming, stress, zelfvertrouwen, accent, persoonlijkheid, intelligentie, eerlijkheid of geschiktheid voor aanname, noch uit uw stem noch anderszins.",
    neverHiring:
      "Geen aannamebeslissingen en geen kandidaatrangschikking gericht op recruiters.",
    neverPrompts:
      "Geen blootstelling van systeemprompts, ontwikkelaarsprompts, interne redenering of geheimen.",
  },
  about: {
    pageTitle: "Over Ask4Mo",
    lead:
      "Ask4Mo, de Intelligent Interview Coach, helpt kandidaten zich voor te bereiden op de gesprekken die ertoe doen. Het leidende idee is eenvoudig: Ask More. Be More. Betere vragen, onderbouwde antwoorden en eerlijk oefenen leiden tot betere resultaten.",
    trust:
      "Ask4Mo is gebouwd om vóór alles betrouwbaar te zijn. De voorbereiding is gebaseerd op bronnen die u kunt controleren, uw gegevens zijn standaard privé, AI-beslissingen die ertoe doen vereisen uw goedkeuring, en het product is eerlijk over wat het wel en niet kan. Het neemt geen aannamebeslissingen, rangschikt geen kandidaten voor recruiters en beoordeelt u niet op basis van uw stem.",
    capstone:
      "Dit is een Capstone-product. Sommige mogelijkheden (bijvoorbeeld live realtime spraak en bepaalde kennisdatasets) worden geleverd met een eerlijke, duidelijk vermelde validatiestatus in plaats van te veel te beloven.",
    seeAlso: "Zie ook",
    imageAlt:
      "Twee mensen in een doordacht coachinggesprek in een rustige bibliotheek.",
    contact:
      "Vragen of privacyverzoeken? Neem contact op met de ondersteuning op het adres dat voor uw implementatie is geconfigureerd (zie het Help Center zodra u bent aangemeld).",
  },
  help: {
    heading: "Help",
    eyebrow: "Hoe Ask4Mo werkt",
    description:
      "Een doorzoekbare gids voor elk onderdeel van Ask4Mo, de ideeën erachter en een herhaalbare rondleiding.",
    journeyImageAlt:
      "Een geïllustreerde reis, van het begrijpen van een rol tot reflectie, via gesprek en oefening.",
    tourTitle: "Nieuw hier?",
    tourBody: "Doe een rondleiding van twee minuten door het hele traject.",
    searchLabel: "Zoeken in help",
    searchExamples: "Zoeken in help, bijvoorbeeld voortgang, bronnen, memory, rapport",
    noMatch: "Geen help-onderwerpen komen overeen met “{query}”. Probeer een ander woord.",
  },
  marketing: {
    heroImageAlt:
      "Een professional bereidt interviewnotities voor aan de eettafel in zacht ochtendlicht.",
    problemImageAlt:
      "Handen ordenen vacatureonderzoek, notities en interviewmateriaal in één opportunity-map.",
    productImageAlt:
      "Een met de hand getekende opportunity-map die bedrijfsonderzoek, bewijs, gesprek, oefening en feedback verbindt.",
    navAria: "Marketing",
    navAriaMobile: "Marketing (mobiel)",
  },
  trust: {
    imageAlt:
      "Een persoon plaatst privébewijs in een gecontroleerde documentmap, naast bronmateriaal.",
    moreDetail: "Meer details",
    isolationTerm: "Accountisolatie",
    isolationDesc:
      "Uw gegevens zijn beperkt tot uw account. Platformbeheerders gebruiken een begrensde operationele console met uitsluitend metadata; er is geen weergeven als gebruiker en geen zoeken in privégegevens.",
    privateTerm: "Standaard privé",
    privateDesc:
      "Uw cv, antwoorden, rapporten, Memory en Story Bank zijn privé. Er wordt niets met iemand gedeeld tenzij u een uitdrukkelijke deelactie uitvoert.",
    oppPrivateTerm: "Uw Opportunity is privé",
    oppPrivateDesc:
      "Een Opportunity is uw eigen voorbereidingsruimte voor één baan. Deze is privé voor u en gescheiden van een samenwerkingsworkspace. Opportunities worden nooit automatisch gedeeld.",
    workspaceShareTerm: "Uitdrukkelijk delen in de workspace",
    workspaceShareDesc:
      "Delen in een workspace is alleen-lezen en wordt altijd door u gestart. Het verwijderen van een gedeeld item of het verlaten ervan trekt de toegang in.",
    sourcesTerm: "Bronnen die u kunt controleren",
    sourcesDesc:
      "Onderbouwde antwoorden noemen de bronnen erachter. Wanneer bewijs ontbreekt, onthoudt Mo zich in plaats van feiten te verzinnen.",
    factsSeparateTerm: "Bedrijfsfeiten blijven gescheiden van opinie",
    factsSeparateDesc:
      "Bedrijfsonderzoek houdt feiten, context uit werknemersbeoordelingen en AI-suggesties duidelijk gescheiden, op basis van bronnen die u kunt controleren. Platforms voor werknemersbeoordelingen zoals Glassdoor en Kununu zijn niet geïntegreerd; Ask4Mo verwijst ernaar in plaats van beoordelingen te kopiëren of te verzinnen.",
    suggestionsTerm: "AI-suggesties zijn geen feiten",
    suggestionsDesc:
      "Door het model gegenereerde suggesties en interviewfeedback zijn coachingbegeleiding. Ze zijn duidelijk gescheiden van bewijs en worden nooit als geverifieerde feiten gepresenteerd.",
    evidenceGovernedTerm: "Uw bewijs is beheerd",
    evidenceGovernedDesc:
      "In de voorbereiding wordt alleen loopbaanbewijs gebruikt dat u hebt goedgekeurd. Afgewezen of niet-beoordeeld bewijs wordt uitgesloten, en het verwijderen van een bron haalt deze uit gebruik.",
    layeredContextTerm: "Gelaagde context, niet één geheugen",
    layeredContextDesc:
      "Uw accountvoorkeuren, de context van een Opportunity, uw keuzes per sessie en uw documenten zijn afzonderlijk. Ask4Mo voegt ze niet samen tot één ongecontroleerde geheugenopslag, en langetermijn-Memory wordt alleen opgeslagen wanneer u het goedkeurt.",
    languageMarketTerm: "Uw taal, uw markt",
    languageMarketDesc:
      "Uw interfacetaal staat los van uw interviewtaal, uw dicteertaal en uw beoogde arbeidsmarkt. Het wijzigen van de een verandert nooit de andere.",
    approvalsTerm: "Menselijke goedkeuringen",
    approvalsDesc:
      "Het opslaan van langetermijn-Memory en belangrijke overdrachten vereisen uw uitdrukkelijke goedkeuring.",
    noHiringTerm: "Geen aannamebeslissingen",
    noHiringDesc:
      "Ask4Mo neemt of beveelt geen aannamebeslissingen aan en rangschikt geen kandidaten voor recruiters.",
    noVoiceTraitTerm: "Geen afleiding van kenmerken uit de stem",
    noVoiceTraitDesc:
      "Uw stem wordt nooit gebruikt om emotie, persoonlijkheid, zelfvertrouwen, accent of geschiktheid voor aanname af te leiden. Er bestaat geen enkele stemscore.",
    noAudioTerm: "Geen audio-opslag",
    noAudioDesc:
      "Ask4Mo neemt uw microfoonaudio niet op en slaat deze niet op. Realtime spraak wordt naar een provider gestuurd om het gesprek mogelijk te maken, onder het eigen beleid van die provider.",
    boundedAgentsTerm: "Begrensde AI-agenten",
    boundedAgentsDesc:
      "Mo gebruikt een kleine, toegestane set hulpmiddelen met hervalidatie aan de serverzijde. Er is geen autonome zelfwijziging in productie.",
    exportDeleteTerm: "Exporteren en verwijderen",
    exportDeleteDesc:
      "U kunt uw gegevens exporteren en uw account en de door de applicatie beheerde gegevens op elk moment permanent verwijderen.",
    providerBoundariesTerm: "Providergrenzen",
    providerBoundariesDesc:
      "Langlevende providersleutels blijven aan de serverzijde en worden nooit naar uw browser gestuurd. Kostbare functies hebben gebruikslimieten aan de serverzijde en een pauzeschakelaar voor de operator.",
  },
};

const legal: Record<string, LegalFragment> = { en, de, fr, es, it, pt, nl };

export default legal;
