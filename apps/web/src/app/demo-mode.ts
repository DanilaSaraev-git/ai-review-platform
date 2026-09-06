/** Demo is an explicit build, with its own API and service-worker scope. */
export const isDemoMode = import.meta.env.VITE_MSW_SCENARIO === 'demo';

export const appBaseUrl = import.meta.env.BASE_URL;

export const DEMO_NOTICE = 'Пройдите разбор двух замечаний, загрузку версии с правками и завершение проверки. Исходник и результаты синтетические; выбранные файлы не анализируются и не отправляются на сервер.';

export const DEMO_REPLY_NOTICE = 'Заранее подготовленный ответ для демонстрации; он не сгенерирован по вашему вопросу.';
