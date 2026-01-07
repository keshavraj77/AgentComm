#!/usr/bin/env python3
"""
Settings Dialog for A2A Client
"""

import logging
from typing import Optional, Dict, Any, List, Union

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QFormLayout, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from agentcomm.agents.agent_registry import AgentRegistry, Agent, AgentAuthentication, AgentCapabilities
from agentcomm.llm.llm_router import LLMRouter
from agentcomm.ui.custom_dialogs import StyledMessageBox

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """
    Dialog for configuring application settings
    """
    
    settings_changed = pyqtSignal()
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_router: LLMRouter,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the settings dialog
        
        Args:
            agent_registry: Agent registry instance
            llm_router: LLM router instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.agent_registry = agent_registry
        self.llm_router = llm_router

        # Store references to LLM input fields for batch saving
        self.llm_inputs = {}

        self.setWindowTitle("Settings")
        self.setMinimumSize(800, 600)

        # Apply modern dark theme
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:1 #1e293b);
            }
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
                margin: 2px;
                border-radius: 8px 8px 0px 0px;
                font-size: 14px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #4a5568;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #2d3748;
                color: #ffffff;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #667eea;
                background: #1a202c;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background: #2d3748;
                color: #ffffff;
                selection-background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border: 2px solid #4a5568;
                border-radius: 8px;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #4a5568;
                border-radius: 5px;
                background: #2d3748;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #667eea;
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: 2px solid #667eea;
            }
            QCheckBox::indicator:checked:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QGroupBox {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                border: 2px solid #4a5568;
                border-radius: 10px;
                margin-top: 15px;
                padding-top: 20px;
                background: rgba(45, 55, 72, 0.3);
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
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #1e293b;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background: #1e293b;
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
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
            QPushButton:pressed {
                background: #5a67d8;
                padding-top: 12px;
                padding-bottom: 8px;
            }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background: #4a5568;
                border-radius: 4px;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background: #667eea;
            }
        """)

        # Create the layout
        self.layout = QVBoxLayout(self)
        
        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        # Create the agents tab
        self.agents_tab = QWidget()
        self.tab_widget.addTab(self.agents_tab, "Agents")
        self.setup_agents_tab()
        
        # Create the LLMs tab
        self.llms_tab = QWidget()
        self.tab_widget.addTab(self.llms_tab, "LLMs")
        self.setup_llms_tab()
        
        # Create the general tab
        self.general_tab = QWidget()
        self.tab_widget.addTab(self.general_tab, "General")
        self.setup_general_tab()
        
        # Create the buttons
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.apply_and_accept)
        self.ok_button.setObjectName("ok_button")  # Add object name for easier identification
        self.button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.button_layout.addWidget(self.cancel_button)
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        self.apply_button.setObjectName("apply_button")  # Add object name for easier identification
        self.button_layout.addWidget(self.apply_button)
        
        self.layout.addLayout(self.button_layout)
    
    def setup_agents_tab(self):
        """
        Set up the agents tab
        """
        # Create the layout
        layout = QVBoxLayout(self.agents_tab)
        
        # Create the agents list
        self.agents_group = QGroupBox("Agents")
        agents_layout = QVBoxLayout(self.agents_group)
        
        # Create a scroll area for the agents
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Create a widget to hold the agent forms
        self.agents_container = QWidget()
        self.agents_container.setStyleSheet("background: transparent;")
        self.agents_layout = QVBoxLayout(self.agents_container)
        self.agents_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(self.agents_container)
        
        agents_layout.addWidget(scroll_area)
        
        # Create the add agent button
        self.add_agent_button = QPushButton("Add Agent")
        self.add_agent_button.clicked.connect(self.add_agent)
        agents_layout.addWidget(self.add_agent_button)
        
        layout.addWidget(self.agents_group)
        
        # Load the agents
        self.load_agents()
    
    def setup_llms_tab(self):
        """
        Set up the LLMs tab
        """
        # Create the layout
        layout = QVBoxLayout(self.llms_tab)
        
        # Create the LLMs list
        self.llms_group = QGroupBox("LLM Providers")
        llms_layout = QVBoxLayout(self.llms_group)
        
        # Create a scroll area for the LLMs
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Create a widget to hold the LLM forms
        self.llms_container = QWidget()
        self.llms_container.setStyleSheet("background: transparent;")
        self.llms_layout = QVBoxLayout(self.llms_container)
        self.llms_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(self.llms_container)
        
        llms_layout.addWidget(scroll_area)
        
        layout.addWidget(self.llms_group)
        
        # Load the LLMs
        self.load_llms()
    
    def setup_general_tab(self):
        """
        Set up the general tab
        """
        # Create the layout
        layout = QVBoxLayout(self.general_tab)

        # Create scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)

        # Webhook Settings Group
        webhook_group = QGroupBox("Webhook Settings")
        webhook_layout = QFormLayout()
        webhook_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        webhook_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.webhook_port_input = QSpinBox()
        self.webhook_port_input.setMinimum(1024)
        self.webhook_port_input.setMaximum(65535)
        self.webhook_port_input.setValue(8000)
        webhook_layout.addRow("Webhook Port:", self.webhook_port_input)

        webhook_group.setLayout(webhook_layout)
        container_layout.addWidget(webhook_group)

        # ngrok Settings Group
        ngrok_group = QGroupBox("Push Notifications (ngrok)")
        ngrok_layout = QFormLayout()
        ngrok_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        ngrok_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.ngrok_enabled_checkbox = QCheckBox("Enable push notifications via ngrok")
        self.ngrok_enabled_checkbox.setChecked(False)
        ngrok_layout.addRow("", self.ngrok_enabled_checkbox)

        # Add info label
        info_label = QLabel("Push notifications allow agents to send real-time updates.\nRequires ngrok account (free): https://ngrok.com")
        info_label.setStyleSheet("color: #a0aec0; font-size: 11px; padding: 5px;")
        info_label.setWordWrap(True)
        ngrok_layout.addRow("", info_label)

        self.ngrok_token_input = QLineEdit()
        self.ngrok_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ngrok_token_input.setPlaceholderText("Enter your ngrok auth token")
        ngrok_layout.addRow("ngrok Auth Token:", self.ngrok_token_input)

        self.ngrok_region_combo = QComboBox()
        self.ngrok_region_combo.addItems(["us", "eu", "ap", "au", "sa", "jp", "in"])
        self.ngrok_region_combo.setCurrentText("us")
        ngrok_layout.addRow("ngrok Region:", self.ngrok_region_combo)

        # Add help button
        help_button = QPushButton("How to get ngrok token?")
        help_button.clicked.connect(self.show_ngrok_help)
        ngrok_layout.addRow("", help_button)

        ngrok_group.setLayout(ngrok_layout)
        container_layout.addWidget(ngrok_group)

        # General Settings Group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()
        general_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        general_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.auto_connect_checkbox = QCheckBox("Auto-connect to default agent")
        self.auto_connect_checkbox.setChecked(True)
        general_layout.addRow("", self.auto_connect_checkbox)

        general_group.setLayout(general_layout)
        container_layout.addWidget(general_group)

        container_layout.addStretch()
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        # Load current settings
        self.load_general_settings()

    def load_general_settings(self):
        """Load general settings from config"""
        try:
            from agentcomm.config.settings import Settings
            settings = Settings()

            # Load webhook settings
            self.webhook_port_input.setValue(settings.get("webhook_port", 8000))

            # Load ngrok settings
            self.ngrok_enabled_checkbox.setChecked(settings.get("ngrok.enabled", False))
            self.ngrok_token_input.setText(settings.get("ngrok.auth_token", ""))
            self.ngrok_region_combo.setCurrentText(settings.get("ngrok.region", "us"))

            # Load general settings
            # Note: auto_connect setting may not exist yet, will be added when implementing

        except Exception as e:
            logger.error(f"Error loading general settings: {e}")

    def show_ngrok_help(self):
        """Show help dialog for ngrok setup"""
        help_text = """<h3>How to Get ngrok Auth Token</h3>
        <p><b>Step 1:</b> Sign up for a free ngrok account at <a href="https://ngrok.com">https://ngrok.com</a></p>
        <p><b>Step 2:</b> Log in to your ngrok dashboard</p>
        <p><b>Step 3:</b> Go to "Your Authtoken" section</p>
        <p><b>Step 4:</b> Copy your auth token</p>
        <p><b>Step 5:</b> Paste it in the "ngrok Auth Token" field above</p>
        <br>
        <p><b>Note:</b> The free tier is sufficient for this application.</p>
        <p>Once configured, agents will be able to send you real-time push notifications when tasks complete.</p>
        """

        StyledMessageBox.information(self, "ngrok Setup Help", help_text)
    
    def load_agents(self):
        """
        Load the agents into the form
        """
        # Clear the layout
        while self.agents_layout.count():
            item = self.agents_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Add the agents
        for agent in self.agent_registry.get_all_agents():
            self.add_agent_form(agent)
    
    def load_llms(self):
        """
        Load the LLMs into the form
        """
        # Clear the layout and input references
        while self.llms_layout.count():
            item = self.llms_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.llm_inputs.clear()

        # Add the LLMs
        for llm_id, provider in self.llm_router.get_all_providers().items():
            self.add_llm_form(llm_id, provider)

        # Add spacer to push content to top
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.llms_layout.addItem(spacer)
    
    def add_agent_form(self, agent: Optional[Agent] = None):
        """
        Add an agent form
        
        Args:
            agent: Optional agent to populate the form with
        """
        # Create the group box
        group_box = QGroupBox(agent.name if agent else "New Agent")
        form_layout = QFormLayout(group_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Add the form fields
        id_input = QLineEdit(agent.id if agent else "")
        form_layout.addRow("ID:", id_input)
        
        name_input = QLineEdit(agent.name if agent else "")
        form_layout.addRow("Name:", name_input)
        
        description_input = QLineEdit(agent.description if agent else "")
        form_layout.addRow("Description:", description_input)
        
        url_input = QLineEdit(agent.url if agent else "")
        form_layout.addRow("URL:", url_input)
        
        # Authentication
        auth_type_combo = QComboBox()
        auth_type_combo.addItems(["none", "api_key", "bearer", "basic"])
        if agent:
            auth_type_combo.setCurrentText(agent.authentication.auth_type)
        form_layout.addRow("Auth Type:", auth_type_combo)
        
        api_key_name_input = QLineEdit(agent.authentication.api_key_name if agent and agent.authentication.api_key_name else "")
        form_layout.addRow("API Key Name:", api_key_name_input)
        
        token_input = QLineEdit(agent.authentication.token if agent and agent.authentication.token else "")
        token_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Token:", token_input)
        
        # Capabilities
        streaming_checkbox = QCheckBox()
        streaming_checkbox.setChecked(agent.capabilities.streaming if agent else False)
        form_layout.addRow("Streaming:", streaming_checkbox)
        
        push_notifications_checkbox = QCheckBox()
        push_notifications_checkbox.setChecked(agent.capabilities.push_notifications if agent else False)
        form_layout.addRow("Push Notifications:", push_notifications_checkbox)
        
        file_upload_checkbox = QCheckBox()
        file_upload_checkbox.setChecked(agent.capabilities.file_upload if agent else False)
        form_layout.addRow("File Upload:", file_upload_checkbox)
        
        tool_use_checkbox = QCheckBox()
        tool_use_checkbox.setChecked(agent.capabilities.tool_use if agent else False)
        form_layout.addRow("Tool Use:", tool_use_checkbox)
        
        # Default
        is_default_checkbox = QCheckBox()
        is_default_checkbox.setChecked(agent.is_default if agent else False)
        form_layout.addRow("Default Agent:", is_default_checkbox)
        
        # Add the buttons
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(lambda: self.save_agent(
            group_box,
            id_input.text(),
            name_input.text(),
            description_input.text(),
            url_input.text(),
            auth_type_combo.currentText(),
            api_key_name_input.text(),
            token_input.text(),
            streaming_checkbox.isChecked(),
            push_notifications_checkbox.isChecked(),
            file_upload_checkbox.isChecked(),
            tool_use_checkbox.isChecked(),
            is_default_checkbox.isChecked()
        ))
        button_layout.addWidget(save_button)
        
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self.remove_agent(group_box, id_input.text()))
        button_layout.addWidget(remove_button)
        
        form_layout.addRow("", button_layout)
        
        # Add the group box to the layout
        self.agents_layout.addWidget(group_box)
    
    def add_llm_form(self, llm_id: str, provider: Any):
        """
        Add an LLM form
        
        Args:
            llm_id: LLM ID
            provider: LLM provider
        """
        # Create the group box
        group_box = QGroupBox(llm_id)
        form_layout = QFormLayout(group_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Add the form fields based on the provider type
        if llm_id == "OpenAI":
            api_key_input = QLineEdit(provider.api_key if hasattr(provider, "api_key") else "")
            api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            form_layout.addRow("API Key:", api_key_input)

            model_input = QLineEdit(provider.default_model if hasattr(provider, "default_model") else "")
            form_layout.addRow("Default Model:", model_input)

            temperature_input = QDoubleSpinBox()
            temperature_input.setMinimum(0.0)
            temperature_input.setMaximum(2.0)
            temperature_input.setSingleStep(0.1)
            temperature_input.setValue(provider.temperature if hasattr(provider, "temperature") else 0.7)
            form_layout.addRow("Temperature:", temperature_input)

            # Store references for batch saving
            self.llm_inputs[llm_id] = {
                "api_key": api_key_input,
                "default_model": model_input,
                "temperature": temperature_input
            }

            # Add the save button
            save_button = QPushButton("Save")
            save_button.clicked.connect(lambda: self.save_llm(
                llm_id,
                {
                    "api_key": api_key_input.text(),
                    "default_model": model_input.text(),
                    "temperature": temperature_input.value()
                }
            ))
            form_layout.addRow("", save_button)
        
        elif llm_id == "Google Gemini":
            api_key_input = QLineEdit(provider.api_key if hasattr(provider, "api_key") else "")
            api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            form_layout.addRow("API Key:", api_key_input)

            model_input = QLineEdit(provider.default_model if hasattr(provider, "default_model") else "")
            form_layout.addRow("Default Model:", model_input)

            temperature_input = QDoubleSpinBox()
            temperature_input.setMinimum(0.0)
            temperature_input.setMaximum(2.0)
            temperature_input.setSingleStep(0.1)
            temperature_input.setValue(provider.temperature if hasattr(provider, "temperature") else 0.7)
            form_layout.addRow("Temperature:", temperature_input)

            # Store references for batch saving
            self.llm_inputs[llm_id] = {
                "api_key": api_key_input,
                "default_model": model_input,
                "temperature": temperature_input
            }

            # Add the save button
            save_button = QPushButton("Save")
            save_button.clicked.connect(lambda: self.save_llm(
                llm_id,
                {
                    "api_key": api_key_input.text(),
                    "default_model": model_input.text(),
                    "temperature": temperature_input.value()
                }
            ))
            form_layout.addRow("", save_button)
        
        elif llm_id == "Anthropic Claude":
            api_key_input = QLineEdit(provider.api_key if hasattr(provider, "api_key") else "")
            api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            form_layout.addRow("API Key:", api_key_input)

            model_input = QLineEdit(provider.default_model if hasattr(provider, "default_model") else "")
            form_layout.addRow("Default Model:", model_input)

            temperature_input = QDoubleSpinBox()
            temperature_input.setMinimum(0.0)
            temperature_input.setMaximum(2.0)
            temperature_input.setSingleStep(0.1)
            temperature_input.setValue(provider.temperature if hasattr(provider, "temperature") else 0.7)
            form_layout.addRow("Temperature:", temperature_input)

            # Store references for batch saving
            self.llm_inputs[llm_id] = {
                "api_key": api_key_input,
                "default_model": model_input,
                "temperature": temperature_input
            }

            # Add the save button
            save_button = QPushButton("Save")
            save_button.clicked.connect(lambda: self.save_llm(
                llm_id,
                {
                    "api_key": api_key_input.text(),
                    "default_model": model_input.text(),
                    "temperature": temperature_input.value()
                }
            ))
            form_layout.addRow("", save_button)
        
        elif llm_id == "Local LLM":
            host_input = QLineEdit(provider.host if hasattr(provider, "host") else "http://localhost:11434")
            form_layout.addRow("Host:", host_input)

            model_input = QLineEdit(provider.default_model if hasattr(provider, "default_model") else "")
            form_layout.addRow("Default Model:", model_input)

            temperature_input = QDoubleSpinBox()
            temperature_input.setMinimum(0.0)
            temperature_input.setMaximum(2.0)
            temperature_input.setSingleStep(0.1)
            temperature_input.setValue(provider.temperature if hasattr(provider, "temperature") else 0.7)
            form_layout.addRow("Temperature:", temperature_input)

            # Store references for batch saving
            self.llm_inputs[llm_id] = {
                "host": host_input,
                "default_model": model_input,
                "temperature": temperature_input
            }

            # Add the save button
            save_button = QPushButton("Save")
            save_button.clicked.connect(lambda: self.save_llm(
                llm_id,
                {
                    "host": host_input.text(),
                    "default_model": model_input.text(),
                    "temperature": temperature_input.value()
                }
            ))
            form_layout.addRow("", save_button)
        
        # Add the group box to the layout
        self.llms_layout.addWidget(group_box)
    
    def add_agent(self):
        """
        Add a new agent form
        """
        self.add_agent_form()
    
    def save_agent(
        self,
        group_box: QGroupBox,
        agent_id: str,
        name: str,
        description: str,
        url: str,
        auth_type: str,
        api_key_name: str,
        token: str,
        streaming: bool,
        push_notifications: bool,
        file_upload: bool,
        tool_use: bool,
        is_default: bool
    ):
        """
        Save an agent
        
        Args:
            group_box: Group box containing the form
            agent_id: Agent ID
            name: Agent name
            description: Agent description
            url: Agent URL
            auth_type: Authentication type
            api_key_name: API key name
            token: Authentication token
            streaming: Whether the agent supports streaming
            push_notifications: Whether the agent supports push notifications
            file_upload: Whether the agent supports file upload
            tool_use: Whether the agent supports tool use
            is_default: Whether the agent is the default
        """
        try:
            # Validate the form
            if not agent_id:
                StyledMessageBox.warning(self, "Validation Error", "Agent ID is required")
                return

            if not name:
                StyledMessageBox.warning(self, "Validation Error", "Agent name is required")
                return

            if not url:
                StyledMessageBox.warning(self, "Validation Error", "Agent URL is required")
                return
            
            # Create the agent
            agent = Agent(
                id=agent_id,
                name=name,
                description=description,
                url=url,
                capabilities=AgentCapabilities(
                    streaming=streaming,
                    push_notifications=push_notifications,
                    file_upload=file_upload,
                    tool_use=tool_use
                ),
                authentication=AgentAuthentication(
                    auth_type=auth_type,
                    api_key_name=api_key_name,
                    token=token
                ),
                default_input_modes=["text/plain"],
                default_output_modes=["text/plain"],
                is_default=is_default,
                is_built_in=False
            )
            
            # Add the agent to the registry
            logger.info(f"Saving agent: {name} ({agent_id})")
            if self.agent_registry.add_agent(agent):
                # Update the group box title
                group_box.setTitle(name)

                StyledMessageBox.information(self, "Success", f"Agent {name} saved successfully")
                logger.info(f"Agent {name} ({agent_id}) saved successfully")
                self.settings_changed.emit()
            else:
                StyledMessageBox.warning(self, "Error", f"Failed to save agent {name}")
                logger.error(f"Failed to save agent {name} ({agent_id})")

        except Exception as e:
            logger.error(f"Error saving agent: {e}")
            StyledMessageBox.critical(self, "Error", f"Error saving agent: {e}")
    
    def remove_agent(self, group_box: QGroupBox, agent_id: str):
        """
        Remove an agent
        
        Args:
            group_box: Group box containing the form
            agent_id: Agent ID
        """
        try:
            # Confirm the removal
            if StyledMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove agent {agent_id}?"
            ):
                # Remove the agent from the registry
                if self.agent_registry.remove_agent(agent_id):
                    # Remove the group box
                    self.agents_layout.removeWidget(group_box)
                    group_box.deleteLater()

                    StyledMessageBox.information(self, "Success", f"Agent {agent_id} removed successfully")
                else:
                    StyledMessageBox.warning(self, "Error", f"Failed to remove agent {agent_id}")

        except Exception as e:
            logger.error(f"Error removing agent: {e}")
            StyledMessageBox.critical(self, "Error", f"Error removing agent: {e}")
    
    def save_llm(self, llm_id: str, config: Dict[str, Any]):
        """
        Save an LLM configuration

        Args:
            llm_id: LLM ID
            config: LLM configuration
        """
        try:
            # Get the current LLM configuration from the agent registry's config store
            config_store = self.agent_registry.config_store

            # Update the configuration in the config store
            if "providers" not in config_store.llm_config:
                config_store.llm_config["providers"] = {}

            if llm_id not in config_store.llm_config["providers"]:
                config_store.llm_config["providers"][llm_id] = {}

            for key, value in config.items():
                config_store.llm_config["providers"][llm_id][key] = value

            # Save the configuration
            if config_store.save_config("llm"):
                # Reload LLM router with new config
                self.llm_router.reload_config()
                StyledMessageBox.information(self, "Success", f"LLM {llm_id} configuration saved successfully")
                self.settings_changed.emit()
            else:
                StyledMessageBox.warning(self, "Error", f"Failed to save LLM {llm_id} configuration")

        except Exception as e:
            logger.error(f"Error saving LLM configuration: {e}")
            StyledMessageBox.critical(self, "Error", f"Error saving LLM configuration: {e}")
    
    def apply_and_accept(self):
        """
        Apply settings and accept the dialog
        """
        logger.info("OK button clicked - applying settings and closing dialog")
        self.apply_settings()
        self.accept()
        
    def apply_settings(self):
        """
        Apply the settings
        """
        logger.info("Apply button clicked - applying all settings")
        try:
            # Save all LLM configurations
            config_store = self.agent_registry.config_store
            success = True

            # Save general settings (webhook port and ngrok)
            from agentcomm.config.settings import Settings
            settings = Settings()

            settings.set("webhook_port", self.webhook_port_input.value())
            settings.set("ngrok.enabled", self.ngrok_enabled_checkbox.isChecked())
            settings.set("ngrok.auth_token", self.ngrok_token_input.text())
            settings.set("ngrok.region", self.ngrok_region_combo.currentText())

            logger.info(f"Saved general settings: webhook_port={self.webhook_port_input.value()}, ngrok_enabled={self.ngrok_enabled_checkbox.isChecked()}")

            # Process LLM settings
            for llm_id, inputs in self.llm_inputs.items():
                # Build config dict based on provider type
                config = {}

                if llm_id == "Local LLM":
                    config = {
                        "host": inputs["host"].text(),
                        "default_model": inputs["default_model"].text(),
                        "temperature": inputs["temperature"].value()
                    }
                else:
                    config = {
                        "api_key": inputs["api_key"].text(),
                        "default_model": inputs["default_model"].text(),
                        "temperature": inputs["temperature"].value()
                    }

                # Update config in config_store
                if "providers" not in config_store.llm_config:
                    config_store.llm_config["providers"] = {}

                if llm_id not in config_store.llm_config["providers"]:
                    config_store.llm_config["providers"][llm_id] = {}

                for key, value in config.items():
                    config_store.llm_config["providers"][llm_id][key] = value

            # Save LLM settings to file
            if not config_store.save_config("llm"):
                success = False
                logger.error("Failed to save LLM settings")
            else:
                # Reload LLM router with new config
                self.llm_router.reload_config()

            # Process agent settings - collect all agent data from the UI
            # This ensures any unsaved agent changes are also applied
            agents_to_save = []
            
            # Iterate through all agent form widgets in the agents container
            for i in range(self.agents_layout.count()):
                item = self.agents_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QGroupBox):
                    group_box = item.widget()
                    
                    # Extract agent data from form fields
                    agent_data = self._extract_agent_data_from_form(group_box)
                    if agent_data and agent_data.get("id") and agent_data.get("name") and agent_data.get("url"):
                        # Only save agents with required fields (id, name, url)
                        agents_to_save.append(agent_data)
                        logger.info(f"Collected agent data for: {agent_data.get('name')} ({agent_data.get('id')})")
            
            # Update the config store with all agent data
            if agents_to_save:
                # The agents_config is actually a list in practice, despite the type hint
                config_store.agents_config = agents_to_save  # type: ignore
                logger.info(f"Saving {len(agents_to_save)} agents to configuration")
                if not config_store.save_config("agents"):
                    success = False
                    logger.error("Failed to save agent settings")
                else:
                    # Reload the agent registry to apply changes
                    logger.info("Reloading agent registry after configuration save")
                    self.agent_registry.load_agents()
            else:
                # If no valid agents were found in the UI, but there are agents in the config,
                # we should still save an empty list to clear any invalid agents
                if config_store.agents_config and len(config_store.agents_config) > 0:
                    config_store.agents_config = []  # type: ignore
                    if config_store.save_config("agents"):
                        logger.info("Cleared invalid agents from configuration")
                        self.agent_registry.load_agents()
            
            # Show appropriate message based on success
            if success:
                StyledMessageBox.information(self, "Success", "All settings applied successfully")
                self.settings_changed.emit()
            else:
                StyledMessageBox.warning(self, "Error", "Failed to save some settings")

        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            StyledMessageBox.critical(self, "Error", f"Error applying settings: {e}")
    
    def _extract_agent_data_from_form(self, group_box: QGroupBox) -> Optional[Dict[str, Any]]:
        """
        Extract agent data from form fields in a group box
        
        Args:
            group_box: Group box containing the agent form
            
        Returns:
            Dictionary with agent data or None if extraction fails
        """
        try:
            # Direct approach to find form fields by their types
            agent_data = {
                "capabilities": {},
                "authentication": {},
                "default_input_modes": ["text/plain"],
                "default_output_modes": ["text/plain"],
                "is_built_in": False
            }
            
            # Find all input widgets in the group box
            for child in group_box.findChildren(QLineEdit):
                if child.objectName() == "id_input" or child.placeholderText() == "ID":
                    agent_data["id"] = child.text().strip()
                elif child.objectName() == "name_input" or child.placeholderText() == "Name":
                    agent_data["name"] = child.text().strip()
                elif child.objectName() == "description_input" or child.placeholderText() == "Description":
                    agent_data["description"] = child.text().strip()
                elif child.objectName() == "url_input" or child.placeholderText() == "URL":
                    agent_data["url"] = child.text().strip()
                elif child.objectName() == "api_key_name_input" or "api key" in child.placeholderText().lower():
                    agent_data["authentication"]["api_key_name"] = child.text().strip()
                elif child.objectName() == "token_input" or "token" in child.placeholderText().lower():
                    agent_data["authentication"]["token"] = child.text().strip()
            
            # Find auth type combo box
            for child in group_box.findChildren(QComboBox):
                if child.objectName() == "auth_type_combo" or any("auth" in item.lower() for item in [child.itemText(i) for i in range(child.count())]):
                    agent_data["authentication"]["auth_type"] = child.currentText()
            
            # Find checkboxes
            for child in group_box.findChildren(QCheckBox):
                if "streaming" in child.text().lower():
                    agent_data["capabilities"]["streaming"] = child.isChecked()
                elif "push" in child.text().lower():
                    agent_data["capabilities"]["push_notifications"] = child.isChecked()
                elif "file" in child.text().lower():
                    agent_data["capabilities"]["file_upload"] = child.isChecked()
                elif "tool" in child.text().lower():
                    agent_data["capabilities"]["tool_use"] = child.isChecked()
                elif "default" in child.text().lower():
                    agent_data["is_default"] = child.isChecked()
            
            # Alternative approach: try to find form layout and extract fields
            if not agent_data.get("id") or not agent_data.get("name") or not agent_data.get("url"):
                # Find form layout
                form_layout = None
                for layout in group_box.findChildren(QFormLayout):
                    form_layout = layout
                    break
                
                if form_layout:
                    # Process each row in the form
                    for row in range(form_layout.rowCount()):
                        label_item = form_layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                        field_item = form_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                        
                        if not label_item or not field_item:
                            continue
                            
                        label_widget = label_item.widget()
                        field_widget = field_item.widget()
                        
                        if not label_widget or not field_widget:
                            continue
                        
                        # Get the field name from the label text
                        field_name = label_widget.text().replace(":", "").lower()
                        
                        # Extract value based on widget type
                        if isinstance(field_widget, QLineEdit):
                            value = field_widget.text().strip()
                            if field_name == "id":
                                agent_data["id"] = value
                            elif field_name == "name":
                                agent_data["name"] = value
                            elif field_name == "description":
                                agent_data["description"] = value
                            elif field_name == "url":
                                agent_data["url"] = value
                            elif field_name == "api key name":
                                agent_data["authentication"]["api_key_name"] = value
                            elif field_name == "token":
                                agent_data["authentication"]["token"] = value
                        elif isinstance(field_widget, QComboBox):
                            value = field_widget.currentText()
                            if field_name == "auth type":
                                agent_data["authentication"]["auth_type"] = value
                        elif isinstance(field_widget, QCheckBox):
                            value = field_widget.isChecked()
                            if field_name == "streaming":
                                agent_data["capabilities"]["streaming"] = value
                            elif field_name == "push notifications":
                                agent_data["capabilities"]["push_notifications"] = value
                            elif field_name == "file upload":
                                agent_data["capabilities"]["file_upload"] = value
                            elif field_name == "tool use":
                                agent_data["capabilities"]["tool_use"] = value
                            elif field_name == "default agent":
                                agent_data["is_default"] = value
            
            # Ensure all required capabilities are set
            for cap in ["streaming", "push_notifications", "file_upload", "tool_use"]:
                if cap not in agent_data["capabilities"]:
                    agent_data["capabilities"][cap] = False
            
            # Ensure all required authentication fields are set
            if "auth_type" not in agent_data["authentication"]:
                agent_data["authentication"]["auth_type"] = "none"
            if "api_key_name" not in agent_data["authentication"]:
                agent_data["authentication"]["api_key_name"] = ""
            if "token" not in agent_data["authentication"]:
                agent_data["authentication"]["token"] = ""
            
            # Log the extracted data for debugging
            logger.debug(f"Extracted agent data: {agent_data}")
            
            return agent_data
            
        except Exception as e:
            logger.error(f"Error extracting agent data from form: {e}")
            return None
