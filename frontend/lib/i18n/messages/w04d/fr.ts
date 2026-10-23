import type en from "./en";

const fr: typeof en = {
  states: {
    aiNotConfigured: "Les fonctions d’IA ne sont pas configurées dans cet environnement Ask4Mo ; rien n’a donc été démarré. Votre travail enregistré et votre historique restent disponibles.",
    aiProviderUnavailable: "Le service d’IA n’a pas pu terminer cette demande pour le moment. Rien n’a été perdu et rien n’a été lancé deux fois. Veuillez réessayer dans un instant.",
  },
  providerMode: {
    label: "Mode IA",
    live: "IA : en direct",
    offline: "IA : mode test hors ligne",
    notConfigured: "IA : non configurée",
    unknown: "IA : état inconnu",
    liveHint: "Un fournisseur d’IA en direct est configuré pour cet environnement. Il s’agit d’une configuration, pas d’un contrôle de fonctionnement.",
    offlineHint: "Aucune IA en direct n’est utilisée ici. Les réponses proviennent de données de test et ne constituent pas un vrai coaching.",
    notConfiguredHint: "Les fonctions d’IA ne sont pas configurées dans cet environnement ; Mo et l’entraînement ne peuvent donc pas fonctionner.",
    unknownHint: "Ask4Mo n’a pas pu confirmer le mode IA de cet environnement.",
  },
  recentRuns: {
    title: "Votre préparation récente avec Mo",
    hint: "Seules vos propres sessions sont listées. Ouvrez-en une pour reprendre là où vous vous êtes arrêté.",
    empty: "Vous ne vous êtes pas encore préparé avec Mo.",
    open: "Ouvrir",
    started: "Commencée le {date}",
    stateStarted: "En cours",
    stateReady: "Prête",
    stateFailed: "Non terminée",
    loadError: "Vos sessions récentes n’ont pas pu être chargées.",
  },
  betaPricing: {
    statement: "Ask4Mo est une bêta privée gratuite, sur invitation uniquement. Rien ne peut être acheté et aucun prix ne s’applique.",
    freeInBeta: "Gratuit pendant la bêta",
    planNote: "Les offres décrivent ce qu’un compte bêta peut utiliser. Rien ici n’est en vente.",
  },
  onboarding: {
    stepSaveError: "Nous n’avons pas pu enregistrer cette étape. Veuillez réessayer.",
  },
};

export default fr;
