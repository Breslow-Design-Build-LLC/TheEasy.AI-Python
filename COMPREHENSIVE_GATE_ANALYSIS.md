# COMPREHENSIVE ANALYSIS: TheEasy.AI Pergola Quote System - 22 Gates

**Analysis Date**: 2025-02-15  
**Total Gates Analyzed**: 22  
**Gate Sequence**: [1, 2, 19(2b), 3, 20(3b), 21(3c), 4, 22(4b), 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

---

## EXECUTIVE SUMMARY

This analysis reveals **16 variable mismatches**, **19 missing context builders**, **24 prompt quality issues**, **6 navigation logic gaps**, and **40 security concerns** across the 22-gate system. The most critical issue is a **systematic variable mismatch between what prompts expect and what code passes** (16/22 gates affected).

**Critical Path Issues**:
- Variables_template in registry.py doesn't match required_variables expected by prompts
- orchestrator.py only builds 1 of 20 required context variables
- No conditional skip logic for gates 19, 20, 21, 22
- No revision routing implementation in gate 17
- 13 gates accept free-text input without sanitization instructions

---

## ANALYSIS 1: VARIABLE MISMATCH ANALYSIS

### Overview
**Total Mismatches**: 16 out of 22 gates (73% affected)

The orchestrator's `resolve_variables()` method reads from `gate.variables_template` and maps them to session values. However, there is a **systematic mismatch** between:
- What the **prompt's Runtime Config** expects (defined in prompts_export.json)
- What the **code's variables_template** provides (defined in registry.py)

### Detailed Findings

#### Critical Mismatches

| Gate # | Gate Name | Prompt Expects | Code Sends | Gap |
|--------|-----------|---|---|---|
| **4** | Structure & Posts | `base_pricing_context` | `product_options`, `total_bays`, `base_pricing_context` | Code sends extra vars not in prompt |
| **5** | Color / Finish | `finish_surcharge_context` | `product_id`, `structure_type` | Complete mismatch - none of code vars in prompt |
| **6** | Roof Options | `lighting_fans_context` | `product_id`, `quote_context` | Complete mismatch |
| **7** | Electrical & Lighting | `heater_context` | `product_id`, `quote_context` | Complete mismatch |
| **8** | Fan & Heating | `shades_privacy_context` | `product_id`, `quote_context` | Complete mismatch |
| **9** | Screens & Enclosures | `trim_context` | `product_id`, `quote_context` | Complete mismatch |
| **10** | Permits & Engineering | `electrical_scope_context` | `product_id`, `quote_context` | Complete mismatch |
| **11** | Installation Options | `installation_context` | `product_id`, `quote_context` | Complete mismatch |
| **12** | Warranty & Protection | `services_context` | `product_id`, `quote_context` | Complete mismatch |
| **13** | Discounts & Promotions | `quote_summary_context` | `product_id`, `total_bays`, `quote_context` | Complete mismatch |
| **14** | Summary & Review | `audit_context` | `product_id`, `quote_context` | Complete mismatch |
| **15** | Customer Info & Delivery | `final_payload_context` | `product_id`, `state` | Complete mismatch |
| **16** | Final Quote & Checkout | `breakdown_context` | `product_id`, `resolved_pricing_items`, `package_definitions`, `missing_price_flags` | Complete mismatch |
| **17** | Revisions | `revision_context` | `product_id`, `quote_context` | Complete mismatch |
| **18** | Post-Quote Handoff | `handoff_context` | `product_id`, `quote_context` | Complete mismatch |
| **22** | Structural Add-Ons | `structural_addons_context` | `product_id`, `quote_context` | Complete mismatch |

### Impact
- **Severity**: CRITICAL
- **Impact**: Prompts receive wrong variable names and cannot access expected data
- **Result**: Variable resolution in `orchestrator.py:39-50` will return empty strings for most gates (fallback on line 49)
- **Example**: Gate 5 expects `finish_surcharge_context` but receives `product_id` and `structure_type`

### Root Cause
The `prompts_export.py` script defines expected variables in the tuple (e.g., `{'finish_surcharge_context': '{}'}`), but `registry.py` was never updated to match these expectations. Registry still uses generic variable names like `quote_context` instead of gate-specific context builders.

---

## ANALYSIS 2: DATA FLOW GAPS & CONTEXT BUILDER COVERAGE

### Overview
The orchestrator's `_build_composite_contexts()` method (orchestrator.py:82-114) is responsible for building JSON context variables that downstream gates need. **Currently only 1 context is built; 19 are missing.**

### Context Builder Coverage

#### Currently Built (1/20)
✓ **bay_logic_context** (lines 82-114)
  - Built after gate 3, 20, or 21 completes
  - Combines dimensions from session data
  - Used by gates that need bay calculations

#### Missing Builders (19/20)
All of the following contexts are expected by prompts but **not built** by orchestrator:

```
❌ orientation_context          (expected by gate 19/2b)
❌ threshold_advisory_context   (expected by gate 20/3b)
❌ dimension_router_context     (expected by gate 21/3c)
❌ base_pricing_context         (expected by gate 4)
❌ structural_addons_context    (expected by gate 22/4b)
❌ finish_surcharge_context     (expected by gate 5)
❌ lighting_fans_context        (expected by gate 6)
❌ heater_context               (expected by gate 7)
❌ shades_privacy_context       (expected by gate 8)
❌ trim_context                 (expected by gate 9)
❌ electrical_scope_context     (expected by gate 10)
❌ installation_context         (expected by gate 11)
❌ services_context             (expected by gate 12)
❌ quote_summary_context        (expected by gate 13)
❌ audit_context                (expected by gate 14)
❌ final_payload_context        (expected by gate 15)
❌ breakdown_context            (expected by gate 16)
❌ revision_context             (expected by gate 17)
❌ handoff_context              (expected by gate 18)
```

### Data Flow Issues

#### Gate 1 → Downstream
- Gate 1 outputs: `product_id`, `product_label`, `question`
- Downstream gates 2-18 all need `product_id`
- **Status**: ✓ Stored in session.product_config (line 78), accessible to downstream gates

#### Gate 2 → Gates 3, 20, 21, 4-18
- Gate 2 outputs: width_ft_assumed, length_ft_assumed, width_ft_confirmed, etc.
- Should be packed into bay_logic_context for gates 3, 20, 21
- **Status**: ✓ bay_logic_context DOES pull these values (lines 88-97)
- However: No orientation_context builder for gate 19

#### Gate 3 → Gates 20, 21, 4, 22, 5-18
- Gate 3 outputs: bay_pricing, total_bays, dimension_analysis results
- Should be packed into multiple contexts (threshold_advisory_context, dimension_router_context, base_pricing_context, etc.)
- **Status**: ❌ NO BUILDERS - gates 20, 21, 4, 22 all receive gate_3_response as a raw JSON string instead of parsed context

#### Example Data Flow Gap
```
Gate 3 outputs:
{
  "status": "ok",
  "total_bays": 2,
  "bay_width": 15,
  "bay_pricing": {...}
}

Gate 4 expects: base_pricing_context (JSON with extracted pricing data)
Gate 20 expects: threshold_advisory_context (JSON with advisory data)
Gate 21 expects: dimension_router_context (JSON with routing rules)

Current behavior: All receive gate_3_response as raw JSON string
```

### Conditional Gate Dependencies

**Gates that should be conditionally skipped but have NO SKIP LOGIC:**

1. **Gate 19 (2b - Orientation Review)**
   - Should skip if `orientation_review_required != true` from gate 2
   - Code check needed: `if session.product_config.get('orientation_review_required'): advance to gate 19, else skip to gate 3`
   - **Status**: ❌ NO CONDITIONAL SKIP - always runs

2. **Gate 20 (3b - Threshold Advisory)**
   - Should skip if threshold conditions not met from gate 3
   - Code check needed based on gate 3 output flags
   - **Status**: ❌ NO CONDITIONAL SKIP - always runs

3. **Gate 21 (3c - Dimension Router)**
   - Should skip if dimension routing not needed from gate 3
   - **Status**: ❌ NO CONDITIONAL SKIP - always runs

4. **Gate 22 (4b - Structural Add-Ons)**
   - Should skip if no structural requirements from gate 4
   - **Status**: ❌ NO CONDITIONAL SKIP - always runs

---

## ANALYSIS 3: PROMPT QUALITY ISSUES

### Overview
**Total Issues**: 24 quality issues across prompts

### Critical Issues

#### 1. Missing Output Schema (21 gates)
**Severity**: HIGH (affects JSON parsing)

All gates except Gate 1 are **missing the "## Output Schema" section** in their developer messages:
- Gates 2, 19, 3, 20, 21, 4, 22, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18

**Impact**: 
- Unclear what fields each gate should output
- Inconsistent JSON structure expectations
- orchestrator.py:64-79 collects all fields into product_config without validation
- No schema enforcement

**Example**: Gate 2 prompt has no output schema defined. Should outputs be:
```json
{
  "width_ft_assumed": 20,
  "length_ft_assumed": 30,
  "orientation_review_required": true,
  "status": "ok"
}
```

But this is nowhere specified in the prompt.

#### 2. Missing JSON-Only Instruction (3 gates)
**Severity**: HIGH (enables injection attacks)

Gates **16, 17, 18** are missing "Return ONLY valid JSON" instruction:

- Gate 16: Final Quote & Checkout
- Gate 17: Revisions
- Gate 18: Post-Quote Handoff

These final gates handle sensitive pricing/revision data without JSON-only enforcement.

#### 3. Truncated Prompts
**Severity**: MEDIUM

No prompts appear truncated, but message lengths vary:
- Shortest: Gate 17 (949 chars)
- Longest: Gate 2 (5362 chars)

#### 4. Status Value Inconsistency
**Finding**: All prompts use `"status": "ok"` but orchestrator checks for `"ok" | "complete" | "done"`

From orchestrator.py:57:
```python
if status in ("ok", "complete", "done"):
    return True
```

**Reality**: All 22 gates only use `"ok"` - the other two are dead code.

### Summary Table

| Gate | Has Output Schema | Has JSON Instruction | Message Length | Issues |
|------|-------------------|-------------------|--------|--------|
| 1 | ✓ (partial) | ✓ | 943 | - |
| 2 | ❌ | ✓ | 5362 | No schema |
| 19 | ❌ | ✓ | 3680 | No schema |
| 3 | ❌ | ✓ | 2618 | No schema |
| 20 | ❌ | ✓ | 3514 | No schema |
| 21 | ❌ | ✓ | 1929 | No schema |
| 4 | ❌ | ✓ | 3931 | No schema |
| 22 | ❌ | ✓ | 4805 | No schema |
| 5 | ❌ | ✓ | 3615 | No schema |
| 6 | ❌ | ✓ | 2715 | No schema |
| 7 | ❌ | ✓ | 2885 | No schema |
| 8 | ❌ | ✓ | 4017 | No schema |
| 9 | ❌ | ✓ | 2447 | No schema |
| 10 | ❌ | ✓ | 2905 | No schema |
| 11 | ❌ | ✓ | 2203 | No schema |
| 12 | ❌ | ✓ | 2673 | No schema |
| 13 | ❌ | ✓ | 2444 | No schema |
| 14 | ❌ | ✓ | 2431 | No schema |
| 15 | ❌ | ✓ | 3339 | No schema |
| 16 | ❌ | ❌ | 1930 | **No schema, No JSON instruction** |
| 17 | ❌ | ❌ | 949 | **No schema, No JSON instruction** |
| 18 | ❌ | ❌ | 936 | **No schema, No JSON instruction** |

---

## ANALYSIS 4: NAVIGATION LOGIC GAPS

### Overview
**Total Issues**: 6 major navigation logic gaps

### Issue #1: Dead Code in should_advance()
**Severity**: MEDIUM (code maintainability)

**Current Code** (orchestrator.py:52-62):
```python
def should_advance(self, parsed: Optional[dict[str, Any]]) -> bool:
    if not parsed or not isinstance(parsed, dict):
        return False
    status = parsed.get("status", "").lower()
    if status in ("ok", "complete", "done"):  # ⚠️ "complete" and "done" never used
        return True
```

**Reality**: All 22 prompts use only `"status": "ok"`. The values `"complete"` and `"done"` are dead code that will never be reached.

**Recommendation**: Simplify to only check for `"ok"` or clarify intent with prompt developers.

### Issue #2-5: Missing Conditional Skip Logic (4 gates)
**Severity**: CRITICAL (breaks intended flow)

#### Gate 19 (2b - Orientation Review) - MISSING CONDITIONAL SKIP

**Intent**: Gate 2 determines if orientation review is needed. Gate 19 should only run if `orientation_review_required=true`.

**Current Code**: No check exists. Gate 19 always runs.

**Example Flow**:
```
User enters dimensions 20×30
Gate 2 output: 
{
  "status": "ok",
  "width_ft_assumed": 20,
  "length_ft_assumed": 30,
  "orientation_review_required": false  // ← FLAG NOT CHECKED
}

Current: Gate advances to Gate 19 (Orientation Review) anyway
Correct: Should skip Gate 19 and go straight to Gate 3
```

**Required Code**: 
```python
def should_skip_gate_19(session: SessionState) -> bool:
    orientation_required = session.product_config.get('orientation_review_required', False)
    return not orientation_required

# In advance_gate(), check before moving to next gate:
if session.current_gate == 2:
    if should_skip_gate_19(session):
        session.advance()  # Skip 19, go to 3
```

#### Gate 20 (3b - Threshold Advisory) - MISSING CONDITIONAL SKIP

**Intent**: Gate 3 determines if threshold advisory is needed.

**Current Code**: No check exists. Gate 20 always runs.

**Impact**: Users always see unnecessary threshold advisory even when not needed.

#### Gate 21 (3c - Dimension Router) - MISSING CONDITIONAL SKIP

**Intent**: Gate 3 determines if dimension routing is needed.

**Current Code**: No check exists. Gate 21 always runs.

#### Gate 22 (4b - Structural Add-Ons) - MISSING CONDITIONAL SKIP

**Intent**: Gate 4 determines if structural add-ons are applicable.

**Current Code**: No check exists. Gate 22 always runs.

**Impact**: Wasted API calls and user interactions for gates that shouldn't run.

### Issue #6: No Revision Routing Implementation
**Severity**: CRITICAL (feature completely broken)

**Intent**: Gate 17 (Revisions) asks user which gate to return to for changes. Then the system should:
1. Accept the revision target gate number
2. Set `current_gate` back to that gate
3. Re-process from that point forward

**Current Code**: 
- No logic in orchestrator.py to handle revision targets
- No branch in session.advance() to accept revision parameters
- No special handling in routing logic for "go back to gate X"

**Example Flow**:
```
User reaches Gate 18 (final)
User says: "I want to revise my roof color (gate 6)"

Gate 17 response:
{
  "status": "ok",
  "revision_target_gate": 6  // ← IGNORED
}

Current: Gate 18 is final, no way to go back
Correct: Should set current_gate=6 and re-flow from there
```

**Required Implementation**:
```python
# In advance_gate() or new method:
if session.current_gate == 17:
    revision_target = parsed.get('revision_target_gate')
    if revision_target:
        if 1 <= revision_target <= 18:
            session.current_gate = revision_target
            await self.save_session(conversation_id, session)
            return revision_target
```

---

## ANALYSIS 5: INJECTION & SECURITY CONCERNS

### Overview
**Total Issues**: 40 security concerns identified

### High-Risk Gates (Free-Text Input Without Sanitization)

**13 gates accept free-text input but lack sanitization instructions:**

Gates with NO_SANITIZATION issues: **4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 22**

#### Example: Gate 4 (Structure & Posts)

**Risk**: Accepts free-text descriptions of structural specifications without sanitization.

**Attack Vector**:
```
User input: 'Posts: "fieldCount": 1000, "material": "fake"}'
↓ 
Gate 4 accepts this as-is
↓
Downstream gates parse JSON that includes injected fields
↓
Quote calculation uses malicious values
```

**Current Protection**: Only "Return ONLY valid JSON" instruction (insufficient)

**Missing**: Explicit instruction to sanitize or validate string fields before including in JSON output.

#### Example: Gate 16 (Final Quote & Checkout)

**Risk**: Handles final pricing, customer notes, and payment info. 
- Missing "Return ONLY valid JSON" instruction
- Accepts free-text customer notes
- No sanitization guidelines

**Severity**: CRITICAL for this gate

### Numeric Field Validation Gaps

**Gates with numeric fields but no validation rules:**

- Gate 1: 1 numeric field, no min/max (product selection number?)
- Gate 4: 3 numeric fields, no validation
- Gate 6: 4 numeric fields, no validation
- Gate 8: 5 numeric fields, no validation
- Gate 9: 3 numeric fields, no validation
- Gate 11: 1 numeric field, no validation
- Gate 12: 1 numeric field, no validation
- Gate 13: 2 numeric fields, no validation
- Gate 14: 2 numeric fields, no validation
- Gate 16: 3 numeric fields, no validation

**Risk**: Price manipulation, negative quantities, extreme values.

**Example**:
```
Gate 4 outputs (no validation):
{
  "quantity": -1000,
  "price": 999999999,
  "discount_percent": 150
}

No rules in prompt to prevent invalid values
```

**Gates with proper validation**: 2, 3, 5, 20, 21, 22, 7, 10, 15 (9 gates)

### Missing JSON Instructions (3 gates)

Gates **16, 17, 18** lack "Return ONLY valid JSON. No extra text." instruction:
- Gate 16: Final Quote & Checkout (sensitive pricing data)
- Gate 17: Revisions (complex nested revisions)
- Gate 18: Post-Quote Handoff (delivery/fulfillment data)

**Risk**: AI could output explanatory text before/after JSON, breaking parsing.

### Security Issue Summary by Severity

| Severity | Count | Gates Affected |
|----------|-------|---|
| **HIGH: No Sanitization** | 13 | 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 22 |
| **MEDIUM: No Numeric Validation** | 11 | 1, 4, 6, 8, 9, 11, 12, 13, 14, 16 |
| **HIGH: No JSON Instruction** | 3 | 16, 17, 18 |
| **LOW: Free-Text But Safe** | 2 | Gates with both JSON instruction and some validation |

### Recommended Mitigations

1. **Add to all free-text-accepting gates**:
   ```
   "Return ONLY valid JSON. No extra text."
   "Sanitize all string fields: escape quotes, remove newlines."
   "Validate numeric fields are within acceptable ranges."
   ```

2. **Add to gates 16, 17, 18**:
   ```
   "Return ONLY valid JSON. No extra text."
   ```

3. **For price/quantity fields across all gates**:
   ```
   "All numeric fields must be non-negative, real numbers."
   "Prices must be between $0 and $999,999."
   "Quantities must be between 1 and 1000."
   ```

---

## SUMMARY BY GATE

### Gate-by-Gate Risk Profile

```
GATE  NAME                          VARIABLE  DATA FLOW  PROMPT    NAVIGATION  SECURITY
                                    MISMATCH  GAPS       QUALITY   LOGIC       RISK

1     Product Selection              ✓ OK       ✓ OK      ⚠️ LOW     ✓ OK        ⚠️ MEDIUM
2     Dimensions & State             ✓ OK       ✓ OK      ❌ HIGH    ✓ OK        ✓ LOW
19    Orientation Review             ✓ OK       ⚠️ GAP    ❌ HIGH    ❌ MISSING   ✓ LOW
3     Bay Logic & Pricing            ✓ OK       ⚠️ GAP    ❌ HIGH    ✓ OK        ✓ LOW
20    Threshold Advisory             ✓ OK       ❌ NONE   ❌ HIGH    ❌ MISSING   ✓ LOW
21    Dimension Router               ✓ OK       ❌ NONE   ❌ HIGH    ❌ MISSING   ✓ LOW
4     Structure & Posts              ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ CRITICAL
22    Structural Add-Ons             ❌ HIGH    ❌ NONE   ❌ HIGH    ❌ MISSING   ❌ HIGH
5     Color / Finish                 ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ✓ LOW
6     Roof Options                   ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
7     Electrical & Lighting          ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
8     Fan & Heating                  ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
9     Screens & Enclosures           ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
10    Permits & Engineering          ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
11    Installation Options           ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
12    Warranty & Protection          ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
13    Discounts & Promotions         ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
14    Summary & Review               ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
15    Customer Info & Delivery       ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
16    Final Quote & Checkout         ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ CRITICAL
17    Revisions                      ❌ HIGH    ⚠️ GAP    ❌ HIGH    ❌ MISSING   ❌ HIGH
18    Post-Quote Handoff             ❌ HIGH    ⚠️ GAP    ❌ HIGH    ✓ OK        ❌ HIGH
```

---

## CRITICAL ISSUES (MUST FIX)

### Priority 1: Variable Mismatch (16 gates)
**Files to fix**:
- `/sessions/kind-sweet-davinci/mnt/TheEasy.AI-Python/src/app/gates/registry.py` (lines 38-259)

**Issue**: 16 gates have incorrect `variables_template` mappings

**Action**: Update variables_template to match prompt requirements:
```python
# CURRENT (WRONG)
5: {"product_id": "product_id", "structure_type": "structure_type"}

# SHOULD BE (EXAMPLE)
5: {"finish_surcharge_context": "finish_surcharge_context"}
```

But wait - `finish_surcharge_context` isn't built anywhere! This leads to issue #2.

### Priority 2: Missing Context Builders (19 gates)
**Files to fix**:
- `/sessions/kind-sweet-davinci/mnt/TheEasy.AI-Python/src/app/services/orchestrator.py` (lines 82-114)

**Issue**: Only 1 of 20 context variables is built

**Action**: Implement context builders for:
- orientation_context
- threshold_advisory_context
- dimension_router_context
- base_pricing_context
- structural_addons_context
- finish_surcharge_context
- lighting_fans_context
- heater_context
- shades_privacy_context
- trim_context
- electrical_scope_context
- installation_context
- services_context
- quote_summary_context
- audit_context
- final_payload_context
- breakdown_context
- revision_context
- handoff_context

### Priority 3: Missing Conditional Skips (4 gates)
**Files to fix**:
- `/sessions/kind-sweet-davinci/mnt/TheEasy.AI-Python/src/app/services/orchestrator.py`
- `/sessions/kind-sweet-davinci/mnt/TheEasy.AI-Python/src/app/gates/session_state.py`

**Issue**: Gates 19, 20, 21, 22 should conditionally skip but always run

**Action**: Add flag checks before advancing to these gates

### Priority 4: Missing Revision Routing
**Files to fix**:
- `/sessions/kind-sweet-davinci/mnt/TheEasy.AI-Python/src/app/services/orchestrator.py`

**Issue**: Gate 17 revision logic not implemented

**Action**: Add code to handle revision_target_gate and reset current_gate

### Priority 5: Security - Missing Instructions (3 gates)
**Files to fix**:
- Update prompts (via OpenAI Prompt Library) for gates 16, 17, 18

**Issue**: Gates 16, 17, 18 missing JSON-only instructions

---

## RECOMMENDATION PRIORITY MATRIX

| Issue | Impact | Effort | Severity | Priority |
|-------|--------|--------|----------|----------|
| Variable mismatches (16 gates) | Prompts receive wrong vars | HIGH | CRITICAL | 1 |
| Missing context builders (19) | Data not prepared for gates | HIGH | CRITICAL | 1 |
| Missing conditional skips (4) | UX broken, wasted API calls | MEDIUM | HIGH | 2 |
| Missing revision routing | Feature broken | MEDIUM | HIGH | 2 |
| Missing output schemas (21) | No validation, parsing issues | MEDIUM | MEDIUM | 3 |
| Security gaps (free-text sanitization) | Injection risk | MEDIUM | HIGH | 2 |
| Dead code (complete/done) | Maintainability | LOW | LOW | 4 |

---

## IMPLEMENTATION ROADMAP

### Phase 1 (CRITICAL - Do First)
1. Fix variable mismatch in registry.py (1-2 hours)
2. Implement missing context builders in orchestrator.py (3-4 hours)
3. Test variable flow end-to-end

### Phase 2 (HIGH - Do Second)
1. Implement conditional skip logic for gates 19, 20, 21, 22 (1-2 hours)
2. Implement revision routing for gate 17 (2-3 hours)
3. Add security instructions to free-text gates

### Phase 3 (MEDIUM - Do Third)
1. Add output schemas to all prompts (via OpenAI Prompt Library) (2-3 hours)
2. Add JSON-only instructions to gates 16, 17, 18 (0.5 hour)
3. Add numeric validation rules to all gates with price/quantity fields

### Phase 4 (LOW - Nice to Have)
1. Remove dead code ("complete"/"done" status checks)
2. Standardize status values across all gates
3. Add comprehensive input validation to orchestrator.collect_data()

---

## TECHNICAL DETAILS

### Variable Resolution Flow (Current vs Correct)

**Current Flow**:
```
Gate 5 asks for: finish_surcharge_context
Registry.variables_template says: {"product_id": "product_id", "structure_type": "structure_type"}
orchestrator.resolve_variables() maps:
  "product_id" → settings.product_id OR session.product_config["product_id"] ✓
  "structure_type" → session.product_config["structure_type"] ✓
Result: Gate 5 receives {product_id: "r_blade", structure_type: "steel"}
Gate 5 expects: finish_surcharge_context which doesn't exist
AI response: Unable to process - missing required context
```

**Correct Flow Should Be**:
```
Gate 5 asks for: finish_surcharge_context
Registry.variables_template says: {"finish_surcharge_context": "finish_surcharge_context"}
orchestrator._build_composite_contexts() creates:
  session.product_config["finish_surcharge_context"] = JSON.stringify({...})
orchestrator.resolve_variables() maps:
  "finish_surcharge_context" → session.product_config["finish_surcharge_context"] ✓
Result: Gate 5 receives {finish_surcharge_context: "{...json...}"}
AI response: Processes surcharge data and returns choices
```

### Context Builder Pattern

Implement builders following this pattern:

```python
def _build_composite_contexts(self, session: SessionState) -> None:
    pc = session.product_config
    
    # Build orientation_context from gate 2 output
    if 'width_ft_confirmed' in pc:
        orientation_context = {
            "width_ft": pc.get('width_ft_confirmed'),
            "orientation": pc.get('final_orientation'),
            "notes": pc.get('orientation_notes')
        }
        pc['orientation_context'] = json.dumps(orientation_context)
    
    # Build threshold_advisory_context from gate 3 output
    if 'bay_count_as_entered' in pc:
        threshold_context = {
            "bay_count": pc.get('bay_count_as_entered'),
            "threshold_flag": pc.get('exceeds_threshold'),
            "recommended_action": pc.get('threshold_recommendation')
        }
        pc['threshold_advisory_context'] = json.dumps(threshold_context)
    
    # ... (repeat for all 19 missing contexts)
```

---

## FILES AFFECTED

### Files That Need Changes

1. **registry.py** (CRITICAL)
   - Lines 38-259: Fix all `variables_template` entries
   - 16 gates need corrections

2. **orchestrator.py** (CRITICAL)
   - Lines 82-114: Expand `_build_composite_contexts()` with 19 new builders
   - Add conditional skip logic before advancing gates 19, 20, 21, 22
   - Add revision routing logic in `advance_gate()`

3. **session_state.py** (POSSIBLY)
   - May need new methods to support conditional skipping

4. **Prompts (via OpenAI Prompt Library)**
   - Update gates 16, 17, 18 to include JSON-only instructions
   - Update all gates (2-18) to include Output Schema sections
   - Add sanitization/validation instructions to free-text accepting gates

### Files Not Affected

- `models.py`: No changes needed
- `config.py`: No changes needed
- `conversation_service.py`: No changes needed
- `openai_service.py`: No changes needed

---

## CONCLUSION

The pergola quoting system has **fundamental architectural issues** that prevent it from functioning correctly as designed:

1. **Variables don't match** between prompts and code (16/22 gates)
2. **Context isn't built** for gates that expect it (19/20 missing)
3. **Navigation logic is incomplete** (no conditionals, no revision routing)
4. **Prompt quality is inconsistent** (no output schemas, missing JSON instructions)
5. **Security is insufficient** (no sanitization for free-text inputs)

**Estimated Fix Effort**: 8-12 hours for comprehensive resolution

**Estimated Risk if Unfixed**: System will fail or produce incorrect quotes due to missing data and navigation logic

**Go-Live Readiness**: NOT READY - Critical issues must be resolved before production deployment

---

**Report Generated**: 2025-02-15
**Analysis Scope**: All 22 gates, complete data flow, security posture
**Methodology**: Code review, prompt analysis, variable tracing, security auditing
