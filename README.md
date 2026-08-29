# StudioERP v2 — Kernel + Rings

Greenfield rebuild of StudioERP as a stable **kernel + feature rings**
architecture (Plan A). The original modular monolith (sibling `Offsite ERP/`) is
the **behaviour reference / parity source**; this tree ports behaviour module by
module, ring by ring, keeping the old system intact until parity is proven.

## Architecture

```
k0  kernel           config · security · db · money · rbac/financial
                     isolation · errors · state machines · audit · currency
k1  platform         (enums/state machines, org structure, settings, notifications)
r2  people           identity · employees · attendance · leave · holidays
r3  work             projects · tasks · timesheets · site-visits
r4  money            finance (invoices/expenses) · payroll
r5  intelligence     reports · dashboard · notices · meetings · backup · audit UI
f   frontend rings   api clients + feature UI, shipped per-ring
```

- A module depends only on **inner** rings (enforced via `.importlinter`).
- Cross-module reads via ring service layers, never direct model imports.
- New v2 modules become **new outer rings** requiring zero kernel change.
- Full spec: `_ai_context/plans/2026-08-29_kernel_rings_spec.md` (in the repo).

## Current status

- **Phase 4 (kernel core, k0): done.** Lazy async DB session, RBAC + financial
  isolation, money/currency, errors, state machines, security, audit, middleware.
- Rings 1–5 + frontend: in progress (see the repo `_ai_context/tasks.md`).

## Develop

```bash
python -m venv .venv
.venv\Scripts\python  -m pip install -e ".[dev]"
ruff check src tests
pytest
```

> On Windows, the `tzdata` package is required for `Asia/Kolkata` —
> included in `pyproject.toml` dependencies.
