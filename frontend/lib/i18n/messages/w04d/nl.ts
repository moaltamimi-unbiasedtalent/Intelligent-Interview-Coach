import type en from "./en";

const nl: typeof en = {
  states: {
    aiNotConfigured: "AI-functies zijn in deze Ask4Mo-omgeving niet ingesteld, dus er is niets gestart. Je opgeslagen werk en je geschiedenis blijven beschikbaar.",
    aiProviderUnavailable: "De AI-dienst kon dit verzoek nu niet afronden. Er is niets verloren gegaan en niets dubbel gestart. Probeer het over een moment opnieuw.",
  },
  providerMode: {
    label: "AI-modus",
    live: "AI: live",
    offline: "AI: offline testmodus",
    notConfigured: "AI: niet ingesteld",
    unknown: "AI: status onbekend",
    liveHint: "Voor deze omgeving is een live AI-aanbieder ingesteld. Dit is een configuratie, geen gezondheidscontrole.",
    offlineHint: "Hier wordt geen live AI gebruikt. Antwoorden komen uit testgegevens en zijn geen echte coaching.",
    notConfiguredHint: "AI-functies zijn in deze omgeving niet ingesteld, dus Mo en Oefenen kunnen niet werken.",
    unknownHint: "Ask4Mo kon de AI-modus van deze omgeving niet bevestigen.",
  },
  recentRuns: {
    title: "Je recente voorbereiding met Mo",
    hint: "Alleen je eigen sessies worden getoond. Open er een om verder te gaan waar je gebleven was.",
    empty: "Je hebt je nog niet met Mo voorbereid.",
    open: "Openen",
    started: "Gestart op {date}",
    stateStarted: "Bezig",
    stateReady: "Klaar",
    stateFailed: "Niet voltooid",
    loadError: "Je recente sessies konden niet worden geladen.",
  },
  betaPricing: {
    statement: "Ask4Mo is een gratis privébèta, alleen op uitnodiging. Er kan niets worden gekocht en er geldt geen prijs.",
    freeInBeta: "Gratis in de bèta",
    planNote: "Abonnementen beschrijven wat een bètaaccount kan gebruiken. Niets hier is te koop.",
  },
};

export default nl;
