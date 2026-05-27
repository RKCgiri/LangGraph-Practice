from langgraph.graph import StateGraph, START, END
from Separation_Of_Context import field_separator, llm_field_checker
from Check_Validate_separation import NodeState
from Separation_Of_Context import field_separator, llm_field_checker
from Human_In_The_Loop import human_in_the_loop, Conditional_function, build_preview, apply_field_edit, edit_node_properties
from Code_Generation import code_generation
print("Sita Ram")
# ================================
# 8. GRAPH ASSEMBLY
# ================================

graph = StateGraph(NodeState)

graph.add_node("separation",        field_separator)
graph.add_node("llm_field_checker", llm_field_checker)
graph.add_node("human_in_the_loop", human_in_the_loop)
graph.add_node("code_generation",   code_generation)

graph.add_edge(START, "separation")
graph.add_edge("separation",       "llm_field_checker")
graph.add_edge("llm_field_checker","human_in_the_loop")


graph.add_conditional_edges(
    "human_in_the_loop",
    Conditional_function,
    {
        "human_in_the_loop": "human_in_the_loop",
        "code_generation":   "code_generation",
    }
)

graph.add_edge("code_generation", END)

workflow = graph.compile()


# ================================
# 9. RUNNER
# ================================

def run_interactive(user_query: str) -> NodeState:
    """Drive the workflow from the terminal."""
    print("\n Starting workflow …\n")
    result = workflow.invoke({"user_input": user_query})
    return result


# ================================
# 10. ENTRYPOINT
# ================================

if __name__ == "__main__":

    user_query = ("""  Limit a list of data based on the 'Max Items' and 'Keep' properties found in the props dictionary.

    Args:
        data (List[Any]): 
            The input list of items that needs to be limited.
        
        props (Dict[str, Any]): 
            A dictionary containing properties. It will always be a dictionary, 
            but may include nested lists or dictionaries. The function looks for:
            
            - "Max Items": An integer (as value or string) specifying the maximum number 
              of items to keep from `data`.
            - "Keep": A string indicating which items to keep, 
              must be either "First Items" or "Last Items" (case-insensitive).

    Returns:
        List[Any]: 
            A limited version of the input `data` list, either from the beginning or 
            the end, depending on the "Keep" value.

    Raises:
        TypeError: 
            - If `props` is not a dictionary.
            - If `data` is not a list.
        
        ValueError: 
            - If "Max Items" is missing, not an integer, or less than zero.
            - If "Keep" is provided but not one of "First Items" or "Last Items".    """)

    final_state = run_interactive(user_query)

    print("\nCode generation complete. Final node state:\n")
    print(final_state["nodeCode"])