#!/usr/bin/env python3
"""
MCP Server Settings Dialog
Manage MCP server configurations - add, edit, remove, enable/disable servers
"""

import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QGroupBox, QScrollArea, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog, QFileDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from agentcomm.mcp.mcp_registry import MCPRegistry, MCPServerConfig
from agentcomm.ui.custom_dialogs import StyledMessageBox

logger = logging.getLogger(__name__)


class MCPServerDialog(QDialog):
    """Dialog for adding or editing an MCP server"""

    server_configured = pyqtSignal(MCPServerConfig)

    def __init__(
        self,
        config: Optional[MCPServerConfig] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Configure MCP Server" if config else "Add MCP Server")
        self.setMinimumSize(500, 400)

        self._setup_ui()
        if config:
            self._load_config(config)

    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:1 #1e293b);
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background: #2d3748;
                color: #ffffff;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #667eea;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
        """)

        layout = QVBoxLayout(self)

        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #4a5568;
                border-radius: 10px;
                background: #1e293b;
                padding: 10px;
            }
            QTabBar::tab {
                background: #2d3748;
                color: #ffffff;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
            }
        """)

        basic_tab = self._create_basic_tab()
        transport_tab = self._create_transport_tab()
        env_tab = self._create_env_tab()

        tab_widget.addTab(basic_tab, "Basic")
        tab_widget.addTab(transport_tab, "Transport")
        tab_widget.addTab(env_tab, "Environment")

        layout.addWidget(tab_widget)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _create_basic_tab(self) -> QWidget:
        """Create the basic configuration tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.server_id_edit = QLineEdit()
        layout.addRow("Server ID:", self.server_id_edit)

        self.name_edit = QLineEdit()
        layout.addRow("Display Name:", self.name_edit)

        return tab

    def _create_transport_tab(self) -> QWidget:
        """Create the transport configuration tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["stdio", "sse"])
        self.transport_combo.currentTextChanged.connect(self._on_transport_changed)
        layout.addRow("Transport:", self.transport_combo)

        self.command_edit = QLineEdit()
        layout.addRow("Command:", self.command_edit)

        self.args_edit = QLineEdit()
        layout.addRow("Arguments (comma-separated):", self.args_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://localhost:8080/sse")
        layout.addRow("URL:", self.url_edit)

        return tab

    def _create_env_tab(self) -> QWidget:
        """Create the environment variables tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.env_vars_text = QLineEdit()
        self.env_vars_text.setPlaceholderText("KEY1=value1,KEY2=value2")
        self.env_vars_text.setStyleSheet("""
            QLineEdit {
                background: #2d3748;
                color: #ffffff;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(QLabel("Environment Variables (comma-separated key=value):"))
        layout.addWidget(self.env_vars_text)

        layout.addStretch()
        return tab

    def _on_transport_changed(self, transport: str):
        """Handle transport type change"""
        if transport == "stdio":
            self.command_edit.setEnabled(True)
            self.args_edit.setEnabled(True)
            self.url_edit.setEnabled(False)
        else:
            self.command_edit.setEnabled(False)
            self.args_edit.setEnabled(False)
            self.url_edit.setEnabled(True)

    def _load_config(self, config: MCPServerConfig):
        """Load configuration into the dialog"""
        self.server_id_edit.setText(config.server_id)
        self.server_id_edit.setEnabled(False)
        self.name_edit.setText(config.name)
        self.transport_combo.setCurrentText(config.transport)

        if config.command:
            self.command_edit.setText(config.command)
        if config.args:
            self.args_edit.setText(" ".join(config.args))

        if config.url:
            self.url_edit.setText(config.url)

        if config.env:
            env_str = ",".join(f"{k}={v}" for k, v in config.env.items())
            self.env_vars_text.setText(env_str)

    def _save(self):
        """Save the configuration"""
        server_id = self.server_id_edit.text().strip()
        name = self.name_edit.text().strip()
        transport = self.transport_combo.currentText()

        if not server_id:
            StyledMessageBox.warning(self, "Validation Error", "Server ID is required")
            return

        if not name:
            StyledMessageBox.warning(self, "Validation Error", "Display name is required")
            return

        config = MCPServerConfig(
            server_id=server_id,
            name=name,
            transport=transport
        )

        if transport == "stdio":
            command = self.command_edit.text().strip()
            args_str = self.args_edit.text().strip()
            args = args_str.split() if args_str else []

            if not command:
                StyledMessageBox.warning(self, "Validation Error", "Command is required for stdio transport")
                return

            config.command = command
            config.args = args
        else:
            url = self.url_edit.text().strip()
            if not url:
                StyledMessageBox.warning(self, "Validation Error", "URL is required for SSE transport")
                return
            config.url = url

        env_str = self.env_vars_text.text().strip()
        if env_str:
            env = {}
            for pair in env_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    env[k.strip()] = v.strip()
            config.env = env

        self.server_configured.emit(config)
        self.accept()

    def get_config(self) -> Optional[MCPServerConfig]:
        """Get the configured server"""
        return None


class MCPSettingsDialog(QDialog):
    """
    Main MCP Settings Dialog
    Manage all MCP server configurations
    """

    settings_changed = pyqtSignal()

    def __init__(
        self,
        mcp_registry: MCPRegistry,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mcp_registry = mcp_registry

        self.setWindowTitle("MCP Server Settings")
        self.setMinimumSize(700, 500)

        self._setup_ui()
        self._refresh_servers()

    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:1 #1e293b);
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QGroupBox {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                border: 2px solid #4a5568;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 5px;
                margin-left: 10px;
            }
        """)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        self._servers_group = QGroupBox("MCP Servers")
        self._servers_layout = QVBoxLayout(self._servers_group)

        self._servers_list = QListWidget()
        self._servers_list.setStyleSheet("""
            QListWidget {
                background: rgba(45, 55, 72, 0.5);
                color: #ffffff;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: rgba(102, 126, 234, 0.2);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
            }
        """)
        self._servers_layout.addWidget(self._servers_list)

        self.container_layout.addWidget(self._servers_group)
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Add Server")
        self.add_btn.setFixedHeight(40)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1=0, x2=1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
            }
        """)
        self.add_btn.clicked.connect(self._add_server)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setFixedHeight(40)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background: #2d3748;
                color: #ffffff;
                border: 1px solid #4a5568;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #4a5568;
                border-color: #667eea;
            }
        """)
        self.edit_btn.clicked.connect(self._edit_server)
        button_layout.addWidget(self.edit_btn)

        self.remove_btn = QPushButton("🗑️ Remove")
        self.remove_btn.setFixedHeight(40)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background: #2d3748;
                color: #ef4444;
                border: 1px solid #4a5568;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #ef4444;
                color: white;
                border-color: #ef4444;
            }
        """)
        self.remove_btn.clicked.connect(self._remove_server)
        button_layout.addWidget(self.remove_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop=1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2=1, y2:0,
                    stop:0 #764ba2, stop=1 #667eea);
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _refresh_servers(self):
        """Refresh the servers list"""
        self._servers_list.clear()

        for config in self.mcp_registry.get_all_servers():
            item = QListWidgetItem(f"🔌 {config.name}")
            item.setData(Qt.ItemDataRole.UserRole, config.server_id)

            transport_info = f" ({config.transport})" if config.transport else ""
            item.setToolTip(f"Server ID: {config.server_id}{transport_info}")

            self._servers_list.addItem(item)

    def _add_server(self):
        """Add a new MCP server"""
        dialog = MCPServerDialog(parent=self)
        dialog.server_configured.connect(self._on_server_configured)
        dialog.exec()

    def _edit_server(self):
        """Edit the selected server"""
        current_item = self._servers_list.currentItem()
        if not current_item:
            StyledMessageBox.warning(self, "No Selection", "Please select a server to edit")
            return

        server_id = current_item.data(Qt.ItemDataRole.UserRole)
        config = self.mcp_registry.get_server(server_id)

        if config:
            dialog = MCPServerDialog(config=config, parent=self)
            dialog.server_configured.connect(self._on_server_configured)
            dialog.exec()

    def _remove_server(self):
        """Remove the selected server"""
        current_item = self._servers_list.currentItem()
        if not current_item:
            StyledMessageBox.warning(self, "No Selection", "Please select a server to remove")
            return

        server_id = current_item.data(Qt.ItemDataRole.UserRole)
        server = self.mcp_registry.get_server(server_id)
        server_name = server.name if server else server_id

        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove MCP server '{server_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.mcp_registry.remove_server(server_id)
            self._refresh_servers()
            self.settings_changed.emit()

    def _on_server_configured(self, config: MCPServerConfig):
        """Handle configured server"""
        self.mcp_registry.add_server(config)
        self._refresh_servers()
        self.settings_changed.emit()

    def closeEvent(self, event):
        """Handle close event"""
        event.accept()
