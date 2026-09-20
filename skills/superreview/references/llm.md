# LLM and agent systems

Trace context assembly, truncation, retrieval provenance, and exact candidate identity.
Distinguish observed, inferred, and carried values across stages. Inspect tool authorization
outside the prompt, validation of structured output, bounded retries, cost limits,
timeouts, fallback visibility, and idempotency of actions. Delimiters help clarity but do
not make prompt injection safe. Untrusted input must not acquire authority over tools.
Evaluate proposed prompt fixes against multiple examples and previous success cases.
Neither model agreement nor schema-valid output proves a claim is true. Verify current API
and model identifiers against authoritative docs when needed; knowledge age is not evidence.
