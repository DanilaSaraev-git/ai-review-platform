import type { ReactNode } from 'react';

export function ReviewWorkspace({
  toolbar,
  document,
  panel,
}: {
  toolbar: ReactNode;
  document: ReactNode;
  panel: ReactNode;
}) {
  return (
    <main className="flex min-h-0 flex-1 flex-col bg-canvas">
      <div className="sticky top-13 z-20 flex min-h-15 flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-2.5 sm:px-5 lg:static">
        {toolbar}
      </div>
      <div className="grid min-h-0 flex-1 lg:h-0 lg:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)] lg:overflow-hidden">
        <div className="min-w-0 border-b border-line bg-[#eef0f3] p-3 sm:p-5 lg:min-h-0 lg:overflow-auto lg:border-b-0 lg:border-r">
          {document}
        </div>
        <aside className="min-w-0 bg-surface lg:min-h-0 lg:overflow-hidden" aria-label="Панель разбора">
          {panel}
        </aside>
      </div>
    </main>
  );
}
