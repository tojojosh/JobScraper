

## Task: Build UK Skilled Jobs Web-Scraping Portal (Daily Engine + Table UI + Exports)

### Goal

Create a web portal that **daily scrapes the web** for **high-quality skilled jobs in the UK**, prioritizing a provided list of target companies but **also discovering jobs beyond them**. The system must store results per day, display them in a searchable/filterable table, and provide **CSV/Excel exports** plus a **daily JSON output** containing all jobs extracted that day.

---

## Core Features

### 1) Daily Scraping Engine

* Runs **once per day** (scheduled job).
* Scrapes “high-quality skilled jobs” across:

  * Company career pages (especially the focus company list)
  * Job boards / aggregators / other web sources (beyond the list)
* Extracts and normalizes job data into a consistent schema.
* Deduplication rules:

  * Prevent duplicates within a day and across days (based on URL canonicalization + title/company/location similarity).
* Basic data quality checks:

  * Must include **title**, **company**, **location**, **url** at minimum.
  * UK-only constraint (filter out non-UK roles unless remote explicitly UK-based).

### 2) Data Storage + Daily Snapshots

* Persist all scraped jobs in a database.
* Maintain **daily snapshots** of extracted jobs so each day can be viewed/exported independently.
* Track metadata per record:

  * `scrape_date` (YYYY-MM-DD)
  * `source` (domain/source label)
  * `first_seen_date`, `last_seen_date` (optional but useful)

### 3) Portal UI: Jobs Table View

A table view listing scraped jobs with:

* **Date range filter** (e.g., start date → end date, defaults to last 7 days)
* Search (title/company/location keyword)
* Sort (by date, company, title, location)
* Pagination
* Row click opens the **Individual Job Link** in a new tab.

**Table columns (minimum):**

* S/NO (row index)
* Company Name
* Job Title
* Individual Job Link
* Location
* (Optional but recommended) Category, Experience Level, Job Type, Scrape Date, Source

### 4) Export: CSV + Excel

* Export current filtered table results to:

  * **CSV**
  * **Excel (.xlsx)**
* Export respects date range + search filters + sorts.

### 5) Daily JSON Output

For each day, provide a downloadable/viewable JSON containing all jobs extracted that day.

**JSON format (per job object):**

```json
{
  "title": "Senior Software Engineer",
  "company": "Tech Company Inc",
  "location": "United Kingdom",
  "category": "Technology",
  "experience_level": "Senior Level",
  "job_type": "Full-time",
  "url": "https://company.com/careers/senior-software-engineer"
}
```

Notes:

* If category/experience_level/job_type cannot be confidently extracted, set them to `null` (do not invent).
* The daily JSON file should be accessible via the UI per day (e.g., “Download JSON for 2026-02-05”).

---

## Focus Companies (Priority Seeds)

Use the following list as **priority targets** (seed list). The engine should scrape these first but must **also search beyond them**.

> Include the full company list exactly as provided by the user (A&O Shearman, AMD, AON, ARM, … wsp).
> (Implementation detail: store this as a “target_companies” table/list to allow future edits without code changes.)

---

## Non-Functional Requirements

* Reliability: daily run must complete and log success/failure.
* Observability: logs + basic run stats (jobs found, new jobs, duplicates removed, failed sources).
* Compliance/ethics: respect robots.txt where applicable and rate-limit requests; avoid aggressive scraping.
* Performance: UI should load quickly for at least tens of thousands of rows (server-side pagination recommended).

---

## Acceptance Criteria

1. A scheduled daily job runs automatically and stores results with a `scrape_date`.
2. The portal displays a table of jobs with the required columns and a **date range filter**.
3. Users can export filtered results to **CSV** and **Excel**.
4. For any given date, a **daily JSON** is available containing all jobs extracted that day, matching the defined format.
5. Focus companies are prioritized, but results also include jobs from companies outside the list.
6. Deduplication prevents repeated identical jobs flooding results.

Rules

If category, experience level, or job type cannot be extracted → set to null.

JSON must be downloadable per day (e.g., Download JSON for 2026-02-05).

Focus Companies (Priority Seed List)

The scraper must prioritize these companies but must also search beyond them.

Company Target List

A&O Shearman
AMD
AON
ARM
ARM Holdings
ARUP
ASOS
AXA Investment Managers
Aberdeen
Accenture
Accurx
Addleshaw Goddard
Admiral Group
Airbus
Alphasights
Amazon
Amazon UK
American Express
Analysis Group
Analysys Mason
Ankar
Anson McCade
Anthropic
Anyvan
Apple
Arcadis
Archangel Autonomy
Archangel Lightworks
Arma Partners
Artic Lake
Ashurst
AstraZeneca
Astroscale
Atkins
Atkinsrealis
Aviva
BAE System
BAE Systems
BBC
BCG
BDO
BNP Paribas
BP
BT Group
Bain & Company
Baker McKenzie
Balfour Beatty
Bank Of England
Bank of America
Barchester Healthcare
Barclays
Bird & Bird
BlackRock
Blackstone
Bloomberg
Boots
Bristol Myers Squibb
British Red Cross
Bupa
Burges Salmon
CGI UK
CMC Markets
CMS
Cambridge Consultants
Capgemini
Capital One
Caterpillar
Centrica
Chevron
Cisco Systems UK
Citigroup
Civil Service
Colliers
Costello Medical
Darktrace
Deliveroo
Deloitte
Dentons
Deutsche Bank
Diageo
Dojo
Drax
Dyson
EBRD
EDF Energy
EasyJet
Ernst & Young
Eversheds Sutherland
Expedia Group
Experian
ExxonMobil
Fidelity International
Financial Conduct Authority
Flutter International
Freshfields
Fujitsu UK
G-Research
GE Aerospace
GSK
Goldman Sachs
Google
Google DeepMind
Grant Thornton
HSBC
Hogan Lovells
IBM UK
Infosys UK
Intercom
Isomorphic Labs
JP Morgan
Jacobs UK
Jane Street
Johnson & Johnson UK
KPMG
Lloyds Banking Group
Macquarie
Mars UK
Mastercard UK
McKinsey & Company
Meta
Microsoft
Mistral AI
Monzo
Morgan Stanley
Mott MacDonald
NHS
NatWest Group
Netflix UK
Network Rail
Nomura
Norton Rose Fulbright
Ocado Group
Oliver Wyman
Oracle UK
Orbex
P&G
Pfizer UK
Pinsent Masons
PwC
Rolls-Royce
SAP UK
SSE
Salesforce UK
Sanofi
Santander
Schneider Electric
Schroders
Shell
Skanska
Softwire
Sony Music UK
Spotify UK
Standard Chartered
Starling Bank
Synthesia
THG
TikTok
Trainline
Transport For London
UBS
Unilever
University College London
University Of Oxford
Visa
WPP
WSP
Wayve
Wise
Wood PLC
Zaha Hadid Architects
Zepz

(Note: Store this list in configuration or database, not hardcoded.)

Non-Functional Requirements

Reliability: Daily runs must log success/failure.

Observability: Logs and run statistics required.

Compliance:

Respect robots.txt where applicable.

Apply request rate limiting.

Performance:

Must support tens of thousands of rows.

Use server-side pagination if needed.

Acceptance Criteria

Daily scheduled scraper runs automatically.

Jobs stored with scrape date.

Portal table supports filtering, search, sorting, pagination.

CSV and Excel exports work correctly.

Daily JSON available and matches schema.

Focus companies prioritized but not exclusive.

Deduplication working across and within days.
