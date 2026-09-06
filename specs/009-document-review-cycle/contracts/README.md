# Interfaces

Канонический контракт находится в `contracts/review-platform/v1/openapi.yaml`; guest-v1 и API static генерируются от него. Новые ресурсы описывают семейства документов/версии/историю запусков, сопоставление и подтверждения исправлений, PDF. Существующий document_id остаётся ID версии; старые payload и enum не переопределяются.

Повтор использует прежний createReviewRun с новым idempotency key. Upload новой версии использует прежние ограничения и guest admission. Сравнение и PDF проверяют владение workspace/run/family на сервере. PDF response: application/pdf, attachment, private/no-store. Финальные operation IDs и поля фиксируются в каноническом контракте до web/backend реализации.
