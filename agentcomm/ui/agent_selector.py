#!/usr/bin/env python3
"""
Agent Selector Widget for A2A Client
"""

import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QGroupBox, QSplitter, QStyledItemDelegate
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
        """Custom paint method to draw pulsing glow"""
        # Call the default paint first
        super().paint(painter, option, index)

        # Check if this is the active item
        item_id = index.data(Qt.ItemDataRole.UserRole)
        is_active = False

        if self.session_manager and item_id:
            is_active = (self.session_manager.current_entity_id == item_id)

        if is_active:
            import math
            from PyQt6.QtGui import QRadialGradient, QPen

            # Calculate pulse opacity
            opacity = 0.6 + 0.4 * abs(math.sin(self._pulse_step * math.pi / 50))

            # Determine glow color based on list type - use contrasting colors
            list_widget = self.parent()
            if hasattr(list_widget, 'objectName'):
                # Bright yellow for LLMs (stands out against green selection)
                # Orange for Agents (contrasts with purple selection)
                glow_color = QColor("#fbbf24") if "llm" in list_widget.objectName().lower() else QColor("#f97316")
            else:
                glow_color = QColor("#f97316")

            # Draw pulsing glow around the emoji icon area
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Create radial gradient for glow effect
            glow_center_x = option.rect.left() + 30  # Position over the emoji
            glow_center_y = option.rect.center().y()

            gradient = QRadialGradient(glow_center_x, glow_center_y, 22)  # Reduced radius

            # Bright center
            center_color = QColor(glow_color)
            center_color.setAlphaF(opacity * 0.85)
            gradient.setColorAt(0, center_color)

            # Mid glow
            mid_color = QColor(glow_color)
            mid_color.setAlphaF(opacity * 0.45)
            gradient.setColorAt(0.5, mid_color)

            # Outer glow (fade out)
            outer_color = QColor(glow_color)
            outer_color.setAlphaF(0)
            gradient.setColorAt(1, outer_color)

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)

            # Draw the glow circle - reduced radius
            painter.drawEllipse(glow_center_x - 22, glow_center_y - 22, 44, 44)


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
                margin-top: 12px;
                padding-top: 20px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(102, 126, 234, 0.05), stop:1 rgba(118, 75, 162, 0.05));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 12px;
                background: transparent;
                color: #a78bfa;
                font-weight: 700;
            }
        """)
        self.agents_layout = QVBoxLayout(self.agents_group)

        # Create the agents list
        self.agents_list = QListWidget()
        self.agents_list.setObjectName("agents_list")
        self.agents_list.setStyleSheet("""
            QListWidget {
                background: rgba(42, 42, 42, 0.6);
                color: #e5e7eb;
                border: none;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-radius: 6px;
                margin: 3px 2px;
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
                margin-top: 12px;
                padding-top: 20px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(16, 185, 129, 0.05), stop:1 rgba(5, 150, 105, 0.05));
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 12px;
                background: transparent;
                color: #34d399;
                font-weight: 700;
            }
        """)
        self.llms_layout = QVBoxLayout(self.llms_group)
        
        # Create the LLMs list
        self.llms_list = QListWidget()
        self.llms_list.setObjectName("llms_list")
        self.llms_list.setStyleSheet("""
            QListWidget {
                background: rgba(42, 42, 42, 0.6);
                color: #e5e7eb;
                border: none;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px 10px;
                border-radius: 6px;
                margin: 3px 2px;
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


