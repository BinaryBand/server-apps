# Copilot Instructions

## Architecture

**Reconciler Model** Model the system as a set of resources and a reconciler that ensures the actual state converges to the desired state. The reconciler should be designed to be idempotent and handle transient failures gracefully.

**Unidirectional Data Flow** Data and control should 'waterfall' in a single direction. In the startup flow, data flows from volumes → permissions → compose → post-start → health, and never back upstream.

## [Architectural Checklist](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles)

- [ ] Design for **idempotency** and handle transient failures gracefully.
- [ ] Observable
- [ ] Single Responsibility Principle
- [ ] Separation of Concerns
- [ ] Explicit Dependencies
- [ ] Encapsulation
- [ ] Bounded Contexts
- [ ] Dependency Inversion
