#!/usr/bin/env python3
"""
viziac.py — terminal visualizer for Information Access Cost (IAC) result JSON files.

Usage:
    python viziac.py <iac_result.json>
"""

import json
import sys
import pathlib
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text
from rich.rule import Rule
from rich.padding import Padding

console = Console()

# ── color / style constants ───────────────────────────────────────────────────

CREDIT_STYLE = {
    "FULL": ("green", "●", "FULL"),
    "PARTIAL": ("yellow", "◐", "PARTIAL"),
    "NONE": ("bright_black", "○", "NONE"),
    "CONTRADICTED": ("red", "✖", "CONTRADICTED"),
}

COMPONENT_NAME_STYLE = {
    "location_score": "cyan",
    "need_score": "magenta",
    "resource_score": "blue",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def clean_fact_str(s: str) -> str:
    """Simplifies long strings for better table fitting."""
    if not s:
        return ""
    # Simplify RelationPredicate enums
    s = s.replace("RelationPredicate.", "")
    # Simplify common prefixes
    s = s.replace("LocationFact: ", "Loc: ")
    s = s.replace("RelationFact: ", "Rel: ")
    s = s.replace("SpatialFact: ", "Spa: ")
    return s

def format_cost(val: float) -> str:
    return f"{val:.2f}"

def get_credit_markup(credit_type: str) -> Text:
    color, icon, label = CREDIT_STYLE.get(credit_type, ("white", "?", credit_type))
    return Text.from_markup(f"[{color}]{icon} {label}[/{color}]")

# ── renderers ─────────────────────────────────────────────────────────────────

def render_summary(data: dict) -> None:
    total_saved = data.get("total_cost_saved", 0)
    omission = data.get("omission_cost", 0)
    misinfo = data.get("misinformation_cost", 0)
    multiplier = data.get("misinformation_multiplier", 1.0)
    combined = data.get("combined_cost", 0)

    table = Table(box=box.ROUNDED, title="[bold]IAC Result Summary[/bold]", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Total Cost Saved", f"[bold green]{format_cost(total_saved)}[/bold green]")
    table.add_row("Omission Cost", f"[bold yellow]{format_cost(omission)}[/bold yellow]")
    table.add_row("Misinformation Cost", f"[bold red]{format_cost(misinfo)}[/bold red]")
    table.add_row("Misinfo Multiplier", f"[dim]x {format_cost(multiplier)}[/dim]")
    table.add_row(Rule(style="dim"), Rule(style="dim"))
    table.add_row("Combined Cost", f"[bold cyan]{format_cost(combined)}[/bold cyan]")

    console.print(Padding(table, (1, 0, 1, 0)))

def render_entity(name: str, scores: dict) -> None:
    console.print(Rule(f"[bold blue]Entity: {name.upper()}[/bold blue]", style="blue"))
    
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Component", style="bold", width=12)
    table.add_column("Credit", width=14)
    table.add_column("Fact Details", ratio=3)
    table.add_column("Costs", width=22)

    for comp_key in ["location_score", "need_score", "resource_score"]:
        comp_data = scores.get(comp_key, {})
        comp_display_name = comp_key.replace("_score", "").capitalize()
        comp_color = COMPONENT_NAME_STYLE.get(comp_key, "white")
        
        credit_type = comp_data.get("credit_type", "NONE")
        credit_markup = get_credit_markup(credit_type)
        
        eval_fact = clean_fact_str(comp_data.get("evaluated_fact") or "")
        gt_fact = clean_fact_str(comp_data.get("ground_truth_fact") or "")
        
        if not eval_fact: eval_fact = "[dim]N/A[/dim]"
        if not gt_fact: gt_fact = "[dim]N/A[/dim]"
        
        fact_details = Text()
        fact_details.append("Eval: ", style="dim")
        fact_details.append(f"{eval_fact}\n")
        fact_details.append("GT:   ", style="dim")
        fact_details.append(f"{gt_fact}", style="italic")

        costs_text = Text()
        costs_text.append(f"Saved:    {format_cost(comp_data.get('cost_saved', 0))}\n", style="green")
        costs_text.append(f"Omission: {format_cost(comp_data.get('omission_cost', 0))}\n", style="yellow")
        costs_text.append(f"Misinfo:  {format_cost(comp_data.get('misinformation_cost', 0))}", style="red")

        table.add_row(
            Text(comp_display_name, style=comp_color),
            credit_markup,
            fact_details,
            costs_text
        )

    console.print(table)
    console.print()

def print_legend() -> None:
    parts = []
    for style_key, (color, icon, label) in CREDIT_STYLE.items():
        parts.append(f"[{color}]{icon} {label}[/{color}]")
    console.print(Padding("  ".join(parts), (0, 0, 1, 2)))

# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        console.print("[red]Usage:[/red] python viziac.py <iac_result.json>")
        sys.exit(1)

    path = pathlib.Path(sys.argv[1])
    if not path.exists():
        console.print(f"[red]File not found:[/red] {sys.argv[1]}")
        sys.exit(1)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON parse error:[/red] {e}")
        sys.exit(1)

    render_summary(data)
    print_legend()
    
    entity_scores = data.get("entity_scores", {})
    for entity_name, scores in entity_scores.items():
        render_entity(entity_name, scores)

if __name__ == "__main__":
    main()
