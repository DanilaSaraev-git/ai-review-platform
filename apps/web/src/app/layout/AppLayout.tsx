import { Link, Outlet } from 'react-router';

/**
 * Каркас страницы.
 *
 * В шапке нет элементов аккаунта, выхода, ролей и участников: контур v1 не
 * содержит авторизации и обслуживает одно настроенное рабочее пространство
 * (FR-002, принцип IV). Имя действующего лица показывается только там, где оно
 * означает атрибуцию созданного, — на карточках запусков и решений.
 */
export function AppLayout() {
  return (
    <div className="min-h-screen bg-surface-muted">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3">
          <span
            aria-hidden="true"
            className="flex size-7 items-center justify-center rounded bg-accent text-xs font-bold text-white"
          >
            AR
          </span>
          <Link to="/" className="text-base font-semibold text-ink">
            AI Review
          </Link>
          <span className="text-sm text-ink-muted">предварительное ревью ТЗ на данные</span>
        </div>
      </header>

      <Outlet />

      <footer className="mx-auto max-w-7xl px-6 py-8 text-xs text-ink-muted">
        Замечания — кандидаты на уточнение, а не подтверждённые дефекты. Итоговое решение по каждому принимает аналитик.
      </footer>
    </div>
  );
}

export default AppLayout;
