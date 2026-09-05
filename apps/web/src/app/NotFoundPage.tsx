import { Link } from 'react-router';

/**
 * Обычное «не найдено».
 *
 * workspaceId в URL — namespace, а не доказательство доступа, поэтому чужой
 * идентификатор выглядит как отсутствие ресурса. Никаких упоминаний входа,
 * прав и доступа (FR-003, принцип IV).
 */
export function NotFoundPage({ detail }: { detail?: string }) {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-xl font-semibold text-ink">Не найдено</h1>
      <p className="mt-2 text-ink-muted">
        {detail ?? 'Такой страницы или ресурса нет. Возможно, ссылка устарела или идентификатор указан неверно.'}
      </p>
      <p className="mt-6">
        <Link className="text-accent underline" to="/">
          К списку проверок
        </Link>
      </p>
    </main>
  );
}

export default NotFoundPage;
