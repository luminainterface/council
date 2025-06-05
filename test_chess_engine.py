#!/usr/bin/env python3
"""
Unit Tests for 2048-Chess α-Engine
==================================

Tests for merge operations, isomorph detection, and strategic moves.
"""

import asyncio
import unittest
from datetime import datetime

from chess_engine import (
    ChessEngine, ChessBoard, Tile, Move, Position,
    TileType, MoveType
)

class TestChessEngine(unittest.TestCase):
    """Unit tests for chess engine components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.board = ChessBoard(size=4)  # Smaller board for testing
        self.engine = ChessEngine()
    
    def test_tile_creation(self):
        """Test tile creation and properties"""
        pos = Position(1, 1)
        tile = Tile(pos, TileType.TASK, value=2)
        
        self.assertEqual(tile.position, pos)
        self.assertEqual(tile.tile_type, TileType.TASK)
        self.assertEqual(tile.value, 2)
        self.assertEqual(tile.power, 4)  # 2^2
    
    def test_tile_merge_compatibility(self):
        """Test tile merge compatibility rules"""
        task_tile = Tile(Position(0, 0), TileType.TASK, value=1)
        agent_tile = Tile(Position(0, 1), TileType.AGENT, value=1)
        same_task = Tile(Position(1, 0), TileType.TASK, value=1)
        empty_tile = Tile(Position(1, 1), TileType.EMPTY)
        
        # Task + Agent should merge
        self.assertTrue(task_tile.can_merge_with(agent_tile))
        
        # Same type/value should merge
        self.assertTrue(task_tile.can_merge_with(same_task))
        
        # Empty tiles cannot merge
        self.assertFalse(task_tile.can_merge_with(empty_tile))
        self.assertFalse(empty_tile.can_merge_with(task_tile))
    
    def test_tile_merge_operation(self):
        """Test actual tile merging"""
        task_tile = Tile(Position(0, 0), TileType.TASK, value=1, 
                         metadata={'action': 'create'})
        agent_tile = Tile(Position(0, 1), TileType.AGENT, value=1,
                         metadata={'capability': 'file_ops'})
        
        # Merge task + agent
        merged = task_tile.merge_with(agent_tile)
        
        self.assertEqual(merged.tile_type, TileType.MERGE)
        self.assertEqual(merged.value, 2)  # 1 + 1
        self.assertIn('action', merged.metadata)
        self.assertIn('capability', merged.metadata)
        self.assertIn('merge_history', merged.metadata)
    
    def test_same_type_merge(self):
        """Test merging tiles of same type"""
        task1 = Tile(Position(0, 0), TileType.TASK, value=2)
        task2 = Tile(Position(0, 1), TileType.TASK, value=2)
        
        merged = task1.merge_with(task2)
        
        self.assertEqual(merged.tile_type, TileType.TASK)
        self.assertEqual(merged.value, 3)  # max(2,2) + 1
    
    def test_board_initialization(self):
        """Test board initialization"""
        board = ChessBoard(size=3)
        
        self.assertEqual(board.size, 3)
        self.assertEqual(len(board.board), 9)  # 3x3
        
        # All positions should be empty
        for pos, tile in board.board.items():
            self.assertEqual(tile.tile_type, TileType.EMPTY)
    
    def test_board_tile_operations(self):
        """Test setting and getting tiles"""
        pos = Position(1, 1)
        tile = Tile(pos, TileType.TASK, value=1)
        
        # Set tile
        success = self.board.set_tile(pos, tile)
        self.assertTrue(success)
        
        # Get tile
        retrieved = self.board.get_tile(pos)
        self.assertEqual(retrieved.tile_type, TileType.TASK)
        self.assertEqual(retrieved.value, 1)
        
        # Check not empty
        self.assertFalse(self.board.is_empty(pos))
    
    def test_board_boundaries(self):
        """Test board boundary handling"""
        # Invalid position should fail
        invalid_pos = Position(10, 10)
        tile = Tile(invalid_pos, TileType.TASK, value=1)
        
        success = self.board.set_tile(invalid_pos, tile)
        self.assertFalse(success)
    
    def test_spawn_move(self):
        """Test spawn move application"""
        pos = Position(1, 1)
        move = Move(
            move_id="test_spawn",
            move_type=MoveType.SPAWN,
            from_pos=None,
            to_pos=pos,
            tile_data={'type': 'task', 'value': 1}
        )
        
        success = self.board.apply_move(move)
        self.assertTrue(success)
        
        # Check tile was created
        tile = self.board.get_tile(pos)
        self.assertEqual(tile.tile_type, TileType.TASK)
        self.assertEqual(tile.value, 1)
    
    def test_regular_move(self):
        """Test regular tile movement"""
        from_pos = Position(0, 0)
        to_pos = Position(0, 1)
        
        # Place initial tile
        initial_tile = Tile(from_pos, TileType.TASK, value=2)
        self.board.set_tile(from_pos, initial_tile)
        
        # Create move
        move = Move(
            move_id="test_move",
            move_type=MoveType.MOVE,
            from_pos=from_pos,
            to_pos=to_pos
        )
        
        success = self.board.apply_move(move)
        self.assertTrue(success)
        
        # Check tile moved
        self.assertTrue(self.board.is_empty(from_pos))
        moved_tile = self.board.get_tile(to_pos)
        self.assertEqual(moved_tile.tile_type, TileType.TASK)
        self.assertEqual(moved_tile.value, 2)
    
    def test_merge_move(self):
        """Test merge move application"""
        pos1 = Position(0, 0)
        pos2 = Position(0, 1)
        
        # Place tiles
        tile1 = Tile(pos1, TileType.TASK, value=1)
        tile2 = Tile(pos2, TileType.AGENT, value=1)
        self.board.set_tile(pos1, tile1)
        self.board.set_tile(pos2, tile2)
        
        # Create merge move
        move = Move(
            move_id="test_merge",
            move_type=MoveType.MERGE,
            from_pos=pos1,
            to_pos=pos2,
            merge_target=pos2
        )
        
        success = self.board.apply_move(move)
        self.assertTrue(success)
        
        # Check merge result
        self.assertTrue(self.board.is_empty(pos1))
        merged_tile = self.board.get_tile(pos2)
        self.assertEqual(merged_tile.tile_type, TileType.MERGE)
        self.assertEqual(merged_tile.value, 2)
    
    def test_execute_move(self):
        """Test execute move for goal completion"""
        pos = Position(1, 1)
        
        # Place merge tile with sufficient value
        merge_tile = Tile(pos, TileType.MERGE, value=3)
        self.board.set_tile(pos, merge_tile)
        
        # Create execute move
        move = Move(
            move_id="test_execute",
            move_type=MoveType.EXECUTE,
            from_pos=None,
            to_pos=pos
        )
        
        success = self.board.apply_move(move)
        self.assertTrue(success)
        
        # Check goal tile created
        goal_tile = self.board.get_tile(pos)
        self.assertEqual(goal_tile.tile_type, TileType.GOAL)
    
    def test_win_condition(self):
        """Test win condition detection"""
        # Initially no win
        self.assertFalse(self.board.check_win_condition())
        
        # Place goal tile
        pos = Position(1, 1)
        goal_tile = Tile(pos, TileType.GOAL, value=3)
        self.board.set_tile(pos, goal_tile)
        
        # Should now win
        self.assertTrue(self.board.check_win_condition())
    
    def test_isomorph_detection(self):
        """Test isomorphic state detection"""
        # Get initial hash
        hash1 = self.board.get_board_state_hash()
        
        # Make some moves and revert
        pos = Position(0, 0)
        tile = Tile(pos, TileType.TASK, value=1)
        self.board.set_tile(pos, tile)
        
        hash2 = self.board.get_board_state_hash()
        self.assertNotEqual(hash1, hash2)
        
        # Remove tile (back to initial state)
        empty_tile = Tile(pos, TileType.EMPTY)
        self.board.set_tile(pos, empty_tile)
        
        hash3 = self.board.get_board_state_hash()
        self.assertEqual(hash1, hash3)
    
    def test_board_rank_calculation(self):
        """Test board rank (complexity) calculation"""
        initial_rank = self.board.board_rank
        self.assertEqual(initial_rank, 0)
        
        # Add some tiles
        tile1 = Tile(Position(0, 0), TileType.TASK, value=2)
        tile2 = Tile(Position(1, 1), TileType.AGENT, value=1)
        
        self.board.set_tile(Position(0, 0), tile1)
        self.board.set_tile(Position(1, 1), tile2)
        
        # Rank should increase
        self.assertGreater(self.board.board_rank, initial_rank)
        expected_rank = 2 + 1 + 2  # values + count
        self.assertEqual(self.board.board_rank, expected_rank)
    
    def test_find_possible_moves(self):
        """Test move discovery"""
        # Empty board should only allow spawns
        moves = self.board.find_possible_moves()
        spawn_moves = [m for m in moves if m.move_type == MoveType.SPAWN]
        self.assertGreater(len(spawn_moves), 0)
        
        # Add tiles to enable more move types
        tile1 = Tile(Position(0, 0), TileType.TASK, value=1)
        tile2 = Tile(Position(0, 1), TileType.AGENT, value=1)
        self.board.set_tile(Position(0, 0), tile1)
        self.board.set_tile(Position(0, 1), tile2)
        
        moves = self.board.find_possible_moves()
        move_types = {m.move_type for m in moves}
        
        # Should have move and merge options
        self.assertIn(MoveType.MOVE, move_types)
        self.assertIn(MoveType.MERGE, move_types)
    
    def test_position_neighbors(self):
        """Test position neighbor calculation"""
        center = Position(2, 2)
        neighbors = center.neighbors(board_size=5)
        
        # Should have 8 neighbors for center position
        self.assertEqual(len(neighbors), 8)
        
        # Corner position should have fewer neighbors
        corner = Position(0, 0)
        corner_neighbors = corner.neighbors(board_size=5)
        self.assertEqual(len(corner_neighbors), 3)
    
    def test_position_distance(self):
        """Test position distance calculation"""
        pos1 = Position(0, 0)
        pos2 = Position(3, 4)
        
        distance = pos1.distance_to(pos2)
        expected = 5.0  # 3-4-5 triangle
        self.assertEqual(distance, expected)

class TestChessEngineIntegration(unittest.TestCase):
    """Integration tests for complete chess engine"""
    
    def setUp(self):
        self.engine = ChessEngine()
    
    def test_engine_initialization(self):
        """Test engine initialization"""
        self.assertFalse(self.engine.running)
        self.assertEqual(len(self.engine.state_history), 0)
        self.assertIsInstance(self.engine.board, ChessBoard)
    
    def test_move_scoring(self):
        """Test move scoring heuristics"""
        # Create moves of different types
        spawn_move = Move("test", MoveType.SPAWN, None, Position(0, 0),
                         tile_data={'type': 'task', 'value': 1})
        merge_move = Move("test", MoveType.MERGE, Position(0, 0), Position(0, 1))
        execute_move = Move("test", MoveType.EXECUTE, None, Position(1, 1))
        
        objective = "create → write → read"
        
        spawn_score = self.engine._score_move(spawn_move, objective)
        merge_score = self.engine._score_move(merge_move, objective)
        execute_score = self.engine._score_move(execute_move, objective)
        
        # Execute should score highest
        self.assertGreater(execute_score, merge_score)
        self.assertGreater(merge_score, spawn_score)

    async def test_short_game(self):
        """Test a short game scenario"""
        # Override max moves for quick test
        self.engine.max_moves = 5
        self.engine.tick_interval = 0.1  # Faster ticks
        
        result = await self.engine.start_game("test_objective")
        
        # Should complete (win or reach move limit)
        self.assertIn(result['status'], ['win', 'incomplete'])
        self.assertLessEqual(result['moves'], 5)
        self.assertGreater(result['time_seconds'], 0)

def run_tests():
    """Run all tests and display results"""
    print("🧪 Running 2048-Chess α-Engine Unit Tests")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestChessEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestChessEngineIntegration))
    
    # Run tests with custom runner
    class CustomTestResult(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.success_count = 0
            
        def addSuccess(self, test):
            super().addSuccess(test)
            self.success_count += 1
            print(f"✅ {test._testMethodName}")
            
        def addError(self, test, err):
            super().addError(test, err)
            print(f"❌ {test._testMethodName}: ERROR")
            
        def addFailure(self, test, err):
            super().addFailure(test, err)
            print(f"❌ {test._testMethodName}: FAIL")
    
    runner = unittest.TextTestRunner(resultclass=CustomTestResult, verbosity=0)
    result = runner.run(suite)
    
    # Summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    successes = total_tests - failures - errors
    
    print(f"\n📊 Test Results:")
    print(f"   Total: {total_tests}")
    print(f"   Passed: {successes}")
    print(f"   Failed: {failures}")
    print(f"   Errors: {errors}")
    
    success_rate = successes / total_tests if total_tests > 0 else 0
    print(f"   Success Rate: {success_rate:.1%}")
    
    if failures == 0 and errors == 0:
        print("\n🎯 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️ {failures + errors} TESTS FAILED")
        return False

if __name__ == "__main__":
    # Run the tests
    success = run_tests()
    
    # Also run the integration test
    print(f"\n🎮 Running Integration Test...")
    
    async def integration_test():
        engine = ChessEngine()
        engine.max_moves = 8  # Target moves
        engine.tick_interval = 0.01  # Very fast for testing
        
        result = await engine.start_game("create → write → read")
        
        print(f"   Result: {result['status']}")
        print(f"   Moves: {result['moves']}/8")
        print(f"   Time: {result['time_seconds']:.3f}s")
        
        return result['status'] == 'win' and result['moves'] <= 8
    
    integration_success = asyncio.run(integration_test())
    
    overall_success = success and integration_success
    print(f"\n{'🎯 CHESS ENGINE READY!' if overall_success else '⚠️ NEEDS OPTIMIZATION'}")
    print(f"Unit Tests: {'✅' if success else '❌'}")
    print(f"Integration: {'✅' if integration_success else '❌'}")
    
    exit(0 if overall_success else 1) 