# Bank Statement Distribution

Automated, single-trigger workflow that emails bank statements to financiers as
**direct attachments** (no Drive links, no external URLs — works with locked-down
financier IT).

It replaces the 2–4 hour manual cycle:

| Manual step today | Automated here |
|---|---|
| Download statements one by one from each bank folder | Pulls the latest files from Drive via the API |
| Regroup files by entity (Drive is organised by bank) | Regroups by **entity** automatically |
| Compress & split to stay under the 25 MB email cap | Zips and bin-packs into multiple `<25 MB` zips/emails |
| Send multiple emails to each financier | Sends per-financier emails via the Gmail API |
| Repeat every month | One scheduled trigger; re-reads "latest" each run |

**Adding a financier** = add one entry to `config.yaml`. No code changes.

---

## How it works

```
Drive (bank → entity → files)        config.yaml (who needs which entity)
            │                                   │
            ▼                                   ▼
   list entities ──► select "latest" ──► download ──► zip + split <25MB ──► email per financier
```

- **Regroup by entity** — every immediate sub-folder of a bank folder is an
  *entity*; the same entity name is merged across all three bank folders. Files
  are prefixed with the bank name so `BCA` and `Mandiri` statements never clash.
- **Latest** — default `latest_per_folder` grabs the newest file in each entity
  folder, regardless of upload date or naming. Switchable to `month` (by Drive
  modified-date) or `filename_period` (by month in the filename).
- **25 MB limit** — Gmail caps the *encoded* message at 25 MB and base64 inflates
  attachments ~37%, so each zip is built to fit once encoded. If an entity's
  statements don't fit one zip, they're split into several **independently
  openable** zips (`SMI_2026-05_part1of2.zip`) — no multi-part archives that
  financier IT can't reassemble. Too many zips for one email → multiple emails.

## Project layout

```
run.py                 CLI: auth | discover | dry-run | send
run_monthly.ps1        Unattended wrapper for Windows Task Scheduler
config.example.yaml    Copy → config.yaml, then edit
bankstmt/
  config.py            load/validate config.yaml
  google_auth.py       one OAuth credential for Drive(read) + Gmail(send)
  drive.py             walk bank→entity folders, download files
  selection.py         pick the "latest" statements
  packaging.py         zip + bin-pack under the 25 MB limit
  mailer.py            send via Gmail API with attachments
  pipeline.py          orchestrates the whole run
tests/test_logic.py    offline checks (no Drive/Gmail needed)
```

---

## Setup (once)

### 1. Install
```powershell
cd C:\Users\cecil\OneDrive\Desktop\staffinc\p2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Google credentials
The script needs an OAuth client with two scopes: **Drive read-only** and
**Gmail send**. You can **reuse the same Google Cloud project as p1** — no need
to re-share folders.

**In the Cloud project, regardless of which option below:** enable the
**Gmail API** (p1 only used Drive/Sheets). *APIs & Services → Library → Gmail API
→ Enable.* The Gmail *send* permission is new, so the first login shows a fresh
consent screen — expected.

Then pick one:

- **Reuse p1's client (default).** `.env` is already pre-filled with p1's
  `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` and `GOOGLE_OAUTH_PORT=8080`. p1's
  client is a *Web* type, so add **`http://localhost:8080/`** to its
  *Authorized redirect URIs* (*Credentials → that OAuth client → edit*). Done.

- **New Desktop client (cleanest).** *Credentials → Create credentials → OAuth
  client ID → Desktop app*, download the JSON as **`client_secret.json`** next to
  `run.py`, and delete the `GOOGLE_OAUTH_PORT` line from `.env`. Desktop clients
  accept any loopback port, so there's no redirect URI to register.

### 3. Authorise (one browser login)
```powershell
.\.venv\Scripts\python.exe run.py auth
```
Sign in as the account that can see the statement folders and send mail. A
`token.json` is cached; **every run after this is unattended** (it auto-refreshes).

### 4. Configure
```powershell
copy config.example.yaml config.yaml
.\.venv\Scripts\python.exe run.py discover   # prints the real entity names
```
Edit `config.yaml`: set the `financiers:` list (name, email, entities) using the
entity names `discover` printed. The three source folder IDs are pre-filled.

---

## Run

```powershell
# See exactly what would be sent — downloads, zips, splits, but sends nothing:
.\.venv\Scripts\python.exe run.py dry-run

# Do it for real:
.\.venv\Scripts\python.exe run.py send
```

`dry-run` reports each financier, the entities covered, how many zips, their
sizes, and any file too big to fit a single attachment.

## Schedule it (monthly, hands-off)

Register `run_monthly.ps1` with Windows Task Scheduler to fire on the 1st of each
month. It runs `send --unattended` and logs to `runs\YYYY-MM.log`.

One command (creates a task that runs at 07:00 on the 1st of every month):

```powershell
schtasks /Create /TN "BankStatements-Monthly" /SC MONTHLY /D 1 /ST 07:00 `
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PWD\run_monthly.ps1`"" /F
```

To run it on demand: `schtasks /Run /TN "BankStatements-Monthly"`.
To remove it: `schtasks /Delete /TN "BankStatements-Monthly" /F`.

Equivalent via the GUI: *Task Scheduler → Create Task → Triggers →
New → Monthly → Months: all, Days: 1 → Action: Start a program →
`powershell.exe` with arguments
`-NoProfile -ExecutionPolicy Bypass -File "C:\Users\cecil\OneDrive\Desktop\staffinc\p2\run_monthly.ps1"`.*
Tick *Run whether user is logged on or not*.

## Verify the logic anytime
```powershell
.\.venv\Scripts\python.exe -m tests.test_logic
```
Checks period resolution, latest-file selection, the 25 MB split, and per-email
batching — all offline (no Drive/Gmail calls).

---

## Notes & limits
- `token.json`, `config.yaml`, `client_secret.json`, `.env` and `work/` are
  git-ignored — secrets and financier contacts stay local.
- A *single* statement file larger than ~18 MB raw can't be shrunk by zipping
  (PDFs are already compressed); it's sent as its own zip and flagged in the run
  output. Split such a source PDF if the email bounces.
- Switch selection behaviour in `config.yaml → selection.mode` if "latest" should
  mean "this month by date" or "matches the month in the filename" instead of
  "newest file in the folder".
