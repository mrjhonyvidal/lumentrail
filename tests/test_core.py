import tempfile
import unittest
import zipfile
from pathlib import Path

from lumentrail.datasets import DEMO_JUDGEMENTS, DEMO_PASSAGES, csv_passages, medquad_records
from lumentrail.embedding import HashEmbedder
from lumentrail.evaluation import evaluate
from lumentrail.memory import add_note, delete_notes, list_notes
from lumentrail.retrieval import search
from lumentrail.storage import connect, replace_passages


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
