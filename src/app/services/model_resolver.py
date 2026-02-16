"""Model resolver — walks the 5-level priority chain to determine which LLM
model (and temperature) to use for a given gate + agent combination.

Resolution order (most specific wins):
  1. gate_agent_map.model_override_id    (this gate + this agent)
  2. prompts.model_override_id           (active prompt for this gate)
  3. gates.default_model_id              (this gate, any agent)
  4. agents.default_model_id             (this agent, any gate)
  5. llm_models defaults                 (fallback: gpt-4.1)
"""

from __future__ import annotations

from typing import Any

from . import supabase_service as supa

# Default fallback model if nothing is configured
_FALLBACK_MODEL_ID = "gpt-4.1"

# In-memory cache: (gate_number, agent_slug) -> resolved model dict
_resolution_cache: dict[tuple[int, str], dict[str, Any]] = {}


def clear_cache() -> None:
    """Clear the resolution cache (call after config changes)."""
    _resolution_cache.clear()


def resolve_model(gate_number: int, agent_slug: str) -> dict[str, Any]:
    """Resolve the LLM model for a gate + agent, following the 5-level chain.

    Returns:
        dict with keys: model_id, provider, display_name, temperature, etc.
        Includes a 'temperature' key merged from the best available source.
    """
    cache_key = (gate_number, agent_slug)
    if cache_key in _resolution_cache:
        return _resolution_cache[cache_key]

    resolved_model_id: str | None = None
    resolved_temperature: float | None = None

    # Level 1: gate_agent_map override (most specific)
    mappings = supa.get_agents_for_gate(gate_number)
    for mapping in mappings:
        if mapping["agent_slug"] == agent_slug:
            if mapping.get("model_override_id"):
                resolved_model_id = mapping["model_override_id"]
            if mapping.get("temperature_override") is not None:
                resolved_temperature = mapping["temperature_override"]
            break

    # Level 2: prompt override
    if not resolved_model_id:
        prompt = supa.get_active_prompt(gate_number=gate_number, prompt_type="gate")
        if prompt and prompt.get("model_override_id"):
            resolved_model_id = prompt["model_override_id"]
        if resolved_temperature is None and prompt and prompt.get("temperature_override") is not None:
            resolved_temperature = prompt["temperature_override"]

    # Level 3: gate default
    if not resolved_model_id:
        gate = supa.get_gate(gate_number)
        if gate and gate.get("default_model_id"):
            resolved_model_id = gate["default_model_id"]

    # Level 4: agent default
    if not resolved_model_id:
        agent = supa.get_agent(agent_slug)
        if agent and agent.get("default_model_id"):
            resolved_model_id = agent["default_model_id"]
        if resolved_temperature is None and agent and agent.get("temperature") is not None:
            resolved_temperature = agent["temperature"]

    # Level 5: global fallback
    if not resolved_model_id:
        resolved_model_id = _FALLBACK_MODEL_ID

    # Fetch full model details
    model = supa.get_llm_model(resolved_model_id)
    if not model:
        # Hard fallback if model not in registry
        model = {
            "model_id": resolved_model_id,
            "provider": "openai",
            "display_name": resolved_model_id,
            "category": "unknown",
            "default_temperature": 0.0,
        }

    # Merge temperature (resolved override > model default)
    if resolved_temperature is None:
        resolved_temperature = model.get("default_temperature", 0.0)

    result = {**model, "temperature": resolved_temperature}
    _resolution_cache[cache_key] = result
    return result


def resolve_chain_model(gate_number: int) -> dict[str, Any]:
    """Resolve the fast model for chain-advance calls.

    Checks gates.chain_model_id first, falls back to gpt-4.1-mini.
    """
    gate = supa.get_gate(gate_number)
    chain_model_id = None
    if gate:
        chain_model_id = gate.get("chain_model_id")

    if not chain_model_id:
        chain_model_id = "gpt-4.1-mini"

    model = supa.get_llm_model(chain_model_id)
    if not model:
        model = {
            "model_id": chain_model_id,
            "provider": "openai",
            "display_name": "GPT-4.1 Mini",
            "default_temperature": 0.0,
        }
    return {**model, "temperature": 0.0}
