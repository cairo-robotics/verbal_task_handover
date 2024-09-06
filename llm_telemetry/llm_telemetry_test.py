import pygame
from treasure_hunt.src.game_mdp import GameState, Direction, start_state
from treasure_hunt.src.core import GameMap
from treasure_hunt.visualization.state_visualizer import StateVisualizer
from treasure_hunt.src.telemetry import Telemetry, DummyTelemetry, Event
import os
from pygame.locals import HWSURFACE, DOUBLEBUF, RESIZABLE
import json
import argparse

# Initialize Pygame
pygame.init()

MAP_DIRECTORY = '/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/maps/map0/'
SAVE_DIRECTORY = './saves/'
TELEMETRY_SAVE_DIRECTORY = SAVE_DIRECTORY + 'telemetry/'

SAVE_FILENAME = 'save.pkl'

# Constants
TILE_SIZE = 64
SCREEN_WIDTH = 15 * TILE_SIZE
SCREEN_HEIGHT = 15 * TILE_SIZE
FPS = 30

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

def on_render(window, state_vis, state, game_map):
    window.fill(BLACK)
    surface = state_vis.render_state(state, game_map)
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
    
    if args.telemetry:
        telemetry_file = os.path.join(TELEMETRY_SAVE_DIRECTORY, args.telemetry)
        telemetry = Telemetry(telemetry_file, args.overwrite_telemetry)
    else:
        telemetry = DummyTelemetry()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("2D Adventure Game")
    clock = pygame.time.Clock()


    if load_file:
        state = GameState.load(load_file)
        player_pos = state.player_pos
        player_dir = state.player_dir
        current_room = state.current_room
        print("Game loaded from ", load_file)
    else:
        current_room = 'room0'
        player_dir = Direction.SOUTH
        player_pos = [2, 2]  # Start position (y, x)
        objects = start_state(os.path.join(MAP_DIRECTORY, 'objects.json'))
        state = GameState(player_pos, player_dir, current_room, objects)
        print("Initializing new game...")

    # transitions = load_transitions(os.path.join(MAP_DIRECTORY, 'transitions.json'))
    # game_map = load_map(MAP_DIRECTORY + current_room + '.txt')
    game_map = GameMap(MAP_DIRECTORY, current_room)
    pygame.init()

    window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT),  HWSURFACE | DOUBLEBUF | RESIZABLE)
    state_vis = StateVisualizer()
    surface = state_vis.render_state(state, game_map)
    surface_size = surface.get_size()
    x, y  = (1920 - surface_size[0]) // 2, (1080 - surface_size[1]) // 2
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
                    if interact_output:
                        telemetry.log_event(*interact_output)
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

                    if game_map.is_valid_move(new_pos, state):
                        player_pos = new_pos

                    new_room, new_player_pos = game_map.check_transition(player_pos)
                    if new_room:
                        current_room = new_room
                        player_pos = new_player_pos
                        game_map.update_map(current_room)
                        state.update_current_room(current_room)
                        telemetry.log_event(Event.ROOM_ENTERED, current_room)

                    if player_pos != state.player_pos:
                        telemetry.log_event(Event.PLAYER_MOVED, str(player_pos))

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
    parser.add_argument('--telemetry', type=str, default="telemetry_test.txt", help='Filename of the telemetry log file')
    parser.add_argument('--append-telemetry', action='store_true', help="Overwrite the telemetry log file")
    args = parser.parse_args()

    main(args)
