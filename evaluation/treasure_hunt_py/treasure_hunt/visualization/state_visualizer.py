import pygame
from treasure_hunt.visualization.utils import *
from treasure_hunt.src.game_mdp import Direction
import os
import copy
import json

# GRAPHICS_DIR = "./assets/"
GRAPHICS_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/assets/"

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
class StateVisualizer:
    DEFAULT_VALUES = {
        "tile_size" : 96, # game resolution
        "font_size" : 36,
        "game_surface_fps" : 30,
        "game_width_in_tiles" : 15,
        "game_height_in_tiles" : 15,
    }

    def __init__(self, config_filename="graphics_config.json", **kwargs):

        params = copy.deepcopy(self.DEFAULT_VALUES)
        params.update(kwargs)
        self.configure(**params)


        self.UNSCALED_TILE_SIZE = 32 # sprite resolution
        # Load a font
        self.font = pygame.font.SysFont('Arial', self.font_size)

        self.SPRITES = {}
        self.MULTI_FRAME_SPRITES = {}

        self.load_sprites_from_config(os.path.join(GRAPHICS_DIR, config_filename))

    def load_sprites_from_config(self, config_filename):
        with open(config_filename, "r") as f:
            config = json.load(f)
        for sprite_name in config:
            if config[sprite_name]["type"] == "single":
                self.SPRITES[sprite_name] = SingleFramePygameImage(os.path.join(GRAPHICS_DIR, config[sprite_name]["path"]))
                self.SPRITES[sprite_name].sprite_scaling = config[sprite_name]["scaling"]
            elif config[sprite_name]["type"] == "multi":
                self.MULTI_FRAME_SPRITES[sprite_name] = MultiFramePygameImage(os.path.join(GRAPHICS_DIR, config[sprite_name]["path"]), os.path.join(GRAPHICS_DIR, config[sprite_name]["config"]))
                self.MULTI_FRAME_SPRITES[sprite_name].sprite_scaling = config[sprite_name]["scaling"]

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
                    self.SPRITES["grass"].blit_on_surface_scaled(surface, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE), (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

    def _render_grid_with_textures(self, surface, grid, texture_map):
        for y, row in enumerate(texture_map):
            for x, tile in enumerate(row):
                if tile == "#":
                    pygame.draw.rect(surface, WHITE, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                else:
                    self.SPRITES["grass"].blit_on_surface_scaled(surface, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE), (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                    if tile in self.MULTI_FRAME_SPRITES["dirt"].mapping:
                        mfs = self.MULTI_FRAME_SPRITES["dirt"]
                        frame_name = mfs.mapping[tile] + ".png"
                        mfs.blit_on_surface_scaled(surface,
                                                (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE),
                                                frame_name,
                                                (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                    elif tile in self.MULTI_FRAME_SPRITES["walls"].mapping:
                        mfs = self.MULTI_FRAME_SPRITES["walls"]
                        frame_name = mfs.mapping[tile] + ".png"
                        mfs.blit_on_surface_scaled(surface,
                                                (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE),
                                                frame_name,
                                                (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

    def _render_textbox(self, surface):
        surface_width, surface_height = surface.get_size()
        textbox_height = surface_height // 6
        textbox_width = int(surface_width * 0.7)

        # Create a surface for the textbox background
        textbox_surface = pygame.Surface((textbox_width, textbox_height))
        textbox_surface.fill(WHITE)

        textbox_position = (int((surface_width - textbox_width) // 2), int(surface_height * 0.75))
        return textbox_surface, textbox_position

    def _render_text(self, surface, text):
        textbox_surface, textbox_position = self._render_textbox(surface)
        text_surface = self.font.render(text, True, BLACK) 
        text_rect = text_surface.get_rect(center=(textbox_surface.get_width() // 2, textbox_surface.get_height() // 2))
        textbox_surface.blit(text_surface, text_rect)
        surface.blit(textbox_surface, textbox_position)

    def _render_hud(self, surface, state):
        # for now: just render the score
        score_text = "Score: " + str(state.score)
        score_surface = self.font.render(score_text, True, WHITE)
        surface.blit(score_surface, (10, 10))

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
                    z = self.SPRITES[obj.sprite].sprite_scaling
                    x += ((1 - z)/2)
                    y += ((1 - z)/2)
                    self.SPRITES[obj.sprite].blit_on_surface_scaled(surface, self._position_in_unscaled_pixels((x, y)), (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                elif obj.sprite in ["door_open", "door_closed"]:
                    sprite_name = ("OPEN" if obj.sprite == "door_open" else "CLOSED") + ".png"
                    self.MULTI_FRAME_SPRITES["door"].blit_on_surface_scaled(surface, self._position_in_unscaled_pixels((x, y)), sprite_name, (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

    def _position_in_unscaled_pixels(self, position):
        """
        get x and y coordinates in tiles, returns x and y coordinates in pixels
        """
        (x,y) = position
        return (self.UNSCALED_TILE_SIZE * x, self.UNSCALED_TILE_SIZE * y)

    @property
    def scale_by_factor(self):
        return self.tile_size/self.UNSCALED_TILE_SIZE

    def render_state(self, state, game_map):
        grid_surface = pygame.surface.Surface(self._unscaled_grid_pixel_size(game_map.grid))

        if game_map.texture_map is not None:
            self._render_grid_with_textures(grid_surface, game_map.grid, game_map.texture_map)
        else:
            self._render_grid(grid_surface, game_map.grid)
        
        self._render_player(grid_surface, state)
        self._render_objects(grid_surface, state)

        if self.scale_by_factor != 1:
            grid_surface = scale_surface_by_factor(grid_surface, self.scale_by_factor)

        # import pdb; pdb.set_trace() 
        tiles_width = max(self.game_width_in_tiles, len(game_map.grid[0]))
        tiles_height = max(self.game_height_in_tiles, len(game_map.grid))

        game_surface = pygame.surface.Surface((self.tile_size * tiles_width, self.tile_size * tiles_height))
        grid_rect = grid_surface.get_rect(center=(game_surface.get_width() // 2, grid_surface.get_height() // 2))
        game_surface.blit(grid_surface, grid_rect)

        text_to_display = state.displayed_text
        if text_to_display:
            self._render_text(game_surface, text_to_display)
        self._render_hud(game_surface, state)

        return game_surface