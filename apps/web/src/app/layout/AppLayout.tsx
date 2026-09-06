import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { Icon } from '@/components/ui/Icon';

/** Общая оболочка Numbat в настроенном рабочем пространстве. */
export function AppLayout() {
  const { pathname } = useLocation();
  const isNew = pathname === '/new';
  const currentPage = isNew ? 'Новая проверка' : pathname === '/' ? 'История' : 'Разбор ТЗ';
  return (
    <div className="numbat-app">
      <aside className="numbat-sidebar">
        <Link to="/" className="numbat-brand" aria-label="Numbat — история проверок">
          <span className="numbat-brand-mark"><img src="/numbat-icon.png" alt="" width="35" height="35" /></span>
          <span>Numbat</span>
        </Link>
        <nav className="numbat-navigation" aria-label="Основные разделы">
          <NavLink to="/new" aria-label="Создать проверку" className="numbat-nav-link"><Icon name="plus" />Новая проверка</NavLink>
          <Link to="/" className={`numbat-nav-link${!isNew ? ' active' : ''}`} aria-current={!isNew ? 'page' : undefined}>
            <Icon name="history" />История проверок
          </Link>
        </nav>
        <div className="numbat-workspace-label"><Icon name="layers" />Рабочее пространство</div>
      </aside>
      <div className="numbat-main">
        <header className="numbat-topbar">
          <nav aria-label="Разделы" className="numbat-breadcrumbs">
            <Link to="/">Проверки</Link><Icon name="chevron-right" size={12} /><span aria-current="page">{currentPage}</span>
          </nav>
        </header>
        <div className="numbat-route"><Outlet /></div>
      </div>
    </div>
  );
}
export default AppLayout;
