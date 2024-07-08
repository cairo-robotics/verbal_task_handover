import os
import logging
import sys

os.environ["OPENAI_API_KEY"] = "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"

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from llama_index.core import SimpleDirectoryReader, KnowledgeGraphIndex
from llama_index.core.graph_stores import SimpleGraphStore

from llama_index.llms.openai import OpenAI
from llama_index.core import Settings
# from IPython.display import Markdown, display

documents = SimpleDirectoryReader(
    "./data/ipass_handover_modified"
).load_data()

llm = OpenAI(temperature=0, model="gpt-3.5-turbo")
Settings.llm = llm
Settings.chunk_size = 512

from llama_index.core import StorageContext

graph_store = SimpleGraphStore()
storage_context = StorageContext.from_defaults(graph_store=graph_store)

index = KnowledgeGraphIndex.from_documents(
    documents,
    max_triplets_per_chunk=10,
    storage_context=storage_context
)

## create graph
from pyvis.network import Network

g = index.get_networkx_graph()
net = Network(notebook=True, cdn_resources="in_line", directed=True)
net.from_nx(g)
net.show("example.html")