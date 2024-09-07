import os
import json

class GameMap:
    def __init__(self, map_dir, starting_room='room0'):
        self.map_dir = map_dir
        self.texture_map_dir = os.path.join(map_dir, 'texture_maps/')
        self.current_room = starting_room

        self.update_map(starting_room)
        self.transitions = self._load_transitions(map_dir + 'transitions.json')

    def update_map(self, room_name):
        self.current_room   = room_name
        self.grid           = self._load_grid(os.path.join(self.map_dir, room_name + '.txt'))
        self.texture_map    = self._load_texture_map(os.path.join(self.texture_map_dir, room_name + '.txt'))

    def _find_in_map(self, char):
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if cell == char:
                    return y, x
        return None

    def _load_grid(self, filename):
        with open(filename, 'r') as f:
            return [list(line.strip()) for line in f]
        
    def _load_texture_map(self, filename):
        try:
            with open(filename, 'r') as f:
                return [list(line.strip()) for line in f]
        except FileNotFoundError:
            return None
        
    def _load_transitions(self, filename):
        with open(filename, 'r') as f:
            return json.load(f)

    def is_valid_move(self, new_pos, state):
        rows = len(self.grid)
        cols = len(self.grid[0])
        x, y = new_pos
        if 0 <= y < rows and 0 <= x < cols:
            if self.grid[y][x] == ' ':
                return True
            elif self.grid[y][x].isdigit():
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