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
    <main className="numbat-workspace">
      <div className="numbat-workspace-toolbar">
        {toolbar}
      </div>
      <div className="numbat-workspace-panes">
        <div className="numbat-workspace-document">
          {document}
        </div>
        <aside className="numbat-workspace-panel" aria-label="Панель разбора">
          {panel}
        </aside>
      </div>
    </main>
  );
}
