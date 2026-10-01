import type en from "./en";

const pt: typeof en = {
  dataPrivacy: {
    // Page
    eyebrow: "Conta",
    title: "Os seus dados e a sua privacidade",
    description:
      "Veja o que o Ask4Mo guarda para si, transfira uma cópia, elimine itens individuais, reveja o que partilha e elimine a sua conta. Tudo aqui se aplica apenas aos seus próprios dados.",
    backToAccount: "Voltar à conta",
    working: "A processar…",
    removed: "Removido.",
    actionFailed: "Isso não funcionou e nada foi alterado. Tente novamente.",

    // 1. Overview
    overviewTitle: "O que o Ask4Mo guarda para si",
    overviewIntro: "O que está guardado neste momento na sua conta.",
    cardOpportunities: "Oportunidades",
    cardOpportunitiesDesc: "Contextos de emprego que criou, incluindo os arquivados.",
    cardDocuments: "Documentos",
    cardDocumentsDesc: "CV e descrições de funções que carregou, com o que foi extraído deles.",
    cardMemories: "Memória guardada",
    cardMemoriesDesc: "Factos de preparação que aprovou para o Mo reutilizar.",
    cardInterviews: "Entrevistas de prática",
    cardInterviewsDesc: "Entrevistas concluídas com as suas respostas, comentários e relatórios.",
    cardShares: "Itens que partilha",
    cardSharesDesc: "Relatórios ou histórias a que deu acesso de leitura a um espaço de trabalho.",
    cardWorkspaces: "Espaços de trabalho",
    cardWorkspacesDesc: "Espaços de trabalho a que pertence.",
    cardAccount: "Conta e preferências",
    cardAccountDesc:
      "O seu e-mail, método de início de sessão, plano e definições de idioma. Só são removidos quando elimina a sua conta.",

    // 2. Export
    exportTitle: "Transfira os seus dados",
    exportIntro:
      "Obtenha uma cópia dos seus dados como ficheiro JSON. É criado quando clica e vai diretamente para o seu dispositivo. O Ask4Mo não guarda o ficheiro, por isso não há nenhuma ligação que expire.",
    exportButton: "Transferir os meus dados (JSON)",
    exportIncluded: "Incluído",
    incAccount: "Detalhes da conta e preferências",
    incOpportunities: "Oportunidades",
    incDocuments: "Detalhes dos documentos e as evidências extraídas deles (não os ficheiros originais)",
    incStories: "Histórias",
    incMemories: "Memória guardada",
    incInterviews: "Entrevistas de prática: perguntas, as suas respostas, comentários e relatórios",
    incFeedback: "Comentários que enviou",
    incSharing: "Pertença a espaços de trabalho e o que partilha",
    exportExcluded: "Não incluído",
    excFiles: "Os seus ficheiros originais carregados. Transfira-os a partir de Documentos.",
    excAudit: "Registos de segurança e auditoria mantidos pela plataforma",
    excOthers: "Dados de outras pessoas, incluindo tudo o que foi partilhado consigo",
    excInternal: "Prompts internos, raciocínio do modelo e segredos",
    excLegal: "Um histórico de que versões legais aceitou (ainda não é registado)",

    // 3. Manage individual data
    manageTitle: "Remover dados individuais",
    manageIntro: "Remova um item sem encerrar a sua conta. Eliminar não pode ser desfeito.",
    manageEmpty: "Não há nada guardado aqui.",
    manageLoadFailed: "Não foi possível carregar esta lista.",
    deleteAction: "Eliminar",
    archiveAction: "Arquivar",
    archivedBadge: "Arquivada",
    itemOpportunity: "Oportunidade",
    itemDocument: "Documento",
    itemMemory: "Memória",
    itemInterview: "Entrevista",
    itemUntitled: "Sem título",
    oppNote:
      "Arquivar oculta uma oportunidade e mantém-na. Eliminar remove-a para sempre. As suas entrevistas de prática e relatórios mantêm-se, mas deixam de estar associados a ela. Um documento de descrição de função associado é mantido: elimine-o em Documentos.",
    docNote:
      "Eliminar um documento remove o ficheiro carregado, o texto extraído e as evidências retiradas dele. As histórias criadas a partir dele são mantidas, mas deixam de estar marcadas como baseadas no seu documento.",
    memNote:
      "Remover uma memória impede que o Mo a reutilize em preparações futuras. As suas entrevistas e relatórios anteriores não são afetados.",
    intNote:
      "Eliminar uma entrevista remove as suas perguntas, as suas respostas, os comentários e o relatório, e termina qualquer partilha desse relatório em espaços de trabalho.",
    chatNote:
      "As conversas de preparação com o Mo são dados de trabalho da sua preparação atual. Ainda não é possível remover uma conversa individual a partir desta página.",
    feedbackNote: "As avaliações que deu podem ser repostas onde as deu. São removidas quando elimina a sua conta.",
    confirmDeleteOpportunityTitle: "Eliminar esta oportunidade?",
    confirmDeleteOpportunityBody:
      "“{name}” será eliminada para sempre. As entrevistas e relatórios associados são mantidos, sem a associação. Para a manter mas ocultá-la, arquive-a em vez disso.",
    confirmArchiveOpportunityTitle: "Arquivar esta oportunidade?",
    confirmArchiveOpportunityBody: "“{name}” será ocultada das suas listas, mas mantida. Poderá encontrá-la mais tarde.",
    confirmDeleteDocumentTitle: "Eliminar este documento?",
    confirmDeleteDocumentBody:
      "“{name}” será eliminado para sempre, incluindo o ficheiro, o texto extraído e as evidências retiradas dele.",
    confirmDeleteMemoryTitle: "Eliminar esta memória?",
    confirmDeleteMemoryBody:
      "O Mo deixará de reutilizar “{name}”. As suas entrevistas e relatórios anteriores não são afetados.",
    confirmDeleteInterviewTitle: "Eliminar esta entrevista?",
    confirmDeleteInterviewBody:
      "“{name}” será eliminada para sempre, com as suas respostas, comentários e relatório. Qualquer partilha em espaços de trabalho termina.",
    confirmArchive: "Arquivar",
    confirmDelete: "Eliminar para sempre",

    // 4. Sharing
    sharingTitle: "Partilha e acesso",
    sharingIntro:
      "Nada é partilhado a menos que o partilhe. Revogar impede os membros de ver um item a partir de agora. Não retira nada do que já viram.",
    sharingEmpty: "Não está a partilhar nada.",
    sharingLoadFailed: "Não foi possível carregar as suas partilhas.",
    sharedReport: "Relatório de entrevista",
    sharedStory: "História",
    sharedItem: "Item partilhado",
    sharedWith: "Partilhado com {workspace}",
    workspaceFallback: "espaço de trabalho {id}",
    revokeAction: "Revogar acesso",
    confirmRevokeTitle: "Revogar o acesso?",
    confirmRevokeBody:
      "Os membros de {workspace} deixarão de poder ver este item. O que já viram não pode ser retirado.",
    confirmRevoke: "Revogar acesso",
    manageWorkspaces: "Gerir espaços de trabalho",

    // 5. Retention
    retentionTitle: "Retenção",
    retentionIntro: "Durante quanto tempo os seus dados são mantidos, em termos simples. Não definimos prazos fixos de armazenamento para o seu conteúdo.",
    retentionActive: "Enquanto a sua conta estiver aberta, os itens acima são mantidos até os eliminar.",
    retentionDelete:
      "Eliminar um item ou a sua conta remove-o do Ask4Mo de imediato. As cópias de segurança não são apagadas instantaneamente.",
    retentionSecurity:
      "Os registos de segurança, como eventos de início de sessão e da conta, são mantidos sem a sua identidade depois de eliminar a sua conta.",
    retentionProviders:
      "Quando o Mo ou uma entrevista de prática usa um fornecedor de IA, o texto que envia é processado por esse fornecedor segundo os seus próprios termos.",

    // 6. Legal
    legalTitle: "Consentimento e documentos legais",
    legalIntro: "Os documentos que regem a sua utilização do Ask4Mo.",
    legalTerms: "Termos de utilização",
    legalPrivacy: "Privacidade",
    legalAi: "Transparência da IA",
    legalNotRecorded:
      "O Ask4Mo ainda não regista que versão destes documentos aceitou, por isso não há histórico de aceitação para mostrar aqui.",
    legalReview:
      "As traduções de documentos legais são rascunhos de engenharia e nem todas foram revistas por um advogado.",

    // 7. Account deletion
    accountZoneTitle: "Eliminar a sua conta",
    accountZoneBody:
      "Eliminar a sua conta é permanente. Use primeiro as opções acima se quiser apenas remover alguns dos seus dados.",
    accountZoneButton: "Eliminar a minha conta…",
    accountConfirmTitle: "Eliminar a sua conta?",
    accountConfirmIntro: "Isto não pode ser desfeito. Elimina:",
    accDelOpportunities: "As suas oportunidades",
    accDelDocuments: "Os seus documentos e ficheiros carregados",
    accDelMemories: "A sua memória guardada, histórias e comentários",
    accDelInterviews: "As suas entrevistas de prática, respostas e relatórios",
    accDelSharing: "As suas partilhas e pertença a espaços de trabalho (os espaços de trabalho de que é proprietário passam para outro membro ou são eliminados)",
    accDelAccount: "O seu início de sessão, preferências e plano",
    accountConfirmKept:
      "Os registos de segurança são mantidos sem a sua identidade. As cópias de segurança não são apagadas instantaneamente. Alguns dados de trabalho das conversas de preparação podem permanecer até serem limpos.",
    accountConfirmExport: "Transferir primeiro os seus dados",
    accountConfirmKeep: "Manter a minha conta",
    accountConfirmDelete: "Eliminar a minha conta para sempre",
    accountDeleteFailed: "A sua conta não foi eliminada. Nada foi alterado. Tente novamente.",
  },
};

export default pt;
