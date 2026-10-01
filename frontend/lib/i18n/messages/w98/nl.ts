import type en from "./en";

const nl: typeof en = {
  dataPrivacy: {
    // Page
    eyebrow: "Account",
    title: "Uw gegevens en privacy",
    description:
      "Bekijk wat Ask4Mo voor u bewaart, download een kopie, verwijder afzonderlijke items, controleer wat u deelt en verwijder uw account. Alles hier geldt alleen voor uw eigen gegevens.",
    backToAccount: "Terug naar account",
    working: "Bezig…",
    removed: "Verwijderd.",
    actionFailed: "Dat is niet gelukt en er is niets gewijzigd. Probeer het opnieuw.",

    // 1. Overview
    overviewTitle: "Wat Ask4Mo voor u bewaart",
    overviewIntro: "Wat er nu onder uw account is opgeslagen.",
    cardOpportunities: "Kansen",
    cardOpportunitiesDesc: "Vacaturecontexten die u hebt gemaakt, inclusief gearchiveerde.",
    cardDocuments: "Documenten",
    cardDocumentsDesc: "Cv’s en functieomschrijvingen die u hebt geüpload, met wat daaruit is gehaald.",
    cardMemories: "Opgeslagen geheugen",
    cardMemoriesDesc: "Voorbereidingsfeiten die u hebt goedgekeurd zodat Mo ze opnieuw kan gebruiken.",
    cardInterviews: "Oefengesprekken",
    cardInterviewsDesc: "Voltooide gesprekken met uw antwoorden, feedback en rapporten.",
    cardShares: "Items die u deelt",
    cardSharesDesc: "Rapporten of verhalen waarvoor u een werkruimte leestoegang hebt gegeven.",
    cardWorkspaces: "Werkruimtes",
    cardWorkspacesDesc: "Werkruimtes waartoe u behoort.",
    cardAccount: "Account en voorkeuren",
    cardAccountDesc:
      "Uw e-mailadres, inlogmethode, abonnement en taalinstellingen. Deze worden alleen verwijderd als u uw account verwijdert.",

    // 2. Export
    exportTitle: "Uw gegevens downloaden",
    exportIntro:
      "Ontvang een kopie van uw gegevens als JSON-bestand. Het wordt gemaakt zodra u klikt en gaat rechtstreeks naar uw apparaat. Ask4Mo bewaart het bestand niet, dus er is geen link die verloopt.",
    exportButton: "Mijn gegevens downloaden (JSON)",
    exportIncluded: "Inbegrepen",
    incAccount: "Accountgegevens en voorkeuren",
    incOpportunities: "Kansen",
    incDocuments: "Documentgegevens en het bewijs dat eruit is gehaald (niet de originele bestanden)",
    incStories: "Verhalen",
    incMemories: "Opgeslagen geheugen",
    incInterviews: "Oefengesprekken: vragen, uw antwoorden, feedback en rapporten",
    incFeedback: "Feedback die u hebt ingediend",
    incSharing: "Lidmaatschappen van werkruimtes en wat u deelt",
    exportExcluded: "Niet inbegrepen",
    excFiles: "Uw originele geüploade bestanden. Download ze via Documenten.",
    excAudit: "Beveiligings- en auditgegevens die het platform bewaart",
    excOthers: "Gegevens van anderen, inclusief alles wat met u is gedeeld",
    excInternal: "Interne prompts, modelredenering en geheimen",
    excLegal: "Een geschiedenis van welke juridische versies u hebt geaccepteerd (dit wordt nog niet vastgelegd)",

    // 3. Manage individual data
    manageTitle: "Afzonderlijke gegevens verwijderen",
    manageIntro: "Verwijder één item zonder uw account te sluiten. Verwijderen kan niet ongedaan worden gemaakt.",
    manageEmpty: "Hier is niets opgeslagen.",
    manageLoadFailed: "Deze lijst kon niet worden geladen.",
    deleteAction: "Verwijderen",
    archiveAction: "Archiveren",
    archivedBadge: "Gearchiveerd",
    itemOpportunity: "Kans",
    itemDocument: "Document",
    itemMemory: "Geheugen",
    itemInterview: "Gesprek",
    itemUntitled: "Zonder titel",
    oppNote:
      "Archiveren verbergt een kans en bewaart die. Verwijderen verwijdert haar voorgoed. Uw oefengesprekken en rapporten blijven bestaan, maar zijn niet langer eraan gekoppeld. Een eraan gekoppeld functieomschrijvingsdocument blijft bewaard: verwijder het onder Documenten.",
    docNote:
      "Een document verwijderen verwijdert het geüploade bestand, de geëxtraheerde tekst en het daaruit gehaalde bewijs. Verhalen die ervan zijn gemaakt blijven bewaard, maar zijn niet langer gemarkeerd als gebaseerd op uw document.",
    memNote:
      "Een geheugenitem verwijderen zorgt ervoor dat Mo het niet meer gebruikt bij toekomstige voorbereiding. Uw eerdere gesprekken en rapporten blijven ongewijzigd.",
    intNote:
      "Een gesprek verwijderen verwijdert de vragen, uw antwoorden, de feedback en het rapport, en beëindigt elke deling van dat rapport met werkruimtes.",
    chatNote:
      "Voorbereidingschats met Mo zijn werkgegevens voor uw huidige voorbereiding. Een enkele chat vanaf deze pagina verwijderen is nog niet mogelijk.",
    feedbackNote: "Beoordelingen die u hebt gegeven kunt u terugzetten op de plek waar u ze gaf. Ze worden verwijderd als u uw account verwijdert.",
    confirmDeleteOpportunityTitle: "Deze kans verwijderen?",
    confirmDeleteOpportunityBody:
      "“{name}” wordt voorgoed verwijderd. Gekoppelde gesprekken en rapporten blijven bewaard, zonder de koppeling. Wilt u de kans bewaren maar verbergen, archiveer haar dan.",
    confirmArchiveOpportunityTitle: "Deze kans archiveren?",
    confirmArchiveOpportunityBody: "“{name}” wordt verborgen in uw lijsten, maar blijft bewaard. U kunt haar later terugvinden.",
    confirmDeleteDocumentTitle: "Dit document verwijderen?",
    confirmDeleteDocumentBody:
      "“{name}” wordt voorgoed verwijderd, inclusief het bestand, de geëxtraheerde tekst en het daaruit gehaalde bewijs.",
    confirmDeleteMemoryTitle: "Dit geheugenitem verwijderen?",
    confirmDeleteMemoryBody:
      "Mo gebruikt “{name}” niet meer. Uw eerdere gesprekken en rapporten blijven ongewijzigd.",
    confirmDeleteInterviewTitle: "Dit gesprek verwijderen?",
    confirmDeleteInterviewBody:
      "“{name}” wordt voorgoed verwijderd, met uw antwoorden, feedback en rapport. Elke deling met werkruimtes eindigt.",
    confirmArchive: "Archiveren",
    confirmDelete: "Voorgoed verwijderen",

    // 4. Sharing
    sharingTitle: "Delen en toegang",
    sharingIntro:
      "Er wordt niets gedeeld tenzij u het deelt. Intrekken zorgt ervoor dat leden een item vanaf nu niet meer kunnen bekijken. Wat ze al hebben gezien, wordt niet teruggehaald.",
    sharingEmpty: "U deelt niets.",
    sharingLoadFailed: "Uw gedeelde items konden niet worden geladen.",
    sharedReport: "Gesprekrapport",
    sharedStory: "Verhaal",
    sharedItem: "Gedeeld item",
    sharedWith: "Gedeeld met {workspace}",
    workspaceFallback: "werkruimte {id}",
    revokeAction: "Toegang intrekken",
    confirmRevokeTitle: "Toegang intrekken?",
    confirmRevokeBody:
      "Leden van {workspace} kunnen dit item niet meer bekijken. Wat ze al hebben gezien, kan niet worden teruggehaald.",
    confirmRevoke: "Toegang intrekken",
    manageWorkspaces: "Werkruimtes beheren",

    // 5. Retention
    retentionTitle: "Bewaring",
    retentionIntro: "Hoe lang uw gegevens worden bewaard, in gewone woorden. Wij stellen geen vaste bewaartermijnen in voor uw inhoud.",
    retentionActive: "Zolang uw account open is, worden de bovenstaande items bewaard tot u ze verwijdert.",
    retentionDelete:
      "Een item of uw account verwijderen haalt het meteen uit Ask4Mo. Back-ups worden niet direct gewist.",
    retentionSecurity:
      "Beveiligingsgegevens, zoals inlog- en accountgebeurtenissen, worden zonder uw identiteit bewaard nadat u uw account hebt verwijderd.",
    retentionProviders:
      "Wanneer Mo of een oefengesprek een AI-provider gebruikt, wordt de tekst die u verstuurt door die provider verwerkt volgens zijn eigen voorwaarden.",

    // 6. Legal
    legalTitle: "Toestemming en juridische documenten",
    legalIntro: "De documenten die uw gebruik van Ask4Mo regelen.",
    legalTerms: "Gebruiksvoorwaarden",
    legalPrivacy: "Privacy",
    legalAi: "AI-transparantie",
    legalNotRecorded:
      "Ask4Mo legt nog niet vast welke versie van deze documenten u hebt geaccepteerd, dus er is hier geen acceptatiegeschiedenis om te tonen.",
    legalReview:
      "Vertalingen van juridische documenten zijn technische concepten en zijn niet allemaal door een jurist beoordeeld.",

    // 7. Account deletion
    accountZoneTitle: "Uw account verwijderen",
    accountZoneBody:
      "Uw account verwijderen is permanent. Gebruik eerst de bovenstaande opties als u slechts een deel van uw gegevens wilt verwijderen.",
    accountZoneButton: "Mijn account verwijderen…",
    accountConfirmTitle: "Uw account verwijderen?",
    accountConfirmIntro: "Dit kan niet ongedaan worden gemaakt. Het verwijdert:",
    accDelOpportunities: "Uw kansen",
    accDelDocuments: "Uw documenten en geüploade bestanden",
    accDelMemories: "Uw opgeslagen geheugen, verhalen en feedback",
    accDelInterviews: "Uw oefengesprekken, antwoorden en rapporten",
    accDelSharing: "Uw gedeelde items en lidmaatschappen van werkruimtes (werkruimtes waarvan u eigenaar bent, gaan over op een ander lid of worden verwijderd)",
    accDelAccount: "Uw login, voorkeuren en abonnement",
    accountConfirmKept:
      "Beveiligingsgegevens worden zonder uw identiteit bewaard. Back-ups worden niet direct gewist. Sommige werkgegevens van voorbereidingschats kunnen blijven bestaan tot ze worden opgeruimd.",
    accountConfirmExport: "Eerst uw gegevens downloaden",
    accountConfirmKeep: "Mijn account behouden",
    accountConfirmDelete: "Mijn account voorgoed verwijderen",
    accountDeleteFailed: "Uw account is niet verwijderd. Er is niets gewijzigd. Probeer het opnieuw.",
  },
};

export default nl;
