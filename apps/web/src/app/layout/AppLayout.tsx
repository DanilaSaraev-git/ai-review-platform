import { Link, NavLink, Outlet } from 'react-router';

/**
 * Каркас страницы: шапка, левая панель разделов и область маршрута.
 * Раскладка веб-интерфейса v1.
 *
 * В шапке нет элементов аккаунта, выхода, ролей и участников: контур v1 не
 * содержит авторизации и обслуживает одно настроенное рабочее пространство
 * (FR-002, принцип IV). Имя действующего лица показывается только там, где оно
 * означает атрибуцию созданного, — на карточках запусков и решений.
 */
export function AppLayout() {
  return (
    <div className="group flex min-h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-surface px-4">
        <span
          aria-hidden="true"
          className="flex size-7 items-center justify-center rounded bg-accent text-xs font-bold text-white"
        >
          AR
        </span>
        <Link to="/" className="text-base font-semibold text-ink">
          AI Review
        </Link>
        <span aria-hidden="true" className="h-7 w-px bg-line" />

        {/* Разделы стоят над левым краем контента: с открытой боковой панелью
            отступ равен её ширине, без панели вкладки уходят влево. */}
        <nav
          aria-label="Разделы"
          className="flex h-full items-stretch gap-10 group-has-[[data-side-panel]]:ml-80"
        >
          <NavLink
            to="/"
            className={({ isActive }) =>
              `relative flex items-center text-sm font-semibold ${
                isActive ? 'text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-[3px] after:bg-accent' : 'text-ink-muted'
              }`
            }
          >
            Ревью
          </NavLink>
          <span className="flex items-center text-sm font-semibold text-ink-muted">Профили</span>
        </nav>

        <div className="ml-auto flex items-center gap-4">
          <span className="text-xs text-ink-subtle">Статус AI-ревью</span>
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-canvas px-3 py-1 text-xs font-medium text-ink">
            <span aria-hidden="true" className="size-2 rounded-full bg-ink-subtle" />
            Не запущено
          </span>
        </div>
      </header>

      <div className="flex flex-1">
        <SectionRail />
        <div className="flex min-w-0 flex-1 flex-col">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

/** Левая панель разделов шириной 56px из макета. */
function SectionRail() {
  return (
    <nav aria-label="Основные разделы" className="flex w-14 shrink-0 flex-col items-center gap-2 bg-rail py-4">
      <Link
        to="/new"
        aria-label="Создать проверку"
        className="flex size-10 items-center justify-center rounded bg-surface text-accent"
      >
        <PlusIcon />
      </Link>
      <Link
        to="/"
        aria-label="Проверки"
        className="flex size-10 items-center justify-center rounded text-white hover:bg-rail-active"
      >
        <ClockIcon />
      </Link>
    </nav>
  );
}

const ICON_PROPS = {
  width: 20,
  height: 20,
  viewBox: '0 0 20 20',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const;

function PlusIcon() {
  return (
    <svg {...ICON_PROPS} strokeWidth={2}>
      <path d="M10 4v12M4 10h12" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6v4l2.5 2" />
    </svg>
  );
}

export default AppLayout;
