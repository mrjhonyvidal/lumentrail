# ✦ LumenTrail

**Follow the evidence.** A small, open source lab for retrieval, context, graph links, memory and evaluation. It returns passages with source IDs. It does not generate medical answers.

The default index is five **synthetic** passages. It runs offline with Python alone. The hash vector is a deterministic plumbing baseline, **not a semantic embedding**. Switch to BGE for real dense retrieval, and measure it against keyword and hybrid search before choosing a production stack.

## Start in two minutes

```bash
git clone https://github.com/mrjhonyvidal/lumentrail.git
cd lumentrail
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
lumentrail init
lumentrail search "What is AF?" --method hybrid
lumentrail eval --method hybrid
python -m unittest discover -s tests -v
```

To measure test coverage, install the test extra and run `coverage run -m unittest discover -s tests` followed by `coverage report -m`. Coverage describes exercised code paths; it is not a measure of retrieval or clinical quality.

Or run without installing: `PYTHONPATH=src python3 -m lumentrail init`.

The CLI prints a short brand line and JSON results. Its main commands are `init`, `fetch`, `import-csv`, `ingest`, `search`, `eval`, `memory`, `serve`, `sandbox`, `infra` and `repo`. Run `lumentrail --help` for arguments. The [notebook](notebooks/01_retrieval_lab.ipynb) walks through search and evaluation.

## Use public data

```bash
lumentrail fetch medquad --limit 200
lumentrail ingest data/medquad_passages.jsonl --embedding hash
lumentrail search "What is atrial fibrillation?"

pip install -e '.[models]'
lumentrail ingest data/medquad_passages.jsonl --embedding bge
lumentrail search "What is an irregular heartbeat?" --embedding bge --rerank
```

`fetch medquad` downloads the [original MedQuAD GitHub archive](https://github.com/abachaa/MedQuAD), keeps source links and skips missing answers. The original collection is CC BY 4.0 and credits Asma Ben Abacha and Dina Demner-Fushman. Three MedlinePlus subsets intentionally omit answers due to copyright. Downloaded data is ignored by Git. Check source date, clinical suitability and licence before using it beyond this lab. The Kaggle MedQuAD mirror and Hugging Face derivatives are alternatives; inspect their provenance and licence before substituting them.

If you obtain a QA CSV from [Kaggle's MedQuAD mirror](https://www.kaggle.com/datasets/pythonafroz/medquad-medical-question-answer-for-ai-research) or a [Hugging Face dataset](https://huggingface.co/datasets), adapt its actual column names explicitly:

```bash
lumentrail import-csv data/downloads/your-file.csv \
  --question-column question --answer-column answer \
  --source https://www.kaggle.com/datasets/pythonafroz/medquad-medical-question-answer-for-ai-research
lumentrail ingest data/imported_passages.jsonl --embedding hash
```

The CSV stays local. LumenTrail does not assume every mirror has the same fields, licence or answers. Its optional BGE model is downloaded from Hugging Face when you choose `--embedding bge`.

```bash
pip install -e '.[healthsearchqa]'
lumentrail fetch healthsearchqa --limit 50
```

This downloads the [HealthSearchQA supplementary workbook](https://www.nature.com/articles/s41586-023-06291-2) and writes **unlabelled questions**. It does not invent correct passages. Review each question against your current corpus, fill `relevant_ids`, then run `lumentrail eval data/your_reviewed_questions.jsonl`. Question only datasets cannot establish retrieval recall or clinical correctness on their own.

## What the code demonstrates

| Piece | Implementation | Lesson |
| --- | --- | --- |
| Keyword | SQLite FTS5 with BM25 | Acronyms and exact terms matter. |
| Dense | Exact cosine scan | Start with a measurable baseline. This is not an ANN engine. |
| Hybrid | Reciprocal rank fusion | Combine ranks without mixing incompatible raw scores. |
| Reranking | Optional MS MARCO cross encoder | Reorder a small candidate set; measure the cost. |
| Graph links | Explicit `entities` plus `--expand-entities` | Traversal is useful when relations matter. This is a small graph exercise, not automated GraphRAG. |
| Memory | User scoped, dated, expiring notes | Keep a journal separate from the public knowledge index. |
| Evals | Recall@k, precision@k and MRR | Freeze labels and compare changes on the same questions. |

The [BGE small English model](https://huggingface.co/BAAI/bge-small-en-v1.5) is a practical lightweight starting point, not a universal winner. The optional [MS MARCO MiniLM L6 cross encoder](https://www.sbert.net/docs/pretrained-models/ce-msmarco.html) was trained for general passages, not clinical adjudication. Test medical acronyms, dosage details, negation, language and source freshness on your own reviewed data. Changing the embedding model requires re-ingesting the index; the code rejects mixed model versions.

## A simple evaluation loop

1. Save questions and reviewed relevant passage IDs in JSONL. Include exact terms, paraphrases, stale passages, no-answer cases and permission boundaries.
2. Run `lumentrail eval --method keyword`, then `dense`, then `hybrid`, with the same `--limit` and corpus.
3. Inspect every miss in `cases`. Check chunking and labels before tuning models.
4. If you add generation, review each claim against its cited passage. Record unsupported claims, citation precision, abstentions, latency and cost separately. Do not treat retrieval recall as an answer-safety score.

No user or tenant access-control schema exists in this small public-data lab. Do **not** put private patient records into its knowledge index. The memory command is for synthetic notes only and stores local plaintext SQLite. It supports date-aware lookup and deletion, but is not a healthcare record system. Logs omit HTTP questions.

## Local read-only API

```bash
export LUMENTRAIL_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(36))')"
lumentrail serve
curl -H "Authorization: Bearer $LUMENTRAIL_API_TOKEN" \
  'http://127.0.0.1:8080/search?question=What%20is%20AF%3F'
```

Only `/search` is exposed. It requires a token, reads the database in SQLite read-only mode, caps query length and does not log questions. Bind outside localhost only behind a TLS proxy. Rotate the token and use cloud secret stores. This lab does not include a patient-facing answer generator.

`lumentrail sandbox` builds a container with the synthetic index and binds it to `127.0.0.1:8080`. It needs Docker and the token above. The image runs as a non-root user with a read-only filesystem at runtime. Build your own image and push it to a registry before using Terraform.

## Cloud and Raspberry Pi examples

Each `infra/` folder has `terraform.tfvars.example`. Copy it to a private `.tfvars` file, supply an **existing** secret and image, then run:

```bash
lumentrail infra gcp plan --var-file infra/gcp/terraform.tfvars
lumentrail infra gcp apply --var-file infra/gcp/terraform.tfvars --approve
```

Replace `gcp` with `aws`, `azure` or `pi`. `apply` and `destroy` require `--approve`. Review a plan first. Terraform may charge for created resources. The CLI never creates cloud credentials or stores a token in Terraform state.

- **GCP:** Cloud Run with internal ingress, a dedicated service account and an existing Secret Manager token. Give invoker access only to approved callers.
- **AWS:** Fargate task in existing private subnets, ingress from one approved security group, Secrets Manager token and short CloudWatch retention. Provide NAT or the required VPC endpoints so the task can pull its image, read its secret and write logs. Connect from within the VPC.
- **Azure:** Container App in an existing internal environment, Key Vault reference through a user assigned identity and internal ingress. Give the identity secret read access and the image pull role needed by your registry.
- **Raspberry Pi:** Terraform uses SSH with strict host-key checking to restart a container from an existing registry image. Put the token in `/etc/lumentrail/api.env` on the Pi with restricted permissions. The port stays on loopback; use the output SSH tunnel to reach it. Use an ARM64 image.

These are **private demo deployments**, not a complete production platform. For real use, add your organisation's network path, identity, monitoring, durable storage and tenant permissions, then threat-model the full path. Cloud images contain only the synthetic index. Real embeddings are not baked into the default container.

## Agent context and a local Git repository

Codex and Claude Code can read [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md). They describe the evidence boundary and the test command. Keep retrieved text as data, not agent instructions; never add private health notes to prompts without a clear user action.

```bash
lumentrail repo init
git add .
git commit -m "Initial LumenTrail lab"
lumentrail repo publish --name lumentrail
```

Publishing uses GitHub CLI after authentication. It is separate from the site repository. Add a remote yourself if you prefer another host.

## Layout

```text
src/lumentrail/   CLI, data import, retrieval, evals, memory and API
tests/            Offline behaviour checks
notebooks/        Short worked experiments
infra/            GCP, AWS, Azure and Raspberry Pi examples
data/             Generated local files, ignored where sensitive or large
```

Software is MIT licensed. Public datasets retain their own licences and attribution.
