from __future__ import annotations

import procrastinate


def create_procrastinate_app(database_url: str) -> procrastinate.App:
    connector = procrastinate.PsycopgConnector(
        conninfo=database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    )
    return procrastinate.App(connector=connector)


class ProcrastinateQueue:
    def __init__(self, app: procrastinate.App) -> None:
        self.app = app

    async def publish(self, task_name: str, payload: dict[str, object]) -> int:
        task = self.app.tasks.get(task_name)
        if task is None:
            raise ValueError("unknown queue task")
        return await task.defer_async(**payload)
