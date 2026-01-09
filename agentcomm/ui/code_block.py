#!/usr/bin/env python3
"""
Code Block Widget for A2A Client
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton, QLabel, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QClipboard, QIcon

from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

logger = logging.getLogger(__name__)

class CodeBlockWidget(QFrame):
    """
    Widget for displaying code blocks with syntax highlighting and copy button
    """

    def __init__(self, code: str = "", language: str = "", parent: Optional[QWidget] = None):
        """
        Initialize the code block widget

        Args:
            code: The code content
            language: The language identifier (e.g. 'python', 'javascript')
            parent: Parent widget
        """
        super().__init__(parent)
        self.code = code
        self.language = language

        # Styling for the outer container
        self.setObjectName("CodeBlockWidget")
        self.setStyleSheet("""
            #CodeBlockWidget {
                background-color: #1e1e1e;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                margin: 4px 0px;
            }
        """)
        
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Header (Language label + Copy button)
        self.header = QWidget()
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(12, 6, 8, 6)
        self.header_layout.setSpacing(10)
        
        # Header background
        self.header.setStyleSheet("""
            background-color: #2a2a2a;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom: 1px solid #3f3f46;
        """)
        
        # Language Label
        display_lang = language if language else "text"
        self.lang_label = QLabel(display_lang)
        self.lang_label.setStyleSheet("""
            color: #9ca3af;
            font-size: 12px;
            font-weight: bold;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            text-transform: lowercase;
        """)
        self.header_layout.addWidget(self.lang_label)
        
        self.header_layout.addStretch()
        
        # Copy Button
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFixedHeight(24)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                padding: 0 8px;
                text-align: right;
            }
            QPushButton:hover {
                background: #3f3f46;
                color: #e5e7eb;
            }
            QPushButton:pressed {
                background: #52525b;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_code)
        self.header_layout.addWidget(self.copy_btn)
        
        self.layout.addWidget(self.header)

        # Code Content
        self.code_view = QTextBrowser()
        self.code_view.setReadOnly(True)
        self.code_view.setOpenExternalLinks(False)
        self.code_view.setFrameShape(QFrame.Shape.NoFrame)
        
        # CSS for code view area
        self.code_view.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        
        self.code_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.code_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Set resize policy
        from PyQt6.QtWidgets import QSizePolicy
        self.code_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # Adjust height based on content
        self.code_view.document().contentsChanged.connect(self.adjust_height)

        self.layout.addWidget(self.code_view)
        
        # Initial render
        self.render_code()

    def update_content(self, code: str, language: str = ""):
        """Update the code and language"""
        if self.code == code and self.language == language:
            return
            
        self.code = code
        if language:
            self.language = language
            self.lang_label.setText(language)
            
        self.render_code()

    def render_code(self):
        """Highlight and render the code"""
        try:
            if self.language:
                lexer = get_lexer_by_name(self.language)
            else:
                lexer = guess_lexer(self.code)
        except ClassNotFound:
            lexer = get_lexer_by_name("text")

        formatter = HtmlFormatter(
            style="vs",  # VS Code like style
            noclasses=True, # Inline styles for simplicity in QTextBrowser
            wrapcode=True
        )
        
        # Pygments vs style needs some tweaking for dark mode manual overrides if needed
        # But let's try a dark style
        try:
            formatter = HtmlFormatter(style="monokai", noclasses=True, wrapcode=True)
        except Exception:
            pass # Fallback

        try:
            highlighted_html = highlight(self.code, lexer, formatter)
        except Exception as e:
            logger.error(f"Error highlighting code: {e}")
            highlighted_html = f"<pre>{self.code}</pre>"
        
        # Wrap in body with specific color to ensure readability
        full_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                    margin: 0;
                }}
                pre {{
                    margin: 0;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
            </style>
        </head>
        <body>
            {highlighted_html}
        </body>
        </html>
        """
        
        self.code_view.setHtml(full_html)
        self.adjust_height()

    def adjust_height(self):
        """Fit height to content"""
        doc = self.code_view.document()
        doc.setTextWidth(self.code_view.viewport().width())
        height = doc.size().height() + 24 # + padding
        # Min height 50, max height 600 (then scroll)
        height = max(50, min(height, 600))
        self.code_view.setFixedHeight(int(height))

    def copy_code(self):
        """Copy code to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code)
        
        # Feedback
        original_text = self.copy_btn.text()
        self.copy_btn.setText("Copied!")
        self.copy_btn.setStyleSheet("""
             QPushButton {
                background: transparent;
                color: #10b981;  /* Green for success */
                border: none;
                border-radius: 4px;
                font-size: 11px;
                padding: 0 8px;
                text-align: right;
            }
        """)
        
        # Reset after 2 seconds
        QTimer.singleShot(2000, lambda: self.reset_copy_btn(original_text))

    def reset_copy_btn(self, text):
        self.copy_btn.setText(text)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9ca3af;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                padding: 0 8px;
                text-align: right;
            }
            QPushButton:hover {
                background: #3f3f46;
                color: #e5e7eb;
            }
        """)
