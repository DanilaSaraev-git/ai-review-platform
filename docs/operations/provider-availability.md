# Доступность провайдеров моделей из России

Проверено по публичным страницам 6 сентября 2026 года. Это эксплуатационная справка о каталогах и условиях подключения; доступность с IP нашего сервера, работа схемы отчёта и качество ревью не проверялись. Тесты, бенчмарки, probes, обращения к API моделей и платные вызовы не выполнялись. Профили моделей и конфигурация не изменялись.

## Российские поставщики API

| Поставщик | Что подтверждено документами | Границы для MVP |
| --- | --- | --- |
| Cloud.ru Foundation Models | Есть OpenAI-compatible API, в каталоге указана именно `openai/gpt-5.4-mini` со Structure Output. | GPT-5.4-mini — внешняя модель: данные покидают инфраструктуру Cloud.ru. Условия всей цепочки внешнего API для нашего сценария не установлены. |
| Yandex AI Studio | Поддерживаются российские плательщики, OpenAI-compatible Chat Completions и JSON Schema. | Нужно выбрать другую модель: GPT-5.4-mini в просмотренном каталоге не указана. |
| GigaChat API | Есть совместимость с OpenAI SDK и строгий схемный вывод. | В документации для юрлиц покупка токенов ограничена действующими клиентами; отличается авторизация и форма `response_format`. |
| VseGPT | Провайдер заявляет доступ из России; есть OpenAI-compatible API и GPT-5.4-mini со Structured Outputs. | Посредник; наличие в каталоге не подтверждает выполнение условий исходного поставщика. Требуется платный уровень доступа к модели. |
| ProxyAPI | Провайдер заявляет доступ к GPT из России через европейские прокси; GPT-5.4-mini есть в прайс-листе. | Посредник; конкретные условия исходного поставщика и строгий вывод нашей схемы не подтверждены. |
| Timeweb Cloud AI Gateway | Есть совместимый Chat Completions API и GPT-5.4 Mini в продуктовом каталоге. | Поддержка `strict` у конкретной модели и условия внешнего маршрута требуют уточнения. |

## Подтверждения и особенности адаптера

**Cloud.ru.** [Каталог](https://cloud.ru/docs/foundation-models/ug/topics/overview__available__models) различает внутренние и внешние модели. `openai/gpt-5.4-mini` — внешняя, контекст 400000, заявлены Function Calling и Structure Output; `openai/gpt-oss-120b` — внутренняя и является другой моделью. Внутренние Kimi-K2.6, DeepSeek-V4-Pro и Qwen3.6-35B-A3B также перечислены. Для внутренних моделей Cloud.ru заявляет отсутствие передачи во внешние системы, логирования и хранения пользовательских данных; для внешних подтверждает передачу за пределы своей инфраструктуры.

[Спецификация API Cloud.ru](https://cloud.ru/docs/foundation-models/ug/topics/api-ref__specs) описывает `POST https://foundation-models.api.cloud.ru/v1/chat/completions`, BearerAuth, `max_completion_tokens` и `response_format.json_schema.strict`. Страница спецификации иногда отображает только загрузку; параметры видны в индексируемом содержимом того же официального URL. Это описание интерфейса, не подтверждение `reasoning_effort=none` и всей схемы отчёта у конкретной внешней модели. [Тарификация](https://cloud.ru/docs/foundation-models/ug/topics/pricing?source-platform=Evolution) — pay-as-you-go, входные и генерируемые токены; точный тариф и способы пополнения здесь не проверены.

**Yandex AI Studio.** [Оплата Yandex Cloud](https://yandex.cloud/ru/docs/billing/qa/payment) прямо поддерживает резидентов РФ: RUB и карты российских банков; перечислены карта, СБП и перевод с расчётного счёта для бизнеса. [API reference](https://aistudio.yandex.ru/ru/docs/ai-studio/api/Chat-Completions/createChatCompletion) описывает `/v1/chat/completions` на `ai.api.cloud.yandex.net` и `response_format.json_schema.strict`. Нужны API-ключ, идентификатор каталога и URI модели `gpt://<folder>/<model>`.

[Пример структурированного вывода](https://aistudio.yandex.ru/ru/docs/ai-studio/operations/generation/completions-structured) использует `json_schema`; в примере strict не задан. [Каталог](https://aistudio.yandex.ru/ru/docs/ai-studio/concepts/generation/models) содержит Alice AI LLM / Flash, YandexGPT, DeepSeek, Qwen и gpt-oss. У некоторых моделей близкий срок вывода: Qwen3 235B — 30.09.2026, gpt-oss 20b/120b — 30.10.2026. Эти варианты требуют учёта жизненного цикла при выборе default. Место обработки всех вариантов в этой проверке отдельно не подтверждено.

**GigaChat.** [Быстрый старт для юрлиц](https://developers.sber.ru/docs/ru/gigachat/legal-quickstart), обновлённый 31.08.2026, ограничивает покупку токенов действующими клиентами и требует сертификаты НУЦ Минцифры. [Тарифы для юрлиц](https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs) также относятся к действующим клиентам. Это ограничение относится к описанному сценарию для юрлиц и не позволяет обещать беспрепятственную активацию нового корпоративного аккаунта.

[Совместимость с OpenAI](https://developers.sber.ru/docs/ru/gigachat/guides/compatible-openai): базовый URL `https://api.giga.chat/v1`; ключ авторизации обменивается на access token, действующий 30 минут. Потребуется серверное обновление токена. [Схемный вывод](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output) использует `response_format: {type: "json_schema", schema: {...}, strict: true}` — вложенность отличается от OpenAI. GPT-5.4-mini через этот API не подтверждена.

**VseGPT.** [Описание API](https://vsegpt.ru/Docs/API/Code) заявляет доступ из России и OpenAI-compatible `/v1/chat/completions` с Bearer-аутентификацией. [Каталог](https://www.vsegpt.ru/Docs/Models) содержит `openai/gpt-5.4-mini` с `structured-outputs`, уровень «Базовый+», модель недоступна на тестовом уровне. [Дополнительные параметры](https://vsegpt.ru/Docs/API/AddFeatures) показывают `json_schema` со `strict`. Применимость всех исходных параметров MVP и схемы отчёта экспериментально не проверена.

**ProxyAPI.** [Продуктовая страница](https://proxyapi.ru/) описывает доступ из РФ через европейские прокси; [прайс-лист](https://proxyapi.ru/pricing/list) включает `gpt-5.4-mini`, [документация моделей](https://proxyapi.ru/docs/models) — совместимые идентификаторы. Это заявления посредника, а не подтверждение разрешения OpenAI для российского конечного клиента.

**Timeweb Cloud.** [AI Gateway](https://timeweb.cloud/docs/ai-agents/api-usage/ai-gateway) описывает Chat Completions с базовым URL `https://api.timeweb.ai/v1`; [каталог AI Agents](https://timeweb.cloud/services/ai-agents) перечисляет GPT-5.4 Mini. Строгий схемный вывод этой модели просмотренными страницами не подтверждён.

## Граница рекомендаций

Для сохранения GPT-5.4-mini по каталогу подходят прежде всего Cloud.ru и VseGPT; перед активацией нужно уточнить доступ для нашего аккаунта и сценария, условия внешней модели и поддержку параметров. Для выполнения модели в инфраструктуре российского поставщика следует рассматривать внутренние модели Cloud.ru; Yandex AI Studio — отдельный кандидат при допустимости замены модели. Это предложения, а не принятое решение о смене профиля.

Россия отсутствует в [поддерживаемых странах OpenAI API](https://developers.openai.com/api/docs/supported-countries). OpenAI предупреждает о возможной блокировке за доступ или предоставление доступа из неподдерживаемых стран. Российский посредник или иностранный IP сами по себе не подтверждают допустимость всей цепочки. Указанные каталоги не являются рекомендацией обходить эти условия.

Hugging Face / Novita не включены в подтверждённо доступные варианты: явное подтверждение поддержки РФ в проведённой проверке не получено. Прежний успешный серверный запрос подтверждает только тот конкретный запуск и не устанавливает текущие договорные условия.
