#!/usr/bin/env python3
"""
Agent Selector Widget for A2A Client
"""

import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QGroupBox, QSplitter, QStyledItemDelegate, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QIcon, QColor, QPainter, QBrush

from agentcomm.agents.agent_registry import AgentRegistry, Agent
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.core.session_manager import SessionManager

logger = logging.getLogger(__name__)


class PulsingDotDelegate(QStyledItemDelegate):
    """
    Custom delegate that draws a pulsing dot for active items
    """

    def __init__(self, session_manager: Optional[SessionManager] = None, parent=None):
        super().__init__(parent)
        self.session_manager = session_manager
        self._pulse_step = 0

        # Setup animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._animate)
        self.timer.start(50)  # Update every 50ms

    def _animate(self):
        """Animate the pulse effect"""
        self._pulse_step = (self._pulse_step + 1) % 100
        # Trigger repaint of all items
        if self.parent():
            self.parent().viewport().update()

    def paint(self, painter, option, index):
        """Custom paint method to draw pulsing dot"""
        # Call the default paint first
        super().paint(painter, option, index)

        # Check if this is the active item
        item_id = index.data(Qt.ItemDataRole.UserRole)
        is_active = False

        if self.session_manager and item_id:
            is_active = (self.session_manager.current_entity_id == item_id)

        if is_active:
            import math
            from PyQt6.QtGui import QPen

            # Calculate pulse opacity - from 0 (invisible) to 1 (fully visible)
            opacity = abs(math.sin(self._pulse_step * math.pi / 50))

            # Determine color based on list type
            list_widget = self.parent()
            if hasattr(list_widget, 'objectName'):
                # Bright yellow for LLMs (stands out against green selection)
                # Orange for Agents (contrasts with purple selection)
                dot_color = QColor("#fbbf24") if "llm" in list_widget.objectName().lower() else QColor("#f97316")
            else:
                dot_color = QColor("#f97316")

            # Draw concentrated pulsing dot on the right side
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Position dot on the right side with some padding
            dot_center_x = option.rect.right() - 15  # 15px from right edge
            dot_center_y = option.rect.center().y()
            dot_radius = 4  # Small concentrated dot

            # Draw solid circle with pulsing opacity
            dot_color.setAlphaF(opacity)
            painter.setBrush(QBrush(dot_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(dot_center_x - dot_radius, dot_center_y - dot_radius, dot_radius * 2, dot_radius * 2)


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
        session_manager: Optional[SessionManager] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the agent selector

        Args:
            agent_registry: Agent registry instance
            llm_router: LLM router instance
            session_manager: Session manager instance (optional)
            parent: Parent widget
        """
        super().__init__(parent)

        self.agent_registry = agent_registry
        self.llm_router = llm_router
        self.session_manager = session_manager

        # Set modern styling for the sidebar with gradient
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a1a, stop:1 #212121);
            }
        """)

        # Create the layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)

        # Create thread selector header
        self.thread_header = QHBoxLayout()
        self.thread_header.setContentsMargins(0, 0, 0, 0)
        self.thread_header.setSpacing(8)

        # Thread selector label
        thread_label = QLabel("Chats:")
        thread_label.setStyleSheet("""
            color: #9ca3af;
            font-size: 12px;
            font-weight: 600;
        """)
        self.thread_header.addWidget(thread_label)

        # Thread dropdown
        self.thread_selector = QComboBox()
        self.thread_selector.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                color: #e5e7eb;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 10px;
                padding-right: 25px;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9ca3af;
                width: 0px;
                height: 0px;
                margin-right: 5px;
            }
            QComboBox::down-arrow:hover {
                border-top: 5px solid #3b82f6;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                color: #e5e7eb;
                selection-background-color: #3b82f6;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
        """)
        self.thread_header.addWidget(self.thread_selector, 1)

        # New thread button (icon only)
        self.new_thread_btn = QPushButton("➕")
        self.new_thread_btn.setFixedSize(32, 32)
        self.new_thread_btn.setToolTip("New chat")
        self.new_thread_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_thread_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6b7280;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #3b82f6;
                color: white;
            }
            QPushButton:pressed {
                background: #2563eb;
                color: white;
            }
        """)
        self.thread_header.addWidget(self.new_thread_btn)

        # Rename thread button (icon only)
        self.rename_thread_btn = QPushButton("✏️")
        self.rename_thread_btn.setFixedSize(32, 32)
        self.rename_thread_btn.setToolTip("Rename chat")
        self.rename_thread_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rename_thread_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6b7280;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #52525b;
                color: white;
            }
            QPushButton:pressed {
                background: #3f3f46;
                color: white;
            }
            QPushButton:disabled {
                color: #4b5563;
                background: transparent;
            }
        """)
        self.thread_header.addWidget(self.rename_thread_btn)

        self.layout.addLayout(self.thread_header)

        # Create the agents group
        self.agents_group = QGroupBox("Agents")
        self.agents_group.setStyleSheet("""
            QGroupBox {
                color: #e5e7eb;
                font-size: 14px;
                font-weight: 600;
                border: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
                margin-top: 10px;
                padding-top: 28px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(102, 126, 234, 0.05), stop:1 rgba(118, 75, 162, 0.05));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 12px 12px;
                background: transparent;
                color: #a78bfa;
                font-weight: 700;
            }
        """)
        self.agents_layout = QVBoxLayout(self.agents_group)

        # Create the agents list
        self.agents_list = QListWidget()
        self.agents_list.setObjectName("agents_list")
        self.agents_list.setMaximumHeight(200)
        self.agents_list.setStyleSheet("""
            QListWidget {
                background: rgba(42, 42, 42, 0.6);
                color: #e5e7eb;
                border: none;
                border-radius: 8px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin: 2px 2px;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background: rgba(102, 126, 234, 0.15);
                border: 1px solid rgba(102, 126, 234, 0.3);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                font-weight: 600;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)

        # Set custom delegate for pulse animation
        self.agents_delegate = PulsingDotDelegate(self.session_manager, self.agents_list)
        self.agents_list.setItemDelegate(self.agents_delegate)

        self.agents_list.itemClicked.connect(self.on_agent_clicked)
        self.agents_layout.addWidget(self.agents_list)

        # Create the refresh agents button
        self.refresh_agents_button = QPushButton("↻")
        self.refresh_agents_button.setFixedHeight(40)
        self.refresh_agents_button.setToolTip("Refresh agents list")
        self.refresh_agents_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_agents_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px;
                font-size: 18px;
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
                color: #e5e7eb;
                font-size: 14px;
                font-weight: 600;
                border: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                border-radius: 12px;
                margin-top: 10px;
                padding-top: 28px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(16, 185, 129, 0.05), stop:1 rgba(5, 150, 105, 0.05));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 12px 12px;
                background: transparent;
                color: #34d399;
                font-weight: 700;
            }
        """)
        self.llms_layout = QVBoxLayout(self.llms_group)
        
        # Create the LLMs list
        self.llms_list = QListWidget()
        self.llms_list.setObjectName("llms_list")
        self.llms_list.setMaximumHeight(200)
        self.llms_list.setStyleSheet("""
            QListWidget {
                background: rgba(42, 42, 42, 0.6);
                color: #e5e7eb;
                border: none;
                border-radius: 8px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                margin: 2px 2px;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background: rgba(16, 185, 129, 0.15);
                border: 1px solid rgba(16, 185, 129, 0.3);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                font-weight: 600;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)

        # Set custom delegate for pulse animation
        self.llms_delegate = PulsingDotDelegate(self.session_manager, self.llms_list)
        self.llms_list.setItemDelegate(self.llms_delegate)

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

        # Add the agents with icon (delegate will draw pulse dot for active one)
        for agent in self.agent_registry.get_all_agents():
            item = QListWidgetItem(f"🤖  {agent.name}")
            item.setData(Qt.ItemDataRole.UserRole, agent.id)
            self.agents_list.addItem(item)
    
    def refresh_llms(self):
        """
        Refresh the LLMs list
        """
        # Clear the list
        self.llms_list.clear()

        # Add the LLMs with icon (delegate will draw pulse dot for active one)
        for llm_id in self.llm_router.get_all_providers().keys():
            item = QListWidgetItem(f"🧠  {llm_id}")
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

            # Trigger repaint to update pulse indicators
            QTimer.singleShot(100, self.agents_list.viewport().update)
            QTimer.singleShot(100, self.llms_list.viewport().update)
    
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

            # Trigger repaint to update pulse indicators
            QTimer.singleShot(100, self.agents_list.viewport().update)
            QTimer.singleShot(100, self.llms_list.viewport().update)


