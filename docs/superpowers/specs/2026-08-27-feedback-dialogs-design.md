# Feedback dialogs & publish progress

## Goal
Replace all native `alert` / `confirm` / `prompt` with in-app Toast + Confirm/Prompt modals. Add a publish progress overlay so Review/Studio publishing is not opaque.

## API
- `toast.success|error|info(message)`
- `confirmDialog({ message, title?, confirmLabel?, cancelLabel?, danger? }) => Promise<boolean>`
- `promptDialog({ message, title?, placeholder?, expectedValue? }) => Promise<string | null>`
- `<PublishProgressOverlay open phase platforms? />` — staged UX while a single publish request runs

## Scope
All frontend call sites of alert/confirm/prompt and `alertValidationErrors`. Keep destructive semantics via Confirm/Prompt modals.
