# LumenTrail

Search a small collection of passages and check whether the right evidence comes back. Start with five made-up passages, then try your own documents. The project helps you understand search before adding an AI answer writer.

```bash
git clone https://github.com/mrjhonyvidal/lumentrail.git
cd lumentrail
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
lumentrail init
lumentrail search "What is AF?" --method keyword
lumentrail eval --method keyword --limit 2
python -m unittest discover -s tests -v
```

**You need:** Python 3.11 or newer. Allow about five minutes on a laptop. Internet is needed for installation; the example itself runs offline. **Account: none. Estimated service cost: £0.** This excludes your laptop and electricity.

You should see passages with source IDs, then an evaluation report with `recall_at_k`, `precision_at_k` and `mean_reciprocal_rank`. The tests should pass. A high score on five made-up passages only checks that the example works.

## If setup gets stuck

- Check `python3 --version`. On Windows, use `py -3` to create the environment and `.venv\Scripts\Activate.ps1` in PowerShell to activate it.
- Without installing the package, run `PYTHONPATH=src python3 -m lumentrail init` on macOS or Linux. Replace `init` with the other commands above as needed.
- Run commands from the project folder. `init` writes the demo index into `data/`; use it to reset the learning example.

## Try one change

Run the same question with `--method dense`, then `--method hybrid`. Dense search compares numeric representations of text; hybrid search combines keyword and dense results. The default numeric representation hashes words. It is a plumbing example and does not understand meaning.

Next, edit a copy of `data/demo_judgements.jsonl` and inspect which passage IDs your questions should find. Keep those judgements fixed while comparing search methods. The [retrieval notebook](notebooks/01_retrieval_lab.ipynb) walks through the same experiment.

## Choose a next step

| I want to... | Start here |
| --- | --- |
| Use my own passages or a public dataset | [Data import](docs/guide.md#use-public-data) |
| Try a real text embedding model | [Optional BGE model](docs/guide.md#use-public-data) |
| Understand the search methods | [Implementation map](docs/guide.md#what-the-code-demonstrates) |
| Try dated notes or chunking | [Learning path](docs/guide.md#follow-the-learning-path) |
| Call search over HTTP | [Local API](docs/guide.md#local-read-only-api) |
| Explore Docker, cloud or a Raspberry Pi | [Deployment examples](docs/guide.md#cloud-and-raspberry-pi-examples) |

The optional local model has no API charge, but downloads model files and uses more memory and compute. Cloud resources are separate, billable experiments. Nothing in the quick start creates them.

## What to read in the code

`src/lumentrail/retrieval.py` finds passages, `evaluation.py` compares them with reviewed IDs, and `chunking.py` splits text. `tests/test_core.py` shows the expected behaviour. Keep the public index separate from the optional personal-note store.

Health-related passages in the demo are synthetic. This lab returns evidence, not medical answers. Use public or made-up data while learning; the project has no tenant access controls for private records.

[Blog walkthrough](https://trailblazergarage.com/how-to-evaluate-rag-without-fooling-yourself/) · [Further experiments](docs/guide.md) · [MIT licence](LICENSE)
