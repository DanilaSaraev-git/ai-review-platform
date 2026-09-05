import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Field, RadioCards, StatusBadge, TextArea, TextInput } from './index';

/**
 * Базовый уровень доступности (FR-041, FR-042).
 * Проверяется, что подписи связаны с полями, состояния читаются текстом,
 * а элементы управления достижимы с клавиатуры.
 */
describe('примитивы интерфейса (FR-041, FR-042)', () => {
  it('связывает подпись с полем ввода', () => {
    render(
      <Field label="Обоснование" hint="Обязательно">
        {(id, describedBy) => <TextArea id={id} aria-describedby={describedBy} />}
      </Field>,
    );

    expect(screen.getByLabelText('Обоснование')).toBeInTheDocument();
    expect(screen.getByLabelText('Обоснование')).toHaveAccessibleDescription('Обязательно');
  });

  it('объявляет ошибку поля как сообщение для чтения с экрана', () => {
    render(
      <Field label="Обоснование" error="Укажите обоснование">
        {(id, describedBy) => <TextInput id={id} aria-describedby={describedBy} />}
      </Field>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Укажите обоснование');
  });

  it('передаёт состояние текстом, а не только цветом', () => {
    render(
      <>
        <StatusBadge tone="ok">Завершено</StatusBadge>
        <StatusBadge tone="danger">Не удалось</StatusBadge>
      </>,
    );

    expect(screen.getByText('Завершено')).toBeInTheDocument();
    expect(screen.getByText('Не удалось')).toBeInTheDocument();
  });

  it('позволяет выбрать вариант с клавиатуры', async () => {
    const user = userEvent.setup();
    render(
      <RadioCards
        legend="Статус"
        name="status"
        value="confirmed"
        onValueChange={() => {}}
        options={[
          { value: 'confirmed', label: 'Подтверждено' },
          { value: 'rejected', label: 'Отклонено' },
        ]}
      />,
    );

    await user.tab();
    expect(screen.getByRole('radio', { name: 'Подтверждено' })).toHaveFocus();
  });

  it('не даёт выбрать недоступный вариант и называет причину', () => {
    render(
      <RadioCards
        legend="Профиль модели"
        name="model"
        value={undefined}
        onValueChange={() => {}}
        options={[
          { value: 'a', label: 'Доступный' },
          { value: 'b', label: 'Недоступный', disabled: true, disabledReason: 'Профиль недоступен' },
        ]}
      />,
    );

    expect(screen.getByRole('radio', { name: /Недоступный/u })).toBeDisabled();
    expect(screen.getByText('Профиль недоступен')).toBeInTheDocument();
  });
});
