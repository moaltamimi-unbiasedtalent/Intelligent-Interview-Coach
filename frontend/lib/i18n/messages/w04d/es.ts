import type en from "./en";

const es: typeof en = {
  states: {
    aiNotConfigured: "Las funciones de IA no están configuradas en este entorno de Ask4Mo, así que no se inició nada. Tu trabajo guardado y tu historial siguen disponibles.",
    aiProviderUnavailable: "El servicio de IA no pudo completar esta solicitud en este momento. No se perdió nada y nada se inició dos veces. Inténtalo de nuevo en un momento.",
  },
  providerMode: {
    label: "Modo de IA",
    live: "IA: en vivo",
    offline: "IA: modo de prueba sin conexión",
    notConfigured: "IA: no configurada",
    unknown: "IA: estado desconocido",
    liveHint: "Hay un proveedor de IA en vivo configurado para este entorno. Es una configuración, no una comprobación de estado.",
    offlineHint: "Aquí no se usa IA en vivo. Las respuestas proceden de datos de prueba y no son coaching real.",
    notConfiguredHint: "Las funciones de IA no están configuradas en este entorno, así que Mo y la práctica no pueden funcionar.",
    unknownHint: "Ask4Mo no pudo confirmar el modo de IA de este entorno.",
  },
  recentRuns: {
    title: "Tu preparación reciente con Mo",
    hint: "Solo se muestran tus propias sesiones. Abre una para continuar donde lo dejaste.",
    empty: "Todavía no te has preparado con Mo.",
    open: "Abrir",
    started: "Iniciada el {date}",
    stateStarted: "En curso",
    stateReady: "Lista",
    stateFailed: "No se completó",
    loadError: "No se pudieron cargar tus sesiones recientes.",
  },
  betaPricing: {
    statement: "Ask4Mo es una beta privada gratuita, solo por invitación. No se puede comprar nada y no se aplica ningún precio.",
    freeInBeta: "Gratis durante la beta",
    planNote: "Los planes describen lo que puede usar una cuenta beta. Nada aquí está a la venta.",
  },
};

export default es;
