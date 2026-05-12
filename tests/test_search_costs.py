import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path
sys.path.append("/home/kaleb/code/verbal_task_handover")

from src.pipelines.evaluation.search_costs import expected_search_cost

class TestSearchCosts(unittest.TestCase):

    @patch('src.pipelines.evaluation.search_costs.load_transitions')
    @patch('src.pipelines.evaluation.search_costs.get_room_center')
    @patch('src.pipelines.evaluation.search_costs.find_steps_between_rooms')
    @patch('os.path.exists')
    def test_expected_search_cost_uniform(self, mock_exists, mock_find_steps, mock_get_center, mock_load_transitions):
        # Setup mocks
        mock_exists.return_value = True
        mock_load_transitions.return_value = {}
        mock_get_center.return_value = (0, 0)
        
        # Distances:
        # start -> r1: 10
        # start -> r2: 20
        # r1 -> r2: 5
        # r2 -> r1: 5
        def side_effect(rooms_dir, r1, p1, r2, p2, trans):
            if (r1, r2) == ('start', 'room1'): return 10
            if (r1, r2) == ('start', 'room2'): return 20
            if (r1, r2) == ('room1', 'room2'): return 5
            if (r1, r2) == ('room2', 'room1'): return 5
            return 0

        mock_find_steps.side_effect = side_effect
        
        # Search rooms: room1, room2
        # Order [room1, room2]:
        # Cost to room1: 10
        # Cost to room2: 10 + 5 = 15
        # Expected cost (uniform): 0.5 * 10 + 0.5 * 15 = 12.5
        
        # Order [room2, room1]:
        # Cost to room2: 20
        # Cost to room1: 20 + 5 = 25
        # Expected cost (uniform): 0.5 * 20 + 0.5 * 25 = 22.5
        
        # Min expected cost should be 12.5
        cost = expected_search_cost('start', ['room1', 'room2'])
        self.assertEqual(cost, 12.5)

    @patch('src.pipelines.evaluation.search_costs.load_transitions')
    @patch('src.pipelines.evaluation.search_costs.get_room_center')
    @patch('src.pipelines.evaluation.search_costs.find_steps_between_rooms')
    @patch('os.path.exists')
    def test_expected_search_cost_weighted(self, mock_exists, mock_find_steps, mock_get_center, mock_load_transitions):
        # Setup mocks
        mock_exists.return_value = True
        mock_load_transitions.return_value = {}
        mock_get_center.return_value = (0, 0)
        
        # Distances:
        # start -> r1: 10
        # start -> r2: 20
        # r1 -> r2: 5
        def side_effect(rooms_dir, r1, p1, r2, p2, trans):
            if (r1, r2) == ('start', 'room1'): return 10
            if (r1, r2) == ('start', 'room2'): return 20
            if (r1, r2) == ('room1', 'room2'): return 5
            if (r1, r2) == ('room2', 'room1'): return 5
            return 0

        mock_find_steps.side_effect = side_effect
        
        # Probabilities: room1: 0.1, room2: 0.9
        room_probs = {'room1': 0.1, 'room2': 0.9}
        
        # Order [room1, room2]:
        # Expected cost: 0.1 * 10 + 0.9 * 15 = 1.0 + 13.5 = 14.5
        
        # Order [room2, room1]:
        # Expected cost: 0.9 * 20 + 0.1 * 25 = 18.0 + 2.5 = 20.5
        
        # In this case, even though room2 has higher prob, starting with room1 (which is much closer) 
        # might still be better if the distances were different.
        # But with these numbers, [room1, room2] is still better.
        
        # Let's try [room2, room1] being better by making room2 much more likely and closer.
        # If room2 is 0.99 prob and dist(start, r2) = 1, dist(start, r1) = 100
        def side_effect_2(rooms_dir, r1, p1, r2, p2, trans):
            if (r1, r2) == ('start', 'room1'): return 100
            if (r1, r2) == ('start', 'room2'): return 1
            if (r1, r2) == ('room1', 'room2'): return 10
            if (r1, r2) == ('room2', 'room1'): return 10
            return 0
        mock_find_steps.side_effect = side_effect_2
        
        room_probs_2 = {'room1': 0.01, 'room2': 0.99}
        # Order [room1, room2]: 0.01 * 100 + 0.99 * 110 = 1 + 108.9 = 109.9
        # Order [room2, room1]: 0.99 * 1 + 0.01 * 11 = 0.99 + 0.11 = 1.1
        
        cost = expected_search_cost('start', ['room1', 'room2'], room_probs_2)
        self.assertAlmostEqual(cost, 1.1)

if __name__ == "__main__":
    unittest.main()
