import type en from "./en";

const nl: typeof en = {
  auth: {
    verifyLinkExpired: "Deze verificatielink is verlopen. Log in en vraag een nieuwe aan via je accountpagina.",
    verifyLinkUsed: "Deze verificatielink is al gebruikt. Als je e-mailadres is geverifieerd, kun je inloggen.",
    resetLinkExpired: "Deze resetlink is verlopen. Vraag een nieuwe aan.",
    resetLinkUsed: "Deze resetlink is al gebruikt. Moet je je wachtwoord nog resetten, vraag dan een nieuwe link aan.",
    resendCooldown: "Er is zojuist een link verstuurd. Wacht een minuut voordat je een nieuwe aanvraagt.",
    emailUnavailable: "We konden de e-mail nu niet versturen. Probeer het later opnieuw.",
    resendSent: "Als je e-mailadres niet is geverifieerd, hebben we een nieuwe link gestuurd.",
    registerSent: "Als dit e-mailadres kan worden geregistreerd, hebben we een verificatielink gestuurd. Controleer je inbox en log daarna in.",
    forgotSent: "Als er een account bestaat voor dit e-mailadres, hebben we een link voor het resetten van je wachtwoord gestuurd.",
  },
};

export default nl;
