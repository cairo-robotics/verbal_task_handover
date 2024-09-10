import os
import json

class GameMap:
    def __init__(self, map_dir, starting_room='room0'):
        self.map_dir = map_dir
        self.texture_map_dir = os.path.join(map_dir, 'texture_maps/')
        self.texture_config  = self._load_texture_config(os.path.join(self.texture_map_dir, 'texture_config.json'))
        self.current_room = starting_room

        self.update_map(starting_room)
        self.transitions = self._load_transitions(map_dir + 'transitions.json')

    def update_map(self, room_name):
        self.current_room   = room_name
        self.grid           = self._load_grid(os.path.join(self.map_dir, room_name + '.txt'))
        self.texture_maps   = self._load_texture_maps(os.path.join(self.texture_map_dir, room_name))

    @property
    def all_texture_maps(self):
        return self.texture_maps.keys()

    def get_texture_data(self, coords, map_class):
        x, y = coords
        key = self.texture_maps[map_class][y][x]

        if key in ' -':
            return None, None
        
        sprite_type = self.texture_config[map_class]["sprite"]
        if key in "#":
            frame_name  = self.auto_tiler(self.texture_maps[map_class], x, y, key)
            # import pdb; pdb.set_trace()
            print(frame_name)
        else:
            frame_name  = self.texture_config[map_class]["mapping"][key]

        return sprite_type, frame_name

    def _load_texture_config(self, filename):
        with open(filename, 'r') as f:
            return json.load(f)

    def _find_in_map(self, char):
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if cell == char:
                    return y, x
        return None

    def _load_grid(self, filename):
        with open(filename, 'r') as f:
            return [list(line.rstrip('\n')) for line in f]
        
    def _load_texture_map(self, filename):
        try:
            with open(filename, 'r') as f:
                return [list(line.rstrip('\n')) for line in f]
        except FileNotFoundError:
            return None
        
    def _load_texture_maps(self, map_dir):
        texture_maps = {}
        try:
            for filename in os.listdir(map_dir):
                if filename.endswith('.txt'):
                    map_name = filename.split('.')[0]
                    texture_maps[map_name] = self._load_texture_map(os.path.join(map_dir, filename))
        except FileNotFoundError:
            pass
        return texture_maps
        
    def _load_transitions(self, filename):
        with open(filename, 'r') as f:
            return json.load(f)

    def is_valid_move(self, new_pos, state):
        rows = len(self.grid)
        cols = len(self.grid[0])
        x, y = new_pos
        if 0 <= y < rows and 0 <= x < cols:
            if self.grid[y][x] in ' T': # T is just a placemarker for treasure
                return True
            elif self.grid[y][x].isdigit() or self.grid[y][x] == 'D':
                # check if door is passable
                door = state._get_object_at_position(new_pos)
                if door is None or door.is_passable:
                    return True
        return False

    # Check for transition between rooms
    def check_transition(self, player_pos):
        x, y = player_pos
        if self.grid[y][x] in self.transitions[self.current_room]:
            new_room, door_id =  self.transitions[self.current_room][self.grid[y][x]]
            self.update_map(new_room)
            door_pos = self._find_in_map(str(door_id))
            new_pos = [door_pos[1], door_pos[0]]
            return new_room, new_pos
        return None, None

    # def move_player(self, state, new_pos, new_dir):
    #     move_success = False
    #     player_pos = state.player_pos
    #     if not state.player_in_interaction:
    #         if self._is_valid_move(new_pos, state):
    #             print("Player moved to", new_pos)
    #             player_pos = new_pos
    #             move_success = True

    #         new_room, new_player_pos = self._check_transition(player_pos)
    #         if new_room:
    #             print("Player moved to", new_room, new_player_pos)
    #             self.update_map(new_room)
    #             state.update_current_room(new_room)
    #             move_success = True
            
    #         state.player_pos = player_pos
    #         state.player_dir = new_dir

    #     return move_success, self.current_room, state.player_pos
    def auto_tiler(self, grid, x, y, key):
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
            return "top_left"
        elif top and bottom and left and right and not bottom_left:
            return "top_right"
        elif top and bottom and left and right and not top_right:
            return "bottom_left"
        elif top and bottom and left and right and not top_left:
            return "bottom_right"
        elif top and bottom and left and right:
            return "center"
        elif top and left and right and not bottom:
            return "top"
        elif bottom and left and right and not top:
            return "bottom"
        elif left and top and bottom and not right:
            return "left"
        elif right and top and bottom and not left:
            return "right"
        elif top and left and not right and not bottom:
            return "outer_corner_top_left"
        elif top and right and not left and not bottom:
            return "outer_corner_top_right"
        elif bottom and left and not right and not top:
            return "outer_corner_bottom_left"
        elif bottom and right and not left and not top:
            return "outer_corner_bottom_right"
        elif left:
            return "horizontal_left"
        elif right:
            return "horizontal_right"
        elif top:
            return "vertical_top"
        elif bottom:
            return "vertical_bottom"
        else:
            return "center"  # or perhaps a default texture