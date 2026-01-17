#!/usr/bin/env python3
"""
Sidebar with Icon Navigation and Dialog-based Agent/LLM Selection
Similar to original AgentSelector - clicking opens dialogs for agent/LLM selection
"""

import logging
from typing import Optional, Dict, List
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QDialog, QScrollArea, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QPropertyAnimation, QEasingCurve

from agentcomm.agents.agent_registry import AgentRegistry, Agent
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.core.session_manager import SessionManager, Thread

logger = logging.getLogger(__name__)


class SidebarIconType(Enum):
    AGENTS = "agents"
    LLMS = "llms"
    MCP = "mcp"
    WORKFLOWS = "workflows"
    THREADS = "threads"
    SETTINGS = "settings"


class ThreadItemWidget(QWidget):
    """Custom widget for thread list items with delete button"""
    
    delete_requested = pyqtSignal(str)  # Emits thread_id
    clicked = pyqtSignal(str)  # Emits thread_id
    
    def __init__(self, thread_id: str, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thread_id = thread_id
        self._is_selected = False
        self._setup_ui(title)
        
    def _setup_ui(self, title: str):
        self._update_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        
        # Thread title with word wrap for long text
        self._title = QLabel(f"💬 {title}")
        self._title.setStyleSheet("""
            QLabel {
                color: #e5e7eb;
                font-size: 12px;
            }
        """)
        # Enable word wrap and disable text elision
        self._title.setWordWrap(True)
        self._title.setTextFormat(Qt.TextFormat.PlainText)
        self._title.setMinimumWidth(50)
        self._title.setMaximumWidth(280)  # Constrain width to force wrapping
        self._title.setSizePolicy(
            self._title.sizePolicy().horizontalPolicy(),
            self._title.sizePolicy().verticalPolicy()
        )
        # Set tooltip to show full text on hover
        self._title.setToolTip(title)
        layout.addWidget(self._title, 1)
        
        # Delete button (hidden by default, shown on hover)
        self._delete_btn = QPushButton("×")
        self._delete_btn.setFixedSize(18, 18)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setToolTip("Delete thread")
        self._delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6b7280;
                border: none;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ef4444;
                color: white;
            }
        """)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        self._delete_btn.hide()  # Hidden by default
        layout.addWidget(self._delete_btn)
    
    def _update_style(self):
        """Update stylesheet based on selection state"""
        if self._is_selected:
            self.setStyleSheet("""
                QWidget {
                    background: #667eea;
                    border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background: transparent;
                    border-radius: 6px;
                }
                QWidget:hover {
                    background: rgba(102, 126, 234, 0.15);
                }
            """)
    
    def setSelected(self, selected: bool):
        """Set the selection state of this widget"""
        self._is_selected = selected
        self._update_style()
        # Update title color for selected state
        if selected:
            self._title.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
        else:
            self._title.setStyleSheet("""
                QLabel {
                    color: #e5e7eb;
                    font-size: 12px;
                }
            """)
    
    def sizeHint(self):
        """Return size hint that accommodates wrapped text"""
        # Force the label to calculate its size based on current width
        if self.width() > 0:
            self._title.setMaximumWidth(self.width() - 40)  # Account for margins and delete button
        
        # Get the label's size hint which accounts for word wrap
        label_height = self._title.sizeHint().height()
        # Add padding from layout margins (top + bottom = 12)
        total_height = label_height + 12
        # Ensure minimum height
        return QSize(300, max(total_height, 36))
        
    def enterEvent(self, event):
        """Show delete button on hover"""
        self._delete_btn.show()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Hide delete button when not hovering"""
        self._delete_btn.hide()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        """Emit clicked signal when widget is clicked"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.thread_id)
        super().mousePressEvent(event)
        
    def _on_delete_clicked(self):
        """Handle delete button click"""
        self.delete_requested.emit(self.thread_id)


class IconButton(QPushButton):
    """Custom icon button with hover effects"""

    def __init__(self, icon_text: str, tooltip: str, parent: Optional[QWidget] = None):
        super().__init__(icon_text, parent)
        self.setFixedSize(50, 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._is_active = False

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 10px;
                font-size: 24px;
                padding: 0px;
                color: #6b7280;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.15);
                color: #3b82f6;
            }
            QPushButton:checked {
                background: rgba(99, 102, 241, 0.2);
                color: #a78bfa;
            }
            QPushButton:checked:hover {
                background: rgba(99, 102, 241, 0.3);
            }
        """)

    def setActive(self, active: bool):
        """Set button as active (selected)"""
        self._is_active = active
        self.setChecked(active)


class AgentSelectionDialog(QDialog):
    """Dialog for selecting an agent"""

    agent_selected = pyqtSignal(str)

    def __init__(
        self,
        agent_registry: AgentRegistry,
        current_entity_id: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.agent_registry = agent_registry
        self.current_entity_id = current_entity_id

        self.setWindowTitle("Select Agent")
        self.setMinimumSize(400, 500)

        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI"""
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1b2e, stop:1 #2d3748);
                border: 2px solid #4f46e5;
                border-radius: 12px;
            }
            QLabel {
                color: #e5e7eb;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self)

        search = QLineEdit()
        search.setPlaceholderText("🔍 Search agents...")
        search.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                color: #e5e7eb;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #667eea;
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        layout.addWidget(search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        self.agents_list = QListWidget()
        self.agents_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-radius: 8px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: rgba(102, 126, 234, 0.2);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                font-weight: 600;
            }
        """)

        for agent in self.agent_registry.get_all_agents():
            item = QListWidgetItem(f"🤖  {agent.name}")
            item.setData(Qt.ItemDataRole.UserRole, agent.id)
            self.agents_list.addItem(item)

        container_layout.addWidget(self.agents_list)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        button_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #e5e7eb;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn, 1)

        select_btn = QPushButton("Select Agent")
        select_btn.setFixedHeight(40)
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
        """)
        select_btn.clicked.connect(self._on_select)
        button_layout.addWidget(select_btn, 1)

        layout.addLayout(button_layout)

        search.textChanged.connect(self._filter_agents)
        self.agents_list.itemDoubleClicked.connect(self._on_agent_double_clicked)

    def _filter_agents(self, text: str):
        """Filter agents by search text"""
        for i in range(self.agents_list.count()):
            item = self.agents_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_select(self):
        """Handle select button click"""
        current_item = self.agents_list.currentItem()
        if current_item:
            agent_id = current_item.data(Qt.ItemDataRole.UserRole)
            if agent_id:
                self.agent_selected.emit(agent_id)
                self.accept()

    def _on_agent_double_clicked(self, item):
        """Handle double click on agent item"""
        self._on_select()


class LLMSelectionDialog(QDialog):
    """Dialog for selecting an LLM"""

    llm_selected = pyqtSignal(str)

    def __init__(
        self,
        llm_router: LLMRouter,
        current_entity_id: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.llm_router = llm_router
        self.current_entity_id = current_entity_id

        self.setWindowTitle("Select LLM Provider")
        self.setMinimumSize(400, 500)

        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI"""
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e3a8a, stop:1 #047857);
                border: 2px solid #059669;
                border-radius: 12px;
            }
            QLabel {
                color: #e5e7eb;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self)

        search = QLineEdit()
        search.setPlaceholderText("🔍 Search LLMs...")
        search.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                color: #e5e7eb;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #10b981;
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        
        # Add MCP Status indicator
        mcp_status_layout = QHBoxLayout()
        from agentcomm.config.settings import Settings
        settings = Settings()
        enabled_mcp = settings.get("mcp.enabled_servers", [])
        mcp_count = len(enabled_mcp)
        
        mcp_label = QLabel(f"🔌 {mcp_count} MCP Servers Enabled")
        mcp_label.setStyleSheet("color: #10b981; font-weight: 600; font-size: 13px;")
        mcp_status_layout.addWidget(mcp_label)
        
        mcp_status_layout.addStretch()
        
        mcp_settings_btn = QPushButton("Manage")
        mcp_settings_btn.setFixedSize(70, 24)
        mcp_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mcp_settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(16, 185, 129, 0.15);
                color: #10b981;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(16, 185, 129, 0.25);
            }
        """)
        mcp_settings_btn.clicked.connect(self._on_mcp_settings_clicked)
        mcp_status_layout.addWidget(mcp_settings_btn)
        
        layout.addLayout(mcp_status_layout)
        
        layout.addWidget(search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        self.llms_list = QListWidget()
        self.llms_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-radius: 8px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: rgba(16, 185, 129, 0.2);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                font-weight: 600;
            }
        """)

        for llm_id in self.llm_router.get_all_providers().keys():
            item = QListWidgetItem(f"🧠  {llm_id}")
            item.setData(Qt.ItemDataRole.UserRole, llm_id)
            self.llms_list.addItem(item)

        container_layout.addWidget(self.llms_list)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        button_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #e5e7eb;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn, 1)

        select_btn = QPushButton("Select LLM")
        select_btn.setFixedHeight(40)
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
            }
        """)
        select_btn.clicked.connect(self._on_select)
        button_layout.addWidget(select_btn, 1)

        layout.addLayout(button_layout)

        search.textChanged.connect(self._filter_llms)
        self.llms_list.itemDoubleClicked.connect(self._on_llm_double_clicked)

    def _on_mcp_settings_clicked(self):
        """Handle manage MCP settings button"""
        # We need to notify the parent to open settings
        # This is a bit tricky, but since it's a dialog, we can just accept/reject 
        # or emit a signal if the parent connects to it.
        # For simplicity, let's close the dialog and tell the parent to open MCP settings.
        self.done(100) # Custom return code for MCP settings

    def _filter_llms(self, text: str):
        """Filter LLMs by search text"""
        for i in range(self.llms_list.count()):
            item = self.llms_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_select(self):
        """Handle select button click"""
        current_item = self.llms_list.currentItem()
        if current_item:
            llm_id = current_item.data(Qt.ItemDataRole.UserRole)
            if llm_id:
                self.llm_selected.emit(llm_id)
                self.accept()

    def _on_llm_double_clicked(self, item):
        """Handle double click on LLM item"""
        self._on_select()


class Sidebar(QWidget):
    """
    Sidebar with icon navigation
    Icons open dialogs for agent/LLM selection (like original AgentSelector)
    """

    entity_selected = pyqtSignal(str, str)
    thread_selected = pyqtSignal(str)
    settings_requested = pyqtSignal(object)
    view_change_requested = pyqtSignal(str)

    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        session_manager: SessionManager,
        mcp_registry,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.session_manager = session_manager
        self.mcp_registry = mcp_registry

        self._current_entity_type = None
        self._current_entity_id = None
        self._expanded_thread_panel = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup sidebar UI"""
        # self.setFixedWidth(60)  <- Removed fixed width constraints
        # self.setMaximumWidth(60)
        self.setStyleSheet("""
            QWidget#sidebar_container {
                background: transparent;
            }
        """)

        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # --- Icon Bar ---
        self._icon_bar = QWidget()
        self._icon_bar.setFixedWidth(60)
        self._icon_bar.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f0f0f, stop:1 #1a1a1a);
                border-right: 1px solid #3f3f46;
            }
        """)
        
        icon_layout = QVBoxLayout(self._icon_bar)
        icon_layout.setContentsMargins(0, 8, 0, 8)
        icon_layout.setSpacing(4)

        self._icon_buttons: Dict[SidebarIconType, IconButton] = {}

        icons_config = [
            (SidebarIconType.THREADS, "💬", "Threads"),
            (SidebarIconType.AGENTS, "🤖", "Agents"),
            (SidebarIconType.LLMS, "🧠", "LLMs"),
            (SidebarIconType.MCP, "🔌", "MCP"),
            (SidebarIconType.WORKFLOWS, "📊", "Workflows"),
            (SidebarIconType.SETTINGS, "⚙️", "Settings"),
        ]

        for icon_type, icon_text, tooltip in icons_config:
            btn = IconButton(icon_text, tooltip)
            btn.clicked.connect(lambda checked, t=icon_type, b=btn: self._on_icon_clicked(t, b))
            icon_layout.addWidget(btn)
            self._icon_buttons[icon_type] = btn

        icon_layout.addStretch()
        
        self._main_layout.addWidget(self._icon_bar)

        self._setup_thread_panel()

    def _setup_thread_panel(self):
        """Setup thread panel (collapsible below icons)"""
        self._thread_panel = QWidget()
        self._thread_panel.setFixedWidth(0)
        self._thread_panel.setMaximumWidth(0)
        self._thread_panel.setStyleSheet("""
            QWidget {
                background: #1a1a1a;
                border-right: 1px solid #3f3f46;
            }
        """)

        layout = QVBoxLayout(self._thread_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet("""
            QWidget {
                background: rgba(45, 45, 45, 0.8);
                border-bottom: 1px solid #3f3f46;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)

        self._title_label = QLabel("💬 Threads")
        self._title_label.setStyleSheet("""
            QLabel {
                color: #e5e7eb;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        header_layout.addWidget(self._title_label)
        
        header_layout.addStretch()
        
        # New thread button in header
        self._new_thread_btn = QPushButton("+")
        self._new_thread_btn.setFixedSize(24, 24)
        self._new_thread_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_thread_btn.setToolTip("New Thread")
        self._new_thread_btn.setStyleSheet("""
            QPushButton {
                background: rgba(102, 126, 234, 0.3);
                color: #a5b4fc;
                border: 1px solid rgba(102, 126, 234, 0.5);
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #667eea;
                color: white;
                border: 1px solid #667eea;
            }
        """)
        self._new_thread_btn.clicked.connect(self._create_new_thread)
        header_layout.addWidget(self._new_thread_btn)

        self._collapse_btn = QPushButton("▲")
        self._collapse_btn.setFixedSize(20, 20)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6b7280;
                border: none;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #e5e7eb;
            }
        """)
        self._collapse_btn.clicked.connect(self._toggle_thread_panel)
        header_layout.addWidget(self._collapse_btn)

        layout.addWidget(header)

        self._threads_list = QListWidget()
        self._threads_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 0px;
                border-radius: 6px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: transparent;
            }
            QListWidget::item:selected {
                background: transparent;
            }
        """)
        # Enable uniform item sizes to be disabled so items can have different heights
        self._threads_list.setUniformItemSizes(False)
        # Set resize mode to adjust contents
        self._threads_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._threads_list.itemClicked.connect(self._on_thread_clicked)
        layout.addWidget(self._threads_list)
        
        self._thread_panel.setLayout(layout)

        self._main_layout.addWidget(self._thread_panel)

    def _on_icon_clicked(self, icon_type: SidebarIconType, button: IconButton):
        """Handle icon button click"""
        if icon_type == SidebarIconType.SETTINGS:
            self.settings_requested.emit(None)
            return

        if icon_type == SidebarIconType.WORKFLOWS:
            self.view_change_requested.emit("workflows")
        elif icon_type == SidebarIconType.MCP:
            self.settings_requested.emit("mcp")

        if self._expanded_thread_panel and icon_type != SidebarIconType.THREADS:
            self._collapse_thread_panel()

        for other_type, other_btn in self._icon_buttons.items():
            if other_type != icon_type:
                other_btn.setActive(False)

        button.setActive(True)

        if icon_type == SidebarIconType.AGENTS:
            self._show_agent_dialog()
        elif icon_type == SidebarIconType.LLMS:
            self._show_llm_dialog()
        elif icon_type == SidebarIconType.THREADS:
            self._toggle_thread_panel()

    def _show_agent_dialog(self):
        """Show agent selection dialog"""
        dialog = AgentSelectionDialog(
            self.agent_registry,
            self._current_entity_id if self._current_entity_type == "agent" else None,
            self
        )
        dialog.agent_selected.connect(self._on_agent_selected)
        dialog.exec()

    def _update_thread_title(self):
        """Update the thread panel title"""
        if self._current_entity_type == "agent":
             self._title_label.setText("🤖 Agent Threads")
        elif self._current_entity_type == "llm":
             self._title_label.setText("🧠 LLM Threads")
        else:
             self._title_label.setText("💬 Threads")

    def _show_llm_dialog(self):
        """Show LLM selection dialog"""
        dialog = LLMSelectionDialog(
            self.llm_router,
            self._current_entity_id if self._current_entity_type == "llm" else None,
            self
        )
        dialog.llm_selected.connect(self._on_llm_selected)
        result = dialog.exec()
        if result == 100:
            self.settings_requested.emit("mcp")

    def _toggle_thread_panel(self):
        """Toggle thread panel visibility"""
        if self._expanded_thread_panel:
            self._collapse_thread_panel()
        else:
            self._expand_thread_panel()

    def _expand_thread_panel(self):
        """Expand thread panel"""
        self._expanded_thread_panel = True
        self._thread_panel.setFixedWidth(320)
        self._thread_panel.setMaximumWidth(320)
        self._collapse_btn.setText("▼")
        self._refresh_threads()

    def _collapse_thread_panel(self):
        """Collapse thread panel"""
        self._expanded_thread_panel = False
        self._thread_panel.setFixedWidth(0)
        self._thread_panel.setMaximumWidth(0)
        self._collapse_btn.setText("▲")

    def _on_agent_selected(self, agent_id: str):
        """Handle agent selection"""
        self.entity_selected.emit(agent_id, "agent")
        self._current_entity_id = agent_id
        self._current_entity_type = "agent"

    def _on_llm_selected(self, llm_id: str):
        """Handle LLM selection"""
        self.entity_selected.emit(llm_id, "llm")
        self._current_entity_id = llm_id
        self._current_entity_type = "llm"

    def _on_thread_clicked(self, item):
        """Handle thread selection"""
        thread_id = item.data(Qt.ItemDataRole.UserRole)
        if thread_id:
            self.thread_selected.emit(thread_id)

    def _create_new_thread(self):
        """Create a new thread"""
        thread_id = self.session_manager.create_thread(
            self._current_entity_id or "default",
            self._current_entity_type or "agent"
        )
        if thread_id:
            self._refresh_threads()
            self.thread_selected.emit(thread_id)

    def _delete_current_thread(self):
        """Delete current thread"""
        current_item = self._threads_list.currentItem()
        if current_item:
            thread_id = current_item.data(Qt.ItemDataRole.UserRole)
            if thread_id and self.session_manager.delete_thread(thread_id):
                self._refresh_threads()

    def _refresh_threads(self):
        """Refresh threads list (internal method)"""
        self._threads_list.clear()
        
        # Filter threads by current entity
        threads = self.session_manager.get_threads_for_entity(self._current_entity_id)
        
        for thread in sorted(threads, key=lambda t: t.created_at, reverse=True):
            # Create list item
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, thread.thread_id)
            self._threads_list.addItem(item)
            
            # Create custom widget with delete button
            thread_widget = ThreadItemWidget(thread.thread_id, thread.title)
            thread_widget.clicked.connect(self._on_thread_widget_clicked)
            thread_widget.delete_requested.connect(self._on_thread_delete_requested)
            self._threads_list.setItemWidget(item, thread_widget)
            
            # Calculate and set size hint based on widget's actual size
            widget_height = thread_widget.sizeHint().height()
            item.setSizeHint(QSize(300, widget_height))
            
        self._update_thread_title()
    
    def _on_thread_widget_clicked(self, thread_id: str):
        """Handle thread widget click"""
        # Update selection styling for all thread widgets
        for i in range(self._threads_list.count()):
            item = self._threads_list.item(i)
            widget = self._threads_list.itemWidget(item)
            if widget and isinstance(widget, ThreadItemWidget):
                widget.setSelected(widget.thread_id == thread_id)
        
        self.thread_selected.emit(thread_id)
    
    def _on_thread_delete_requested(self, thread_id: str):
        """Handle thread delete request"""
        if self.session_manager.delete_thread(thread_id):
            self._refresh_threads()

    def load_threads(self):
        """Load threads list (public method, calls _refresh_threads)"""
        self._refresh_threads()

    def set_current_entity(self, entity_id: str, entity_type: str):
        """Set current entity selection"""
        self._current_entity_id = entity_id
        self._current_entity_type = entity_type
        
        # Auto-refresh threads when entity changes if (threads panel is open OR entity is selected)
        if self._expanded_thread_panel or True: # Always refresh data
            self._refresh_threads()

    def refresh_threads(self):
        """Refresh threads list (public method)"""
        self._refresh_threads()
