import type en from "./en";

const fr: typeof en = {
  dataPrivacy: {
    // Page
    eyebrow: "Compte",
    title: "Vos données et votre confidentialité",
    description:
      "Voyez ce qu’Ask4Mo conserve pour vous, téléchargez une copie, supprimez des éléments individuels, vérifiez ce que vous partagez et supprimez votre compte. Tout ce qui figure ici concerne uniquement vos propres données.",
    backToAccount: "Retour au compte",
    working: "En cours…",
    removed: "Supprimé.",
    actionFailed: "Cela n’a pas fonctionné et rien n’a été modifié. Veuillez réessayer.",

    // 1. Overview
    overviewTitle: "Ce qu’Ask4Mo conserve pour vous",
    overviewIntro: "Ce qui est actuellement enregistré sous votre compte.",
    cardOpportunities: "Opportunités",
    cardOpportunitiesDesc: "Les contextes de poste que vous avez créés, y compris ceux archivés.",
    cardDocuments: "Documents",
    cardDocumentsDesc: "Les CV et descriptions de poste que vous avez téléversés, avec ce qui en a été extrait.",
    cardMemories: "Mémoire enregistrée",
    cardMemoriesDesc: "Des éléments de préparation que vous avez approuvés pour que Mo les réutilise.",
    cardInterviews: "Entretiens d’entraînement",
    cardInterviewsDesc: "Les entretiens terminés avec vos réponses, retours et rapports.",
    cardShares: "Éléments que vous partagez",
    cardSharesDesc: "Les rapports ou histoires pour lesquels vous avez donné un accès en lecture à un espace de travail.",
    cardWorkspaces: "Espaces de travail",
    cardWorkspacesDesc: "Les espaces de travail dont vous êtes membre.",
    cardAccount: "Compte et préférences",
    cardAccountDesc:
      "Votre e-mail, votre méthode de connexion, votre formule et vos réglages de langue. Ils ne sont supprimés que si vous supprimez votre compte.",

    // 2. Export
    exportTitle: "Télécharger vos données",
    exportIntro:
      "Obtenez une copie de vos données sous forme de fichier JSON. Elle est créée au moment du clic et va directement sur votre appareil. Ask4Mo ne conserve pas le fichier, il n’y a donc aucun lien qui expire.",
    exportButton: "Télécharger mes données (JSON)",
    exportIncluded: "Inclus",
    incAccount: "Détails du compte et préférences",
    incOpportunities: "Opportunités",
    incDocuments: "Détails des documents et preuves qui en ont été extraites (pas les fichiers d’origine)",
    incStories: "Histoires",
    incMemories: "Mémoire enregistrée",
    incInterviews: "Entretiens d’entraînement : questions, vos réponses, retours et rapports",
    incFeedback: "Retours que vous avez envoyés",
    incSharing: "Appartenances aux espaces de travail et ce que vous partagez",
    exportExcluded: "Non inclus",
    excFiles: "Vos fichiers d’origine téléversés. Téléchargez-les depuis Documents.",
    excAudit: "Journaux de sécurité et d’audit conservés par la plateforme",
    excOthers: "Les données d’autres personnes, y compris tout ce qui est partagé avec vous",
    excInternal: "Prompts internes, raisonnement du modèle et secrets",
    excLegal: "L’historique des versions juridiques que vous avez acceptées (il n’est pas encore enregistré)",

    // 3. Manage individual data
    manageTitle: "Supprimer des données individuelles",
    manageIntro: "Supprimez un élément sans fermer votre compte. La suppression est irréversible.",
    manageEmpty: "Rien n’est enregistré ici.",
    manageLoadFailed: "Cette liste n’a pas pu être chargée.",
    deleteAction: "Supprimer",
    archiveAction: "Archiver",
    archivedBadge: "Archivée",
    itemOpportunity: "Opportunité",
    itemDocument: "Document",
    itemMemory: "Mémoire",
    itemInterview: "Entretien",
    itemUntitled: "Sans titre",
    oppNote:
      "Archiver masque une opportunité et la conserve. Supprimer la retire définitivement. Vos entretiens d’entraînement et rapports restent, mais ne lui sont plus liés. Un document de description de poste qui lui est lié est conservé : supprimez-le dans Documents.",
    docNote:
      "Supprimer un document retire le fichier téléversé, son texte extrait et les preuves qui en ont été tirées. Les histoires construites à partir de lui sont conservées, mais ne sont plus indiquées comme basées sur votre document.",
    memNote:
      "Supprimer un élément de mémoire empêche Mo de le réutiliser dans vos préparations futures. Vos entretiens et rapports passés ne sont pas affectés.",
    intNote:
      "Supprimer un entretien retire ses questions, vos réponses, le retour et le rapport, et met fin à tout partage de ce rapport dans un espace de travail.",
    chatNote:
      "Les conversations de préparation avec Mo sont des données de travail pour votre préparation en cours. Supprimer une conversation isolée depuis cette page n’est pas encore possible.",
    feedbackNote: "Les évaluations que vous avez données peuvent être réinitialisées là où vous les avez données. Elles sont supprimées lorsque vous supprimez votre compte.",
    confirmDeleteOpportunityTitle: "Supprimer cette opportunité ?",
    confirmDeleteOpportunityBody:
      "“{name}” sera supprimée définitivement. Les entretiens et rapports liés sont conservés, sans le lien. Pour la garder mais la masquer, archivez-la plutôt.",
    confirmArchiveOpportunityTitle: "Archiver cette opportunité ?",
    confirmArchiveOpportunityBody: "“{name}” sera masquée de vos listes mais conservée. Vous pourrez la retrouver plus tard.",
    confirmDeleteDocumentTitle: "Supprimer ce document ?",
    confirmDeleteDocumentBody:
      "“{name}” sera supprimé définitivement, y compris le fichier, le texte extrait et les preuves qui en ont été tirées.",
    confirmDeleteMemoryTitle: "Supprimer cet élément de mémoire ?",
    confirmDeleteMemoryBody:
      "Mo ne réutilisera plus “{name}”. Vos entretiens et rapports passés ne sont pas affectés.",
    confirmDeleteInterviewTitle: "Supprimer cet entretien ?",
    confirmDeleteInterviewBody:
      "“{name}” sera supprimé définitivement, avec vos réponses, le retour et le rapport. Tout partage dans un espace de travail prend fin.",
    confirmArchive: "Archiver",
    confirmDelete: "Supprimer définitivement",

    // 4. Sharing
    sharingTitle: "Partage et accès",
    sharingIntro:
      "Rien n’est partagé sans que vous le partagiez. Révoquer empêche les membres de voir un élément à partir de maintenant. Cela ne reprend rien de ce qu’ils ont déjà vu.",
    sharingEmpty: "Vous ne partagez rien.",
    sharingLoadFailed: "Vos partages n’ont pas pu être chargés.",
    sharedReport: "Rapport d’entretien",
    sharedStory: "Histoire",
    sharedItem: "Élément partagé",
    sharedWith: "Partagé avec {workspace}",
    workspaceFallback: "espace de travail {id}",
    revokeAction: "Révoquer l’accès",
    confirmRevokeTitle: "Révoquer l’accès ?",
    confirmRevokeBody:
      "Les membres de {workspace} ne pourront plus voir cet élément. Ce qu’ils ont déjà vu ne peut pas être repris.",
    confirmRevoke: "Révoquer l’accès",
    manageWorkspaces: "Gérer les espaces de travail",

    // 5. Retention
    retentionTitle: "Conservation",
    retentionIntro: "Combien de temps vos données sont conservées, en termes simples. Nous ne fixons pas de durées de stockage précises pour votre contenu.",
    retentionActive: "Tant que votre compte est ouvert, les éléments ci-dessus sont conservés jusqu’à ce que vous les supprimiez.",
    retentionDelete:
      "Supprimer un élément ou votre compte le retire immédiatement d’Ask4Mo. Les sauvegardes ne sont pas effacées instantanément.",
    retentionSecurity:
      "Les journaux de sécurité, comme les événements de connexion et de compte, sont conservés sans votre identité après la suppression de votre compte.",
    retentionProviders:
      "Lorsque Mo ou un entretien d’entraînement utilise un fournisseur d’IA, le texte que vous envoyez est traité par ce fournisseur selon ses propres conditions.",

    // 6. Legal
    legalTitle: "Consentement et documents juridiques",
    legalIntro: "Les documents qui encadrent votre utilisation d’Ask4Mo.",
    legalTerms: "Conditions d’utilisation",
    legalPrivacy: "Confidentialité",
    legalAi: "Transparence de l’IA",
    legalNotRecorded:
      "Ask4Mo n’enregistre pas encore quelle version de ces documents vous avez acceptée, il n’y a donc pas d’historique d’acceptation à afficher ici.",
    legalReview:
      "Les traductions des documents juridiques sont des brouillons d’ingénierie et n’ont pas toutes été relues par un juriste.",

    // 7. Account deletion
    accountZoneTitle: "Supprimer votre compte",
    accountZoneBody:
      "La suppression de votre compte est définitive. Utilisez d’abord les options ci-dessus si vous souhaitez seulement supprimer une partie de vos données.",
    accountZoneButton: "Supprimer mon compte…",
    accountConfirmTitle: "Supprimer votre compte ?",
    accountConfirmIntro: "Cette action est irréversible. Elle supprime :",
    accDelOpportunities: "Vos opportunités",
    accDelDocuments: "Vos documents et fichiers téléversés",
    accDelMemories: "Votre mémoire enregistrée, vos histoires et vos retours",
    accDelInterviews: "Vos entretiens d’entraînement, réponses et rapports",
    accDelSharing: "Vos partages et appartenances aux espaces de travail (les espaces de travail dont vous êtes propriétaire passent à un autre membre ou sont supprimés)",
    accDelAccount: "Votre connexion, vos préférences et votre formule",
    accountConfirmKept:
      "Les journaux de sécurité sont conservés sans votre identité. Les sauvegardes ne sont pas effacées instantanément. Certaines données de travail des conversations de préparation peuvent subsister jusqu’à leur nettoyage.",
    accountConfirmExport: "Télécharger d’abord vos données",
    accountConfirmKeep: "Garder mon compte",
    accountConfirmDelete: "Supprimer mon compte définitivement",
    accountDeleteFailed: "Votre compte n’a pas été supprimé. Rien n’a été modifié. Veuillez réessayer.",
  },
};

export default fr;
