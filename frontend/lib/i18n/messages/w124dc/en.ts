// W12.4D-C checkout copy (English source of truth). Truthful by construction: no string says payment succeeded, a subscription is active or Premium is unlocked.
// The protected slogan is not part of this file.

const en = {
  checkout: {
    title: "Premium subscription",
    unavailable: "Checkout is not open yet. Premium is a preview and has no approved price, so nothing can be purchased today.",
    signInRequired: "Sign in to continue. Checkout always starts from your own account.",
    selectPlan: "Premium is selected. You will finish on a secure page run by our payment partner.",
    start: "Continue to secure checkout",
    preparing: "Preparing your secure checkout…",
    redirecting: "Redirecting you to the secure checkout…",
    pendingTitle: "We are waiting for confirmation",
    pendingBody: "You came back from checkout. Your plan has not changed yet. Access changes only after our payment partner confirms the subscription, which can take a little while.",
    canceledTitle: "Checkout canceled",
    canceledBody: "You canceled checkout. Nothing was charged and your plan has not changed.",
    expired: "This checkout expired. Nothing was charged. You can start a new one.",
    providerUnavailable: "The payment provider could not start checkout. Nothing was charged. Please try again later.",
    statusUnavailable: "We could not load your checkout status right now.",
    retry: "Try again",
    sellerNote: "Our payment partner is the seller of record for paid subscriptions and sends receipts and payment emails.",
    manageNote: "You manage a paid subscription with that partner. Ask4Mo does not store card details.",
    noInvoices: "No invoices or receipts are shown here because none have been issued by Ask4Mo.",
    returnTitle: "Checkout status",
    backToAccount: "Back to your account",
    stillChecking: "Checking…",
    confirmedTitle: "Premium subscription confirmed",
    confirmedBody: "Our payment partner confirmed your subscription and your plan has been updated.",
    confirmedNoAccessTitle: "Subscription confirmed by our payment partner",
    confirmedNoAccessBody: "Your plan has not changed yet. Access is updated only when the rules for paid plans are in force.",
    pastDueTitle: "Payment needs attention",
    pastDueBody: "Our payment partner could not collect your latest payment. You manage a paid subscription with that partner.",
    cancelScheduledTitle: "Cancellation scheduled",
    cancelScheduledBody: "Your subscription is set to end at the end of the current period. Nothing has ended yet.",
    endedTitle: "Subscription ended",
    endedBody: "Your paid subscription has ended. Free features remain available.",
  },
};

export default en;
