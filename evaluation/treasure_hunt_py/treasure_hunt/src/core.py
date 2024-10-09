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
        map_dict = self.texture_config[map_class]["mapping"]
        if key in map_dict:
            frame_name  = self.texture_config[map_class]["mapping"][key]
        else:
            frame_name = None
        return sprite_type, frame_name

    def _load_texture_config(self, filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

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
    def check_transition(self, player_pos, game_state):
        x, y = player_pos
        try:
            if self.grid[y][x] in self.transitions[self.current_room]:
                # make sure the transition is not blocked by an object (e.g. hidden stairs)
                if not game_state.check_available_transition(x, y):
                    return None, None

                new_room, door_id =  self.transitions[self.current_room][self.grid[y][x]]
                self.update_map(new_room)
                door_pos = self._find_in_map(str(door_id))
                new_pos = [door_pos[1], door_pos[0]]
                return new_room, new_pos
            return None, None
        except KeyError:
            return None, None