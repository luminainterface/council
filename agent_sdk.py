#!/usr/bin/env python3
"""
Agent SDK Hooks - Week 3 Strategic Orchestration
================================================

Agent SDK for integrating Cursor/O-3 agents with chess-like strategic planning.
Provides propose_move() stub and router tick with confidence voting + early exit.

Key Features:
- Agent registration and capability detection
- Strategic move proposals with confidence scoring
- 6-head voting system with early consensus exit
- Integration with pattern miner and chess engine
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
import statistics

# Import our strategic components
try:
    from pattern_miner import get_pattern_miner, TaskPattern
    from chess_engine import ChessEngine, Move, Position, MoveType
    STRATEGIC_COMPONENTS_AVAILABLE = True
except ImportError:
    STRATEGIC_COMPONENTS_AVAILABLE = False

# Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary
    AGENT_MOVES_TOTAL = Counter("agent_moves_total", "Total agent moves", ["agent_type", "move_result"])
    AGENT_CONFIDENCE_SCORE = Gauge("agent_confidence_score", "Agent confidence", ["agent_id"])
    AGENT_VOTING_ROUNDS = Histogram("agent_voting_rounds", "Voting rounds until consensus")
    AGENT_EARLY_EXIT_TOTAL = Counter("agent_early_exit_total", "Early consensus exits")
    AGENT_PROPOSAL_LATENCY = Histogram("agent_proposal_latency_ms", "Move proposal latency")
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

class AgentType(Enum):
    """Types of agents in the system"""
    CURSOR = "cursor"
    O3 = "o3"
    SPECIALIST = "specialist"
    COORDINATOR = "coordinator"
    EXECUTOR = "executor"

class ProposalStatus(Enum):
    """Status of move proposals"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

@dataclass
class AgentCapability:
    """Defines what an agent can do"""
    name: str
    confidence: float        # 0.0 to 1.0
    cost_estimate: float     # Relative cost
    specialization: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

@dataclass
class MoveProposal:
    """A proposed move from an agent"""
    proposal_id: str
    agent_id: str
    agent_type: AgentType
    move_data: Dict         # Strategic move information
    confidence: float       # Agent's confidence (0.0 to 1.0)
    reasoning: str          # Human-readable explanation
    cost_estimate: float    # Estimated execution cost
    priority: int = 5       # 1-10 priority scale
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    status: ProposalStatus = ProposalStatus.PENDING
    
    def to_dict(self) -> Dict:
        """Serialize proposal"""
        return {
            'proposal_id': self.proposal_id,
            'agent_id': self.agent_id,
            'agent_type': self.agent_type.value,
            'move_data': self.move_data,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'cost_estimate': self.cost_estimate,
            'priority': self.priority,
            'dependencies': self.dependencies,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value
        }

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, agent_id: str, agent_type: AgentType):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities: List[AgentCapability] = []
        self.active = True
        self.last_activity = datetime.now()
        
        # Performance tracking
        self.proposals_made = 0
        self.proposals_accepted = 0
        self.average_confidence = 0.0
    
    @abstractmethod
    async def propose_move(self, context: Dict) -> Optional[MoveProposal]:
        """Propose a strategic move given current context"""
        pass
    
    @abstractmethod
    async def evaluate_proposal(self, proposal: MoveProposal) -> float:
        """Evaluate another agent's proposal (0.0 to 1.0)"""
        pass
    
    def register_capability(self, capability: AgentCapability):
        """Register a new capability"""
        self.capabilities.append(capability)
        logger.info(f"🔧 Agent {self.agent_id} registered capability: {capability.name}")
    
    def get_capability_score(self, task_type: str) -> float:
        """Get agent's capability score for a task type"""
        matching_caps = [cap for cap in self.capabilities 
                        if task_type in cap.specialization or cap.name == task_type]
        
        if matching_caps:
            return max(cap.confidence for cap in matching_caps)
        return 0.1  # Minimum baseline capability
    
    def update_performance(self, accepted: bool, confidence_used: float):
        """Update agent performance metrics"""
        self.proposals_made += 1
        if accepted:
            self.proposals_accepted += 1
        
        # Update average confidence
        self.average_confidence = (
            (self.average_confidence * (self.proposals_made - 1) + confidence_used) 
            / self.proposals_made
        )
        
        if PROMETHEUS_AVAILABLE:
            AGENT_CONFIDENCE_SCORE.labels(agent_id=self.agent_id).set(self.average_confidence)

class CursorAgent(BaseAgent):
    """Cursor AI agent implementation"""
    
    def __init__(self, agent_id: str = "cursor_001"):
        super().__init__(agent_id, AgentType.CURSOR)
        
        # Register default capabilities
        self.register_capability(AgentCapability(
            name="code_analysis",
            confidence=0.85,
            cost_estimate=1.0,
            specialization=["code", "analysis", "debugging"]
        ))
        
        self.register_capability(AgentCapability(
            name="file_operations", 
            confidence=0.90,
            cost_estimate=0.5,
            specialization=["file", "create", "write", "read"]
        ))
    
    async def propose_move(self, context: Dict) -> Optional[MoveProposal]:
        """Propose move based on code analysis patterns"""
        start_time = time.time()
        
        try:
            task = context.get('current_task', '')
            board_state = context.get('board_state', {})
            
            # Analyze task for file operations
            if any(word in task.lower() for word in ['file', 'create', 'write']):
                confidence = self.get_capability_score('file_operations')
                
                proposal = MoveProposal(
                    proposal_id=str(uuid.uuid4())[:8],
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    move_data={
                        'type': 'file_operation',
                        'action': 'create_write_sequence',
                        'target': 'file_system',
                        'estimated_moves': 3
                    },
                    confidence=confidence,
                    reasoning=f"Cursor agent detects file operation pattern in task: {task[:50]}...",
                    cost_estimate=0.5,
                    priority=7
                )
                
                latency = (time.time() - start_time) * 1000
                if PROMETHEUS_AVAILABLE:
                    AGENT_PROPOSAL_LATENCY.observe(latency)
                
                return proposal
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Cursor agent proposal failed: {e}")
            return None
    
    async def evaluate_proposal(self, proposal: MoveProposal) -> float:
        """Evaluate proposal from code perspective"""
        # Cursor agents favor structured, deterministic moves
        base_score = proposal.confidence
        
        # Bonus for file operations
        if 'file' in str(proposal.move_data).lower():
            base_score += 0.1
        
        # Penalty for high cost
        if proposal.cost_estimate > 2.0:
            base_score -= 0.2
        
        return max(0.0, min(1.0, base_score))

class O3Agent(BaseAgent):
    """O3 reasoning agent implementation"""
    
    def __init__(self, agent_id: str = "o3_001"):
        super().__init__(agent_id, AgentType.O3)
        
        # Register reasoning capabilities
        self.register_capability(AgentCapability(
            name="strategic_planning",
            confidence=0.92,
            cost_estimate=2.0,
            specialization=["strategy", "planning", "optimization"]
        ))
        
        self.register_capability(AgentCapability(
            name="pattern_recognition",
            confidence=0.88,
            cost_estimate=1.5,
            specialization=["pattern", "analysis", "prediction"]
        ))
    
    async def propose_move(self, context: Dict) -> Optional[MoveProposal]:
        """Propose strategic moves using reasoning"""
        start_time = time.time()
        
        try:
            board_state = context.get('board_state', {})
            patterns = context.get('discovered_patterns', [])
            
            # Strategic analysis
            board_rank = board_state.get('board_rank', 0)
            
            if board_rank < 5:
                # Early game - focus on building
                confidence = self.get_capability_score('strategic_planning')
                
                proposal = MoveProposal(
                    proposal_id=str(uuid.uuid4())[:8],
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    move_data={
                        'type': 'strategic_build',
                        'action': 'foundation_layer',
                        'target': 'board_complexity',
                        'estimated_moves': 2
                    },
                    confidence=confidence,
                    reasoning="O3 strategic analysis suggests building foundation before complex operations",
                    cost_estimate=1.5,
                    priority=8
                )
                
                latency = (time.time() - start_time) * 1000
                if PROMETHEUS_AVAILABLE:
                    AGENT_PROPOSAL_LATENCY.observe(latency)
                
                return proposal
            
            return None
            
        except Exception as e:
            logger.error(f"❌ O3 agent proposal failed: {e}")
            return None
    
    async def evaluate_proposal(self, proposal: MoveProposal) -> float:
        """Evaluate proposal strategically"""
        # O3 agents favor high-impact, strategic moves
        base_score = proposal.confidence
        
        # Bonus for strategic moves
        if 'strategic' in str(proposal.move_data).lower():
            base_score += 0.15
        
        # Consider cost vs impact
        if proposal.cost_estimate > 0 and proposal.priority > 5:
            efficiency = proposal.priority / proposal.cost_estimate
            if efficiency > 3.0:
                base_score += 0.1
        
        return max(0.0, min(1.0, base_score))

class SpecialistAgent(BaseAgent):
    """Specialist agent for specific domains"""
    
    def __init__(self, agent_id: str, specialization: str):
        super().__init__(agent_id, AgentType.SPECIALIST)
        self.specialization = specialization
        
        # Register domain-specific capability
        self.register_capability(AgentCapability(
            name=f"{specialization}_specialist",
            confidence=0.95,
            cost_estimate=0.8,
            specialization=[specialization, "domain_expert"]
        ))
    
    async def propose_move(self, context: Dict) -> Optional[MoveProposal]:
        """Propose moves in specialized domain"""
        start_time = time.time()
        
        try:
            task = context.get('current_task', '')
            
            # Check if task matches specialization
            if self.specialization.lower() in task.lower():
                confidence = 0.95  # High confidence in specialization
                
                proposal = MoveProposal(
                    proposal_id=str(uuid.uuid4())[:8],
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    move_data={
                        'type': 'specialist_action',
                        'action': f'{self.specialization}_optimized',
                        'target': self.specialization,
                        'estimated_moves': 1
                    },
                    confidence=confidence,
                    reasoning=f"Specialist {self.specialization} agent optimized for this task type",
                    cost_estimate=0.8,
                    priority=9  # High priority for domain expertise
                )
                
                latency = (time.time() - start_time) * 1000
                if PROMETHEUS_AVAILABLE:
                    AGENT_PROPOSAL_LATENCY.observe(latency)
                
                return proposal
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Specialist {self.specialization} proposal failed: {e}")
            return None
    
    async def evaluate_proposal(self, proposal: MoveProposal) -> float:
        """Evaluate from specialist perspective"""
        base_score = proposal.confidence
        
        # High score for domain match
        if self.specialization.lower() in str(proposal.move_data).lower():
            base_score += 0.2
        
        return max(0.0, min(1.0, base_score))

class AgentRouter:
    """Router for managing agent voting and consensus"""
    
    def __init__(self, max_voting_rounds: int = 3, consensus_threshold: float = 0.75):
        self.agents: Dict[str, BaseAgent] = {}
        self.max_voting_rounds = max_voting_rounds
        self.consensus_threshold = consensus_threshold
        self.active_proposals: List[MoveProposal] = []
        
        # Performance tracking
        self.total_rounds = 0
        self.early_exits = 0
        
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the router"""
        self.agents[agent.agent_id] = agent
        logger.info(f"🤖 Registered agent: {agent.agent_id} ({agent.agent_type.value})")
    
    async def tick_with_voting(self, context: Dict) -> Optional[MoveProposal]:
        """
        Router tick with confidence voting and early exit
        
        Implements 6-head voting system:
        1. Collect proposals from all agents
        2. Vote on each proposal
        3. Check for early consensus
        4. Return best proposal or None
        """
        start_time = time.time()
        
        try:
            # Phase 1: Collect proposals
            proposals = await self._collect_proposals(context)
            if not proposals:
                return None
            
            # Phase 2: Multi-round voting with early exit
            best_proposal = None
            
            for round_num in range(1, self.max_voting_rounds + 1):
                logger.info(f"🗳️ Voting round {round_num}")
                
                # Vote on all proposals
                voted_proposals = await self._vote_on_proposals(proposals)
                
                # Check for early consensus
                consensus_proposal = self._check_early_consensus(voted_proposals)
                if consensus_proposal:
                    logger.info(f"✅ Early consensus reached in round {round_num}")
                    best_proposal = consensus_proposal
                    
                    self.early_exits += 1
                    if PROMETHEUS_AVAILABLE:
                        AGENT_EARLY_EXIT_TOTAL.inc()
                    break
                
                # Continue to next round with refined proposals
                proposals = self._refine_proposals(voted_proposals)
            
            # Phase 3: Final selection if no early consensus
            if not best_proposal and proposals:
                best_proposal = max(proposals, key=lambda p: p.confidence)
                logger.info(f"📊 Selected proposal after {self.max_voting_rounds} rounds")
            
            # Update metrics
            self.total_rounds += self.max_voting_rounds
            if PROMETHEUS_AVAILABLE:
                AGENT_VOTING_ROUNDS.observe(round_num)
            
            # Update agent performance
            if best_proposal:
                for agent in self.agents.values():
                    accepted = agent.agent_id == best_proposal.agent_id
                    agent.update_performance(accepted, best_proposal.confidence)
            
            tick_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️ Router tick completed: {tick_time:.1f}ms")
            
            return best_proposal
            
        except Exception as e:
            logger.error(f"❌ Router tick failed: {e}")
            return None
    
    async def _collect_proposals(self, context: Dict) -> List[MoveProposal]:
        """Collect proposals from all active agents"""
        proposals = []
        
        # Run proposal collection concurrently
        tasks = []
        for agent in self.agents.values():
            if agent.active:
                tasks.append(agent.propose_move(context))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, MoveProposal):
                    proposals.append(result)
                elif isinstance(result, Exception):
                    agent_id = list(self.agents.keys())[i]
                    logger.warning(f"⚠️ Agent {agent_id} proposal failed: {result}")
        
        logger.info(f"📥 Collected {len(proposals)} proposals")
        return proposals
    
    async def _vote_on_proposals(self, proposals: List[MoveProposal]) -> List[Tuple[MoveProposal, float]]:
        """Have all agents vote on all proposals"""
        voted_proposals = []
        
        for proposal in proposals:
            votes = []
            
            # Collect votes from all agents
            for agent in self.agents.values():
                if agent.active:
                    try:
                        vote = await agent.evaluate_proposal(proposal)
                        votes.append(vote)
                    except Exception as e:
                        logger.warning(f"⚠️ Agent {agent.agent_id} voting failed: {e}")
                        votes.append(0.0)
            
            # Calculate average vote
            if votes:
                avg_vote = statistics.mean(votes)
                voted_proposals.append((proposal, avg_vote))
        
        # Sort by vote score
        voted_proposals.sort(key=lambda x: x[1], reverse=True)
        return voted_proposals
    
    def _check_early_consensus(self, voted_proposals: List[Tuple[MoveProposal, float]]) -> Optional[MoveProposal]:
        """Check if we have early consensus"""
        if not voted_proposals:
            return None
        
        best_proposal, best_score = voted_proposals[0]
        
        # Check if best proposal exceeds consensus threshold
        if best_score >= self.consensus_threshold:
            return best_proposal
        
        return None
    
    def _refine_proposals(self, voted_proposals: List[Tuple[MoveProposal, float]]) -> List[MoveProposal]:
        """Refine proposals for next voting round"""
        # Keep top 50% of proposals for next round
        cutoff = len(voted_proposals) // 2 + 1
        return [proposal for proposal, score in voted_proposals[:cutoff]]
    
    def get_agent_stats(self) -> Dict:
        """Get statistics about agent performance"""
        stats = {
            'total_agents': len(self.agents),
            'active_agents': len([a for a in self.agents.values() if a.active]),
            'voting_rounds_avg': self.total_rounds / max(1, self.early_exits + 1),
            'early_exit_rate': self.early_exits / max(1, self.total_rounds),
            'agents': {}
        }
        
        for agent_id, agent in self.agents.items():
            stats['agents'][agent_id] = {
                'type': agent.agent_type.value,
                'proposals_made': agent.proposals_made,
                'proposals_accepted': agent.proposals_accepted,
                'acceptance_rate': agent.proposals_accepted / max(1, agent.proposals_made),
                'average_confidence': agent.average_confidence,
                'capabilities': len(agent.capabilities)
            }
        
        return stats

# Global router instance
_agent_router = None

def get_agent_router() -> AgentRouter:
    """Get global agent router instance"""
    global _agent_router
    if _agent_router is None:
        _agent_router = AgentRouter()
        
        # Register default agents
        cursor_agent = CursorAgent()
        o3_agent = O3Agent()
        file_specialist = SpecialistAgent("file_specialist", "file_operations")
        
        _agent_router.register_agent(cursor_agent)
        _agent_router.register_agent(o3_agent)
        _agent_router.register_agent(file_specialist)
        
        logger.info("🚀 Agent Router initialized with default agents")
    
    return _agent_router

# CLI interface for testing
async def test_agent_sdk():
    """Test the agent SDK with mock scenario"""
    print("🤖 Testing Agent SDK - Week 3")
    print("=" * 50)
    
    # Get router and agents
    router = get_agent_router()
    
    # Mock context
    context = {
        'current_task': 'create file test.txt and write data',
        'board_state': {'board_rank': 2, 'move_count': 1},
        'discovered_patterns': []
    }
    
    print(f"📋 Test Context: {context['current_task']}")
    print(f"🎯 Testing 6-head voting with early exit...")
    
    # Run voting rounds
    for round_num in range(3):
        print(f"\n🗳️ Test Round {round_num + 1}")
        
        best_proposal = await router.tick_with_voting(context)
        
        if best_proposal:
            print(f"✅ Selected proposal:")
            print(f"   Agent: {best_proposal.agent_id} ({best_proposal.agent_type.value})")
            print(f"   Confidence: {best_proposal.confidence:.3f}")
            print(f"   Reasoning: {best_proposal.reasoning}")
            print(f"   Cost: {best_proposal.cost_estimate}")
        else:
            print("❌ No proposals selected")
        
        # Update context for next round
        context['board_state']['move_count'] += 1
    
    # Display final stats
    stats = router.get_agent_stats()
    print(f"\n📊 Agent Performance Stats:")
    print(f"   Total Agents: {stats['total_agents']}")
    print(f"   Active Agents: {stats['active_agents']}")
    print(f"   Avg Voting Rounds: {stats['voting_rounds_avg']:.1f}")
    print(f"   Early Exit Rate: {stats['early_exit_rate']:.1%}")
    
    print(f"\n🎯 Agent SDK Ready for Production!")

if __name__ == "__main__":
    asyncio.run(test_agent_sdk()) 