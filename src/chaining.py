from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
# from langgraph.graph import StateGraph
# from langgraph.graph.message import add_messages
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQAChain
from langchain.messages import HumanMessage, SystemMessage

import os
import networkx as nx
from typing import List, Dict, Any
from typing_extensions import TypedDict


api_key = os.environ['OPENAI_API_KEY']

llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")
llm_transformer = LLMGraphTransformer(llm=llm)

prompt_template = """Use the following knowledge to answer the question:
{context}

Question: {question}
Answer:"""

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=prompt_template
)

text = """
2024-09-03 14:43:04 - Room entered: room2
2024-09-03 14:43:05 - Item obtained: ['key0']
2024-09-03 14:43:07 - Room entered: room0
2024-09-03 14:43:08 - Door unlocked: door_to_room1 using key0
2024-09-03 14:43:08 - Room entered: room1
2024-09-03 14:43:09 - NPC interact: mark
2024-09-03 14:43:09 - Item obtained: key1
2024-09-03 14:43:10 - Room entered: room0
"""
documents = [Document(page_content=text)]
graph_documents = llm_transformer.convert_to_graph_documents(documents)
print(f"Nodes:{graph_documents[0].nodes}")
print(f"Relationships:{graph_documents[0].relationships}")


class State(TypedDict):
    messages: List[Any]
    graph: Dict[str, Any]

def find_nodes_by_attribute(graph, attr, value):
    nodes = [node for node, data in graph.nodes(data=True) if data.get(attr) == value]
    return nodes

def find_edges(graph, node):
    return list(graph.edges(node))


class HandoffRAG:
    def __init__(self):
        prompt_template = """Use the following knowledge to answer the question:
        {context}

        Question: {question}
        Answer:"""

        self.prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=prompt_template
        )
        
        self.chain = RetrievalQAChain.from_retriever(
            retriever=lambda query: self.retrieve_from_graph_chain(graph, query),
            prompt=prompt
        )

        # self.graph_builder = StateGraph(State)

    # Run the chain to generate an answer
    def generate_answer(self, question: str):
        return self.chain.run(question=question)
    
    # Custom retriever that queries your NetworkX graph
    def retrieve_from_graph_chain(self, graph, query: str):
        context = self.retrieve_from_graph(graph, query)
        return {"context": context}
    


# def chatbot(state: State):
#     human_message = next(human for human in state["messages"] if isinstance(human, HumanMessage))
#     system_message = next(system for system in state["messages"] if isinstance(system, SystemMessage))
    
#     if human_message.text.strip() == "/update":
#         state = update_graph(state, human_message.text)
#     else:
#         answer = get_answer(state, human_message.text)
#         state["messages"].append(HumanMessage(answer))
    
#     return {"messages": state["messages"]}

# # Add the chatbot node to the graph builder
# graph_builder.add_node("chatbot", chatbot)
# graph_builder.set_entry_point("chatbot")
# graph_builder.set_finish_point("chatbot")

# graph = graph_builder.compile()
