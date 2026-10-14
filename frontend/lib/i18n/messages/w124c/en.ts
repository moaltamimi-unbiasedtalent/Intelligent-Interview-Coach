// W12.4C identity-email states (English source of truth). Merged additively into the `auth` namespace.
// The protected slogan is not part of this file.

const en = {
  auth: {
    verifyLinkExpired: "This verification link has expired. Sign in and request a new one from your account page.",
    verifyLinkUsed: "This verification link was already used. If your email is verified, you can sign in.",
    resetLinkExpired: "This reset link has expired. Please request a new one.",
    resetLinkUsed: "This reset link was already used. If you still need to reset your password, request a new link.",
    resendCooldown: "A link was just sent. Please wait a minute before asking for another.",
    emailUnavailable: "We could not send the email right now. Please try again later.",
    resendSent: "If your email is unverified, we've sent a new link.",
    registerSent: "If that email can be registered, we've sent a verification link. Please check your inbox, then sign in.",
    forgotSent: "If an account exists for that email, we've sent a password-reset link.",
  },
};

export default en;
