"""Cost tracking service for MegaBook.

Tracks LLM usage costs in both NOK and USD with configurable stop limits.
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from decimal import Decimal, ROUND_HALF_UP

from src.services.llm_provider import UsageInfo


# Exchange rate (should be configurable or fetched from API)
# As of early 2024, approximate rate
USD_TO_NOK = Decimal("10.5")


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for an operation."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    input_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    total_cost_nok: Decimal
    timestamp: datetime
    operation: str
    model: str


@dataclass
class SessionCosts:
    """Cost tracking for a processing session."""
    session_id: str
    start_time: datetime
    costs: List[CostBreakdown]
    total_cost_usd: Decimal
    total_cost_nok: Decimal
    is_stopped: bool = False
    stop_reason: Optional[str] = None
    
    def add_cost(self, cost: CostBreakdown) -> None:
        """Add a cost breakdown to the session."""
        self.costs.append(cost)
        self.total_cost_usd += cost.total_cost_usd
        self.total_cost_nok += cost.total_cost_nok
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "costs": [
                {
                    **asdict(c),
                    "input_cost_usd": str(c.input_cost_usd),
                    "output_cost_usd": str(c.output_cost_usd),
                    "total_cost_usd": str(c.total_cost_usd),
                    "total_cost_nok": str(c.total_cost_nok),
                    "timestamp": c.timestamp.isoformat(),
                }
                for c in self.costs
            ],
            "total_cost_usd": str(self.total_cost_usd),
            "total_cost_nok": str(self.total_cost_nok),
            "is_stopped": self.is_stopped,
            "stop_reason": self.stop_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SessionCosts":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            costs=[
                CostBreakdown(
                    prompt_tokens=c["prompt_tokens"],
                    completion_tokens=c["completion_tokens"],
                    total_tokens=c["total_tokens"],
                    input_cost_usd=Decimal(c["input_cost_usd"]),
                    output_cost_usd=Decimal(c["output_cost_usd"]),
                    total_cost_usd=Decimal(c["total_cost_usd"]),
                    total_cost_nok=Decimal(c["total_cost_nok"]),
                    timestamp=datetime.fromisoformat(c["timestamp"]),
                    operation=c["operation"],
                    model=c["model"],
                )
                for c in data["costs"]
            ],
            total_cost_usd=Decimal(data["total_cost_usd"]),
            total_cost_nok=Decimal(data["total_cost_nok"]),
            is_stopped=data["is_stopped"],
            stop_reason=data.get("stop_reason"),
        )


class CostTrackingService:
    """Service for tracking LLM usage costs."""
    
    def __init__(self, storage_path: Path, cost_limit_nok: float = 10.0) -> None:
        """Initialize the cost tracking service.
        
        Args:
            storage_path: Directory to store cost tracking files
            cost_limit_nok: Cost limit in Norwegian Kroner
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.cost_limit_nok = Decimal(str(cost_limit_nok))
        self._current_session: Optional[SessionCosts] = None
    
    def start_session(self, session_id: str) -> SessionCosts:
        """Start a new cost tracking session.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            New session costs object
        """
        self._current_session = SessionCosts(
            session_id=session_id,
            start_time=datetime.now(),
            costs=[],
            total_cost_usd=Decimal("0"),
            total_cost_nok=Decimal("0"),
        )
        return self._current_session
    
    def end_session(self) -> Optional[SessionCosts]:
        """End the current session and save costs.
        
        Returns:
            Session costs or None if no active session
        """
        if not self._current_session:
            return None
        
        session = self._current_session
        self._save_session(session)
        self._current_session = None
        
        return session
    
    def record_usage(
        self,
        usage: UsageInfo,
        model: str,
        cost_per_1k: Dict[str, float],
        operation: str = "unknown",
    ) -> CostBreakdown:
        """Record usage and calculate costs.
        
        Args:
            usage: Token usage information
            model: Model name
            cost_per_1k: Cost per 1K tokens {"input": float, "output": float}
            operation: Description of the operation
            
        Returns:
            Cost breakdown
        """
        # Calculate costs
        input_cost = Decimal(str(cost_per_1k["input"])) * Decimal(usage.prompt_tokens) / 1000
        output_cost = Decimal(str(cost_per_1k["output"])) * Decimal(usage.completion_tokens) / 1000
        total_usd = (input_cost + output_cost).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        total_nok = (total_usd * USD_TO_NOK).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        
        cost = CostBreakdown(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            input_cost_usd=input_cost.quantize(Decimal("0.0001")),
            output_cost_usd=output_cost.quantize(Decimal("0.0001")),
            total_cost_usd=total_usd,
            total_cost_nok=total_nok,
            timestamp=datetime.now(),
            operation=operation,
            model=model,
        )
        
        if self._current_session:
            self._current_session.add_cost(cost)
        
        return cost
    
    def check_limit(self) -> tuple[bool, Optional[str]]:
        """Check if cost limit has been reached.
        
        Returns:
            Tuple of (should_stop, reason)
        """
        if not self._current_session:
            return False, None
        
        if self._current_session.total_cost_nok >= self.cost_limit_nok:
            return True, f"Cost limit reached: {self._current_session.total_cost_nok} NOK >= {self.cost_limit_nok} NOK"
        
        return False, None
    
    def stop_session(self, reason: str) -> None:
        """Mark the current session as stopped.
        
        Args:
            reason: Reason for stopping
        """
        if self._current_session:
            self._current_session.is_stopped = True
            self._current_session.stop_reason = reason
    
    def resume_session(self) -> None:
        """Resume a stopped session."""
        if self._current_session:
            self._current_session.is_stopped = False
            self._current_session.stop_reason = None
    
    def get_current_session(self) -> Optional[SessionCosts]:
        """Get the current active session."""
        return self._current_session
    
    def _save_session(self, session: SessionCosts) -> None:
        """Save session costs to file."""
        filename = f"{session.session_id}_{session.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.storage_path / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2)
    
    def load_session(self, session_id: str) -> Optional[SessionCosts]:
        """Load a session from file.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session costs or None if not found
        """
        # Find file matching session_id
        for filepath in self.storage_path.glob(f"{session_id}_*.json"):
            with open(filepath, "r", encoding="utf-8") as f:
                return SessionCosts.from_dict(json.load(f))
        
        return None
    
    def list_sessions(self) -> List[Dict]:
        """List all saved sessions.
        
        Returns:
            List of session summaries
        """
        sessions = []
        
        for filepath in self.storage_path.glob("*.json"):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions.append({
                    "session_id": data["session_id"],
                    "start_time": data["start_time"],
                    "total_cost_usd": data["total_cost_usd"],
                    "total_cost_nok": data["total_cost_nok"],
                    "is_stopped": data["is_stopped"],
                })
        
        return sorted(sessions, key=lambda s: s["start_time"], reverse=True)
    
    def get_total_costs(self, days: Optional[int] = None) -> Dict[str, Decimal]:
        """Get total costs across all sessions.
        
        Args:
            days: Optional filter for last N days
            
        Returns:
            Dictionary with total USD and NOK costs
        """
        total_usd = Decimal("0")
        total_nok = Decimal("0")
        
        cutoff = None
        if days:
            cutoff = datetime.now() - __import__('datetime').timedelta(days=days)
        
        for session_data in self.list_sessions():
            if cutoff:
                session_time = datetime.fromisoformat(session_data["start_time"])
                if session_time < cutoff:
                    continue
            
            total_usd += Decimal(session_data["total_cost_usd"])
            total_nok += Decimal(session_data["total_cost_nok"])
        
        return {
            "usd": total_usd,
            "nok": total_nok,
        }