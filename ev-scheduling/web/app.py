"""FastAPI chat server for the EV Charging Schedule Agent.

Serves the HTML chat UI at GET / and handles chat messages at POST /api/chat.
Runs the real Python agent (including CVXPY solver) inline.

Usage (from project root):
    uvicorn web.app:app --reload --port 8000
    # Then open http://localhost:8000

Requires OPENAI_API_KEY in .env or the environment.
"""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so agent imports work when the
# server is started from any directory.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

app = FastAPI(title="EV Charging Schedule Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_HTML_PATH = Path(__file__).parent / "index.html"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    include_visualization: bool = True
    include_images: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FOLLOWUP_INDICATORS = [
    "same scenario", "same evs", "same setup", "same situation",
    "those evs", "the evs", "these evs", "previous", "again",
    "what if", "but with", "instead", "also", "now", "try",
    "modify", "change", "adjust", "update", "redo",
]


def _is_followup_question(message: str) -> bool:
    """Check if the message is a follow-up referencing previous context."""
    msg_lower = message.lower()
    return any(indicator in msg_lower for indicator in _FOLLOWUP_INDICATORS)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the chat UI."""
    if not _HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=_HTML_PATH.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat(req: ChatRequest) -> JSONResponse:
    """Run the agent on the user's message and return a response.

    agent parses user's input, extract session
    parameters, and calls the CVXPY solver to compute an optimal schedule.
    If required information is missing, agent asks for clarification

    Accepts:
        message: The user's latest message.
        history: Prior turns (used for display only; agent is stateless per call).
        include_visualization: If True, include structured visualization data.
        include_images: If True, include PNG images.

    Returns:
        {
            "response": str,
            "needs_clarification": bool,
            "missing_fields": [...] (if needs_clarification=True),
            "visualization": {...} (if include_visualization=True and schedule was computed)
        }
        or on error:
        { "error": str }
    """
    try:
        from agent.run import run_agent_from_text, ClarificationResult, AgentResult
        from agent.parse.parse import parse_nl_problem, parsed_problem_to_day_site_tou
    except ImportError as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Agent import failed: {exc}. Make sure you are running from the project root."},
        )

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse(
            status_code=500,
            content={"error": "OPENAI_API_KEY is not set. Add it to .env or set it in your environment."},
        )

    # Build context from conversation history for follow-up questions
    # Include recent user messages so agent can understand references like "same scenario"
    context_parts = []
    for msg in req.history[-6:]:  # Last 3 exchanges (6 messages)
        if msg.role == "user":
            context_parts.append(f"User previously said: {msg.content}")
    
    # Combine history context with current message
    if context_parts and _is_followup_question(req.message):
        full_message = "\n".join(context_parts) + f"\n\nCurrent request: {req.message}"
    else:
        full_message = req.message

    try:
        result = run_agent_from_text(full_message, api_key=api_key)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Agent error: {exc}"},
        )

    if isinstance(result, ClarificationResult):
        # Parse again to get the missing_fields list for the UI
        try:
            parse_result = parse_nl_problem(req.message, api_key=api_key)
            missing = parse_result.missing_fields
        except Exception:
            missing = []

        return JSONResponse(content={
            "response": result.message,
            "needs_clarification": True,
            "missing_fields": missing,
        })

    # Check if inference was used
    used_inference = False
    inference_notes: List[str] = []
    try:
        parse_result = parse_nl_problem(req.message, api_key=api_key)
        used_inference = parse_result.used_inference
        inference_notes = parse_result.inference_notes
    except Exception:
        pass

    response_content: Dict[str, Any] = {
        "response": result.explanation,
        "needs_clarification": False,
        "used_inference": used_inference,
        "inference_notes": inference_notes,
    }

    if req.include_visualization:
        try:
            from visualization.output import build_visualization_data
            from evaluation.metrics import pct_fully_served as calc_pct_served

            parse_result = parse_nl_problem(req.message, api_key=api_key)
            if parse_result.problem is not None:
                day, site, tou = parsed_problem_to_day_site_tou(parse_result.problem)
                pct_served = calc_pct_served(result.schedule, day, day.dt_hours)

                viz_data = build_visualization_data(
                    schedule=result.schedule,
                    day=day,
                    total_cost_usd=result.total_cost_usd,
                    peak_load_kw=result.peak_load_kw,
                    unmet_energy_kwh=result.unmet_energy_kwh,
                    pct_fully_served=pct_served,
                    explanation=result.explanation,
                    feasible=result.feasible,
                    include_images=req.include_images,
                )
                response_content["visualization"] = viz_data.to_dict()
        except Exception:
            pass

    return JSONResponse(content=response_content)


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """Simple health check."""
    api_key_set = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return {"status": "ok", "api_key_set": api_key_set}
