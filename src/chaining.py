from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langgraph.graph import StateGraph
# from langgraph.graph.message import add_messages
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQAChain
from langchain.messages import HumanMessage, SystemMessage

from langchain import hub
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

import os
import networkx as nx
from typing import List, Dict, Any
from typing_extensions import TypedDict

FILE = "/home/kaleb/code/verbal_task_handover/llm_telemetry/saves/telemetry/telemetry_test.txt"


api_key = os.environ['OPENAI_API_KEY']

llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")
llm_transformer = LLMGraphTransformer(llm=llm)

class State(TypedDict):
    messages: List[Any]
    graph: nx.Graph

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

        self.state: State = {"messages": [], "graph": nx.Graph()}  # Initialize graph in state

    def initialize_chain(self):
        self.chain = RetrievalQAChain.from_retriever(
            retriever=lambda query: self.retrieve_from_graph_chain(self.state["graph"], query),
            prompt=self.prompt
        )

    def find_nodes_by_attribute(self, attr, value):
        nodes = [node for node, data in self.state["graph"].nodes(data=True) if data.get(attr) == value]
        return nodes

    def find_edges(self, node):
        return list(self.state["graph"].edges(node))

    def generate_graph_from_telemetry(self, filename: str):
        with open(filename, "r") as f:
            text = f.read()
        documents = [Document(page_content=text)]
        graph_documents = llm_transformer.convert_to_graph_documents(documents)
        self.state["graph"] = graph_documents[0]  # Store the graph in state
        return self.state["graph"]

    # Track the conversation history by storing questions and answers
    def add_to_conversation_history(self, question: str, answer: str):
        self.state["messages"].append({"question": question, "answer": answer})

    # Run the chain to generate an answer and update the conversation history
    def generate_answer(self, question: str):
        answer = self.chain.run(question=question)
        self.add_to_conversation_history(question, answer)  # Store Q&A in history
        return answer
    
    # Custom retriever that queries your NetworkX graph
    def retrieve_from_graph_chain(self, graph, query: str):
        context = self.retrieve_from_graph(graph, query)
        return {"context": context}

    # Example retrieval from the graph based on a query (modify as needed)
    def retrieve_from_graph(self, graph, query: str):
        # For now, we return node names as an example
        relevant_nodes = self.find_nodes_by_attribute("name", query)
        return ", ".join(relevant_nodes) if relevant_nodes else "No relevant nodes found."

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
# graph_builder.set_entrypip_point("chatbot")
# graph_builder.set_finish_point("chatbot")

# graph = graph_builder.compile()


if __name__ == "__main__":
    rag = HandoffRAG()
    rag.initialize_chain()
    rag.generate_graph_from_telemetry(FILE)

    # Ask a question and generate an answer
    question = "What rooms has the player visited?"
    answer = rag.generate_answer(question)
    print(f"Q: {question}\nA: {answer}")

