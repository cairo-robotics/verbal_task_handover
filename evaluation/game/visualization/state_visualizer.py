import pygame
from evaluation.game.visualization.utils import *
from evaluation.game.scripts.game_mdp import Direction
import os
import copy

GRAPHICS_DIR = "./evaluation/game/assets/"

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
class StateVisualizer:
    DEFAULT_VALUES = {
        # "height": 20 * 96,
        # "width": 20 * 96,
        "tile_size": 96,
        "window_fps" : 30,
        "sprite_scaling" : {
            "chest" : 0.7,
        }
    }

    def __init__(self, **kwargs):

        params = copy.deepcopy(self.DEFAULT_VALUES)
        params.update(kwargs)
        self.configure(**params)

        self.MULTI_FRAME_SPRITES = {
            "player": MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "player.png"), os.path.join(GRAPHICS_DIR, "char_sprites.json")),
            "mark"  : MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "mark.png"), os.path.join(GRAPHICS_DIR, "char_sprites.json")),
        }

        self.UNSCALED_TILE_SIZE = 32
        grass_tile = pygame.image.load(os.path.join(GRAPHICS_DIR, "grass.png")).convert_alpha()
        grass_tile = pygame.transform.scale(grass_tile, (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
        
        chest_closed = pygame.image.load(os.path.join(GRAPHICS_DIR, "chest_closed.png")).convert_alpha()
        chest_closed = pygame.transform.scale(chest_closed, (self.UNSCALED_TILE_SIZE * self.sprite_scaling["chest"], self.UNSCALED_TILE_SIZE * self.sprite_scaling["chest"]))
        chest_open   = pygame.image.load(os.path.join(GRAPHICS_DIR, "chest_open.png")).convert_alpha()
        chest_open = pygame.transform.scale(chest_open, (self.UNSCALED_TILE_SIZE * self.sprite_scaling["chest"], self.UNSCALED_TILE_SIZE * self.sprite_scaling["chest"]))

        self.SPRITES = {
            "grass" : grass_tile,
            "chest_open" : chest_open,
            "chest_closed" : chest_closed
        }

    @classmethod
    def configure_defaults(cls, **kwargs):
        cls._check_config_validity(kwargs)
        cls.DEFAULT_VALUES.update(copy.deepcopy(kwargs))

    def configure(self, **kwargs):
        # StateVisualizer._check_config_validity(kwargs)
        for param_name, param_value in copy.deepcopy(kwargs).items():
            setattr(self, param_name, param_value)

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
                    surface.blit(self.SPRITES["grass"], (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE))

    def _render_player(self, surface, state):
        player_dir = state.player_dir
        dir_name = Direction.DIRECTION_TO_NAME[player_dir]
        sprite_name = dir_name + "_2.png"
        x_offset = (self.MULTI_FRAME_SPRITES["player"].sprite_size[1] - self.MULTI_FRAME_SPRITES["player"].sprite_size[0]) / (2 * self.MULTI_FRAME_SPRITES["player"].sprite_size[1])
        player_pos = (state.player_pos[1] + x_offset,
                      state.player_pos[0])
        self.MULTI_FRAME_SPRITES["player"].blit_on_surface(surface,
                                        self._position_in_unscaled_pixels(player_pos),
                                        sprite_name)
        
    def _render_objects(self, surface, state):
        # import pdb; pdb.set_trace()
        for obj in state.objects:
            if obj.type == "npc":
                x_offset = (self.MULTI_FRAME_SPRITES[obj.name].sprite_size[1] - self.MULTI_FRAME_SPRITES[obj.name].sprite_size[0]) / (2 * self.MULTI_FRAME_SPRITES[obj.name].sprite_size[1])
                npc_pos = (obj.position[1] + x_offset, obj.position[0])
                sprite_name = Direction.DIRECTION_TO_NAME[obj.orientation] + "_2.png"
                self.MULTI_FRAME_SPRITES[obj.name].blit_on_surface(surface,
                                                                   self._position_in_unscaled_pixels(npc_pos),
                                                                   sprite_name)
            else:
                x, y = obj.position
                if obj.sprite in ["chest_open", "chest_closed"]:
                    z = self.sprite_scaling["chest"]
                    x += ((1 - z)/2)
                    y += ((1 - z)/2)
                    if obj.sprite == "chest_open":
                        surface.blit(self.SPRITES["chest_open"], self._position_in_unscaled_pixels((x, y)))
                    else:
                        surface.blit(self.SPRITES["chest_closed"], self._position_in_unscaled_pixels((x, y)))

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
    
    @property
    def scale_by_factor(self):
        return self.tile_size/self.UNSCALED_TILE_SIZE

    def render_state(self, state, grid=None):
        grid_surface = pygame.surface.Surface(self._unscaled_grid_pixel_size(grid))
        self._render_grid(grid_surface, grid)
        self._render_player(grid_surface, state)
        self._render_objects(grid_surface, state)

        if self.scale_by_factor != 1:
            grid_surface = scale_surface_by_factor(grid_surface, self.scale_by_factor)

        rendered_surface = grid_surface

        result_surface_size = (rendered_surface.get_width(), rendered_surface.get_height())

        if result_surface_size != rendered_surface.get_size():
            result_surface = blit_on_new_surface_of_size(rendered_surface, result_surface_size, background_color=self.background_color)
        else:
            result_surface = rendered_surface

        return result_surface
    