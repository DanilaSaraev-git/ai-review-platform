import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import type { ReviewRun } from '@/api/generated/model';
import * as fixtures from '@/mocks/fixtures';
import { renderWithProviders } from '@/test/render';
import { RUN_STATE_TEXT } from '@/lib/error-messages';
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
    expect(screen.getByText(RUN_STATE_TEXT[state].hint)).toBeInTheDocument();
  });

  it.each(['completed', 'failed', 'cancelled'] as const)(
    'для состояния «%s» заменяет устаревший прогресс итогом и длительностью',
    (state) => {
      const run: ReviewRun = {
        ...fixtures.runQueued,
        state,
        progress: { percent: 40, message: 'Reviewing document' },
      };
      renderWithProviders(<RunStatePanel run={run} progress={noProgress} />);

      expect(screen.getByText(RUN_STATE_TEXT[state].hint)).toBeInTheDocument();
      expect(screen.getByText('Длительность: 5 с')).toBeInTheDocument();
      expect(screen.queryByText('Reviewing document')).not.toBeInTheDocument();
      expect(screen.queryByText(/^Идёт/u)).not.toBeInTheDocument();
    },
  );

  it('сохраняет сообщение о прогрессе и время ожидания активной проверки', () => {
    const run: ReviewRun = {
      ...fixtures.runQueued,
      state: 'reviewing',
      progress: { percent: 40, message: 'Разбираем направления проверки' },
    };
    renderWithProviders(<RunStatePanel run={run} progress={noProgress} />);

    expect(screen.getByText('Разбираем направления проверки')).toBeInTheDocument();
    expect(screen.getByText('Идёт 5 с')).toBeInTheDocument();
  });

  it('называет причину неудачи, признак повтора и отсутствие отчёта', () => {
    renderWithProviders(<RunStatePanel run={fixtures.runFailed} progress={noProgress} />);

    expect(screen.getByText(/не соответствующий контракту/u)).toBeInTheDocument();
    expect(screen.getByText(/Повтор допустим/u)).toBeInTheDocument();
    expect(screen.getByText(/Отчёт не опубликован/u)).toBeInTheDocument();
  });

  it.each(['validation_failed', 'model_output_invalid'] as const)(
    'при «%s» без разрешённого повтора не требует менять документ',
    (code) => {
      const run: ReviewRun = {
        ...fixtures.runFailed,
        error: { code, retryable: false, message: 'Provider detail must not be displayed' },
      };
      renderWithProviders(<RunStatePanel run={run} progress={noProgress} />);

      expect(screen.getByText(/Ответ модели не удалось подтвердить/u)).toBeInTheDocument();
      expect(screen.getByText(/Причину отказа нужно уточнить перед новой проверкой/u)).toBeInTheDocument();
      expect(screen.queryByText(/Повтор допустим|Повтор не поможет|другие входные данные/u)).not.toBeInTheDocument();
      expect(screen.queryByText('Provider detail must not be displayed')).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: /Открыть отчёт/u })).not.toBeInTheDocument();
    },
  );

  it('при другой ошибке без разрешённого повтора предлагает уточнить причину', () => {
    const run: ReviewRun = {
      ...fixtures.runFailed,
      error: { code: 'internal_error', retryable: false, message: 'Internal detail' },
    };
    renderWithProviders(<RunStatePanel run={run} progress={noProgress} />);

    expect(screen.getByText('Перед новой проверкой нужно уточнить причину ошибки.')).toBeInTheDocument();
    expect(screen.queryByText(/Повтор допустим|Повтор не поможет/u)).not.toBeInTheDocument();
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
