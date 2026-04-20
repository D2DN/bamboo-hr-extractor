# bamboo-hr-extractor

Extract candidate data from BambooHR ATS via API.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

## Configuration

All parameters can be set via `.env` file **or** CLI flags:

| Env var | CLI flag | Default | Description |
| --- | --- | --- | --- |
| `BAMBOO_API_KEY` | `--api-key` | — | BambooHR API key |
| `BAMBOO_COMPANY_DOMAIN` | `--domain` | — | Company subdomain (e.g. `cerbexa`) |
| `BAMBOO_APPLICATION_STATUS` | `--status` | `ALL` | `NEW` · `ACTIVE` · `INACTIVE` · `HIRED` · `ALL` · `ALL_ACTIVE` |
| `BAMBOO_JOB_ID` | `--job-id` | — | Filter by exact job ID |
| `BAMBOO_JOB_TITLE` | `--job-title` | — | Filter by job title (partial match, case-insensitive, overrides `--job-id`) |
| `BAMBOO_NEW_SINCE` | `--new-since` | — | Filter from date `YYYY-MM-DD HH:MM:SS` |
| `BAMBOO_OUTPUT_FORMAT` | `--format` | `csv` | `csv` or `json` |
| `BAMBOO_OUTPUT_FILE` | `--output` | `candidates_export` | Output filename (without extension) |
| `BAMBOO_RESUMES_DIR` | `--resumes-dir` | — | Folder to save downloaded CVs (skipped if not set) |
| — | `--demo` | `false` | Limit output to 10 candidates |

## Usage

Extract all candidates (uses `.env` config):

```bash
python3 main.py extract
```

Demo mode — limit to 10 candidates:

```bash
python3 main.py extract --demo
```

Override options via CLI:

```bash
python3 main.py extract --status ACTIVE --format json
```

Download CVs into a local folder:

```bash
python3 main.py extract --resumes-dir ./resumes
```

Filter by job title (partial match):

```bash
python3 main.py extract --job-title "Développeur(euse) React Native"
```

List available jobs (to find title keywords or IDs):

```bash
python3 main.py list-jobs
```

## Web UI

Start the local server:

```bash
python3 server.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## API Key

Generate your API key in BambooHR: click your name (bottom-left) -> **API Keys**.

The key owner must have **ATS settings access** to retrieve candidate data.
