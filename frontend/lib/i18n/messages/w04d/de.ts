import type en from "./en";

const de: typeof en = {
  states: {
    aiNotConfigured: "KI-Funktionen sind in dieser Ask4Mo-Umgebung nicht eingerichtet, daher wurde nichts gestartet. Ihre gespeicherten Arbeiten und Ihr Verlauf bleiben verfügbar.",
    aiProviderUnavailable: "Der KI-Dienst konnte diese Anfrage gerade nicht abschließen. Es ging nichts verloren und nichts wurde doppelt gestartet. Bitte versuchen Sie es gleich noch einmal.",
  },
  providerMode: {
    label: "KI-Modus",
    live: "KI: live",
    offline: "KI: Offline-Testmodus",
    notConfigured: "KI: nicht eingerichtet",
    unknown: "KI: Status unbekannt",
    liveHint: "Für diese Umgebung ist ein Live-KI-Anbieter eingerichtet. Das ist eine Konfiguration, keine Gesundheitsprüfung.",
    offlineHint: "Hier wird keine Live-KI verwendet. Die Antworten stammen aus Testdaten und sind kein echtes Coaching.",
    notConfiguredHint: "KI-Funktionen sind in dieser Umgebung nicht eingerichtet, daher können Mo und Üben nicht laufen.",
    unknownHint: "Ask4Mo konnte den KI-Modus dieser Umgebung nicht bestätigen.",
  },
  recentRuns: {
    title: "Ihre letzte Vorbereitung mit Mo",
    hint: "Es werden nur Ihre eigenen Sitzungen angezeigt. Öffnen Sie eine, um dort weiterzumachen, wo Sie aufgehört haben.",
    empty: "Sie haben sich noch nicht mit Mo vorbereitet.",
    open: "Öffnen",
    started: "Gestartet {date}",
    stateStarted: "In Bearbeitung",
    stateReady: "Bereit",
    stateFailed: "Nicht abgeschlossen",
    loadError: "Ihre letzten Sitzungen konnten nicht geladen werden.",
  },
  betaPricing: {
    statement: "Ask4Mo ist eine kostenlose Beta nur auf Einladung. Es kann nichts gekauft werden, und es gilt kein Preis.",
    freeInBeta: "Kostenlos in der Beta",
    planNote: "Pläne beschreiben, was ein Beta-Konto nutzen kann. Nichts hier steht zum Verkauf.",
  },
};

export default de;
