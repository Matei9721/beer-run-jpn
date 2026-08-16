# ADR-001: Keep owner invite controls in the existing run picker

## Context

The run picker already owns the selected-run summary, owner-role affordance,
sheet focus trap, mobile bottom-sheet layout, and close/focus restoration. The
recipient flow has different lifecycle requirements: an anonymous deep link,
authentication continuation, acceptance races, and URL cleanup.

## Decision

Keep the owner invite subview's DOM state and compact copy/share controls in
`beer-runs.js`, while keeping invite protocol validation, recipient flow,
stale guards, and URL/security rules in `static/js/modules/invites.js`. The app
module remains the identity/context orchestration boundary and supplies the
API callback.

## Consequences

This avoids a second picker-like sheet and preserves the existing accessibility
and mobile behavior. Invite-specific protocol logic remains isolated from the
picker; if owner controls later need an independent surface, they can move to
the focused invite module without changing the API or acceptance contract.
