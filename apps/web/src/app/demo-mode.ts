/** Demo is an explicit build, with its own API and service-worker scope. */
export const isDemoMode = import.meta.env.VITE_MSW_SCENARIO === 'demo';

export const appBaseUrl = import.meta.env.BASE_URL;

export const DEMO_NOTICE = 'Показываем заранее подготовленный разбор демонстрационного документа. Выбранный файл не анализируется. Модель не вызывается.';

export const DEMO_REPLY_NOTICE = 'Заранее подготовленный ответ для демонстрации; он не сгенерирован по вашему вопросу.';
