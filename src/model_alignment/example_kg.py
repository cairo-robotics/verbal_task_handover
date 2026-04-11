from pydantic_schema import *

example_kg = KnowledgeGraph(
    facts=[
        LocationFact(
            entity=Argument(
                type="named",
                value="lily"
            ),
            location=Location(
                type="directional",
                directions=[Direction.WEST, Direction.NORTH],
                mode="path"
            ),
            is_partial=False,
            provenance="lily is to the west then north"
        ),

        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(
                type="existential",
                value=None,
                location=Location(
                    type="directional",
                    directions=[Direction.EAST],
                    mode="path"  # single direction → path is fine
                )
            ),
            object=Argument(
                type="named",
                value="red potion"
            ),
            is_partial=True,
            provenance="someone to the east needs a red potion"
        ),

        RelationFact(
            predicate=RelationPredicate.HAS_MESSAGE_FOR,
            subject=Argument(
                type="existential",
                location=Location(
                    type="directional",
                    directions=[Direction.WEST],
                    mode="path"
                )
            ),
            target=Argument(
                type="existential"
            ),
            is_partial=True,
            provenance="someone to the west has a message for someone"
        )
    ],
)