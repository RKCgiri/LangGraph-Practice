from typing import TypedDict, List, Dict, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Model setup
model = ChatOpenAI(
    model="gpt-4o",
    timeout=60,
    max_retries=3,
    temperature=0.3,
    verbose=False
)

# ================================
# 2. STATE
# ================================

class NodeState(TypedDict, total=False):
    user_input:      str
    nodeName:        str
    nodeIcon:        str
    nodeColor:       str
    nodeCategory:    str
    nodeDescription: str
    nodeProperty:    List[Dict]
    nodeCode:        str
    approved:        bool


# ================================
# 3. PYDANTIC MODEL
# ================================
class Option(BaseModel):
    name: str
    value: str

class NodeProperty(BaseModel):
    label:       str = Field(..., description="Label of the property")
    type:        Literal[
                     "text",
                     "number",
                     "text-area",
                     "dropdown",
                     "multi-select",
                     "checkbox",
                     "tag"
                 ] = Field(..., description="Type of the property")
    defaultValue:  Optional[str]       = Field(None, description="Default value")
    placeholder:   Optional[str]       = Field(None, description="Placeholder text")

    options: Optional[List[Option]] = Field(
        None,
        description="Options for dropdown or multi-select"
    )
    controlledByAnotherProperty: Optional[List[str]] = Field(
        None,
        description="Name of the property that controls the visibility of this property."
    )
    @model_validator(mode="after")
    def validate_options(self):
        if self.type in ["dropdown",] and not self.options:
            raise ValueError("Options required for dropdown/multi-select")
        return self

class NodeModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True,
    )
    nodeName:        Optional[str] = Field(None, description="Name of the node")
    nodeIcon:        Optional[Literal[
                         "mouse-pointer", "clock", "webhook", "file-input",
                         "file-output", "notebook-pen", "file-archive", "globe",
                         "message-circle", "notepad-text", "aperture",
                         "message-square", "bot", "notepad-text-dashed",
                         "file-pen-line", "terminal", "table-columns-split",
                         "handshake", "merge", "shield-x", "pause",
                         "copy-minus", "funnel", "key-round"
                     ]] = Field(None, description="Allowed node icons")
    nodeColor:       Optional[str] = Field(None, description="Color for the node")
    nodeCategory:    Optional[Literal[
                         "Trigger",
                         "Data Manipulation",
                         "Flow Manipulation",
                         "Flow Control",
                         "Core",
                         "Database nodes",
                         "AI/ML"
                     ]] = Field(None, description="Allowed node categories")
    nodeDescription: Optional[str]                = Field(None, description="Description of the node")
    nodeProperty:    Optional[List[NodeProperty]] = Field(
        default_factory=list,
        description="Properties of the node"
    )
    nodeCode:        Optional[str] = Field(None, description="Python code for the node's functionality")


EDITABLE_FIELDS: Dict[str, str] = {
    "nodeName":        "Node Name",
    "nodeIcon":        "Node Icon",
    "nodeColor":       "Node Color (hex)",
    "nodeCategory":    "Node Category",
    "nodeDescription": "Node Description",
    "nodeProperty":    "Node Properties",
}

model_with_structured_output = model.with_structured_output(NodeModel)

# ================================
# VALIDATION AND CHECK FUNCTIONS
# ================================

# This file contains validation and checking utilities for the node generator

def validate_node_state(state: dict) -> bool:
    """Basic validation of the node state."""
    required_fields = ["nodeName", "nodeIcon", "nodeColor", "nodeCategory", "nodeDescription"]
    for field in required_fields:
        if not state.get(field):
            return False
    return True

def check_property_consistency(props: list) -> list:
    """Check for consistency in node properties."""
    issues = []
    for i, prop in enumerate(props):
        if prop.get("type") in ["dropdown", "multi-select"] and not prop.get("options"):
            issues.append(f"Property {i}: {prop.get('label')} missing options")
    return issues

def sanitize_input(input_str: str) -> str:
    """Sanitize user input."""
    return input_str.strip() if input_str else ""
