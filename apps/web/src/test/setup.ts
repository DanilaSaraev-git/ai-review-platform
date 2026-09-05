import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { cleanup } from '@testing-library/react';
import { mockServer } from '@/mocks/server';

// Компонентные тесты идут против тех же MSW handlers, что и dev-сборка:
// ветвления логики UI по источнику данных нет (принцип III).
beforeAll(() => {
  mockServer.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  cleanup();
  mockServer.resetHandlers();
});

afterAll(() => {
  mockServer.close();
});
