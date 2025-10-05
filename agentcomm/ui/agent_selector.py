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

        # Set modern styling for the sidebar
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e293b, stop:1 #0f172a);
            }
        """)

        # Create the layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)

        # Create the agents group
        self.agents_group = QGroupBox("Agents")
        self.agents_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #4a5568;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 5px;
            }
        """)
        self.agents_layout = QVBoxLayout(self.agents_group)

        # Create the agents list
        self.agents_list = QListWidget()
        self.agents_list.setStyleSheet("""
            QListWidget {
                background: #2d3748;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 5px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: #4a5568;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
            }
        """)
        self.agents_list.itemClicked.connect(self.on_agent_clicked)
        self.agents_layout.addWidget(self.agents_list)

        # Create the refresh agents button
        self.refresh_agents_button = QPushButton("Refresh Agents")
        self.refresh_agents_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QPushButton:pressed {
                background: #5a67d8;
            }
        """)
        self.refresh_agents_button.clicked.connect(self.refresh_agents)
        self.agents_layout.addWidget(self.refresh_agents_button)

        self.layout.addWidget(self.agents_group)

        # Create the LLMs group
        self.llms_group = QGroupBox("LLMs")
        self.llms_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid #4a5568;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f093fb, stop:1 #f5576c);
                border-radius: 5px;
            }
        """)
        self.llms_layout = QVBoxLayout(self.llms_group)
        
        # Create the LLMs list
        self.llms_list = QListWidget()
        self.llms_list.setStyleSheet("""
            QListWidget {
                background: #2d3748;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 5px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: #4a5568;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f093fb, stop:1 #f5576c);
            }
        """)
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


