#!/usr/bin/env python3
"""
Main Window for A2A Client
"""

import sys
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QToolBar, QMenu, QMenuBar, QApplication, QTabWidget
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon
from pathlib import Path

from agentcomm.core.session_manager import SessionManager
from agentcomm.agents.agent_registry import AgentRegistry
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.mcp.mcp_registry import MCPRegistry
from agentcomm.ui.chat_widget import ChatWidget
from agentcomm.ui.agent_selector import AgentSelector
from agentcomm.ui.settings_dialog import SettingsDialog
from agentcomm.ui.walkthrough import WalkthroughManager
from agentcomm.ui.orchestration.workflow_panel import WorkflowPanel
from agentcomm.orchestration.workflow_store import WorkflowStore

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
        mcp_registry: MCPRegistry,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize main window

        Args:
            session_manager: Session manager instance
            agent_registry: Agent registry instance
            llm_router: LLM router instance
            mcp_registry: MCP registry instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.session_manager = session_manager
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.mcp_registry = mcp_registry
        
        self.setWindowTitle("AgentComm")
        self.setMinimumSize(1000, 700)

        # Set window icon
        logo_path = Path(__file__).parent / "logo.svg"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Apply minimalist dark theme to main window
        self.setStyleSheet("""
            QMainWindow {
                background: #1a1a1a;
            }
            QMenuBar {
                background: #212121;
                color: #e5e7eb;
                padding: 4px;
                font-size: 12px;
                border-bottom: 1px solid #3f3f46;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #3f3f46;
            }
            QMenu {
                background: #2a2a2a;
                color: #e5e7eb;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #3b82f6;
                color: white;
            }
            QStatusBar {
                background: #212121;
                color: #9ca3af;
                font-size: 11px;
                border-top: 1px solid #3f3f46;
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
        self.agent_selector = AgentSelector(self.agent_registry, self.llm_router, self.session_manager)
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

        # Register thread callback for refreshing thread list
        self.session_manager.register_thread_callback(self._thread_safe_refresh_thread_list)

        # Set object names for walkthrough
        self._set_object_names()

        # Initialize walkthrough
        self.walkthrough_manager = WalkthroughManager(self)

        # Show walkthrough for first-time users
        is_first_time = WalkthroughManager.is_first_time_user()
        print(f"Is first time user: {is_first_time}")
        if is_first_time:
            # Delay walkthrough to ensure UI is fully loaded
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.walkthrough_manager.start)
        else:
            print("Not first time - walkthrough will not auto-start")
        
    def create_menu_bar(self):
        """
        Create the menu bar
        """
        # Create the menu bar
        menu_bar = self.menuBar()

        # Create the File menu
        file_menu = menu_bar.addMenu("&File")

        # Add copyright/developer credit
        credit_action = QAction("Built by Keshav", self)
        credit_action.setEnabled(False)  # Make it non-clickable (display only)
        credit_action.setStatusTip("Developer: Keshav")
        file_menu.addAction(credit_action)

        file_menu.addSeparator()

        # Add settings action to File menu for macOS
        import platform
        is_mac = platform.system() == 'Darwin'
        if is_mac:
            settings_action = QAction("Settings", self)
            settings_action.setStatusTip("Open settings")
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
        walkthrough_action = QAction("Show &Walkthrough", self)
        walkthrough_action.setStatusTip("Show the application walkthrough")
        walkthrough_action.triggered.connect(self.show_walkthrough)
        help_menu.addAction(walkthrough_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.setStatusTip("Show the application's About box")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Add a spacer to push settings button to the right
        from PyQt6.QtWidgets import QSizePolicy
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        menu_bar.setCornerWidget(spacer, Qt.Corner.TopLeftCorner)

        # Add settings icon button on the right side (only for non-macOS platforms)
        if not is_mac:
            self.settings_action = QAction("⚙", self)
            self.settings_action.setObjectName("settings_action")
            self.settings_action.setStatusTip("Open settings")
            self.settings_action.triggered.connect(self.open_settings)

            # Create a widget to hold the settings button
            settings_widget = QWidget()
            settings_layout = QHBoxLayout(settings_widget)
            settings_layout.setContentsMargins(8, 0, 8, 0)
            settings_layout.setSpacing(0)

            from PyQt6.QtWidgets import QPushButton
            settings_btn = QPushButton("⚙")
            settings_btn.setFixedSize(32, 32)
            settings_btn.setToolTip("Settings")
            settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            settings_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #9ca3af;
                    border: none;
                    border-radius: 6px;
                    font-size: 18px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background: #3f3f46;
                    color: #3b82f6;
                }
                QPushButton:pressed {
                    background: #3b82f6;
                    color: white;
                }
            """)
            settings_btn.clicked.connect(self.open_settings)
            settings_layout.addWidget(settings_btn)

            menu_bar.setCornerWidget(settings_widget, Qt.Corner.TopRightCorner)
        
        # Create a custom toolbar with settings button for macOS compatibility
        if is_mac:  # macOS
            self.create_toolbar_with_settings()
            
    def create_toolbar(self):
        """
        Create the toolbar
        """
        # Toolbar removed - settings button now in menu bar corner
        pass
        
    def create_toolbar_with_settings(self):
        """
        Create a custom toolbar with settings button for macOS compatibility
        """
        from PyQt6.QtWidgets import QToolBar, QWidget, QHBoxLayout, QPushButton, QSizePolicy
        
        # Create a toolbar that will be placed at the top
        toolbar = QToolBar("Settings Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setObjectName("settings_toolbar")
        
        # Set toolbar style
        toolbar.setStyleSheet("""
            QToolBar {
                background: #212121;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        
        # Create a container widget to hold the settings button
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(0)
        
        # Add a spacer to push the button to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(spacer)
        
        # Create the settings button
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(32, 32)
        settings_btn.setToolTip("Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 6px;
                font-size: 18px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #3f3f46;
                color: #3b82f6;
            }
            QPushButton:pressed {
                background: #3b82f6;
                color: white;
            }
        """)
        settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(settings_btn)
        
        # Add the container to the toolbar
        toolbar.addWidget(container)
        
        # Add the toolbar to the main window
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
    def connect_signals(self):
        """
        Connect signals and slots
        """
        # Connect agent selector signals
        self.agent_selector.agent_selected.connect(self.on_agent_selected)
        self.agent_selector.llm_selected.connect(self.on_llm_selected)

        # Connect thread control signals from agent_selector
        self.agent_selector.thread_selector.currentIndexChanged.connect(self.on_thread_changed)
        self.agent_selector.new_thread_btn.clicked.connect(self.create_new_thread)
        self.agent_selector.rename_thread_btn.clicked.connect(self.rename_current_thread)
        
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
            # Refresh the thread list for this entity
            self.refresh_thread_list()
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
            # Refresh the thread list for this entity
            self.refresh_thread_list()
            self.status_bar.showMessage(f"Connected to LLM: {llm_id}")
        else:
            self.status_bar.showMessage(f"Failed to connect to LLM: {llm_id}")

    def on_thread_changed(self, index: int):
        """
        Handle thread selection change

        Args:
            index: Index of the selected thread
        """
        if index < 0:
            return

        thread_id = self.agent_selector.thread_selector.itemData(index)
        if thread_id and self.session_manager.switch_thread(thread_id):
            # Clear and reload chat
            self.chat_widget.clear_chat()
            self.chat_widget.load_chat_history()

    def create_new_thread(self):
        """
        Create a new thread for the current entity
        """
        if not self.chat_widget.current_entity_id or not self.chat_widget.current_entity_type:
            logger.warning("No entity selected or entity type not set")
            return

        thread_id = self.session_manager.create_thread(
            self.chat_widget.current_entity_id,
            self.chat_widget.current_entity_type
        )
        if thread_id:
            # Switch to the new thread
            if self.session_manager.switch_thread(thread_id):
                # Refresh the thread list and load history
                self.refresh_thread_list()
                self.chat_widget.clear_chat()
                self.chat_widget.load_chat_history()

    def rename_current_thread(self):
        """
        Rename the current thread
        """
        current_thread = self.session_manager.get_current_thread()
        if not current_thread:
            logger.warning("No thread selected")
            return

        # Use styled input dialog
        from agentcomm.ui.custom_dialogs import StyledInputDialog

        new_title, ok = StyledInputDialog.get_text_input(
            self,
            "Rename Thread",
            "Enter new thread name:",
            current_thread.title
        )

        if ok and new_title.strip():
            if self.session_manager.rename_thread(current_thread.thread_id, new_title.strip()):
                self.refresh_thread_list()

    def _thread_safe_refresh_thread_list(self):
        """Thread-safe wrapper for refresh_thread_list"""
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(
            self, "refresh_thread_list",
            Qt.ConnectionType.QueuedConnection
        )

    @pyqtSlot()
    def refresh_thread_list(self):
        """
        Refresh the thread dropdown list in agent_selector
        """
        # Block signals to avoid triggering on_thread_changed
        self.agent_selector.thread_selector.blockSignals(True)

        # Save current selection
        current_thread = self.session_manager.get_current_thread()
        current_thread_id = current_thread.thread_id if current_thread else None

        # Clear and repopulate the dropdown
        self.agent_selector.thread_selector.clear()

        # Get threads for the current entity
        threads = self.session_manager.get_threads_for_entity()

        # Add threads to dropdown
        for thread in threads:
            self.agent_selector.thread_selector.addItem(thread.title, thread.thread_id)

        # Restore selection
        if current_thread_id:
            index = self.agent_selector.thread_selector.findData(current_thread_id)
            if index >= 0:
                self.agent_selector.thread_selector.setCurrentIndex(index)

        # Re-enable signals
        self.agent_selector.thread_selector.blockSignals(False)

        # Update button states
        has_threads = len(threads) > 0
        self.agent_selector.rename_thread_btn.setEnabled(has_threads)
        self.chat_widget.delete_thread_btn.setEnabled(has_threads and len(threads) > 1)
    
    def open_settings(self):
        """
        Open the settings dialog
        """
        settings_dialog = SettingsDialog(self.agent_registry, self.llm_router, self)
        # Connect settings changed signal to reload configuration
        settings_dialog.settings_changed.connect(self.reload_current_configuration)
        settings_dialog.exec()

    def reload_current_configuration(self):
        """
        Reload the current configuration (agent or LLM)
        """
        logger.info("Settings changed, reloading current configuration...")
        
        # Determine current entity from session manager (source of truth)
        entity_id = self.session_manager.current_entity_id
        entity_type = self.session_manager.current_entity_type
        
        if not entity_id or not entity_type:
            return
            
        # Get current thread ID
        current_thread = self.session_manager.get_current_thread()
        thread_id = current_thread.thread_id if current_thread else None
        
        # Re-select the entity to refresh configuration
        # This updates the AgentComm instance in SessionManager with the new configuration
        if entity_type == "agent":
            logger.info(f"Reloading agent {entity_id} configuration")
            self.session_manager.select_agent(entity_id, thread_id)
            
        elif entity_type == "llm":
            logger.info(f"Reloading LLM {entity_id} configuration")
            self.session_manager.select_llm(entity_id, thread_id)
            
        # Update status bar
        self.status_bar.showMessage("Configuration reloaded")
    
    def show_about(self):
        """
        Show the about dialog
        """
        from agentcomm.ui.custom_dialogs import StyledMessageBox

        StyledMessageBox.information(
            self,
            "About AgentComm",
            "AgentComm - A2A Client with Multi-LLM Integration\n\n"
            "A Python-based application designed to interact with A2A "
            "(Agent-to-Agent) protocol-compliant agents while also providing "
            "direct access to various Large Language Models (LLMs)."
        )

    def show_walkthrough(self):
        """
        Show the application walkthrough
        """
        if hasattr(self, 'walkthrough_manager'):
            self.walkthrough_manager.start()

    def _set_object_names(self):
        """
        Set object names for widgets to be used in walkthrough
        """
        # Agent selector widgets
        if hasattr(self.agent_selector, 'agents_list'):
            self.agent_selector.agents_list.setObjectName("agent_list")
        if hasattr(self.agent_selector, 'llms_list'):
            self.agent_selector.llms_list.setObjectName("llms_list")
        if hasattr(self.agent_selector, 'refresh_agents_button'):
            self.agent_selector.refresh_agents_button.setObjectName("refresh_agents_button")
        # Thread controls now in agent_selector
        if hasattr(self.agent_selector, 'thread_selector'):
            self.agent_selector.thread_selector.setObjectName("thread_selector")
        if hasattr(self.agent_selector, 'new_thread_btn'):
            self.agent_selector.new_thread_btn.setObjectName("new_thread_button")
        if hasattr(self.agent_selector, 'rename_thread_btn'):
            self.agent_selector.rename_thread_btn.setObjectName("rename_thread_button")

        # Chat widget components
        if hasattr(self.chat_widget, 'delete_thread_btn'):
            self.chat_widget.delete_thread_btn.setObjectName("delete_thread_button")
        if hasattr(self.chat_widget, 'chat_scroll_area'):
            self.chat_widget.chat_scroll_area.setObjectName("chat_display")
        if hasattr(self.chat_widget, 'message_input'):
            self.chat_widget.message_input.setObjectName("message_input")
        if hasattr(self.chat_widget, 'send_button'):
            self.chat_widget.send_button.setObjectName("send_button")
        if hasattr(self.chat_widget, 'reset_button'):
            self.chat_widget.reset_button.setObjectName("reset_button")
    
    def closeEvent(self, event):
        """
        Handle the close event
        
        Args:
            event: Close event
        """
        # Clean up resources
        event.accept()


