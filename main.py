"""
Pixous Technologies — Estimation & Invoicing Pipeline — CLI Entry Point

Usage:
    python main.py --file document.pdf
    python main.py --url https://example.com/doc.pdf
    python main.py --text "Build a web app that..."
    python main.py                                   # Interactive mode

Outputs:
    output/<project_name>_quotation.md   — Structured quotation
    output/<project_name>_data.json      — Full JSON data
"""

from __future__ import annotations

import os
import sys

# Force UTF-8 on Windows to prevent emoji encoding errors in Rich
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.markdown import Markdown

import config
from agents.graph import run_pipeline

console = Console()


def _sanitize_filename(name: str) -> str:
    """Create a filesystem-safe filename."""
    safe = re.sub(r'[^\w\s-]', '', name).strip()
    safe = re.sub(r'[\s]+', '_', safe)
    return safe[:50] or "project"


def _print_banner():
    """Print the startup banner."""
    console.print(Panel.fit(
        "[bold cyan]📄 Pixous Technologies — Estimation & Invoicing[/bold cyan]\n"
        "[dim]Mistral OCR → Groq LLM → Gemini Web Search[/dim]\n"
        "[dim]Powered by LangGraph Agentic Architecture[/dim]",
        border_style="cyan",
    ))
    console.print()


def _print_config_status():
    """Show configuration status."""
    table = Table(title="🔑 API Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Keys", justify="right")

    mistral_ok = bool(config.MISTRAL_API_KEY)
    groq_ok = len(config.GROQ_API_KEYS) > 0
    gemini_ok = len(config.GEMINI_API_KEYS) > 0

    table.add_row("Mistral OCR", "✅ Ready" if mistral_ok else "❌ Missing", "1" if mistral_ok else "0")
    table.add_row("Groq LLM", "✅ Ready" if groq_ok else "❌ Missing", str(len(config.GROQ_API_KEYS)))
    table.add_row("Gemini Search", "✅ Ready" if gemini_ok else "❌ Missing", str(len(config.GEMINI_API_KEYS)))

    console.print(table)
    console.print()

    if not all([mistral_ok, groq_ok, gemini_ok]):
        console.print("[bold red]⚠️  Some API keys are missing. Check your .env file.[/bold red]")
        return False
    return True


def _print_logs(logs: list[str]):
    """Print pipeline logs."""
    console.print("\n[bold yellow]📝 Pipeline Log:[/bold yellow]")
    for entry in logs:
        console.print(f"  {entry}")


def _save_outputs(state: dict):
    """Save quotation, BRD, SRS, and JSON data to output directory."""
    analysis = state.get("project_analysis", {})
    project_name = _sanitize_filename(analysis.get("project_name", "project"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{project_name}_{timestamp}"

    # Save Markdown quotation
    md_path = os.path.join(config.OUTPUT_DIR, f"{base_name}_quotation.md")
    quotation_md = state.get("quotation_markdown", "")
    if quotation_md:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(quotation_md)
        console.print(f"\n[bold green]✅ Quotation saved:[/bold green] {md_path}")

    # Save BRD
    brd_markdown = state.get("brd_markdown", "")
    if brd_markdown:
        brd_path = os.path.join(config.OUTPUT_DIR, f"{base_name}_brd.md")
        with open(brd_path, "w", encoding="utf-8") as f:
            f.write(brd_markdown)
        console.print(f"[bold green]✅ Business Requirements Document (BRD) saved:[/bold green] {brd_path}")

    # Save SRS
    srs_markdown = state.get("srs_markdown", "")
    if srs_markdown:
        srs_path = os.path.join(config.OUTPUT_DIR, f"{base_name}_srs.md")
        with open(srs_path, "w", encoding="utf-8") as f:
            f.write(srs_markdown)
        console.print(f"[bold green]✅ Software Requirements Specification (SRS) saved:[/bold green] {srs_path}")

    # Save JSON data
    json_path = os.path.join(config.OUTPUT_DIR, f"{base_name}_data.json")
    json_data = state.get("quotation_json", {})
    if json_data:
        if brd_markdown:
            json_data["brd_markdown"] = brd_markdown
        if srs_markdown:
            json_data["srs_markdown"] = srs_markdown
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        console.print(f"[bold green]✅ JSON data saved:[/bold green]  {json_path}")

    return md_path, json_path


def main():
    _print_banner()

    parser = argparse.ArgumentParser(
        description="Pixous Technologies — Analyze documents and generate cost quotations, BRD, and SRS",
    )
    parser.add_argument("--file", "-f", type=str, help="Path to a document file (PDF, DOCX, TXT)")
    parser.add_argument("--url", "-u", type=str, help="URL to a document")
    parser.add_argument("--text", "-t", type=str, help="Raw text input (requirement description)")
    parser.add_argument("--brd", action="store_true", help="Generate a detailed Business Requirements Document (BRD)")
    parser.add_argument("--srs", action="store_true", help="Generate a detailed Software Requirements Specification (SRS)")
    parser.add_argument("--no-search", action="store_true", help="Skip web search stage")
    parser.add_argument("--output-format", choices=["md", "json", "both"], default="both", help="Output format")

    args = parser.parse_args()

    # Check configuration
    if not _print_config_status():
        sys.exit(1)

    # Determine input
    raw_input = None
    if args.file:
        raw_input = args.file
        console.print(f"[cyan]📁 Input file:[/cyan] {args.file}")
    elif args.url:
        raw_input = args.url
        console.print(f"[cyan]🌐 Input URL:[/cyan] {args.url}")
    elif args.text:
        raw_input = args.text
        console.print(f"[cyan]📝 Text input:[/cyan] {args.text[:100]}...")
    else:
        # Interactive mode
        console.print("[bold cyan]No input specified. Enter your requirements below.[/bold cyan]")
        console.print("[dim](Paste your text and press Enter twice to submit, or type a file path/URL)[/dim]\n")

        lines = []
        empty_count = 0
        try:
            while True:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                    lines.append(line)
                else:
                    empty_count = 0
                    lines.append(line)
        except EOFError:
            pass

        raw_input = "\n".join(lines).strip()
        if not raw_input:
            console.print("[bold red]❌ No input provided. Exiting.[/bold red]")
            sys.exit(1)

    console.print()

    # Run the pipeline
    console.print(Panel("[bold green]🚀 Starting Pipeline...[/bold green]", border_style="green"))
    console.print()

    try:
        with console.status("[bold cyan]Processing...", spinner="dots"):
            final_state = asyncio.run(run_pipeline(
                raw_input=raw_input,
                generate_brd=args.brd,
                generate_srs=args.srs
            ))

        # Print logs
        _print_logs(final_state.get("log", []))

        # Print errors if any
        errors = final_state.get("errors", [])
        if errors:
            console.print("\n[bold red]⚠️  Errors encountered:[/bold red]")
            for err in errors:
                console.print(f"  [red]• {err}[/red]")

        # Save outputs
        md_path, json_path = _save_outputs(final_state)

        # Display quotation preview
        quotation_md = final_state.get("quotation_markdown", "")
        if quotation_md:
            console.print("\n")
            console.print(Panel("[bold cyan]📋 Quotation Preview[/bold cyan]", border_style="cyan"))
            console.print(Markdown(quotation_md))

        console.print(Panel.fit(
            "[bold green]✅ Pipeline Complete![/bold green]",
            border_style="green",
        ))

    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️  Pipeline interrupted by user.[/bold yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]❌ Pipeline failed: {e}[/bold red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
