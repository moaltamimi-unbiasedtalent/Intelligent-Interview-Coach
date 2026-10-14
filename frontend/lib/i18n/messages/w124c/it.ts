import type en from "./en";

const it: typeof en = {
  auth: {
    verifyLinkExpired: "Questo link di verifica è scaduto. Accedi e richiedine uno nuovo dalla pagina del tuo account.",
    verifyLinkUsed: "Questo link di verifica è già stato usato. Se la tua email è verificata, puoi accedere.",
    resetLinkExpired: "Questo link di reimpostazione è scaduto. Richiedine uno nuovo.",
    resetLinkUsed: "Questo link di reimpostazione è già stato usato. Se devi ancora reimpostare la password, richiedi un nuovo link.",
    resendCooldown: "Un link è stato appena inviato. Attendi un minuto prima di richiederne un altro.",
    emailUnavailable: "Non siamo riusciti a inviare l'email in questo momento. Riprova più tardi.",
    resendSent: "Se la tua email non è verificata, ti abbiamo inviato un nuovo link.",
    registerSent: "Se questa email può essere registrata, abbiamo inviato un link di verifica. Controlla la posta in arrivo, poi accedi.",
    forgotSent: "Se esiste un account per questa email, abbiamo inviato un link per reimpostare la password.",
  },
};

export default it;
