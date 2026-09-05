import * as Label from '@radix-ui/react-label';
import * as RadioGroup from '@radix-ui/react-radio-group';
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react';
import { useId } from 'react';

/**
 * Примитивы интерфейса на Radix UI.
 *
 * Каждый элемент управления получает видимую подпись, все состояния
 * сопровождаются текстом или знаком и не различаются одним лишь цветом
 * (FR-041, FR-042, решение R-12).
 */

type Tone = 'neutral' | 'ok' | 'warn' | 'danger' | 'progress';

const TONE_MARK: Record<Tone, string> = {
  neutral: '•',
  ok: '✓',
  warn: '!',
  danger: '✕',
  progress: '⟳',
};

const TONE_CLASS: Record<Tone, string> = {
  neutral: 'border-line text-ink-muted',
  ok: 'border-ok text-ok',
  warn: 'border-warn text-warn',
  danger: 'border-accent text-accent',
  progress: 'border-line text-ink',
};

/** Состояние всегда читается текстом и знаком, а не только цветом (FR-042). */
export function StatusBadge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASS[tone]}`}
    >
      <span aria-hidden="true">{TONE_MARK[tone]}</span>
      {children}
    </span>
  );
}

export function Button({
  variant = 'secondary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded border px-3 py-1.5 text-sm font-medium transition cursor-pointer disabled:cursor-not-allowed disabled:opacity-50';
  const styles = {
    primary: 'border-accent bg-accent text-white hover:bg-red-800',
    secondary: 'border-line bg-surface text-ink hover:bg-surface-muted',
    ghost: 'border-transparent bg-transparent text-ink hover:bg-surface-muted',
  } as const;
  return <button type="button" className={`${base} ${styles[variant]} ${className}`} {...props} />;
}

interface FieldProps {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}

/** Подпись связана с полем; ошибка и подсказка объявлены через aria-describedby. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  return (
    <div className="flex flex-col gap-1">
      <Label.Root className="text-sm font-medium text-ink" htmlFor={id}>
        {label}
      </Label.Root>
      {hint ? (
        <p id={hintId} className="text-xs text-ink-muted">
          {hint}
        </p>
      ) : null}
      {children(id, describedBy)}
      {error ? (
        <p id={errorId} role="alert" className="text-xs font-medium text-accent">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`rounded border border-line bg-surface px-3 py-1.5 text-sm text-ink ${className}`}
      {...props}
    />
  );
}

export function TextArea({ className = '', ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`min-h-24 rounded border border-line bg-surface px-3 py-1.5 text-sm text-ink ${className}`}
      {...props}
    />
  );
}

export interface RadioOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
  disabledReason?: string;
}

/** Выбор одного значения с клавиатуры: стрелки и пробел работают штатно. */
export function RadioCards({
  legend,
  options,
  value,
  onValueChange,
  name,
}: {
  legend: string;
  options: readonly RadioOption[];
  value: string | undefined;
  onValueChange: (value: string) => void;
  name: string;
}) {
  return (
    <fieldset className="border-0 p-0">
      <legend className="mb-2 text-sm font-medium text-ink">{legend}</legend>
      <RadioGroup.Root
        className="flex flex-col gap-2"
        value={value ?? ''}
        onValueChange={onValueChange}
        name={name}
        aria-label={legend}
      >
        {options.map((option) => {
          const itemId = `${name}-${option.value}`;
          return (
            <div key={option.value} className="flex items-start gap-2">
              <RadioGroup.Item
                id={itemId}
                value={option.value}
                disabled={option.disabled}
                className="mt-1 size-4 shrink-0 cursor-pointer rounded-full border border-line bg-surface disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RadioGroup.Indicator className="block size-full rounded-full border-4 border-accent" />
              </RadioGroup.Item>
              <Label.Root htmlFor={itemId} className="cursor-pointer text-sm text-ink">
                <span className="font-medium">{option.label}</span>
                {option.description ? <span className="block text-xs text-ink-muted">{option.description}</span> : null}
                {option.disabled && option.disabledReason ? (
                  <span className="block text-xs font-medium text-warn">{option.disabledReason}</span>
                ) : null}
              </Label.Root>
            </div>
          );
        })}
      </RadioGroup.Root>
    </fieldset>
  );
}

export function Callout({ tone = 'neutral', title, children }: { tone?: Tone; title: string; children?: ReactNode }) {
  return (
    <div className={`rounded border-l-4 bg-surface p-3 text-sm ${TONE_CLASS[tone]}`} role="note">
      <p className="font-medium">
        <span aria-hidden="true" className="mr-1.5">
          {TONE_MARK[tone]}
        </span>
        {title}
      </p>
      {children ? <div className="mt-1 text-ink-muted">{children}</div> : null}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" className="text-sm text-ink-muted">
      <span aria-hidden="true" className="mr-1.5">
        ⟳
      </span>
      {label}
    </p>
  );
}
