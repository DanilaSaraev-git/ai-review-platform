# Data model: 006 MVP launch

Каноническая модель переиспользуется из [глоссария](../../docs/domain-glossary.md) и [v1](../../contracts/review-platform/v1/README.md). Публичные DTO и схема базы не меняются планом.

| Сущность | Связи/состояние | Инвариант |
| --- | --- | --- |
| Document / Context source | workspace, extraction state, fragments | Оригинал сохраняется; ошибки извлечения явно видны |
| Review run | document + profiles + execution snapshot | Недоступная модель не принимается в работу |
| Review report | run, findings, coverage, provenance | После публикации bytes/ETag неизменны |
| Finding state | report finding, revision, human decision | Stale revision даёт 409; решение отдельно |
| Dialogue turn | finding, revision, user text, async response | Один генерируемый ход, retry не создаёт новый смысловой ход |
| Model availability | operator configuration + credential state | Unconfigured недоступен; synthetic не production fallback |
| Release (operator) | Git commit, build, config reference, previous release | Секреты не внутри Git/archive |
| Backup set (operator) | DB dump, artifact archive, manifest/time/version | Согласованная пара, проверяемая в отдельной среде |

Изменения UI состояния локальны: выбранный finding остаётся в URL, document selection/highlight сохраняется в общей рабочей области; draft хранится до успешного сохранения или явного изменения пользователем. Gateway admission не превращает configured actor в персональную идентичность.
