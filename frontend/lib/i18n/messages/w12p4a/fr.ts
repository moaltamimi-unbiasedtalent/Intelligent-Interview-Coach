import type en from "./en";

const fr: typeof en = {
  states: {
    usageQuotaExhausted: "Vous avez utilisé le quota d’IA inclus pour cette période. Votre travail enregistré et votre historique restent disponibles. Il redevient disponible à la réinitialisation de la période.",
  },
  quotaUx: {
    title: "Quota d’utilisation",
    lead: "Le quota affiché ici est calculé par Ask4Mo pour votre compte et la période en cours.",
    f_practice_session: "Séances d’entraînement à l’entretien",
    f_career_ai: "Demandes de coaching par IA",
    st_available: "Disponible",
    st_exhausted: "Épuisé pour l’instant",
    st_not_configured: "Pas encore configuré",
    st_unavailable: "Temporairement indisponible",
    used: "Utilisé",
    remaining: "Restant",
    resets: "Réinitialisation",
    per_hour: "par heure",
    per_day: "par jour",
    per_month: "par mois",
    notConfigured: "Aucun quota n’a encore été configuré pour cette fonctionnalité.",
    exhaustedNote: "Ce quota est réinitialisé à l’heure indiquée. Votre travail enregistré et votre historique restent disponibles.",
  },
};

export default fr;
