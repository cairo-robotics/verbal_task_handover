import pygame
from treasure_hunt.src.game_mdp import GameState, Direction, start_state
from treasure_hunt.src.core import GameMap
from treasure_hunt.visualization.state_visualizer import StateVisualizer
from treasure_hunt.src.telemetry import Telemetry, DummyTelemetry, Event
from treasure_hunt.scripts.distractor import DistractorTaskManager
import os
from pygame.locals import HWSURFACE, DOUBLEBUF, RESIZABLE
import argparse
from collections import deque

# Initialize Pygame
pygame.init()

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
MAP_DIRECTORY = GAME_DIR + '/../maps/map2/'
SAVE_DIRECTORY = GAME_DIR + '/../saves/'
TELEMETRY_SAVE_DIRECTORY = SAVE_DIRECTORY + 'telemetry/'

SAVE_FILENAME = 'test_save'

STARTING_ROOM = 'room0'

DISTRACTOR_START_TIME = 5 # in minutes after script is executed
TOTAL_TASK_TIME = 10 # in minutes

# Constants  
TILE_SIZE = 96
SCREEN_WIDTH = 15 * TILE_SIZE
SCREEN_HEIGHT = 15 * TILE_SIZE
FPS = 30
MOVE_DURATION = 300 # time it takes to move from one tile to another in milliseconds
# MOVE_DURATION = 10

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

VISUAL_PARAMS = {
    'tile_size': TILE_SIZE,
    'font_size' : 36,
    'game_surface_fps' : FPS,
    'use_darkness' : False,
    'light_radius' : 2,
    'walk_animation_frames' : 3
}

STARTING_TEXT = [
    "The study task will now begin. (Press SPACE to continue)",
    "This map is loosely based on a hospital floor.",
    "There are 5 'patient' rooms, labeled room1 through room5. (The name of your current room is in the top-right.)",
    "Your goal is to fulfill the requests of the patients in each room.",
    "Among other tasks, you will need to bring each patient the correct color POTION."
    "The potion colors needed are as follows:",
    "Room 1 needs a GOLD potion.",
    "Room 2 needs a BLUE potion.",
    "Room 3 needs a RED potion.",
    "Room 4 needs a GREEN potion.",
    "Room 5 needs an ORANGE potion.",
    "You can also check with each patient to see which they need, but remember that this will cost you time.",
    "Patients may also ask you to bring their requests to NPCs elsewhere on the map.",
    "Press SPACE to begin the task."
]

def ending_popup():
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Show the message box
    messagebox.showinfo("Time up", "Your time is up. Your game has been saved. Please notify the experimenter.")

def on_render(window, state_vis, state, game_map):
    window.fill(BLACK)
    surface = state_vis.render_state(state, game_map)
    state_vis.scale_blit_to_window(window, surface)
    pygame.display.flip()

# Main game loop
def main(args):
    if args.load:
        save_file = args.save or args.load
        load_file = os.path.join(SAVE_DIRECTORY, args.load)
    else:
        load_file = None
        save_file = args.save or SAVE_FILENAME

    
    telemetry_file = os.path.join(TELEMETRY_SAVE_DIRECTORY, save_file + '.txt')
    telemetry = Telemetry(telemetry_file, args.overwrite_telemetry)
    save_file = os.path.join(SAVE_DIRECTORY, save_file)

    pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Treasure Hunt Task")
    clock = pygame.time.Clock()

    if load_file:
        state = GameState.load(load_file)
        player_pos = state.player.pos
        player_dir = state.player.dir
        current_room = state.current_room
        print("Game loaded from ", load_file)
    else:
        current_room = STARTING_ROOM
        player_dir = Direction.SOUTH
        player_pos = [2, 2]  # Start position (y, x)
        objects = start_state(os.path.join(MAP_DIRECTORY, 'objects.json'))
        state = GameState(player_pos, player_dir, current_room, objects)
        print("Initializing new game...")
        state.text_queue = deque([[line, ""] for line in STARTING_TEXT])
        state.handle_interact()

    state.set_telemetry(telemetry)

    # transitions = load_transitions(os.path.join(MAP_DIRECTORY, 'transitions.json'))
    # game_map = load_map(MAP_DIRECTORY + current_room + '.txt')
    game_map = GameMap(MAP_DIRECTORY, current_room)
    pygame.init()

    window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT),  HWSURFACE | DOUBLEBUF | RESIZABLE)
    state_vis = StateVisualizer(**VISUAL_PARAMS)
    surface = state_vis.render_state(state, game_map)
    surface_size = surface.get_size()
    x, y  = (1920 - surface_size[0]) // 2, (1080 - surface_size[1]) // 2
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (x, y)
    window.blit(surface, (0, 0))
    pygame.display.flip()

    running = True
    move_start_time = None
    move_duration = MOVE_DURATION  # Duration of the move in milliseconds
    move_target_pos = None
    keys_pressed = {pygame.K_LEFT: False, pygame.K_RIGHT: False, pygame.K_UP: False, pygame.K_DOWN: False}


    # set timer to start distractor task (will pause game while task is running)
    distractor_manager = DistractorTaskManager()
    distractor_manager.start_timer_and_launch(wait_duration=DISTRACTOR_START_TIME)


    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                telemetry.cleanup()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    state.handle_esc()
                    
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    state.save(save_file)
                    print("Game saved to ", save_file)
                
                elif state.player_in_module:
                    state.handle_keypress(event.key)
                
                elif event.key == pygame.K_SPACE:
                    interact_output = state.handle_interact()
                    # if interact_output:
                    #     telemetry.log_event(*interact_output)

                # elif event.key == pygame.K_F4:
                #     running = False
                #     telemetry.cleanup()

                elif event.key in keys_pressed and not state.player_in_interaction:
                    keys_pressed[event.key] = True
                    if move_target_pos is None:
                        new_pos = list(player_pos)
                        player_dir = state.player.dir
                        if keys_pressed[pygame.K_LEFT]:
                            new_pos[0] -= 1
                            player_dir = Direction.WEST
                        elif keys_pressed[pygame.K_RIGHT]:
                            new_pos[0] += 1
                            player_dir = Direction.EAST
                        elif keys_pressed[pygame.K_UP]:
                            new_pos[1] -= 1
                            player_dir = Direction.NORTH
                        elif keys_pressed[pygame.K_DOWN]:
                            new_pos[1] += 1
                            player_dir = Direction.SOUTH

                        if game_map.is_valid_move(new_pos, state):
                            move_target_pos = new_pos
                            move_start_time = pygame.time.get_ticks()
                        else:
                            move_target_pos = list(player_pos)
                        state.player.dir = player_dir

            elif event.type == pygame.KEYUP:
                if event.key in keys_pressed:
                    keys_pressed[event.key] = False

        # handle held arrow keys for movement
        if move_target_pos is None:
            new_pos = list(player_pos)
            player_dir = state.player.dir
            key_held = (keys_pressed[pygame.K_LEFT] or keys_pressed[pygame.K_RIGHT] or keys_pressed[pygame.K_UP] or keys_pressed[pygame.K_DOWN])
            if keys_pressed[pygame.K_LEFT]:
                new_pos[0] -= 1
                player_dir = Direction.WEST
            elif keys_pressed[pygame.K_RIGHT]:
                new_pos[0] += 1
                player_dir = Direction.EAST
            elif keys_pressed[pygame.K_UP]:
                new_pos[1] -= 1
                player_dir = Direction.NORTH
            elif keys_pressed[pygame.K_DOWN]:
                new_pos[1] += 1
                player_dir = Direction.SOUTH

            if key_held and game_map.is_valid_move(new_pos, state):
                move_target_pos = new_pos
                move_start_time = pygame.time.get_ticks()
                state.player.dir = player_dir

        if move_target_pos is not None:
            elapsed_time = pygame.time.get_ticks() - move_start_time
            if elapsed_time >= move_duration:
                player_pos = move_target_pos
                move_target_pos = None
                new_room, new_player_pos = game_map.check_transition(player_pos, state)
                if new_room:
                    current_room = new_room
                    player_pos = new_player_pos
                    state.update_current_room(current_room)
                    # telemetry.log_event(Event.ROOM_ENTERED, current_room)
                state.player.pos = player_pos

                # immediately queue next move if possible
                keys = pygame.key.get_pressed()
                if keys[pygame.K_LEFT]:
                    new_pos = list(player_pos)
                    new_pos[0] -= 1
                    if game_map.is_valid_move(new_pos, state):
                        state.player.dir = Direction.WEST
                        move_target_pos = new_pos
                        move_start_time = pygame.time.get_ticks()
                elif keys[pygame.K_RIGHT]:
                    new_pos = list(player_pos)
                    new_pos[0] += 1
                    if game_map.is_valid_move(new_pos, state):
                        state.player.dir = Direction.EAST
                        move_target_pos = new_pos
                        move_start_time = pygame.time.get_ticks()
                elif keys[pygame.K_UP]:
                    new_pos = list(player_pos)
                    new_pos[1] -= 1
                    if game_map.is_valid_move(new_pos, state):
                        state.player.dir = Direction.NORTH
                        move_target_pos = new_pos
                        move_start_time = pygame.time.get_ticks()
                elif keys[pygame.K_DOWN]:
                    new_pos = list(player_pos)
                    new_pos[1] += 1
                    if game_map.is_valid_move(new_pos, state):
                        state.player.dir = Direction.SOUTH
                        move_target_pos = new_pos
                        move_start_time = pygame.time.get_ticks()

            else:
                progress = elapsed_time / move_duration
                state.player.pos = [
                    player_pos[0] + (move_target_pos[0] - player_pos[0]) * progress,
                    player_pos[1] + (move_target_pos[1] - player_pos[1]) * progress
                ]

        on_render(window, state_vis, state, game_map)
        
        dt = clock.tick(FPS)
        state.tick(dt)
        if distractor_manager.distractor_active:
            distractor_manager.wait_for_completion()
        
        if state.elapsed_time > TOTAL_TASK_TIME * 60:
            # save game state
            state.save(save_file)
            # show ending popup
            ending_popup()

            running = False
            telemetry.cleanup()
        
    pygame.quit()

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Your Pygame game with save/load and telemetry functionality")
    parser.add_argument('--load', type=str, help='Filename of the save file to load')
    parser.add_argument('--save', type=str, default="test_save", help='Filename of the save file to write')
    parser.add_argument('--overwrite-telemetry', action='store_true', help='Overwrite the telemetry log file')
    args = parser.parse_args()

    main(args)
