import pygame
from treasure_hunt.src.game_mdp import GameState, Direction, start_state
from treasure_hunt.src.core import GameMap
from treasure_hunt.src.modules import WireModule
from treasure_hunt.visualization.state_visualizer import StateVisualizer
from treasure_hunt.visualization.utils import run_static_resizeable_window
from treasure_hunt.visualization.module_visualizer import WireModuleInterface
import os
import argparse

# Initialize Pygame
pygame.init()

ROOM = 'room14'

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
MAP_DIRECTORY = GAME_DIR + '/../maps/map1/'
SAVE_DIRECTORY = GAME_DIR + '/../saves/'

SAVE_FILENAME = 'test_save.pkl'

# Constants  
TILE_SIZE = 64
SCREEN_WIDTH = 15 * TILE_SIZE
SCREEN_HEIGHT = 15 * TILE_SIZE
FPS = 30

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


# Main game loop
def main(args):
    if args.load:
        load_file = os.path.join(SAVE_DIRECTORY, args.load)
    else:
        load_file = None

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("2D Adventure Game")

    if load_file:
        state = GameState.load(load_file)
        player_pos = state.player_pos
        player_dir = state.player_dir
        current_room = state.current_room
        print("Game loaded from ", load_file)
    else:
        current_room = ROOM
        player_dir = Direction.SOUTH
        player_pos = [0, 0]  # Start position (y, x)
        objects = start_state(os.path.join(MAP_DIRECTORY, 'objects.json'))
        state = GameState(player_pos, player_dir, current_room, objects)
        print("Initializing new game...")

    # transitions = load_transitions(os.path.join(MAP_DIRECTORY, 'transitions.json'))
    # game_map = load_map(MAP_DIRECTORY + current_room + '.txt')
    game_map = GameMap(MAP_DIRECTORY, current_room)
    state_vis = StateVisualizer()
    # surface = state_vis.render_state(state, game_map)

    wire_module = WireModule.random()
    surface = state_vis.render_module(wire_module, game_map)

    run_static_resizeable_window(surface)

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Your Pygame game with save/load functionality")
    parser.add_argument('--load', type=str, help='Filename of the save file to load')
    parser.add_argument('--save', type=str, help='Filename of the save file to write')
    parser.add_argument('--telemetry', type=str, help='Filename of the telemetry log file')
    parser.add_argument('--overwrite-telemetry', action='store_true', help='Overwrite the telemetry log file')
    args = parser.parse_args()

    main(args)
