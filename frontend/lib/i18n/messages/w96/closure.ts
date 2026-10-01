// P10B-W9.7A localization closure fragment (all eight locales).
//
// Strings found by direct visual QA of the running product that the W9.6 scanner could not see:
//   - home.feat*        : the four authenticated-Home feature blocks (a string-tuple array in app/app/page.tsx)
//   - practice.questionProgress, prepare.evidenceSources*/sourceUntitled/sourcesAria, marketing.lastUpdated :
//                         text MIXED with `{}` expressions in JSX
//   - coach.insufficientEvidence : the first-person insufficient-evidence note rendered in Mo's reply
//                         bubble. It is Mo-voiced deterministic text, so it follows the Mo CONVERSATION
//                         language (not the interface language); every other key here is UI chrome and
//                         follows the INTERFACE language.
// The protected slogan is not part of this fragment (it is BRAND_SLOGAN, never translated).

const en = {
  home: {
    feat1Title: "Prepare with evidence",
    feat1Body: "Grounded career information and citations when needed.",
    feat2Title: "Practise with purpose",
    feat2Body: "Tailored questions based on the role and your preparation context.",
    feat3Title: "Stay in control",
    feat3Body: "Memory and important handoffs require clear approval.",
    feat4Title: "Improve over time",
    feat4Body: "Structured feedback, progress and reusable preparation context.",
  },
  practice: { questionProgress: "Question {current} of {total}" },
  prepare: {
    evidenceSourcesOne: "Career evidence: 1 source",
    evidenceSourcesOther: "Career evidence: {n} sources",
    sourceUntitled: "Source",
    sourcesAria: "Sources: {names}",
  },
  marketing: { lastUpdated: "Last updated: {date} · Engineering draft" },
  coach: {
    insufficientEvidence:
      "I don’t have enough reliable evidence to answer that confidently. Adding a job description or more about the role can help.",
  },
};

type Closure = { [N in keyof typeof en]: { [K in keyof (typeof en)[N]]: string } };

const de: Closure = {
  home: {
    feat1Title: "Mit Belegen vorbereiten",
    feat1Body: "Fundierte Karriereinformationen und Quellenangaben, wenn nötig.",
    feat2Title: "Gezielt üben",
    feat2Body: "Maßgeschneiderte Fragen auf Basis der Stelle und Ihres Vorbereitungskontexts.",
    feat3Title: "Die Kontrolle behalten",
    feat3Body: "Memory und wichtige Übergaben erfordern Ihre ausdrückliche Freigabe.",
    feat4Title: "Mit der Zeit besser werden",
    feat4Body: "Strukturiertes Feedback, Fortschritt und wiederverwendbarer Vorbereitungskontext.",
  },
  practice: { questionProgress: "Frage {current} von {total}" },
  prepare: {
    evidenceSourcesOne: "Karrierenachweise: 1 Quelle",
    evidenceSourcesOther: "Karrierenachweise: {n} Quellen",
    sourceUntitled: "Quelle",
    sourcesAria: "Quellen: {names}",
  },
  marketing: { lastUpdated: "Zuletzt aktualisiert: {date} · Technischer Entwurf" },
  coach: {
    insufficientEvidence:
      "Ich habe nicht genügend verlässliche Belege, um das sicher zu beantworten. Eine Stellenbeschreibung oder mehr Informationen zur Stelle können helfen.",
  },
};

const fr: Closure = {
  home: {
    feat1Title: "Se préparer avec des preuves",
    feat1Body: "Des informations de carrière fondées et des citations lorsque c’est utile.",
    feat2Title: "S’entraîner avec méthode",
    feat2Body: "Des questions adaptées au poste et à votre contexte de préparation.",
    feat3Title: "Garder le contrôle",
    feat3Body: "La mémoire et les transferts importants nécessitent une approbation claire.",
    feat4Title: "S’améliorer avec le temps",
    feat4Body: "Retours structurés, progression et contexte de préparation réutilisable.",
  },
  practice: { questionProgress: "Question {current} sur {total}" },
  prepare: {
    evidenceSourcesOne: "Preuves de carrière: 1 source",
    evidenceSourcesOther: "Preuves de carrière: {n} sources",
    sourceUntitled: "Source",
    sourcesAria: "Sources: {names}",
  },
  marketing: { lastUpdated: "Dernière mise à jour: {date} · Brouillon technique" },
  coach: {
    insufficientEvidence:
      "Je n’ai pas assez de preuves fiables pour y répondre avec assurance. Ajouter une description de poste ou plus de détails sur le poste peut aider.",
  },
};

const es: Closure = {
  home: {
    feat1Title: "Prepárate con evidencia",
    feat1Body: "Información profesional fundamentada y citas cuando hacen falta.",
    feat2Title: "Practica con propósito",
    feat2Body: "Preguntas a medida según el puesto y tu contexto de preparación.",
    feat3Title: "Mantén el control",
    feat3Body: "La memoria y los traspasos importantes requieren una aprobación clara.",
    feat4Title: "Mejora con el tiempo",
    feat4Body: "Feedback estructurado, progreso y contexto de preparación reutilizable.",
  },
  practice: { questionProgress: "Pregunta {current} de {total}" },
  prepare: {
    evidenceSourcesOne: "Evidencia profesional: 1 fuente",
    evidenceSourcesOther: "Evidencia profesional: {n} fuentes",
    sourceUntitled: "Fuente",
    sourcesAria: "Fuentes: {names}",
  },
  marketing: { lastUpdated: "Última actualización: {date} · Borrador técnico" },
  coach: {
    insufficientEvidence:
      "No tengo evidencia fiable suficiente para responder con seguridad. Añadir una descripción del puesto o más información sobre el puesto puede ayudar.",
  },
};

const it: Closure = {
  home: {
    feat1Title: "Preparati con le prove",
    feat1Body: "Informazioni di carriera fondate e citazioni quando servono.",
    feat2Title: "Esercitati con metodo",
    feat2Body: "Domande su misura in base al ruolo e al tuo contesto di preparazione.",
    feat3Title: "Mantieni il controllo",
    feat3Body: "La memoria e i passaggi importanti richiedono un’approvazione chiara.",
    feat4Title: "Migliora nel tempo",
    feat4Body: "Feedback strutturato, progressi e contesto di preparazione riutilizzabile.",
  },
  practice: { questionProgress: "Domanda {current} di {total}" },
  prepare: {
    evidenceSourcesOne: "Evidenze di carriera: 1 fonte",
    evidenceSourcesOther: "Evidenze di carriera: {n} fonti",
    sourceUntitled: "Fonte",
    sourcesAria: "Fonti: {names}",
  },
  marketing: { lastUpdated: "Ultimo aggiornamento: {date} · Bozza tecnica" },
  coach: {
    insufficientEvidence:
      "Non ho prove affidabili sufficienti per rispondere con sicurezza. Aggiungere una descrizione del ruolo o più informazioni sul ruolo può aiutare.",
  },
};

const pt: Closure = {
  home: {
    feat1Title: "Prepare-se com evidências",
    feat1Body: "Informação de carreira fundamentada e citações quando necessário.",
    feat2Title: "Pratique com propósito",
    feat2Body: "Perguntas à medida da função e do seu contexto de preparação.",
    feat3Title: "Mantenha o controlo",
    feat3Body: "A memória e as transferências importantes exigem aprovação clara.",
    feat4Title: "Melhore ao longo do tempo",
    feat4Body: "Feedback estruturado, progresso e contexto de preparação reutilizável.",
  },
  practice: { questionProgress: "Pergunta {current} de {total}" },
  prepare: {
    evidenceSourcesOne: "Evidências de carreira: 1 fonte",
    evidenceSourcesOther: "Evidências de carreira: {n} fontes",
    sourceUntitled: "Fonte",
    sourcesAria: "Fontes: {names}",
  },
  marketing: { lastUpdated: "Última atualização: {date} · Rascunho técnico" },
  coach: {
    insufficientEvidence:
      "Não tenho evidências fiáveis suficientes para responder com segurança. Adicionar uma descrição da função ou mais informações sobre a função pode ajudar.",
  },
};

const nl: Closure = {
  home: {
    feat1Title: "Bereid u voor met bewijs",
    feat1Body: "Onderbouwde loopbaaninformatie en bronvermeldingen wanneer nodig.",
    feat2Title: "Oefen met een doel",
    feat2Body: "Vragen op maat van de functie en uw voorbereidingscontext.",
    feat3Title: "Houd de controle",
    feat3Body: "Geheugen en belangrijke overdrachten vereisen duidelijke goedkeuring.",
    feat4Title: "Verbeter in de loop van de tijd",
    feat4Body: "Gestructureerde feedback, voortgang en herbruikbare voorbereidingscontext.",
  },
  practice: { questionProgress: "Vraag {current} van {total}" },
  prepare: {
    evidenceSourcesOne: "Loopbaanonderbouwing: 1 bron",
    evidenceSourcesOther: "Loopbaanonderbouwing: {n} bronnen",
    sourceUntitled: "Bron",
    sourcesAria: "Bronnen: {names}",
  },
  marketing: { lastUpdated: "Laatst bijgewerkt: {date} · Technisch concept" },
  coach: {
    insufficientEvidence:
      "Ik heb onvoldoende betrouwbaar bewijs om dit met vertrouwen te beantwoorden. Een functieomschrijving of meer informatie over de functie kan helpen.",
  },
};

const ru: Closure = {
  home: {
    feat1Title: "Подготовка с опорой на подтверждения",
    feat1Body: "Обоснованная карьерная информация и ссылки на источники, когда они нужны.",
    feat2Title: "Тренировка с целью",
    feat2Body: "Вопросы, подобранные под должность и ваш контекст подготовки.",
    feat3Title: "Контроль остаётся за вами",
    feat3Body: "Память и важные передачи требуют вашего явного одобрения.",
    feat4Title: "Рост со временем",
    feat4Body: "Структурированная обратная связь, прогресс и повторно используемый контекст подготовки.",
  },
  practice: { questionProgress: "Вопрос {current} из {total}" },
  prepare: {
    evidenceSourcesOne: "Подтверждения опыта: 1 источник",
    evidenceSourcesOther: "Подтверждения опыта, источников: {n}",
    sourceUntitled: "Источник",
    sourcesAria: "Источники: {names}",
  },
  marketing: { lastUpdated: "Последнее обновление: {date} · Технический черновик" },
  coach: {
    insufficientEvidence:
      "У меня недостаточно надёжных подтверждений, чтобы уверенно на это ответить. Поможет описание вакансии или больше сведений о должности.",
  },
};

const closure = { en, de, fr, es, it, pt, nl, ru };
export default closure;
