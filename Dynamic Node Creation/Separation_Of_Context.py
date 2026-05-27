from Check_Validate_separation import model_with_structured_output, NodeModel, NodeState, model, SystemMessage, HumanMessage
from typing import List, Dict, Optional
import json


# ================================
# 5. FIELD SEPARATOR
# ================================

SEPARATOR_SYSTEM_PROMPT = """
        You are an expert node designer for a visual workflow automation platform.

                    Your job is to analyse the user's description and extract a structured node
                    definition that exactly matches the schema below.

                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    FIELD RULES
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    nodeName        → camelCase identifier, no spaces (e.g. "httpRequestNode")

                    nodeIcon        → pick the single best fit from this exact list:
                                    mouse-pointer, clock, webhook, file-input, file-output,
                                    notebook-pen, file-archive, globe, message-circle,
                                    notepad-text, aperture, message-square, bot,
                                    notepad-text-dashed, file-pen-line, terminal,
                                    table-columns-split, handshake, merge, shield-x, pause,
                                    copy-minus, funnel, key-round

                    nodeColor       → a plain color name or hex (e.g. "blue", "#3B82F6")

                    nodeCategory    → one of exactly:
                                    Trigger | Data Manipulation | Flow Manipulation |
                                    Flow Control | Core | Database nodes | AI/ML

                    nodeDescription → one clear sentence describing what the node does

                    nodeProperty    → list of UI controls the user configures (see rules below)

                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    nodeProperty FIELD RULES
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    Each property object must contain:

                    label        → human-readable name shown in the UI
                    type         → one of: text | number | text-area | dropdown |
                                            multi-select | checkbox | tag
                    defaultValue → pre-filled value string (null if none)
                    placeholder  → hint text shown inside the input (null if none)
                    options      → list of { "name": "<label>", "value": "<stored value>" }
                                    *** REQUIRED when type is "dropdown" or "multi-select" ***
                                    *** null for all other types ***
                    controlledByAnotherProperty
                                → list of other property labels whose truthy value makes
                                    this property visible  (null if always visible)

                    TYPE SELECTION GUIDE:
                    Free text input              → text
                    Long / multiline / code      → text-area
                    Integer or float             → number
                    Single choice from a list    → dropdown      ← must set options
                    Multiple choices             → multi-select  ← must set options
                    Boolean toggle               → checkbox
                    Comma-separated tags         → tag

                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    REFERENCE EXAMPLES
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    text property:
                    { "label": "Match Fields", "type": "text",
                    "defaultValue": "", "placeholder": "e.g. id,name",
                    "options": null, "controlledByAnotherProperty": null }

                    dropdown property (options REQUIRED):
                    { "label": "Case Sensitive Match", "type": "dropdown",
                    "defaultValue": "yes", "placeholder": "",
                    "options": [{"name": "Yes", "value": "yes"},
                                {"name": "No",  "value": "no"}],
                    "controlledByAnotherProperty": null }

                    text-area property:
                    { "label": "Code", "type": "text-area",
                    "defaultValue": "", "placeholder": "Write your code here",
                    "options": null, "controlledByAnotherProperty": null }

                    dropdown property with controlled child:
                    { "label": "Enable Filter", "type": "dropdown",
                    "defaultValue": "no", "placeholder": "",
                    "options": [{"name": "Yes", "value": "yes"},
                                {"name": "No",  "value": "no"}],
                    "controlledByAnotherProperty": null }

                    { "label": "Filter Value", "type": "text",
                    "defaultValue": null, "placeholder": "Enter filter…",
                    "options": null, "controlledByAnotherProperty": ["Enable Filter"] }

                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    STRICT INSTRUCTIONS
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    1. Infer every field from the user's description — do NOT ask clarifying questions.
                    2. If a top-level field cannot be determined, set it to null
                    (or [] for nodeProperty).
                    3. ALWAYS populate "options" for dropdown and multi-select types.
                    4. Leave nodeCode as null — it is generated later.
                    5. Return only the structured JSON — no markdown, no explanation.
"""

def field_separator(state: NodeState) -> NodeState:
    user_input = state["user_input"]

    messages = [
        SystemMessage(content=SEPARATOR_SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ]

    result: NodeModel = model_with_structured_output.invoke(messages)

    updates: NodeState = {
        "nodeName":        result.nodeName,
        "nodeIcon":        result.nodeIcon,
        "nodeColor":       result.nodeColor,
        "nodeCategory":    result.nodeCategory,
        "nodeDescription": result.nodeDescription,
        "nodeProperty":    [p.model_dump() for p in (result.nodeProperty or [])],
        "nodeCode":        None,
        "approved":        False,
    }
    return updates


# ================================
# 6. LLM FIELD CHECKER
# ================================

# ── Allowed values (used both in validation and in the LLM prompts) ───────
ALLOWED_ICONS = [
    "mouse-pointer", "clock", "webhook", "file-input", "file-output",
    "notebook-pen", "file-archive", "globe", "message-circle", "notepad-text",
    "aperture", "message-square", "bot", "notepad-text-dashed", "file-pen-line",
    "terminal", "table-columns-split", "handshake", "merge", "shield-x", "pause",
    "copy-minus", "funnel", "key-round",
]
ALLOWED_CATEGORIES = [
    "Trigger", "Data Manipulation", "Flow Manipulation",
    "Flow Control", "Core", "Database nodes", "AI/ML",
]
ALLOWED_PROP_TYPES = [
    "text", "number", "text-area", "dropdown", "multi-select", "checkbox", "tag",
]


class Issue:
    """Describes a single detected problem in the current state."""
    def __init__(self, field: str, problem: str, context: str = ""):
        self.field   = field    # which state key is affected
        self.problem = problem  # short description of what is wrong
        self.context = context  # extra info (e.g. property label for nested issues)

    def __repr__(self):
        return f"Issue(field={self.field!r}, problem={self.problem!r}, context={self.context!r})"


def detect_issues(state: dict) -> List[Issue]:
    """
    Programmatically scan the state and return a list of Issues.
    Covers:
      • Top-level fields that are None / empty string
      • nodeProperty items missing a label or type
      • dropdown / multi-select properties without options
    """
    issues: List[Issue] = []

    # ── Top-level required fields ──────────────────────────────────────────
    top_level_checks = {
        "nodeName":        "Node name is missing",
        "nodeIcon":        "Node icon is missing",
        "nodeColor":       "Node color is missing",
        "nodeCategory":    "Node category is missing",
        "nodeDescription": "Node description is missing",
    }
    for field, problem in top_level_checks.items():
        val = state.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            issues.append(Issue(field=field, problem=problem))
        elif field == "nodeIcon" and val not in ALLOWED_ICONS:
            issues.append(Issue(
                field=field,
                problem=f"'{val}' is not a valid icon name",
            ))
        elif field == "nodeCategory" and val not in ALLOWED_CATEGORIES:
            issues.append(Issue(
                field=field,
                problem=f"'{val}' is not a valid category",
            ))

    # ── nodeProperty validation ────────────────────────────────────────────
    for i, prop in enumerate(state.get("nodeProperty") or []):
        label = prop.get("label") or f"property #{i+1}"

        if not prop.get("label"):
            issues.append(Issue(
                field="nodeProperty",
                problem="A property is missing its label",
                context=f"property index {i}",
            ))

        ptype = prop.get("type")
        if not ptype or ptype not in ALLOWED_PROP_TYPES:
            issues.append(Issue(
                field="nodeProperty",
                problem=f"Property '{label}' has an invalid or missing type: {ptype!r}",
                context=label,
            ))

        if ptype in ("dropdown") and not prop.get("options"):
            issues.append(Issue(
                field="nodeProperty",
                problem=f"Property '{label}' is a {ptype} but has no options defined",
                context=label,
            ))

    return issues


# ── LLM prompts used inside the checker ───────────────────────────────────

CHECKER_QUESTION_PROMPT = """
                You are a helpful assistant inside a node-builder tool.

                The user has just described a workflow node. The system tried to extract all
                fields automatically but one field is missing or incorrect.

                Node context:
                {context}

                Problem detected:
                {problem}

                Field affected: {field}

                Write a SHORT, friendly question (1-2 sentences) asking the user to provide
                the correct value for this field.

                If the field has a fixed set of allowed values, list them clearly in your question.
                Do not start with "I" — start with the field name or a direct question word.
                Return ONLY the question text, nothing else.
                """

CHECKER_PARSE_PROMPT = """
                You are a strict value extractor for a node-builder tool.

                Field: {field}
                Problem: {problem}
                Constraints: {constraints}
                User's raw answer: "{answer}"

                Extract the valid value from the user's answer and return it as JSON:
                {{"field": "<field name>", "value": "<extracted valid value>"}}

                Rules:
                - If the answer clearly maps to a valid value, return it.
                - For nodeIcon: return exactly one string from the allowed list that best matches.
                - For nodeCategory: return exactly one string from the allowed list that best matches.
                - For a nodeProperty options issue: return a JSON array of option objects
                like [{{"name": "...", "value": "..."}}] as the value string.
                - If the answer is unusable or empty, return:
                {{"field": null, "value": null}}

                Return ONLY the JSON object, no explanation.
"""


def _build_node_context(state: dict) -> str:
    """One-line summary of the node so the LLM has context when asking questions."""
    return (
        f"nodeName={state.get('nodeName') or '(unknown)'}, "
        f"nodeCategory={state.get('nodeCategory') or '(unknown)'}, "
        f"nodeDescription={state.get('nodeDescription') or '(unknown)'}"
    )


def _constraints_for_issue(issue: Issue) -> str:
    """Return a human-readable constraint string for the LLM parser."""
    if issue.field == "nodeIcon":
        return f"Must be one of: {', '.join(ALLOWED_ICONS)}"
    if issue.field == "nodeCategory":
        return f"Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
    if issue.field == "nodeProperty" and "options" in issue.problem:
        return (
            'Must be a list of options. '
            'Return as JSON array: [{"name": "Label", "value": "stored_value"}, ...]'
        )
    if issue.field == "nodeProperty" and "type" in issue.problem:
        return f"Must be one of: {', '.join(ALLOWED_PROP_TYPES)}"
    return "Free text — match the context of the node."


def _ask_and_parse(issue: Issue, state: dict) -> Optional[Dict]:
    """
    Use the LLM to generate a question, show it to the user via input(),
    then use the LLM again to parse and validate the answer.
    Returns {"field": ..., "value": ...} or None if the answer was unusable.
    """
    # Step 1: LLM generates the question
    question_prompt = CHECKER_QUESTION_PROMPT.format(
        context=_build_node_context(state),
        problem=issue.problem,
        field=issue.field,
    )
    q_response = model.invoke([SystemMessage(content=question_prompt)])
    question   = q_response.content.strip()

    # Step 2: Show the question and get user input
    print(f"\n  {question}")
    answer = input("  Your answer: ").strip()

    if not answer:
        return None

    # Step 3: LLM parses and validates the answer
    parse_prompt = CHECKER_PARSE_PROMPT.format(
        field=issue.field,
        problem=issue.problem,
        constraints=_constraints_for_issue(issue),
        answer=answer,
    )
    p_response = model.invoke([SystemMessage(content=parse_prompt)])
    raw        = p_response.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    try:
        parsed = json.loads(raw)
        if parsed.get("field") and parsed.get("value"):
            return parsed
    except (json.JSONDecodeError, AttributeError):
        pass

    return None


def _apply_parsed(state: dict, result: Dict, issue: Issue) -> dict:
    """
    Write the parsed value back into the correct place in state.
    Handles both top-level fields and nested nodeProperty fixes.
    """
    state  = dict(state)
    field  = result["field"]
    value  = result["value"]

    if field != "nodeProperty":
        # Simple top-level assignment
        state[field] = value
        return state

    # nodeProperty — need to find the right property by context label
    props = [dict(p) for p in (state.get("nodeProperty") or [])]

    if "options" in issue.problem:
        # Fix the options list of the named property
        target_label = issue.context
        # value may be a JSON string or already a list
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = []
        for prop in props:
            if prop.get("label") == target_label:
                prop["options"] = value
                break

    elif "label" in issue.problem:
        idx = int(issue.context.split()[-1]) if issue.context else 0
        if 0 <= idx < len(props):
            props[idx]["label"] = value

    elif "type" in issue.problem:
        target_label = issue.context
        for prop in props:
            if prop.get("label") == target_label:
                prop["type"] = value
                break

    state["nodeProperty"] = props
    return state


def llm_field_checker(state: NodeState) -> NodeState:
    """
    Node 2 – LLM Field Checker
    Detects missing / invalid fields and runs an interactive
    LLM ↔ user conversation to fix each one before human review.
    """
    current = dict(state)
    issues  = detect_issues(current)

    if not issues:
        print("\n  All fields detected correctly. Moving to review stage.\n")
        return current

    total = len(issues)
    print(f"\n  Found {total} field(s) that need your input.\n")

    for idx, issue in enumerate(issues, 1):
        print(f"  [{idx}/{total}]  {issue.problem}")

        # Retry loop — keep asking until we get a valid answer
        while True:
            result = _ask_and_parse(issue, current)
            if result:
                current = _apply_parsed(current, result, issue)
                print("  Updated.\n")
                break
            else:
                print(" Could not understand that answer. Please try again.")

    print("  All issues resolved. Proceeding to human review.\n")
    return current
