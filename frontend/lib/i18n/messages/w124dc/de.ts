import type en from "./en";

const de: typeof en = {
  checkout: {
    title: "Premium-Abo",
    unavailable: "Der Checkout ist noch nicht geöffnet. Premium ist eine Vorschau ohne genehmigten Preis, daher kann heute nichts gekauft werden.",
    signInRequired: "Melde dich an, um fortzufahren. Der Checkout startet immer in deinem eigenen Konto.",
    selectPlan: "Premium ist ausgewählt. Du schließt den Kauf auf einer sicheren Seite unseres Zahlungspartners ab.",
    start: "Weiter zum sicheren Checkout",
    preparing: "Dein sicherer Checkout wird vorbereitet …",
    redirecting: "Du wirst zum sicheren Checkout weitergeleitet …",
    pendingTitle: "Wir warten auf die Bestätigung",
    pendingBody: "Du bist vom Checkout zurückgekehrt. Dein Tarif hat sich noch nicht geändert. Der Zugang ändert sich erst, wenn unser Zahlungspartner das Abo bestätigt, was etwas dauern kann.",
    canceledTitle: "Checkout abgebrochen",
    canceledBody: "Du hast den Checkout abgebrochen. Es wurde nichts berechnet und dein Tarif hat sich nicht geändert.",
    expired: "Dieser Checkout ist abgelaufen. Es wurde nichts berechnet. Du kannst einen neuen starten.",
    providerUnavailable: "Der Zahlungsanbieter konnte den Checkout nicht starten. Es wurde nichts berechnet. Bitte versuche es später erneut.",
    statusUnavailable: "Dein Checkout-Status konnte gerade nicht geladen werden.",
    retry: "Erneut versuchen",
    sellerNote: "Unser Zahlungspartner ist der Verkäufer bezahlter Abos und sendet Belege und Zahlungs-E-Mails.",
    manageNote: "Ein bezahltes Abo verwaltest du bei diesem Partner. Ask4Mo speichert keine Kartendaten.",
    noInvoices: "Hier werden keine Rechnungen oder Belege angezeigt, da Ask4Mo keine ausgestellt hat.",
    returnTitle: "Checkout-Status",
    backToAccount: "Zurück zu deinem Konto",
    stillChecking: "Wird geprüft …",
  },
};

export default de;
