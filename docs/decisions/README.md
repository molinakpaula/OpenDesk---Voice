# Architecture Decision Records

Architecture Decision Records explain why important technical choices were
made, which alternatives were considered, and what consequences remain. They
make trade-offs reviewable instead of leaving future contributors to infer them
from code.

| ADR | Decision |
| --- | --- |
| [001](001-backend-owns-operational-context.md) | FastAPI owns operational context and disclosure |
| [002](002-wood-lot-central-entity.md) | Wood lot is the central entity |
| [003](003-separate-transport-entity.md) | Transport movements are separate from lots |
| [004](004-caller-first-conversation.md) | Use a caller-ID-first conversation |
| [005](005-json-before-database.md) | Use validated JSON before adding a database |
| [006](006-python-translations.md) | Keep initial translations in Python |
