Guidelines to reduce common LLM coding mistakes. Use alongside project-specific instructions.

**Trade-off:** These guidelines prioritize carefulness over speed. Use your judgment for trivial tasks.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Make trade-offs explicit.**

Before implementing:

- State assumptions explicitly. If unsure, ask.
- If multiple interpretations exist, present them — don't pick one silently.
- If a simpler approach exists, say so. Push back if needed.
- If something is unclear, stop. State what's unclear and ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- Don't add features that weren't requested.
- Don't abstract code that's only used once.
- Don't add "flexibility" or "configurability" that wasn't requested.
- Don't add error handling for scenarios that can't occur.
- If you wrote 200 lines but 50 would suffice, rewrite.

Ask yourself: "Would a senior engineer say 'this is over-engineered'?" If so, simplify.

## 3. Surgical Changes

**Change only what's necessary. Clean up only what you created.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor what isn't broken.
- Match the existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

If your changes create orphans:

- Remove imports/variables/functions made unnecessary by your changes.
- Don't remove existing dead code unless asked.

Test: Every changed line should directly relate to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Convert tasks into verifiable goals:

- "Add validation" → "Write tests for invalid input and make them pass"
- "Fix bug" → "Write a reproducing test and make it pass"
- "Refactor X" → "Confirm tests pass before and after the change"

For multi-step tasks, state a concise plan:

```
1. [Step] → Verify: [what to check]
2. [Step] → Verify: [what to check]
3. [Step] → Verify: [what to check]
```

Strong success criteria allow independent looping. Weak criteria ("make it work") always require confirmation.
