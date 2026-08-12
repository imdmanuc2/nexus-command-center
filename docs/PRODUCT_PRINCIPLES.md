# Nexus Command Center Version 1 Product Principles

Package 073 establishes the Version 1 operator experience around Mission Control.

1. **One page, one primary purpose.** Mission Control answers: what needs attention right now?
2. **One metric, one canonical source.** Home V2 consumes `/api/platform/dashboard-summary` for canonical dashboard state.
3. **One object, one Digital Twin.** Inventory and topology views launch the same object workspace.
4. **One operation, one evidence trail.** Operations remain object-centric and auditable.
5. **One recommendation, one reason.** Recommendations should explain the condition that produced them.
6. **Calm by default.** Detailed engineering views remain available, but do not crowd the operator landing view.
7. **Progressive disclosure.** Mission-critical information is visible immediately; engineering and production detail is one expansion away.

## Mission Control information hierarchy

1. Platform health and production summary
2. Needs Attention
3. Operations Brief
4. Operational Readiness
5. Recent Activity
6. Engineering & Production Detail

This document is a product standard for Version 1 UI work and should be updated deliberately rather than package-by-package.
