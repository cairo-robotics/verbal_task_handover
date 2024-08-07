import pygame
from evaluation.game.visualization.utils import MultiFramePygameImage
from game_mdp import GameState, Direction, start_state
from evaluation.game.visualization.state_visualizer import StateVisualizer
import os
from pygame.locals import HWSURFACE, DOUBLEBUF, RESIZABLE
import json

# Initialize Pygame
pygame.init()

MAP_DIRECTORY = './evaluation/game/maps/'

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
def is_valid_move(game_map, new_pos):
    rows = len(game_map)
    cols = len(game_map[0])
    y, x = new_pos
    if 0 <= y < rows and 0 <= x < cols:
        return game_map[y][x] in ' 0123456'
    return False

# Check for transition
def check_transition(current_room, game_map, transitions, player_pos):
    y, x = player_pos
    # if current_room == 'room1' and game_map[y][x] == '>':
    #     return 'room2', [y, 1]  # Transition to room2, new player position
    # elif current_room == 'room2' and game_map[y][x] == '<':
    #     return 'room1', [y, len(game_map[0]) - 2]  # Transition to room1, new player position
    # return None, None
    if game_map[y][x] in transitions[current_room]:
        new_room, new_pos =  transitions[current_room][game_map[y][x]]
        return new_room, new_pos
    return None, None

def on_render(window, state_vis, state, grid):
    window.fill(BLACK)
    surface = state_vis.render_state(state, grid)
    window.blit(surface, (0, 0))
    pygame.display.flip()

# Main game loop
def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("2D Adventure Game")
    clock = pygame.time.Clock()

    current_room = 'room1'
    game_map = load_map(MAP_DIRECTORY + current_room + '.txt')

    player_pos = [2, 2]  # Start position (y, x)
    player_dir = Direction.SOUTH
    objects = start_state('./evaluation/game/maps/objects.json')
    transitions = load_transitions('./evaluation/game/maps/transitions.json')
    state = GameState(player_pos, player_dir, current_room, objects)
    print(state.objects)
    # player_sprite = pygame.image.load('./evaluation/game/assets/vita_single.png').convert_alpha()
    # player_sprite = pygame.transform.scale(player_sprite, (TILE_SIZE, TILE_SIZE))

    pygame.init()

    state_vis = StateVisualizer()
    surface = state_vis.render_state(state, game_map)
    surface_size = surface.get_size()
    x, y  = (1920 - surface_size[0]) // 2, (1080 - surface_size[1]) // 2
    grid_shape = (len(game_map[0]), len(game_map))
    # grid_shape = (SCREEN_WIDTH, SCREEN_HEIGHT)
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (x, y)

    window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT),  HWSURFACE | DOUBLEBUF | RESIZABLE)
    window.blit(surface, (0, 0))
    pygame.display.flip()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    interact_output = state.handle_interact(game_map)
                else:
                    new_pos = list(player_pos)
                    if event.key == pygame.K_LEFT:
                        new_pos[1] -= 1
                        player_dir = Direction.WEST
                    elif event.key == pygame.K_RIGHT:
                        new_pos[1] += 1
                        player_dir = Direction.EAST
                    elif event.key == pygame.K_UP:
                        new_pos[0] -= 1
                        player_dir = Direction.NORTH
                    elif event.key == pygame.K_DOWN:
                        new_pos[0] += 1
                        player_dir = Direction.SOUTH

                    if is_valid_move(game_map, new_pos):
                        player_pos = new_pos

                    new_room, new_player_pos = check_transition(current_room, game_map, transitions, player_pos)
                    if new_room:
                        current_room = new_room
                        game_map = load_map(MAP_DIRECTORY + current_room + '.txt')
                        player_pos = new_player_pos
                    state.player_pos = player_pos
                    state.player_dir = player_dir
                    state.current_room = current_room

        on_render(window, state_vis, state, game_map)
        clock.tick(FPS)

    pygame.quit()

if __name__ == '__main__':
    main()
