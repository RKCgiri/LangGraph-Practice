from Check_Validate_separation import model, SystemMessage, NodeState
import json
from typing import List, Dict, Optional

# ================================
# LLM FIELD CHECKER  —  Full Validation
#
#  Pass 1 — Manual (plain input())  →  nodeName, nodeIcon, nodeColor, nodeCategory
#  Pass 2 — LLM-assisted            →  nodeDescription, nodeProperty (all sub-fields)
# ================================

# ── Allowed values ─────────────────────────────────────────────────────────
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
TYPES_REQUIRING_OPTIONS = ("dropdown", "multi-select")


# ══════════════════════════════════════════════════════════════════════════
# PASS 1 — MANUAL FIXES
#   nodeName, nodeIcon, nodeColor, nodeCategory
#   No LLM. Just show current value → ask user → validate → apply.
# ══════════════════════════════════════════════════════════════════════════


def _manual_fix_nodeName(state: dict) -> dict:
    name = (state.get("nodeName") or "").strip()
    # Accept any non-empty name (spaces allowed)
    if name:
        return state

    # If missing, ask user
    print("\n  [nodeName]  Node name is missing.")

    while True:
        answer = input(
            "  Enter the node name (letters, spaces allowed)\n"
            "  e.g.  http request node, limit node, compare dataset node\n"
            "  → "
        ).strip()

        if answer:  # only check non-empty
            state = dict(state)
            state["nodeName"] = answer
            print(f" nodeName → '{answer}'")
            return state

        print(" Name cannot be empty. Try again.")


def _manual_fix_nodeIcon(state: dict) -> dict:
    icon = (state.get("nodeIcon") or "").strip()
    if icon in ALLOWED_ICONS:
        return state                                  

    if not icon:
        print("\n  [nodeIcon]  Node icon is missing.")
    else:
        print(f"\n  [nodeIcon]  '{icon}' is not a valid icon name.")

    # Print menu in rows of 4
    print("  Allowed icons:")
    for i in range(0, len(ALLOWED_ICONS), 4):
        row = ALLOWED_ICONS[i:i + 4]
        print("    " + "  |  ".join(f"{i+j+1:2}. {v}" for j, v in enumerate(row)))

    while True:
        answer = input("\n  Enter the icon name exactly as shown\n  → ").strip()
        if answer in ALLOWED_ICONS:
            state = dict(state)
            state["nodeIcon"] = answer
            print(f" nodeIcon → '{answer}'")
            return state
        # Partial match convenience
        matches = [ic for ic in ALLOWED_ICONS if answer.lower() in ic.lower()]
        if len(matches) == 1:
            state = dict(state)
            state["nodeIcon"] = matches[0]
            print(f" nodeIcon → '{matches[0]}'  (matched from '{answer}')")
            return state
        if matches:
            print(f"  Ambiguous — matches: {', '.join(matches)}. Be more specific.")
        else:
            print(" No match. Enter the exact icon name from the list above.")


def _manual_fix_nodeColor(state: dict) -> dict:
    color = (state.get("nodeColor") or "").strip()
    if color:
        return state                                 

    print("\n  [nodeColor]  Node color is missing.")
    while True:
        answer = input(
            "  Enter a color  (e.g.  blue, #3B82F6, #FF5733)\n  → "
        ).strip()
        if answer:
            state = dict(state)
            state["nodeColor"] = answer
            print(f" nodeColor → '{answer}'")
            return state
        print("Color cannot be empty.")


def _manual_fix_nodeCategory(state: dict) -> dict:
    cat = (state.get("nodeCategory") or "").strip()
    if cat in ALLOWED_CATEGORIES:
        return state                               

    if not cat:
        print("\n  [nodeCategory]  Node category is missing.")
    else:
        print(f"\n  [nodeCategory]  '{cat}' is not a valid category.")

    print("  Allowed categories:")
    for i, c in enumerate(ALLOWED_CATEGORIES, 1):
        print(f"    {i}. {c}")

    while True:
        answer = input(
            "\n  Enter the category name or its number\n  → "
        ).strip()

        # Accept number
        if answer.isdigit() and 1 <= int(answer) <= len(ALLOWED_CATEGORIES):
            chosen = ALLOWED_CATEGORIES[int(answer) - 1]
            state  = dict(state)
            state["nodeCategory"] = chosen
            print(f" nodeCategory → '{chosen}'")
            return state

        # Exact match
        if answer in ALLOWED_CATEGORIES:
            state = dict(state)
            state["nodeCategory"] = answer
            print(f"nodeCategory → '{answer}'")
            return state

        # Partial match
        matches = [c for c in ALLOWED_CATEGORIES if answer.lower() in c.lower()]
        if len(matches) == 1:
            state = dict(state)
            state["nodeCategory"] = matches[0]
            print(f"nodeCategory → '{matches[0]}'  (matched from '{answer}')")
            return state
        if matches:
            print(f" Ambiguous — matches: {', '.join(matches)}. Be more specific.")
        else:
            print("Not recognised. Enter a number or the exact category name.")


def run_manual_fixes(state: dict) -> dict:
    """Run all four manual checks in sequence. Only prompts when a field needs fixing."""
    state = _manual_fix_nodeName(state)
    state = _manual_fix_nodeIcon(state)
    state = _manual_fix_nodeColor(state)
    state = _manual_fix_nodeCategory(state)
    return state


# ══════════════════════════════════════════════════════════════════════════
# PASS 2 — LLM-ASSISTED ISSUE DETECTION + FIX
#   nodeDescription  and  nodeProperty  only
# ══════════════════════════════════════════════════════════════════════════

class Issue:
    """
    One detected problem inside nodeDescription or nodeProperty.

    Attributes
    ----------
    field        : "nodeDescription"  or  "nodeProperty"
    problem      : human-readable description
    context      : property label (or "property index N")
    sub_field    : "label" | "type" | "options" | "option_name" |
                   "option_value" | "defaultValue" | "controlledBy"
    prop_index   : 0-based index in nodeProperty list  (-1 for nodeDescription)
    option_index : 0-based index of the bad option     (-1 if not option-level)
    """
    def __init__(
        self,
        field:        str,
        problem:      str,
        context:      str = "",
        sub_field:    str = "",
        prop_index:   int = -1,
        option_index: int = -1,
    ):
        self.field        = field
        self.problem      = problem
        self.context      = context
        self.sub_field    = sub_field
        self.prop_index   = prop_index
        self.option_index = option_index

    def __repr__(self):
        return (
            f"Issue(field={self.field!r}, sub={self.sub_field!r}, "
            f"ctx={self.context!r}, problem={self.problem!r})"
        )


def detect_llm_issues(state: dict) -> List[Issue]:
    """
    Scan nodeDescription and nodeProperty and return every Issue found.

    nodeDescription
    ───────────────
    • Must be present and non-empty.

    nodeProperty (per property)
    ────────────────────────────
    • label          : present, non-empty, unique across the list
    • type           : present, one of ALLOWED_PROP_TYPES
    • options        : required for dropdown / multi-select; must be a non-empty list
    • options[i].name  : non-empty
    • options[i].value : non-empty
    • options        : no duplicate values within the same property
    • defaultValue   : if set for dropdown/multi-select → must match an option value
    • controlledByAnotherProperty : every referenced label must exist in the list
    """
    issues: List[Issue] = []

    # ── nodeDescription ────────────────────────────────────────────────────
    if not (state.get("nodeDescription") or "").strip():
        issues.append(Issue(
            field="nodeDescription",
            problem="Node description is missing or empty",
        ))

    # ── nodeProperty ───────────────────────────────────────────────────────
    props: List[dict] = state.get("nodeProperty") or []

    # Build label list for cross-reference checks
    all_labels = [
        (p.get("label") or "").strip()
        for p in props
        if (p.get("label") or "").strip()
    ]

    # Duplicate label check
    seen_labels: Dict[str, int] = {}
    for i, lbl in enumerate(all_labels):
        if lbl in seen_labels:
            issues.append(Issue(
                field="nodeProperty",
                problem=f"Duplicate property label '{lbl}' — labels must be unique",
                context=lbl,
                sub_field="label",
                prop_index=i,
            ))
        else:
            seen_labels[lbl] = i

    # Per-property deep checks
    for i, prop in enumerate(props):
        label   = (prop.get("label") or "").strip()
        display = f"'{label}'" if label else f"property #{i + 1}"

        # label
        if not label:
            issues.append(Issue(
                field="nodeProperty",
                problem=f"Property #{i + 1} is missing a label",
                context=f"property index {i}",
                sub_field="label",
                prop_index=i,
            ))

        # type
        ptype = (prop.get("type") or "").strip()
        if not ptype:
            issues.append(Issue(
                field="nodeProperty",
                problem=f"Property {display} has no type set",
                context=label or f"property index {i}",
                sub_field="type",
                prop_index=i,
            ))
        elif ptype not in ALLOWED_PROP_TYPES:
            issues.append(Issue(
                field="nodeProperty",
                problem=(
                    f"Property {display} has invalid type '{ptype}'. "
                    f"Must be one of: {', '.join(ALLOWED_PROP_TYPES)}"
                ),
                context=label or f"property index {i}",
                sub_field="type",
                prop_index=i,
            ))

        # options (required for dropdown )
        if ptype in TYPES_REQUIRING_OPTIONS:
            raw_opts = prop.get("options")

            if not raw_opts:
                issues.append(Issue(
                    field="nodeProperty",
                    problem=(
                        f"Property {display} is type '{ptype}' but has no options. "
                        "At least one option with 'name' and 'value' is required."
                    ),
                    context=label or f"property index {i}",
                    sub_field="options",
                    prop_index=i,
                ))
            elif not isinstance(raw_opts, list):
                issues.append(Issue(
                    field="nodeProperty",
                    problem=f"Property {display} options must be a list, got {type(raw_opts).__name__}",
                    context=label or f"property index {i}",
                    sub_field="options",
                    prop_index=i,
                ))
            else:
                seen_opt_values: Dict[str, int] = {}

                for j, opt in enumerate(raw_opts):
                    opt_name  = (opt.get("name")  or "").strip() if isinstance(opt, dict) else ""
                    opt_value = (opt.get("value") or "").strip() if isinstance(opt, dict) else ""

                    if not opt_name:
                        issues.append(Issue(
                            field="nodeProperty",
                            problem=f"Property {display} — option #{j+1} is missing a 'name'",
                            context=label or f"property index {i}",
                            sub_field="option_name",
                            prop_index=i,
                            option_index=j,
                        ))

                    if not opt_value:
                        issues.append(Issue(
                            field="nodeProperty",
                            problem=(
                                f"Property {display} — option #{j+1} ('{opt_name}') "
                                "is missing a 'value'"
                            ),
                            context=label or f"property index {i}",
                            sub_field="option_value",
                            prop_index=i,
                            option_index=j,
                        ))

                    if opt_value:
                        if opt_value in seen_opt_values:
                            issues.append(Issue(
                                field="nodeProperty",
                                problem=(
                                    f"Property {display} has duplicate option value '{opt_value}' "
                                    f"(options #{seen_opt_values[opt_value]+1} and #{j+1})"
                                ),
                                context=label or f"property index {i}",
                                sub_field="options",
                                prop_index=i,
                                option_index=j,
                            ))
                        else:
                            seen_opt_values[opt_value] = j

                # defaultValue must match an existing option value
                default = (prop.get("defaultValue") or "").strip()
                if default and default not in seen_opt_values:
                    issues.append(Issue(
                        field="nodeProperty",
                        problem=(
                            f"Property {display} defaultValue '{default}' does not match "
                            f"any option value. Valid values: {', '.join(seen_opt_values.keys())}"
                        ),
                        context=label or f"property index {i}",
                        sub_field="defaultValue",
                        prop_index=i,
                    ))

        # controlledByAnotherProperty cross-reference
        controlled_by = prop.get("controlledByAnotherProperty")
        if controlled_by:
            if not isinstance(controlled_by, list):
                issues.append(Issue(
                    field="nodeProperty",
                    problem=(
                        f"Property {display} — controlledByAnotherProperty must be a list, "
                        f"got {type(controlled_by).__name__}"
                    ),
                    context=label or f"property index {i}",
                    sub_field="controlledBy",
                    prop_index=i,
                ))
            else:
                for ref in controlled_by:
                    if ref not in all_labels:
                        issues.append(Issue(
                            field="nodeProperty",
                            problem=(
                                f"Property {display} references '{ref}' in "
                                "controlledByAnotherProperty but no property with that label exists. "
                                f"Available labels: {', '.join(all_labels) or 'none'}"
                            ),
                            context=label or f"property index {i}",
                            sub_field="controlledBy",
                            prop_index=i,
                        ))

    return issues


# ── LLM prompts ────────────────────────────────────────────────────────────

CHECKER_QUESTION_PROMPT = """
                            You are a helpful assistant inside a node-builder tool.

                            The system detected a problem that needs the user's input.

                            Node context  : {context}
                            Field affected: {field}
                            Sub-field     : {sub_field}
                            Problem       : {problem}

                            Write a SHORT, friendly question (1-2 sentences) asking the user to provide
                            the correct value. If the field has a fixed set of allowed values, list them.
                            Do NOT start with "I". Start with the field name or a direct question word.
                            Return ONLY the question, nothing else.
                            """

CHECKER_PARSE_PROMPT = """
                        You are a strict value extractor for a node-builder tool.

                        Field      : {field}
                        Sub-field  : {sub_field}
                        Problem    : {problem}
                        Constraints: {constraints}
                        User answer: "{answer}"

                        Extract the valid value and return ONLY this JSON object:
                        {{"field": "{field}", "sub_field": "{sub_field}", "value": <extracted value>, "prop_index": {prop_index}, "option_index": {option_index}}}

                        Extraction rules:
                        - nodeDescription → cleaned description string
                        - label           → cleaned label string
                        - type            → exactly one of: text, number, text-area, dropdown, multi-select, checkbox, tag
                        - options         → JSON array: [{{"name": "...", "value": "..."}}]
                        - option_name     → plain string for the option name
                        - option_value    → plain string for the option value
                        - defaultValue    → plain string matching an existing option value
                        - controlledBy    → JSON array of label strings
                        - free text       → cleaned string

                        If the answer is unusable, return:
                        {{"field": null, "sub_field": null, "value": null, "prop_index": -1, "option_index": -1}}

                        Return ONLY the JSON object, no explanation.
                        """


def _build_node_context(state: dict) -> str:
    return (
        f"nodeName={state.get('nodeName') or '(unknown)'}, "
        f"nodeCategory={state.get('nodeCategory') or '(unknown)'}, "
        f"nodeDescription={state.get('nodeDescription') or '(unknown)'}"
    )


def _constraints_for_issue(issue: Issue) -> str:
    if issue.sub_field == "type":
        return f"Must be one of: {', '.join(ALLOWED_PROP_TYPES)}"
    if issue.sub_field in ("options", "option_name", "option_value"):
        return (
            'List of options. Each needs "name" (display label) and "value" (stored). '
            'Example: [{"name": "Yes", "value": "yes"}, {"name": "No", "value": "no"}]'
        )
    if issue.sub_field == "defaultValue":
        return "Must exactly match one of the existing option values."
    if issue.sub_field == "controlledBy":
        return "Must be a list of existing property label strings."
    if issue.field == "nodeDescription":
        return "A clear one-sentence description of what the node does."
    return "Free text — match the context of the node."


def _ask_and_parse_llm(issue: Issue, state: dict) -> Optional[Dict]:
    """LLM question → user input → LLM parse. Returns parsed dict or None."""
    # Generate question
    question = model.invoke([
        SystemMessage(content=CHECKER_QUESTION_PROMPT.format(
            context=_build_node_context(state),
            field=issue.field,
            sub_field=issue.sub_field or "—",
            problem=issue.problem,
        ))
    ]).content.strip()

    print(f"\n {question}")
    answer = input("  Your answer: ").strip()
    if not answer:
        return None

    # Parse answer
    raw = model.invoke([
        SystemMessage(content=CHECKER_PARSE_PROMPT.format(
            field=issue.field,
            sub_field=issue.sub_field or "",
            problem=issue.problem,
            constraints=_constraints_for_issue(issue),
            answer=answer,
            prop_index=issue.prop_index,
            option_index=issue.option_index,
        ))
    ]).content.strip()

    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    try:
        parsed = json.loads(raw)
        if parsed.get("field") and parsed.get("value") is not None:
            return parsed
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    return None


def _apply_parsed(state: dict, result: Dict, issue: Issue) -> dict:
    """Write the validated value into the correct location in state."""
    state     = dict(state)
    field     = result.get("field")
    sub_field = result.get("sub_field") or issue.sub_field
    value     = result.get("value")
    p_idx     = result.get("prop_index",   issue.prop_index)
    o_idx     = result.get("option_index", issue.option_index)

    # nodeDescription
    if field == "nodeDescription":
        state["nodeDescription"] = str(value).strip()
        return state

    # nodeProperty
    props = [dict(p) for p in (state.get("nodeProperty") or [])]

    def _find_prop(label: str, idx: int) -> Optional[int]:
        for k, p in enumerate(props):
            if p.get("label") == label:
                return k
        return idx if 0 <= idx < len(props) else None

    target_idx = _find_prop(issue.context, p_idx)
    if target_idx is None:
        return state

    prop = props[target_idx]

    if sub_field == "label":
        prop["label"] = str(value).strip()

    elif sub_field == "type":
        prop["type"] = str(value).strip()

    elif sub_field == "options":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = []
        prop["options"] = value if isinstance(value, list) else []

    elif sub_field == "option_name":
        opts = prop.get("options") or []
        if 0 <= o_idx < len(opts):
            opts[o_idx]["name"] = str(value).strip()
        prop["options"] = opts

    elif sub_field == "option_value":
        opts = prop.get("options") or []
        if 0 <= o_idx < len(opts):
            opts[o_idx]["value"] = str(value).strip()
        prop["options"] = opts

    elif sub_field == "defaultValue":
        prop["defaultValue"] = str(value).strip()

    elif sub_field == "controlledBy":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = [value]
        prop["controlledByAnotherProperty"] = value if isinstance(value, list) else [value]

    props[target_idx] = prop
    state["nodeProperty"] = props
    return state


def _print_property_summary(props: list) -> None:
    if not props:
        print("    (none)")
        return
    for i, p in enumerate(props, 1):
        default_info = f"  default={p['defaultValue']}" if p.get("defaultValue") else ""
        opts_info    = ""
        if p.get("options"):
            opt_vals  = ", ".join(o.get("value", "?") for o in p["options"])
            opts_info = f"  options=[{opt_vals}]"
        print(
            f"    {i}. {(p.get('label') or '(no label)'):<24}"
            f" [{p.get('type') or '?'}]{default_info}{opts_info}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════

def llm_field_checker(state: NodeState) -> NodeState:
    """
    LLM Field Checker node — two-pass validation.

    Pass 1  (manual)      →  nodeName, nodeIcon, nodeColor, nodeCategory
    Pass 2  (LLM-assisted) →  nodeDescription, nodeProperty
    """
    current = dict(state)

    # ── Pass 1: Manual fixes ──────────────────────────────────────────────
    print("\n  ── Pass 1: Checking nodeName / nodeIcon / nodeColor / nodeCategory ──")
    current = run_manual_fixes(current)
    print(" Top-level fields verified.\n")

    # ── Pass 2: LLM-assisted fixes ────────────────────────────────────────
    print("  ── Pass 2: Checking nodeDescription and nodeProperty (LLM) ──────")
    print("  Current nodeProperty:")
    _print_property_summary(current.get("nodeProperty") or [])
    print()

    issues = detect_llm_issues(current)

    if not issues:
        print(" nodeDescription and nodeProperty look correct. Proceeding.\n")
        return current

    total = len(issues)
    print(f" Found {total} issue(s) to resolve.\n")

    for idx, issue in enumerate(issues, 1):
        print(f"  ─── Issue [{idx}/{total}] ──────────────────────────────")
        print(f"  Field    : {issue.field}"
              + (f"  →  {issue.sub_field}" if issue.sub_field else ""))
        print(f"  Problem  : {issue.problem}")

        while True:
            result = _ask_and_parse_llm(issue, current)
            if result:
                current = _apply_parsed(current, result, issue)
                print(" Updated.\n")
                break
            else:
                print("Could not understand that answer — please try again.")

    print(" All issues resolved. Proceeding to human review.\n")
    print(" Updated nodeProperty:")
    _print_property_summary(current.get("nodeProperty") or [])
    print()
    return current