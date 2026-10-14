import type en from "./en";

const de: typeof en = {
  auth: {
    verifyLinkExpired: "Dieser Bestätigungslink ist abgelaufen. Melde dich an und fordere auf deiner Kontoseite einen neuen an.",
    verifyLinkUsed: "Dieser Bestätigungslink wurde bereits verwendet. Wenn deine E-Mail bestätigt ist, kannst du dich anmelden.",
    resetLinkExpired: "Dieser Link zum Zurücksetzen ist abgelaufen. Bitte fordere einen neuen an.",
    resetLinkUsed: "Dieser Link zum Zurücksetzen wurde bereits verwendet. Wenn du dein Passwort noch zurücksetzen musst, fordere einen neuen Link an.",
    resendCooldown: "Ein Link wurde gerade gesendet. Bitte warte eine Minute, bevor du einen weiteren anforderst.",
    emailUnavailable: "Wir konnten die E-Mail gerade nicht senden. Bitte versuche es später erneut.",
    resendSent: "Wenn deine E-Mail-Adresse unbestätigt ist, haben wir einen neuen Link gesendet.",
    registerSent: "Wenn diese E-Mail-Adresse registriert werden kann, haben wir einen Bestätigungslink gesendet. Bitte prüfe dein Postfach und melde dich dann an.",
    forgotSent: "Wenn für diese E-Mail-Adresse ein Konto existiert, haben wir einen Link zum Zurücksetzen des Passworts gesendet.",
  },
};

export default de;
