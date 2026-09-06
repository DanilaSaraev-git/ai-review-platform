import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { Icon } from '@/components/ui/Icon';
import { appBaseUrl, DEMO_NOTICE, isDemoMode } from '@/app/demo-mode';

/** Общая оболочка Numbat в настроенном рабочем пространстве. */
export function AppLayout() {
  const { pathname } = useLocation();
  const isNew = pathname === '/new';
  const isDocuments = pathname.startsWith('/documents');
  const currentPage = isNew ? 'Новая проверка' : isDocuments ? 'Документы' : pathname === '/' ? 'История' : 'Разбор ТЗ';
  return (
    <div className="numbat-app">
      <aside className="numbat-sidebar">
        <Link to="/" className="numbat-brand" aria-label="Numbat — история проверок">
          <span className="numbat-brand-mark"><img src={`${appBaseUrl}numbat-icon.png`} alt="" width="35" height="35" /></span>
          <span>Numbat</span>
        </Link>
        <nav className="numbat-navigation" aria-label="Основные разделы">
          <NavLink to="/new" aria-label="Создать проверку" className="numbat-nav-link"><Icon name="plus" />Новая проверка</NavLink>
          {!isDemoMode ? <NavLink to="/documents" className="numbat-nav-link"><Icon name="file-text" />Документы</NavLink> : null}
          <Link to="/" className={`numbat-nav-link${!isNew && !isDocuments ? ' active' : ''}`} aria-current={!isNew && !isDocuments ? 'page' : undefined}>
            <Icon name="history" /><span className="sm:hidden">История</span><span className="hidden sm:inline">История проверок</span>
          </Link>
        </nav>
        <div className="numbat-workspace-label"><Icon name="layers" />Рабочее пространство</div>
      </aside>
      <div className="numbat-main">
        <header className="numbat-topbar">
          <nav aria-label="Разделы" className="numbat-breadcrumbs">
            <Link to="/">Проверки</Link><Icon name="chevron-right" size={12} /><span aria-current="page">{currentPage}</span>
          </nav>
          <a href={isDemoMode ? '/' : '/demo/new'} className="ml-auto pl-3 text-xs font-medium text-accent hover:underline">
            {isDemoMode ? 'К рабочему сервису' : 'Деморежим'}
          </a>
        </header>
        {isDemoMode ? (
          <aside aria-label="Демонстрационный режим" className="shrink-0 border-b border-line bg-accent-tint px-5 py-2 text-xs leading-relaxed text-ink">
            <strong className="mr-2 font-medium text-accent">Деморежим · без модели</strong>
            {DEMO_NOTICE} Диалог содержит готовые ответы. Решения сохраняются только в этой вкладке.
          </aside>
        ) : null}
        <div className="numbat-route"><Outlet /></div>
      </div>
    </div>
  );
}
export default AppLayout;
