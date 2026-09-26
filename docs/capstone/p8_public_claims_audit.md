# P8 Public Claims Audit

_Every significant public/marketing claim checked against the actual implementation. Public
copy must follow this audit. Classification: SUPPORTED / SUPPORTED WITH LIMITATION /
UNVALIDATED / DO NOT CLAIM._

| Claim | Classification | Basis / limitation |
|---|---|---|
| Interview preparation & practice | **SUPPORTED** | Prepare + Interview Practice delivered (P1–P7), full lifecycle with evaluation, history, progress. |
| Grounded answers with sources | **SUPPORTED** | RAG with citations; abstention when evidence is missing (P6). Copy says "sources you can check", not "always correct". |
| Private documents & Story Bank | **SUPPORTED** | P4 private storage (opaque keys, auth-mediated, attachment-only), claims + Story Bank. |
| Private by default / explicit sharing | **SUPPORTED** | Owner-scoped data; workspace sharing is explicit, view-only (P6.5). Verified by security tests. |
| Candidate-controlled Memory | **SUPPORTED** | Memory HITL approval; edit/delete (P6/P7). |
| Seven-language product experience | **SUPPORTED WITH LIMITATION** | UI + voice across 7 locales; translations are ENGINEERING DRAFT (no human/legal review). Say "in your language", not "professionally translated". |
| Multilingual **turn-based** voice | **SUPPORTED** | P7: Listen/Speak in 7 languages; browser/OS-dependent availability. |
| **Realtime** voice | **SUPPORTED WITH LIMITATION** | P7.5 architecture delivered + deterministically validated; **LIVE NOT RUN**. Public copy must say "available where configured", never "fully live realtime in all languages". |
| Voice privacy (no trait inference, no audio storage) | **SUPPORTED** | No emotion/accent/confidence/hiring inference; Ask4Mo stores no audio (P7/P7.5). Realtime provider processing disclosed honestly. |
| No hiring decisions / no recruiter ranking | **SUPPORTED** | Not built; explicitly out of scope. |
| Career knowledge (compensation/credentials/roles) | **SUPPORTED WITH LIMITATION** | K1–K4 datasets shipped with abstention; figures are engineering-draft, K4 live UNVALIDATED. Do not present figures as authoritative. |
| OCR for documents | **SUPPORTED WITH LIMITATION** | Optional OCR (pytesseract) with content validation; live quality UNVALIDATED; not claimed as perfect. |
| Malware scanning of uploads | **SUPPORTED WITH LIMITATION** | Scanner abstraction + fail-closed policy; a real scanner (ClamAV) is configured per deployment. Never display "virus-free" unless a real scan ran. |
| Premium plan | **SUPPORTED WITH LIMITATION** | Pricing PRESENTATION only. **DO NOT** imply online purchase — no billing/checkout exists; CTA is a truthful preview request. |
| Export & delete my data | **SUPPORTED** | Export endpoint + full application-controlled deletion cascade (P8). Backups age out per provider retention (disclosed). |
| Hosted / HTTPS / open registration | **UNVALIDATED** | Deployment artifacts + env validation READY; EX-12 requires an authorized deployment (NOT RUN). Do not claim "live in production". |
| Google sign-in | **UNVALIDATED** | Implemented; disables cleanly when unconfigured; live sign-in NOT RUN. |
| "Guarantees a job / interview success" | **DO NOT CLAIM** | Never claim outcomes. |
| "100% accurate / bias-free" | **DO NOT CLAIM** | AI can be wrong; no bias guarantee. |
| "GDPR certified / compliant" | **DO NOT CLAIM** | Policies are engineering drafts pending legal review; no certification. |
| Certification badges | **DO NOT CLAIM** | None held. |

**Applied in copy:** the marketing site uses "available where configured" for realtime, "in
your language" (not "professionally translated"), "engineering draft — pending legal review"
banners on Privacy/Terms/AI-transparency, and a truthful Premium "preview / request access"
CTA with an explicit "no online payments" note. The home hero avoids outcome guarantees.
