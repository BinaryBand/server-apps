# Copilot Instructions

## [Architectural Checklist](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles)

- [ ] Separation of Concerns
- [ ] Encapsulation
- [ ] Dependency Inversion
- [ ] Explicit Dependencies
- [ ] Single Responsibility
- [ ] Don't Repeat Yourself (DRY)
- [ ] Persistence-agnostic
- [ ] Bounded Contexts
- [ ] Idempotency
- [ ] Observability

## Reconciler Model

Model the system as a set of resources and a reconciler that ensures the actual state converges to the desired state. The reconciler should be designed to be idempotent and handle transient failures gracefully.
