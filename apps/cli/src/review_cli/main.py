from __future__ import annotations

import typer

from review_cli.commands.api_smoke import api_smoke, verify_evidence
from review_cli.commands.contract_smoke import contract_smoke
from review_cli.commands.model_smoke import model_smoke
from review_cli.commands.poc import read_poc
from review_cli.commands.review import review

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
app.command("review")(review)
app.command("contract-smoke")(contract_smoke)
app.command("read-poc-v1")(read_poc)
app.command("api-smoke")(api_smoke)
app.command("verify-evidence")(verify_evidence)
app.command("model-smoke")(model_smoke)


def main() -> None:
    app()
