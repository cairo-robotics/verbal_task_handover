import pygame
from treasure_hunt.src.game_mdp import GameState, Direction, start_state
from treasure_hunt.visualization.state_visualizer import StateVisualizer
# from treasure_hunt.src.telemetry import Telemetry
from llm_telemetry import LLMTelemetryFull as Telemetry
import os
from pygame.locals import HWSURFACE, DOUBLEBUF, RESIZABLE
import json
import argparse

# Initialize Pygame
pygame.init()

MAP_DIRECTORY = '/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/maps/map0/'
SAVE_DIRECTORY = './saves/'
TELEMETRY_SAVE_DIRECTORY = SAVE_DIRECTORY + 'telemetry/'

SAVE_FILENAME = 'test_save.pkl'
TELEMETRY_FILENAME = 'telemetry_log.txt'

# Constants
TILE_SIZE = 64
SCREEN_WIDTH = 15 * TILE_SIZE
SCREEN_HEIGHT = 15 * TILE_SIZE
FPS = 30

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

# Load the map
def load_map(filename):
    with open(filename, 'r') as f:
        return [list(line.strip()) for line in f]
    
def load_transitions(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# Check collision
def is_valid_move(game_map, new_pos, game_state):
    rows = len(game_map)
    cols = len(game_map[0])
    x, y = new_pos
    if 0 <= y < rows and 0 <= x < cols:
        if game_map[y][x] == ' ':
            return True
        elif game_map[y][x] in '0123456':
            # check if door is passable
            door = game_state._get_object_at_position(new_pos)
            if door is None or door.is_passable:
                return True
    return False

# Check for transition
def check_transition(current_room, game_map, transitions, player_pos):
    x, y = player_pos
    if game_map[y][x] in transitions[current_room]:
        new_room, new_pos =  transitions[current_room][game_map[y][x]]
        return new_room, new_pos
    return None, None

def on_render(window, state_vis, state, grid):
    window.fill(BLACK)
    surface = state_vis.render_state(state, grid)
    state_vis.scale_blit_to_window(window, surface)
    # window.blit(surface, (0, 0))
    pygame.display.flip()

# Main game loop
def main(args):
    if args.load:
        save_file = args.save or args.load
        load_file = os.path.join(SAVE_DIRECTORY, args.load)
    else:
        load_file = None
        save_file = args.save or SAVE_FILENAME

    save_file = os.path.join(SAVE_DIRECTORY, save_file)
    
    telemetry_file = args.telemetry or TELEMETRY_FILENAME
    telemetry_file = os.path.join(TELEMETRY_SAVE_DIRECTORY, telemetry_file)

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("2D Adventure Game")
    clock = pygame.time.Clock()

    telemetry = Telemetry(telemetry_file, args.overwrite_telemetry)

    if load_file:
        state = GameState.load(load_file, telemetry=telemetry)
        player_pos = state.player_pos
        player_dir = state.player_dir
        current_room = state.current_room
        print("Game loaded from ", load_file)
    else:
        current_room = 'room0'
        player_dir = Direction.SOUTH
        player_pos = [2, 2]  # Start position (y, x)
        objects = start_state(os.path.join(MAP_DIRECTORY, 'objects.json'))
        state = GameState(player_pos, player_dir, current_room, objects, telemetry=telemetry)
        print("Initializing new game...")

    transitions = load_transitions(os.path.join(MAP_DIRECTORY, 'transitions.json'))
    game_map = load_map(MAP_DIRECTORY + current_room + '.txt')
    pygame.init()

    window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT),  HWSURFACE | DOUBLEBUF | RESIZABLE)
    state_vis = StateVisualizer()
    state_vis.set_texture_map_dir(os.path.join(MAP_DIRECTORY, 'texture_maps/'))
    surface = state_vis.render_state(state, game_map)
    surface_size = surface.get_size()
    x, y  = (1920 - surface_size[0]) // 2, (1080 - surface_size[1]) // 2
    grid_shape = (len(game_map[0]), len(game_map))
    # grid_shape = (SCREEN_WIDTH, SCREEN_HEIGHT)
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (x, y)
    window.blit(surface, (0, 0))
    pygame.display.flip()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    interact_output = state.handle_interact()
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    state.save(save_file)
                    print("Game saved to ", save_file)

                elif event.key == pygame.K_ESCAPE:
                    running = False
                    telemetry.cleanup()

                elif not state.player_in_interaction:
                    new_pos = list(player_pos)
                    if event.key == pygame.K_LEFT:
                        new_pos[0] -= 1
                        player_dir = Direction.WEST
                    elif event.key == pygame.K_RIGHT:
                        new_pos[0] += 1
                        player_dir = Direction.EAST
                    elif event.key == pygame.K_UP:
                        new_pos[1] -= 1
                        player_dir = Direction.NORTH
                    elif event.key == pygame.K_DOWN:
                        new_pos[1] += 1
                        player_dir = Direction.SOUTH

                    if is_valid_move(game_map, new_pos, state):
                        player_pos = new_pos

                    new_room, new_player_pos = check_transition(current_room, game_map, transitions, player_pos)
                    if new_room:
                        current_room = new_room
                        game_map = load_map(MAP_DIRECTORY + current_room + '.txt')
                        player_pos = new_player_pos
                        state.update_current_room(current_room)
                    state.player_pos = player_pos
                    state.player_dir = player_dir

        on_render(window, state_vis, state, game_map)
        clock.tick(FPS)

    pygame.quit()

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Your Pygame game with save/load functionality")
    parser.add_argument('--load', type=str, help='Filename of the save file to load')
    parser.add_argument('--save', type=str, help='Filename of the save file to write')
    parser.add_argument('--telemetry', type=str, help='Filename of the telemetry log file')
    parser.add_argument('--overwrite-telemetry', action='store_true', help='Overwrite the telemetry log file')
    args = parser.parse_args()

    main(args)
