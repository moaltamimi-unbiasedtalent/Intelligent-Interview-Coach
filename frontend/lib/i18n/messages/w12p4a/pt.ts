import type en from "./en";

const pt: typeof en = {
  states: {
    usageQuotaExhausted: "Utilizou a quota de IA incluída para este período. O seu trabalho guardado e o seu histórico continuam disponíveis. Voltará a estar disponível quando o período for reiniciado.",
  },
  quotaUx: {
    title: "Quota de utilização",
    lead: "A quota apresentada aqui é calculada pelo Ask4Mo para a sua conta e o período atual.",
    f_practice_session: "Sessões de prática de entrevista",
    f_career_ai: "Pedidos de coaching com IA",
    st_available: "Disponível",
    st_exhausted: "Esgotada por agora",
    st_not_configured: "Ainda não configurada",
    st_unavailable: "Temporariamente indisponível",
    used: "Utilizado",
    remaining: "Restante",
    resets: "Reinicia",
    per_hour: "por hora",
    per_day: "por dia",
    per_month: "por mês",
    notConfigured: "Ainda não foi configurada nenhuma quota para esta funcionalidade.",
    exhaustedNote: "Esta quota é reiniciada à hora indicada. O seu trabalho guardado e o seu histórico continuam disponíveis.",
  },
};

export default pt;
