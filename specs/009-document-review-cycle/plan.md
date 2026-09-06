# Implementation Plan: Цикл документа и PDF

**Branch**: `codex/009-document-review-cycle` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)

## Summary

Добавить логический документ над неизменяемыми версиями, связанные запуски, консервативное сопоставление замечаний и PDF согласованного состояния. Существующие ID версий и байты опубликованных отчётов сохраняются.

## Technical Context

- Текущий Python/FastAPI/psycopg runtime, PostgreSQL и Alembic; поддержать PostgreSQL и синтетический fixture adapter.
- Web: текущие React/TypeScript/TanStack Query, Orval и MSW. Ручных DTO нет.
- PDF: ReportLab с поставляемым кириллическим шрифтом DejaVu Sans; статический PDF формируется без браузера и LLM.
- Сопоставление: чистая детерминированная функция, точные однозначные признаки для автоматической связи; похожие и неоднозначные пары для ручной проверки. Смена IDs/номеров страниц не определяет идентичность.
- Хранилище: добавить семейства/членство версий, базу запуска и отдельное состояние цикла с ревизией; не встраивать mutable состояние в canonical report.
- Тесты: pytest (domain, HTTP, PostgreSQL, migration), Vitest/MSW, Playwright; PDF extraction и визуальный render.
- Численные SLO не заданы. Использовать существующие ограничения размера и квоты; сравнение и экспорт не требуют внешней модели.
- Baseline: design 1978ea6 и guest 87889d6 объединены в 6ce14c1; объединение проверено отдельным регрессионным набором. Не использовать старый main как основание выпуска.

## Constitution Check

До и после дизайна: совместимые дополнительные HTTP ресурсы, unchanged v1 IDs/enums и canonical report; отдельный контрактный commit/PR; сгенерированный клиент; независимые backend/web проверки; guest ownership; решение модели не становится human decision; только синтетические fixtures. Нарушений не требуется.

## Project Structure

- `contracts/review-platform/`: новые ресурсы и примеры, затем генерация guest/static контрактов.
- `packages/review-core/`: чистое сопоставление и fixture behavior.
- `packages/review-runtime/`: миграция, PostgreSQL цикл и renderer PDF.
- `apps/api/`: DTO и routes ресурсов цикла.
- `apps/web/`: карточки документов, версии, повтор, панель сравнения и PDF.
- `tests/`: контракт, миграции, HTTP/guest и полный синтетический цикл.

Документы дизайна: [research](research.md), [data model](data-model.md), [interfaces](contracts/README.md), [quickstart](quickstart.md), [tasks](tasks.md).

## Delivery

1. Spec quality gate и отдельный контрактный срез.
2. Параллельно backend/storage, pure matching/PDF, web против контрактных примеров.
3. Интеграция, полные релевантные проверки, визуальная проверка PDF/UI и независимый review.
4. Изменения остаются в отдельной ветке; production deployment не входит в текущее поручение.
