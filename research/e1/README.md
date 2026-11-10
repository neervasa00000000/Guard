# E1 paper artifacts

This is the directory named in the TileSeal (repository Guard) IEEE Access manuscript's data-and-code statement. Guard is an [MIT-licensed repository](../../LICENSE). The archive DOI has not yet been issued.

| Artifact | Status in this directory |
|---|---|
| Publication and reproduction checklist | Present |
| E1 rendering, validation, and attack harness | Not yet added |
| Per-target CSVs and summaries | Not yet added |
| Figure generation scripts | Not yet added |
| Font-cluster statistics | Not yet added |
| Run logs and environment metadata | Not yet added |
| Input source URLs, licences, and SHA-256 receipts | Not yet added |

A local development harness exists on a separate branch. Its validation and smoke checks are development evidence. The full manuscript run, input receipts, and publication artifacts are pending.

Once the artifacts are published, run these commands from the repository root of the artifact commit. The paths below describe the planned layout and are pending with the harness:

```sh
python3 -m venv .venv-e1
.venv-e1/bin/python -m pip install -r research/e1/requirements.txt
bash research/e1/fetch_data.sh
.venv-e1/bin/python research/e1/render.py validate --n 304
.venv-e1/bin/python research/e1/run.py
.venv-e1/bin/python research/e1/plot.py
```

The manuscript tool revision is [`f8f2558`](https://github.com/neervasa00000000/Guard/commit/f8f2558a5f82bb99842781a0e3bc03fec39fd3c5), marked by `paper-v5.7`. Add the artifacts in a later commit and update the manuscript's data statement with that artifact revision and its archive DOI when issued. Preserve the original tool revision.
