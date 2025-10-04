#!/usr/bin/env python3
"""
Agent Selector Widget for A2A Client
"""

import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QGroupBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon

from agentcomm.agents.agent_registry import AgentRegistry, Agent
from agentcomm.llm.llm_router import LLMRouter

logger = logging.getLogger(__name__)

class AgentSelector(QWidget):
    """
    Widget for selecting agents and LLMs
    """
    
    agent_selected = pyqtSignal(str)
    llm_selected = pyqtSignal(str)
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the agent selector
        
        Args:
            agent_registry: Agent registry instance
            llm_router: LLM router instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        
        # Create the layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Create the agents group
        self.agents_group = QGroupBox("Agents")
        self.agents_layout = QVBoxLayout(self.agents_group)
        
        # Create the agents list
        self.agents_list = QListWidget()
        self.agents_list.itemClicked.connect(self.on_agent_clicked)
        self.agents_layout.addWidget(self.agents_list)
        
        # Create the refresh agents button
        self.refresh_agents_button = QPushButton("Refresh Agents")
        self.refresh_agents_button.clicked.connect(self.refresh_agents)
        self.agents_layout.addWidget(self.refresh_agents_button)
        
        self.layout.addWidget(self.agents_group)
        
        # Create the LLMs group
        self.llms_group = QGroupBox("LLMs")
        self.llms_layout = QVBoxLayout(self.llms_group)
        
        # Create the LLMs list
        self.llms_list = QListWidget()
        self.llms_list.itemClicked.connect(self.on_llm_clicked)
        self.llms_layout.addWidget(self.llms_list)
        
        self.layout.addWidget(self.llms_group)
        
        # Load the agents and LLMs
        self.refresh_agents()
        self.refresh_llms()
    
    def refresh_agents(self):
        """
        Refresh the agents list
        """
        # Clear the list
        self.agents_list.clear()
        
        # Add the agents
        for agent in self.agent_registry.get_all_agents():
            item = QListWidgetItem(agent.name)
            item.setData(Qt.ItemDataRole.UserRole, agent.id)
            self.agents_list.addItem(item)
    
    def refresh_llms(self):
        """
        Refresh the LLMs list
        """
        # Clear the list
        self.llms_list.clear()
        
        # Add the LLMs
        for llm_id in self.llm_router.get_all_providers().keys():
            item = QListWidgetItem(llm_id)
            item.setData(Qt.ItemDataRole.UserRole, llm_id)
            self.llms_list.addItem(item)
    
    @pyqtSlot(QListWidgetItem)
    def on_agent_clicked(self, item: QListWidgetItem):
        """
        Handle agent selection
        
        Args:
            item: Selected item
        """
        agent_id = item.data(Qt.ItemDataRole.UserRole)
        if agent_id:
            # Deselect any selected LLM
            self.llms_list.clearSelection()
            
            # Emit the agent selected signal
            self.agent_selected.emit(agent_id)
    
    @pyqtSlot(QListWidgetItem)
    def on_llm_clicked(self, item: QListWidgetItem):
        """
        Handle LLM selection
        
        Args:
            item: Selected item
        """
        llm_id = item.data(Qt.ItemDataRole.UserRole)
        if llm_id:
            # Deselect any selected agent
            self.agents_list.clearSelection()
            
            # Emit the LLM selected signal
            self.llm_selected.emit(llm_id)


