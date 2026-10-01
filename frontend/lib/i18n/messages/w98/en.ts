// P10B-W9.8 - Data & Privacy Center copy (English source of truth).
//
// Wording rules: say exactly what the backend does. "Delete" = removed from the account now (not
// recoverable); "Archive" = hidden but kept; "Revoke" = future access stops, nothing already seen is
// erased. No retention periods, no legal-compliance claims. The protected slogan is not part of this file.

const en = {
  dataPrivacy: {
    // Page
    eyebrow: "Account",
    title: "Your data & privacy",
    description:
      "See what Ask4Mo keeps for you, download a copy, remove individual items, review what you share, and delete your account. Everything here applies only to your own data.",
    backToAccount: "Back to account",
    working: "Working…",
    removed: "Removed.",
    actionFailed: "That did not work and nothing was changed. Please try again.",

    // 1. Overview
    overviewTitle: "What Ask4Mo stores for you",
    overviewIntro: "What is stored under your account right now.",
    cardOpportunities: "Opportunities",
    cardOpportunitiesDesc: "Job contexts you created, including archived ones.",
    cardDocuments: "Documents",
    cardDocumentsDesc: "CVs and job descriptions you uploaded, with what was extracted from them.",
    cardMemories: "Saved memories",
    cardMemoriesDesc: "Preparation facts you approved for Mo to reuse.",
    cardInterviews: "Practice interviews",
    cardInterviewsDesc: "Completed interviews with your answers, feedback and reports.",
    cardShares: "Items you share",
    cardSharesDesc: "Reports or stories you gave a workspace view access to.",
    cardWorkspaces: "Workspaces",
    cardWorkspacesDesc: "Workspaces you belong to.",
    cardAccount: "Account and preferences",
    cardAccountDesc:
      "Your email, sign-in method, plan and language settings. These are removed only when you delete your account.",

    // 2. Export
    exportTitle: "Download your data",
    exportIntro:
      "Get a copy of your data as a JSON file. It is created when you click and goes straight to your device. Ask4Mo does not keep the file, so there is no link that expires.",
    exportButton: "Download my data (JSON)",
    exportIncluded: "Included",
    incAccount: "Account details and preferences",
    incOpportunities: "Opportunities",
    incDocuments: "Document details and the evidence extracted from them (not the original files)",
    incStories: "Stories",
    incMemories: "Saved memories",
    incInterviews: "Practice interviews: questions, your answers, feedback and reports",
    incFeedback: "Feedback you submitted",
    incSharing: "Workspace memberships and what you share",
    exportExcluded: "Not included",
    excFiles: "Your original uploaded files. Download them from Documents.",
    excAudit: "Security and audit records kept by the platform",
    excOthers: "Other people's data, including anything shared with you",
    excInternal: "Internal prompts, model reasoning and secrets",
    excLegal: "A history of which legal versions you accepted (it is not recorded yet)",

    // 3. Manage individual data
    manageTitle: "Remove individual data",
    manageIntro: "Remove one item without closing your account. Deleting cannot be undone.",
    manageEmpty: "Nothing stored here.",
    manageLoadFailed: "This list could not be loaded.",
    deleteAction: "Delete",
    archiveAction: "Archive",
    archivedBadge: "Archived",
    itemOpportunity: "Opportunity",
    itemDocument: "Document",
    itemMemory: "Memory",
    itemInterview: "Interview",
    itemUntitled: "Untitled",
    oppNote:
      "Archive hides an Opportunity and keeps it. Delete removes it for good. Your practice interviews and reports stay but are no longer linked to it. A job description document linked to it is kept: delete it under Documents.",
    docNote:
      "Deleting a document removes the uploaded file, its extracted text and the evidence taken from it. Stories built from it are kept but are no longer marked as based on your document.",
    memNote:
      "Removing a memory stops Mo from reusing it in future preparation. Your past interviews and reports are not affected.",
    intNote:
      "Deleting an interview removes its questions, your answers, the feedback and the report, and ends any workspace sharing of that report.",
    chatNote:
      "Preparation chats with Mo are working data for your current preparation. Removing a single chat from this page is not available yet.",
    feedbackNote: "Ratings you gave can be reset where you gave them. They are removed when you delete your account.",
    confirmDeleteOpportunityTitle: "Delete this Opportunity?",
    confirmDeleteOpportunityBody:
      "“{name}” will be deleted for good. Linked interviews and reports are kept, without the link. To keep it but hide it, archive it instead.",
    confirmArchiveOpportunityTitle: "Archive this Opportunity?",
    confirmArchiveOpportunityBody: "“{name}” will be hidden from your lists but kept. You can still find it later.",
    confirmDeleteDocumentTitle: "Delete this document?",
    confirmDeleteDocumentBody:
      "“{name}” will be deleted for good, including the file, the extracted text and the evidence taken from it.",
    confirmDeleteMemoryTitle: "Delete this memory?",
    confirmDeleteMemoryBody:
      "Mo will no longer reuse “{name}”. Your past interviews and reports are not affected.",
    confirmDeleteInterviewTitle: "Delete this interview?",
    confirmDeleteInterviewBody:
      "“{name}” will be deleted for good, with your answers, feedback and report. Any workspace sharing of it ends.",
    confirmArchive: "Archive",
    confirmDelete: "Delete for good",

    // 4. Sharing
    sharingTitle: "Sharing and access",
    sharingIntro:
      "Nothing is shared unless you share it. Revoking stops members from viewing an item from now on. It does not take back anything they already saw.",
    sharingEmpty: "You are not sharing anything.",
    sharingLoadFailed: "Your shares could not be loaded.",
    sharedReport: "Interview report",
    sharedStory: "Story",
    sharedItem: "Shared item",
    sharedWith: "Shared with {workspace}",
    workspaceFallback: "workspace {id}",
    revokeAction: "Revoke access",
    confirmRevokeTitle: "Revoke access?",
    confirmRevokeBody:
      "Members of {workspace} will no longer be able to view this item. Anything they already saw cannot be taken back.",
    confirmRevoke: "Revoke access",
    manageWorkspaces: "Manage workspaces",

    // 5. Retention
    retentionTitle: "Retention",
    retentionIntro: "How long your data is kept, in plain terms. We do not set fixed storage periods for your content.",
    retentionActive: "While your account is open, the items above are kept until you delete them.",
    retentionDelete:
      "Deleting an item or your account removes it from Ask4Mo straight away. Backups are not erased instantly.",
    retentionSecurity:
      "Security records, such as sign-in and account events, are kept with your identity removed after you delete your account.",
    retentionProviders:
      "When Mo or a practice interview uses an AI provider, the text you send is processed by that provider under its own terms.",

    // 6. Legal
    legalTitle: "Consent and legal documents",
    legalIntro: "The documents that govern your use of Ask4Mo.",
    legalTerms: "Terms of Use",
    legalPrivacy: "Privacy Policy",
    legalAi: "AI Transparency",
    legalNotRecorded:
      "Ask4Mo does not yet record which version of these documents you accepted, so there is no acceptance history to show here.",
    legalReview:
      "Translations of legal documents are engineering drafts and have not all been reviewed by a lawyer.",

    // 7. Account deletion
    accountZoneTitle: "Delete your account",
    accountZoneBody:
      "Deleting your account is permanent. Use the options above first if you only want to remove some of your data.",
    accountZoneButton: "Delete my account…",
    accountConfirmTitle: "Delete your account?",
    accountConfirmIntro: "This cannot be undone. It deletes:",
    accDelOpportunities: "Your Opportunities",
    accDelDocuments: "Your documents and uploaded files",
    accDelMemories: "Your saved memories, stories and feedback",
    accDelInterviews: "Your practice interviews, answers and reports",
    accDelSharing: "Your sharing and workspace memberships (workspaces you own pass to another member or are deleted)",
    accDelAccount: "Your sign-in, preferences and plan",
    accountConfirmKept:
      "Security records are kept with your identity removed. Backups are not erased instantly. Some preparation-chat working data may remain until it is cleaned up.",
    accountConfirmExport: "Download your data first",
    accountConfirmKeep: "Keep my account",
    accountConfirmDelete: "Delete my account for good",
    accountDeleteFailed: "Your account was not deleted. Nothing was changed. Please try again.",
  },
};

export default en;
