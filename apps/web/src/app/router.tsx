import { createBrowserRouter } from 'react-router';
import { AppLayout } from './layout/AppLayout';
import { NotFoundPage } from './NotFoundPage';
import { HomePage } from '@/features/review-run/HomePage';
import { RunPage } from '@/features/review-run/RunPage';
import { NewReviewPage } from '@/features/new-review/NewReviewPage';
import { ReportPage } from '@/features/review-report/ReportPage';
import { FindingPage } from '@/features/review-report/FindingPage';

/**
 * Маршруты приложения (contracts/routes.md).
 *
 * workspaceId в маршрутах не участвует: он приходит из GET /v1/bootstrap.
 * Экранов входа, регистрации, ролей и выбора рабочего пространства нет
 * (FR-002, принцип IV). Выбранное замечание — часть URL, поэтому разбор
 * восстанавливается по прямой ссылке и после обновления страницы.
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    errorElement: <NotFoundPage />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'new', element: <NewReviewPage /> },
      { path: 'runs/:runId', element: <RunPage /> },
      { path: 'runs/:runId/report', element: <ReportPage /> },
      { path: 'runs/:runId/report/findings/:findingId', element: <FindingPage /> },
      { path: 'runs/:runId/report/findings/:findingId/dialogue', element: <FindingPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
