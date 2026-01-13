"""
Workflow Store

Persists workflow definitions to JSON files.
Follows the ConfigStore pattern used throughout AgentComm.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from agentcomm.orchestration.workflow import Workflow

logger = logging.getLogger(__name__)


class WorkflowStore:
    """
    Persists workflow definitions to JSON.

    Follows the ConfigStore pattern from agentcomm/core/config_store.py
    for consistency with the rest of the application.

    Usage:
        store = WorkflowStore()
        store.save_workflow(workflow)
        workflow = store.get_workflow(workflow_id)
        all_workflows = store.get_all_workflows()
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the workflow store.

        Args:
            config_dir: Path to config directory (default: agentcomm/config)
        """
        if config_dir is None:
            self.config_dir = Path(__file__).parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

        self.workflows_file = self.config_dir / "workflows.json"
        self.workflows: Dict[str, Workflow] = {}

        self._ensure_config_dir()
        self._load_workflows()

    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_workflows(self) -> None:
        """Load workflows from JSON file"""
        try:
            if self.workflows_file.exists():
                with open(self.workflows_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for wf_data in data.get("workflows", []):
                    workflow = Workflow.from_dict(wf_data)
                    self.workflows[workflow.workflow_id] = workflow

                logger.info(f"Loaded {len(self.workflows)} workflows")
            else:
                logger.info("No workflows file found, starting fresh")
                self._create_default_file()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing workflows.json: {e}")
            self.workflows = {}
        except Exception as e:
            logger.error(f"Error loading workflows: {e}")
            self.workflows = {}

    def _create_default_file(self) -> None:
        """Create default workflows.json file"""
        default_data = {"workflows": []}
        try:
            with open(self.workflows_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2)
            logger.info(f"Created default workflows file at {self.workflows_file}")
        except Exception as e:
            logger.error(f"Error creating default workflows file: {e}")

    def _persist(self) -> bool:
        """Persist all workflows to disk"""
        try:
            data = {
                "workflows": [wf.to_dict() for wf in self.workflows.values()]
            }
            with open(self.workflows_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Persisted {len(self.workflows)} workflows")
            return True
        except Exception as e:
            logger.error(f"Error persisting workflows: {e}")
            return False

    def save_workflow(self, workflow: Workflow) -> bool:
        """
        Save a workflow.

        If the workflow has no ID, one will be generated.
        Updates the updated_at timestamp.

        Args:
            workflow: Workflow to save

        Returns:
            True if saved successfully
        """
        try:
            import uuid
            if not workflow.workflow_id:
                workflow.workflow_id = str(uuid.uuid4())

            workflow.updated_at = datetime.now().isoformat()
            self.workflows[workflow.workflow_id] = workflow

            logger.info(f"Saved workflow: {workflow.name} ({workflow.workflow_id})")
            return self._persist()
        except Exception as e:
            logger.error(f"Error saving workflow: {e}")
            return False

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """
        Get a workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow if found, None otherwise
        """
        return self.workflows.get(workflow_id)

    def get_workflow_by_name(self, name: str) -> Optional[Workflow]:
        """
        Get a workflow by name.

        Args:
            name: Workflow name

        Returns:
            First workflow matching the name, None if not found
        """
        for workflow in self.workflows.values():
            if workflow.name == name:
                return workflow
        return None

    def get_all_workflows(self) -> List[Workflow]:
        """
        Get all workflows.

        Returns:
            List of all workflows, sorted by updated_at (newest first)
        """
        workflows = list(self.workflows.values())
        workflows.sort(key=lambda w: w.updated_at, reverse=True)
        return workflows

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: ID of workflow to delete

        Returns:
            True if deleted successfully
        """
        if workflow_id in self.workflows:
            workflow_name = self.workflows[workflow_id].name
            del self.workflows[workflow_id]
            logger.info(f"Deleted workflow: {workflow_name} ({workflow_id})")
            return self._persist()
        logger.warning(f"Workflow not found: {workflow_id}")
        return False

    def duplicate_workflow(self, workflow_id: str, new_name: Optional[str] = None) -> Optional[Workflow]:
        """
        Create a copy of an existing workflow.

        Args:
            workflow_id: ID of workflow to duplicate
            new_name: Name for the new workflow (default: original name + " (Copy)")

        Returns:
            The new workflow if successful, None otherwise
        """
        original = self.get_workflow(workflow_id)
        if not original:
            return None

        import uuid
        from copy import deepcopy

        # Create a deep copy
        new_workflow_data = original.to_dict()
        new_workflow_data["workflow_id"] = str(uuid.uuid4())
        new_workflow_data["name"] = new_name or f"{original.name} (Copy)"
        new_workflow_data["created_at"] = datetime.now().isoformat()
        new_workflow_data["updated_at"] = datetime.now().isoformat()

        new_workflow = Workflow.from_dict(new_workflow_data)
        self.save_workflow(new_workflow)

        return new_workflow

    def export_workflow(self, workflow_id: str) -> Optional[str]:
        """
        Export a workflow to JSON string.

        Args:
            workflow_id: ID of workflow to export

        Returns:
            JSON string representation of the workflow
        """
        workflow = self.get_workflow(workflow_id)
        if workflow:
            return json.dumps(workflow.to_dict(), indent=2)
        return None

    def import_workflow(self, json_str: str) -> Optional[Workflow]:
        """
        Import a workflow from JSON string.

        Generates a new ID to avoid conflicts.

        Args:
            json_str: JSON string representation of a workflow

        Returns:
            The imported workflow if successful
        """
        try:
            import uuid
            data = json.loads(json_str)

            # Generate new ID to avoid conflicts
            data["workflow_id"] = str(uuid.uuid4())
            data["created_at"] = datetime.now().isoformat()
            data["updated_at"] = datetime.now().isoformat()

            workflow = Workflow.from_dict(data)
            self.save_workflow(workflow)

            logger.info(f"Imported workflow: {workflow.name}")
            return workflow
        except Exception as e:
            logger.error(f"Error importing workflow: {e}")
            return None

    def reload(self) -> None:
        """Reload workflows from disk"""
        self.workflows = {}
        self._load_workflows()
