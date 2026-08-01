# Scholaris

Scholaris is a desktop study assistant built with `tkinter` and `ttkbootstrap`.
It loads PDFs with OCR, sends the extracted text to an AI model for study help,
and renders markdown + LaTeX-style math in a dark themed interface.

## Features

- OCR-based PDF text extraction
- AI-generated:
  - summaries
  - question answering
  - quizzes
- dark themed multi-page GUI
- markdown preview rendering
- LaTeX math preview support using `$...$` and `$$...$$`
- local history saved to `data/history.json`

## App pages

- **Document** — load a PDF and inspect OCR text
- **Summary** — generate and preview study notes
- **Questions** — ask questions about the loaded document
- **Quiz** — generate quiz material from the document
- **History** — review saved AI outputs

## Requirements

- Python `3.14`
- Windows is the currently tested environment
- [`uv`](https://docs.astral.sh/uv/) recommended for dependency management and running

## Installation

From the project root:

```sh
uv sync
```

## Environment variables

Create a `.env` file in the project root.

Example:

```env
GROQ_API_KEY=your_api_key_here
GROQ_API_URL=https://api.groq.com/openai/v1
```

You can also use:

```env
OPENAI_API_KEY=your_api_key_here
```

### Notes

- `ai.py` uses the `openai` Python package.
- The app is currently configured to work with an OpenAI-compatible API base URL.
- If `GROQ_API_KEY` is present, it is preferred.
- If `OPENAI_API_KEY` is present, it is used as a fallback.

## Running the app

```sh
uv run python main.py
```

## OCR behavior

PDF loading uses OCR rather than native PDF text extraction.

Current behavior:

- tries `PaddleOCR` first
- falls back to `RapidOCR` if Paddle cannot initialize

This fallback exists because `paddlepaddle` support can lag behind the newest
Python versions.

### OCR caveats

- large PDFs may take a while to load
- scanned/image-heavy PDFs work better than before, but OCR is still imperfect
- layout-heavy documents may lose formatting during extraction

## AI output formatting

The AI prompts are set up to prefer:

- markdown headings
- bullet points
- short readable sections
- LaTeX math when formulas appear

That means responses like these should preview well:

```md
# Derivatives

The derivative of $x^2$ is $2x$.

$$
\int_0^1 x^2 \, dx = \frac{1}{3}
$$
```

## Project structure

```text
Scholaris/
├── ai.py
├── gui.py
├── main.py
├── pdf_reader.py
├── storage.py
├── data/
│   └── history.json
├── pyproject.toml
└── README.md
```

## Main modules

### `main.py`
Starts the GUI.

### `gui.py`
Contains the dark themed desktop interface, page navigation, markdown preview,
and interaction handlers.

### `pdf_reader.py`
Handles PDF selection and OCR-based text extraction.

### `ai.py`
Sends text to the configured AI provider for:

- summary generation
- question answering
- quiz generation

It also writes history entries to disk.

### `storage.py`
Simple JSON load/save helpers.

## History storage

AI interactions are saved to:

```text
data/history.json
```

Each entry stores:

- `action`
- `prompt`
- `response`

## Troubleshooting

### PDF OCR fails

If you get OCR-related errors:

- run `uv sync` again
- make sure you launch with `uv run python main.py`
- try a smaller PDF first to verify the OCR path works

### AI requests fail

Check:

- your API key is set in `.env`
- your base URL is correct
- the provider supports the models configured in `ai.py`

### Preview looks wrong

The preview expects markdown and LaTeX-style math:

- inline math: `$a^2+b^2=c^2$`
- block math:

```md
$$
E = mc^2
$$
```

## Current limitations

- OCR can be slow on large PDFs
- OCR text quality depends on source quality
- quiz count in the UI is currently a display/control value; the underlying AI
  logic may still need tighter enforcement if you want exact counts every time
- the app is desktop-first and not packaged as an executable yet

## Future ideas

- page-by-page OCR progress
- export notes/history as markdown or PDF
- clickable history entries that repopulate editor panes
- stricter quiz formatting and answer keys
- model/provider selection in the GUI
