# LumenTrail

A customer asks when a refund will arrive. The answer is in a policy document, but the assistant finds a page about returning an item instead. Writing a more polished reply will not fix the missing information.

**LumenTrail is a small Python lab for checking whether document search finds the evidence an AI assistant needs.** Give it a question and some text passages. It returns matching passages with their sources, then lets you compare them with the passages you expected.

Use it before connecting search to an AI answer writer, or when a change to your documents makes answers worse. Engineers can compare search methods; product owners can read the questions and sources to decide what counts as a useful result. The project keeps that search decision visible instead of hiding it inside a finished answer.

## Run the demo

The bundled example uses five fictional health-related passages and three saved test questions. They keep the source text small enough to inspect by hand; they are not a medical knowledge base. The refund-policy situation above explains the same search problem in a different setting. You can replace the passages with your own prepared text later.

You run the demo in your terminal, with no web interface or AI account needed.

```bash
git clone https://github.com/mrjhonyvidal/lumentrail.git
cd lumentrail
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
lumentrail init
lumentrail search "What is asthma?" --method keyword --limit 1
lumentrail eval --method keyword --limit 2
python -m unittest discover -s tests -v
```

**You need:** Python 3.11 or newer. Allow about five minutes on a laptop. Internet is needed for installation; the example itself runs offline. **Account: none. Estimated service cost: £0.** This excludes your laptop and electricity.

The search should return one passage with ID `demo-asthma`, its original text and source `synthetic-demo`. This is a saved example being found, not a newly generated answer.

The evaluation checks three questions against their expected passage IDs. Look at `cases` to see the expected and returned IDs for each question. All three expected passages should appear within the first two results. The tests should pass. These small examples check that the project works; they do not establish how well it will search your documents.

## What you can use it for

- **Compare search methods:** search by keywords, try an optional model that compares text by meaning, or combine both methods.
- **Check whether a change helps:** keep the same questions and expected sources, change the search method, then inspect what improved or went missing.
- **Build on the search code:** load your own text records and reuse the Python functions or local HTTP API in another application. You prepare the text first; the project does not import PDF or Word files directly.

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
