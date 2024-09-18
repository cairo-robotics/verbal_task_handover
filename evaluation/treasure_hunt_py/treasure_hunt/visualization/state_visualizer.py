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

def within_radius(pos1, pos2, r):
    return (pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 <= r**2

def auto_tile(grid, x, y, key):
    layers = []

    # Check surrounding tiles
    top = grid[y-1][x] == key if y > 0 else True
    bottom = grid[y+1][x] == key if y < len(grid)-1 else True
    left = grid[y][x-1] == key if x > 0 else True
    right = grid[y][x+1] == key if x < len(grid[0])-1 else True

    # Check diagonals
    top_left = grid[y-1][x-1] == key if y > 0 and x > 0 else True
    top_right = grid[y-1][x+1] == key if y > 0 and x < len(grid[0])-1 else True
    bottom_left = grid[y+1][x-1] == key if y < len(grid)-1 and x > 0 else True
    bottom_right = grid[y+1][x+1] == key if y < len(grid)-1 and x < len(grid[0])-1 else True

    if top and bottom and left and right and not bottom_right:
        return "inner_bottom_right"
    elif top and bottom and left and right and not bottom_left:
        return "inner_bottom_left"
    elif top and bottom and left and right and not top_right:
        return "inner_top_right"
    elif top and bottom and left and right and not top_left:
        return "inner_top_left"
        
    elif top and bottom and left and right:
        return "center"
    elif top and left and right and not bottom:
        return "bottom"
    elif bottom and left and right and not top:
        return "top"
    elif left and top and bottom and not right:
        return "right"
    elif right and top and bottom and not left:
        return "left"
    elif top and left and not right and not bottom:
        return "bottom_right"
    elif top and right and not left and not bottom:
        return "bottom_left"
    elif bottom and left and not right and not top:
        return "top_right"
    elif bottom and right and not left and not top:
        return "top_left"
    elif left and right:
        return "horizontal"
    elif top and bottom:
        return "vertical"
    elif top:
        return "vertical_bottom"
    elif bottom:
        return "vertical_top"
    elif left:
        return "horizontal_right"
    elif right:
        return "horizontal_left"
    else:
        return "single"  # or perhaps a default texture
    
    return layers

class StateVisualizer:
    DEFAULT_VALUES = {
        "use_darkness" : False, # if true: require TM Flash to see
        "light_radius" : 3, # how far the player can see (if use_darkness is True)
        "tile_size" : 96, # game resolution
        "font_size" : 36,
        "game_surface_fps" : 30,
        "game_width_in_tiles" : 15,
        "game_height_in_tiles" : 15,
        "config_filename" : "graphics_config.json"
    }

    def __init__(self, **kwargs):

        params = copy.deepcopy(self.DEFAULT_VALUES)
        params.update(kwargs)
        self.configure(**params)


        self.UNSCALED_TILE_SIZE = 32 # sprite resolution
        # Load a font
        self.font = pygame.font.SysFont('Arial', self.font_size)

        self.SPRITES = {}
        self.MULTI_FRAME_SPRITES = {}

        self.load_sprites_from_config(os.path.join(GRAPHICS_DIR, self.config_filename))

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
                if "extra_sprites" in config[sprite_name]:
                    for extra_sprite in config[sprite_name]["extra_sprites"]:
                        self.MULTI_FRAME_SPRITES[sprite_name].add_extra_sprite(extra_sprite["name"] + '.png', os.path.join(GRAPHICS_DIR, extra_sprite["path"]))
                if "layer" in config[sprite_name] and config[sprite_name]["layer"]:
                    self.MULTI_FRAME_SPRITES[sprite_name].layer = True
                if "auto_tile" in config[sprite_name] and config[sprite_name]["auto_tile"]:
                    self.MULTI_FRAME_SPRITES[sprite_name].auto_tile = True

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
                    # pygame.draw.rect(surface, WHITE, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                    frame_name = auto_tile(grid, x, y, "#") + ".png"
                    self.MULTI_FRAME_SPRITES["walls"].blit_on_surface_scaled(surface, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE), frame_name, (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                elif tile == "-":
                    pygame.draw.rect(surface, BLACK, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                else:
                    self.SPRITES["grass"].blit_on_surface_scaled(surface, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE), (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

    def _render_grid_with_textures(self, surface, game_map):
        texture_map_names = game_map.all_texture_maps

        for map_name in texture_map_names:
            texture_map = game_map.texture_maps[map_name]
            for y in range(len(texture_map)):
                for x in range(len(texture_map[y])):
                    sprite_name, frame_name = game_map.get_texture_data((x, y), map_name)
                    if sprite_name is not None:
                        if frame_name is not None:
                            mfs = self.MULTI_FRAME_SPRITES[sprite_name]

                            if mfs.auto_tile and frame_name == "default":
                                frame_name = auto_tile(texture_map, x, y, texture_map[y][x])

                            mfs.blit_on_surface_scaled(surface,
                                                       (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE),
                                                       frame_name + ".png",
                                                       (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                        elif sprite_name in self.SPRITES:
                            self.SPRITES[sprite_name].blit_on_surface_scaled(surface, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE), (self.UNSCALED_TILE_SIZE, self.UNSCA_UNSCALED_TILE_SIZELED_TILE_SIZE))

    def _render_textbox(self, surface):
        surface_width, surface_height = surface.get_size()
        textbox_height = surface_height // 6
        textbox_width = int(surface_width * 0.7)

        # Create a surface for the textbox background
        textbox_surface = pygame.Surface((textbox_width, textbox_height))
        textbox_surface.fill(WHITE)

        textbox_position = (int((surface_width - textbox_width) // 2), int(surface_height * 0.75))
        return textbox_surface, textbox_position
    
    def _render_text(self, surface, text, item=None):
        textbox_surface, textbox_position = self._render_textbox(surface)
        textbox_width = textbox_surface.get_width()
        textbox_height = textbox_surface.get_height()
        line_height = self.font.get_linesize()  # Height of each line

        margin = 20  # Horizontal buffer/padding from the edges of the textbox

        words = text.split(' ')
        lines = []
        current_line = ""

        # Split text into multiple lines that fit within the textbox width (considering margin)
        for word in words:
            test_line = current_line + word + " "
            test_surface = self.font.render(test_line, True, BLACK)
            
            # If the test line is too wide, finalize the current line and start a new one
            if test_surface.get_width() > textbox_width - 2 * margin:
                lines.append(current_line)  # Add the current line to the list
                current_line = word + " "  # Start a new line with the current word
            else:
                current_line = test_line  # Continue adding words to the current line
        
        # Add the last line if there's any text left in current_line
        if current_line:
            lines.append(current_line)

        # Calculate total height of the rendered text and the starting y-position for centering
        total_text_height = len(lines) * line_height
        start_y = (textbox_height - total_text_height) // 2

        # Render each line and blit onto the textbox, centered with margin
        for i, line in enumerate(lines):
            text_surface = self.font.render(line, True, BLACK)
            # Center the text within the available width (textbox_width - 2 * margin)
            text_rect = text_surface.get_rect(midtop=((textbox_width // 2), start_y + i * line_height))
            textbox_surface.blit(text_surface, text_rect)

        # Blit item sprite if applicable
        if item:
            if "gem" in item:
                mfs = self.MULTI_FRAME_SPRITES["gems"]
            elif "key" in item:
                mfs = self.MULTI_FRAME_SPRITES["keys"]
            
            item_sprite_size = get_scaled_surface_size(mfs, (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
            item_sprite_pos = (textbox_surface.get_width() // 2 - item_sprite_size[0] // 2, textbox_surface.get_height() - item_sprite_size[1] - 10)
            mfs.blit_on_surface_scaled(textbox_surface, item_sprite_pos, item + ".png", (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

        # Blit the textbox onto the main surface
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
            if not obj.is_visible:
                continue
            if obj.type == "npc":
                x_offset = (self.MULTI_FRAME_SPRITES[obj.name].sprite_size[1] - self.MULTI_FRAME_SPRITES[obj.name].sprite_size[0]) / (2 * self.MULTI_FRAME_SPRITES[obj.name].sprite_size[1])
                npc_pos = (obj.position[0] + x_offset, obj.position[1])
                sprite_name = Direction.DIRECTION_TO_NAME[obj.orientation] + "_2.png"
                self.MULTI_FRAME_SPRITES[obj.name].blit_on_surface(surface,
                                                                   self._position_in_unscaled_pixels(npc_pos),
                                                                   sprite_name)
            elif obj.sprite is not None:
                x, y = obj.position
                
                if obj.type in self.MULTI_FRAME_SPRITES:
                    img_name = obj.type
                    z = self.MULTI_FRAME_SPRITES[img_name].sprite_scaling
                    x += ((1 - z)/2)
                    y += ((1 - z)/2)
                    self.MULTI_FRAME_SPRITES[img_name].blit_on_surface_scaled(surface, self._position_in_unscaled_pixels((x, y)), obj.sprite + ".png", (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))
                
                elif obj.sprite in self.SPRITES:
                    self.SPRITES[obj.sprite].blit_on_surface_scaled(surface, self._position_in_unscaled_pixels(obj.position), (self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

    def _position_in_unscaled_pixels(self, position):
        """
        get x and y coordinates in tiles, returns x and y coordinates in pixels
        """
        (x,y) = position
        return (self.UNSCALED_TILE_SIZE * x, self.UNSCALED_TILE_SIZE * y)
    
    def _apply_darkness_mask(self, state, game_map, surface):
        player_pos = state.player_pos
        
        for y in range(len(game_map.grid)):
            for x in range(len(game_map.grid[y])):
                if not within_radius(player_pos, (x, y), self.light_radius):
                    pygame.draw.rect(surface, BLACK, (x * self.UNSCALED_TILE_SIZE, y * self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE, self.UNSCALED_TILE_SIZE))

    @property
    def scale_by_factor(self):
        return self.tile_size/self.UNSCALED_TILE_SIZE

    def render_state(self, state, game_map):
        grid_surface = pygame.surface.Surface(self._unscaled_grid_pixel_size(game_map.grid))

        self._render_grid(grid_surface, game_map.grid)
        if game_map.texture_maps:
            self._render_grid_with_textures(grid_surface, game_map)
        
        self._render_objects(grid_surface, state)
        self._render_player(grid_surface, state)

        if self.use_darkness:
            self._apply_darkness_mask(state, game_map, grid_surface)

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
            self._render_text(game_surface, text_to_display, state.displayed_icon)
        self._render_hud(game_surface, state)

        return game_surface