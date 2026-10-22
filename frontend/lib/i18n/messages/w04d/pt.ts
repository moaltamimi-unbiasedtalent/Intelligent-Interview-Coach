import type en from "./en";

const pt: typeof en = {
  states: {
    aiNotConfigured: "As funcionalidades de IA não estão configuradas neste ambiente do Ask4Mo, por isso nada foi iniciado. O seu trabalho guardado e o seu histórico continuam disponíveis.",
    aiProviderUnavailable: "O serviço de IA não conseguiu concluir este pedido neste momento. Nada se perdeu e nada foi iniciado duas vezes. Tente novamente dentro de instantes.",
  },
  providerMode: {
    label: "Modo de IA",
    live: "IA: em direto",
    offline: "IA: modo de teste offline",
    notConfigured: "IA: não configurada",
    unknown: "IA: estado desconhecido",
    liveHint: "Está configurado um fornecedor de IA em direto para este ambiente. É uma configuração, não uma verificação de funcionamento.",
    offlineHint: "Aqui não é usada IA em direto. As respostas vêm de dados de teste e não são coaching real.",
    notConfiguredHint: "As funcionalidades de IA não estão configuradas neste ambiente, por isso o Mo e a prática não podem funcionar.",
    unknownHint: "O Ask4Mo não conseguiu confirmar o modo de IA deste ambiente.",
  },
  recentRuns: {
    title: "A sua preparação recente com o Mo",
    hint: "Só são listadas as suas próprias sessões. Abra uma para continuar onde ficou.",
    empty: "Ainda não se preparou com o Mo.",
    open: "Abrir",
    started: "Iniciada em {date}",
    stateStarted: "Em curso",
    stateReady: "Pronta",
    stateFailed: "Não concluída",
    loadError: "Não foi possível carregar as suas sessões recentes.",
  },
  betaPricing: {
    statement: "O Ask4Mo é uma beta privada gratuita, apenas por convite. Não é possível comprar nada e não se aplica nenhum preço.",
    freeInBeta: "Grátis durante a beta",
    planNote: "Os planos descrevem o que uma conta beta pode usar. Nada aqui está à venda.",
  },
};

export default pt;
