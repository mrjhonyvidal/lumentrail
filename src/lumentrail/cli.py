"""One entry point for data, experiments, a local API and infrastructure."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from .api import serve
from .datasets import (DEMO_JUDGEMENTS, DEMO_PASSAGES, HEALTHSEARCHQA_WORKBOOK,
                       MEDQUAD_ARCHIVE, csv_passages, download, healthsearchqa_records,
                       medquad_records, read_jsonl, write_jsonl)
from .embedding import make_embedder
from .evaluation import evaluate
from .memory import add_note, delete_notes, list_notes
from .retrieval import search
from .storage import connect, replace_passages

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = Path("data/lumentrail.db")


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="lumentrail", description="✦ LUMENTRAIL | Follow the evidence")
    command.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    actions = command.add_subparsers(dest="action", required=True)
    actions.add_parser("init", help="Create a tiny offline teaching index and judgements")

    fetch = actions.add_parser("fetch", help="Download and prepare a public dataset")
    fetch.add_argument("dataset", choices=["medquad", "healthsearchqa"])
    fetch.add_argument("--limit", type=int, default=200)

    import_csv = actions.add_parser("import-csv", help="Adapt a downloaded Kaggle or Hugging Face QA CSV")
    import_csv.add_argument("path", type=Path)
    import_csv.add_argument("--question-column", required=True)
    import_csv.add_argument("--answer-column", required=True)
    import_csv.add_argument("--source", required=True, help="Dataset or source URL for attribution")
    import_csv.add_argument("--output", type=Path, default=Path("data/imported_passages.jsonl"))

    ingest = actions.add_parser("ingest", help="Replace the index with JSONL passages")
    ingest.add_argument("path", type=Path)
    ingest.add_argument("--embedding", choices=["hash", "bge"], default="hash")

    query = actions.add_parser("search", help="Inspect retrieved evidence")
    query.add_argument("question")
    query.add_argument("--embedding", choices=["hash", "bge"], default="hash")
    query.add_argument("--method", choices=["keyword", "dense", "hybrid"], default="hybrid")
    query.add_argument("--limit", type=int, default=3)
    query.add_argument("--rerank", action="store_true")
    query.add_argument("--expand-entities", action="store_true")

    evaluation = actions.add_parser("eval", help="Measure retrieval with reviewed relevance labels")
    evaluation.add_argument("judgements", type=Path, nargs="?", default=Path("data/demo_judgements.jsonl"))
    evaluation.add_argument("--embedding", choices=["hash", "bge"], default="hash")
    evaluation.add_argument("--method", choices=["keyword", "dense", "hybrid"], default="hybrid")
    evaluation.add_argument("--limit", type=int, default=3)

    memory = actions.add_parser("memory", help="Opt-in, user-scoped synthetic journal notes")
    memory.add_argument("operation", choices=["add", "list", "delete"])
    memory.add_argument("person")
    memory.add_argument("note", nargs="?")
    memory.add_argument("--valid-at", default=date.today().isoformat())
    memory.add_argument("--expires-at")

    server = actions.add_parser("serve", help="Start a token-protected read-only API")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)
    server.add_argument("--embedding", choices=["hash", "bge"], default="hash")

    sandbox = actions.add_parser("sandbox", help="Build and run the local read-only container")
    sandbox.add_argument("--port", type=int, default=8080)

    infrastructure = actions.add_parser("infra", help="Run Terraform for a cloud or Pi target")
    infrastructure.add_argument("provider", choices=["aws", "gcp", "azure", "pi"])
    infrastructure.add_argument("operation", choices=["init", "validate", "plan", "apply", "destroy"])
    infrastructure.add_argument("--var-file", type=Path)
    infrastructure.add_argument("--approve", action="store_true")

    repository = actions.add_parser("repo", help="Initialise or publish this standalone Git repository")
    repository.add_argument("operation", choices=["init", "publish"])
    repository.add_argument("--name", default="lumentrail")
    return command


def main() -> None:
    arguments = parser().parse_args()
    print("✦ LUMENTRAIL  |  follow the evidence", file=sys.stderr)
    try:
        execute(arguments)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def execute(arguments: argparse.Namespace) -> None:
    if arguments.action == "init":
        write_jsonl(Path("data/demo_passages.jsonl"), DEMO_PASSAGES)
        write_jsonl(Path("data/demo_judgements.jsonl"), DEMO_JUDGEMENTS)
        with connect(arguments.database) as connection:
            embedder = make_embedder("hash")
            texts = [f'{item["question"]} {item["answer"]}' for item in DEMO_PASSAGES]
            replace_passages(connection, DEMO_PASSAGES, embedder.encode(texts), embedder.name)
        print("Ready: five synthetic passages, three judgements, offline hash baseline.")
        return
    if arguments.action == "fetch":
        if arguments.limit < 1:
            raise ValueError("Limit must be positive")
        folder = Path("data/downloads")
        if arguments.dataset == "medquad":
            archive = folder / "medquad-master.zip"
            if not archive.exists():
                download(MEDQUAD_ARCHIVE, archive)
            records = medquad_records(archive, arguments.limit)
            destination = Path("data/medquad_passages.jsonl")
        else:
            archive = folder / "healthsearchqa.xlsx"
            if not archive.exists():
                download(HEALTHSEARCHQA_WORKBOOK, archive)
            records = healthsearchqa_records(archive, arguments.limit)
            destination = Path("data/healthsearchqa_unlabelled.jsonl")
        write_jsonl(destination, records)
        print(f"Wrote {len(records)} records to {destination}")
        return
    if arguments.action == "import-csv":
        records = csv_passages(arguments.path, arguments.question_column,
                               arguments.answer_column, arguments.source)
        if not records:
            raise ValueError("No complete question and answer rows found")
        write_jsonl(arguments.output, records)
        print(f"Wrote {len(records)} passages to {arguments.output}")
        return
    if arguments.action == "ingest":
        records = read_jsonl(arguments.path)
        if not records:
            raise ValueError("No passages found")
        for record in records:
            if not all(record.get(field) for field in ("id", "question", "answer", "source")):
                raise ValueError("Each passage needs id, question, answer and source")
        embedder = make_embedder(arguments.embedding)
        texts = [f'{record["question"]} {record["answer"]}' for record in records]
        embeddings = embedder.encode(texts)
        with connect(arguments.database) as connection:
            replace_passages(connection, records, embeddings, embedder.name)
        print(f"Indexed {len(records)} passages with {embedder.name}")
        return
    if arguments.action in {"search", "eval"}:
        embedder = make_embedder(arguments.embedding)
        with connect(arguments.database) as connection:
            if arguments.action == "search":
                result = search(connection, arguments.question, embedder, method=arguments.method,
                                limit=arguments.limit, rerank=arguments.rerank,
                                expand_entities=arguments.expand_entities)
            else:
                result = evaluate(connection, read_jsonl(arguments.judgements), embedder,
                                  method=arguments.method, limit=arguments.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if arguments.action == "memory":
        with connect(arguments.database) as connection:
            if arguments.operation == "add":
                if not arguments.note:
                    raise ValueError("Provide a note")
                result = {"id": add_note(connection, arguments.person, arguments.note,
                                         arguments.valid_at, arguments.expires_at)}
            elif arguments.operation == "list":
                result = list_notes(connection, arguments.person, arguments.valid_at)
            else:
                result = {"deleted": delete_notes(connection, arguments.person)}
        print(json.dumps(result, indent=2))
        return
    if arguments.action == "serve":
        serve(arguments.database, arguments.host, arguments.port, arguments.embedding)
        return
    if arguments.action == "sandbox":
        token = os.environ.get("LUMENTRAIL_API_TOKEN", "")
        if len(token) < 32:
            raise ValueError("Set LUMENTRAIL_API_TOKEN to at least 32 random characters")
        run(["docker", "build", "-t", "lumentrail:local", "."], cwd=PROJECT_ROOT)
        run(["docker", "run", "--rm", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
             "-p", f"127.0.0.1:{arguments.port}:8080", "-e", "LUMENTRAIL_BEHIND_TLS_PROXY=1",
             "-e", "LUMENTRAIL_API_TOKEN", "lumentrail:local"])
        return
    if arguments.action == "infra":
        directory = PROJECT_ROOT / "infra" / arguments.provider
        if arguments.operation in {"apply", "destroy"} and not arguments.approve:
            raise ValueError("Pass --approve after reviewing a Terraform plan")
        if arguments.operation != "init":
            run(["terraform", "-chdir=" + str(directory), "init", "-input=false"])
        command = ["terraform", "-chdir=" + str(directory), arguments.operation]
        if arguments.operation in {"plan", "apply", "destroy"}:
            command.append("-input=false")
            if arguments.var_file:
                command.extend(["-var-file", str(arguments.var_file.resolve())])
            if arguments.approve and arguments.operation in {"apply", "destroy"}:
                command.append("-auto-approve")
        run(command)
        return
    if arguments.action == "repo":
        if arguments.operation == "init":
            run(["git", "init", "-b", "main"], cwd=PROJECT_ROOT)
        else:
            run(["gh", "auth", "status"], cwd=PROJECT_ROOT)
            run(["gh", "repo", "create", arguments.name, "--public", "--source", ".", "--push"], cwd=PROJECT_ROOT)


if __name__ == "__main__":
    main()
