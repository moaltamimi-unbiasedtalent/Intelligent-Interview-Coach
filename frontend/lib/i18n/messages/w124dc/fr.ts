import type en from "./en";

const fr: typeof en = {
  checkout: {
    title: "Abonnement Premium",
    unavailable: "Le paiement n'est pas encore ouvert. Premium est un aperçu sans prix approuvé, donc rien ne peut être acheté aujourd'hui.",
    signInRequired: "Connecte-toi pour continuer. Le paiement démarre toujours depuis ton propre compte.",
    selectPlan: "Premium est sélectionné. Tu termineras sur une page sécurisée gérée par notre partenaire de paiement.",
    start: "Continuer vers le paiement sécurisé",
    preparing: "Préparation de ton paiement sécurisé…",
    redirecting: "Redirection vers le paiement sécurisé…",
    pendingTitle: "Nous attendons la confirmation",
    pendingBody: "Tu es revenu du paiement. Ton offre n'a pas encore changé. L'accès change seulement après la confirmation de l'abonnement par notre partenaire de paiement, ce qui peut prendre un peu de temps.",
    canceledTitle: "Paiement annulé",
    canceledBody: "Tu as annulé le paiement. Rien n'a été débité et ton offre n'a pas changé.",
    expired: "Ce paiement a expiré. Rien n'a été débité. Tu peux en démarrer un nouveau.",
    providerUnavailable: "Le prestataire de paiement n'a pas pu démarrer le paiement. Rien n'a été débité. Réessaie plus tard.",
    statusUnavailable: "Impossible de charger l'état de ton paiement pour le moment.",
    retry: "Réessayer",
    sellerNote: "Notre partenaire de paiement est le vendeur des abonnements payants et envoie les reçus et les e-mails de paiement.",
    manageNote: "Tu gères un abonnement payant auprès de ce partenaire. Ask4Mo ne conserve aucune donnée de carte.",
    noInvoices: "Aucune facture ni aucun reçu n'est affiché ici, car Ask4Mo n'en a émis aucun.",
    returnTitle: "État du paiement",
    backToAccount: "Retour à ton compte",
    stillChecking: "Vérification…",
  },
};

export default fr;
