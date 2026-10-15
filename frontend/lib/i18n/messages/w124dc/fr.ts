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
    confirmedTitle: "Abonnement Premium confirmé",
    confirmedBody: "Notre partenaire de paiement a confirmé ton abonnement et ton offre a été mise à jour.",
    confirmedNoAccessTitle: "Abonnement confirmé par notre partenaire de paiement",
    confirmedNoAccessBody: "Ton offre n'a pas encore changé. L'accès est mis à jour uniquement lorsque les règles des offres payantes sont en vigueur.",
    pastDueTitle: "Paiement à vérifier",
    pastDueBody: "Notre partenaire de paiement n'a pas pu encaisser ton dernier paiement. Tu gères un abonnement payant auprès de ce partenaire.",
    cancelScheduledTitle: "Résiliation programmée",
    cancelScheduledBody: "Ton abonnement prendra fin à la fin de la période en cours. Rien n'est encore terminé.",
    endedTitle: "Abonnement terminé",
    endedBody: "Ton abonnement payant est terminé. Les fonctionnalités gratuites restent disponibles.",
  },
};

export default fr;
