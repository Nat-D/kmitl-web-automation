# KMITL · Agentic Web Search & Automation

A tiny, hands-on demo for **LLM Lecture 12 — Agentic Web Search & Automation**.
An agent that:

1. **Searches the web** (Tavily), **fetches** a page, **extracts** the main text, and
   **answers with a citation** it can't fake — the `search → fetch → extract → answer`
   pipeline from the lecture.
2. Shows **prompt-injection defense**: a toggle to see a hostile page hijack a *naive*
   agent, and how labelling fetched text as *untrusted data* stops it.
3. **Drives a real browser** (Playwright) for the jobs search can't do: a
   JavaScript-rendered page, and a multi-step **login** flow.

Stack: **FastAPI + uv** (backend), **Svelte + Vite** (frontend), **Tavily** (search),
**Playwright** (browser). Same stack as the course.

---

## What you'll need

| Tool | Why | Get it |
|---|---|---|
| **Python 3.11+** and [**uv**](https://docs.astral.sh/uv/) | run the backend | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node 18+** (`npm`) | run the Svelte frontend | https://nodejs.org |
| **Tavily API key** | the web-search tool | free dev key at https://tavily.com |
| **Course LLM key** | the model (`gemma-4-E4B-it`) | course portal → **Profile → API key** |

---

## Setup (two terminals)

### 1 · Backend (FastAPI)

```bash
cd backend
uv sync                              # create the venv + install deps
uv run playwright install chromium   # one-time: REQUIRED for the Browser tab (skip it and it errors)
cp .env.example .env                 # then edit .env and paste your two keys
uv run uvicorn app.main:app --reload --port 8000
```

Your `backend/.env` should look like:

```
TAVILY_API_KEY=tvly-xxxxxxxx
LLM_API_KEY=sk-xxxxxxxx
```

Check it's alive: open http://localhost:8000/api/health — you should see
`{"llm_key_set": true, "tavily_key_set": true, ...}`.

### 2 · Frontend (Svelte)

```bash
cd frontend
npm install
npm run dev
```

Open the URL it prints (**http://localhost:5173**). The frontend proxies `/api` to the
backend on port 8000, so both must be running.

---

## Using it

**Tab 1 — Search agent.** Ask a question that needs fresh, real-world facts (e.g.
*"What year was KMITL founded? Cite the source URL you read."*). Watch the **ACT/OBS
trace**: the model calls `web_search`, picks a URL, calls `fetch_page`, reads the
extracted text, and answers with a citation your code recorded at fetch time.

- Toggle **Defended** off to see the *prompt-injection* problem: a naive agent will
  follow instructions hidden in a page. With it on, fetched text is wrapped and
  labelled as untrusted **data**, and the system prompt tells the model never to obey it.

**Tab 2 — Browser automation.**
- **Plain GET vs browser render** on `https://quotes.toscrape.com/js/`: a plain HTTP
  GET sees almost nothing (the page is built by JavaScript); Playwright runs the JS and
  the 10 quotes appear. *This is when you escalate from `fetch` to a browser.*
- **Login automation**: the four primitives — `goto`, `fill`, `click`, `read` —
  sequenced into a login flow (the site accepts any username/password), with the
  ACT/OBS trace.

---

## How it maps to the lecture

| Lecture 12 | Where in the code |
|---|---|
| §2 web search as a tool | `backend/app/tools.py` → `web_search` (Tavily) |
| §3 fetch & extract main text | `tools.py` → `Fetcher.fetch` (`httpx` + `trafilatura`) |
| §4 the tool-calling agent loop | `backend/app/agent.py` → `run_search_agent` |
| §5 / §8.3 citations you can't fabricate | `Fetcher.trail` (recorded at fetch time) |
| §6 browser automation | `backend/app/browser.py` (Playwright) |
| §7 / §8.5 prompt-injection defense | `wrap_untrusted` + the *Defended* toggle |

---

## Safety notes (important)

- **Fetched page text is untrusted data, never commands.** The defended agent wraps and
  labels it; the *real* safety net is architectural — allow-list domains/tools and keep a
  human in the loop for anything with side effects.
- **Be a good web citizen.** This demo sets an honest `User-Agent`, de-duplicates URLs,
  and only visits sites built for practice. Respect `robots.txt`, rate-limit, and read a
  site's Terms of Service before automating it.
- **Never commit your keys.** They live in `backend/.env`, which is git-ignored.

---

## Troubleshooting

- **"Compare plain GET vs browser" (or login automation) shows a browser error** — the
  browser isn't installed. Run `uv run playwright install chromium` in the `backend/`
  folder, then click again. (The app now tells you this instead of a blank error; if you
  see "Executable doesn't exist," it's the same fix.)
- **`playwright install` itself fails / your OS is too old for the current browser
  build** — pin an older Playwright (`uv pip install 'playwright==1.45'`) then re-run
  `uv run playwright install chromium`. On Linux you may also need
  `uv run playwright install-deps` (installs the shared libraries Chromium needs).
- **`NotImplementedError` / `_make_subprocess_transport` when using the browser** — this
  came from running Playwright's async API on a server event loop that can't spawn a
  subprocess (Windows' selector loop, some uvicorn/uvloop setups). The app now runs
  Playwright's **sync** API in a worker thread (`asyncio.to_thread`), which sidesteps it
  on every platform — just pull the latest code.
- **`tavily_key_set: false` / `llm_key_set: false`** — your `backend/.env` is missing or
  the backend wasn't restarted after editing it.
- **Frontend can't reach the API** — make sure the backend is running on port 8000; the
  Vite dev server proxies `/api` there.
- **Agent answers without fetching** — that's the lesson in §4/§8.6: snippets are for
  *finding*, not *answering*. The system prompt already tells it to fetch first.

---

Built for the **Building LLM-Powered Applications** course at KMITL.
