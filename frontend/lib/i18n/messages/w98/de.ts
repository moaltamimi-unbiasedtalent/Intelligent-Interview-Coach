import type en from "./en";

const de: typeof en = {
  dataPrivacy: {
    // Page
    eyebrow: "Konto",
    title: "Ihre Daten & Ihr Datenschutz",
    description:
      "Sehen Sie, was Ask4Mo für Sie speichert, laden Sie eine Kopie herunter, entfernen Sie einzelne Elemente, prüfen Sie, was Sie teilen, und löschen Sie Ihr Konto. Alles hier betrifft nur Ihre eigenen Daten.",
    backToAccount: "Zurück zum Konto",
    working: "Wird bearbeitet…",
    removed: "Entfernt.",
    actionFailed: "Das hat nicht funktioniert und nichts wurde geändert. Bitte versuchen Sie es erneut.",

    // 1. Overview
    overviewTitle: "Was Ask4Mo für Sie speichert",
    overviewIntro: "Was aktuell unter Ihrem Konto gespeichert ist.",
    cardOpportunities: "Möglichkeiten",
    cardOpportunitiesDesc: "Von Ihnen erstellte Stellenkontexte, einschließlich archivierter.",
    cardDocuments: "Dokumente",
    cardDocumentsDesc: "Hochgeladene Lebensläufe und Stellenbeschreibungen mit den daraus extrahierten Daten.",
    cardMemories: "Gespeicherte Notizen",
    cardMemoriesDesc: "Von Ihnen freigegebene Vorbereitungsfakten, die Mo wiederverwenden darf.",
    cardInterviews: "Übungsinterviews",
    cardInterviewsDesc: "Abgeschlossene Interviews mit Ihren Antworten, Feedback und Berichten.",
    cardShares: "Von Ihnen geteilte Elemente",
    cardSharesDesc: "Berichte oder Storys, für die Sie einem Arbeitsbereich Lesezugriff gegeben haben.",
    cardWorkspaces: "Arbeitsbereiche",
    cardWorkspacesDesc: "Arbeitsbereiche, denen Sie angehören.",
    cardAccount: "Konto und Einstellungen",
    cardAccountDesc:
      "Ihre E-Mail-Adresse, Anmeldemethode, Ihr Tarif und Ihre Spracheinstellungen. Diese werden nur entfernt, wenn Sie Ihr Konto löschen.",

    // 2. Export
    exportTitle: "Ihre Daten herunterladen",
    exportIntro:
      "Laden Sie eine Kopie Ihrer Daten als JSON-Datei herunter. Sie wird beim Klicken erstellt und geht direkt an Ihr Gerät. Ask4Mo speichert die Datei nicht, daher gibt es keinen Link, der abläuft.",
    exportButton: "Meine Daten herunterladen (JSON)",
    exportIncluded: "Enthalten",
    incAccount: "Kontodetails und Einstellungen",
    incOpportunities: "Möglichkeiten",
    incDocuments: "Dokumentdetails und die daraus extrahierten Belege (nicht die Originaldateien)",
    incStories: "Storys",
    incMemories: "Gespeicherte Notizen",
    incInterviews: "Übungsinterviews: Fragen, Ihre Antworten, Feedback und Berichte",
    incFeedback: "Von Ihnen abgegebenes Feedback",
    incSharing: "Mitgliedschaften in Arbeitsbereichen und was Sie teilen",
    exportExcluded: "Nicht enthalten",
    excFiles: "Ihre hochgeladenen Originaldateien. Laden Sie diese unter Dokumente herunter.",
    excAudit: "Sicherheits- und Prüfprotokolle der Plattform",
    excOthers: "Daten anderer Personen, einschließlich allem, was mit Ihnen geteilt wurde",
    excInternal: "Interne Prompts, Modellüberlegungen und Geheimnisse",
    excLegal: "Ein Verlauf, welche rechtlichen Versionen Sie akzeptiert haben (er wird noch nicht erfasst)",

    // 3. Manage individual data
    manageTitle: "Einzelne Daten entfernen",
    manageIntro: "Entfernen Sie ein einzelnes Element, ohne Ihr Konto zu schließen. Löschen kann nicht rückgängig gemacht werden.",
    manageEmpty: "Hier ist nichts gespeichert.",
    manageLoadFailed: "Diese Liste konnte nicht geladen werden.",
    deleteAction: "Löschen",
    archiveAction: "Archivieren",
    archivedBadge: "Archiviert",
    itemOpportunity: "Möglichkeit",
    itemDocument: "Dokument",
    itemMemory: "Notiz",
    itemInterview: "Interview",
    itemUntitled: "Ohne Titel",
    oppNote:
      "Archivieren blendet eine Möglichkeit aus und behält sie. Löschen entfernt sie endgültig. Ihre Übungsinterviews und Berichte bleiben erhalten, sind aber nicht mehr mit ihr verknüpft. Ein damit verknüpftes Stellenbeschreibungsdokument bleibt erhalten: Löschen Sie es unter Dokumente.",
    docNote:
      "Das Löschen eines Dokuments entfernt die hochgeladene Datei, den extrahierten Text und die daraus entnommenen Belege. Daraus erstellte Storys bleiben erhalten, sind aber nicht mehr als auf Ihrem Dokument basierend markiert.",
    memNote:
      "Das Entfernen einer Notiz verhindert, dass Mo sie in künftigen Vorbereitungen wiederverwendet. Ihre bisherigen Interviews und Berichte sind nicht betroffen.",
    intNote:
      "Das Löschen eines Interviews entfernt seine Fragen, Ihre Antworten, das Feedback und den Bericht und beendet jede Freigabe dieses Berichts in Arbeitsbereichen.",
    chatNote:
      "Vorbereitungschats mit Mo sind Arbeitsdaten für Ihre aktuelle Vorbereitung. Einen einzelnen Chat auf dieser Seite zu entfernen ist noch nicht möglich.",
    feedbackNote: "Abgegebene Bewertungen können dort zurückgesetzt werden, wo Sie sie gegeben haben. Sie werden entfernt, wenn Sie Ihr Konto löschen.",
    confirmDeleteOpportunityTitle: "Diese Möglichkeit löschen?",
    confirmDeleteOpportunityBody:
      "“{name}” wird endgültig gelöscht. Verknüpfte Interviews und Berichte bleiben erhalten, ohne die Verknüpfung. Um sie zu behalten, aber auszublenden, archivieren Sie sie stattdessen.",
    confirmArchiveOpportunityTitle: "Diese Möglichkeit archivieren?",
    confirmArchiveOpportunityBody: "“{name}” wird in Ihren Listen ausgeblendet, aber behalten. Sie können sie später wiederfinden.",
    confirmDeleteDocumentTitle: "Dieses Dokument löschen?",
    confirmDeleteDocumentBody:
      "“{name}” wird endgültig gelöscht, einschließlich der Datei, des extrahierten Textes und der daraus entnommenen Belege.",
    confirmDeleteMemoryTitle: "Diese Notiz löschen?",
    confirmDeleteMemoryBody:
      "Mo wird “{name}” nicht mehr wiederverwenden. Ihre bisherigen Interviews und Berichte sind nicht betroffen.",
    confirmDeleteInterviewTitle: "Dieses Interview löschen?",
    confirmDeleteInterviewBody:
      "“{name}” wird endgültig gelöscht, mit Ihren Antworten, dem Feedback und dem Bericht. Jede Freigabe in Arbeitsbereichen endet.",
    confirmArchive: "Archivieren",
    confirmDelete: "Endgültig löschen",

    // 4. Sharing
    sharingTitle: "Teilen und Zugriff",
    sharingIntro:
      "Nichts wird geteilt, es sei denn, Sie teilen es. Das Widerrufen verhindert ab jetzt, dass Mitglieder ein Element ansehen. Es nimmt nichts zurück, was sie bereits gesehen haben.",
    sharingEmpty: "Sie teilen derzeit nichts.",
    sharingLoadFailed: "Ihre Freigaben konnten nicht geladen werden.",
    sharedReport: "Interviewbericht",
    sharedStory: "Story",
    sharedItem: "Geteiltes Element",
    sharedWith: "Geteilt mit {workspace}",
    workspaceFallback: "Arbeitsbereich {id}",
    revokeAction: "Zugriff widerrufen",
    confirmRevokeTitle: "Zugriff widerrufen?",
    confirmRevokeBody:
      "Mitglieder von {workspace} können dieses Element nicht mehr ansehen. Was sie bereits gesehen haben, kann nicht zurückgenommen werden.",
    confirmRevoke: "Zugriff widerrufen",
    manageWorkspaces: "Arbeitsbereiche verwalten",

    // 5. Retention
    retentionTitle: "Aufbewahrung",
    retentionIntro: "Wie lange Ihre Daten aufbewahrt werden, in einfachen Worten. Wir legen keine festen Speicherfristen für Ihre Inhalte fest.",
    retentionActive: "Solange Ihr Konto besteht, werden die oben genannten Elemente aufbewahrt, bis Sie sie löschen.",
    retentionDelete:
      "Das Löschen eines Elements oder Ihres Kontos entfernt es sofort aus Ask4Mo. Backups werden nicht sofort gelöscht.",
    retentionSecurity:
      "Sicherheitsprotokolle, etwa zu Anmeldungen und Kontoereignissen, werden nach dem Löschen Ihres Kontos ohne Ihre Identität aufbewahrt.",
    retentionProviders:
      "Wenn Mo oder ein Übungsinterview einen KI-Anbieter nutzt, wird der von Ihnen gesendete Text von diesem Anbieter nach dessen eigenen Bedingungen verarbeitet.",

    // 6. Legal
    legalTitle: "Einwilligung und rechtliche Dokumente",
    legalIntro: "Die Dokumente, die Ihre Nutzung von Ask4Mo regeln.",
    legalTerms: "Nutzungsbedingungen",
    legalPrivacy: "Datenschutz",
    legalAi: "KI-Transparenz",
    legalNotRecorded:
      "Ask4Mo erfasst noch nicht, welche Version dieser Dokumente Sie akzeptiert haben, daher gibt es hier keinen Zustimmungsverlauf.",
    legalReview:
      "Übersetzungen rechtlicher Dokumente sind technische Entwürfe und wurden nicht alle von einem Juristen geprüft.",

    // 7. Account deletion
    accountZoneTitle: "Konto löschen",
    accountZoneBody:
      "Das Löschen Ihres Kontos ist dauerhaft. Nutzen Sie zuerst die Optionen oben, wenn Sie nur einen Teil Ihrer Daten entfernen möchten.",
    accountZoneButton: "Mein Konto löschen…",
    accountConfirmTitle: "Ihr Konto löschen?",
    accountConfirmIntro: "Das kann nicht rückgängig gemacht werden. Gelöscht werden:",
    accDelOpportunities: "Ihre Möglichkeiten",
    accDelDocuments: "Ihre Dokumente und hochgeladenen Dateien",
    accDelMemories: "Ihre gespeicherten Notizen, Storys und Ihr Feedback",
    accDelInterviews: "Ihre Übungsinterviews, Antworten und Berichte",
    accDelSharing: "Ihre Freigaben und Mitgliedschaften in Arbeitsbereichen (Arbeitsbereiche, die Ihnen gehören, gehen an ein anderes Mitglied über oder werden gelöscht)",
    accDelAccount: "Ihre Anmeldung, Einstellungen und Ihr Tarif",
    accountConfirmKept:
      "Sicherheitsprotokolle werden ohne Ihre Identität aufbewahrt. Backups werden nicht sofort gelöscht. Einige Arbeitsdaten aus Vorbereitungschats können bestehen bleiben, bis sie bereinigt werden.",
    accountConfirmExport: "Zuerst Ihre Daten herunterladen",
    accountConfirmKeep: "Mein Konto behalten",
    accountConfirmDelete: "Mein Konto endgültig löschen",
    accountDeleteFailed: "Ihr Konto wurde nicht gelöscht. Nichts wurde geändert. Bitte versuchen Sie es erneut.",
  },
};

export default de;
