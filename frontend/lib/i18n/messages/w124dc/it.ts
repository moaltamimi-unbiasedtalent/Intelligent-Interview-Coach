import type en from "./en";

const it: typeof en = {
  checkout: {
    title: "Abbonamento Premium",
    unavailable: "Il pagamento non è ancora aperto. Premium è un'anteprima senza prezzo approvato, quindi oggi non si può acquistare nulla.",
    signInRequired: "Accedi per continuare. Il pagamento parte sempre dal tuo account.",
    selectPlan: "Premium è selezionato. Concluderai su una pagina sicura del nostro partner di pagamento.",
    start: "Continua al pagamento sicuro",
    preparing: "Preparazione del pagamento sicuro…",
    redirecting: "Reindirizzamento al pagamento sicuro…",
    pendingTitle: "Attendiamo la conferma",
    pendingBody: "Sei tornato dal pagamento. Il tuo piano non è ancora cambiato. L'accesso cambia solo dopo la conferma dell'abbonamento da parte del nostro partner di pagamento, che può richiedere un po' di tempo.",
    canceledTitle: "Pagamento annullato",
    canceledBody: "Hai annullato il pagamento. Non è stato addebitato nulla e il tuo piano non è cambiato.",
    expired: "Questo pagamento è scaduto. Non è stato addebitato nulla. Puoi iniziarne uno nuovo.",
    providerUnavailable: "Il fornitore di pagamenti non ha potuto avviare il pagamento. Non è stato addebitato nulla. Riprova più tardi.",
    statusUnavailable: "Al momento non riusciamo a caricare lo stato del pagamento.",
    retry: "Riprova",
    sellerNote: "Il nostro partner di pagamento è il venditore degli abbonamenti a pagamento e invia ricevute ed e-mail di pagamento.",
    manageNote: "Gestisci un abbonamento a pagamento con quel partner. Ask4Mo non conserva i dati della carta.",
    noInvoices: "Qui non vengono mostrate fatture o ricevute perché Ask4Mo non ne ha emesse.",
    returnTitle: "Stato del pagamento",
    backToAccount: "Torna al tuo account",
    stillChecking: "Verifica in corso…",
    confirmedTitle: "Abbonamento Premium confermato",
    confirmedBody: "Il nostro partner di pagamento ha confermato il tuo abbonamento e il tuo piano è stato aggiornato.",
    confirmedNoAccessTitle: "Abbonamento confermato dal nostro partner di pagamento",
    confirmedNoAccessBody: "Il tuo piano non è ancora cambiato. L'accesso viene aggiornato solo quando le regole dei piani a pagamento sono in vigore.",
    pastDueTitle: "Il pagamento richiede attenzione",
    pastDueBody: "Il nostro partner di pagamento non ha potuto incassare l'ultimo pagamento. Gestisci un abbonamento a pagamento con quel partner.",
    cancelScheduledTitle: "Cancellazione programmata",
    cancelScheduledBody: "Il tuo abbonamento terminerà alla fine del periodo corrente. Non è ancora terminato nulla.",
    endedTitle: "Abbonamento terminato",
    endedBody: "Il tuo abbonamento a pagamento è terminato. Le funzioni gratuite restano disponibili.",
  },
};

export default it;
