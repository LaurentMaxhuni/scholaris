from __future__ import annotations

from collections.abc import Callable
import html
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

from latex2mathml.converter import convert as latex_to_mathml
import markdown
from tkinterweb import HtmlFrame
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, END, LEFT, RIGHT, X

from ai import answer_questions
from ai import generate_quiz
from ai import summarize_text
from pdf_reader import choose_pdf
from pdf_reader import extract_text_from_pdf
from storage import load_json


Callback = Callable[..., None]
HISTORY_FILE = Path(__file__).resolve().parent / "data" / "history.json"
PREVIEW_BG = "#0f172a"
PREVIEW_FG = "#e2e8f0"
MUTED_FG = "#94a3b8"
CARD_BG = "#172033"


class ScholarisApp(ttk.Window):
    def __init__(self) -> None:
        super().__init__(themename="darkly")
        self.title("Scholaris")
        self.geometry("1480x920")
        self.minsize(1180, 760)

        self.selected_file = tk.StringVar(value="No PDF selected")
        self.status_text = tk.StringVar(value="Ready")
        self.progress_text = tk.StringVar(value="Idle")
        self.question_text = tk.StringVar()
        self.quiz_count = tk.IntVar(value=5)

        self.on_browse_pdf: Callback | None = None
        self.on_summarize: Callback | None = None
        self.on_ask: Callback | None = None
        self.on_generate_quiz: Callback | None = None
        self.on_clear: Callback | None = None
        self.on_save_notes: Callback | None = None

        self.history_records: list[dict] = []
        self.history_lookup: dict[str, dict] = {}
        self.page_tabs: dict[str, str] = {}

        self._configure_styles()
        self._build_layout()
        self.refresh_history()

    def _configure_styles(self) -> None:
        style = self.style
        style.configure("App.TFrame", background="#0b1120")
        style.configure("Panel.TFrame", background="#111827")
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("Sidebar.TFrame", background="#060b16")
        style.configure("Sidebar.TLabel", background="#060b16", foreground="#f8fafc")
        style.configure("Muted.Sidebar.TLabel", background="#060b16", foreground=MUTED_FG)
        style.configure("Hero.TLabel", font=("Segoe UI Semibold", 28), background="#0b1120", foreground="#f8fafc")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16), background=CARD_BG, foreground="#f8fafc")
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 13), background=CARD_BG, foreground="#f8fafc")
        style.configure("Body.TLabel", font=("Segoe UI", 10), background=CARD_BG, foreground=MUTED_FG)
        style.configure("MetricValue.TLabel", font=("Segoe UI Semibold", 18), background=CARD_BG, foreground="#f8fafc")
        style.configure("MetricLabel.TLabel", font=("Segoe UI", 9), background=CARD_BG, foreground=MUTED_FG)
        style.configure("Page.TFrame", background="#111827")
        style.configure("History.Treeview", rowheight=30)

    def _build_layout(self) -> None:
        container = ttk.Frame(self, style="App.TFrame", padding=18)
        container.pack(fill=BOTH, expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        self._build_sidebar(container)
        self._build_main_area(container)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        sidebar = ttk.Frame(parent, style="Sidebar.TFrame", padding=22)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        sidebar.configure(width=290)
        sidebar.grid_propagate(False)

        ttk.Label(sidebar, text="Scholaris", style="Sidebar.TLabel", font=("Segoe UI Semibold", 26)).pack(anchor="w")
        ttk.Label(sidebar, text="AI study workspace", style="Muted.Sidebar.TLabel", font=("Segoe UI", 11)).pack(anchor="w", pady=(4, 20))

        feature_box = ttk.Frame(sidebar, style="Sidebar.TFrame")
        feature_box.pack(fill=X, pady=(0, 20))
        features = [
            ("Document", "Load and inspect your PDF"),
            ("Summary", "Markdown + math preview"),
            ("Questions", "Document-based Q&A"),
            ("Quiz", "Practice generation"),
            ("History", "Saved AI responses"),
        ]
        for title, subtitle in features:
            item = ttk.Frame(feature_box, style="Sidebar.TFrame", padding=(0, 8))
            item.pack(fill=X)
            ttk.Label(item, text=title, style="Sidebar.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w")
            ttk.Label(item, text=subtitle, style="Muted.Sidebar.TLabel", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        ttk.Separator(sidebar, bootstyle="secondary").pack(fill=X, pady=16)
        ttk.Label(sidebar, text="Pages", style="Sidebar.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 8))

        self.nav_buttons: dict[str, ttk.Button] = {}
        for key, label, style_name in [
            ("document", "Document", "primary"),
            ("summary", "Summary", "info"),
            ("questions", "Questions", "warning"),
            ("quiz", "Quiz", "success"),
            ("history", "History", "secondary"),
        ]:
            button = ttk.Button(sidebar, text=label, bootstyle=f"outline-{style_name}", command=lambda k=key: self._show_page(k))
            button.pack(fill=X, pady=4)
            self.nav_buttons[key] = button

        ttk.Separator(sidebar, bootstyle="secondary").pack(fill=X, pady=16)
        ttk.Label(sidebar, text="Quick actions", style="Sidebar.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 8))
        ttk.Button(sidebar, text="Browse PDF", bootstyle="light", command=self._handle_browse_pdf).pack(fill=X, pady=4)
        ttk.Button(sidebar, text="Summarize", bootstyle="primary", command=self._handle_summarize).pack(fill=X, pady=4)
        ttk.Button(sidebar, text="Generate Quiz", bootstyle="success", command=self._handle_generate_quiz).pack(fill=X, pady=4)
        ttk.Button(sidebar, text="Save Notes", bootstyle="outline-light", command=self._handle_save_notes).pack(fill=X, pady=4)
        ttk.Button(sidebar, text="Clear Workspace", bootstyle="outline-light", command=self._handle_clear).pack(fill=X, pady=4)

        ttk.Separator(sidebar, bootstyle="secondary").pack(fill=X, pady=16)
        ttk.Label(
            sidebar,
            text="Preview uses HTML + MathML for much better equation rendering in dark mode.",
            style="Muted.Sidebar.TLabel",
            wraplength=230,
            justify=LEFT,
        ).pack(anchor="w")

    def _build_main_area(self, parent: ttk.Frame) -> None:
        main = ttk.Frame(parent, style="App.TFrame")
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self._build_header(main)
        self._build_metrics(main)
        self._build_pages(main)
        self._build_statusbar(main)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Scholaris workspace", style="Hero.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Separate pages for document review, markdown summaries, Q&A, quizzes, and history.",
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        actions = ttk.Frame(header, style="App.TFrame")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(actions, text="Summary Page", bootstyle="primary", command=lambda: self._show_page("summary")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(actions, text="History Page", bootstyle="outline-light", command=lambda: self._show_page("history")).pack(side=LEFT)

    def _build_metrics(self, parent: ttk.Frame) -> None:
        metrics = ttk.Frame(parent, style="App.TFrame")
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        metrics.columnconfigure((0, 1, 2), weight=1)

        self.file_metric = self._metric_card(metrics, 0, "Source file", "No file")
        self.summary_metric = self._metric_card(metrics, 1, "Summary status", "Waiting")
        self.quiz_metric = self._metric_card(metrics, 2, "Quiz items", str(self.quiz_count.get()))

    def _metric_card(self, parent: ttk.Frame, column: int, label: str, value: str) -> ttk.Label:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(card, text=label, style="MetricLabel.TLabel").pack(anchor="w")
        value_label = ttk.Label(card, text=value, style="MetricValue.TLabel")
        value_label.pack(anchor="w", pady=(8, 0))
        return value_label

    def _build_pages(self, parent: ttk.Frame) -> None:
        wrapper = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        wrapper.grid(row=2, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        self.main_tabs = ttk.Notebook(wrapper, bootstyle="dark")
        self.main_tabs.grid(row=0, column=0, sticky="nsew")

        self._build_document_page()
        self._build_summary_page()
        self._build_questions_page()
        self._build_quiz_page()
        self._build_history_page()

        self.main_tabs.bind("<<NotebookTabChanged>>", self._handle_tab_change)
        self._show_page("document")

    def _build_document_page(self) -> None:
        page = self._create_page("document", "Document")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)

        card = self._page_card(page, 0)
        card.rowconfigure(3, weight=1)
        card.columnconfigure(0, weight=1)

        self._page_title(card, "Document source", "Load a PDF and inspect the extracted text before running AI tools.")

        file_row = ttk.Frame(card, style="Card.TFrame")
        file_row.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        file_row.columnconfigure(0, weight=1)
        ttk.Entry(file_row, textvariable=self.selected_file, state="readonly").grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(file_row, text="Browse PDF", bootstyle="info", command=self._handle_browse_pdf).grid(row=0, column=1)

        ttk.Label(card, text="Extracted text", style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.source_text = self._build_textbox(card, font=("Cascadia Code", 10))
        self.source_text.grid(row=3, column=0, sticky="nsew")

    def _build_summary_page(self) -> None:
        page = self._create_page("summary", "Summary")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        card = self._page_card(page, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        self._page_title(card, "Markdown study notes", "Generate notes and see both raw markdown and rendered preview.")

        controls = ttk.Frame(card, style="Card.TFrame")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ttk.Button(controls, text="Generate Summary", bootstyle="primary", command=self._handle_summarize).pack(side=LEFT)
        ttk.Button(controls, text="Save Notes", bootstyle="outline-light", command=self._handle_save_notes).pack(side=LEFT, padx=8)

        panel = ttk.Panedwindow(card, orient="horizontal")
        panel.grid(row=2, column=0, sticky="nsew")

        editor_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(1, weight=1)
        ttk.Label(editor_frame, text="Raw markdown", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.summary_text = self._build_textbox(editor_frame)
        self.summary_text.grid(row=1, column=0, sticky="nsew")
        self.summary_text.bind("<KeyRelease>", lambda _event: self._refresh_markdown_preview(self.summary_preview, self.summary_text.get("1.0", END)))

        preview_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        ttk.Label(preview_frame, text="Rendered preview", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.summary_preview = self._build_preview_frame(preview_frame)
        self.summary_preview.grid(row=1, column=0, sticky="nsew")

        panel.add(editor_frame, weight=1)
        panel.add(preview_frame, weight=1)

    def _build_questions_page(self) -> None:
        page = self._create_page("questions", "Questions")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        card = self._page_card(page, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(3, weight=1)

        self._page_title(card, "Document Q&A", "Ask focused questions against the currently loaded source document.")

        prompt_row = ttk.Frame(card, style="Card.TFrame")
        prompt_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        prompt_row.columnconfigure(0, weight=1)
        ttk.Entry(prompt_row, textvariable=self.question_text).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(prompt_row, text="Ask", bootstyle="warning", command=self._handle_ask).grid(row=0, column=1)

        panel = ttk.Panedwindow(card, orient="horizontal")
        panel.grid(row=3, column=0, sticky="nsew")

        answer_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        answer_frame.columnconfigure(0, weight=1)
        answer_frame.rowconfigure(1, weight=1)
        ttk.Label(answer_frame, text="Answer markdown", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.answer_text = self._build_textbox(answer_frame)
        self.answer_text.grid(row=1, column=0, sticky="nsew")
        self.answer_text.bind("<KeyRelease>", lambda _event: self._refresh_markdown_preview(self.answer_preview, self.answer_text.get("1.0", END)))

        preview_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        ttk.Label(preview_frame, text="Rendered preview", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.answer_preview = self._build_preview_frame(preview_frame)
        self.answer_preview.grid(row=1, column=0, sticky="nsew")

        panel.add(answer_frame, weight=1)
        panel.add(preview_frame, weight=1)

    def _build_quiz_page(self) -> None:
        page = self._create_page("quiz", "Quiz")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        card = self._page_card(page, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(3, weight=1)

        self._page_title(card, "Quiz builder", "Generate quiz material and preview it as rendered markdown.")

        controls = ttk.Frame(card, style="Card.TFrame")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(controls, text="Questions:", style="Body.TLabel").pack(side=LEFT)
        ttk.Spinbox(controls, from_=3, to=20, textvariable=self.quiz_count, width=6).pack(side=LEFT, padx=8)
        ttk.Button(controls, text="Build Quiz", bootstyle="success", command=self._handle_generate_quiz).pack(side=RIGHT)

        panel = ttk.Panedwindow(card, orient="horizontal")
        panel.grid(row=3, column=0, sticky="nsew")

        quiz_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        quiz_frame.columnconfigure(0, weight=1)
        quiz_frame.rowconfigure(1, weight=1)
        ttk.Label(quiz_frame, text="Quiz markdown", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.quiz_text = self._build_textbox(quiz_frame)
        self.quiz_text.grid(row=1, column=0, sticky="nsew")
        self.quiz_text.bind("<KeyRelease>", lambda _event: self._refresh_markdown_preview(self.quiz_preview, self.quiz_text.get("1.0", END)))

        preview_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        ttk.Label(preview_frame, text="Rendered preview", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.quiz_preview = self._build_preview_frame(preview_frame)
        self.quiz_preview.grid(row=1, column=0, sticky="nsew")

        panel.add(quiz_frame, weight=1)
        panel.add(preview_frame, weight=1)

    def _build_history_page(self) -> None:
        page = self._create_page("history", "History")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        card = self._page_card(page, 0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

        self._page_title(card, "History", "Review saved AI outputs without touching the underlying logic.")

        toolbar = ttk.Frame(card, style="Card.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        ttk.Button(toolbar, text="Refresh History", bootstyle="outline-info", command=self.refresh_history).pack(side=LEFT)

        panel = ttk.Panedwindow(card, orient="horizontal")
        panel.grid(row=2, column=0, sticky="nsew")

        list_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        ttk.Label(list_frame, text="Entries", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.history_tree = ttk.Treeview(
            list_frame,
            columns=("action", "prompt"),
            show="headings",
            bootstyle="info",
            height=16,
        )
        self.history_tree.heading("action", text="Action")
        self.history_tree.heading("prompt", text="Prompt")
        self.history_tree.column("action", width=120, anchor="w")
        self.history_tree.column("prompt", width=420, anchor="w")
        self.history_tree.grid(row=1, column=0, sticky="nsew")
        self.history_tree.bind("<<TreeviewSelect>>", self._handle_history_select)

        preview_frame = ttk.Frame(panel, style="Card.TFrame", padding=12)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(2, weight=1)
        ttk.Label(preview_frame, text="Entry detail", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.history_meta = ttk.Label(preview_frame, text="Select a history item to preview it.", style="Body.TLabel")
        self.history_meta.grid(row=1, column=0, sticky="w", pady=(6, 10))
        self.history_preview = self._build_preview_frame(preview_frame)
        self.history_preview.grid(row=2, column=0, sticky="nsew")

        panel.add(list_frame, weight=1)
        panel.add(preview_frame, weight=1)

    def _create_page(self, key: str, title: str) -> ttk.Frame:
        page = ttk.Frame(self.main_tabs, style="Page.TFrame", padding=12)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        self.main_tabs.add(page, text=title)
        self.page_tabs[key] = str(page)
        return page

    def _page_card(self, parent: ttk.Frame, row: int) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.grid(row=row, column=0, sticky="nsew")
        return card

    def _page_title(self, parent: ttk.Frame, title: str, subtitle: str) -> None:
        header = ttk.Frame(parent, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ttk.Label(header, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text=subtitle, style="Body.TLabel").pack(anchor="w", pady=(6, 0))

    def _build_textbox(self, parent: ttk.Frame, font: tuple[str, int] = ("Segoe UI", 10)) -> ScrolledText:
        return ScrolledText(
            parent,
            wrap="word",
            font=font,
            relief="flat",
            borderwidth=1,
            padx=12,
            pady=12,
            background=PREVIEW_BG,
            foreground=PREVIEW_FG,
            insertbackground=PREVIEW_FG,
        )

    def _build_preview_frame(self, parent: ttk.Frame) -> HtmlFrame:
        preview = HtmlFrame(parent, messages_enabled=False, vertical_scrollbar="auto")
        preview.load_html(self._markdown_to_html("_Nothing to preview yet._"))
        return preview

    def _build_statusbar(self, parent: ttk.Frame) -> None:
        statusbar = ttk.Frame(parent, style="App.TFrame")
        statusbar.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(statusbar, textvariable=self.status_text, style="Body.TLabel").pack(side=LEFT)
        ttk.Label(statusbar, textvariable=self.progress_text, style="Body.TLabel").pack(side=RIGHT)

    def _show_page(self, key: str) -> None:
        tab_id = self.page_tabs.get(key)
        if tab_id:
            self.main_tabs.select(tab_id)
            self._set_active_nav(key)

    def _set_active_nav(self, active_key: str) -> None:
        styles = {
            "document": "outline-primary",
            "summary": "outline-info",
            "questions": "outline-warning",
            "quiz": "outline-success",
            "history": "outline-secondary",
        }
        active_styles = {
            "document": "primary",
            "summary": "info",
            "questions": "warning",
            "quiz": "success",
            "history": "secondary",
        }
        for key, button in self.nav_buttons.items():
            button.configure(bootstyle=active_styles[key] if key == active_key else styles[key])

    def _handle_tab_change(self, _event: object) -> None:
        selected = self.main_tabs.select()
        for key, tab_id in self.page_tabs.items():
            if tab_id == selected:
                self._set_active_nav(key)
                break

    def _handle_browse_pdf(self) -> None:
        if self.on_browse_pdf:
            self.on_browse_pdf(self)
            return

        file_path = choose_pdf()
        if not file_path:
            return

        self.set_selected_file(file_path)
        self.set_progress("OCR loading PDF...")
        self.set_status("Reading PDF with local OCR. This may take a moment...")
        self.configure(cursor="watch")
        self.update_idletasks()

        try:
            text = extract_text_from_pdf(file_path)
        except Exception as error:
            self.configure(cursor="")
            self.set_progress("Idle")
            messagebox.showerror("PDF Load Error", str(error))
            self.set_status("PDF load failed.")
            return

        self.configure(cursor="")
        self.set_progress("OCR complete")
        self.set_source_text(text)
        self.set_status("PDF loaded.")
        self._show_page("document")

    def _handle_summarize(self) -> None:
        if self.on_summarize:
            self.on_summarize(self)
            return

        text = self.source_text.get("1.0", END).strip()
        if not text:
            self.set_status("Load a PDF before summarizing.")
            return

        self.set_status("Generating summary...")
        try:
            result = summarize_text(text)
        except Exception as error:
            messagebox.showerror("Summary Error", str(error))
            self.set_status("Summary failed.")
            return

        self.set_summary_text(result)
        self.set_status("Summary ready.")
        self._show_page("summary")
        self.refresh_history()

    def _handle_ask(self) -> None:
        if self.on_ask:
            self.on_ask(self)
            return

        text = self.source_text.get("1.0", END).strip()
        question = self.question_text.get().strip()
        if not text:
            self.set_status("Load a PDF before asking questions.")
            return
        if not question:
            self.set_status("Enter a question first.")
            return

        self.set_status("Getting answer...")
        try:
            result = answer_questions(text, question)
        except Exception as error:
            messagebox.showerror("Question Error", str(error))
            self.set_status("Answer failed.")
            return

        self.set_answer_text(result)
        self.set_status("Answer ready.")
        self._show_page("questions")
        self.refresh_history()

    def _handle_generate_quiz(self) -> None:
        self.quiz_metric.configure(text=str(self.quiz_count.get()))
        if self.on_generate_quiz:
            self.on_generate_quiz(self)
            return

        text = self.source_text.get("1.0", END).strip()
        if not text:
            self.set_status("Load a PDF before generating a quiz.")
            return

        self.set_status("Generating quiz...")
        try:
            result = generate_quiz(text)
        except Exception as error:
            messagebox.showerror("Quiz Error", str(error))
            self.set_status("Quiz failed.")
            return

        self.set_quiz_text(result)
        self.set_status("Quiz ready.")
        self._show_page("quiz")
        self.refresh_history()

    def _handle_clear(self) -> None:
        if self.on_clear:
            self.on_clear(self)
            return

        self.selected_file.set("No PDF selected")
        self.question_text.set("")
        self.clear_textboxes()
        self.file_metric.configure(text="No file")
        self.summary_metric.configure(text="Waiting")
        self.quiz_metric.configure(text=str(self.quiz_count.get()))
        self._refresh_markdown_preview(self.summary_preview, "")
        self._refresh_markdown_preview(self.answer_preview, "")
        self._refresh_markdown_preview(self.quiz_preview, "")
        self.history_meta.configure(text="Select a history item to preview it.")
        self._refresh_markdown_preview(self.history_preview, "")
        self.set_status("Workspace cleared.")
        self.set_progress("Idle")
        self._show_page("document")

    def _handle_save_notes(self) -> None:
        if self.on_save_notes:
            self.on_save_notes(self)
            return

        content = self.summary_text.get("1.0", END).strip()
        if not content:
            self.set_status("Nothing to save.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Notes",
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)

        self.set_status("Notes saved.")

    def _handle_history_select(self, _event: object) -> None:
        selection = self.history_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        entry = self.history_lookup.get(item_id)
        if not entry:
            return

        action = entry.get("action", "unknown")
        prompt = entry.get("prompt", "")
        response = entry.get("response", "")
        self.history_meta.configure(text=f"Action: {action} | Prompt length: {len(prompt)}")

        detail_markdown = (
            f"## {action.title()}\n\n"
            f"### Prompt\n\n```text\n{prompt}\n```\n\n"
            f"### Response\n\n{response}"
        )
        self._refresh_markdown_preview(self.history_preview, detail_markdown)

    def refresh_history(self) -> None:
        self.history_records = load_json(HISTORY_FILE)
        if not isinstance(self.history_records, list):
            self.history_records = []

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.history_lookup.clear()

        for index, entry in enumerate(reversed(self.history_records)):
            action = str(entry.get("action", "unknown"))
            prompt = str(entry.get("prompt", "")).replace("\n", " ").strip()
            prompt_preview = (prompt[:80] + "...") if len(prompt) > 80 else prompt
            item_id = f"history-{index}"
            self.history_tree.insert("", "end", iid=item_id, values=(action, prompt_preview))
            self.history_lookup[item_id] = entry

    def set_selected_file(self, file_path: str) -> None:
        self.selected_file.set(file_path)
        self.file_metric.configure(text=Path(file_path).name or "No file")

    def set_status(self, message: str) -> None:
        self.status_text.set(message)

    def set_progress(self, message: str) -> None:
        self.progress_text.set(message)

    def set_source_text(self, content: str) -> None:
        self._replace_text(self.source_text, content)

    def set_summary_text(self, content: str) -> None:
        self._replace_text(self.summary_text, content)
        self._refresh_markdown_preview(self.summary_preview, content)
        self.summary_metric.configure(text="Ready" if content.strip() else "Waiting")

    def set_answer_text(self, content: str) -> None:
        self._replace_text(self.answer_text, content)
        self._refresh_markdown_preview(self.answer_preview, content)

    def set_quiz_text(self, content: str) -> None:
        self._replace_text(self.quiz_text, content)
        self._refresh_markdown_preview(self.quiz_preview, content)

    def clear_textboxes(self) -> None:
        for textbox in (self.source_text, self.summary_text, self.answer_text, self.quiz_text):
            textbox.delete("1.0", END)

    @staticmethod
    def _replace_text(widget: ScrolledText, content: str) -> None:
        widget.delete("1.0", END)
        widget.insert("1.0", content)

    def _refresh_markdown_preview(self, widget: HtmlFrame, content: str) -> None:
        markdown_text = content.strip() or "_Nothing to preview yet._"
        widget.load_html(self._markdown_to_html(markdown_text))

    def _markdown_to_html(self, content: str) -> str:
        processed, math_tokens = self._extract_math_tokens(content)
        body = markdown.markdown(processed, extensions=["fenced_code", "tables", "nl2br"])
        for token, replacement in math_tokens.items():
            body = body.replace(token, replacement)

        return (
            "<html><head><meta charset='utf-8'><style>"
            "html, body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 14px; }"
            "body { line-height: 1.7; font-size: 14px; }"
            "h1, h2, h3, h4, h5, h6 { color: #f8fafc; margin: 0.8em 0 0.35em; }"
            "p, li { color: #e2e8f0; }"
            "code { background: #111827; color: #93c5fd; padding: 2px 5px; border-radius: 4px; }"
            "pre { background: #111827; color: #e5e7eb; padding: 12px; border: 1px solid #334155; border-radius: 8px; overflow-x: auto; }"
            "pre code { background: transparent; color: inherit; padding: 0; }"
            "blockquote { border-left: 4px solid #38bdf8; margin: 1em 0; padding: 0.25em 0 0.25em 1em; color: #cbd5e1; }"
            "table { border-collapse: collapse; width: 100%; margin: 1em 0; }"
            "th, td { border: 1px solid #334155; padding: 8px; text-align: left; }"
            "th { background: #172033; color: #f8fafc; }"
            "a { color: #7dd3fc; }"
            ".math-inline math, .math-block math { color: #f8fafc; font-size: 1.06em; }"
            ".math-block { margin: 1em 0; padding: 0.8em 1em; background: #111827; border: 1px solid #334155; border-radius: 8px; overflow-x: auto; }"
            "</style></head><body>"
            f"{body}"
            "</body></html>"
        )

    def _extract_math_tokens(self, content: str) -> tuple[str, dict[str, str]]:
        tokens: dict[str, str] = {}
        token_index = 0

        def replace_block(match: re.Match[str]) -> str:
            nonlocal token_index
            expr = match.group(1).strip()
            token = f"MATHBLOCKTOKEN{token_index}"
            token_index += 1
            tokens[token] = self._math_block_html(expr)
            return f"\n\n{token}\n\n"

        def replace_inline(match: re.Match[str]) -> str:
            nonlocal token_index
            expr = match.group(1).strip()
            token = f"MATHINLINETOKEN{token_index}"
            token_index += 1
            tokens[token] = self._math_inline_html(expr)
            return token

        processed = re.sub(r"\$\$(.*?)\$\$", replace_block, content, flags=re.DOTALL)
        processed = re.sub(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", replace_inline, processed)
        return processed, tokens

    def _math_inline_html(self, expression: str) -> str:
        return f"<span class='math-inline'>{self._latex_to_mathml_html(expression, inline=True)}</span>"

    def _math_block_html(self, expression: str) -> str:
        return f"<div class='math-block'>{self._latex_to_mathml_html(expression, inline=False)}</div>"

    def _latex_to_mathml_html(self, expression: str, inline: bool) -> str:
        try:
            mathml = latex_to_mathml(expression)
            if not inline:
                mathml = mathml.replace('display="inline"', 'display="block"')
            return mathml
        except Exception:
            escaped = html.escape(expression)
            return f"<code>{escaped}</code>"


def run() -> None:
    app = ScholarisApp()
    app.mainloop()


if __name__ == "__main__":
    run()
