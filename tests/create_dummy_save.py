
import pickle
from collections import defaultdict
from treasure_hunt.src.game_mdp import GameState, NPC, Player, Direction
from src.pipelines.evaluation.costs import PATIENT_DATA

def create_dummy_save():
    objects = defaultdict(dict)
    for p_id, p_info in PATIENT_DATA.items():
        name = p_info["name"]
        objects[p_info["location"]][name] = NPC(name, (0,0), "NORTH", [["hello", None]])
    
    state = GameState((0,0), (0,1), "room 0", objects=objects)
    with open("tests/p1.pkl", "wb") as f:
        pickle.dump(state, f)

if __name__ == "__main__":
    create_dummy_save()
