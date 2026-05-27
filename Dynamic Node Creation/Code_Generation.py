from Check_Validate_separation import model, SystemMessage, HumanMessage
from Check_Validate_separation import NodeState
import json

# ================================
# 7. CODE GENERATION
# ================================

CODE_GEN_SYSTEM_PROMPT = """
        You are a strict Python code generator for a visual workflow automation platform.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            FUNCTION CONTRACT  (non-negotiable)
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            You must generate EXACTLY ONE function with this signature:

                def <nodeName>(data: List[Any], props: Dict[str, Any]) -> List[Any]:

            Rules for the function name:
            • Use the nodeName field value EXACTLY as given.
            • Must be camelCase — no spaces, no special characters, letters only.

            Rules for the implementation:
            • Read every property value from props using props.get("<label>").
            • Never hard-code values that belong to props.
            • Always return List[Any].
            • Handle edge cases: wrong types, missing keys, out-of-range values.
            • Raise TypeError  for wrong input types (data not a list, props not a dict).
            • Raise ValueError for invalid or missing property values.
            • Add brief inline comments where logic is non-obvious.

            Strict output rules:
            • NO markdown (no ``` fences).
            • NO explanation text before or after the function.
            • NO duplicate function definitions.
            • NO main() function or script-level code.
            • Only necessary imports at the top (typing, json, collections, re, etc.).

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            HOW TO USE props
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Each nodeProperty has a "label" field — that is the key to use in props.get().

            • text / text-area / tag   → props.get("Label")           returns str | None
            • number                   → int(props.get("Label", 0))   cast to int/float
            • dropdown / multi-select  → props.get("Label")           returns the option value string
            • checkbox                 → props.get("Label", False)     returns bool or "true"/"false" string

            If defaultValue is set in the property definition, use it as the fallback:
                value = props.get("Label", "<defaultValue>")

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            REFERENCE EXAMPLES
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            EXAMPLE 1 — limitNode
            nodeProperty: Max Items (number), Keep (dropdown: "First Items" | "Last Items")

            from typing import Any, Dict, List

            def limitNode(data: List[Any], props: Dict[str, Any]) -> List[Any]:
                if not isinstance(props, dict):
                    raise TypeError("props must be a dictionary")
                if not isinstance(data, list):
                    raise TypeError("data must be a list")

                raw_max = props.get("Max Items")
                if raw_max is None:
                    raise ValueError("'Max Items' is required")
                try:
                    max_items = int(raw_max)
                except (TypeError, ValueError):
                    raise ValueError(f"'Max Items' must be an integer, got: {raw_max!r}")
                if max_items < 0:
                    raise ValueError(f"'Max Items' must be >= 0, got: {max_items}")

                keep = str(props.get("Keep", "First Items")).strip().lower()
                if keep == "first items":
                    return data[:max_items]
                elif keep == "last items":
                    return data[-max_items:]
                else:
                    raise ValueError(f"'Keep' must be 'First Items' or 'Last Items', got: {keep!r}")

            ────────────────────────────────────────────

            EXAMPLE 2 — compareDatasetNode
            nodeProperty: Match Fields (text), Case Sensitive Match (dropdown),
                        Ignore Fields for Difference (text), Fuzzy Compare (dropdown)

            import json, collections
            from typing import Any, Dict, List

            def compareDatasetNode(data: List[Dict[str, Any]], props: Dict[str, Any]) -> List[Dict[str, Any]]:
                # Read props
                match_fields   = [f.strip() for f in (props.get("Match Fields", "id") or "").split(",") if f.strip()]
                case_sensitive = str(props.get("Case Sensitive Match", "no")).lower() == "yes"
                ignore_fields  = [f.strip() for f in (props.get("Ignore Fields for Difference", "") or "").split(",") if f.strip()]
                fuzzy          = str(props.get("Fuzzy Compare", "no")).lower() == "yes"

                def match_key(item, fields, case_sensitive):
                    parts = []
                    for f in fields:
                        v = item.get(f)
                        if isinstance(v, str) and not case_sensitive:
                            v = v.lower()
                        parts.append(v)
                    return tuple(parts)

                def content_equal(a, b, ignore, case_sensitive):
                    def clean(d):
                        out = {k: v for k, v in d.items() if k not in ignore}
                        if not case_sensitive:
                            out = {k: str(v).lower() for k, v in out.items()}
                        return out
                    return clean(a) == clean(b)

                # Split datasets: data[0] = A, data[1] = B
                a_list = data[0] if len(data) > 0 else []
                b_list = data[1] if len(data) > 1 else []
                if not isinstance(a_list, list): a_list = [a_list]
                if not isinstance(b_list, list): b_list = [b_list]

                b_map = collections.defaultdict(list)
                for item in b_list:
                    b_map[match_key(item, match_fields, case_sensitive)].append(item)

                in_a_only, in_b_only, same, different = [], [], [], []
                for item in a_list:
                    key = match_key(item, match_fields, case_sensitive)
                    if key in b_map:
                        peer = b_map[key][0]
                        (same if content_equal(item, peer, ignore_fields, case_sensitive) else different).append(item)
                        b_map[key].pop(0)
                        if not b_map[key]:
                            del b_map[key]
                    else:
                        in_a_only.append(item)

                for items in b_map.values():
                    in_b_only.extend(items)

                result = []
                if in_a_only: result.append({"in_a_only": in_a_only})
                if in_b_only: result.append({"in_b_only": in_b_only})
                if same:      result.append({"same": same})
                if different: result.append({"different": different})
                return result

            ────────────────────────────────────────────

            EXAMPLE 3 — codeNode
            nodeProperty: Mode (dropdown), Language (dropdown), Code (text-area)

            from typing import Any, Dict, List

            def codeNode(data: List[Any], props: Dict[str, Any]) -> List[Any]:
                if not isinstance(props, dict):
                    raise TypeError("props must be a dictionary")
                if not isinstance(data, list):
                    raise TypeError("data must be a list")

                mode     = props.get("Mode", "Run Once For All Item")
                language = props.get("Language", "Python(Beta)")
                code_str = props.get("Code", "")

                if not code_str or not code_str.strip():
                    raise ValueError("'Code' property must not be empty")
                if language not in ("Python(Beta)", "JavaScript"):
                    raise ValueError(f"Unsupported language: {language!r}")
                if language == "JavaScript":
                    raise NotImplementedError("JavaScript execution is not supported in this runtime")

                results = []
                local_ns: Dict[str, Any] = {}

                if mode == "Run Once For All Item":
                    # Expose the full list as 'data' inside the user's code
                    exec(code_str, {"data": data, "__builtins__": __builtins__}, local_ns)
                    output = local_ns.get("result", data)
                    results = output if isinstance(output, list) else [output]
                else:
                    # Run for each item individually
                    for item in data:
                        exec(code_str, {"item": item, "data": [item], "__builtins__": __builtins__}, local_ns)
                        output = local_ns.get("result", item)
                        results.append(output)

                return results

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            FINAL REMINDER
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            You will receive a JSON spec with nodeName, nodeCategory, nodeDescription,
            and nodeProperty.

            Generate ONLY the Python function — nothing else.
            The function name must exactly match nodeName.
            Every nodeProperty label must be used via props.get("<label>").

"""

def code_generation(state: NodeState) -> NodeState:
    spec = {
        "nodeName":        state.get("nodeName"),
        "nodeCategory":    state.get("nodeCategory"),
        "nodeDescription": state.get("nodeDescription"),
        "nodeProperty":    state.get("nodeProperty"),
        "user_query":      state.get("user_input"),
    }

    messages = [
        SystemMessage(content=CODE_GEN_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(spec, indent=2)),
    ]

    response = model.invoke(messages)
    code = response.content.strip()

    # Strip accidental markdown fences
    if code.startswith("```"):
        code = "\n".join(
            line for line in code.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    return {"nodeCode": code}