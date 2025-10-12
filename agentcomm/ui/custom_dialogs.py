"""
Custom styled dialogs for AgentComm
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from typing import Optional


class StyledMessageBox(QDialog):
    """
    Custom styled message box with gradient background
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        message: str,
        icon_type: str = "question"  # question, warning, information, critical
    ):
        """
        Initialize the styled message box

        Args:
            parent: Parent widget
            title: Dialog title
            message: Dialog message
            icon_type: Type of icon to display
        """
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        # Apply gradient background styling
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2d3748, stop:1 #1e293b);
                border: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
                padding: 10px;
                background: transparent;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QPushButton:pressed {
                background: #5a67d8;
                padding-top: 14px;
                padding-bottom: 10px;
            }
            QPushButton#cancelButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a5568, stop:1 #2d3748);
            }
            QPushButton#cancelButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2d3748, stop:1 #4a5568);
            }
        """)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Add icon and message
        content_layout = QHBoxLayout()

        # Icon label
        icon_label = QLabel()
        if icon_type == "question":
            icon_label.setText("❓")
        elif icon_type == "warning":
            icon_label.setText("⚠️")
        elif icon_type == "information":
            icon_label.setText("ℹ️")
        elif icon_type == "critical":
            icon_label.setText("❌")

        icon_label.setStyleSheet("font-size: 32px; padding: 0px 10px;")
        content_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        # Message label
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        content_layout.addWidget(message_label, stretch=1)

        layout.addLayout(content_layout)

        # Add buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.yes_button = QPushButton("Yes")
        self.yes_button.clicked.connect(self.accept)
        button_layout.addWidget(self.yes_button)

        self.no_button = QPushButton("No")
        self.no_button.setObjectName("cancelButton")
        self.no_button.clicked.connect(self.reject)
        button_layout.addWidget(self.no_button)

        layout.addLayout(button_layout)

    @staticmethod
    def question(
        parent: Optional[QWidget],
        title: str,
        message: str
    ) -> bool:
        """
        Show a question dialog and return True if Yes was clicked

        Args:
            parent: Parent widget
            title: Dialog title
            message: Dialog message

        Returns:
            True if Yes was clicked, False otherwise
        """
        dialog = StyledMessageBox(parent, title, message, "question")
        return dialog.exec() == QDialog.DialogCode.Accepted

    @staticmethod
    def warning(
        parent: Optional[QWidget],
        title: str,
        message: str
    ):
        """
        Show a warning dialog with OK button

        Args:
            parent: Parent widget
            title: Dialog title
            message: Dialog message
        """
        dialog = StyledMessageBox(parent, title, message, "warning")
        dialog.no_button.hide()
        dialog.yes_button.setText("OK")
        dialog.exec()

    @staticmethod
    def information(
        parent: Optional[QWidget],
        title: str,
        message: str
    ):
        """
        Show an information dialog with OK button

        Args:
            parent: Parent widget
            title: Dialog title
            message: Dialog message
        """
        dialog = StyledMessageBox(parent, title, message, "information")
        dialog.no_button.hide()
        dialog.yes_button.setText("OK")
        dialog.exec()

    @staticmethod
    def critical(
        parent: Optional[QWidget],
        title: str,
        message: str
    ):
        """
        Show a critical/error dialog with OK button

        Args:
            parent: Parent widget
            title: Dialog title
            message: Dialog message
        """
        dialog = StyledMessageBox(parent, title, message, "critical")
        dialog.no_button.hide()
        dialog.yes_button.setText("OK")
        dialog.exec()


class StyledInputDialog(QDialog):
    """
    Custom styled input dialog with gradient background
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        label: str,
        text: str = ""
    ):
        """
        Initialize the styled input dialog

        Args:
            parent: Parent widget
            title: Dialog title
            label: Label text for the input field
            text: Default text value
        """
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        # Apply gradient background styling
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2d3748, stop:1 #1e293b);
                border: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
                padding: 5px;
                background: transparent;
            }
            QLineEdit {
                background: #1e293b;
                color: #ffffff;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: #667eea;
            }
            QLineEdit:focus {
                border: 2px solid #667eea;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                min-width: 90px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
            QPushButton:pressed {
                background: #5a67d8;
                padding-top: 14px;
                padding-bottom: 10px;
            }
            QPushButton#cancelButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a5568, stop:1 #2d3748);
            }
            QPushButton#cancelButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2d3748, stop:1 #4a5568);
            }
        """)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Add label
        label_widget = QLabel(label)
        layout.addWidget(label_widget)

        # Add input field
        self.input_field = QLineEdit()
        self.input_field.setText(text)
        self.input_field.selectAll()
        layout.addWidget(self.input_field)

        # Add buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_text(self) -> str:
        """
        Get the entered text

        Returns:
            The text entered by the user
        """
        return self.input_field.text()

    @staticmethod
    def get_text_input(
        parent: Optional[QWidget],
        title: str,
        label: str,
        text: str = ""
    ) -> tuple[str, bool]:
        """
        Show an input dialog and return the entered text and OK status

        Args:
            parent: Parent widget
            title: Dialog title
            label: Label text for the input field
            text: Default text value

        Returns:
            Tuple of (entered_text, ok_pressed)
        """
        dialog = StyledInputDialog(parent, title, label, text)
        result = dialog.exec()
        return dialog.get_text(), result == QDialog.DialogCode.Accepted
