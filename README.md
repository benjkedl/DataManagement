# DataManagement

## MedHub API Ingestion

The repository includes `medhub_fetch.py`, a standalone helper to ingest data
from the MedHub REST API into pandas DataFrames.

### Prerequisites

- Python 3.10+
- `pip install pandas requests urllib3`

### Quick start

1. Export your MedHub credentials:

   ```bash
   export MEDHUB_BASE_URL="https://api.medhub.com"
   export MEDHUB_CLIENT_ID="your-client-id"
   export MEDHUB_CLIENT_SECRET="your-client-secret"
   ```

2. Fetch one or more endpoints:

   ```bash
   python medhub_fetch.py v1/trainees v1/evaluations --output-dir data/
   ```

   The script retrieves each endpoint, flattens the JSON payload with
   `pandas.json_normalize`, and saves the resulting DataFrame(s) as CSV in the
   specified directory. Use `--output-format parquet` or `--output-format json`
   to change the output format.

3. For ad-hoc inspection without saving to disk, omit `--output-dir` and review
   the preview printed to stdout.

### Advanced options

- `--param key=value` to append custom query parameters (repeatable)
- `--max-pages` to limit pagination during exploratory runs
- `--record-path` and `--meta` to tailor `pandas.json_normalize` for nested
  structures
- `--no-normalize` to obtain the raw JSON objects as DataFrame rows

Run `python medhub_fetch.py --help` for the full list of supported flags.
