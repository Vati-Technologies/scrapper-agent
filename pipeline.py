from typing import Annotated, TypedDict
from operator import add
from langgraph.graph import StateGraph, START, END

from nodes.scrape_node   import scrape_node
from nodes.enrich_node   import enrich_node
from nodes.dedup_node    import dedup_node
from nodes.analyze_node  import analyze_node
from nodes.excel_node    import excel_node
from nodes.deliver_node  import deliver_node


# ── State ─────────────────────────────────────────────────────────────────────

class LeadGenState(TypedDict):
    # Input
    client_id:              str
    whatsapp_number:        str
    industry:               str
    city:                   str
    request_id:             int
    star_min:               float | None
    star_max:               float | None

    # Pipeline data
    raw_businesses:         list
    enriched_businesses:    list
    new_businesses:         list
    analyzed_businesses:    list

    # Output
    excel_path:             str
    delivery_status:        str

    # Error accumulator
    errors: Annotated[list, add]


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_pipeline():
    graph = StateGraph(LeadGenState)

    graph.add_node("scrape",   scrape_node)
    graph.add_node("enrich",   enrich_node)
    graph.add_node("dedup",    dedup_node)
    graph.add_node("analyze",  analyze_node)
    graph.add_node("excel",    excel_node)
    graph.add_node("deliver",  deliver_node)

    graph.add_edge(START,     "scrape")
    graph.add_edge("scrape",  "enrich")
    graph.add_edge("enrich",  "dedup")
    graph.add_edge("dedup",   "analyze")
    graph.add_conditional_edges("analyze", _check_leads, {"ok": "excel", "empty": END})
    graph.add_edge("excel",   "deliver")
    graph.add_edge("deliver", END)

    return graph.compile()


def _check_leads(state: LeadGenState) -> str:
    """If no leads survived dedup + analysis, end early."""
    if not state.get("analyzed_businesses"):
        return "empty"
    return "ok"


# ── Entry point ───────────────────────────────────────────────────────────────

pipeline = build_pipeline()


def run_pipeline(
    client_id: str,
    whatsapp_number: str,
    industry: str,
    city: str,
    request_id: int,
    star_min: float | None = None,
    star_max: float | None = None,
) -> dict:
    initial_state = {
        "client_id":            client_id,
        "whatsapp_number":      whatsapp_number,
        "industry":             industry,
        "city":                 city,
        "request_id":           request_id,
        "star_min":             star_min,
        "star_max":             star_max,
        "raw_businesses":       [],
        "enriched_businesses":  [],
        "new_businesses":       [],
        "analyzed_businesses":  [],
        "excel_path":           "",
        "delivery_status":      "",
        "errors":               [],
    }

    result = pipeline.invoke(initial_state)
    return result
