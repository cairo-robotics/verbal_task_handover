"""
Pipeline Visualizer — Handover Knowledge Graph Explorer
Run:  python app.py
Then open http://localhost:8050
"""
import json, base64, pathlib
from typing import Any

import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update
import dash_cytoscape as cyto

cyto.load_extra_layouts()

# ── helpers ──────────────────────────────────────────────────────────────────

def arg_label(arg: dict | None) -> str:
    if not arg:
        return "?"
    if arg.get("type") == "existential":
        return "unknown"
    return arg.get("value") or "?"


def loc_label(loc: dict | None) -> str:
    if not loc:
        return "?"
    if loc.get("type") == "room":
        return loc.get("room") or "?"
    dirs = loc.get("directions") or []
    mode = loc.get("mode") or "set"
    sep = " then " if mode == "path" else " and "
    return sep.join(dirs) if dirs else "?"


def detect_fact_type(fact: dict) -> str:
    """Infer which pydantic model this fact represents."""
    if "predicate" in fact:
        return "relation"
    if "entity" in fact and "location" in fact and "direction" not in fact:
        return "location"
    if "subject" in fact and "direction" in fact and "location_a" not in fact:
        return "spatial"
    if "location_a" in fact:
        return "connection"
    return "unknown"


def fact_summary(fact: dict) -> str:
    ftype = detect_fact_type(fact)
    if ftype == "relation":
        s = arg_label(fact.get("subject"))
        pred = fact.get("predicate", "?")
        o = arg_label(fact.get("object")) if fact.get("object") else ""
        t = arg_label(fact.get("target")) if fact.get("target") else ""
        parts = [p for p in [o, t] if p and p != "?"]
        return f"{s} —[{pred}]→ {', '.join(parts) or '?'}"
    if ftype == "location":
        e = arg_label(fact.get("entity"))
        loc = loc_label(fact.get("location"))
        return f"{e} in {loc}"
    if ftype == "spatial":
        s = arg_label(fact.get("subject"))
        d = fact.get("direction", "?")
        ref = arg_label(fact.get("reference")) if fact.get("reference") else ""
        return f"{s} is {d}" + (f" of {ref}" if ref else "")
    if ftype == "connection":
        a = loc_label(fact.get("location_a"))
        b = loc_label(fact.get("location_b"))
        d = fact.get("direction", "")
        return f"{a} ↔ {b}" + (f" ({d})" if d else "")
    return "unknown fact"


# ── graph builder ─────────────────────────────────────────────────────────────

SOURCE_COLORS = {
    "base": "#185FA5",      # blue
    "new":  "#854F0B",      # amber
    "both": "#3B6D11",      # green  (shared/novel in merged)
}
CONFLICT_COLOR = "#A32D2D"  # red

FACT_TYPE_SHAPES = {
    "relation":   "round-rectangle",
    "location":   "ellipse",
    "spatial":    "diamond",
    "connection": "hexagon",
    "unknown":    "rectangle",
}


def classify_merged_fact(fact: dict, conflict_fact_ids: set) -> str:
    """For merged graphs: shared / novel / conflict."""
    fid = fact.get("id", "")
    if fid in conflict_fact_ids:
        return "conflict"
    src = fact.get("source", "")
    if src == "new":
        return "novel"
    return "shared"


def build_cyto_elements(data: dict, mode: str) -> list[dict]:
    """Convert a KnowledgeGraph dict into cytoscape elements."""
    facts = data.get("facts", [])
    conflicts = data.get("conflicts", [])
    conflict_base_ids = {c["base_fact_id"] for c in conflicts}
    conflict_new_ids  = {c["new_fact"]["id"] for c in conflicts}
    all_conflict_ids  = conflict_base_ids | conflict_new_ids

    nodes: dict[str, dict] = {}   # node_id → data dict
    edges: list[dict] = []

    def ensure_entity_node(label: str, node_id: str, source: str, shape: str = "ellipse") -> str:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id, "label": label,
                "kind": "entity", "source": source,
                "shape": shape, "color": SOURCE_COLORS.get(source, "#888"),
            }
        return node_id

    def ensure_room_node(room: str, source: str) -> str:
        nid = f"room:{room}"
        if nid not in nodes:
            nodes[nid] = {
                "id": nid, "label": room,
                "kind": "room", "source": source,
                "shape": "round-rectangle",
                "color": SOURCE_COLORS.get(source, "#888"),
            }
        return nid

    for fact in facts:
        fid    = fact.get("id", "?")
        source = fact.get("source") or "base"
        ftype  = detect_fact_type(fact)
        partial = fact.get("is_partial", False)
        provenance = fact.get("provenance") or ""

        if mode == "merged":
            cls = classify_merged_fact(fact, all_conflict_ids)
            color = {"shared": SOURCE_COLORS["base"],
                     "novel":  SOURCE_COLORS["new"],
                     "conflict": CONFLICT_COLOR}.get(cls, "#888")
            edge_color = color
        else:
            color = SOURCE_COLORS.get(source, "#888")
            edge_color = color
            cls = source

        # ── location fact: entity → room ────────────────────────────────────
        if ftype == "location":
            entity = fact.get("entity", {})
            elabel = arg_label(entity)
            enid   = f"entity:{elabel}"
            ensure_entity_node(elabel, enid, source)

            loc = fact.get("location", {})
            if loc.get("type") == "room":
                rnid = ensure_room_node(loc.get("room", "?"), source)
                edges.append({"source": enid, "target": rnid,
                               "label": "in", "color": edge_color,
                               "partial": partial, "cls": cls,
                               "provenance": provenance, "fact_id": fid})
            else:
                # directional — create a virtual direction node
                dlabel = loc_label(loc)
                dnid = f"dir:{fid}"
                nodes[dnid] = {"id": dnid, "label": f"~ {dlabel}",
                               "kind": "direction", "source": source,
                               "shape": "diamond", "color": color}
                edges.append({"source": enid, "target": dnid,
                               "label": "~in", "color": edge_color,
                               "partial": True, "cls": cls,
                               "provenance": provenance, "fact_id": fid})

        # ── relation fact ────────────────────────────────────────────────────
        elif ftype == "relation":
            subj   = fact.get("subject", {})
            obj    = fact.get("object")
            target = fact.get("target")
            pred   = fact.get("predicate", "?")

            slabel = arg_label(subj)
            snid   = f"entity:{slabel}"
            ensure_entity_node(slabel, snid, source)

            if obj:
                olabel = arg_label(obj)
                onid   = f"entity:{olabel}"
                ensure_entity_node(olabel, onid, source)
                edges.append({"source": snid, "target": onid,
                               "label": pred, "color": edge_color,
                               "partial": partial, "cls": cls,
                               "provenance": provenance, "fact_id": fid})
            if target:
                tlabel = arg_label(target)
                tnid   = f"entity:{tlabel}"
                ensure_entity_node(tlabel, tnid, source)
                edges.append({"source": snid, "target": tnid,
                               "label": f"{pred} →", "color": edge_color,
                               "partial": partial, "cls": cls,
                               "provenance": provenance, "fact_id": fid})

        # ── spatial fact ─────────────────────────────────────────────────────
        elif ftype == "spatial":
            subj = fact.get("subject", {})
            ref  = fact.get("reference")
            d    = fact.get("direction", "?")
            slabel = arg_label(subj)
            snid   = f"entity:{slabel}"
            ensure_entity_node(slabel, snid, source)
            if ref:
                rlabel = arg_label(ref)
                rnid   = f"entity:{rlabel}"
                ensure_entity_node(rlabel, rnid, source)
                edges.append({"source": snid, "target": rnid,
                               "label": d + " of", "color": edge_color,
                               "partial": partial, "cls": cls,
                               "provenance": provenance, "fact_id": fid})

        # ── connection fact ──────────────────────────────────────────────────
        elif ftype == "connection":
            la = fact.get("location_a", {})
            lb = fact.get("location_b", {})
            d  = fact.get("direction", "")
            anid = ensure_room_node(loc_label(la), source)
            bnid = ensure_room_node(loc_label(lb), source)
            edges.append({"source": anid, "target": bnid,
                           "label": d or "connects", "color": edge_color,
                           "partial": partial, "cls": cls,
                           "provenance": provenance, "fact_id": fid})

    elements = []
    for nid, nd in nodes.items():
        elements.append({"data": {**nd}, "classes": nd.get("kind", "")})

    for i, e in enumerate(edges):
        eid = f"e{i}"
        elements.append({"data": {
            "id": eid, "source": e["source"], "target": e["target"],
            "label": e["label"], "color": e["color"],
            "partial": e["partial"], "cls": e["cls"],
            "provenance": e["provenance"], "fact_id": e["fact_id"],
        }})

    return elements


def build_conflict_cards(conflicts: list[dict]) -> list:
    if not conflicts:
        return [html.P("No conflicts.", style={"color": "#888", "font-size": "13px"})]
    cards = []
    for c in conflicts:
        nf = c.get("new_fact", {})
        cards.append(html.Div([
            html.Div([
                html.Span("CONFLICT", style={
                    "background": "#FCEBEB", "color": "#A32D2D",
                    "font-size": "10px", "font-weight": "600",
                    "padding": "2px 8px", "border-radius": "20px",
                    "letter-spacing": ".05em",
                }),
                html.Span(f"  field: {c.get('field_name','?')}",
                          style={"font-size": "12px", "color": "#666", "margin-left": "8px"}),
            ], style={"margin-bottom": "6px"}),
            html.Div([
                html.Span("Base: ", style={"color": "#185FA5", "font-weight": "500", "font-size": "12px"}),
                html.Code(json.dumps(c.get("base_value", "?"), indent=None),
                          style={"font-size": "12px"}),
            ]),
            html.Div([
                html.Span("Report: ", style={"color": "#854F0B", "font-weight": "500", "font-size": "12px"}),
                html.Code(json.dumps(c.get("new_value", "?"), indent=None),
                          style={"font-size": "12px"}),
            ], style={"margin-top": "2px"}),
            html.Div(
                f'Provenance: "{nf.get("provenance","")}"' if nf.get("provenance") else "",
                style={"font-size": "11px", "color": "#888", "margin-top": "4px",
                       "font-style": "italic"}
            ),
        ], style={
            "border": "0.5px solid #F09595",
            "border-radius": "8px",
            "padding": "10px 12px",
            "margin-bottom": "8px",
            "background": "#FFFAFA",
        }))
    return cards


# ── cytoscape stylesheet ─────────────────────────────────────────────────────

CYTO_STYLESHEET = [
    {"selector": "node", "style": {
        "label": "data(label)",
        "text-valign": "center", "text-halign": "center",
        "font-size": "11px", "font-family": "monospace",
        "color": "#fff",
        "background-color": "data(color)",
        "shape": "data(shape)",
        "width": "label", "height": "label",
        "padding": "8px",
        "border-width": 1, "border-color": "#fff",
    }},
    {"selector": "node.room", "style": {
        "font-size": "12px", "font-weight": "bold",
        "padding": "10px",
    }},
    {"selector": "node.direction", "style": {
        "border-style": "dashed", "opacity": 0.75,
    }},
    {"selector": "edge", "style": {
        "label": "data(label)",
        "font-size": "10px",
        "text-rotation": "autorotate",
        "text-margin-y": "-8px",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "arrow-scale": 1.2,
        "line-color": "data(color)",
        "target-arrow-color": "data(color)",
        "color": "#444",
        "width": 1.5,
    }},
    {"selector": "edge[partial = true]", "style": {
        "line-style": "dashed",
        "opacity": 0.7,
    }},
]


# ── layout ────────────────────────────────────────────────────────────────────

LEGEND_ITEMS_SINGLE = [
    ("#185FA5", "Telemetry (base)"),
    ("#854F0B", "User report (new)"),
]
LEGEND_ITEMS_MERGED = [
    ("#185FA5", "Shared fact"),
    ("#3B6D11", "Novel (user-only)"),
    ("#A32D2D", "Conflict"),
]


def legend(items: list) -> html.Div:
    return html.Div([
        html.Div([
            html.Span(style={"display": "inline-block", "width": "12px", "height": "12px",
                             "border-radius": "50%", "background": color,
                             "margin-right": "6px", "vertical-align": "middle"}),
            html.Span(label, style={"font-size": "12px", "color": "#555", "vertical-align": "middle"}),
        ], style={"margin-right": "16px", "display": "inline-block"})
        for color, label in items
    ] + [
        html.Span("── solid = certain  ╌╌ dashed = partial",
                  style={"font-size": "11px", "color": "#999", "margin-left": "8px"})
    ], style={"margin-bottom": "10px"})


app = dash.Dash(__name__, title="Pipeline Visualizer")

app.layout = html.Div([
    html.H2("Handover pipeline visualizer",
            style={"font-size": "18px", "font-weight": "500",
                   "margin": "0 0 4px", "color": "#1a1a1a"}),
    html.P("Load a knowledge graph JSON from any pipeline stage to inspect facts and conflicts.",
           style={"font-size": "13px", "color": "#666", "margin": "0 0 16px"}),

    # ── file loader ──────────────────────────────────────────────────────────
    html.Div([
        dcc.Upload(
            id="upload",
            children=html.Div([
                "Drop a JSON file here or ",
                html.A("browse", style={"color": "#185FA5", "cursor": "pointer"}),
            ], style={"font-size": "13px", "color": "#555"}),
            style={
                "border": "1px dashed #bbb", "border-radius": "8px",
                "padding": "16px 20px", "text-align": "center",
                "background": "#fafafa", "cursor": "pointer",
                "margin-bottom": "8px",
            },
            multiple=False,
        ),
        html.Div(id="sample-buttons", children=[
            html.Span("Load sample: ", style={"font-size": "12px", "color": "#888"}),
            *[html.Button(name, id=f"btn-{name}", n_clicks=0,
                          style={"font-size": "12px", "margin": "0 4px",
                                 "padding": "3px 10px", "cursor": "pointer"})
              for name in ("telemetry_graph", "user_report_graph", "merged_graph")],
        ], style={"margin-bottom": "12px"}),
    ]),

    # ── status bar ───────────────────────────────────────────────────────────
    html.Div(id="status-bar", style={"font-size": "12px", "color": "#888", "margin-bottom": "10px"}),

    # ── legend ───────────────────────────────────────────────────────────────
    html.Div(id="legend-div"),

    # ── main content ─────────────────────────────────────────────────────────
    html.Div([
        # graph panel
        html.Div([
            cyto.Cytoscape(
                id="graph",
                layout={"name": "cose", "animate": False,
                        "nodeRepulsion": 8000, "idealEdgeLength": 120,
                        "gravity": 0.25},
                style={"width": "100%", "height": "520px",
                       "border": "0.5px solid #e0e0e0", "border-radius": "8px",
                       "background": "#f9f9f9"},
                elements=[],
                stylesheet=CYTO_STYLESHEET,
                responsive=True,
            ),
            html.Div([
                html.Label("Layout:", style={"font-size": "12px", "color": "#666",
                                             "margin-right": "6px"}),
                dcc.Dropdown(
                    id="layout-select",
                    options=[{"label": l, "value": l}
                             for l in ["cose", "cola", "breadthfirst", "circle", "grid"]],
                    value="cose",
                    clearable=False,
                    style={"width": "160px", "font-size": "12px", "display": "inline-block"},
                ),
            ], style={"margin-top": "8px", "display": "flex", "align-items": "center"}),
        ], style={"flex": "1 1 60%", "min-width": "0"}),

        # side panel
        html.Div([
            html.Div(id="detail-panel", children=[
                html.P("Click a node or edge to inspect it.",
                       style={"font-size": "13px", "color": "#999"}),
            ], style={
                "border": "0.5px solid #e0e0e0", "border-radius": "8px",
                "padding": "12px", "min-height": "200px", "margin-bottom": "12px",
                "background": "#fff",
            }),
            html.Div([
                html.H4("Conflicts", style={"font-size": "14px", "font-weight": "500",
                                            "margin": "0 0 8px"}),
                html.Div(id="conflict-panel"),
            ], style={
                "border": "0.5px solid #e0e0e0", "border-radius": "8px",
                "padding": "12px", "background": "#fff",
            }),
        ], style={"flex": "0 0 300px", "margin-left": "16px"}),
    ], style={"display": "flex", "align-items": "flex-start"}),

    # hidden store
    dcc.Store(id="graph-data"),

], style={"font-family": "system-ui, sans-serif", "max-width": "1200px",
           "margin": "24px auto", "padding": "0 24px"})


# ── callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("graph-data", "data"),
    Output("status-bar", "children"),
    Input("upload", "contents"),
    Input("btn-telemetry_graph", "n_clicks"),
    Input("btn-user_report_graph", "n_clicks"),
    Input("btn-merged_graph", "n_clicks"),
    State("upload", "filename"),
    prevent_initial_call=True,
)
def load_graph(contents, btn_t, btn_u, btn_m, filename):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update

    trigger = ctx.triggered[0]["prop_id"]

    if "upload" in trigger and contents:
        _, content_string = contents.split(",")
        raw = base64.b64decode(content_string)
        try:
            data = json.loads(raw)
        except Exception as e:
            return no_update, f"Error parsing JSON: {e}"
        n_facts = len(data.get("facts", []))
        n_conf  = len(data.get("conflicts", []))
        return data, f"Loaded: {filename} — {n_facts} facts, {n_conf} conflicts"

    sample_map = {
        "btn-telemetry_graph.n_clicks":   "samples/telemetry_graph.json",
        "btn-user_report_graph.n_clicks": "samples/user_report_graph.json",
        "btn-merged_graph.n_clicks":      "samples/merged_graph.json",
    }
    path = sample_map.get(trigger)
    if path and pathlib.Path(path).exists():
        data = json.loads(pathlib.Path(path).read_text())
        n_facts = len(data.get("facts", []))
        n_conf  = len(data.get("conflicts", []))
        return data, f"Loaded: {pathlib.Path(path).name} — {n_facts} facts, {n_conf} conflicts"

    return no_update, "Sample file not found."


@app.callback(
    Output("graph", "elements"),
    Output("conflict-panel", "children"),
    Output("legend-div", "children"),
    Input("graph-data", "data"),
)
def render_graph(data):
    if not data:
        return [], [html.P("No data loaded.", style={"font-size": "13px", "color": "#999"})], []

    conflicts = data.get("conflicts", [])
    mode = "merged" if conflicts else "single"
    elements = build_cyto_elements(data, mode)
    conflict_cards = build_conflict_cards(conflicts)
    leg = legend(LEGEND_ITEMS_MERGED if mode == "merged" else LEGEND_ITEMS_SINGLE)
    return elements, conflict_cards, leg


@app.callback(
    Output("graph", "layout"),
    Input("layout-select", "value"),
)
def update_layout(layout_name):
    base = {"name": layout_name, "animate": False}
    if layout_name == "cose":
        base.update({"nodeRepulsion": 8000, "idealEdgeLength": 120, "gravity": 0.25})
    return base


@app.callback(
    Output("detail-panel", "children"),
    Input("graph", "tapNodeData"),
    Input("graph", "tapEdgeData"),
    State("graph-data", "data"),
)
def show_detail(node_data, edge_data, graph_data):
    ctx = callback_context
    if not ctx.triggered or not graph_data:
        return html.P("Click a node or edge to inspect it.",
                      style={"font-size": "13px", "color": "#999"})

    trigger = ctx.triggered[0]["prop_id"]

    if "tapNodeData" in trigger and node_data:
        nd = node_data
        rows = [
            ("ID", nd.get("id", "?")),
            ("Label", nd.get("label", "?")),
            ("Kind", nd.get("kind", "?")),
            ("Source", nd.get("source", "?")),
        ]
        color = nd.get("color", "#888")
        return [
            html.Div([
                html.Span("●", style={"color": color, "font-size": "18px", "margin-right": "8px"}),
                html.Span(nd.get("label", "?"),
                          style={"font-size": "14px", "font-weight": "500"}),
            ], style={"margin-bottom": "10px"}),
            html.Table([
                html.Tr([html.Td(k, style={"color": "#888", "font-size": "12px",
                                           "padding": "2px 12px 2px 0", "white-space": "nowrap"}),
                         html.Td(v, style={"font-size": "12px", "font-family": "monospace"})])
                for k, v in rows
            ]),
        ]

    if "tapEdgeData" in trigger and edge_data:
        ed = edge_data
        cls = ed.get("cls", "")
        cls_colors = {"base": "#185FA5", "new": "#854F0B",
                      "shared": "#185FA5", "novel": "#3B6D11", "conflict": "#A32D2D"}
        cls_color = cls_colors.get(cls, "#888")
        rows = [
            ("Predicate", ed.get("label", "?")),
            ("From", ed.get("source", "?")),
            ("To",   ed.get("target", "?")),
            ("Class", cls),
            ("Partial", str(ed.get("partial", False))),
        ]
        prov = ed.get("provenance") or ""
        return [
            html.Div([
                html.Span(ed.get("label", "?"),
                          style={"font-size": "14px", "font-weight": "500",
                                 "border-bottom": f"2px solid {cls_color}",
                                 "padding-bottom": "2px"}),
                html.Span(f"  [{cls}]", style={"font-size": "12px", "color": cls_color,
                                               "margin-left": "8px"}),
            ], style={"margin-bottom": "10px"}),
            html.Table([
                html.Tr([html.Td(k, style={"color": "#888", "font-size": "12px",
                                           "padding": "2px 12px 2px 0", "white-space": "nowrap"}),
                         html.Td(v, style={"font-size": "12px", "font-family": "monospace"})])
                for k, v in rows
            ]),
            html.Div([
                html.Span("Provenance: ", style={"font-size": "11px", "color": "#888"}),
                html.Em(f'"{prov}"' if prov else "none",
                        style={"font-size": "11px", "color": "#666"}),
            ], style={"margin-top": "8px", "border-top": "0.5px solid #eee", "padding-top": "6px"}),
        ]

    return html.P("Click a node or edge to inspect it.",
                  style={"font-size": "13px", "color": "#999"})


if __name__ == "__main__":
    app.run(debug=True)
