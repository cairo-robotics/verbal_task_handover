#!/usr/bin/env python3
"""
vizkg.py — terminal visualizer for pipeline knowledge-graph JSON files.

Usage:
    python vizkg.py <file.json> [<file2.json> ...]
    python vizkg.py samples/merged_graph.json
    python vizkg.py samples/telemetry_graph.json samples/user_report_graph.json

Reads files matching the KnowledgeGraph pydantic schema and renders a
color-coded, section-grouped fact list with conflict highlights.
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

SRC_STYLE = {
    "base":  ("blue",        "◆"),   # telemetry
    "new":   ("dark_orange", "◇"),   # user report
    None:    ("grey50",      "○"),
}

MERGE_STYLE = {
    "shared":   ("steel_blue",  "●", ""),
    "novel":    ("green",       "●", ""),
    "conflict": ("red",         "✖", " [dim](conflict)[/dim]"),
}

PRED_STYLE = {
    "needs_potion":       ("cyan",         "needs_potion"),
    "potion_delivered":   ("green",        "potion_delivered"),
    "has_message_for":    ("yellow",       "has_message_for"),
    "message_delivered":  ("green",        "message_delivered"),
    "has_item":           ("magenta",      "has_item"),
}

FACT_TYPE_LABEL = {
    "relation":   ("RELATION",   "cyan"),
    "location":   ("LOCATION",   "blue"),
    "spatial":    ("SPATIAL",    "magenta"),
    "connection": ("CONNECTION", "yellow"),
    "unknown":    ("UNKNOWN",    "grey50"),
}


# ── helpers ───────────────────────────────────────────────────────────────────

def detect_fact_type(fact: dict) -> str:
    if "predicate" in fact:
        return "relation"
    if "entity" in fact and "location" in fact and "direction" not in fact:
        return "location"
    if "subject" in fact and "direction" in fact and "location_a" not in fact:
        return "spatial"
    if "location_a" in fact:
        return "connection"
    return "unknown"


def arg_str(arg: dict | None) -> str:
    if not arg:
        return "?"
    loc = arg.get("location")
    loc_suffix = f" [dim]@ {loc_str(loc)}[/dim]" if loc else ""
    if arg.get("type") == "existential":
        val = arg.get("value")
        label = f"[dim]<{val or 'unknown'}>[/dim]"
        return f"{label}{loc_suffix}"
    val = arg.get("value") or "?"
    return f"[bold]{val}[/bold]{loc_suffix}"


def loc_str(loc: dict | None) -> str:
    if not loc:
        return "?"
    if loc.get("type") == "room":
        return loc.get("room") or "?"
    dirs = loc.get("directions") or []
    mode = loc.get("mode") or "set"
    sep  = " → " if mode == "path" else " & "
    txt  = sep.join(dirs)
    return f"~{txt}"   # ~ prefix signals a directional (partial) location


def pred_markup(pred: str) -> str:
    color, label = PRED_STYLE.get(pred, ("white", pred))
    return f"[{color}]{label}[/{color}]"


def fact_to_text(fact: dict) -> Text:
    """Return a rich Text object describing one fact."""
    ftype   = detect_fact_type(fact)
    partial = fact.get("is_partial", False)

    t = Text()

    if ftype == "relation":
        s    = arg_str(fact.get("subject"))
        pred = pred_markup(fact.get("predicate", "?"))
        obj  = fact.get("object")
        tgt  = fact.get("target")
        parts = []
        if obj:
            parts.append(arg_str(obj))
        if tgt:
            parts.append(f"→ {arg_str(tgt)}")
        rhs = "  ".join(parts) or "[dim]?[/dim]"
        t.append_text(Text.from_markup(f"{s}  {pred}  {rhs}"))

    elif ftype == "location":
        entity = arg_str(fact.get("entity"))
        loc    = loc_str(fact.get("location"))
        prefix = "[dim]~[/dim]" if loc.startswith("~") else ""
        t.append_text(Text.from_markup(f"{entity}  [dim]in[/dim]  {prefix}[bold]{loc.lstrip('~')}[/bold]"))

    elif ftype == "spatial":
        subj = arg_str(fact.get("subject"))
        d    = fact.get("direction", "?")
        ref  = fact.get("reference")
        rhs  = f"[magenta]{d}[/magenta]"
        if ref:
            rhs += f" of {arg_str(ref)}"
        t.append_text(Text.from_markup(f"{subj}  [dim]is[/dim]  {rhs}"))

    elif ftype == "connection":
        a = loc_str(fact.get("location_a"))
        b = loc_str(fact.get("location_b"))
        d = fact.get("direction", "")
        arrow = f"[yellow]─{d}→[/yellow]" if d else "[yellow]↔[/yellow]"
        t.append_text(Text.from_markup(f"[bold]{a}[/bold]  {arrow}  [bold]{b}[/bold]"))

    else:
        t.append("[dim]unrecognized fact[/dim]")

    if partial:
        t.append("  [dim italic](partial)[/dim italic]")

    return t


def classify_merged(fact: dict, conflict_base_ids: set, conflict_new_ids: set) -> str:
    fid = fact.get("id", "")
    if fid in conflict_base_ids or fid in conflict_new_ids:
        return "conflict"
    if fact.get("source") == "new":
        return "novel"
    return "shared"


# ── renderers ─────────────────────────────────────────────────────────────────

def render_single_graph(data: dict, filename: str) -> None:
    facts     = data.get("facts", [])
    conflicts = data.get("conflicts", [])  # shouldn't exist in single-source, but handle it

    # group by fact type
    groups: dict[str, list] = {k: [] for k in FACT_TYPE_LABEL}
    for f in facts:
        groups[detect_fact_type(f)].append(f)

    console.print()
    console.print(Rule(f"[bold]{filename}[/bold]  [dim]({len(facts)} facts)[/dim]"))

    for ftype, label_color in FACT_TYPE_LABEL.items():
        bucket = groups[ftype]
        if not bucket:
            continue
        type_label, type_color = label_color
        console.print(f"\n  [{type_color}]{type_label}[/{type_color}]")

        table = Table(box=None, padding=(0, 1, 0, 2), show_header=False, expand=False)
        table.add_column("src",  no_wrap=True, width=2)
        table.add_column("fact", no_wrap=False)
        table.add_column("prov", no_wrap=False, style="dim italic")

        for f in bucket:
            src   = f.get("source")
            color, icon = SRC_STYLE.get(src, SRC_STYLE[None])
            icon_markup = f"[{color}]{icon}[/{color}]"
            prov  = f.get("provenance") or ""
            prov_display = f'"{prov}"' if prov else ""
            table.add_row(icon_markup, fact_to_text(f), prov_display)

        console.print(table)

    if conflicts:
        _render_conflicts(conflicts)


def render_merged_graph(data: dict, filename: str) -> None:
    facts     = data.get("facts", [])
    conflicts = data.get("conflicts", [])

    conflict_base_ids = {c["base_fact_id"] for c in conflicts}
    conflict_new_ids  = {c["new_fact"]["id"] for c in conflicts}

    # group by classification, then fact type
    buckets: dict[str, dict[str, list]] = {
        "shared":   {k: [] for k in FACT_TYPE_LABEL},
        "novel":    {k: [] for k in FACT_TYPE_LABEL},
        "conflict": {k: [] for k in FACT_TYPE_LABEL},
    }
    for f in facts:
        cls   = classify_merged(f, conflict_base_ids, conflict_new_ids)
        ftype = detect_fact_type(f)
        buckets[cls][ftype].append(f)

    n_shared   = sum(len(v) for v in buckets["shared"].values())
    n_novel    = sum(len(v) for v in buckets["novel"].values())
    n_conflict = len(conflicts)

    console.print()
    console.print(Rule(
        f"[bold]{filename}[/bold]  "
        f"[steel_blue]{n_shared} shared[/steel_blue]  "
        f"[green]{n_novel} novel[/green]  "
        f"[red]{n_conflict} conflict{'s' if n_conflict != 1 else ''}[/red]"
    ))

    for cls, (color, icon, suffix) in MERGE_STYLE.items():
        type_buckets = buckets[cls]
        total = sum(len(v) for v in type_buckets.values())
        if total == 0:
            continue

        console.print(f"\n  [{color}]{icon} {cls.upper()}[/{color}]{suffix}")

        for ftype, label_color in FACT_TYPE_LABEL.items():
            bucket = type_buckets[ftype]
            if not bucket:
                continue
            type_label, type_color = label_color
            console.print(f"    [{type_color} dim]{type_label}[/{type_color} dim]")

            table = Table(box=None, padding=(0, 1, 0, 4), show_header=False, expand=False)
            table.add_column("fact", no_wrap=False)
            table.add_column("prov", no_wrap=False, style="dim italic")

            for f in bucket:
                prov = f.get("provenance") or ""
                prov_display = f'"{prov}"' if prov else ""
                table.add_row(fact_to_text(f), prov_display)

            console.print(table)

    if conflicts:
        _render_conflicts(conflicts)


def _render_conflicts(conflicts: list[dict]) -> None:
    console.print(f"\n  [red bold]✖ CONFLICTS[/red bold]")
    for c in conflicts:
        nf         = c.get("new_fact", {})
        field      = c.get("field_name", "?")
        base_val   = c.get("base_value")
        new_val    = c.get("new_value")
        prov       = nf.get("provenance") or ""

        panel_body = Text()
        panel_body.append(f"  field:   ", style="dim")
        panel_body.append(f"{field}\n", style="bold")
        panel_body.append(f"  base:    ", style="dim")
        panel_body.append(f"{json.dumps(base_val)}\n", style="steel_blue bold")
        panel_body.append(f"  report:  ", style="dim")
        panel_body.append(f"{json.dumps(new_val)}\n", style="dark_orange bold")
        if prov:
            panel_body.append(f'  source:  ', style="dim")
            panel_body.append(f'"{prov}"', style="italic dim")

        console.print(Padding(
            Panel(panel_body, border_style="red", box=box.SIMPLE_HEAVY, expand=False),
            pad=(0, 0, 0, 4)
        ))


def render_side_by_side(data_list: list[tuple[str, dict]]) -> None:
    """Show two single-source graphs side-by-side for manual comparison."""
    if len(data_list) != 2:
        for fname, data in data_list:
            render_single_graph(data, fname)
        return

    (fn_a, da), (fn_b, db) = data_list
    facts_a = {detect_fact_type(f): [] for f in FACT_TYPE_LABEL}
    facts_b = {detect_fact_type(f): [] for f in FACT_TYPE_LABEL}
    for f in da.get("facts", []):
        facts_a.setdefault(detect_fact_type(f), []).append(f)
    for f in db.get("facts", []):
        facts_b.setdefault(detect_fact_type(f), []).append(f)

    console.print()
    console.print(Rule(
        f"[blue bold]{fn_a}[/blue bold]  [dim]vs[/dim]  [dark_orange bold]{fn_b}[/dark_orange bold]"
    ))

    all_types = sorted(set(list(facts_a.keys()) + list(facts_b.keys())))

    for ftype in all_types:
        ba = facts_a.get(ftype, [])
        bb = facts_b.get(ftype, [])
        if not ba and not bb:
            continue

        type_label, type_color = FACT_TYPE_LABEL.get(ftype, ("UNKNOWN", "grey50"))

        def make_panel(bucket, fname, src_color):
            if not bucket:
                return Panel("[dim]none[/dim]", title=f"[{src_color}]{fname}[/{src_color}]",
                             border_style=src_color, expand=True)
            lines = Text()
            for f in bucket:
                lines.append_text(fact_to_text(f))
                prov = f.get("provenance") or ""
                if prov:
                    lines.append(f'\n  "{prov}"', style="dim italic")
                lines.append("\n")
            return Panel(lines, title=f"[{src_color}]{fname}[/{src_color}]",
                         border_style=src_color, expand=True)

        console.print(f"\n  [{type_color}]{type_label}[/{type_color}]")
        console.print(Columns([
            make_panel(ba, fn_a, "blue"),
            make_panel(bb, fn_b, "dark_orange"),
        ], expand=True))


# ── legend ────────────────────────────────────────────────────────────────────

def print_legend(is_merged: bool) -> None:
    console.print()
    if is_merged:
        console.print(
            "  [steel_blue]● shared[/steel_blue]"
            "  [green]● novel (user-only)[/green]"
            "  [red]✖ conflict[/red]"
            "  [dim]  |  italic = partial fact[/dim]"
        )
    else:
        console.print(
            "  [blue]◆ base (telemetry)[/blue]"
            "  [dark_orange]◇ new (user report)[/dark_orange]"
            "  [dim]  |  italic = partial fact[/dim]"
        )


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        console.print("[red]Usage:[/red] python vizkg.py <file.json> [file2.json ...]")
        sys.exit(1)

    loaded = []
    for p in paths:
        path = pathlib.Path(p)
        if not path.exists():
            console.print(f"[red]File not found:[/red] {p}")
            sys.exit(1)
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            console.print(f"[red]JSON parse error in {p}:[/red] {e}")
            sys.exit(1)
        loaded.append((path.name, data))

    # decide render mode
    if len(loaded) == 1:
        fname, data = loaded[0]
        is_merged = bool(data.get("conflicts"))
        print_legend(is_merged)
        if is_merged:
            render_merged_graph(data, fname)
        else:
            render_single_graph(data, fname)
    elif len(loaded) == 2:
        # check if either is merged
        any_merged = any(d.get("conflicts") for _, d in loaded)
        if any_merged:
            for fname, data in loaded:
                is_merged = bool(data.get("conflicts"))
                print_legend(is_merged)
                render_merged_graph(data, fname) if is_merged else render_single_graph(data, fname)
        else:
            print_legend(False)
            render_side_by_side(loaded)
    else:
        for fname, data in loaded:
            is_merged = bool(data.get("conflicts"))
            print_legend(is_merged)
            if is_merged:
                render_merged_graph(data, fname)
            else:
                render_single_graph(data, fname)

    console.print()


if __name__ == "__main__":
    main()