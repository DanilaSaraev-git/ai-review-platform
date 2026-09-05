import { http, HttpResponse } from 'msw';
import type { RequestHandler } from 'msw';
import * as fixtures from '@/mocks/fixtures';
import { API } from './base';
import { happyPath } from './happy-path';

export function modelUnconfigured(): RequestHandler[] {
  return [
    http.get(`${API}/workspaces/:workspaceId/model-profiles`, () =>
      HttpResponse.json({
        items: [{
          ...fixtures.modelProfiles[0]!,
          id: 'unconfigured',
          name: 'Модель не подключена',
          description: 'Подключите модель в конфигурации сервиса.',
          availability: 'unavailable',
        }],
      }),
    ),
    ...happyPath(),
  ];
}
