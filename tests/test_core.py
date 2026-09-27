import contextlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from lumentrail import cli
from lumentrail.api import serve
from lumentrail.chunking import fixed_character_chunks, paragraph_chunks
from lumentrail.datasets import DEMO_JUDGEMENTS, DEMO_PASSAGES, csv_passages, medquad_records
from lumentrail.embedding import HashEmbedder
from lumentrail.evaluation import evaluate
from lumentrail.memory import add_note, delete_notes, list_notes
from lumentrail.retrieval import search
from lumentrail.storage import all_passages, connect, keyword_search, replace_passages


class RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.connection = connect(Path(self.folder.name) / "index.db")
        self.embedder = HashEmbedder()
        texts = [f'{item["question"]} {item["answer"]}' for item in DEMO_PASSAGES]
        replace_passages(self.connection, DEMO_PASSAGES, self.embedder.encode(texts), self.embedder.name)

    def tearDown(self):
        self.connection.close()
        self.folder.cleanup()

    def test_hybrid_finds_acronym_and_evaluates(self):
        hits = search(self.connection, "What is AF?", self.embedder)
        self.assertEqual(hits[0]["id"], "demo-af")
        report = evaluate(self.connection, DEMO_JUDGEMENTS, self.embedder, method="hybrid", limit=3)
        self.assertEqual(report["questions"], 3)
        self.assertGreater(report["recall_at_k"], 0)

    def test_memory_is_scoped_and_expires(self):
        add_note(self.connection, "demo-a", "Synthetic allergy note", "2026-01-01", "2026-02-01")
        self.assertEqual(len(list_notes(self.connection, "demo-a", "2026-01-15")), 1)
        self.assertEqual(list_notes(self.connection, "demo-a", "2026-03-01"), [])
        self.assertEqual(list_notes(self.connection, "demo-b", "2026-01-15"), [])
        self.assertEqual(delete_notes(self.connection, "demo-a"), 1)

    def test_entity_expansion_adds_a_linked_passage(self):
        passages = DEMO_PASSAGES + [{"id": "linked-note", "question": "What can feel like a flutter?",
                                    "answer": "A racing or fluttering feeling may be noticed.",
                                    "source": "synthetic-demo", "entities": ["atrial fibrillation"]}]
        texts = [f'{item["question"]} {item["answer"]}' for item in passages]
        replace_passages(self.connection, passages, self.embedder.encode(texts), self.embedder.name)
        direct = search(self.connection, "AF", self.embedder, method="keyword", limit=3)
        expanded = search(self.connection, "AF", self.embedder, method="keyword", limit=3,
                          expand_entities=True)
        self.assertNotIn("linked-note", [hit["id"] for hit in direct])
        self.assertIn("linked-note", [hit["id"] for hit in expanded])

    def test_embedding_version_mismatch_is_rejected(self):
        self.embedder.name = "changed"
        with self.assertRaises(ValueError):
            search(self.connection, "asthma", self.embedder)

    def test_eval_reports_known_ranks_and_rejects_unlabelled_questions(self):
        report = evaluate(self.connection, [
            {"question": "What is AF?", "relevant_ids": ["demo-af"]},
            {"question": "What is an absent topic?", "relevant_ids": ["missing"]},
        ], self.embedder, method="keyword", limit=1)
        self.assertEqual(report["questions"], 2)
        self.assertEqual(report["recall_at_k"], 0.5)
        self.assertEqual(report["precision_at_k"], 0.5)
        self.assertEqual(report["mean_reciprocal_rank"], 0.5)
        with self.assertRaisesRegex(ValueError, "No reviewed relevance labels"):
            evaluate(self.connection, [{"question": "Unknown?", "relevant_ids": []}],
                     self.embedder, method="hybrid", limit=3)

    def test_reingest_removes_retired_passages_from_both_indexes(self):
        replacement = [{"id": "new", "question": "What is a new topic?",
                        "answer": "A new passage.", "source": "synthetic-demo"}]
        vectors = self.embedder.encode(["What is a new topic? A new passage."])
        replace_passages(self.connection, replacement, vectors, self.embedder.name)
        self.assertEqual([passage["id"] for passage in all_passages(self.connection)], ["new"])
        self.assertEqual(keyword_search(self.connection, "asthma", 3), [])

    def test_search_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            search(self.connection, "", self.embedder)
        with self.assertRaises(ValueError):
            search(self.connection, "AF", self.embedder, limit=21)
        with self.assertRaises(ValueError):
            search(self.connection, "AF", self.embedder, method="unknown")

    def test_chunking_preserves_reviewed_paragraphs(self):
        source = "A short heading.\n\nKeep the caution beside the fact.\n\nAnother topic."
        self.assertEqual("".join(fixed_character_chunks(source, 12)), source)
        self.assertEqual(paragraph_chunks(source, 35),
                         ["A short heading.", "Keep the caution beside the fact.", "Another topic."])
        with self.assertRaisesRegex(ValueError, "review its boundary"):
            paragraph_chunks(source, 12)
        with self.assertRaises(ValueError):
            fixed_character_chunks(source, 0)

    def test_cli_initialises_searches_and_evaluates_a_local_index(self):
        previous_directory = Path.cwd()
        database = Path(self.folder.name) / "cli.db"
        try:
            os.chdir(self.folder.name)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                cli.execute(cli.parser().parse_args(["--database", str(database), "init"]))
                cli.execute(cli.parser().parse_args(["--database", str(database),
                                                     "search", "What is AF?", "--method", "hybrid"]))
            self.assertIn('"id": "demo-af"', output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                cli.execute(cli.parser().parse_args(["--database", str(database),
                                                     "eval", "--method", "hybrid"]))
            self.assertEqual(json.loads(output.getvalue())["questions"], 3)
        finally:
            os.chdir(previous_directory)

    def test_api_refuses_weak_token_and_external_bind_without_proxy(self):
        with mock.patch.dict(os.environ, {"LUMENTRAIL_API_TOKEN": "short"}):
            with self.assertRaisesRegex(ValueError, "at least 32"):
                serve(Path(self.folder.name) / "index.db", "127.0.0.1", 8080, "hash")
        with mock.patch.dict(os.environ, {"LUMENTRAIL_API_TOKEN": "a" * 40}, clear=True):
            with self.assertRaisesRegex(ValueError, "TLS reverse proxy"):
                serve(Path(self.folder.name) / "index.db", "0.0.0.0", 8080, "hash")

    def test_medquad_import_skips_missing_answers_and_preserves_source(self):
        archive = Path(self.folder.name) / "fixture.zip"
        xml = b'''<Document url="https://example.org/topic"><QAPairs>
            <QAPair><Question>What is AF?</Question><Answer>An irregular rhythm.</Answer></QAPair>
            <QAPair><Question>What is X?</Question><Answer></Answer></QAPair>
        </QAPairs></Document>'''
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("MedQuAD-master/1_CancerGov_QA/example.xml", xml)
        records = medquad_records(archive)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "https://example.org/topic")

    def test_csv_import_requires_explicit_columns_and_source(self):
        path = Path(self.folder.name) / "sample.csv"
        path.write_text("prompt,response\nWhat is AF?,An irregular rhythm.\n", encoding="utf-8")
        records = csv_passages(path, "prompt", "response", "https://example.org/dataset")
        self.assertEqual(records[0]["source"], "https://example.org/dataset")
        with self.assertRaises(ValueError):
            csv_passages(path, "question", "answer", "https://example.org/dataset")


if __name__ == "__main__":
    unittest.main()
