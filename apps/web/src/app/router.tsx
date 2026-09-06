import { createBrowserRouter } from 'react-router';
import { AppLayout } from './layout/AppLayout';
import { NotFoundPage } from './NotFoundPage';
import { DocumentsPage } from '@/features/document-cycle/DocumentsPage';
import { DocumentFamilyPage } from '@/features/document-cycle/DocumentFamilyPage';
import { RunPage } from '@/features/review-run/RunPage';
import { NewReviewPage } from '@/features/new-review/NewReviewPage';
import { ReportPage } from '@/features/review-report/ReportPage';
import { FindingPage } from '@/features/review-report/FindingPage';
import { ReviewWorkspaceLayout } from '@/features/review-report/components/ReviewWorkspaceLayout';

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
      { index: true, element: <DocumentsPage /> },
      { path: 'new', element: <NewReviewPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'documents/:familyId', element: <DocumentFamilyPage /> },
      {
        path: 'runs/:runId',
        element: <ReviewWorkspaceLayout />,
        children: [
          { index: true, element: <RunPage /> },
          { path: 'report', element: <ReportPage /> },
          { path: 'report/changes', element: <ReportPage /> },
          { path: 'report/findings/:findingId', element: <FindingPage /> },
          { path: 'report/findings/:findingId/dialogue', element: <FindingPage /> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
], { basename: import.meta.env.BASE_URL });
