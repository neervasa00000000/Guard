# Conformance fixtures

[vectors.json](vectors.json) records the expected verdict and CLI exit code for each case. The checked-in [trust registry](trusted-keys.test.json) is for tests only.

`npm test` and `python3 tests/test_vectors.py` generate the two cases marked `generated` in temporary directories. They cover a GRD2 file over the 32 MiB limit and a valid high-entropy GRD2 image with 1,014 tiles. To create them under `conformance/files/` for another checker, install the repository's [Python dependencies](../requirements.txt) and run this command from the repository root.

```sh
python3 scripts/large_conformance_fixtures.py conformance/files
```
