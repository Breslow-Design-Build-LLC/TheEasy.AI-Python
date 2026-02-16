# A.S.C.E.N.D. Database Schema Design

## Supabase — Orchestration & Prompt Management Layer

**Project:** vwxmhrlkylrkcqoxvhij (Breslow AI Agent)
**Status:** DESIGN REVIEW — not yet created

---

## Existing Tables (already in Supabase — NO CHANGES)

| Table | Purpose | Rows |
|-------|---------|------|
| `product` | 24 product definitions (R-Blade Prices, Heaters, etc.) | 24 |
| `variant` | 1,376 SKU variants per product | 1,376 |
| `variant_values` | Attribute values per variant (width, color, etc.) | 7,322 |
| `value_column_name` | Column metadata/formatters | 52 |
| `project` | Customer projects (GHL + QuickBooks linked) | 151 |
| `n8n_chat_histories` | Legacy n8n chat logs | 886 |
| `documents` | RAG document embeddings | 0 |

---

## New Tables — 11 Tables in 3 Groups

### Group A: Agent & Gate Configuration (5 tables)

These define WHAT the system is — the models, agents, gates, prompts, and their relationships. Changed by developers, not by the quoting flow.

### Group B: Runtime / Session (3 tables)

These track ACTIVE quoting sessions — conversations, messages, and session state. Created and updated during every quote.

### Group C: Audit & Observability (3 tables)

These log EVERYTHING that happens — every agent decision, compliance check, and pricing calculation. Written once, never modified. (Law #2: The Agent is Accountable for Every Decision.)

---

## GROUP A: Agent & Gate Configuration

### Table 1: `llm_models`

Registry of all available LLM models across providers. This is the single source of truth for model names, costs, and capabilities. When you want to swap GPT-4.1 for GPT-5.2 or Claude Opus for Sonnet, you update one row here — every agent and gate that references it picks up the change automatically.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `serial` | NO | auto | Primary key |
| `model_id` | `varchar(100)` | NO | — | API model string: `gpt-4.1`, `gpt-5.2`, `claude-opus-4`, `claude-sonnet-4`, `claude-haiku-4`, `gpt-4.1-mini` |
| `provider` | `varchar(30)` | NO | — | `openai`, `anthropic`, `google`, `local` |
| `display_name` | `varchar(100)` | NO | — | Human-readable: "GPT-4.1", "Claude Opus 4", "GPT-5.2" |
| `category` | `varchar(30)` | NO | — | `reasoning`, `conversation`, `fast`, `vision`, `embedding` |
| `context_window` | `integer` | YES | — | Max tokens (input + output): 128000, 200000, etc. |
| `max_output_tokens` | `integer` | YES | — | Max output tokens: 4096, 16384, etc. |
| `supports_json_mode` | `boolean` | NO | true | Whether the model supports structured JSON output |
| `supports_streaming` | `boolean` | NO | true | Whether the model supports streaming responses |
| `supports_vision` | `boolean` | NO | false | Whether the model can process images |
| `cost_per_1k_input` | `numeric(10,6)` | YES | — | Cost per 1K input tokens in USD |
| `cost_per_1k_output` | `numeric(10,6)` | YES | — | Cost per 1K output tokens in USD |
| `default_temperature` | `float` | YES | 0.0 | Recommended temperature for this model |
| `is_active` | `boolean` | NO | true | Feature flag to retire models without deleting |
| `notes` | `text` | YES | — | "Best for pricing gates", "Use for fast chain-advance", etc. |
| `created_at` | `timestamptz` | NO | now() | — |
| `updated_at` | `timestamptz` | NO | now() | — |

**Unique constraint:** `model_id`

**Seed data:**

| model_id | provider | display_name | category | context_window | supports_json_mode | cost_input | cost_output |
|----------|----------|-------------|----------|----------------|-------------------|------------|-------------|
| `gpt-4.1` | openai | GPT-4.1 | reasoning | 1,047,576 | true | 0.002000 | 0.008000 |
| `gpt-4.1-mini` | openai | GPT-4.1 Mini | fast | 1,047,576 | true | 0.000400 | 0.001600 |
| `gpt-4.1-nano` | openai | GPT-4.1 Nano | fast | 1,047,576 | true | 0.000100 | 0.000400 |
| `gpt-5.2` | openai | GPT-5.2 | reasoning | 1,047,576 | true | — | — |
| `o4-mini` | openai | o4-mini | reasoning | 200,000 | true | 0.001100 | 0.004400 |
| `claude-opus-4` | anthropic | Claude Opus 4 | reasoning | 200,000 | true | 0.015000 | 0.075000 |
| `claude-sonnet-4` | anthropic | Claude Sonnet 4 | conversation | 200,000 | true | 0.003000 | 0.015000 |
| `claude-haiku-4` | anthropic | Claude Haiku 4 | fast | 200,000 | true | 0.000800 | 0.004000 |

**Why this table matters:** Instead of hardcoding model strings across your codebase, every agent, gate, and prompt references this table. To upgrade from GPT-4.1 to GPT-5.2, change one row. To A/B test models, add a new row and point a gate at it.

---

### Table 2: `agents`

Defines the 4 specialized agents in the A.S.C.E.N.D. architecture. Each agent has a default model from `llm_models`, but individual gates can override it.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `serial` | NO | auto | Primary key |
| `slug` | `varchar(50)` | NO | — | Unique identifier: `supervisor`, `conversation`, `pricing`, `compliance` |
| `name` | `varchar(100)` | NO | — | Display name: "Supervisor Agent" |
| `default_model_id` | `varchar(100)` | YES | — | FK → llm_models.model_id (null for Pricing — not an LLM) |
| `temperature` | `float` | YES | 0.0 | Default temperature (can be overridden per gate) |
| `description` | `text` | YES | — | What this agent does |
| `can_access_prices` | `boolean` | NO | false | Whether agent can read pricing data |
| `can_generate_text` | `boolean` | NO | false | Whether agent produces user-facing text |
| `is_llm` | `boolean` | NO | true | False for Pricing agent (deterministic Python) |
| `is_active` | `boolean` | NO | true | Feature flag to disable an agent |
| `config_json` | `jsonb` | YES | '{}' | Extra config (max_tokens, top_p, etc.) |
| `created_at` | `timestamptz` | NO | now() | — |
| `updated_at` | `timestamptz` | NO | now() | — |

**Unique constraint:** `slug`
**Foreign key:** `default_model_id` → `llm_models.model_id`

**Seed data (4 rows):**

| slug | default_model_id | temp | can_access_prices | can_generate_text | is_llm |
|------|-----------------|------|-------------------|-------------------|--------|
| `supervisor` | `gpt-4.1` | 0.0 | read-only | false | true |
| `conversation` | `gpt-4.1` | 0.3 | false | true | true |
| `pricing` | NULL | NULL | true | false | false |
| `compliance` | `gpt-4.1-mini` | 0.0 | read-only | false | true |

---

### Table 3: `gates`

Defines the 22 gates in the quoting flow — their sequence, conditions, and which agents are involved. Each gate can specify its own model (overriding the agent's default), plus a separate fast model for chain-advance calls.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `serial` | NO | auto | Primary key |
| `gate_number` | `integer` | NO | — | Internal gate number (1–22) |
| `step_code` | `varchar(10)` | NO | — | Display code: S01, S02, S02b, S03, etc. |
| `name` | `varchar(100)` | NO | — | "Product Selection", "Bay Logic & Pricing", etc. |
| `sequence_order` | `integer` | NO | — | Position in the execution sequence (1–22) |
| `is_conditional` | `boolean` | NO | false | True for gates 19, 20, 21, 22 |
| `skip_condition` | `text` | YES | — | Python expression or description of when to skip |
| `auto_advance` | `boolean` | NO | false | True if gate can resolve without user input |
| `needs_user_input` | `boolean` | NO | true | Whether this gate typically asks the user a question |
| `needs_pricing` | `boolean` | NO | false | Whether the Pricing agent runs for this gate |
| `needs_compliance` | `boolean` | NO | false | Whether the Compliance agent validates this gate |
| `default_model_id` | `varchar(100)` | YES | — | FK → llm_models.model_id — override model for this gate (null = use agent's default) |
| `chain_model_id` | `varchar(100)` | YES | — | FK → llm_models.model_id — fast model for chain-advance calls (null = use `gpt-4.1-mini`) |
| `context_variable` | `varchar(100)` | NO | — | Variable name injected into the prompt: `bay_logic_context` |
| `context_source_key` | `varchar(100)` | NO | — | Where the variable value comes from in session state |
| `depends_on_gates` | `integer[]` | YES | — | Array of gate numbers whose output this gate needs |
| `description` | `text` | YES | — | What this gate does |
| `is_active` | `boolean` | NO | true | Feature flag |
| `created_at` | `timestamptz` | NO | now() | — |
| `updated_at` | `timestamptz` | NO | now() | — |

**Unique constraints:** `gate_number`, `step_code`, `sequence_order`
**Foreign keys:** `default_model_id` → `llm_models.model_id`, `chain_model_id` → `llm_models.model_id`

**All 22 rows:**

| gate_number | step_code | name | seq | conditional | auto_advance | needs_pricing | needs_compliance | context_variable |
|-------------|-----------|------|-----|-------------|-------------|---------------|-----------------|-----------------|
| 1 | S01 | Product Selection | 1 | false | false | false | false | product_options |
| 2 | S02 | Dimensions & State | 2 | false | false | false | false | dimension_context |
| 19 | S02b | Orientation Confirmation | 3 | true | false | true | true | orientation_context |
| 3 | S03 | Bay Logic & Pricing | 4 | false | true | true | true | bay_logic_context |
| 20 | S03b | Threshold Advisory | 5 | true | false | false | false | threshold_advisory_context |
| 21 | S03c | Dimension Router | 6 | true | true | false | false | dimension_router_context |
| 4 | S04 | Base Pricing | 7 | false | true | true | true | base_pricing_context |
| 22 | S04b | Structural Add-Ons | 8 | true | true | true | true | structural_addons_context |
| 5 | S05 | Color / Finish | 9 | false | false | true | true | finish_surcharge_context |
| 6 | S06 | Lighting & Fans | 10 | false | false | true | true | lighting_fans_context |
| 7 | S07 | Heaters | 11 | false | false | true | true | heater_context |
| 8 | S08 | Shades & Privacy Walls | 12 | false | false | true | true | shades_privacy_context |
| 9 | S09 | Trim & Architectural | 13 | false | false | true | true | trim_context |
| 10 | S10 | Electrical Scope | 14 | false | false | true | true | electrical_scope_context |
| 11 | S11 | Installation Scope | 15 | false | false | false | false | installation_context |
| 12 | S12 | Design / Engineering / Permits | 16 | false | false | false | false | services_context |
| 13 | S13 | Quote Summary | 17 | false | true | true | true | quote_summary_context |
| 14 | S14 | Internal Audit | 18 | false | true | false | true | audit_context |
| 15 | S15 | Final Output Payload | 19 | false | true | false | true | final_payload_context |
| 16 | S16 | Detailed Breakdown | 20 | false | true | false | false | breakdown_context |
| 17 | S17 | Revisions Router | 21 | false | false | false | false | revision_context |
| 18 | S18 | Post-Quote Handoff | 22 | false | false | false | true | handoff_context |

---

### Table 4: `prompts`

Versioned prompt storage. Each gate has a developer message (instructions) that can be updated independently without code deploys. The master prompt (shared across all gates) is also stored here. Each prompt version can optionally pin to a specific model — useful for A/B testing or when a prompt was tuned for a particular model.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key |
| `prompt_type` | `varchar(20)` | NO | — | `master`, `gate`, `agent` |
| `gate_number` | `integer` | YES | — | Which gate this prompt belongs to (null for master/agent prompts) |
| `agent_slug` | `varchar(50)` | YES | — | Which agent uses this prompt (null for gate prompts) |
| `version` | `integer` | NO | 1 | Version number (increments on each edit) |
| `is_active` | `boolean` | NO | true | Only one active version per (prompt_type, gate_number, agent_slug) |
| `name` | `varchar(200)` | NO | — | Human-readable label: "Gate 5 — Color / Finish v3" |
| `developer_message` | `text` | NO | — | The full prompt text with `{variable_name}` placeholders |
| `variables_schema` | `jsonb` | YES | — | JSON schema describing expected variables and their shapes |
| `model_override_id` | `varchar(100)` | YES | — | FK → llm_models.model_id — pin this prompt version to a specific model |
| `temperature_override` | `float` | YES | — | Override temperature |
| `notes` | `text` | YES | — | Change notes: "Fixed comparison mode handling" |
| `created_by` | `varchar(100)` | YES | — | Who created this version |
| `created_at` | `timestamptz` | NO | now() | — |

**Foreign key:** `model_override_id` → `llm_models.model_id`

**Unique constraint:** Only one `is_active = true` per combination of `(prompt_type, gate_number, agent_slug)`

**Prompt types:**

| prompt_type | gate_number | agent_slug | Example |
|-------------|-------------|------------|---------|
| `master` | NULL | NULL | The `_MASTER_PROMPT` — shared system instructions |
| `gate` | 5 | NULL | Gate 5 developer message (color/finish) |
| `agent` | NULL | `supervisor` | Supervisor's routing/reasoning prompt |
| `agent` | NULL | `conversation` | Conversation agent's UX prompt |
| `agent` | NULL | `compliance` | Compliance agent's validation prompt |

---

### Table 5: `gate_agent_map`

Junction table: which agents are involved in each gate, what role they play, and optionally which model to use for this specific gate+agent combination. This is the finest-grained model override — it lets you run the Conversation agent with GPT-4.1 on most gates but switch to GPT-5.2 specifically for Gate 13 (Quote Summary) where quality matters most.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `serial` | NO | auto | Primary key |
| `gate_number` | `integer` | NO | — | FK → gates.gate_number |
| `agent_slug` | `varchar(50)` | NO | — | FK → agents.slug |
| `role` | `varchar(30)` | NO | — | `primary`, `validator`, `formatter`, `observer` |
| `execution_order` | `integer` | NO | 1 | Order within this gate (1 = first) |
| `is_parallel` | `boolean` | NO | false | Can run in parallel with other agents at same order |
| `is_required` | `boolean` | NO | true | If false, gate can proceed without this agent |
| `model_override_id` | `varchar(100)` | YES | — | FK → llm_models.model_id — use this model instead of agent's default for this gate |
| `temperature_override` | `float` | YES | — | Override temperature for this gate+agent |

**Unique constraint:** `(gate_number, agent_slug)`
**Foreign key:** `model_override_id` → `llm_models.model_id`

**Model Resolution Order (most specific wins):**

```
1. gate_agent_map.model_override_id    (this gate + this agent)
2. prompts.model_override_id           (this prompt version)
3. gates.default_model_id              (this gate, any agent)
4. agents.default_model_id             (this agent, any gate)
5. llm_models defaults                 (fallback)
```

**Example rows for Gate 5 (Color / Finish):**

| gate_number | agent_slug | role | execution_order | is_parallel | model_override_id |
|-------------|------------|------|-----------------|-------------|-------------------|
| 5 | supervisor | primary | 1 | false | NULL (uses agent default: gpt-4.1) |
| 5 | pricing | primary | 2 | false | NULL (not an LLM) |
| 5 | conversation | formatter | 3 | true | NULL (uses agent default: gpt-4.1) |
| 5 | compliance | validator | 3 | true | NULL (uses agent default: gpt-4.1-mini) |

**Example: Override for high-value gate:**

| gate_number | agent_slug | role | execution_order | is_parallel | model_override_id |
|-------------|------------|------|-----------------|-------------|-------------------|
| 13 | conversation | formatter | 3 | true | `gpt-5.2` |
| 14 | compliance | validator | 1 | false | `claude-opus-4` |

This means Gate 13's conversation uses GPT-5.2 for best quality, and Gate 14's compliance audit uses Claude Opus 4 for deepest reasoning — while all other gates use the cheaper defaults.

---

## GROUP B: Runtime / Session

### Table 6: `conversations`

Top-level quoting session. One per customer quote attempt.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key (= conversation_id in the API) |
| `project_id` | `integer` | YES | — | FK → project.id (linked CRM project) |
| `customer_name` | `varchar(200)` | YES | — | Customer name if known |
| `customer_email` | `varchar(200)` | YES | — | Customer email |
| `opportunity_id` | `varchar(100)` | YES | — | GoHighLevel opportunity ID |
| `current_gate` | `integer` | NO | 1 | Current gate number in the flow |
| `status` | `varchar(20)` | NO | 'active' | `active`, `completed`, `abandoned`, `revision` |
| `product_id` | `varchar(50)` | YES | — | Selected product: r_blade, r_shade, etc. |
| `product_config` | `jsonb` | NO | '{}' | Full session state (all collected data) |
| `comparison_mode` | `boolean` | NO | false | Whether running dual-orientation pricing |
| `total_gates_completed` | `integer` | NO | 0 | Count of gates with status "ok" |
| `total_api_calls` | `integer` | NO | 0 | Total LLM API calls made |
| `total_tokens_used` | `integer` | NO | 0 | Running token count |
| `started_at` | `timestamptz` | NO | now() | — |
| `completed_at` | `timestamptz` | YES | — | When quote was finalized |
| `updated_at` | `timestamptz` | NO | now() | — |

**Indexes:** `status`, `project_id`, `started_at`

---

### Table 7: `conversation_messages`

Every message in a conversation — user inputs and assistant responses.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key |
| `conversation_id` | `uuid` | NO | — | FK → conversations.id |
| `role` | `varchar(20)` | NO | — | `user`, `assistant`, `system` |
| `content` | `text` | NO | — | Raw message text |
| `gate_number` | `integer` | YES | — | Which gate was active when this message was sent |
| `response_json` | `jsonb` | YES | — | Parsed JSON response (for assistant messages) |
| `metadata_json` | `jsonb` | YES | — | Routing info, gate transitions, timing |
| `agent_slug` | `varchar(50)` | YES | — | Which agent generated this response |
| `model_used` | `varchar(50)` | YES | — | Actual model used for this call |
| `input_tokens` | `integer` | YES | — | Token count for input |
| `output_tokens` | `integer` | YES | — | Token count for output |
| `latency_ms` | `integer` | YES | — | API call duration in milliseconds |
| `created_at` | `timestamptz` | NO | now() | — |

**Indexes:** `conversation_id` + `created_at` (composite), `gate_number`

---

### Table 8: `gate_results`

Stores the final resolved output of each gate for a conversation. One row per gate per conversation. This is the "source of truth" for what each gate decided.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key |
| `conversation_id` | `uuid` | NO | — | FK → conversations.id |
| `gate_number` | `integer` | NO | — | Which gate |
| `status` | `varchar(20)` | NO | — | `ok`, `skipped`, `needs_info`, `error` |
| `result_json` | `jsonb` | NO | '{}' | Full gate output (the parsed JSON response) |
| `pricing_data` | `jsonb` | YES | — | Pricing agent's output (if applicable) |
| `context_snapshot` | `jsonb` | YES | — | The context variable that was injected into the prompt |
| `was_auto_advanced` | `boolean` | NO | false | True if gate resolved without user interaction |
| `was_chain_advanced` | `boolean` | NO | false | True if resolved during chain-advance loop |
| `model_used` | `varchar(50)` | YES | — | Model that processed this gate |
| `attempt_count` | `integer` | NO | 1 | How many attempts (if compliance rejected first try) |
| `resolved_at` | `timestamptz` | NO | now() | — |

**Unique constraint:** `(conversation_id, gate_number)` — can be updated if gate is re-run during revision

**Indexes:** `conversation_id`, `gate_number`

---

## GROUP C: Audit & Observability

### Table 9: `agent_decisions`

Every decision the Supervisor makes — logged with full reasoning. Immutable audit trail.

**(Law #2: The Agent is Accountable for Every Decision)**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key |
| `conversation_id` | `uuid` | NO | — | FK → conversations.id |
| `gate_number` | `integer` | NO | — | Current gate when decision was made |
| `agent_slug` | `varchar(50)` | NO | — | Which agent made this decision (usually `supervisor`) |
| `action` | `varchar(30)` | NO | — | `process_gate`, `chain_advance`, `route_revision`, `skip_gate`, `escalate`, `reject` |
| `target_gate` | `integer` | YES | — | For revisions: which gate to jump to |
| `reasoning` | `text` | NO | — | Full reasoning text (never shown to user) |
| `confidence` | `float` | YES | — | Decision confidence 0.0–1.0 |
| `input_summary` | `text` | YES | — | Summary of what triggered this decision |
| `session_snapshot` | `jsonb` | YES | — | Snapshot of product_config at decision time |
| `created_at` | `timestamptz` | NO | now() | — |

**Indexes:** `conversation_id` + `created_at`, `action`

**This table is APPEND-ONLY — no updates or deletes.**

---

### Table 10: `compliance_checks`

Every validation the Compliance agent performs. One row per gate execution per conversation.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key |
| `conversation_id` | `uuid` | NO | — | FK → conversations.id |
| `gate_number` | `integer` | NO | — | Which gate was validated |
| `passed` | `boolean` | NO | — | Did it pass? |
| `checks_run` | `text[]` | NO | — | List of checks performed |
| `violations` | `text[]` | NO | '{}' | List of violations found |
| `warnings` | `text[]` | NO | '{}' | Non-blocking warnings |
| `hallucination_score` | `float` | YES | — | 0.0 = clean, 1.0 = definite hallucination |
| `gate_output_snapshot` | `jsonb` | YES | — | What was validated |
| `pricing_context_snapshot` | `jsonb` | YES | — | Source data used for validation |
| `model_used` | `varchar(50)` | YES | — | Model used for compliance check |
| `latency_ms` | `integer` | YES | — | How long the check took |
| `created_at` | `timestamptz` | NO | now() | — |

**Indexes:** `conversation_id`, `gate_number`, `passed`

**This table is APPEND-ONLY.**

---

### Table 11: `pricing_traces`

Every calculation the Pricing agent performs — with full math traces. Proves Law #1: Numbers are Never Generated.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NO | gen_random_uuid() | Primary key |
| `conversation_id` | `uuid` | NO | — | FK → conversations.id |
| `gate_number` | `integer` | NO | — | Which gate triggered this calculation |
| `operation` | `varchar(50)` | NO | — | `bay_split`, `base_price_lookup`, `surcharge_calc`, `line_item_total`, etc. |
| `input_data` | `jsonb` | NO | — | Exact inputs: `{product_id, bay_width_ft, total_bays}` |
| `output_data` | `jsonb` | NO | — | Exact outputs: `{sku, unit_price, qty, subtotal}` |
| `math_trace` | `text` | NO | — | Human-readable: "10000 × 2 bays = 20000" |
| `source_product_id` | `integer` | YES | — | FK → product.id (which Supabase product table was queried) |
| `source_variant_id` | `integer` | YES | — | FK → variant.id (which specific SKU was matched) |
| `created_at` | `timestamptz` | NO | now() | — |

**Indexes:** `conversation_id` + `gate_number`, `operation`

**This table is APPEND-ONLY.**

---

## Relationship Diagram

```
                    ┌──────────────────┐
                    │   llm_models     │
                    │ (model registry) │
                    └──┬───┬───┬───┬──┘
                       │   │   │   │  model_id (FK from all below)
          ┌────────────┘   │   │   └────────────────┐
          │                │   │                     │
   ┌──────▼───────┐       │   │        ┌────────────▼──────────┐
   │    agents     │       │   │        │      prompts          │
   │   (4 rows)    │       │   │        │  (versioned, typed)   │
   └──────┬────────┘       │   │        └───────────────────────┘
          │ slug           │   │
   ┌──────┼────────────┐   │   │
   │      │            │   │   │
┌──▼──────▼───┐        │   │   │
│gate_agent_  │        │   │   │
│map (junction)│        │   │   │
└──────┬──────┘        │   │   │
       │               │   │   │
 gate_number           │   │   │
       │               │   │   │
┌──────▼──────────┐    │   │   │
│     gates        │◄──┘   │   │
│   (22 rows)      │◄──────┘   │
└──────┬───────────┘           │
       │                       │
   gate_number                 │
  ┌────┼──────────┬────────────┼───┐
  │    │          │            │   │
┌─▼────▼─┐ ┌─────▼────┐ ┌────▼───▼──┐ ┌────────────┐
│gate_   │ │compliance│ │agent_     │ │pricing_    │
│results │ │_checks   │ │decisions  │ │traces      │
└──┬─────┘ └──┬───────┘ └──┬────────┘ └──┬─────────┘
   │          │            │              │
 conversation_id (FK from all above)      │
   │          │            │              │
┌──▼──────────▼────────────▼──────────────▼──┐
│              conversations                  │
│         (1 per quote session)               │
└──────────────────┬──────────────────────────┘
                   │
             conversation_id
                   │
          ┌────────▼────────┐
          │ conversation_   │
          │ messages         │
          └─────────────────┘
```

---

## RLS Policies (Row Level Security)

| Table | Policy | Description |
|-------|--------|-------------|
| `llm_models` | Public read | Anyone can read model definitions (no secrets stored) |
| `agents` | Public read | Anyone can read agent definitions |
| `gates` | Public read | Anyone can read gate definitions |
| `prompts` | Service role only | Only backend can read/write prompts (contains system instructions) |
| `gate_agent_map` | Public read | Anyone can read the mapping |
| `conversations` | User-scoped | Users can only see their own conversations (via auth.uid() or project ownership) |
| `conversation_messages` | User-scoped | Same as conversations — filtered by conversation ownership |
| `gate_results` | User-scoped | Same |
| `agent_decisions` | Service role only | Audit trail — only backend writes, admin reads |
| `compliance_checks` | Service role only | Same as agent_decisions |
| `pricing_traces` | Service role only | Same |

---

## Useful Views & RPC Functions

### View: `v_conversation_summary`

Quick dashboard view of all active quotes.

```sql
SELECT
  c.id,
  c.customer_name,
  c.product_id,
  c.current_gate,
  g.name AS current_gate_name,
  c.status,
  c.total_gates_completed,
  c.total_api_calls,
  c.started_at,
  c.updated_at
FROM conversations c
JOIN gates g ON g.gate_number = c.current_gate;
```

### View: `v_gate_execution_log`

Full execution timeline for a conversation.

```sql
SELECT
  gr.conversation_id,
  gr.gate_number,
  g.step_code,
  g.name AS gate_name,
  gr.status,
  gr.was_auto_advanced,
  gr.model_used,
  gr.attempt_count,
  cc.passed AS compliance_passed,
  cc.hallucination_score,
  gr.resolved_at
FROM gate_results gr
JOIN gates g ON g.gate_number = gr.gate_number
LEFT JOIN compliance_checks cc
  ON cc.conversation_id = gr.conversation_id
  AND cc.gate_number = gr.gate_number
ORDER BY gr.resolved_at;
```

### RPC: `get_active_prompt(p_gate_number, p_prompt_type)`

Returns the active prompt for a gate or agent.

```sql
CREATE FUNCTION get_active_prompt(
  p_gate_number integer DEFAULT NULL,
  p_prompt_type varchar DEFAULT 'gate',
  p_agent_slug varchar DEFAULT NULL
)
RETURNS TABLE(id uuid, developer_message text, variables_schema jsonb, version integer)
AS $$
  SELECT id, developer_message, variables_schema, version
  FROM prompts
  WHERE prompt_type = p_prompt_type
    AND (gate_number = p_gate_number OR (p_gate_number IS NULL AND gate_number IS NULL))
    AND (agent_slug = p_agent_slug OR (p_agent_slug IS NULL AND agent_slug IS NULL))
    AND is_active = true
  LIMIT 1;
$$ LANGUAGE sql STABLE;
```

### RPC: `get_conversation_state(p_conversation_id)`

Returns the full session state for the orchestrator.

```sql
CREATE FUNCTION get_conversation_state(p_conversation_id uuid)
RETURNS TABLE(
  current_gate integer,
  product_config jsonb,
  status varchar,
  comparison_mode boolean
)
AS $$
  SELECT current_gate, product_config, status, comparison_mode
  FROM conversations
  WHERE id = p_conversation_id;
$$ LANGUAGE sql STABLE;
```

---

## Migration Order

Tables should be created in this order (respecting foreign key dependencies):

1. `llm_models` (no dependencies — must be first, referenced by all Group A tables)
2. `agents` (depends on llm_models)
3. `gates` (depends on llm_models)
4. `prompts` (depends on llm_models)
5. `gate_agent_map` (depends on agents + gates + llm_models)
6. `conversations`
7. `conversation_messages` (depends on conversations)
8. `gate_results` (depends on conversations)
9. `agent_decisions` (depends on conversations)
10. `compliance_checks` (depends on conversations)
11. `pricing_traces` (depends on conversations)

---

## Storage Estimates

| Table | Rows per quote | Rows after 1,000 quotes | Growth rate |
|-------|---------------|------------------------|-------------|
| `llm_models` | 0 (static) | ~10–15 | None (grows only when new models released) |
| `agents` | 0 (static) | 4 | None |
| `gates` | 0 (static) | 22 | None |
| `prompts` | 0 (edited rarely) | ~50 versions | Slow |
| `gate_agent_map` | 0 (static) | ~60 | None |
| `conversations` | 1 | 1,000 | Linear |
| `conversation_messages` | ~30–60 | 30,000–60,000 | Linear |
| `gate_results` | ~15–22 | 15,000–22,000 | Linear |
| `agent_decisions` | ~20–40 | 20,000–40,000 | Linear |
| `compliance_checks` | ~10–15 | 10,000–15,000 | Linear |
| `pricing_traces` | ~20–50 | 20,000–50,000 | Linear |

**Total after 1,000 quotes:** ~100,000–190,000 rows. Well within Supabase free tier.
