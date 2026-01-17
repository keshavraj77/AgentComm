#!/usr/bin/env python3
"""
Main Window for AgentComm with Modern Sidebar Navigation
Features icon-based sidebar with collapsible panels (similar to OpenCode UI)
"""

import sys
import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QToolBar, QMenu, QMenuBar, QApplication, QStackedWidget,
    QFrame, QLabel
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QFont
from pathlib import Path

from agentcomm.core.session_manager import SessionManager
from agentcomm.agents.agent_registry import AgentRegistry
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.mcp.mcp_registry import MCPRegistry
from agentcomm.ui.chat_widget import ChatWidget
from agentcomm.ui.sidebar import Sidebar, SidebarIconType
from agentcomm.ui.settings_dialog import SettingsDialog
from agentcomm.ui.mcp_settings import MCPSettingsDialog
from agentcomm.ui.walkthrough import WalkthroughManager
from agentcomm.ui.orchestration.workflow_panel import WorkflowPanel
from agentcomm.orchestration.workflow_store import WorkflowStore

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    Main window for AgentComm with modern sidebar navigation
    """

    def __init__(
        self,
        session_manager: SessionManager,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        mcp_registry: MCPRegistry,
        workflow_store: WorkflowStore,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.session_manager = session_manager
        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.mcp_registry = mcp_registry
        self.workflow_store = workflow_store

        self._current_entity_type = None
        self._current_entity_id = None

        self.setWindowTitle("AgentComm")
        self.setMinimumSize(1100, 700)

        logo_path = Path(__file__).parent / "logo.svg"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        self._setup_ui()
        self._connect_signals()

        self.session_manager.register_thread_callback(self._thread_safe_refresh_thread_list)

        self._set_object_names()

        self.walkthrough_manager = WalkthroughManager(self)

        is_first_time = WalkthroughManager.is_first_time_user()
        print(f"Is first time user: {is_first_time}")
        if is_first_time:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.walkthrough_manager.start)
        else:
            print("Not first time - walkthrough will not auto-start")

    def _setup_ui(self):
        """Setup the main window UI with sidebar and content area"""
        self.setStyleSheet("""
            QMainWindow {
                background: #0f0f0f;
            }
            QMenuBar {
                background: #1a1a1a;
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
                background: #1a1a1a;
                color: #9ca3af;
                font-size: 11px;
                border-top: 1px solid #3f3f46;
            }
        """)

        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background: #0f0f0f;
            }
        """)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = Sidebar(
            self.agent_registry,
            self.llm_router,
            self.session_manager,
            self.mcp_registry
        )
        main_layout.addWidget(self.sidebar)

        content_container = QWidget()
        content_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f0f0f, stop:1 #1a1a1a);
            }
        """)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._content_stack = QStackedWidget()
        content_layout.addWidget(self._content_stack)

        chat_widget = ChatWidget(self.session_manager)
        self._chat_index = self._content_stack.addWidget(chat_widget)

        workflow_panel = WorkflowPanel(
            agent_registry=self.agent_registry,
            llm_router=self.llm_router,
            workflow_store=self.workflow_store,
            webhook_handler=self.session_manager.webhook_handler,
            ngrok_manager=self.session_manager.ngrok_manager
        )
        self._workflow_index = self._content_stack.addWidget(workflow_panel)

        content_container.setLayout(content_layout)
        main_layout.addWidget(content_container, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.create_menu_bar()

        self._workflow_panel = workflow_panel
        self._chat_widget = chat_widget

    def create_menu_bar(self):
        """Create the menu bar"""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        credit_action = QAction("Built by Keshav", self)
        credit_action.setEnabled(False)
        credit_action.setStatusTip("Developer: Keshav")
        file_menu.addAction(credit_action)

        file_menu.addSeparator()

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

        help_menu = menu_bar.addMenu("&Help")

        walkthrough_action = QAction("Show &Walkthrough", self)
        walkthrough_action.setStatusTip("Show the application walkthrough")
        walkthrough_action.triggered.connect(self.show_walkthrough)
        help_menu.addAction(walkthrough_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.setStatusTip("Show the application's About box")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        from PyQt6.QtWidgets import QSizePolicy
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        menu_bar.setCornerWidget(spacer, Qt.Corner.TopLeftCorner)

        if not is_mac:
            self.settings_action = QAction("⚙", self)
            self.settings_action.setObjectName("settings_action")
            self.settings_action.setStatusTip("Open settings")
            self.settings_action.triggered.connect(self.open_settings)

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

        if is_mac:
            self.create_toolbar_with_settings()

    def create_toolbar_with_settings(self):
        """Create a custom toolbar with settings button for macOS compatibility"""
        from PyQt6.QtWidgets import QToolBar, QWidget, QHBoxLayout, QPushButton, QSizePolicy

        toolbar = QToolBar("Settings Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setObjectName("settings_toolbar")

        toolbar.setStyleSheet("""
            QToolBar {
                background: #1a1a1a;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(0)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(spacer)

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

        toolbar.addWidget(container)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _connect_signals(self):
        """Connect signals between components"""
        self.sidebar.entity_selected.connect(self._on_entity_selected)
        self.sidebar.thread_selected.connect(self._on_thread_selected)
        self.sidebar.settings_requested.connect(self._open_settings_menu)
        self.sidebar.view_change_requested.connect(self._on_view_change_requested)

    @pyqtSlot(str, str)
    def _on_entity_selected(self, entity_id: str, entity_type: str):
        """Handle entity selection from sidebar"""
        logger.info(f"Entity selected: {entity_id} ({entity_type})")

        self._current_entity_id = entity_id
        self._current_entity_type = entity_type

        if entity_type == "agent":
            if self.session_manager.select_agent(entity_id):
                self._chat_widget.set_current_entity(entity_id, "agent")
                self.status_bar.showMessage(f"Connected to agent: {entity_id}")
                self.sidebar.set_current_entity(entity_id, entity_type)
                self.refresh_thread_list()
        elif entity_type == "llm":
            if self.session_manager.select_llm(entity_id):
                self._chat_widget.set_current_entity(entity_id, "llm")
                self.status_bar.showMessage(f"Connected to LLM: {entity_id}")
                self.sidebar.set_current_entity(entity_id, entity_type)
                self.refresh_thread_list()

    @pyqtSlot(str)
    def _on_thread_selected(self, thread_id: str):
        """Handle thread selection from sidebar"""
        if thread_id and self.session_manager.switch_thread(thread_id):
            self._chat_widget.clear_chat()
            self._chat_widget.load_chat_history()

    @pyqtSlot(str)
    def _on_view_change_requested(self, view_name: str):
        """Handle view change request from sidebar"""
        if view_name == "chat":
            self._content_stack.setCurrentIndex(self._chat_index)
        elif view_name == "workflows":
            self._content_stack.setCurrentIndex(self._workflow_index)

    @pyqtSlot(object)
    def _open_settings_menu(self, tab_name: Optional[str] = None):
        """Open settings dialog based on active panel or show options"""
        self.open_settings(tab_name)

    def _thread_safe_refresh_thread_list(self):
        """Thread-safe wrapper for refresh_thread_list"""
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(
            self, "refresh_thread_list",
            Qt.ConnectionType.QueuedConnection
        )

    @pyqtSlot()
    def refresh_thread_list(self):
        """Refresh the thread list in sidebar"""
        self.sidebar.load_threads()

    def open_settings(self, tab_name: Optional[str] = None):
        """Open the settings dialog"""
        settings_dialog = SettingsDialog(
            self.agent_registry,
            self.llm_router,
            self.mcp_registry,
            self
        )
        
        if tab_name == "mcp":
            # Find the index of the MCP tab
            for i in range(settings_dialog.tab_widget.count()):
                if settings_dialog.tab_widget.tabText(i) == "MCP Servers":
                    settings_dialog.tab_widget.setCurrentIndex(i)
                    break
        
        settings_dialog.settings_changed.connect(self.reload_current_configuration)
        settings_dialog.exec()

    def open_mcp_settings(self):
        """Open MCP settings dialog"""
        mcp_dialog = MCPSettingsDialog(self.mcp_registry, self)
        mcp_dialog.settings_changed.connect(self.reload_current_configuration)
        mcp_dialog.exec()

    def reload_current_configuration(self):
        """Reload the current configuration (agent or LLM)"""
        logger.info("Settings changed, reloading current configuration...")

        # Refresh MCP settings
        self.session_manager.refresh_mcp_settings()

        entity_id = self.session_manager.current_entity_id
        entity_type = self.session_manager.current_entity_type

        if not entity_id or not entity_type:
            return

        current_thread = self.session_manager.get_current_thread()
        thread_id = current_thread.thread_id if current_thread else None

        if entity_type == "agent":
            logger.info(f"Reloading agent {entity_id} configuration")
            self.session_manager.select_agent(entity_id, thread_id)
        elif entity_type == "llm":
            logger.info(f"Reloading LLM {entity_id} configuration")
            self.session_manager.select_llm(entity_id, thread_id)

        self.status_bar.showMessage("Configuration reloaded")

    def show_about(self):
        """Show the about dialog"""
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
        """Show the application walkthrough"""
        if hasattr(self, 'walkthrough_manager'):
            self.walkthrough_manager.start()

    def _set_object_names(self):
        """Set object names for widgets to be used in walkthrough"""
        if hasattr(self.sidebar, '_threads_list'):
            self.sidebar._threads_list.setObjectName("thread_list")

        if hasattr(self._chat_widget, 'message_input'):
            self._chat_widget.message_input.setObjectName("message_input")
        if hasattr(self._chat_widget, 'send_button'):
            self._chat_widget.send_button.setObjectName("send_button")

    def closeEvent(self, event):
        """Handle the close event"""
        event.accept()


