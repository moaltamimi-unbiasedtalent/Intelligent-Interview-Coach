// 04D candidate journey reliability copy (English source of truth): accurate provider-failure messages, the AI provider mode indicator, the owner-scoped run list and the ONE free-beta
// pricing statement. "Not configured" (nothing will work here until AI is configured) and "unavailable" (the AI service failed this time) are different facts and never share a message.
// The mode is configuration, not health: live never means the provider is reachable, funded or qualified. No provider name, URL, key hint or price appears here.

const en = {
  states: {
    aiNotConfigured: "AI features are not configured on this Ask4Mo environment, so nothing was started. Your saved work and history remain available.",
    aiProviderUnavailable: "The AI service could not complete this request right now. Nothing was lost and nothing was started twice. Please try again in a moment.",
  },
  providerMode: {
    label: "AI mode",
    live: "AI: live",
    offline: "AI: offline test mode",
    notConfigured: "AI: not configured",
    unknown: "AI: status unknown",
    liveHint: "A live AI provider is configured for this environment. This is configuration, not a health check.",
    offlineHint: "No live AI is used here. Answers come from test fixtures and are not real coaching.",
    notConfiguredHint: "AI features are not configured on this environment, so Mo and Practice cannot run.",
    unknownHint: "Ask4Mo could not confirm the AI mode of this environment.",
  },
  recentRuns: {
    title: "Your recent preparation with Mo",
    hint: "Only your own sessions are listed. Open one to continue where you left off.",
    empty: "You have not prepared with Mo yet.",
    open: "Open",
    started: "Started {date}",
    stateStarted: "In progress",
    stateReady: "Ready",
    stateFailed: "Did not complete",
    loadError: "Your recent sessions could not be loaded.",
  },
  betaPricing: {
    statement: "Ask4Mo is a free, invitation-only private beta. Nothing can be purchased and no price applies.",
    freeInBeta: "Free in the beta",
    planNote: "Plans describe what a beta account can use. Nothing here is on sale.",
  },
};

export default en;
