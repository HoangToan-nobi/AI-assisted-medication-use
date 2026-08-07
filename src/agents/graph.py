from langgraph.graph import END, StateGraph

from src.agents.nodes.explain_node import explain_node
from src.agents.nodes.guardrail_node import guardrail_node
from src.agents.nodes.lookup_node import lookup_node
from src.agents.nodes.normalize_node import normalize_node
from src.agents.nodes.rank_node import rank_node
from src.agents.state import MedCheckState


def should_continue(state: MedCheckState) -> str:
    """Route based on whether an error occurred during processing."""
    if state.get("error"):
        return END
    return "continue"


def build_graph() -> StateGraph:
    graph = StateGraph(MedCheckState)

    # Add nodes
    graph.add_node("normalize", normalize_node)
    graph.add_node("lookup", lookup_node)
    graph.add_node("rank", rank_node)
    graph.add_node("explain", explain_node)
    graph.add_node("guardrail", guardrail_node)

    # Add edges
    graph.set_entry_point("normalize")
    graph.add_conditional_edges("normalize", should_continue, {END: END, "continue": "lookup"})
    graph.add_conditional_edges("lookup", should_continue, {END: END, "continue": "rank"})
    graph.add_conditional_edges("rank", should_continue, {END: END, "continue": "explain"})
    graph.add_conditional_edges("explain", should_continue, {END: END, "continue": "guardrail"})
    graph.add_conditional_edges("guardrail", should_continue, {END: END, "continue": END})

    return graph.compile()


agent = build_graph()
