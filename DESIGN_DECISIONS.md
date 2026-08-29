# Design Decisions — CareRoute AI

## 1. Why Gemini
Gemini handles the one thing LLMs are genuinely good at here: turning messy,
free-text patient requests into structured operational information
(summary, signals, missing information). It never touches the final
routing decision.

## 2. Why structured output (Pydantic)
Gemini's JSON is validated against `IntakeAnalysis` before anything
downstream sees it. A malformed or incomplete response fails loudly
(`LLMError`) instead of silently corrupting a routing decision.

## 3. Why deterministic routing rules
The queue a request lands in is a policy decision, not a language
understanding decision. `data/routing_policy.json` is plain, ordered
AND/ANY rules over a fixed signal vocabulary — auditable and editable by
non-engineers without touching a prompt or a model.

## 4. Why the LLM does not choose the final queue
Keeping "understand" and "decide" as separate steps means the routing
logic is inspectable, testable, and stable even if the model's phrasing
varies between calls. It also means a hallucinated or injected instruction
in patient text cannot directly set the outcome — it can only, at most,
distort the extracted signals, which the policy engine then evaluates the
same way it evaluates any other signal set.

## 5. Why uncertainty detection matters
`information_sufficient` and `missing_information` let the system say "I
don't know yet" instead of guessing. A request with no real content (e.g.
"I need an appointment") is sent back to the patient rather than being
force-routed on invented assumptions.

## 6. Why evidence-linked recommendations
Every recommendation on the doctor's review screen shows the triggered
rule ID, its plain-language description, and the extracted signals/quotes
behind it. This is the difference between "the AI says it's urgent" and
"policy U-03 matched because the request contains recent_injury and
functional_difficulty" — the latter is checkable by a human in seconds.

## 7. Why human approval is mandatory
CareRoute AI is an intake and routing *assistant*. Every request — however
confident the AI recommendation — sits in a doctor/staff queue until a
human approves, modifies, requests clarification, or escalates it. No
appointment is created and no patient is notified without that step.

## 8. Why synthetic data
No real patient data is used anywhere in the prototype. All patients,
histories, and evaluation requests are fabricated for demonstration.

## 9. Why SQLite
Zero setup, a schema simple enough to explain to judges in one slide, and
more than sufficient for a single-process demo.

## 10. Why we intentionally did not use fine-tuning, Qwen, LoRA, QLoRA,
vector databases, or agent frameworks
We intentionally chose an API-based LLM with structured extraction and
explicit policy rules rather than fine-tuning because the prototype has a
small, changing policy set and requires transparent, human-auditable
routing behavior. A vector database implies a retrieval problem we don't
have (there's no corpus to search — each request is judged against a
~15-rule policy file). Agent frameworks add planning/tool-orchestration
overhead for what is, structurally, a single-turn extract-then-route
pipeline. None of this is a claim that CareRoute's approach is novel in
the abstract — structured extraction plus rule engines is a long-standing
pattern — only that it is the right amount of machinery for this problem,
this policy set, and one night of build time.

## Summary
CareRoute combines LLM-based structured intake, information-gap detection,
explicit routing policies, evidence-linked recommendations, and mandatory
human approval into a lightweight clinic intake workflow.
