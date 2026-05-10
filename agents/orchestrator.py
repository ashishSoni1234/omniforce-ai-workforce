from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from agents.sales_agent import SalesAgent
from agents.ops_agent import OpsAgent
from agents.kyc_agent import KYCAgent

SALES_KEYWORDS = {"lead", "prospect", "crm", "sales", "follow", "find", "research", "email", "chase", "update", "company", "companies", "fintech", "startup", "revenue", "outreach"}
# NOTE: removed 'process','review' — too generic, causes false matches on sales prompts like 'payment processing'
OPS_KEYWORDS = {"invoice", "timesheet", "ops", "approve", "report", "summary", "route", "document", "anomal", "upload", "pdf"}
KYC_KEYWORDS = {"kyc", "compliance", "onboard", "verify", "risk", "check", "aml", "due diligence", "new client"}


class WorkflowState(TypedDict):
    task: str
    agent_type: str
    instruction: str
    document_content: str
    client_data: dict
    result: Optional[dict]
    error: Optional[str]
    status: str


def _router_node(state: WorkflowState) -> WorkflowState:
    task = state.get("task", "").lower()
    print(f"[Orchestrator] Routing task: {task[:80]}")

    # If agent_type was explicitly set (from UI), trust it — skip keyword scoring
    existing_agent = state.get("agent_type", "")
    if existing_agent in ("sales", "ops", "kyc"):
        print(f"[Orchestrator] Using explicit agent override: {existing_agent} (keyword routing skipped)")
        return {**state, "status": "routing_complete"}

    kyc_score = sum(1 for kw in KYC_KEYWORDS if kw in task)
    ops_score = sum(1 for kw in OPS_KEYWORDS if kw in task)
    sales_score = sum(1 for kw in SALES_KEYWORDS if kw in task)

    if kyc_score > 0 and kyc_score >= ops_score and kyc_score >= sales_score:
        agent_type = "kyc"
    elif ops_score > 0 and ops_score >= sales_score:
        agent_type = "ops"
    else:
        agent_type = "sales"

    print(f"[Orchestrator] Keyword routing decision: {agent_type} (scores: sales={sales_score}, ops={ops_score}, kyc={kyc_score})")
    return {**state, "agent_type": agent_type, "status": "routing_complete"}


def _sales_node(state: WorkflowState) -> WorkflowState:
    print("[Orchestrator] Executing Sales Agent")
    try:
        agent = SalesAgent()
        result = agent.run(state["instruction"])
        print(f"[Orchestrator] Sales Agent completed. Status: {result.get('status')}")
        return {**state, "result": result, "status": "complete"}
    except Exception as e:
        error_msg = f"[Orchestrator] Sales Agent error: {str(e)}"
        print(error_msg)
        return {**state, "result": None, "error": error_msg, "status": "error"}


def _ops_node(state: WorkflowState) -> WorkflowState:
    print("[Orchestrator] Executing Ops Agent")
    try:
        agent = OpsAgent()
        result = agent.run(
            state["instruction"],
            state.get("document_content", ""),
        )
        print(f"[Orchestrator] Ops Agent completed. Status: {result.get('status')}")
        return {**state, "result": result, "status": "complete"}
    except Exception as e:
        error_msg = f"[Orchestrator] Ops Agent error: {str(e)}"
        print(error_msg)
        return {**state, "result": None, "error": error_msg, "status": "error"}


def _kyc_node(state: WorkflowState) -> WorkflowState:
    print("[Orchestrator] Executing KYC Agent")
    try:
        agent = KYCAgent()
        result = agent.run(
            state["instruction"],
            state.get("client_data", {}),
        )
        print(f"[Orchestrator] KYC Agent completed. Status: {result.get('status')}")
        return {**state, "result": result, "status": "complete"}
    except Exception as e:
        error_msg = f"[Orchestrator] KYC Agent error: {str(e)}"
        print(error_msg)
        return {**state, "result": None, "error": error_msg, "status": "error"}


def _route_to_agent(state: WorkflowState) -> str:
    agent_type = state.get("agent_type", "sales")
    route_map = {"sales": "sales_node", "ops": "ops_node", "kyc": "kyc_node"}
    return route_map.get(agent_type, "sales_node")


def _build_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)

    graph.add_node("router", _router_node)
    graph.add_node("sales_node", _sales_node)
    graph.add_node("ops_node", _ops_node)
    graph.add_node("kyc_node", _kyc_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        _route_to_agent,
        {
            "sales_node": "sales_node",
            "ops_node": "ops_node",
            "kyc_node": "kyc_node",
        },
    )

    graph.add_edge("sales_node", END)
    graph.add_edge("ops_node", END)
    graph.add_edge("kyc_node", END)

    return graph.compile()


_compiled_graph = _build_graph()


def run_workflow(
    task: str,
    instruction: str,
    document_content: str = "",
    client_data: dict = {},
    explicit_agent: str = "",
) -> dict:
    print(f"[Orchestrator] Starting workflow for task: {task[:80]}")

    # If the UI explicitly specifies the agent, skip keyword routing entirely
    forced_agent = explicit_agent.lower().strip() if explicit_agent else ""
    if forced_agent in ("sales", "ops", "kyc"):
        print(f"[Orchestrator] Explicit agent override: {forced_agent} (skipping keyword routing)")

    initial_state: WorkflowState = {
        "task": task,
        # Pre-set agent_type so router can be overridden below
        "agent_type": forced_agent if forced_agent in ("sales", "ops", "kyc") else "sales",
        "instruction": instruction,
        "document_content": document_content,
        "client_data": client_data,
        "result": None,
        "error": None,
        "status": "pending",
    }

    try:
        final_state = _compiled_graph.invoke(initial_state)
        print(f"[Orchestrator] Workflow complete. Agent: {final_state.get('agent_type')}, Status: {final_state.get('status')}")
        return {
            "agent_used": final_state.get("agent_type"),
            "status": final_state.get("status"),
            "result": final_state.get("result"),
            "error": final_state.get("error"),
        }
    except Exception as e:
        error_msg = f"[Orchestrator] Workflow execution failed: {str(e)}"
        print(error_msg)
        return {
            "agent_used": "unknown",
            "status": "error",
            "result": None,
            "error": error_msg,
        }
