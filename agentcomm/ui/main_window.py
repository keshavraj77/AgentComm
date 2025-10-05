#!/usr/bin/env python3
"""
Main Window for A2A Client
"""

import sys
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QToolBar, QMenu, QMenuBar, QApplication
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon
from pathlib import Path

from agentcomm.core.session_manager import SessionManager
from agentcomm.agents.agent_registry import AgentRegistry
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.ui.chat_widget import ChatWidget
from agentcomm.ui.agent_selector import AgentSelector
from agentcomm.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    Main window for the A2A Client application
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the main window
        
        Args:
            session_manager: Session manager instance
            agent_registry: Agent registry instance
            llm_router: LLM router instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.session_manager = session_manager
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        
        self.setWindowTitle("AgentComm")
        self.setMinimumSize(1000, 700)

        # Set window icon
        logo_path = Path(__file__).parent / "logo.svg"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Apply modern dark theme to main window
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:1 #1e293b);
            }
            QMenuBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e293b, stop:1 #0f172a);
                color: #ffffff;
                padding: 5px;
                font-size: 13px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QMenuBar::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
            }
            QMenu {
                background: #2d3748;
                color: #ffffff;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 30px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
            }
            QStatusBar {
                background: #1e293b;
                color: #ffffff;
                font-size: 12px;
            }
        """)

        # Create the central widget
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        self.setCentralWidget(self.central_widget)
        
        # Create the main layout
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create the splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)
        
        # Create the agent selector
        self.agent_selector = AgentSelector(self.agent_registry, self.llm_router)
        self.splitter.addWidget(self.agent_selector)
        
        # Create the chat widget
        self.chat_widget = ChatWidget(self.session_manager)
        self.splitter.addWidget(self.chat_widget)
        
        # Set the splitter sizes
        self.splitter.setSizes([200, 600])
        
        # Create the status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Create the menu bar
        self.create_menu_bar()
        
        # Create the toolbar
        self.create_toolbar()
        
        # Connect signals and slots
        self.connect_signals()
        
    def create_menu_bar(self):
        """
        Create the menu bar
        """
        # Create the menu bar
        menu_bar = self.menuBar()
        
        # Create the File menu
        file_menu = menu_bar.addMenu("&File")
        
        # Add actions to the File menu
        settings_action = QAction("&Settings", self)
        settings_action.setStatusTip("Open settings dialog")
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Create the Help menu
        help_menu = menu_bar.addMenu("&Help")
        
        # Add actions to the Help menu
        about_action = QAction("&About", self)
        about_action.setStatusTip("Show the application's About box")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_toolbar(self):
        """
        Create the toolbar
        """
        # Create the toolbar
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        
        # Add actions to the toolbar
        settings_action = QAction("Settings", self)
        settings_action.setStatusTip("Open settings dialog")
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)
        
    def connect_signals(self):
        """
        Connect signals and slots
        """
        # Connect agent selector signals
        self.agent_selector.agent_selected.connect(self.on_agent_selected)
        self.agent_selector.llm_selected.connect(self.on_llm_selected)
        
    @pyqtSlot(str)
    def on_agent_selected(self, agent_id: str):
        """
        Handle agent selection
        
        Args:
            agent_id: ID of the selected agent
        """
        logger.info(f"Agent selected: {agent_id}")
        
        # Select the agent in the session manager
        if self.session_manager.select_agent(agent_id):
            # Update the chat widget
            self.chat_widget.set_current_entity(agent_id, "agent")
            self.status_bar.showMessage(f"Connected to agent: {agent_id}")
        else:
            self.status_bar.showMessage(f"Failed to connect to agent: {agent_id}")
    
    @pyqtSlot(str)
    def on_llm_selected(self, llm_id: str):
        """
        Handle LLM selection
        
        Args:
            llm_id: ID of the selected LLM
        """
        logger.info(f"LLM selected: {llm_id}")
        
        # Select the LLM in the session manager
        if self.session_manager.select_llm(llm_id):
            # Update the chat widget
            self.chat_widget.set_current_entity(llm_id, "llm")
            self.status_bar.showMessage(f"Connected to LLM: {llm_id}")
        else:
            self.status_bar.showMessage(f"Failed to connect to LLM: {llm_id}")
    
    def open_settings(self):
        """
        Open the settings dialog
        """
        settings_dialog = SettingsDialog(self.agent_registry, self.llm_router, self)
        settings_dialog.exec()
    
    def show_about(self):
        """
        Show the about dialog
        """
        from PyQt6.QtWidgets import QMessageBox
        
        QMessageBox.about(
            self,
            "About A2A Client",
            "A2A Client with Base LLM Integration\n\n"
            "A Python-based application designed to interact with A2A "
            "(Agent-to-Agent) protocol-compliant agents while also providing "
            "direct access to various Large Language Models (LLMs)."
        )
    
    def closeEvent(self, event):
        """
        Handle the close event
        
        Args:
            event: Close event
        """
        # Clean up resources
        event.accept()


