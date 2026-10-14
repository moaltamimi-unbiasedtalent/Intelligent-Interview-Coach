import type en from "./en";

const es: typeof en = {
  auth: {
    verifyLinkExpired: "Este enlace de verificación ha caducado. Inicia sesión y solicita uno nuevo desde la página de tu cuenta.",
    verifyLinkUsed: "Este enlace de verificación ya se usó. Si tu correo está verificado, puedes iniciar sesión.",
    resetLinkExpired: "Este enlace de restablecimiento ha caducado. Solicita uno nuevo.",
    resetLinkUsed: "Este enlace de restablecimiento ya se usó. Si aún necesitas restablecer tu contraseña, solicita un nuevo enlace.",
    resendCooldown: "Se acaba de enviar un enlace. Espera un minuto antes de pedir otro.",
    emailUnavailable: "No pudimos enviar el correo en este momento. Inténtalo de nuevo más tarde.",
    resendSent: "Si tu correo no está verificado, te hemos enviado un nuevo enlace.",
    registerSent: "Si ese correo se puede registrar, hemos enviado un enlace de verificación. Revisa tu bandeja de entrada y luego inicia sesión.",
    forgotSent: "Si existe una cuenta para ese correo, hemos enviado un enlace para restablecer la contraseña.",
  },
};

export default es;
