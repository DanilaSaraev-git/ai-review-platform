import { defineConfig } from 'orval';

// Единственный вход генерации — зафиксированный контракт v1.
// Ручные копии DTO запрещены: типы, клиент, query hooks и MSW handlers
// порождаются только отсюда (принцип II, contracts/orval.md).
export default defineConfig({
  reviewPlatform: {
    input: {
      target: '../../contracts/review-platform/v1/openapi.yaml',
    },
    output: {
      mode: 'split',
      target: 'src/api/generated/endpoints.ts',
      schemas: 'src/api/generated/model',
      client: 'react-query',
      httpClient: 'fetch',
      clean: true,
      mock: {
        generators: [{ type: 'msw' }],
      },
      override: {
        // Возвращается только полезная нагрузка: варианты ошибок в тип данных
        // не попадают, потому что mutator выбрасывает их исключением.
        fetch: {
          includeHttpResponseReturnType: false,
        },
        mutator: {
          path: './src/api/http-client.ts',
          name: 'httpClient',
        },
        // Создающие и изменяющие операции остаются мутациями: запуск проверки,
        // ход диалога и сохранение решения выполняются действием аналитика,
        // а не фоновым запросом.
        query: {
          signal: true,
        },
      },
    },
  },
});
