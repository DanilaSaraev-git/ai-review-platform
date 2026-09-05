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
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-30 flex h-13 shrink-0 items-center gap-3 border-b border-line bg-surface px-3 shadow-[0_1px_2px_rgba(23,32,51,0.03)] md:px-4">
        <span
          aria-hidden="true"
          className="flex size-7 items-center justify-center rounded-[5px] bg-accent text-[11px] font-bold tracking-[-0.02em] text-white"
        >
          AR
        </span>
        <Link to="/" className="text-[15px] font-semibold tracking-[-0.01em] text-ink">
          AI Review
        </Link>
        <span aria-hidden="true" className="mx-1 h-6 w-px bg-line" />
        <nav aria-label="Разделы" className="flex h-full items-stretch">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `relative flex items-center px-2 text-[13px] font-semibold ${
                isActive ? 'text-ink after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-accent' : 'text-ink-muted hover:text-ink'
              }`
            }
          >
            Проверки
          </NavLink>
        </nav>
      </header>

      <div className="flex min-h-0 flex-1 pb-14 md:pb-0">
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
    <nav
      aria-label="Основные разделы"
      className="fixed inset-x-0 bottom-0 z-40 flex h-14 shrink-0 items-center justify-center gap-3 border-t border-rail-active bg-rail px-3 md:static md:h-auto md:w-12 md:flex-col md:justify-start md:border-t-0 md:px-0 md:py-3"
    >
      <Link
        to="/new"
        aria-label="Создать проверку"
        className="flex size-9 items-center justify-center rounded-[5px] bg-white text-accent shadow-sm transition-[background-color,transform] duration-100 active:scale-[0.96]"
      >
        <PlusIcon />
      </Link>
      <Link
        to="/"
        aria-label="Проверки"
        className="flex size-9 items-center justify-center rounded-[5px] text-white/90 transition-[background-color,transform] duration-100 hover:bg-rail-active active:scale-[0.96]"
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
