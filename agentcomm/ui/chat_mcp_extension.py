#!/usr/bin/env python3
"""
Chat Widget with MCP Server Selection Support
Extends ChatWidget to allow selecting MCP servers for LLM calls
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from agentcomm.mcp.mcp_registry import MCPRegistry

logger = logging.getLogger(__name__)


class MCPServerSelector(QFrame):
    """
    MCP Server selector widget for LLM chat
    Allows selecting which MCP servers to use for the current chat
    """

    servers_changed = pyqtSignal(list)

    def __init__(
        self,
        mcp_registry: MCPRegistry,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mcp_registry = mcp_registry
        self._selected_servers: List[str] = []

        self.setFixedHeight(0)
        self.setMaximumHeight(0)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 30, 30, 0.9), stop:1 rgba(20, 20, 20, 0.9));
                border-top: 1px solid #3f3f46;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the MCP selector UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        label = QLabel("🔌 MCP Servers:")
        label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        layout.addWidget(label)

        self._servers_combo = QComboBox()
        self._servers_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                color: #e5e7eb;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 150px;
            }
            QComboBox:hover {
                border: 1px solid #10b981;
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
            }
        """)
        self._servers_combo.currentIndexChanged.connect(self._on_server_selected)
        layout.addWidget(self._servers_combo)

        self._expand_btn = QLabel("▼")
        self._expand_btn.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 10px;
                cursor: pointer;
            }
            QLabel:hover {
                color: #10b981;
            }
        """)
        self._expand_btn.mousePressEvent = self._toggle_expand
        layout.addWidget(self._expand_btn)

        layout.addStretch()

        self._servers_list = QListWidget()
        self._servers_list.setStyleSheet("""
            QListWidget {
                background: rgba(30, 30, 30, 0.8);
                color: #e5e7eb;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: rgba(16, 185, 129, 0.15);
            }
            QListWidget::item:selected {
                background: #10b981;
            }
        """)
        self._servers_list.setMaximumHeight(0)
        layout.addWidget(self._servers_list)

        self._refresh_servers()

    def _refresh_servers(self):
        """Refresh the list of available MCP servers"""
        self._servers_combo.clear()
        self._servers_list.clear()

        for config in self.mcp_registry.get_all_servers():
            self._servers_combo.addItem(f"🔌 {config.name}", config.server_id)

            item = QListWidgetItem(f"🔌 {config.name}")
            item.setData(Qt.ItemDataRole.UserRole, config.server_id)
            item.setCheckState(Qt.CheckState.Checked)
            self._servers_list.addItem(item)

        if self._servers_combo.count() > 0:
            self._servers_combo.setCurrentIndex(0)
            self._selected_servers = [self._servers_combo.currentData()]

    def _on_server_selected(self, index: int):
        """Handle server selection from combo box"""
        if index >= 0:
            server_id = self._servers_combo.itemData(index)
            if server_id:
                if server_id not in self._selected_servers:
                    self._selected_servers.append(server_id)
                    self.servers_changed.emit(self._selected_servers)

    def _toggle_expand(self, event=None):
        """Toggle the servers list expansion"""
        current_height = self._servers_list.maximumHeight()
        if current_height == 0:
            self._servers_list.setMaximumHeight(150)
            self._expand_btn.setText("▲")
            self.setFixedHeight(180)
        else:
            self._servers_list.setMaximumHeight(0)
            self._expand_btn.setText("▼")
            self.setFixedHeight(40)

    def get_selected_servers(self) -> List[str]:
        """Get list of selected server IDs"""
        selected = []
        for i in range(self._servers_list.count()):
            item = self._servers_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def set_selected_servers(self, servers: List[str]):
        """Set the selected servers"""
        self._selected_servers = servers
        for i in range(self._servers_list.count()):
            item = self._servers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) in servers:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    def refresh_servers(self):
        """Refresh the servers list (call after adding/removing servers)"""
        self._refresh_servers()

    def collapse(self):
        """Collapse the selector"""
        self._servers_list.setMaximumHeight(0)
        self._expand_btn.setText("▼")
        self.setFixedHeight(40)

    def expand(self):
        """Expand the selector"""
        self._servers_list.setMaximumHeight(150)
        self._expand_btn.setText("▲")
        self.setFixedHeight(180)


class ChatWidgetMCPExtension:
    """
    Mixin class to add MCP server selection to ChatWidget
    """

    def setup_mcp_extension(self, mcp_registry: MCPRegistry):
        """
        Setup MCP server selection extension

        Args:
            mcp_registry: MCP registry instance
        """
        self.mcp_registry = mcp_registry
        self._mcp_selector = MCPServerSelector(mcp_registry, self)

        if hasattr(self, 'input_layout'):
            self.input_layout.insertWidget(0, self._mcp_selector)

            self._mcp_selector.servers_changed.connect(self._on_mcp_servers_changed)

    def _on_mcp_servers_changed(self, servers: List[str]):
        """Handle MCP servers selection change"""
        logger.info(f"MCP servers selected: {servers}")
        self._selected_mcp_servers = servers

    def get_selected_mcp_servers(self) -> List[str]:
        """Get currently selected MCP servers"""
        if hasattr(self, '_mcp_selector'):
            return self._mcp_selector.get_selected_servers()
        return []

    def set_mcp_servers(self, servers: List[str]):
        """Set selected MCP servers"""
        if hasattr(self, '_mcp_selector'):
            self._mcp_selector.set_selected_servers(servers)

    def refresh_mcp_servers(self):
        """Refresh MCP servers list"""
        if hasattr(self, '_mcp_selector'):
            self._mcp_selector.refresh_servers()

    def show_mcp_selector(self, show: bool = True):
        """Show/hide MCP server selector"""
        if hasattr(self, '_mcp_selector'):
            if show:
                self._mcp_selector.expand()
            else:
                self._mcp_selector.collapse()
