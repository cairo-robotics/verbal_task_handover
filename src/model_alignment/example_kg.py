from pydantic_schema import *

example_kg = KnowledgeGraph(
    source="telemetry",
    locations=[],
    holdings=[],
    tasks=[Task(task_id="task_lily_potion", # "lily needs a gold potion"
                        initiator=Argument(type="entity", value="lily"),
                        status="pending", status_confidence="inferred", 
                        condition_type="item_delivery", 
                        condition_value=Argument(type="entity", value="gold_potion"), 
                        target=Argument(type="entity", value="lily"), target_confidence="inferred"),
            Task(task_id="task_steve_john", # "steve has a message for john"
                        initiator=Argument(type="entity", value="steve"),
                        status="pending", status_confidence="inferred", 
                        condition_type="item_delivery", 
                        condition_value=Argument(type="entity", value="message_from_steve"), 
                        target=Argument(type="entity", value="john"), target_confidence="inferred"),
            
            ],
    conflicts=[]
)