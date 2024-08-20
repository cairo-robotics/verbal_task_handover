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
        "tile_size" : 96, # game resolution
        "game_surface_fps" : 30,
        "sprite_scaling" : {
            "chest" : 0.7,
        },
        "game_width_in_tiles" : 15,
        "game_height_in_tiles" : 15,
    }

    def __init__(self, **kwargs):

        params = copy.deepcopy(self.DEFAULT_VALUES)
        params.update(kwargs)
        self.configure(**params)

        self.MULTI_FRAME_SPRITES = {
            "player": MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "player.png"), os.path.join(GRAPHICS_DIR, "char_sprites.json")),
            "mark"  : MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "mark.png"), os.path.join(GRAPHICS_DIR, "char_sprites.json")),
            "lily"  : MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "lily.png"), os.path.join(GRAPHICS_DIR, "char_sprites.json")),
            "door"  : MultiFramePygameImage(os.path.join(GRAPHICS_DIR, "wooden_door.png"), os.path.join(GRAPHICS_DIR, "wooden_door.json")),
        }

        self.UNSCALED_TILE_SIZE = 32
        # Load a font
        self.font = pygame.font.SysFont('Arial', 24)

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

    def scale_blit_to_window(self, window, surface):
        window_size = window.get_size()
        surface_size = surface.get_size()
        
        scale_factor = min(window_size[0] / surface_size[0], window_size[1] / surface_size[1])
        result_surface = scale_surface_by_factor(surface, scale_factor)

        window.blit(result_surface, (0, 0))

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

    def _render_textbox(self, surface):
        surface_width, surface_height = surface.get_size()
        textbox_height = surface_height // 6
        textbox_width = int(surface_width * 0.7)

        # Create a surface for the textbox background
        textbox_surface = pygame.Surface((textbox_width, textbox_height))
        textbox_surface.fill((255, 255, 255))  # Black background

        textbox_position = (int((surface_width - textbox_width) // 2), int(surface_height * 0.75))
        return textbox_surface, textbox_position

    def _render_text(self, surface, text):
        textbox_surface, textbox_position = self._render_textbox(surface)
        text_surface = self.font.render(text, True, (0, 0, 0))  # Black text
        text_rect = text_surface.get_rect(center=(textbox_surface.get_width() // 2, textbox_surface.get_height() // 2))
        textbox_surface.blit(text_surface, text_rect)
        surface.blit(textbox_surface, textbox_position)

    def _render_player(self, surface, state):
        player_dir = state.player_dir
        dir_name = Direction.DIRECTION_TO_NAME[player_dir]
        sprite_name = dir_name + "_2.png"
        x_offset = (self.MULTI_FRAME_SPRITES["player"].sprite_size[1] - self.MULTI_FRAME_SPRITES["player"].sprite_size[0]) / (2 * self.MULTI_FRAME_SPRITES["player"].sprite_size[1])
        player_pos = (state.player_pos[0] + x_offset,
                      state.player_pos[1])
        self.MULTI_FRAME_SPRITES["player"].blit_on_surface(surface,
                                        self._position_in_unscaled_pixels(player_pos),
                                        sprite_name)
        
    def _render_objects(self, surface, state):
        for obj in state.objects:
            if obj.type == "npc":
                x_offset = (self.MULTI_FRAME_SPRITES[obj.name].sprite_size[1] - self.MULTI_FRAME_SPRITES[obj.name].sprite_size[0]) / (2 * self.MULTI_FRAME_SPRITES[obj.name].sprite_size[1])
                npc_pos = (obj.position[0] + x_offset, obj.position[1])
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
                elif obj.sprite in ["door_open", "door_closed"]:
                    sprite_name = ("OPEN" if obj.sprite == "door_open" else "CLOSED") + ".png"
                    sprite = self.MULTI_FRAME_SPRITES["door"].sprite(sprite_name)
                    rescaled_sprite = pygame.transform.scale(sprite, (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                    # self.MULTI_FRAME_SPRITES["door"].blit_on_surface(surface,
                    #                                                 self._position_in_unscaled_pixels((x, y)),
                    #                                                 sprite_name)
                    surface.blit(rescaled_sprite, self._position_in_unscaled_pixels((x, y)))

    def _position_in_unscaled_pixels(self, position):
        """
        get x and y coordinates in tiles, returns x and y coordinates in pixels
        """
        (x,y) = position
        return (self.UNSCALED_TILE_SIZE * x, self.UNSCALED_TILE_SIZE * y)

    # def _position_in_scaled_pixels(self, position):
    #     """
    #     get x and y coordinates in tiles, returns x and y coordinates in pixels
    #     """
    #     (x,y) = position
    #     return (self.tile_size * x, self.tile_size * y)
    
    @property
    def scale_by_factor(self):
        return self.tile_size/self.UNSCALED_TILE_SIZE

    def render_state(self, state, grid):
        grid_surface = pygame.surface.Surface(self._unscaled_grid_pixel_size(grid))
        # grid_surface = pygame.surface.Surface((self.UNSCALED_TILE_SIZE * self.game_width_in_tiles, self.UNSCALED_TILE_SIZE * self.game_height_in_tiles))

        self._render_grid(grid_surface, grid)
        self._render_player(grid_surface, state)
        self._render_objects(grid_surface, state)

        if self.scale_by_factor != 1:
            grid_surface = scale_surface_by_factor(grid_surface, self.scale_by_factor)

        # import pdb; pdb.set_trace() 
        tiles_width = max(self.game_width_in_tiles, len(grid[0]))
        tiles_height = max(self.game_height_in_tiles, len(grid))

        game_surface = pygame.surface.Surface((self.tile_size * tiles_width, self.tile_size * tiles_height))
        grid_rect = grid_surface.get_rect(center=(game_surface.get_width() // 2, grid_surface.get_height() // 2))
        game_surface.blit(grid_surface, grid_rect)

        text_to_display = state.displayed_text
        if text_to_display:
            self._render_text(game_surface, text_to_display)

        # return game_surface
        return game_surface