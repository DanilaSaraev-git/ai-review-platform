import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import type { ReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { RunStatePanel } from './RunStatePanel';
import { STALL_WARNING } from '../lib/stall-detector';

const ALL_STATES: ReviewRun['state'][] = [
  'queued',
  'preparing',
  'reviewing',
  'validating',
  'completed',
  'failed',
  'cancelled',
];

const noProgress = { durationMs: 5000, isStalled: false, warning: null };

describe('RunStatePanel (FR-013, FR-015, FR-039)', () => {
  it.each(ALL_STATES)('показывает состояние «%s» с подписью и пояснением', (state) => {
    const run: ReviewRun = { ...fixtures.runQueued, state, progress: { percent: 0, message: '' } };
    renderWithProviders(<RunStatePanel run={run} progress={noProgress} />);

    // Ни одно состояние не оставляет экран пустым.
    expect(screen.getByRole('heading', { name: /Состояние проверки/u })).toBeInTheDocument();
    expect(screen.getByText(/Идёт/u)).toBeInTheDocument();
  });

  it('называет причину неудачи, признак повтора и отсутствие отчёта', () => {
    renderWithProviders(<RunStatePanel run={fixtures.runFailed} progress={noProgress} />);

    // Текст причины встречается и в сообщении о прогрессе, и в пояснении к ошибке.
    expect(screen.getAllByText(/не соответствующий контракту/u).length).toBeGreaterThan(0);
    expect(screen.getByText(/Повтор допустим/u)).toBeInTheDocument();
    expect(screen.getByText(/Отчёт не опубликован/u)).toBeInTheDocument();
  });

  it('не предлагает отчёт у неуспешного запуска', () => {
    renderWithProviders(<RunStatePanel run={fixtures.runFailed} progress={noProgress} />);
    expect(screen.queryByRole('link', { name: /Открыть отчёт/u })).not.toBeInTheDocument();
  });

  it('предлагает отчёт у успешного запуска', () => {
    renderWithProviders(<RunStatePanel run={fixtures.runCompleted} progress={noProgress} />);
    expect(screen.getByRole('link', { name: /Открыть отчёт/u })).toBeInTheDocument();
  });

  it('показывает предупреждение о долгом запуске, не подменяя состояние', () => {
    const run: ReviewRun = { ...fixtures.runQueued, state: 'reviewing' };
    renderWithProviders(
      <RunStatePanel run={run} progress={{ durationMs: 21 * 60 * 1000, isStalled: true, warning: STALL_WARNING }} />,
    );

    expect(screen.getAllByText(/дольше обычного/u).length).toBeGreaterThan(0);
    // Предупреждение не подменяет состояние: подпись состояния осталась на месте.
    expect(screen.getAllByText('Проверка').length).toBeGreaterThan(0);
  });

  it('сообщает о потере связи, не теряя состояние запуска', () => {
    renderWithProviders(<RunStatePanel run={fixtures.runQueued} progress={noProgress} isOffline />);
    expect(screen.getByText(/Состояние не обновляется/u)).toBeInTheDocument();
  });

  it('показывает зафиксированные версии проверки', () => {
    renderWithProviders(<RunStatePanel run={fixtures.runCompleted} progress={noProgress} />);
    expect(screen.getByText(/Зафиксированные версии проверки/u)).toBeInTheDocument();
  });
});
