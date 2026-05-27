from Check_Validate_separation import EDITABLE_FIELDS, NodeState

# ================================
# 4. HELPERS
# ================================
def _input_options():
    options = []

    print("\n  Enter options (name + value)")
    print("  Type 'done' when finished\n")

    while True:
        name = input("    Option name: ").strip()
        if name.lower() == "done":
            break

        value = input("    Option value: ").strip()

        if not name or not value:
            print(" Both name and value required.")
            continue

        options.append({"name": name, "value": value})

    return options or None

def build_preview(state: dict) -> str:
    """Return a formatted preview of all current field values."""
    lines = [
        "",
        "=" * 62,
        "  NODE PREVIEW",
        "=" * 62,
        f"  {'nodeName':<18}: {state.get('nodeName')}",
        f"  {'nodeIcon':<18}: {state.get('nodeIcon')}",
        f"  {'nodeColor':<18}: {state.get('nodeColor')}",
        f"  {'nodeCategory':<18}: {state.get('nodeCategory')}",
        f"  {'nodeDescription':<18}: {state.get('nodeDescription')}",
        f"  {'nodeProperty':<18}:",
    ]
    for prop in state.get("nodeProperty") or []:
        default_str = f"  (default: {prop['defaultValue']})" if prop.get("defaultValue") else ""
        lines.append(f"      • {prop['label']} [{prop['type']}]{default_str}")
    lines.append("=" * 62)
    return "\n".join(lines)


def apply_field_edit(state: dict, field: str, new_value: str) -> dict:
    """Return an updated copy of state with one simple field changed.
    nodeProperty is handled separately via edit_node_properties()."""
    state = dict(state)
    state[field] = new_value.strip()
    return state


# ── nodeProperty type options (shown as a numbered menu) ──────────────────
PROPERTY_TYPES = ["text", "number", "text-area", "dropdown", "multi-select", "checkbox", "tag"]


def _pick_type() -> str:
    """Show a numbered type menu and return the chosen type string."""
    print("\n  Property types:")
    for i, t in enumerate(PROPERTY_TYPES, 1):
        print(f"    {i}. {t}")
    while True:
        choice = input("\n  Enter number (1-7): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(PROPERTY_TYPES):
            return PROPERTY_TYPES[int(choice) - 1]
        print("   Invalid choice. Enter a number between 1 and 7.")


def _show_properties(props: list) -> None:
    """Print the current property list as a numbered table."""
    if not props:
        print("\n  (no properties yet)")
        return
    print()
    for i, p in enumerate(props, 1):
        default_str = f"  default={p['defaultValue']}" if p.get("defaultValue") else ""
        placeholder_str = f"  placeholder={p['placeholder']}" if p.get("placeholder") else ""
        print(f"  {i}. {p['label']:<22} [{p['type']}]{default_str}{placeholder_str}")
        options_str = ""
        if p.get("options"):
            options_str = f"  options={len(p['options'])}"
        print(f"  {i}. {p['label']:<22} [{p['type']}]{default_str}{placeholder_str}{options_str}")


def edit_node_properties(current_props: list) -> list:
    """
    Interactive guided editor for nodeProperty.
    Supports: add / edit / delete / done — no JSON required from the user.
    Returns the updated list.
    """
    props = [dict(p) for p in (current_props or [])]   # work on a copy

    while True:
        _show_properties(props)
        print("\n  What would you like to do?")
        print("    a  →  Add a new property")
        print("    e  →  Edit an existing property")
        print("    d  →  Delete a property")
        print("    done  →  Finish editing properties")
        action = input("\n  Your choice: ").strip().lower()

        # ── ADD ──────────────────────────────────────────────────────────
        if action == "a":
            label = input("\n  Property label (name): ").strip()
            if not label:
                print(" Label cannot be empty.")
                continue
            ptype    = _pick_type()
            default  = input("  Default value  (press Enter to skip): ").strip() or None
            holder   = input("  Placeholder    (press Enter to skip): ").strip() or None
            options = None
            if ptype in ["dropdown",]:
                options = _input_options()

            props.append({
                "label": label,
                "type": ptype,
                "defaultValue": default,
                "placeholder": holder,
                "options": options,
                "controlledByAnotherProperty": None,
            })
            print(f" '{label}' added.")
            _show_properties(props)
        # ── EDIT ─────────────────────────────────────────────────────────
        elif action == "e":
            if not props:
                print("  No properties to edit.")
                continue
            idx = input("\n  Enter property number to edit: ").strip()
            if not idx.isdigit() or not (1 <= int(idx) <= len(props)):
                print(" Invalid number.")
                continue
            prop = props[int(idx) - 1]
            print(f"\n  Editing: {prop['label']}  [{prop['type']}]")
            print("  Which sub-field?")
            print("    1. label")
            print("    2. type")
            print("    3. defaultValue")
            print("    4. placeholder")
            print("    5. options")
            sub = input("\n  Enter number (1-4): ").strip()
            if sub == "1":
                new_label = input(f"  Current label: {prop['label']}\n  New label: ").strip()
                if new_label:
                    prop["label"] = new_label
            elif sub == "2":
                prop["type"] = _pick_type()
            elif sub == "3":
                new_default = input(f"  Current default: {prop.get('defaultValue')}\n  New default (Enter to clear): ").strip()
                prop["defaultValue"] = new_default or None
            elif sub == "4":
                new_holder = input(f"  Current placeholder: {prop.get('placeholder')}\n  New placeholder (Enter to clear): ").strip()
                prop["placeholder"] = new_holder or None
            elif sub == "5":
                if prop["type"] not in ["dropdown",]:
                    print(" Options only valid for dropdown or multi-select.")
                    continue

                prop["options"] = _input_options()
            else:
                print(" Invalid choice.")
                continue
            print(f"  Property updated.")
            _show_properties(props)
        # ── DELETE ────────────────────────────────────────────────────────
        elif action == "d":
            if not props:
                print("   No properties to delete.")
                continue
            idx = input("\n  Enter property number to delete: ").strip()
            if not idx.isdigit() or not (1 <= int(idx) <= len(props)):
                print("  Invalid number.")
                continue
            removed = props.pop(int(idx) - 1)
            print(f" '{removed['label']}' deleted.")
            _show_properties(props)

        # ── DONE ─────────────────────────────────────────────────────────
        elif action == "done":
            return props

        else:
            print("  Type  a  e  d  or  done.")
        _show_properties(props)

# ================================
# 6. HUMAN IN THE LOOP
# ================================

def human_in_the_loop(state: NodeState) -> NodeState:

    # ── Step A: show initial preview ──────────────────────────────────────
    print(build_preview(state))
    answer = input("\n  Do you want to proceed?\n  Type  yes  to continue  |  no  to edit fields\n\n  Your answer: ").strip().lower()

    if answer == "yes":
        return {"approved": True}

    # ── Edit loop ─────────────────────────────────────────────────────────
    current = dict(state)

    while True:

        # Step B: which field?
        field_menu = "\n".join(
            f"    {k:<22}  →  {v}" for k, v in EDITABLE_FIELDS.items()
        )
        chosen_field = input(
            "\n  Which field would you like to change?\n\n"
            + field_menu
            + "\n\n  Enter the field name exactly: "
        ).strip()

        if chosen_field not in EDITABLE_FIELDS:
            print(f"\n  '{chosen_field}' is not a valid field name. Please choose from the list above.")
            continue

        # Step C: enter new value
        if chosen_field == "nodeProperty":
            # ── Guided property editor (no JSON needed) ───────────────────
            print("\n  Opening property editor …")
            current["nodeProperty"] = edit_node_properties(current.get("nodeProperty") or [])
        else:
            # ── Simple single-line edit ───────────────────────────────────
            current_display = str(current.get(chosen_field, ""))
            new_value = input(
                f"\n  Field    : {chosen_field}  ({EDITABLE_FIELDS[chosen_field]})"
                f"\n  Current  : {current_display}"
                "\n\n  New value: "
            ).strip()
            current = apply_field_edit(current, chosen_field, new_value)

        # Step D: show updated preview and confirm
        print("\n  Field updated. Revised preview:")
        print(build_preview(current))
        confirm = input(
            "\n  Go ahead?"
            "\n  Type  yes  to proceed to code generation  |  no  to edit more\n"
            "\n  Your answer: "
        ).strip().lower()

        if confirm == "yes":
            current["approved"] = True
            return current

        # "no" → loop back to Step B


# ================================
# CONDITIONAL FUNCTION FOR HUMAN-IN-THE-LOOP NODE
# ================================

def Conditional_function(state: NodeState) -> str:
    if state.get("approved"):
        return "code_generation"
    return "human_in_the_loop"