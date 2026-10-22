import type en from "./en";

const it: typeof en = {
  states: {
    aiNotConfigured: "Le funzioni di IA non sono configurate in questo ambiente Ask4Mo, quindi non è stato avviato nulla. Il tuo lavoro salvato e la tua cronologia restano disponibili.",
    aiProviderUnavailable: "Il servizio di IA non ha potuto completare questa richiesta in questo momento. Non è andato perso nulla e nulla è stato avviato due volte. Riprova tra un attimo.",
  },
  providerMode: {
    label: "Modalità IA",
    live: "IA: dal vivo",
    offline: "IA: modalità di prova offline",
    notConfigured: "IA: non configurata",
    unknown: "IA: stato sconosciuto",
    liveHint: "Per questo ambiente è configurato un fornitore di IA dal vivo. È una configurazione, non un controllo di funzionamento.",
    offlineHint: "Qui non viene usata alcuna IA dal vivo. Le risposte provengono da dati di prova e non sono un vero coaching.",
    notConfiguredHint: "Le funzioni di IA non sono configurate in questo ambiente, quindi Mo e l’allenamento non possono funzionare.",
    unknownHint: "Ask4Mo non ha potuto confermare la modalità IA di questo ambiente.",
  },
  recentRuns: {
    title: "La tua preparazione recente con Mo",
    hint: "Sono elencate solo le tue sessioni. Aprine una per riprendere da dove avevi lasciato.",
    empty: "Non ti sei ancora preparato con Mo.",
    open: "Apri",
    started: "Iniziata il {date}",
    stateStarted: "In corso",
    stateReady: "Pronta",
    stateFailed: "Non completata",
    loadError: "Non è stato possibile caricare le tue sessioni recenti.",
  },
  betaPricing: {
    statement: "Ask4Mo è una beta privata gratuita, solo su invito. Non si può acquistare nulla e non si applica alcun prezzo.",
    freeInBeta: "Gratis durante la beta",
    planNote: "I piani descrivono ciò che può usare un account beta. Nulla qui è in vendita.",
  },
};

export default it;
