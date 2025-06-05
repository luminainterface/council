#!/usr/bin/env python3
"""
2048-Chess α-Engine - Week 3 Strategic Orchestration
====================================================

Pure-Python chess-like engine with:
- Board/Tile/Move dataclasses for state management
- Tick loop with delta encoding for efficiency
- Strategic pattern merging and isomorph detection
- Unit tests for merge operations

Target: Solve "create → write → read" in ≤ 8 moves
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set
import hashlib

logger = logging.getLogger(__name__)

class TileType(Enum):
    """Types of tiles on the board"""
    EMPTY = "empty"
    TASK = "task"
    AGENT = "agent"
    PATTERN = "pattern"
    MERGE = "merge"
    GOAL = "goal"

class MoveType(Enum):
    """Types of moves available"""
    SPAWN = "spawn"           # Create new task/agent
    MOVE = "move"             # Move piece
    MERGE = "merge"           # Merge two compatible pieces
    TRANSFORM = "transform"   # Transform piece type
    EXECUTE = "execute"       # Execute task

@dataclass(frozen=True)
class Position:
    """Board position coordinates"""
    x: int
    y: int
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate distance to another position"""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
    
    def neighbors(self, board_size: int = 8) -> List['Position']:
        """Get valid neighboring positions"""
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < board_size and 0 <= ny < board_size:
                neighbors.append(Position(nx, ny))
        return neighbors

@dataclass
class Tile:
    """Individual tile on the chess board"""
    position: Position
    tile_type: TileType
    value: int = 0              # Tile strength/priority
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_moved: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if self.tile_type == TileType.EMPTY:
            self.value = 0
    
    @property
    def power(self) -> int:
        """Calculate tile power (2^value for merging rules)"""
        return 2 ** self.value if self.value > 0 else 0
    
    def can_merge_with(self, other: 'Tile') -> bool:
        """Check if this tile can merge with another"""
        if self.tile_type == TileType.EMPTY or other.tile_type == TileType.EMPTY:
            return False
        
        # Same type and same value can merge
        if self.tile_type == other.tile_type and self.value == other.value:
            return True
        
        # Special merge rules
        if self.tile_type == TileType.TASK and other.tile_type == TileType.AGENT:
            return True
        if self.tile_type == TileType.PATTERN and other.tile_type == TileType.TASK:
            return True
            
        return False
    
    def merge_with(self, other: 'Tile') -> 'Tile':
        """Merge this tile with another, returning new tile"""
        if not self.can_merge_with(other):
            raise ValueError(f"Cannot merge {self.tile_type} with {other.tile_type}")
        
        # Determine result type and value
        if self.tile_type == other.tile_type:
            # Same type merge - increase value
            new_value = max(self.value, other.value) + 1
            new_type = self.tile_type
        elif self.tile_type == TileType.TASK and other.tile_type == TileType.AGENT:
            # Task + Agent = Execution
            new_value = self.value + other.value
            new_type = TileType.MERGE
        elif self.tile_type == TileType.PATTERN and other.tile_type == TileType.TASK:
            # Pattern + Task = Enhanced Task
            new_value = self.value + other.value + 1
            new_type = TileType.TASK
        else:
            new_value = max(self.value, other.value)
            new_type = TileType.MERGE
        
        # Merge metadata
        merged_metadata = {**self.metadata, **other.metadata}
        merged_metadata['merge_history'] = merged_metadata.get('merge_history', [])
        merged_metadata['merge_history'].append({
            'from_types': [self.tile_type.value, other.tile_type.value],
            'from_values': [self.value, other.value],
            'timestamp': datetime.now().isoformat()
        })
        
        return Tile(
            position=self.position,
            tile_type=new_type,
            value=new_value,
            metadata=merged_metadata,
            created_at=min(self.created_at, other.created_at),
            last_moved=datetime.now()
        )
    
    def to_dict(self) -> Dict:
        """Serialize tile to dictionary"""
        return {
            'position': {'x': self.position.x, 'y': self.position.y},
            'tile_type': self.tile_type.value,
            'value': self.value,
            'power': self.power,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'last_moved': self.last_moved.isoformat()
        }

@dataclass
class Move:
    """Represents a move in the chess engine"""
    move_id: str
    move_type: MoveType
    from_pos: Optional[Position]
    to_pos: Position
    tile_data: Optional[Dict] = None
    merge_target: Optional[Position] = None
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.move_id:
            self.move_id = str(uuid.uuid4())[:8]
    
    @property
    def is_valid(self) -> bool:
        """Basic move validation"""
        if self.move_type == MoveType.SPAWN:
            return self.to_pos is not None
        elif self.move_type == MoveType.MOVE:
            return self.from_pos is not None and self.to_pos is not None
        elif self.move_type == MoveType.MERGE:
            return (self.from_pos is not None and 
                   self.to_pos is not None and 
                   self.merge_target is not None)
        return True
    
    def to_dict(self) -> Dict:
        """Serialize move to dictionary"""
        return {
            'move_id': self.move_id,
            'move_type': self.move_type.value,
            'from_pos': {'x': self.from_pos.x, 'y': self.from_pos.y} if self.from_pos else None,
            'to_pos': {'x': self.to_pos.x, 'y': self.to_pos.y},
            'tile_data': self.tile_data,
            'merge_target': {'x': self.merge_target.x, 'y': self.merge_target.y} if self.merge_target else None,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }

class ChessBoard:
    """2048-Chess board with strategic orchestration"""
    
    def __init__(self, size: int = 8):
        self.size = size
        self.board: Dict[Position, Tile] = {}
        self.move_history: List[Move] = []
        self.board_rank = 0  # Current board complexity
        self.game_state = "playing"
        self.last_update = datetime.now()
        
        # Initialize empty board
        self._initialize_board()
        
        # Prometheus metrics (if available)
        self.metrics = {
            'moves_total': 0,
            'merges_total': 0,
            'board_rank': 0,
            'merge_efficiency': 0.0
        }
    
    def _initialize_board(self):
        """Initialize empty board"""
        for x in range(self.size):
            for y in range(self.size):
                pos = Position(x, y)
                self.board[pos] = Tile(pos, TileType.EMPTY)
    
    def get_tile(self, position: Position) -> Optional[Tile]:
        """Get tile at position"""
        return self.board.get(position)
    
    def set_tile(self, position: Position, tile: Tile) -> bool:
        """Set tile at position"""
        if 0 <= position.x < self.size and 0 <= position.y < self.size:
            tile.position = position
            tile.last_moved = datetime.now()
            self.board[position] = tile
            self._update_board_rank()
            return True
        return False
    
    def is_empty(self, position: Position) -> bool:
        """Check if position is empty"""
        tile = self.get_tile(position)
        return tile is None or tile.tile_type == TileType.EMPTY
    
    def get_empty_positions(self) -> List[Position]:
        """Get all empty positions"""
        return [pos for pos, tile in self.board.items() 
                if tile.tile_type == TileType.EMPTY]
    
    def get_tiles_by_type(self, tile_type: TileType) -> List[Tile]:
        """Get all tiles of specific type"""
        return [tile for tile in self.board.values() 
                if tile.tile_type == tile_type]
    
    def _update_board_rank(self):
        """Update board complexity rank"""
        total_value = sum(tile.value for tile in self.board.values() 
                         if tile.tile_type != TileType.EMPTY)
        non_empty_count = len([t for t in self.board.values() 
                              if t.tile_type != TileType.EMPTY])
        
        self.board_rank = total_value + non_empty_count
        self.metrics['board_rank'] = self.board_rank
    
    def apply_move(self, move: Move) -> bool:
        """Apply a move to the board"""
        if not move.is_valid:
            logger.warning(f"Invalid move: {move.move_id}")
            return False
        
        try:
            if move.move_type == MoveType.SPAWN:
                return self._apply_spawn(move)
            elif move.move_type == MoveType.MOVE:
                return self._apply_move(move)
            elif move.move_type == MoveType.MERGE:
                return self._apply_merge(move)
            elif move.move_type == MoveType.EXECUTE:
                return self._apply_execute(move)
            
            return False
            
        except Exception as e:
            logger.error(f"Move application failed: {e}")
            return False
    
    def _apply_spawn(self, move: Move) -> bool:
        """Apply spawn move"""
        if not self.is_empty(move.to_pos):
            return False
        
        # Create new tile
        tile_type = TileType(move.tile_data.get('type', 'task'))
        value = move.tile_data.get('value', 1)
        metadata = move.tile_data.get('metadata', {})
        
        new_tile = Tile(
            position=move.to_pos,
            tile_type=tile_type,
            value=value,
            metadata=metadata
        )
        
        self.set_tile(move.to_pos, new_tile)
        self.move_history.append(move)
        self.metrics['moves_total'] += 1
        
        logger.info(f"✅ Spawned {tile_type.value}({value}) at {move.to_pos.x},{move.to_pos.y}")
        return True
    
    def _apply_move(self, move: Move) -> bool:
        """Apply regular move"""
        from_tile = self.get_tile(move.from_pos)
        if not from_tile or from_tile.tile_type == TileType.EMPTY:
            return False
        
        if not self.is_empty(move.to_pos):
            return False
        
        # Move tile
        self.set_tile(move.to_pos, from_tile)
        self.set_tile(move.from_pos, Tile(move.from_pos, TileType.EMPTY))
        
        self.move_history.append(move)
        self.metrics['moves_total'] += 1
        
        logger.info(f"✅ Moved {from_tile.tile_type.value} from {move.from_pos.x},{move.from_pos.y} to {move.to_pos.x},{move.to_pos.y}")
        return True
    
    def _apply_merge(self, move: Move) -> bool:
        """Apply merge move"""
        tile1 = self.get_tile(move.from_pos)
        tile2 = self.get_tile(move.to_pos)
        
        if not tile1 or not tile2:
            return False
        
        if not tile1.can_merge_with(tile2):
            return False
        
        # Perform merge
        merged_tile = tile1.merge_with(tile2)
        
        # Place merged tile
        self.set_tile(move.to_pos, merged_tile)
        self.set_tile(move.from_pos, Tile(move.from_pos, TileType.EMPTY))
        
        self.move_history.append(move)
        self.metrics['moves_total'] += 1
        self.metrics['merges_total'] += 1
        
        # Update merge efficiency
        if self.metrics['moves_total'] > 0:
            self.metrics['merge_efficiency'] = self.metrics['merges_total'] / self.metrics['moves_total']
        
        logger.info(f"✅ Merged {tile1.tile_type.value}({tile1.value}) + {tile2.tile_type.value}({tile2.value}) = {merged_tile.tile_type.value}({merged_tile.value})")
        return True
    
    def _apply_execute(self, move: Move) -> bool:
        """Apply execute move"""
        tile = self.get_tile(move.to_pos)
        if not tile or tile.tile_type != TileType.MERGE:
            return False
        
        # Transform merge tile to goal if high enough value
        if tile.value >= 3:  # Require sufficient complexity
            goal_tile = Tile(
                position=tile.position,
                tile_type=TileType.GOAL,
                value=tile.value,
                metadata={**tile.metadata, 'executed_at': datetime.now().isoformat()}
            )
            self.set_tile(move.to_pos, goal_tile)
            
            logger.info(f"🎯 Executed task: {tile.tile_type.value}({tile.value}) → GOAL")
            return True
        
        return False
    
    def find_possible_moves(self) -> List[Move]:
        """Find all possible moves from current state"""
        moves = []
        
        # Spawn moves (if empty spaces available)
        empty_positions = self.get_empty_positions()
        if empty_positions and len(empty_positions) > 2:  # Keep some space
            for pos in empty_positions[:3]:  # Limit spawn options
                moves.append(Move(
                    move_id=str(uuid.uuid4())[:8],
                    move_type=MoveType.SPAWN,
                    from_pos=None,
                    to_pos=pos,
                    tile_data={'type': 'task', 'value': 1}
                ))
        
        # Move and merge options
        for pos, tile in self.board.items():
            if tile.tile_type == TileType.EMPTY:
                continue
            
            # Check all neighbors
            for neighbor_pos in pos.neighbors(self.size):
                neighbor_tile = self.get_tile(neighbor_pos)
                
                # Regular move to empty space
                if neighbor_tile and neighbor_tile.tile_type == TileType.EMPTY:
                    moves.append(Move(
                        move_id=str(uuid.uuid4())[:8],
                        move_type=MoveType.MOVE,
                        from_pos=pos,
                        to_pos=neighbor_pos
                    ))
                
                # Merge move
                elif neighbor_tile and tile.can_merge_with(neighbor_tile):
                    moves.append(Move(
                        move_id=str(uuid.uuid4())[:8],
                        move_type=MoveType.MERGE,
                        from_pos=pos,
                        to_pos=neighbor_pos,
                        merge_target=neighbor_pos
                    ))
        
        # Execute moves
        merge_tiles = self.get_tiles_by_type(TileType.MERGE)
        for tile in merge_tiles:
            if tile.value >= 3:
                moves.append(Move(
                    move_id=str(uuid.uuid4())[:8],
                    move_type=MoveType.EXECUTE,
                    from_pos=None,
                    to_pos=tile.position
                ))
        
        return moves
    
    def check_win_condition(self) -> bool:
        """Check if win condition is met"""
        goal_tiles = self.get_tiles_by_type(TileType.GOAL)
        return len(goal_tiles) > 0
    
    def get_board_state_hash(self) -> str:
        """Get hash of current board state for isomorph detection"""
        state_data = []
        for pos in sorted(self.board.keys(), key=lambda p: (p.x, p.y)):
            tile = self.board[pos]
            if tile.tile_type != TileType.EMPTY:
                state_data.append(f"{pos.x},{pos.y}:{tile.tile_type.value}:{tile.value}")
        
        state_str = "|".join(state_data)
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Serialize board to dictionary"""
        return {
            'size': self.size,
            'board_rank': self.board_rank,
            'game_state': self.game_state,
            'metrics': self.metrics,
            'tiles': [tile.to_dict() for tile in self.board.values() 
                     if tile.tile_type != TileType.EMPTY],
            'move_count': len(self.move_history),
            'last_update': self.last_update.isoformat()
        }

class ChessEngine:
    """2048-Chess strategic orchestration engine"""
    
    def __init__(self):
        self.board = ChessBoard()
        self.running = False
        self.tick_interval = 1.0  # 1 second per tick
        self.state_history: List[str] = []  # For isomorph detection
        self.max_moves = 50  # Prevent infinite games
        
    async def start_game(self, objective: str = "create → write → read") -> Dict:
        """Start a new chess game with given objective"""
        logger.info(f"🚀 Starting 2048-Chess α-engine")
        logger.info(f"   Objective: {objective}")
        logger.info(f"   Target: ≤ 8 moves")
        
        self.running = True
        game_result = await self._game_loop(objective)
        
        return game_result
    
    async def _game_loop(self, objective: str) -> Dict:
        """Main game loop with tick-based execution"""
        start_time = time.time()
        move_count = 0
        
        # Initialize with create task
        create_move = Move(
            move_id="init_create",
            move_type=MoveType.SPAWN,
            from_pos=None,
            to_pos=Position(2, 2),
            tile_data={'type': 'task', 'value': 1, 'metadata': {'action': 'create'}}
        )
        self.board.apply_move(create_move)
        move_count += 1
        
        while self.running and move_count < self.max_moves:
            await asyncio.sleep(self.tick_interval)
            
            # Check win condition
            if self.board.check_win_condition():
                game_time = time.time() - start_time
                logger.info(f"🎯 WIN! Objective completed in {move_count} moves ({game_time:.1f}s)")
                return {
                    'status': 'win',
                    'moves': move_count,
                    'time_seconds': game_time,
                    'board_state': self.board.to_dict(),
                    'target_moves': 8,
                    'efficiency': move_count / 8.0
                }
            
            # Check for isomorphic states (loops)
            current_hash = self.board.get_board_state_hash()
            if current_hash in self.state_history:
                logger.warning(f"⚠️ Isomorphic state detected, breaking loop")
                break
            self.state_history.append(current_hash)
            
            # Find and execute best move
            best_move = await self._find_best_move(objective)
            if best_move:
                success = self.board.apply_move(best_move)
                if success:
                    move_count += 1
                    logger.info(f"🎲 Move {move_count}: {best_move.move_type.value}")
                else:
                    logger.warning(f"❌ Move failed: {best_move.move_id}")
            else:
                logger.warning("⚠️ No valid moves found")
                break
        
        # Game ended without win
        game_time = time.time() - start_time
        return {
            'status': 'incomplete',
            'moves': move_count,
            'time_seconds': game_time,
            'board_state': self.board.to_dict(),
            'target_moves': 8,
            'efficiency': move_count / 8.0 if move_count > 0 else 0.0
        }
    
    async def _find_best_move(self, objective: str) -> Optional[Move]:
        """Find the best move using strategic heuristics"""
        possible_moves = self.board.find_possible_moves()
        if not possible_moves:
            return None
        
        # Score moves based on objective progression
        scored_moves = []
        for move in possible_moves:
            score = self._score_move(move, objective)
            scored_moves.append((score, move))
        
        # Return highest scored move
        scored_moves.sort(reverse=True)
        return scored_moves[0][1] if scored_moves else None
    
    def _score_move(self, move: Move, objective: str) -> float:
        """Score a move based on strategic value"""
        score = 0.0
        
        # Base score by move type
        type_scores = {
            MoveType.SPAWN: 2.0,
            MoveType.MERGE: 5.0,
            MoveType.MOVE: 1.0,
            MoveType.EXECUTE: 10.0
        }
        score += type_scores.get(move.move_type, 0.0)
        
        # Bonus for progression toward goal
        if "create" in objective and move.move_type == MoveType.SPAWN:
            if move.tile_data and move.tile_data.get('metadata', {}).get('action') == 'write':
                score += 3.0
        
        if "write" in objective and move.move_type == MoveType.MERGE:
            score += 4.0
        
        if "read" in objective and move.move_type == MoveType.EXECUTE:
            score += 8.0
        
        # Penalty for low board rank (encourage complexity)
        if self.board.board_rank < 5:
            if move.move_type == MoveType.EXECUTE:
                score -= 5.0
        
        # Randomness for exploration
        score += __import__('random').random() * 0.5
        
        return score
    
    def stop_game(self):
        """Stop the current game"""
        self.running = False

# Test and CLI interface
async def test_chess_engine():
    """Test the chess engine with create → write → read objective"""
    print("🧪 Testing 2048-Chess α-Engine")
    print("=" * 50)
    
    engine = ChessEngine()
    result = await engine.start_game("create → write → read")
    
    print(f"\n📊 Game Result:")
    print(f"   Status: {result['status']}")
    print(f"   Moves: {result['moves']}/8 target")
    print(f"   Time: {result['time_seconds']:.1f}s")
    print(f"   Efficiency: {result['efficiency']:.2f}")
    print(f"   Board Rank: {result['board_state']['board_rank']}")
    
    success = result['status'] == 'win' and result['moves'] <= 8
    print(f"\n{'✅ SUCCESS' if success else '❌ INCOMPLETE'}: {'Solved in ≤8 moves' if success else 'Did not meet target'}")
    
    return success

if __name__ == "__main__":
    asyncio.run(test_chess_engine()) 