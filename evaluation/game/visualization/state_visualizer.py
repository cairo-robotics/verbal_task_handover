import pygame
from evaluation.game.visualization.utils import *
from evaluation.game.scripts.game_mdp import Direction
import os

GRAPHICS_DIR = "./evaluation/game/assets/"

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)

class StateVisualizer:
    def __init__(self, **kwargs):
        self.PLAYER_IMG = MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "000.png"), os.path.join(GRAPHICS_DIR, "char_sprites.json"))
        self.UNSCALED_TILE_SIZE = 32
        self.GRASS_TILE = pygame.image.load(os.path.join(GRAPHICS_DIR, "grass.png")).convert_alpha()
        self.GRASS_TILE = pygame.transform.scale(self.GRASS_TILE, (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
        self.scale_by_factor = 1

    def display_rendered_state(self, state, grid=None):
        surface = self.render_state(state, grid)
        run_static_resizeable_window(surface)

    def _unscaled_grid_pixel_size(self, grid):
        y_tiles = len(grid)
        x_tiles = len(grid[0])
        return (x_tiles * self.UNSCALED_TILE_SIZE, y_tiles * self.UNSCALED_TILE_SIZE)

    def _render_grid(self, surface, grid):
        for y, row in enumerate(grid):
            for x, tile in enumerate(row):
                if tile == "#":
                    pygame.draw.rect(surface, WHITE, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                else:
                    surface.blit(self.GRASS_TILE, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE))

    def _render_player(self, surface, state):
        player_dir = state.player_dir
        dir_name = Direction.DIRECTION_TO_NAME[player_dir]
        sprite_name = dir_name + "_2.png"
        player_pos = (state.player_pos[1], state.player_pos[0])
        self.PLAYER_IMG.blit_on_surface(surface,
                                        self._position_in_unscaled_pixels(player_pos),
                                        sprite_name)

    def _position_in_unscaled_pixels(self, position):
        """
        get x and y coordinates in tiles, returns x and y coordinates in pixels
        """
        (x,y) = position
        return (self.UNSCALED_TILE_SIZE * x, self.UNSCALED_TILE_SIZE * y)

    def _position_in_scaled_pixels(self, position):
        """
        get x and y coordinates in tiles, returns x and y coordinates in pixels
        """
        (x,y) = position
        return (self.tile_size * x, self.tile_size * y)

    def render_state(self, state, grid=None):
        pygame.init()
        grid_surface = pygame.surface.Surface(self._unscaled_grid_pixel_size(grid))
        self._render_grid(grid_surface, grid)
        self._render_player(grid_surface, state)

        if self.scale_by_factor != 1:
            grid_surface = scale_surface_by_factor(grid_surface, self.scale_by_factor)

        rendered_surface = grid_surface

        result_surface_size = (rendered_surface.get_width(), rendered_surface.get_height())

        if result_surface_size != rendered_surface.get_size():
            result_surface = blit_on_new_surface_of_size(rendered_surface, result_surface_size, background_color=self.background_color)
        else:
            result_surface = rendered_surface

        return result_surface
    