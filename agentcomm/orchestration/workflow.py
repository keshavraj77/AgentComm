"""
Workflow Model

Defines the data structures for workflow definitions including nodes, edges,
and the complete workflow. Follows the existing to_dict/from_dict pattern
used throughout AgentComm for serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class WorkflowNode:
    """
    A node in the workflow graph.

    Attributes:
        node_id: Unique identifier for this node
        node_type: Type of node ("agent", "llm", "start", "end", "conditional", "aggregator", "parallel")
        config: Node-specific configuration (prompt_template, system_prompt, etc.)
        position: Visual position in the graph builder {"x": float, "y": float}
    """
    node_id: str
    node_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowNode':
        """Deserialize from dictionary"""
        return cls(
            node_id=data.get("node_id", ""),
            node_type=data.get("node_type", ""),
            config=data.get("config", {}),
            position=data.get("position", {"x": 0.0, "y": 0.0})
        )


@dataclass
class WorkflowEdge:
    """
    An edge connecting two nodes in the workflow.

    Attributes:
        source: Source node ID
        target: Target node ID
        is_conditional: Whether this is a conditional edge
        condition: Condition expression (for conditional edges)
        mapping: Route mapping for conditional edges {"condition_result": "target_node"}
    """
    source: str
    target: str
    is_conditional: bool = False
    condition: Optional[str] = None
    mapping: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "source": self.source,
            "target": self.target,
            "is_conditional": self.is_conditional,
            "condition": self.condition,
            "mapping": self.mapping
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowEdge':
        """Deserialize from dictionary"""
        return cls(
            source=data.get("source", ""),
            target=data.get("target", ""),
            is_conditional=data.get("is_conditional", False),
            condition=data.get("condition"),
            mapping=data.get("mapping")
        )


@dataclass
class Workflow:
    """
    Complete workflow definition.

    A workflow consists of nodes (agents, LLMs, control nodes) connected
    by edges that define the execution flow.

    Attributes:
        workflow_id: Unique identifier
        name: Human-readable name
        description: Workflow description
        nodes: List of workflow nodes
        edges: List of edges connecting nodes
        entry_node: ID of the entry point node
        created_at: Creation timestamp (ISO format)
        updated_at: Last update timestamp (ISO format)
        metadata: Additional metadata (enable_checkpointing, etc.)
    """
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Workflow"
    description: str = ""
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    entry_node: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize workflow to dictionary.

        Follows the existing pattern used in Thread.to_dict() and
        ChatHistory.save_to_dict() for consistency.
        """
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "entry_node": self.entry_node,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """
        Deserialize workflow from dictionary.

        Follows the existing pattern used in Thread.from_dict() and
        ChatHistory.load_from_dict() for consistency.
        """
        return cls(
            workflow_id=data.get("workflow_id", str(uuid.uuid4())),
            name=data.get("name", "Untitled Workflow"),
            description=data.get("description", ""),
            nodes=[WorkflowNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[WorkflowEdge.from_dict(e) for e in data.get("edges", [])],
            entry_node=data.get("entry_node", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )

    def add_node(self, node: WorkflowNode) -> None:
        """Add a node to the workflow"""
        self.nodes.append(node)
        self.updated_at = datetime.now().isoformat()

    def add_edge(self, edge: WorkflowEdge) -> None:
        """Add an edge to the workflow"""
        self.edges.append(edge)
        self.updated_at = datetime.now().isoformat()

    def remove_node(self, node_id: str) -> None:
        """Remove a node and its connected edges"""
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]
        self.updated_at = datetime.now().isoformat()

    def remove_edge(self, source: str, target: str) -> None:
        """Remove an edge"""
        self.edges = [e for e in self.edges if not (e.source == source and e.target == target)]
        self.updated_at = datetime.now().isoformat()

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by ID"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_outgoing_edges(self, node_id: str) -> List[WorkflowEdge]:
        """Get all edges originating from a node"""
        return [e for e in self.edges if e.source == node_id]

    def get_incoming_edges(self, node_id: str) -> List[WorkflowEdge]:
        """Get all edges targeting a node"""
        return [e for e in self.edges if e.target == node_id]

    def validate(self) -> List[str]:
        """
        Validate the workflow structure.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for entry node
        if not self.entry_node:
            errors.append("No entry node defined")
        elif not self.get_node(self.entry_node):
            errors.append(f"Entry node '{self.entry_node}' not found")

        # Check for orphan nodes (no incoming or outgoing edges)
        node_ids = {n.node_id for n in self.nodes}
        for node in self.nodes:
            if node.node_type not in ("start", "end"):
                has_incoming = any(e.target == node.node_id for e in self.edges)
                has_outgoing = any(e.source == node.node_id for e in self.edges)
                if not has_incoming and not has_outgoing:
                    errors.append(f"Node '{node.node_id}' is not connected")

        # Check for invalid edge references
        for edge in self.edges:
            if edge.source not in node_ids:
                errors.append(f"Edge references unknown source '{edge.source}'")
            if edge.target not in node_ids:
                errors.append(f"Edge references unknown target '{edge.target}'")

        return errors
