from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated
from langchain_core.messages import SystemMessage, HumanMessage
import uuid
import re

print("Sita Ram")

# ================================
# 1. LOAD ENV + MODEL
# ================================
load_dotenv()

model = ChatOpenAI(model="gpt-4o-mini",
                    timeout=60,          
                    max_retries=3,
                    temperature=2,
                    verbose=False)

# ================================
#  2. STATE
# ================================

class NodeState(TypedDict, total=False):
    user_input: str
    ikonStudioNodeId: str
    nodeName: str
    nodeCategory: str
    nodeDescription: str
    nodeType: str
    nodeIcon: str
    nodeColor: str
    nodeProperty: List[Dict[str, Any]]
    nodeCode: str
    createdAt: str   
    updatedAt: str
    parsed_output: Dict[str, Any]
    error: str


# ================================
#  3. PYDANTIC MODEL
# ================================

class PropertyOption(BaseModel):
    id: Optional[str] = None
    label: str
    value: str

class NodeProperty(BaseModel):
    name: str
    type: str  
    defaultValue: Optional[str] = None
    value: Optional[str] = None
    controlledBy: Optional[bool] = False
    controllerPropertyName: Optional[str] = None
    controllerPropertyValue: Optional[str] = None
    options: List[PropertyOption] = []
    placeHolder: Optional[str] = None
    id: Optional[str] = None

# class MongoDate(BaseModel):
#     date: str = Field(alias="$date")


IdType = Annotated[
    str,
    Field(default_factory=lambda: f"NODE_FUNC_{uuid.uuid4()}")
]

NonEmptyStr = Annotated[str, Field(min_length=1)]
OptionalStr = Annotated[Optional[str], Field(default="")]
ColorStr = Annotated[str, Field(default="black")]


class NodeEntityModel(BaseModel):
    ikonStudioNodeId: IdType = Field(default_factory=lambda: f"NODE_FUNC_{uuid.uuid4()}")
    nodeName: OptionalStr
    nodeCategory: OptionalStr
    nodeDescription: OptionalStr
    nodeType: OptionalStr
    nodeIcon: OptionalStr
    nodeColor: ColorStr
    nodeProperty: List[NodeProperty] = []
    nodeCode: Optional[str] = None
    createdAt: str
    updatedAt: str

    class_name: str = Field(
        default="com.ikon.ikonstudio.dataservice.entity.NodeEntity",
        alias="_class"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore", 
        validate_assignment=True
    )


model_with_structured_output = model.with_structured_output(NodeEntityModel)


# ================================
#  4. NODE 1: CONTEXT SEPARATION
# ================================
def safe_llm_call(messages):
    for i in range(3):
        try:
            return model_with_structured_output.invoke(messages)
        except Exception as e:
            print(f"Retry {i+1} failed:", e)
    raise Exception("LLM failed after retries")

def context_separation(state: NodeState) -> NodeState:
    try:
        user_input = state.get("user_input", "")

        compact_system_message = """
        You are an expert that converts a user prompt into one strict JSON object matching NodeEntity schema.

        Rules:
        - Output ONLY valid JSON (no markdown/no text/explanations)
        - Always include keys: ikonStudioNodeId,nodeName,nodeCategory,nodeDescription,nodeType,nodeIcon,nodeColor,nodeProperty,nodeCode,createdAt,updatedAt
        - If value is missing: set null (except when defaults are specified)
        - nodeCategory must be UPPER_CASE_WITH_UNDERSCORES
        - nodeColor default is "black"
        - ikonStudioNodeId must be "NODE_FUNC_<uuid>" if missing
        - nodeCode must be null
        - createdAt and updatedAt must be ISO8601 timestamps (generate now if missing)

        nodeProperty items:
        - object must include: name,type,defaultValue,value,controlledBy,controllerPropertyName,controllerPropertyValue,options,placeHolder,id
        - type: "text" or "dropdown"
        - text -> options=[]
        - dropdown -> options array of {id,label,value}
        - controlledBy false unless dependency present

        Field mapping:
        - "Node Name" -> nodeName
        - "Category" -> nodeCategory
        - "Description" -> nodeDescription
        - "Type" -> nodeType
        - "Icon" -> nodeIcon

        Do not hallucinate extra fields. Do not omit keys.
        """

        messages = [
            SystemMessage(content=compact_system_message),
            HumanMessage(content=user_input)
        ]

        parsed = safe_llm_call(messages)

        return {
            **state,
            **parsed.model_dump(),
            "createdAt": parsed.createdAt,
            "updatedAt": parsed.updatedAt
        }

    except Exception as e:
        return {**state, "error": str(e)}


# ================================
#  5. HITL HELPERS
# ================================
def get_missing_fields(state: NodeState) -> List[str]:

    def is_missing(v):
       return v is None or str(v).strip().lower() in ["", "null", "none"]
     
    required = [
        "nodeName",
        "nodeCategory",
        "nodeType",
        "nodeIcon",
        "nodeDescription"
    ]
    return [f for f in required if is_missing(state.get(f))]


# ================================
#  6. NODE 2: HUMAN-IN-THE-LOOP
# ================================
def human_in_the_loop(state: NodeState) -> NodeState:
    try:
        def is_missing(value):
            return value is None or str(value).strip().lower() in ["", "null", "none"]

        required = [
            "nodeName",
            "nodeCategory",
            "nodeType",
            "nodeIcon",
            "nodeDescription"
        ]

        missing = [f for f in required if is_missing(state.get(f))]

        if not missing:
            return state

        print("\n Missing fields:", missing)

        updated = {**state}
        user_text = state.get("user_input", "")

        import re

        patterns = {
            "nodeName": r"node name[:\-]?\s*\n?\s*(\w+)",
            "nodeCategory": r"category[:\-]?\s*\n?\s*([A-Za-z ]+)",
            "nodeDescription": r"description[:\-]?\s*\n?\s*(.+)"
        }

        for field in missing:
            pattern = patterns.get(field)
            match = re.search(pattern, user_text, re.IGNORECASE) if pattern else None

            if match and match.lastindex:
                value = match.group(1).strip()
                print(f" Auto-filled {field}: {value}")
            else:
                value = input(f"Enter value for {field}: ")

            if not value.strip():
                value = input(f"Enter value for {field}: ")

            if field == "nodeCategory":
                value = value.upper().replace(" ", "_")

            updated[field] = value
        
        if not updated.get("nodeType"):
            updated["nodeType"] = "functionalNode"

        if not updated.get("nodeIcon"):
            updated["nodeIcon"] = "settings"

        return updated

    except Exception as e:
        return {**state, "error": str(e)}
    
# ================================
#  7. NODE 3: CODE GENERATION
# ================================
def code_generation(state: NodeState) -> NodeState:
    try:
        description = state.get("nodeDescription", "")
        node_name = state.get("nodeName", "generatedNode")

        if not description:
            return {**state, "error": "Missing description"}

        messages = [
            SystemMessage(
                content=f"""
                    You are a strict Python code generator.

                    Generate EXACTLY one function.

                    FUNCTION NAME: {node_name}

                    SIGNATURE:
                    def {node_name}(data: List[Dict[str, Any]], props: Dict[str, Any]) -> List[Any]:

                    Rules:
                    - ONLY code
                    - NO markdown
                    - NO explanation
                    - NO duplicate functions
                    - MUST follow signature exactly
                    - MUST return List[Any]
                    """
            ),
            HumanMessage(content=description)
        ]

        response = model.invoke(messages)

        code = re.sub(r"```python|```", "", response.content).strip()

        return {**state, "nodeCode": code}

    except Exception as e:
        return {**state, "error": str(e)}

# ================================
# 8. GRAPH
# ================================
graph = StateGraph(NodeState)

graph.add_node("separation", context_separation)
graph.add_node("human_in_the_loop", human_in_the_loop)
graph.add_node("code_generation", code_generation)

graph.add_edge(START, "separation")
graph.add_edge("separation", "human_in_the_loop")
graph.add_edge("human_in_the_loop", "code_generation")
graph.add_edge("code_generation", END)

workflow = graph.compile()

# ================================
# 9. RUN
# ================================
initial_state = {
    "user_input": """
        Create a node with the following details:

        Name: Aggregate_Node     
        Category:
        Data Manipulation

        Description:
        This node aggregates multiple input items into a single output.

        Functional Requirement:
        - Combine data from multiple items
        - Support two modes:
        1. Aggregate individual fields
        2. Merge all item data into one list

        Input:
        List of JSON objects

        Output:
        Aggregated data

        Node Properties:

        1. Aggregate
        - type: dropdown
        - options:
                - Individual Fields
                - All Item Data(Into a Single List)
        - defaultValue: "Individual Fields"

        2. Input Field Name
        - type: text
        - used when Aggregate = Individual Fields

        3. Put Output in Field
        - type: text
        - used when Aggregate = All Item Data

        Rules:
        - Use controlledBy when dependency exists
        - Fields should dynamically depend on Aggregate selection

        Goal:
        Generate structured node with conditional properties.
        """
}

# initial_state = {
#     "user_input": """
#         Create a node for processing some data.

            
#         Description:
#         It should combine things and maybe filter depending on some condition.
#         Not sure exactly how, but it should work on lists.

#         Functional Requirement:
#         - Combine data
#         - Maybe filter
#         - Sometimes return only specific fields

#         Input:
#         Some list

#         Output:
#         Some processed result

#         Node Properties:
#         1. Mode
#         - type: dropdown
#         - options:
#             - Option A
#             - Option B

#         2. Field Name
#         - type: text

#         Notes:
#         - Behavior depends on mode
#         - Not fully defined

#         Goal:
#         Create something flexible.
#     """
# }
# initial_state = {
#     "user_input": """
#         Create a node.
#     """
# }
final_state = workflow.invoke(initial_state)

# ================================
# 10. OUTPUT
# ================================
print("\n FINAL RESULT:\n")
print("Name:", final_state.get("nodeName"))
print("Category:", final_state.get("nodeCategory"))
print("Type:", final_state.get("nodeType"))
print("Icon:", final_state.get("nodeIcon"))
print("Description:", final_state.get("nodeDescription"))
print("\nGenerated Code:\n")
print(final_state.get("nodeCode"))