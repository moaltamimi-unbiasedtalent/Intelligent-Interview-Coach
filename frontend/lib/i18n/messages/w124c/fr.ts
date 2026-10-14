import type en from "./en";

const fr: typeof en = {
  auth: {
    verifyLinkExpired: "Ce lien de vérification a expiré. Connectez-vous et demandez-en un nouveau depuis la page de votre compte.",
    verifyLinkUsed: "Ce lien de vérification a déjà été utilisé. Si votre adresse e-mail est vérifiée, vous pouvez vous connecter.",
    resetLinkExpired: "Ce lien de réinitialisation a expiré. Veuillez en demander un nouveau.",
    resetLinkUsed: "Ce lien de réinitialisation a déjà été utilisé. Si vous devez encore réinitialiser votre mot de passe, demandez un nouveau lien.",
    resendCooldown: "Un lien vient d'être envoyé. Veuillez patienter une minute avant d'en demander un autre.",
    emailUnavailable: "Nous n'avons pas pu envoyer l'e-mail pour le moment. Veuillez réessayer plus tard.",
    resendSent: "Si votre adresse e-mail n'est pas vérifiée, nous vous avons envoyé un nouveau lien.",
    registerSent: "Si cette adresse e-mail peut être enregistrée, nous avons envoyé un lien de vérification. Consultez votre boîte de réception, puis connectez-vous.",
    forgotSent: "Si un compte existe pour cette adresse e-mail, nous avons envoyé un lien de réinitialisation du mot de passe.",
  },
};

export default fr;
