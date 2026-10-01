import type en from "./en";

const es: typeof en = {
  dataPrivacy: {
    // Page
    eyebrow: "Cuenta",
    title: "Tus datos y tu privacidad",
    description:
      "Consulta qué guarda Ask4Mo para ti, descarga una copia, elimina elementos individuales, revisa lo que compartes y elimina tu cuenta. Todo lo que aparece aquí se aplica solo a tus propios datos.",
    backToAccount: "Volver a la cuenta",
    working: "Procesando…",
    removed: "Eliminado.",
    actionFailed: "Eso no funcionó y no se cambió nada. Inténtalo de nuevo.",

    // 1. Overview
    overviewTitle: "Qué guarda Ask4Mo para ti",
    overviewIntro: "Lo que hay guardado ahora mismo en tu cuenta.",
    cardOpportunities: "Oportunidades",
    cardOpportunitiesDesc: "Contextos de empleo que creaste, incluidos los archivados.",
    cardDocuments: "Documentos",
    cardDocumentsDesc: "CV y descripciones de puesto que subiste, con lo que se extrajo de ellos.",
    cardMemories: "Memoria guardada",
    cardMemoriesDesc: "Datos de preparación que aprobaste para que Mo los reutilice.",
    cardInterviews: "Entrevistas de práctica",
    cardInterviewsDesc: "Entrevistas completadas con tus respuestas, comentarios e informes.",
    cardShares: "Elementos que compartes",
    cardSharesDesc: "Informes o historias a los que diste acceso de lectura a un espacio de trabajo.",
    cardWorkspaces: "Espacios de trabajo",
    cardWorkspacesDesc: "Espacios de trabajo a los que perteneces.",
    cardAccount: "Cuenta y preferencias",
    cardAccountDesc:
      "Tu correo electrónico, método de inicio de sesión, plan y ajustes de idioma. Solo se eliminan cuando eliminas tu cuenta.",

    // 2. Export
    exportTitle: "Descarga tus datos",
    exportIntro:
      "Obtén una copia de tus datos como archivo JSON. Se crea cuando haces clic y va directamente a tu dispositivo. Ask4Mo no conserva el archivo, así que no hay ningún enlace que caduque.",
    exportButton: "Descargar mis datos (JSON)",
    exportIncluded: "Incluido",
    incAccount: "Datos de la cuenta y preferencias",
    incOpportunities: "Oportunidades",
    incDocuments: "Detalles de los documentos y las evidencias extraídas de ellos (no los archivos originales)",
    incStories: "Historias",
    incMemories: "Memoria guardada",
    incInterviews: "Entrevistas de práctica: preguntas, tus respuestas, comentarios e informes",
    incFeedback: "Comentarios que enviaste",
    incSharing: "Pertenencia a espacios de trabajo y lo que compartes",
    exportExcluded: "No incluido",
    excFiles: "Tus archivos originales subidos. Descárgalos desde Documentos.",
    excAudit: "Registros de seguridad y auditoría que conserva la plataforma",
    excOthers: "Datos de otras personas, incluido todo lo que se haya compartido contigo",
    excInternal: "Prompts internos, razonamiento del modelo y secretos",
    excLegal: "Un historial de qué versiones legales aceptaste (todavía no se registra)",

    // 3. Manage individual data
    manageTitle: "Eliminar datos individuales",
    manageIntro: "Elimina un elemento sin cerrar tu cuenta. Eliminar no se puede deshacer.",
    manageEmpty: "No hay nada guardado aquí.",
    manageLoadFailed: "No se pudo cargar esta lista.",
    deleteAction: "Eliminar",
    archiveAction: "Archivar",
    archivedBadge: "Archivada",
    itemOpportunity: "Oportunidad",
    itemDocument: "Documento",
    itemMemory: "Memoria",
    itemInterview: "Entrevista",
    itemUntitled: "Sin título",
    oppNote:
      "Archivar oculta una oportunidad y la conserva. Eliminar la quita para siempre. Tus entrevistas de práctica e informes se mantienen, pero ya no están vinculados a ella. Un documento de descripción de puesto vinculado se conserva: elimínalo en Documentos.",
    docNote:
      "Eliminar un documento quita el archivo subido, su texto extraído y las evidencias tomadas de él. Las historias creadas a partir de él se conservan, pero ya no se marcan como basadas en tu documento.",
    memNote:
      "Quitar una memoria evita que Mo la reutilice en futuras preparaciones. Tus entrevistas e informes anteriores no se ven afectados.",
    intNote:
      "Eliminar una entrevista quita sus preguntas, tus respuestas, los comentarios y el informe, y pone fin a cualquier uso compartido de ese informe en espacios de trabajo.",
    chatNote:
      "Los chats de preparación con Mo son datos de trabajo de tu preparación actual. Todavía no es posible quitar un chat individual desde esta página.",
    feedbackNote: "Las valoraciones que diste se pueden restablecer donde las diste. Se eliminan cuando eliminas tu cuenta.",
    confirmDeleteOpportunityTitle: "¿Eliminar esta oportunidad?",
    confirmDeleteOpportunityBody:
      "“{name}” se eliminará para siempre. Las entrevistas e informes vinculados se conservan, sin el vínculo. Para conservarla pero ocultarla, archívala en su lugar.",
    confirmArchiveOpportunityTitle: "¿Archivar esta oportunidad?",
    confirmArchiveOpportunityBody: "“{name}” se ocultará de tus listas, pero se conservará. Podrás encontrarla más adelante.",
    confirmDeleteDocumentTitle: "¿Eliminar este documento?",
    confirmDeleteDocumentBody:
      "“{name}” se eliminará para siempre, incluidos el archivo, el texto extraído y las evidencias tomadas de él.",
    confirmDeleteMemoryTitle: "¿Eliminar esta memoria?",
    confirmDeleteMemoryBody:
      "Mo ya no reutilizará “{name}”. Tus entrevistas e informes anteriores no se ven afectados.",
    confirmDeleteInterviewTitle: "¿Eliminar esta entrevista?",
    confirmDeleteInterviewBody:
      "“{name}” se eliminará para siempre, con tus respuestas, comentarios e informe. Se pone fin a cualquier uso compartido en espacios de trabajo.",
    confirmArchive: "Archivar",
    confirmDelete: "Eliminar para siempre",

    // 4. Sharing
    sharingTitle: "Uso compartido y acceso",
    sharingIntro:
      "No se comparte nada a menos que tú lo compartas. Revocar impide que los miembros vean un elemento a partir de ahora. No retira nada de lo que ya vieron.",
    sharingEmpty: "No estás compartiendo nada.",
    sharingLoadFailed: "No se pudieron cargar tus elementos compartidos.",
    sharedReport: "Informe de entrevista",
    sharedStory: "Historia",
    sharedItem: "Elemento compartido",
    sharedWith: "Compartido con {workspace}",
    workspaceFallback: "espacio de trabajo {id}",
    revokeAction: "Revocar acceso",
    confirmRevokeTitle: "¿Revocar el acceso?",
    confirmRevokeBody:
      "Los miembros de {workspace} ya no podrán ver este elemento. Lo que ya vieron no se puede retirar.",
    confirmRevoke: "Revocar acceso",
    manageWorkspaces: "Gestionar espacios de trabajo",

    // 5. Retention
    retentionTitle: "Conservación",
    retentionIntro: "Cuánto tiempo se conservan tus datos, en términos sencillos. No fijamos plazos de almacenamiento para tu contenido.",
    retentionActive: "Mientras tu cuenta esté abierta, los elementos anteriores se conservan hasta que los elimines.",
    retentionDelete:
      "Eliminar un elemento o tu cuenta lo quita de Ask4Mo de inmediato. Las copias de seguridad no se borran al instante.",
    retentionSecurity:
      "Los registros de seguridad, como los eventos de inicio de sesión y de cuenta, se conservan sin tu identidad después de que elimines tu cuenta.",
    retentionProviders:
      "Cuando Mo o una entrevista de práctica usa un proveedor de IA, ese proveedor procesa el texto que envías según sus propias condiciones.",

    // 6. Legal
    legalTitle: "Consentimiento y documentos legales",
    legalIntro: "Los documentos que regulan tu uso de Ask4Mo.",
    legalTerms: "Condiciones de uso",
    legalPrivacy: "Privacidad",
    legalAi: "Transparencia de la IA",
    legalNotRecorded:
      "Ask4Mo todavía no registra qué versión de estos documentos aceptaste, así que no hay historial de aceptación que mostrar aquí.",
    legalReview:
      "Las traducciones de los documentos legales son borradores de ingeniería y no todas han sido revisadas por un abogado.",

    // 7. Account deletion
    accountZoneTitle: "Eliminar tu cuenta",
    accountZoneBody:
      "Eliminar tu cuenta es permanente. Usa primero las opciones anteriores si solo quieres quitar una parte de tus datos.",
    accountZoneButton: "Eliminar mi cuenta…",
    accountConfirmTitle: "¿Eliminar tu cuenta?",
    accountConfirmIntro: "Esto no se puede deshacer. Elimina:",
    accDelOpportunities: "Tus oportunidades",
    accDelDocuments: "Tus documentos y archivos subidos",
    accDelMemories: "Tu memoria guardada, historias y comentarios",
    accDelInterviews: "Tus entrevistas de práctica, respuestas e informes",
    accDelSharing: "Tus elementos compartidos y pertenencia a espacios de trabajo (los espacios de trabajo que posees pasan a otro miembro o se eliminan)",
    accDelAccount: "Tu inicio de sesión, preferencias y plan",
    accountConfirmKept:
      "Los registros de seguridad se conservan sin tu identidad. Las copias de seguridad no se borran al instante. Algunos datos de trabajo de los chats de preparación pueden permanecer hasta que se limpien.",
    accountConfirmExport: "Descargar primero tus datos",
    accountConfirmKeep: "Conservar mi cuenta",
    accountConfirmDelete: "Eliminar mi cuenta para siempre",
    accountDeleteFailed: "Tu cuenta no se eliminó. No se cambió nada. Inténtalo de nuevo.",
  },
};

export default es;
