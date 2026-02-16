# A.S.C.E.N.D. Developer Guide

## Breslow QuoteApp — Multi-Model Agent Architecture

**Version:** 2.0 — Iteration 5 (Agentic)
**Last Updated:** 2026-02-16

---

## The Three Laws of the Breslow Pricing Agent

1. **Numbers are Never Generated** — Only Retrieved and Calculated
2. **The Agent is Accountable for Every Decision** — Logged with reasoning
3. **Humans Own the Rules** — Agents Execute Them

---

## 1. Architecture Overview

The A.S.C.E.N.D. platform replaces the single-LLM linear gate chain (Iteration 1) with four specialized agents, each with a distinct responsibility and trust boundary.

```
                         ┌─────────────────────┐
                         │     USER MESSAGE     │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │     SUPERVISOR       │
                         │  Claude Opus 4       │
                         │  Temp 0.0            │
                         │  Orchestration +     │
                         │  Reasoning           │
                         └──┬───────┬────────┬──┘
                            │       │        │
               ┌────────────▼──┐ ┌──▼──────┐ ┌▼────────────┐
               │ CONVERSATION  │ │ PRICING │ │ COMPLIANCE   │
               │ Claude Sonnet │ │ Python  │ │ Claude Haiku │
               │ Temp 0.3      │ │ Sandbox │ │ Temp 0.0     │
               │ UX + Dialog   │ │ Numbers │ │ Validation   │
               └───────────────┘ └─────────┘ └──────────────┘
```

### Agent Responsibilities

| Agent | Model | Temp | Role | Can Access Prices? | Can Generate Text? |
|-------|-------|------|------|--------------------|--------------------|
| **Supervisor** | Claude Opus 4 | 0.0 | Orchestration + Reasoning | Read-only (for routing) | No (internal only) |
| **Conversation** | Claude Sonnet 4 | 0.3 | UX + Dialog | NO | Yes |
| **Pricing** | Python Sandbox | N/A | Deterministic calculations | Yes (sole authority) | No |
| **Compliance** | Claude Haiku 4 | 0.0 | Validation + Verification | Read-only (for audit) | No |

### Key Design Principle

The **Conversation agent CANNOT calculate or access prices**. The **Pricing agent is NOT an LLM** — it's deterministic Python code. This separation makes hallucinated prices architecturally impossible.

---

## 2. How the 4 Workflow Patterns Map to A.S.C.E.N.D.

The four sample Python files demonstrate foundational agentic patterns. Here's how each maps to the Breslow architecture:

### Pattern 1: Prompt Chaining (`1-prompt-chaining.py`)

**What it does:** Sequential LLM calls where each step's output feeds the next. A gate check between steps decides whether to continue.

**Maps to:** The core gate-to-gate flow within the Supervisor. Each gate is a link in the chain; the Supervisor decides whether to advance or ask for more info.

```
Gate 2 (Dimensions) → gate check → Gate 19 (Orientation) → gate check → Gate 3 (Bay Logic) → ...
```

**Key code pattern:**
```python
# Extract → Gate Check → Process → Confirm
result_1 = call_gate(gate_number=2, context=dimension_context)

if result_1["status"] != "ok":
    return ask_user(result_1["question"])  # stay on gate

result_2 = call_gate(gate_number=3, context=build_bay_logic(result_1))
# ... chain continues
```

**Breslow adaptation:**
- The "gate check" is `should_advance()` — checks if status is `"ok"`
- The "chain" is `_auto_fetch_and_chain()` — auto-advances through gates that resolve without user input
- Conditional gates (19, 20, 21, 22) are skipped via `should_skip_gate()` without an API call

---

### Pattern 2: Routing (`2-routing.py`)

**What it does:** A classifier LLM determines the request type, then routes to a specialized handler.

**Maps to:** The Supervisor's routing logic. Based on the current gate and session state, it routes to the appropriate agent:

```
User says "I want an R-Blade, 20x16"
  → Supervisor classifies: product + dimensions in one message
  → Routes to: Gate 1 (product) → auto-advance → Gate 2 (dimensions)

User says "change the color to black"
  → Supervisor classifies: revision request
  → Routes to: Gate 17 (Revisions Router) → routes back to Gate 5 (Color)
```

**Key code pattern:**
```python
class RequestRouter(BaseModel):
    intent: Literal["new_quote", "revision", "question", "other"]
    target_gate: Optional[int]
    confidence: float

def route_request(user_input: str, session: SessionState) -> RequestRouter:
    """Supervisor determines what to do with the user's message."""
    response = client.responses.parse(
        model="claude-opus-4",
        instructions=ROUTING_PROMPT.format(
            current_gate=session.current_gate,
            collected_data=json.dumps(session.product_config),
        ),
        input=user_input,
        text_format=RequestRouter,
    )
    return response.output_parsed
```

**Breslow adaptation:**
- During normal flow, routing is implicit (gate sequence determines next step)
- During revisions (Gate 17), routing becomes explicit — the model picks which gate to jump back to
- The `allowed_revision_targets` list constrains where revisions can route

---

### Pattern 3: Parallelization (`3-parallelization.py`)

**What it does:** Multiple LLM calls run concurrently via `asyncio.gather()`, with results merged.

**Maps to:** Two places in the architecture:

**A) Parallel Validation (Compliance agent runs alongside every gate):**
```python
async def process_gate_with_validation(gate_number, session, user_message):
    # Run gate processing and compliance check in parallel
    gate_result, compliance_result = await asyncio.gather(
        call_gate(gate_number, session, user_message),
        run_compliance_check(gate_number, session, user_message),
    )

    if not compliance_result.is_valid:
        return handle_compliance_failure(compliance_result)

    return gate_result
```

**B) Parallel Context Building (multiple pricing lookups at once):**
```python
async def build_all_contexts(session):
    """Fetch pricing data for multiple gates in parallel."""
    base_prices, color_surcharges, lighting, heaters = await asyncio.gather(
        fetch_base_pricing(session.product_config["product_id"]),
        fetch_color_surcharges(session.product_config["product_id"]),
        fetch_lighting_fans(session.product_config["product_id"]),
        fetch_heater_items(),
    )
    return {
        "base_pricing": base_prices,
        "color_surcharges": color_surcharges,
        "lighting": lighting,
        "heaters": heaters,
    }
```

---

### Pattern 4: Orchestrator-Workers (`4-orchestrator.py`)

**What it does:** An orchestrator LLM creates a plan, then delegates sub-tasks to worker LLMs. A reviewer aggregates and polishes.

**Maps to:** The full A.S.C.E.N.D. loop. The Supervisor is the orchestrator; Conversation, Pricing, and Compliance are the workers.

```
Supervisor (plan)
  ├── Pricing Agent (compute line items)      ← Worker
  ├── Conversation Agent (format for user)    ← Worker
  └── Compliance Agent (validate output)      ← Worker/Reviewer
```

**Key code pattern (adapted for Breslow):**
```python
class GatePlan(BaseModel):
    """Supervisor's plan for processing a gate."""
    needs_user_input: bool
    needs_pricing: bool
    pricing_operations: list[str]  # e.g. ["lookup_base_price", "calc_surcharge"]
    needs_compliance: bool

class SupervisorOrchestrator:
    async def process_gate(self, gate_number, session, user_message):
        # Step 1: Supervisor creates plan
        plan = self.create_plan(gate_number, session, user_message)

        # Step 2: Execute workers based on plan
        if plan.needs_pricing:
            pricing_result = self.pricing_agent.execute(
                gate_number, session, plan.pricing_operations
            )

        if plan.needs_user_input:
            conversation_result = self.conversation_agent.generate_question(
                gate_number, session, pricing_result
            )
            return conversation_result  # send to user

        # Step 3: Compliance validates
        compliance_result = self.compliance_agent.validate(
            gate_number, session, pricing_result
        )

        if not compliance_result.passed:
            return self.handle_failure(compliance_result)

        # Step 4: Advance
        return self.advance(session, pricing_result)
```

---

## 3. Implementing Each Agent

### 3.1 Supervisor Agent

The Supervisor receives every user message, decides which gates can be resolved, and delegates to the right agents. It never generates user-facing text.

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from openai import OpenAI

SUPERVISOR_MODEL = "claude-opus-4"
SUPERVISOR_TEMP = 0.0

class SupervisorDecision(BaseModel):
    """What the Supervisor decides to do with a user message."""
    action: Literal[
        "process_gate",       # Normal: process current gate
        "chain_advance",      # Auto-advance through data-only gates
        "route_revision",     # Jump to a different gate
        "escalate",           # Flag for human review
        "reject",             # Invalid/off-topic input
    ]
    target_gate: Optional[int] = Field(
        default=None,
        description="Gate to route to (for revisions)"
    )
    reasoning: str = Field(
        description="Internal reasoning log (never shown to user)"
    )
    needs_pricing: bool = Field(
        default=False,
        description="Whether the Pricing agent should run"
    )
    needs_conversation: bool = Field(
        default=True,
        description="Whether the Conversation agent should generate a response"
    )
    confidence: float = Field(
        description="Confidence in this decision (0-1)"
    )

SUPERVISOR_PROMPT = """\
You are the Supervisor agent for the Breslow QuoteApp. Your job is to:
1. Receive the user's message and current session state
2. Decide which action to take
3. Determine which agents need to run

Current gate: {current_gate} — {gate_name}
Session data collected so far:
{collected_data}

Gate instructions:
{gate_instructions}

Rules:
- If the user provided all required info for this gate → action: process_gate
- If the gate can auto-resolve from collected data → action: chain_advance
- If the user wants to change something from a previous gate → action: route_revision
- If something looks wrong or suspicious → action: escalate
- Log your reasoning clearly for audit trail
"""

def supervisor_decide(
    user_message: str,
    gate_number: int,
    gate_name: str,
    session_data: dict,
    gate_instructions: str,
) -> SupervisorDecision:
    client = OpenAI()
    response = client.responses.parse(
        model=SUPERVISOR_MODEL,
        temperature=SUPERVISOR_TEMP,
        instructions=SUPERVISOR_PROMPT.format(
            current_gate=gate_number,
            gate_name=gate_name,
            collected_data=json.dumps(session_data, default=str),
            gate_instructions=gate_instructions,
        ),
        input=user_message,
        text_format=SupervisorDecision,
    )
    return response.output_parsed
```

### 3.2 Conversation Agent

Generates all user-facing text. Receives pre-calculated numbers from the Pricing agent — never computes them itself.

```python
CONVERSATION_MODEL = "claude-sonnet-4"
CONVERSATION_TEMP = 0.3

class ConversationResponse(BaseModel):
    """User-facing response from the Conversation agent."""
    message: str = Field(description="Friendly message to the user")
    options: Optional[list[dict]] = Field(
        default=None,
        description="Options to present (with pre-calculated prices)"
    )
    needs_input: bool = Field(
        description="Whether we're waiting for user input"
    )

CONVERSATION_PROMPT = """\
You are the Conversation agent for Breslow QuoteApp. Your ONLY job is to
communicate with the customer in a warm, professional tone.

CRITICAL RULES:
- You CANNOT calculate prices. All numbers come from the pricing_data below.
- You CANNOT access product databases. All product info comes from context.
- Present the pre-calculated results clearly. Show the math if provided.
- Ask one clear question at a time.
- Never pressure the customer.

Current gate: {gate_name}
Pricing data (from Pricing Agent — use these numbers exactly):
{pricing_data}

What to communicate:
{communication_goal}
"""

def conversation_respond(
    gate_name: str,
    pricing_data: dict,
    communication_goal: str,
    conversation_history: list[dict],
) -> ConversationResponse:
    client = OpenAI()
    response = client.responses.parse(
        model=CONVERSATION_MODEL,
        temperature=CONVERSATION_TEMP,
        instructions=CONVERSATION_PROMPT.format(
            gate_name=gate_name,
            pricing_data=json.dumps(pricing_data),
            communication_goal=communication_goal,
        ),
        input=conversation_history,
        text_format=ConversationResponse,
    )
    return response.output_parsed
```

### 3.3 Pricing Agent (Deterministic Python — NOT an LLM)

This is pure Python code, not an LLM. Same input always produces the same output.

```python
from src.app.services.pricing_loader import (
    get_base_pricing_table,
    get_color_surcharges,
    get_lighting_fans,
    get_heater_items,
    get_shade_pricing_table,
    get_shade_install_price,
    get_privacy_wall_pricing,
    get_privacy_wall_surcharges,
    get_trim_items,
    get_electrical_items,
    get_structural_items,
    get_installation_items,
    get_multibay_addons,
)
import math
import json


class PricingAgent:
    """Deterministic pricing engine. NOT an LLM.

    Law #1: Numbers are never generated — only retrieved and calculated.
    """

    def compute_base_price(
        self, product_id: str, bay_width_ft: int, bay_length_ft: int, total_bays: int
    ) -> dict:
        """Look up per-bay price and compute total."""
        table = get_base_pricing_table(product_id)

        # Exact match lookup — no interpolation
        match = next(
            (r for r in table
             if r["width_ft"] == bay_width_ft and r["length_ft"] == bay_length_ft),
            None,
        )
        if not match:
            return {
                "error": f"No price found for {bay_width_ft}x{bay_length_ft}",
                "available_sizes": [
                    f"{r['width_ft']}x{r['length_ft']}" for r in table
                ],
            }

        unit_price = match["unit_price"]
        subtotal = round(unit_price * total_bays, 2)

        return {
            "sku": match["sku"],
            "unit_price": unit_price,
            "qty": total_bays,
            "subtotal": subtotal,
            "math_trace": f"{unit_price} x {total_bays} bays = {subtotal}",
        }

    def compute_bay_split(
        self, width_ft: int, length_ft: int, max_bay_w: int, max_bay_l: int
    ) -> dict:
        """Deterministic bay split using ceiling division."""
        width_bays = math.ceil(width_ft / max_bay_w)
        length_bays = math.ceil(length_ft / max_bay_l)
        total_bays = width_bays * length_bays
        bay_width = round(width_ft / width_bays, 2)
        bay_length = round(length_ft / length_bays, 2)

        return {
            "width_bays": width_bays,
            "length_bays": length_bays,
            "total_bays": total_bays,
            "bay_width_ft": bay_width,
            "bay_length_ft": bay_length,
            "math_trace": (
                f"width: {width_ft}/{max_bay_w} = {width_bays} bays, "
                f"length: {length_ft}/{max_bay_l} = {length_bays} bays, "
                f"total: {width_bays}x{length_bays} = {total_bays}"
            ),
        }

    def compute_surcharge(
        self, item: dict, total_bays: int, bay_width_ft: float,
        bay_length_ft: float, base_system_total: float,
    ) -> dict:
        """Apply pricing unit formula to a surcharge item."""
        unit = item.get("pricing_unit", "each")
        value = item.get("value") or item.get("unit_price", 0)
        qty = 0
        subtotal = 0.0

        if unit == "per_bay":
            qty = total_bays
            subtotal = value * qty
        elif unit == "percent":
            qty = 1
            subtotal = round(base_system_total * value / 100, 2)
        elif unit == "per_sq_ft":
            sq_ft = bay_width_ft * bay_length_ft * total_bays
            qty = sq_ft
            subtotal = round(value * sq_ft, 2)
        elif unit == "per_linear_ft":
            perimeter = 2 * (bay_width_ft + bay_length_ft) * total_bays
            qty = perimeter
            subtotal = round(value * perimeter, 2)
        elif unit in ("each", "unit"):
            qty = 1
            subtotal = value

        return {
            "sku": item.get("sku", ""),
            "display_name": item.get("display_name", ""),
            "pricing_unit": unit,
            "unit_price": value,
            "qty": qty,
            "subtotal": subtotal,
            "math_trace": f"{value} x {qty} ({unit}) = {subtotal}",
        }
```

### 3.4 Compliance Agent

Runs on EVERY gate output. Validates numbers, checks for hallucinations, enforces product rules.

```python
COMPLIANCE_MODEL = "claude-haiku-4"
COMPLIANCE_TEMP = 0.0

class ComplianceResult(BaseModel):
    """Compliance agent's validation result."""
    passed: bool
    checks_run: list[str]
    violations: list[str]
    warnings: list[str]
    hallucination_score: float = Field(
        description="0.0 = no hallucination detected, 1.0 = definite hallucination"
    )

COMPLIANCE_PROMPT = """\
You are the Compliance agent. Validate this gate output.

Gate: {gate_number} — {gate_name}

## Checks to perform:
1. NUMBER INTEGRITY: Every price in the output must exist in the pricing
   context. Flag any number that doesn't trace to the source data.
2. PRODUCT RULES: Verify product restrictions (e.g., R-Breeze max width
   23ft, heaters require beams, etc.)
3. MATH VERIFICATION: Check that qty x unit_price = subtotal for every
   line item.
4. HALLUCINATION SCAN: Flag any SKU, price, or product name that doesn't
   appear in the provided context data.
5. COMPARISON MODE: If comparison_mode is true, verify both keep AND swap
   options are fully computed.

Pricing context (source of truth):
{pricing_context}

Gate output to validate:
{gate_output}
"""

async def run_compliance(
    gate_number: int,
    gate_name: str,
    pricing_context: dict,
    gate_output: dict,
) -> ComplianceResult:
    client = AsyncOpenAI()
    response = await client.responses.parse(
        model=COMPLIANCE_MODEL,
        temperature=COMPLIANCE_TEMP,
        instructions=COMPLIANCE_PROMPT.format(
            gate_number=gate_number,
            gate_name=gate_name,
            pricing_context=json.dumps(pricing_context),
            gate_output=json.dumps(gate_output),
        ),
        input="Validate this gate output.",
        text_format=ComplianceResult,
    )
    return response.output_parsed
```

---

## 4. The Full Processing Loop

Here's how all four agents work together on a single user message:

```python
import asyncio
import json
import logging

logger = logging.getLogger("ascend")


class ASCENDOrchestrator:
    """A.S.C.E.N.D. multi-agent orchestrator."""

    def __init__(self):
        self.pricing = PricingAgent()

    async def handle_message(
        self, conversation_id: str, user_message: str
    ) -> dict:
        session = await load_session(conversation_id)
        gate_number = session.current_gate
        gate_def = GATE_DEFS[gate_number]

        # ── Step 1: Supervisor decides what to do ──
        decision = supervisor_decide(
            user_message=user_message,
            gate_number=gate_number,
            gate_name=gate_def["name"],
            session_data=session.product_config,
            gate_instructions=gate_def["instructions"],
        )
        logger.info(f"Supervisor: {decision.action} | {decision.reasoning}")

        # ── Step 2: Handle revision routing ──
        if decision.action == "route_revision":
            session.current_gate = decision.target_gate
            await save_session(conversation_id, session)
            return await self.handle_message(conversation_id, user_message)

        # ── Step 3: Run Pricing Agent if needed ──
        pricing_result = None
        if decision.needs_pricing:
            pricing_result = self._run_pricing(gate_number, session)

        # ── Step 4: Run Compliance + Conversation in parallel ──
        compliance_task = None
        if pricing_result:
            compliance_task = run_compliance(
                gate_number=gate_number,
                gate_name=gate_def["name"],
                pricing_context=self._get_pricing_context(gate_number, session),
                gate_output=pricing_result,
            )

        conversation_task = conversation_respond(
            gate_name=gate_def["name"],
            pricing_data=pricing_result or {},
            communication_goal=self._get_comm_goal(decision, gate_number),
            conversation_history=await get_history(conversation_id),
        )

        # Await both in parallel
        if compliance_task:
            conversation_result, compliance_result = await asyncio.gather(
                conversation_task, compliance_task
            )
        else:
            conversation_result = await conversation_task
            compliance_result = None

        # ── Step 5: Compliance gate ──
        if compliance_result and not compliance_result.passed:
            logger.warning(f"Compliance FAILED: {compliance_result.violations}")
            return {
                "status": "error",
                "message": "We found an issue with this quote. Recalculating...",
                "violations": compliance_result.violations,
            }

        # ── Step 6: Collect data + advance if ok ──
        if not conversation_result.needs_input and pricing_result:
            collect_data(session, gate_number, pricing_result)
            next_gate = await advance_gate(conversation_id, session)

            # Chain-advance through auto-resolvable gates
            if next_gate:
                await self._chain_advance(conversation_id, session)

        await save_session(conversation_id, session)

        return {
            "status": "ok" if not conversation_result.needs_input else "needs_info",
            "message": conversation_result.message,
            "options": conversation_result.options,
            "gate": gate_number,
            "gate_name": gate_def["name"],
        }

    def _run_pricing(self, gate_number: int, session) -> dict:
        """Route to the correct pricing operation based on gate."""
        pc = session.product_config
        product_id = pc.get("product_id", "r_blade")

        if gate_number == 3:  # Bay Logic
            return self.pricing.compute_bay_split(
                width_ft=pc.get("width_ft_confirmed") or pc["width_ft_assumed"],
                length_ft=pc.get("length_ft_confirmed") or pc["length_ft_assumed"],
                max_bay_w=16, max_bay_l=23,
            )
        elif gate_number == 4:  # Base Pricing
            return self.pricing.compute_base_price(
                product_id=product_id,
                bay_width_ft=pc["bay_width_ft"],
                bay_length_ft=pc["bay_length_ft"],
                total_bays=pc["total_bays"],
            )
        # ... additional gates follow same pattern
        return {}

    async def _chain_advance(self, conversation_id, session):
        """Auto-advance through gates that don't need user input.

        Uses Pattern 1 (Prompt Chaining) — each gate's output feeds the next.
        Skips conditional gates via should_skip_gate() without API calls.
        """
        for _ in range(10):
            gate = session.current_gate
            if gate not in GATE_DEFS:
                break
            if should_skip_gate(gate, session):
                session.advance()
                continue

            pricing_result = self._run_pricing(gate, session)
            if not pricing_result:
                break  # Gate needs user input

            compliance = await run_compliance(
                gate, GATE_DEFS[gate]["name"],
                self._get_pricing_context(gate, session),
                pricing_result,
            )
            if not compliance.passed:
                break

            collect_data(session, gate, pricing_result)
            next_gate = session.advance()
            if next_gate is None:
                break

        await save_session(conversation_id, session)
```

---

## 5. API Endpoints

### 5.1 REST API Structure

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Breslow QuoteApp A.S.C.E.N.D. API")

class MessageRequest(BaseModel):
    conversation_id: str
    message: str

class MessageResponse(BaseModel):
    status: str           # "ok" | "needs_info" | "error"
    message: str          # user-facing text from Conversation agent
    options: list | None  # selectable options with prices
    gate: int             # current gate number
    gate_name: str        # human-readable gate name
    metadata: dict | None # debug info (gate transitions, compliance, etc.)

orchestrator = ASCENDOrchestrator()

@app.post("/api/v3/message", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    result = await orchestrator.handle_message(req.conversation_id, req.message)
    return MessageResponse(**result)

@app.post("/api/v3/message/stream")
async def send_message_stream(req: MessageRequest):
    """SSE streaming endpoint for real-time responses."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        async for chunk in orchestrator.handle_message_stream(
            req.conversation_id, req.message
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/api/v3/session/{conversation_id}")
async def get_session(conversation_id: str):
    """Debug endpoint: view current session state."""
    session = await load_session(conversation_id)
    return {
        "current_gate": session.current_gate,
        "product_config": session.product_config,
    }
```

### 5.2 Streaming Response Format

```json
{"type": "chunk", "delta": "Great choice! "}
{"type": "chunk", "delta": "The R-Blade in "}
{"type": "chunk", "delta": "14x20 comes to..."}
{"type": "done", "message": {"status": "ok", "gate": 4, ...}}
```

---

## 6. Gate Sequence and Agent Routing

Each gate maps to specific agent involvement:

| Gate | Name | Supervisor | Pricing | Conversation | Compliance |
|------|------|-----------|---------|-------------|------------|
| 1 | Product Selection | Route | — | Ask user | — |
| 2 | Dimensions & State | Route | — | Ask user | — |
| 19 | Orientation | Route (conditional) | Bay calc | Present options | Validate |
| 3 | Bay Logic | Auto-advance | Bay split | — | Validate math |
| 20 | Threshold Advisory | Route (conditional) | — | Advise user | — |
| 21 | Dimension Router | Auto-advance | — | — | — |
| 4 | Base Pricing | Auto-advance | SKU lookup | — | Validate prices |
| 22 | Structural Add-Ons | Auto-advance | Structural calc | — | Validate |
| 5 | Color / Finish | Route | Surcharge calc | Present options | Validate |
| 6 | Lighting & Fans | Route | Line items | Present options | Validate |
| 7 | Heaters | Route | Line items | Present options | Validate |
| 8 | Shades & Privacy | Route | Line items | Present options | Validate |
| 9 | Trim | Route | Line items | Present options | Validate |
| 10 | Electrical | Route | Line items | Present options | Validate |
| 11 | Installation | Route | — | Ask user | — |
| 12 | Design/Eng/Permits | Route | — | Ask user | — |
| 13 | Quote Summary | Auto-advance | Aggregate | — | Full audit |
| 14 | Internal Audit | Auto-advance | — | — | Deep audit |
| 15 | Final Payload | Auto-advance | — | — | Final check |
| 16 | Detailed Breakdown | Auto-advance | — | Present | — |
| 17 | Revisions Router | Route | — | Ask user | — |
| 18 | Post-Quote Handoff | Route | — | Confirm | Final check |

**"Auto-advance"** = gate resolves without user input, chain-advances to next gate.
**"Route"** = requires user interaction, Conversation agent generates question.
**"Route (conditional)"** = only runs if a flag is set (e.g., orientation_review_required).

---

## 7. Migration Path from V2 to V3

The current `orchestrator_v2.py` uses a single LLM for everything. Here's how to incrementally migrate to the multi-agent architecture:

### Phase 1: Extract Pricing Agent (Week 1)
- Move all math from LLM prompts into `PricingAgent` class
- Gate prompts stop saying "calculate" and start saying "present these results"
- Compliance agent not yet active — validation is still in gate prompts

### Phase 2: Split Conversation Agent (Week 2)
- Extract user-facing text generation into `ConversationAgent`
- Supervisor logic remains in `OrchestratorV2` for now
- Chain-advance still uses `_CHAIN_MODEL` (gpt-4.1-mini)

### Phase 3: Add Compliance Agent (Week 3)
- Add `ComplianceAgent` running on every gate output
- Parallel execution with Conversation agent
- Log all violations for audit trail

### Phase 4: Full Supervisor (Week 4)
- Replace `OrchestratorV2.handle_message` with `SupervisorAgent`
- Supervisor delegates to all three agents
- Full A.S.C.E.N.D. architecture operational

---

## 8. Testing Strategy

### Unit Tests — Pricing Agent
```python
def test_bay_split_exact():
    agent = PricingAgent()
    result = agent.compute_bay_split(28, 20, max_bay_w=16, max_bay_l=23)
    assert result["width_bays"] == 2
    assert result["length_bays"] == 1
    assert result["total_bays"] == 2
    assert result["bay_width_ft"] == 14

def test_no_price_interpolation():
    agent = PricingAgent()
    result = agent.compute_base_price("r_blade", 15, 21, 1)
    # 15x21 must exist in the table or return error
    if "error" in result:
        assert "No price found" in result["error"]
```

### Integration Tests — Compliance
```python
async def test_compliance_catches_hallucinated_price():
    result = await run_compliance(
        gate_number=4,
        gate_name="Base Pricing",
        pricing_context={"pricing_table": [{"width_ft": 14, "length_ft": 20, "unit_price": 10000}]},
        gate_output={"unit_price": 9999, "subtotal": 19998},  # wrong price!
    )
    assert not result.passed
    assert result.hallucination_score > 0.5
```

### End-to-End Tests — Full Quote Flow
```python
async def test_full_quote_happy_path():
    orch = ASCENDOrchestrator()
    cid = "test-123"

    r1 = await orch.handle_message(cid, "I want an R-Blade")
    assert r1["gate"] == 2  # advanced to dimensions

    r2 = await orch.handle_message(cid, "28 by 20 feet, NJ")
    assert r2["gate"] >= 3  # advanced past dimensions

    # ... continue through all gates
```

---

## 9. File Structure

```
src/app/
├── agents/
│   ├── __init__.py
│   ├── supervisor.py        # SupervisorAgent (Claude Opus 4)
│   ├── conversation.py      # ConversationAgent (Claude Sonnet 4)
│   ├── pricing.py           # PricingAgent (deterministic Python)
│   └── compliance.py        # ComplianceAgent (Claude Haiku 4)
├── services/
│   ├── orchestrator_v3.py   # ASCENDOrchestrator (ties agents together)
│   ├── orchestrator_v2.py   # Legacy single-LLM (still active)
│   ├── pricing_loader.py    # Supabase RPC data layer
│   └── conversation_service.py
├── gates/
│   ├── registry.py          # Gate definitions + variable templates
│   ├── session_state.py     # Session persistence
│   └── models.py            # GateConfig, GateStatus
├── routes/
│   ├── v2.py                # /api/v2/* endpoints (legacy)
│   └── v3.py                # /api/v3/* endpoints (A.S.C.E.N.D.)
└── config.py
```

---

## 10. Environment Variables

```env
# Models
SUPERVISOR_MODEL=claude-opus-4
CONVERSATION_MODEL=claude-sonnet-4
COMPLIANCE_MODEL=claude-haiku-4
CHAIN_MODEL=gpt-4.1-mini

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Supabase (pricing data)
SUPABASE_URL=https://vwxmhrlkylrkcqoxvhij.supabase.co
SUPABASE_KEY=eyJ...

# Feature flags
COMPLIANCE_ENABLED=true
PARALLEL_VALIDATION=true
AUDIT_LOGGING=true
```
