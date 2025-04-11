from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

import os

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]

def get_graph():
    graph_builder = StateGraph(State)

    # Create a Chatbot node
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model='claude-3-5-haiku-20241022',
                        temperature=os.getenv("LLM_TEMPERATURE"))


    def chatbot(state: State):
        return {"messages": [llm.invoke(state["messages"])]}


    # The first argument is the unique node name
    # The second argument is the function or object that will be called whenever
    # the node is used.
    graph_builder.add_node("chatbot", chatbot)

    # Add START and END edges
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)

    graph = graph_builder.compile()
    
    return graph