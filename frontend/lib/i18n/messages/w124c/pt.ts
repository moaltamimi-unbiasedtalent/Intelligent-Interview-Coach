import type en from "./en";

const pt: typeof en = {
  auth: {
    verifyLinkExpired: "Este link de verificação expirou. Inicie sessão e peça um novo na página da sua conta.",
    verifyLinkUsed: "Este link de verificação já foi utilizado. Se o seu e-mail estiver verificado, pode iniciar sessão.",
    resetLinkExpired: "Este link de redefinição expirou. Peça um novo.",
    resetLinkUsed: "Este link de redefinição já foi utilizado. Se ainda precisar de redefinir a palavra-passe, peça um novo link.",
    resendCooldown: "Um link acabou de ser enviado. Aguarde um minuto antes de pedir outro.",
    emailUnavailable: "Não foi possível enviar o e-mail neste momento. Tente novamente mais tarde.",
    resendSent: "Se o seu e-mail não estiver verificado, enviámos um novo link.",
    registerSent: "Se este e-mail puder ser registado, enviámos um link de verificação. Verifique a caixa de entrada e depois inicie sessão.",
    forgotSent: "Se existir uma conta para este e-mail, enviámos um link para redefinir a palavra-passe.",
  },
};

export default pt;
