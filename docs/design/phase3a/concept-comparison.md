# Concept Comparison & Recommendation

Four **genuinely different** directions (not recolours). Scores are 1–5, judged
honestly for the target user (a candidate preparing for a professional/management/
executive interview). Totals are a guide, not the decision — trade-offs matter
more, and the **user makes the final call**.

## The four directions

| # | Name | Influence | Essence | Implementation |
|---|------|-----------|---------|----------------|
| A | Quiet Intelligence | Apple | Editorial restraint; one moment per screen | LOW–MEDIUM |
| B | Coach Workspace | heyCoach + Lovable | A present coach; conversation + live rail | MEDIUM–HIGH |
| C | Guided Journey | Canva | Stage-based; always "what's next" | MEDIUM |
| D | Precision Coach | Hybrid | Premium shell + conversational prep + disclosure | MEDIUM–HIGH |

## Scorecard

| Criterion | A | B | C | D |
|-----------|:-:|:-:|:-:|:-:|
| Premium feel | 5 | 4 | 3 | 5 |
| Trust | 4 | 4 | 4 | 5 |
| Coaching feel | 3 | 5 | 3 | 4 |
| Ease of use | 4 | 4 | 5 | 4 |
| Clarity | 4 | 4 | 5 | 4 |
| Interview-anxiety reduction | 4 | 4 | 5 | 4 |
| Agent-interaction suitability | 3 | 5 | 3 | 5 |
| Information density (appropriate) | 3 | 4 | 3 | 5 |
| Mobile usability | 4 | 3 | 4 | 4 |
| Executive-audience suitability | 5 | 3 | 3 | 5 |
| Distinctiveness | 4 | 4 | 3 | 4 |
| Generic-AI-look resistance | 5 | 3 | 4 | 4 |
| **Total (of 60)** | **48** | **47** | **46** | **53** |

Scores are close on purpose — every direction is viable. The spread is in
*where* each is strong.

## Trade-offs

**A — Quiet Intelligence.** The most premium and the most resistant to looking
"AI-generated"; superb for an executive audience. Its risk is the stated one: the
restraint can **hide too much** — gaps, priorities and the coach's help are
understated, which may under-serve an anxious, time-pressed candidate who wants
explicit next steps. Best if we're confident the content can stay minimal.

**B — Coach Workspace.** The warmest and by far the best *coaching feel* and
*agent-interaction* surface — the live context rail is a genuinely good pattern for
an agentic product. Two risks: it can drift toward **chat-centric / generic-AI**
if not carefully framed, and the conversation-plus-rail layout is the **hardest to
collapse well on mobile**. Slightly less "executive-formal".

**C — Guided Journey.** The easiest and clearest; the visible stage model is the
strongest at **reducing interview anxiety** because the user always knows what's
next. Its cost is **premium/executive feel** — more chrome and colour read as less
senior, and it's the least distinctive. Excellent for first-time or nervous users.

**D — Precision Coach.** Deliberately combines A's restraint + executive premium,
B's coaching/agent surface, C's progressive disclosure, and Lovable's plain-
language interaction. It scores highest because it balances *premium + trust +
agent-suitability + appropriate density* without a glaring weakness. Its risk is
**implementation effort** (a conversational workspace with a contextual rail and
strong disclosure is more to build and to make accessible than A or C).

## Implementation implications (§29)

| | A | B | C | D |
|---|---|---|---|---|
| Overall complexity | LOW–MED | MED–HIGH | MED | MED–HIGH |
| Responsive complexity | Low | High (rail→sheet) | Medium | Medium–High |
| Motion complexity | Low | Medium | Medium | Low–Medium |
| Component complexity | Low | High | Medium | Medium–High |
| Accessibility risk | Low | Medium (live region) | Low | Medium |

All four translate cleanly to **Next.js + TypeScript + Tailwind** with accessible
primitives (e.g. Radix/Headless UI). B and D need care: a polite ARIA live region
for coach/agent activity, and a `Sheet`/`Drawer` for the mobile context rail. The
provisional tokens in `design-tokens.md` map directly to a Tailwind theme.

## DESIGN-TEAM RECOMMENDATION — not a final selection

**Recommend Concept D — Precision Coach.**

Why: it fits the target user (senior candidates who want a premium, trustworthy,
low-noise experience) *and* the product's direction (an agentic coach where the
conversation and a contextual preparation panel are first-class), while keeping
technical execution out of the candidate's way. It has no severe weakness on any
criterion.

**Borrow from the others as we build D:**
- From **A** — the discipline of *one dominant action per screen* and the
  shadowless, hairline restraint on the marketing/Home and Practice screens.
- From **B** — the *present-coach* tone and the *live context rail* pattern for
  the preparation workspace (this is the heart of the agent experience).
- From **C** — a lightweight *stage/progress* cue so users always sense where they
  are, without adopting C's heavier chrome.

**Explicitly avoid:**
- Letting D drift chat-centric (keep the rail and next-actions co-equal with the
  conversation — B's risk).
- Over-restraint that hides gaps/priorities (A's risk) — priorities stay visible.
- Decorative colour/AI clichés; any "Thinking…"/reasoning exposure; diagnostics
  leaking into the candidate flow.

**If the user prefers a different balance:** choose **A** for a maximally premium,
minimal-effort build; **C** for the most reassuring, easiest onboarding; **B** if
the coaching relationship should be the product's headline.

The final decision is the user's.
