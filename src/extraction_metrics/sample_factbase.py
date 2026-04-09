from state_ontology import *

factbase = FactExtraction(
    facts=[
        CanonicalFact( # "room 1 needs the gold potion"
            predicate="needs",
            agent=Argument(
                type="existential",
                value="someone",
                location=Location(
                    type="room",
                    value="room_1",
                )
            ),
            object=Argument(
                type="entity",
                value="gold potion"
            )
        ),
        CanonicalFact( # "guy is in room 5"
            predicate="located",
            agent=Argument(
                type="entity",
                value="guy",
                location=Location(
                    type="room",
                    value="room_5",
                )
            )
        ),
        CanonicalFact( # "room 5 needs a potion"
            predicate="needs",
            agent=Argument(
                type="existential",
                value="someone",
                location=Location(
                    type="room",
                    value="room_5",
                )
            ),
            object=Argument(
                type="entity",
                value="potion",
            )
        )
    ]
)

