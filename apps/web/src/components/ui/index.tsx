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
  neutral: 'border-line bg-surface-muted text-ink-muted',
  ok: 'border-ok/20 bg-ok-tint text-ok',
  warn: 'border-warn/20 bg-warn-tint text-warn',
  danger: 'border-accent/20 bg-accent-tint text-accent-strong',
  progress: 'border-line-strong bg-surface-muted text-ink',
};

/** Состояние всегда читается текстом и знаком, а не только цветом (FR-042). */
export function StatusBadge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex max-w-full items-center gap-1.5 rounded-[4px] border px-1.5 py-0.5 text-[11px] leading-4 font-medium ${TONE_CLASS[tone]}`}
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
    'inline-flex min-h-9 cursor-pointer items-center justify-center gap-2 rounded-[6px] border px-3 py-1.5 text-[13px] font-medium shadow-[0_1px_2px_#18183008] transition-[background-color,border-color,color,box-shadow,transform] duration-100 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100';
  const styles = {
    primary: 'border-accent bg-accent text-white hover:border-accent-strong hover:bg-accent-strong disabled:border-line disabled:bg-surface-muted disabled:text-ink-subtle disabled:opacity-100 disabled:shadow-none',
    secondary: 'border-line bg-surface text-ink hover:border-line-strong hover:bg-surface-muted',
    ghost: 'border-transparent bg-transparent text-ink-muted shadow-none hover:bg-surface-muted hover:text-ink',
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
    <div className="flex flex-col gap-1.5">
      <Label.Root className="text-[13px] font-medium text-ink" htmlFor={id}>
        {label}
      </Label.Root>
      {hint ? (
        <p id={hintId} className="max-w-[68ch] text-xs leading-5 text-ink-subtle">
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
      className={`rounded-[6px] border border-line-strong bg-surface px-3 py-2 text-base text-ink transition-[border-color,box-shadow] duration-100 focus:border-accent focus:shadow-[0_0_0_2px_rgba(215,25,32,0.1)] sm:text-sm ${className}`}
      {...props}
    />
  );
}

export function TextArea({ className = '', ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`min-h-24 resize-y rounded-[6px] border border-line-strong bg-surface px-3 py-2 text-base leading-6 text-ink transition-[border-color,box-shadow] duration-100 focus:border-accent focus:shadow-[0_0_0_2px_rgba(215,25,32,0.1)] sm:text-sm ${className}`}
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
  compact = false,
}: {
  legend: string;
  options: readonly RadioOption[];
  value: string | undefined;
  onValueChange: (value: string) => void;
  name: string;
  compact?: boolean;
}) {
  return (
    <fieldset className="border-0 p-0">
      <legend className="mb-2 text-[13px] font-medium text-ink">{legend}</legend>
      <RadioGroup.Root
        className={compact ? 'flex flex-wrap gap-1.5' : 'flex flex-col gap-1.5'}
        value={value ?? ''}
        onValueChange={onValueChange}
        name={name}
        aria-label={legend}
      >
        {options.map((option) => {
          const itemId = `${name}-${option.value}`;
          return (
            <div key={option.value} className={`group flex items-start gap-2.5 rounded-[6px] border border-line bg-surface transition-[border-color,background-color] duration-100 hover:border-line-strong hover:bg-surface-muted has-[[data-state=checked]]:border-accent has-[[data-state=checked]]:bg-accent-tint ${compact ? 'px-2.5 py-1.5' : 'px-3 py-2.5'}`}>
              <RadioGroup.Item
                id={itemId}
                value={option.value}
                disabled={option.disabled}
                className={`${compact ? 'mt-px size-3.5' : 'mt-0.5 size-4'} shrink-0 cursor-pointer rounded-full border border-line-strong bg-surface disabled:cursor-not-allowed disabled:opacity-40`}
              >
                <RadioGroup.Indicator className="block size-full rounded-full border-4 border-accent" />
              </RadioGroup.Item>
              <Label.Root htmlFor={itemId} className="min-w-0 cursor-pointer text-[13px] leading-5 text-ink">
                <span className="font-medium">{option.label}</span>
                {option.description ? <span className="mt-0.5 block text-xs leading-4 text-ink-muted">{option.description}</span> : null}
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
    <div className={`rounded-[6px] border border-l-[3px] p-3 text-[13px] ${TONE_CLASS[tone]}`} role="note">
      <p className="font-medium text-ink">
        <span aria-hidden="true" className="mr-1.5">
          {TONE_MARK[tone]}
        </span>
        {title}
      </p>
      {children ? <div className="mt-1 leading-5 text-ink-muted">{children}</div> : null}
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
