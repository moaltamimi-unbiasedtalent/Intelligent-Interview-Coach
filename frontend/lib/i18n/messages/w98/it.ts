import type en from "./en";

const it: typeof en = {
  dataPrivacy: {
    // Page
    eyebrow: "Account",
    title: "I tuoi dati e la tua privacy",
    description:
      "Scopri cosa conserva Ask4Mo per te, scarica una copia, rimuovi singoli elementi, controlla cosa condividi ed elimina il tuo account. Tutto qui riguarda solo i tuoi dati.",
    backToAccount: "Torna all’account",
    working: "Operazione in corso…",
    removed: "Rimosso.",
    actionFailed: "Non ha funzionato e non è stato modificato nulla. Riprova.",

    // 1. Overview
    overviewTitle: "Cosa conserva Ask4Mo per te",
    overviewIntro: "Ciò che è memorizzato in questo momento nel tuo account.",
    cardOpportunities: "Opportunità",
    cardOpportunitiesDesc: "I contesti di lavoro che hai creato, comprese quelle archiviate.",
    cardDocuments: "Documenti",
    cardDocumentsDesc: "CV e descrizioni di lavoro che hai caricato, con ciò che ne è stato estratto.",
    cardMemories: "Memoria salvata",
    cardMemoriesDesc: "Fatti di preparazione che hai approvato perché Mo li riutilizzi.",
    cardInterviews: "Colloqui di pratica",
    cardInterviewsDesc: "Colloqui completati con le tue risposte, i feedback e i report.",
    cardShares: "Elementi che condividi",
    cardSharesDesc: "Report o storie per cui hai dato accesso in sola visualizzazione a uno spazio di lavoro.",
    cardWorkspaces: "Spazi di lavoro",
    cardWorkspacesDesc: "Gli spazi di lavoro di cui fai parte.",
    cardAccount: "Account e preferenze",
    cardAccountDesc:
      "La tua e-mail, il metodo di accesso, il piano e le impostazioni della lingua. Vengono rimossi solo quando elimini il tuo account.",

    // 2. Export
    exportTitle: "Scarica i tuoi dati",
    exportIntro:
      "Ottieni una copia dei tuoi dati come file JSON. Viene creato quando fai clic e va direttamente sul tuo dispositivo. Ask4Mo non conserva il file, quindi non c’è nessun link che scade.",
    exportButton: "Scarica i miei dati (JSON)",
    exportIncluded: "Inclusi",
    incAccount: "Dettagli dell’account e preferenze",
    incOpportunities: "Opportunità",
    incDocuments: "Dettagli dei documenti e prove estratte da essi (non i file originali)",
    incStories: "Storie",
    incMemories: "Memoria salvata",
    incInterviews: "Colloqui di pratica: domande, le tue risposte, feedback e report",
    incFeedback: "Feedback che hai inviato",
    incSharing: "Appartenenza agli spazi di lavoro e ciò che condividi",
    exportExcluded: "Non inclusi",
    excFiles: "I tuoi file originali caricati. Scaricali da Documenti.",
    excAudit: "Registri di sicurezza e di audit conservati dalla piattaforma",
    excOthers: "Dati di altre persone, compreso tutto ciò che è condiviso con te",
    excInternal: "Prompt interni, ragionamento del modello e segreti",
    excLegal: "Uno storico delle versioni legali che hai accettato (non è ancora registrato)",

    // 3. Manage individual data
    manageTitle: "Rimuovi singoli dati",
    manageIntro: "Rimuovi un elemento senza chiudere il tuo account. L’eliminazione non può essere annullata.",
    manageEmpty: "Qui non c’è nulla di memorizzato.",
    manageLoadFailed: "Non è stato possibile caricare questo elenco.",
    deleteAction: "Elimina",
    archiveAction: "Archivia",
    archivedBadge: "Archiviata",
    itemOpportunity: "Opportunità",
    itemDocument: "Documento",
    itemMemory: "Memoria",
    itemInterview: "Colloquio",
    itemUntitled: "Senza titolo",
    oppNote:
      "Archiviare nasconde un’opportunità e la conserva. Eliminare la rimuove definitivamente. I tuoi colloqui di pratica e i report restano, ma non sono più collegati a essa. Un documento di descrizione del lavoro collegato viene conservato: eliminalo in Documenti.",
    docNote:
      "Eliminare un documento rimuove il file caricato, il testo estratto e le prove ricavate da esso. Le storie create a partire da esso vengono conservate, ma non sono più indicate come basate sul tuo documento.",
    memNote:
      "Rimuovere una memoria impedisce a Mo di riutilizzarla nelle preparazioni future. I tuoi colloqui e report passati non sono interessati.",
    intNote:
      "Eliminare un colloquio rimuove le sue domande, le tue risposte, il feedback e il report, e pone fine a qualsiasi condivisione di quel report negli spazi di lavoro.",
    chatNote:
      "Le chat di preparazione con Mo sono dati di lavoro per la tua preparazione attuale. Rimuovere una singola chat da questa pagina non è ancora possibile.",
    feedbackNote: "Le valutazioni che hai dato possono essere reimpostate dove le hai date. Vengono rimosse quando elimini il tuo account.",
    confirmDeleteOpportunityTitle: "Eliminare questa opportunità?",
    confirmDeleteOpportunityBody:
      "“{name}” verrà eliminata definitivamente. I colloqui e i report collegati vengono conservati, senza il collegamento. Per conservarla ma nasconderla, archiviala invece.",
    confirmArchiveOpportunityTitle: "Archiviare questa opportunità?",
    confirmArchiveOpportunityBody: "“{name}” verrà nascosta dagli elenchi ma conservata. Potrai ritrovarla in seguito.",
    confirmDeleteDocumentTitle: "Eliminare questo documento?",
    confirmDeleteDocumentBody:
      "“{name}” verrà eliminato definitivamente, compresi il file, il testo estratto e le prove ricavate da esso.",
    confirmDeleteMemoryTitle: "Eliminare questa memoria?",
    confirmDeleteMemoryBody:
      "Mo non riutilizzerà più “{name}”. I tuoi colloqui e report passati non sono interessati.",
    confirmDeleteInterviewTitle: "Eliminare questo colloquio?",
    confirmDeleteInterviewBody:
      "“{name}” verrà eliminato definitivamente, con le tue risposte, il feedback e il report. Qualsiasi condivisione negli spazi di lavoro termina.",
    confirmArchive: "Archivia",
    confirmDelete: "Elimina definitivamente",

    // 4. Sharing
    sharingTitle: "Condivisione e accesso",
    sharingIntro:
      "Nulla viene condiviso se non lo condividi tu. Revocare impedisce ai membri di visualizzare un elemento da ora in poi. Non annulla ciò che hanno già visto.",
    sharingEmpty: "Non stai condividendo nulla.",
    sharingLoadFailed: "Non è stato possibile caricare le tue condivisioni.",
    sharedReport: "Report del colloquio",
    sharedStory: "Storia",
    sharedItem: "Elemento condiviso",
    sharedWith: "Condiviso con {workspace}",
    workspaceFallback: "spazio di lavoro {id}",
    revokeAction: "Revoca l’accesso",
    confirmRevokeTitle: "Revocare l’accesso?",
    confirmRevokeBody:
      "I membri di {workspace} non potranno più visualizzare questo elemento. Ciò che hanno già visto non può essere ritirato.",
    confirmRevoke: "Revoca l’accesso",
    manageWorkspaces: "Gestisci gli spazi di lavoro",

    // 5. Retention
    retentionTitle: "Conservazione",
    retentionIntro: "Per quanto tempo vengono conservati i tuoi dati, in termini semplici. Non fissiamo periodi di conservazione per i tuoi contenuti.",
    retentionActive: "Finché il tuo account è aperto, gli elementi sopra vengono conservati finché non li elimini.",
    retentionDelete:
      "Eliminare un elemento o il tuo account lo rimuove subito da Ask4Mo. I backup non vengono cancellati all’istante.",
    retentionSecurity:
      "I registri di sicurezza, come gli eventi di accesso e dell’account, vengono conservati senza la tua identità dopo l’eliminazione del tuo account.",
    retentionProviders:
      "Quando Mo o un colloquio di pratica usa un fornitore di IA, il testo che invii viene elaborato da quel fornitore secondo le sue condizioni.",

    // 6. Legal
    legalTitle: "Consenso e documenti legali",
    legalIntro: "I documenti che regolano l’uso di Ask4Mo da parte tua.",
    legalTerms: "Condizioni d’uso",
    legalPrivacy: "Privacy",
    legalAi: "Trasparenza dell’IA",
    legalNotRecorded:
      "Ask4Mo non registra ancora quale versione di questi documenti hai accettato, quindi qui non c’è uno storico delle accettazioni da mostrare.",
    legalReview:
      "Le traduzioni dei documenti legali sono bozze di ingegneria e non tutte sono state riviste da un avvocato.",

    // 7. Account deletion
    accountZoneTitle: "Elimina il tuo account",
    accountZoneBody:
      "L’eliminazione del tuo account è permanente. Usa prima le opzioni sopra se vuoi rimuovere solo una parte dei tuoi dati.",
    accountZoneButton: "Elimina il mio account…",
    accountConfirmTitle: "Eliminare il tuo account?",
    accountConfirmIntro: "Questa azione non può essere annullata. Elimina:",
    accDelOpportunities: "Le tue opportunità",
    accDelDocuments: "I tuoi documenti e file caricati",
    accDelMemories: "La tua memoria salvata, le storie e i feedback",
    accDelInterviews: "I tuoi colloqui di pratica, le risposte e i report",
    accDelSharing: "Le tue condivisioni e appartenenze agli spazi di lavoro (gli spazi di lavoro di cui sei proprietario passano a un altro membro o vengono eliminati)",
    accDelAccount: "Il tuo accesso, le preferenze e il piano",
    accountConfirmKept:
      "I registri di sicurezza vengono conservati senza la tua identità. I backup non vengono cancellati all’istante. Alcuni dati di lavoro delle chat di preparazione possono restare finché non vengono ripuliti.",
    accountConfirmExport: "Scarica prima i tuoi dati",
    accountConfirmKeep: "Mantieni il mio account",
    accountConfirmDelete: "Elimina il mio account definitivamente",
    accountDeleteFailed: "Il tuo account non è stato eliminato. Non è stato modificato nulla. Riprova.",
  },
};

export default it;
