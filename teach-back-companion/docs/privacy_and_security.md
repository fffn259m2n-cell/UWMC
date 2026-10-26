# Privacy and security

**Data.** Fictional patients only; the loader refuses plans not marked `synthetic`. No
connection to Epic, MyChart or any UW system. Nothing typed into teach-back or chat is stored
or logged by the application. The local SQLite file holds only reminder times, task status
and the documented instruction text. "Clear demo data" deletes it.

**Network.** The app makes no outbound requests: no analytics, fonts, CDNs or AI providers.
It listens on 127.0.0.1 by default and warns if bound to another interface (there is no login).

**Web hardening.** Content-Security-Policy `default-src 'self'` with no inline script or style;
`frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: no-referrer`, `Cache-Control: no-store`, restrictive `Permissions-Policy`.
The API explorer is disabled. All request bodies are size-limited and validated by pydantic.
The front end renders data with `textContent` only, so stored or returned text cannot inject
markup. Test: `test_security_headers`, `test_input_limits_and_unknowns`; the browser check fails
on any CSP violation.

**Content integrity.** Matching rules (misconception patterns) are not sent to the browser.
Plan and library text is scanned for prompt-injection phrasing at load.

## Threat model (prototype scope)

| Threat | Mitigation | Residual |
|---|---|---|
| Real PHI entered into the demo | Synthetic-only plans; nothing typed is stored; banner on every page | A user could still type real details into a field; they are processed in memory and discarded |
| Injected instructions in content | Load-time scan; no LLM in default mode; LLM prompt marks content as data and output is verified | Pattern scan is not exhaustive |
| XSS / clickjacking | CSP without inline code; textContent rendering; frame denial | — |
| Exposure on a network | Localhost default; warning otherwise | No authentication by design |
| Over-trust in automated checks | Verdicts always require human review; limits stated in UI and docs | Human factors remain |

This prototype is **not** a HIPAA-compliant or production-secured system. A real deployment
would need UW Medicine privacy, security, clinical-safety and regulatory review.
