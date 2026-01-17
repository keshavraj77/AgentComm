#!/usr/bin/env python3
"""
Chat Widget for A2A Client
"""

import re
import logging
import asyncio
import threading
import markdown
from typing import Optional, Dict, Any, List
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QTextBrowser, QLineEdit,
    QPushButton, QScrollArea, QLabel, QSplitter, QFrame, QComboBox, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QMetaObject, Q_ARG
from PyQt6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat

from agentcomm.core.session_manager import SessionManager
from agentcomm.llm.chat_history import ChatHistory, ChatMessage
from agentcomm.ui.loading_indicator import LoadingIndicator

logger = logging.getLogger(__name__)


def preprocess_code_blocks(text: str) -> str:
    """
    Preprocess text to fix malformed code blocks.

    Handles:
    - Curly/smart quotes used instead of backticks
    - Missing newlines around code fences
    - Language identifier followed immediately by code (```gopackage main)
    - Text before code fence on same line (Here is code:```go)
    """
    # Replace curly/smart quotes that might be used as backticks
    text = text.replace('\u2018', "'")  # Left single quote
    text = text.replace('\u2019', "'")  # Right single quote
    text = text.replace('\u201C', '"')  # Left double quote
    text = text.replace('\u201D', '"')  # Right double quote
    text = text.replace('\u0060', '`')  # Grave accent
    text = text.replace('\u00B4', '`')  # Acute accent

    # Known programming language identifiers for code fences
    KNOWN_LANGUAGES = {
        'python', 'py', 'javascript', 'js', 'typescript', 'ts', 'java', 'c', 'cpp',
        'c++', 'csharp', 'cs', 'go', 'golang', 'rust', 'rs', 'ruby', 'rb', 'php',
        'swift', 'kotlin', 'scala', 'perl', 'r', 'sql', 'html', 'css', 'scss',
        'sass', 'less', 'xml', 'json', 'yaml', 'yml', 'toml', 'ini', 'bash', 'sh',
        'shell', 'zsh', 'fish', 'powershell', 'ps1', 'dockerfile', 'docker',
        'makefile', 'make', 'cmake', 'lua', 'vim', 'markdown', 'md', 'text', 'txt',
        'plaintext', 'diff', 'git', 'graphql', 'protobuf', 'proto', 'terraform',
        'tf', 'hcl', 'nginx', 'apache', 'jsx', 'tsx', 'vue', 'svelte', 'elm',
        'haskell', 'hs', 'elixir', 'ex', 'erlang', 'erl', 'clojure', 'clj',
        'lisp', 'scheme', 'ocaml', 'ml', 'fsharp', 'fs', 'dart', 'julia', 'jl',
        'zig', 'nim', 'crystal', 'objectivec', 'objc', 'groovy', 'gradle',
    }

    lines = text.split('\n')
    result = []
    in_code_block = False

    for line in lines:
        # Look for ``` anywhere in the line
        if '```' in line and not in_code_block:
            fence_pos = line.find('```')

            # Handle content before the fence
            before_fence = line[:fence_pos]
            after_fence = line[fence_pos + 3:]  # After ```

            # If there's content before the fence, add it as a separate line
            if before_fence.strip():
                result.append(before_fence)

            # Parse language identifier and any code that follows
            # Match: optional language, then optional content
            lang = ""
            code_content = after_fence

            if after_fence:
                # Try to extract a known language identifier
                # Check if the start matches any known language
                lower_after = after_fence.lower()
                matched_lang = None

                # Sort by length descending to match longer languages first
                # e.g., "javascript" before "java", "typescript" before "ts"
                for known_lang in sorted(KNOWN_LANGUAGES, key=len, reverse=True):
                    if lower_after.startswith(known_lang):
                        rest = after_fence[len(known_lang):]
                        # For known languages, always accept even if code follows
                        # immediately (this handles ```gopackage main)
                        matched_lang = after_fence[:len(known_lang)]
                        code_content = rest
                        break

                if matched_lang:
                    lang = matched_lang
                else:
                    # No known language found
                    # Check for generic alphanumeric language id followed by whitespace/end
                    lang_match = re.match(r'^([a-zA-Z][a-zA-Z0-9_+-]*)', after_fence)
                    if lang_match:
                        potential_lang = lang_match.group(1)
                        rest = after_fence[len(potential_lang):]
                        # Only treat as language if followed by whitespace or end
                        # This prevents treating "unknownlangcode" as language "unknownlangcode"
                        if not rest or rest[0].isspace():
                            lang = potential_lang
                            code_content = rest
                        else:
                            # Looks like code without a language identifier
                            code_content = after_fence
                    else:
                        # No alphanumeric start - treat rest as code
                        code_content = after_fence

            # Add the code fence line
            result.append('```' + lang)

            # If there's code content, add it on a new line
            if code_content.strip():
                result.append(code_content.lstrip())

            in_code_block = True

        # Check for closing code fence
        elif '```' in line and in_code_block:
            fence_pos = line.find('```')
            before_fence = line[:fence_pos]
            after_fence = line[fence_pos + 3:]

            # Add any code before the closing fence
            if before_fence.strip():
                result.append(before_fence)

            # Add the closing fence
            result.append('```')
            in_code_block = False

            # Add any content after the closing fence
            if after_fence.strip():
                result.append(after_fence)

        else:
            result.append(line)

    return '\n'.join(result)


def markdown_to_html(text: str) -> str:
    """
    Convert Markdown text to styled HTML

    Args:
        text: Markdown formatted text

    Returns:
        HTML formatted text with styling
    """
    # Preprocess to fix malformed code blocks
    text = preprocess_code_blocks(text)

    # Configure codehilite for syntax highlighting with pygments
    codehilite_config = {
        'codehilite': {
            'guess_lang': True,  # Guess language if not specified
            'css_class': 'codehilite',
            'linenums': False,
            'use_pygments': True,
        }
    }

    # Convert markdown to HTML
    md = markdown.Markdown(
        extensions=['fenced_code', 'codehilite', 'tables', 'nl2br'],
        extension_configs=codehilite_config
    )
    html = md.convert(text)

    # Add custom CSS styling with syntax highlighting
    styled_html = f"""
    <style>
        body {{
            color: #e5e7eb;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
        }}

        strong, b {{
            font-weight: 600;
            color: #ffffff;
        }}

        em, i {{
            font-style: italic;
            color: #d1d5db;
        }}

        code {{
            background: #2a2a2a;
            color: #10b981;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
        }}

        pre {{
            background: #1e1e1e;
            border: 1px solid #3f3f46;
            border-radius: 8px;
            padding: 12px;
            overflow-x: auto;
            overflow-y: visible;
            margin: 8px 0;
            max-width: 100%;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        pre code {{
            background: transparent;
            padding: 0;
            color: #e5e7eb;
            display: block;
            font-size: 13px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        /* Syntax highlighting for code blocks (VS Code Dark+ theme) */
        /* Works for Python, JavaScript, Java, C++, C#, Go, Rust, and more */
        .codehilite {{ background: #1e1e1e; }}
        .codehilite pre {{ margin: 0; background: transparent; }}

        /* Keywords (def, class, if, for, function, const, let, var, etc) */
        .codehilite .k {{ color: #569cd6; font-weight: bold; }}
        .codehilite .kn {{ color: #c586c0; }}  /* keyword namespace (import, package) */
        .codehilite .kd {{ color: #569cd6; }}  /* keyword declaration (var, let, const) */
        .codehilite .kr {{ color: #569cd6; }}  /* keyword reserved */
        .codehilite .kt {{ color: #569cd6; }}  /* keyword type */
        .codehilite .kc {{ color: #569cd6; }}  /* keyword constant (True, False, None, null) */

        /* Function and class names */
        .codehilite .nf {{ color: #dcdcaa; }}  /* function name */
        .codehilite .nc {{ color: #4ec9b0; }}  /* class name */
        .codehilite .nb {{ color: #4ec9b0; }}  /* built-in (print, len, console, etc) */
        .codehilite .nn {{ color: #4ec9b0; }}  /* namespace name */
        .codehilite .nd {{ color: #dcdcaa; }}  /* decorator (@decorator) */

        /* Variables and identifiers */
        .codehilite .n {{ color: #9cdcfe; }}  /* variable name */
        .codehilite .nx {{ color: #9cdcfe; }}  /* variable/identifier (Go, JS) */
        .codehilite .na {{ color: #9cdcfe; }}  /* attribute name */
        .codehilite .bp {{ color: #4ec9b0; }}  /* built-in pseudo (self, this, True, False) */
        .codehilite .w {{ color: #d4d4d4; }}   /* whitespace */

        /* Strings */
        .codehilite .s {{ color: #ce9178; }}   /* string */
        .codehilite .s1 {{ color: #ce9178; }}  /* single quoted string */
        .codehilite .s2 {{ color: #ce9178; }}  /* double quoted string */
        .codehilite .sb {{ color: #ce9178; }}  /* backtick string */
        .codehilite .sc {{ color: #ce9178; }}  /* char */
        .codehilite .sd {{ color: #ce9178; }}  /* docstring */

        /* Numbers */
        .codehilite .mi {{ color: #b5cea8; }}  /* integer */
        .codehilite .mf {{ color: #b5cea8; }}  /* float */
        .codehilite .mh {{ color: #b5cea8; }}  /* hex */
        .codehilite .mo {{ color: #b5cea8; }}  /* octal */

        /* Comments */
        .codehilite .c {{ color: #6a9955; font-style: italic; }}   /* comment */
        .codehilite .c1 {{ color: #6a9955; font-style: italic; }}  /* single line comment */
        .codehilite .cm {{ color: #6a9955; font-style: italic; }}  /* multi-line comment */
        .codehilite .cp {{ color: #6a9955; font-style: italic; }}  /* preprocessor comment */

        /* Operators and punctuation */
        .codehilite .o {{ color: #d4d4d4; }}   /* operator */
        .codehilite .p {{ color: #d4d4d4; }}   /* punctuation */
        .codehilite .w {{ color: #d4d4d4; }}   /* whitespace */

        /* Special for templates and regex */
        .codehilite .sr {{ color: #d16969; }}  /* regex */
        .codehilite .si {{ color: #d7ba7d; }}  /* string interpolation */

        /* HTML/XML */
        .codehilite .nt {{ color: #569cd6; }}  /* tag name */
        .codehilite .err {{ color: #f44747; }}  /* error */

        h1, h2, h3, h4, h5, h6 {{
            color: #ffffff;
            font-weight: 600;
            margin-top: 16px;
            margin-bottom: 8px;
        }}

        h1 {{ font-size: 24px; }}
        h2 {{ font-size: 20px; }}
        h3 {{ font-size: 18px; }}
        h4 {{ font-size: 16px; }}

        ul, ol {{
            margin: 8px 0;
            padding-left: 24px;
        }}

        li {{
            margin: 4px 0;
        }}

        blockquote {{
            border-left: 4px solid #3b82f6;
            padding-left: 12px;
            margin: 8px 0;
            color: #9ca3af;
            font-style: italic;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 8px 0;
        }}

        th, td {{
            border: 1px solid #3f3f46;
            padding: 8px;
            text-align: left;
        }}

        th {{
            background: #2a2a2a;
            font-weight: 600;
        }}

        a {{
            color: #3b82f6;
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        p {{
            margin: 8px 0;
        }}
    </style>
    {html}
    """

    return styled_html


# Global event loop for async operations
_async_loop = None
_async_loop_thread = None

def _get_or_create_event_loop():
    """Get or create a persistent event loop for async operations"""
    global _async_loop, _async_loop_thread

    if _async_loop is None or _async_loop.is_closed():
        def run_event_loop():
            global _async_loop
            _async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_async_loop)
            _async_loop.run_forever()

        _async_loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        _async_loop_thread.start()

        # Wait for the loop to be created
        import time
        while _async_loop is None:
            time.sleep(0.01)

    return _async_loop

def run_async_in_thread(coro_func, *args, on_complete=None, **kwargs):
    """
    Run an async function in a separate thread

    Args:
        coro_func: Async function to run
        *args: Arguments to pass to the function
        on_complete: Callback to call when the function completes
        **kwargs: Keyword arguments to pass to the function
    """
    loop = _get_or_create_event_loop()

    async def wrapper():
        try:
            await coro_func(*args, **kwargs)
            if on_complete:
                on_complete()
        except Exception as e:
            logger.error(f"Error in async task: {e}", exc_info=True)

    # Schedule the coroutine on the persistent event loop
    asyncio.run_coroutine_threadsafe(wrapper(), loop)

class TaskPollingWidget(QFrame):
    """
    Widget for manual task polling when push notifications are disabled.
    Displays task ID and a refresh button.
    """
    refresh_clicked = pyqtSignal(str)  # Emits task_id

    def __init__(self, task_id: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            TaskPollingWidget {
                background-color: #2a2a2a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                margin: 5px 0px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Info icon label
        icon_label = QLabel("⚡")
        icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(icon_label)
        
        # Text info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        status_label = QLabel("Task in Progress")
        status_label.setStyleSheet("color: #e5e7eb; font-weight: bold;")
        info_layout.addWidget(status_label)
        
        id_label = QLabel(f"ID: {task_id[:8]}...")
        id_label.setToolTip(task_id)
        id_label.setStyleSheet("color: #9ca3af; font-family: monospace; font-size: 11px;")
        info_layout.addWidget(id_label)
        
        # Push notification hint
        hint_label = QLabel("Enable push notifications for auto-updates")
        hint_label.setStyleSheet("color: #6b7280; font-size: 10px; font-style: italic;")
        info_layout.addWidget(hint_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(self.refresh_btn)
        
    def _on_refresh_clicked(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Checking...")
        self.refresh_clicked.emit(self.task_id)
        
    def reset_button(self):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Status")


class MessageWidget(QFrame):
    """
    Widget for displaying a single message in the chat
    """

    def __init__(self, message: str, sender: str, is_user: bool = False, sender_icon: str = "🤖", parent: Optional[QWidget] = None):
        """
        Initialize the message widget

        Args:
            message: Message text
            sender: Sender name
            is_user: Whether the message is from the user
            sender_icon: Icon to display before sender name (default: robot emoji)
            parent: Parent widget
        """
        super().__init__(parent)

        # Set up the frame
        self.setFrameShape(QFrame.Shape.NoFrame)

        # Allow widget to shrink to content size
        from PyQt6.QtWidgets import QSizePolicy
        if is_user:
            self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        # Set minimalist background based on the sender
        if is_user:
            self.setStyleSheet("""
                QFrame {
                    background: #374151;
                    border-radius: 16px;
                    padding: 0px;
                    border: none;
                }
                QLabel {
                    background: transparent;
                    border-radius: 16px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: transparent;
                    border-radius: 18px;
                    padding: 0px;
                    border: none;
                }
            """)

        # Create the layout
        layout = QVBoxLayout(self)
        # Minimal spacing between sender name and message
        layout.setSpacing(3)
        # Tighter padding for more compact messages
        if is_user:
            layout.setContentsMargins(12, 8, 12, 8)
        else:
            # AI messages: reduce top padding since we have the sender label
            layout.setContentsMargins(0, 0, 0, 0)

        # Only show sender label for AI messages (not for user)
        if not is_user:
            sender_label = QLabel(f"{sender_icon}  {sender}")
            sender_label.setStyleSheet("""
                font-weight: 600;
                color: #9ca3af;
                font-size: 11px;
                background: transparent;
                padding: 0px;
                margin: 0px;
            """)
            sender_label.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(sender_label)

        # Store is_user for later reference
        self.is_user = is_user

        # Use QLabel for user messages (tighter fit), QTextEdit for AI messages (for streaming)
        if is_user:
            # QLabel for compact, tight-fitting user messages
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            message_label.setTextFormat(Qt.TextFormat.PlainText)
            message_label.setStyleSheet("""
                background-color: transparent;
                color: #e5e7eb;
                font-size: 14px;
                padding: 0px;
                border: none;
            """)

            # Set maximum width for wrapping
            message_label.setMaximumWidth(500)

            layout.addWidget(message_label)
        else:
            # AI messages: Mixed content (Text + Code Blocks)
            self.content_layout = QVBoxLayout()
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(8)
            layout.addLayout(self.content_layout)
            
            # Keep track of blocks to minimize re-rendering
            self.blocks = []
            
            # Initial render
            self.update_content(message)

    def update_content(self, message: str):
        """
        Update the message content (for streaming)
        Smartly updates only what changed
        """
        from agentcomm.ui.code_block import CodeBlockWidget
        
        # Preprocess message to fix malformed code blocks (e.g. standardizing fences)
        # This is critical for streaming where fences might be on the same line as text
        processed_message = preprocess_code_blocks(message)
        
        # Parse message into blocks
        # Returns list of dicts: {'type': 'text'|'code', 'content': str, 'lang': str}
        new_blocks_data = self.parse_message(processed_message)
        
        # If we have more blocks than before, add them
        while len(self.blocks) < len(new_blocks_data):
            block_data = new_blocks_data[len(self.blocks)]
            self.add_block(block_data)
            
        # Update existing blocks
        for i, block_data in enumerate(new_blocks_data):
            widget = self.blocks[i]
            if block_data['type'] == 'code':
                # Check if it's a CodeBlockWidget
                if isinstance(widget, CodeBlockWidget):
                    widget.update_content(block_data['content'], block_data.get('lang', ''))
                else:
                    # Type mismatch (shouldn't happen with append-only streaming usually, but handle it)
                    self.replace_block(i, block_data)
            else:
                # Text block
                if isinstance(widget, QTextBrowser):
                    # Only update if content changed
                    if widget.toPlainText() != block_data['content']:
                         # Convert markdown to HTML and display
                         html_content = markdown_to_html(block_data['content'])
                         widget.setHtml(html_content)
                         self.adjust_text_height(widget)
                else:
                    self.replace_block(i, block_data)

    def add_block(self, block_data):
        """Add a new block widget"""
        from agentcomm.ui.code_block import CodeBlockWidget
        
        if block_data['type'] == 'code':
            widget = CodeBlockWidget(block_data['content'], block_data.get('lang', ''))
            self.content_layout.addWidget(widget)
            self.blocks.append(widget)
        else:
            widget = self.create_text_widget(block_data['content'])
            self.content_layout.addWidget(widget)
            self.blocks.append(widget)

    def replace_block(self, index, block_data):
        """Replace a widget at index"""
        # Remove old
        old_widget = self.blocks[index]
        self.content_layout.removeWidget(old_widget)
        old_widget.deleteLater()
        
        # Add new
        from agentcomm.ui.code_block import CodeBlockWidget
        if block_data['type'] == 'code':
            widget = CodeBlockWidget(block_data['content'], block_data.get('lang', ''))
        else:
            widget = self.create_text_widget(block_data['content'])
            
        # Insert at index
        self.content_layout.insertWidget(index, widget)
        self.blocks[index] = widget

    def create_text_widget(self, content):
        """Create a configured QTextBrowser for markdown text"""
        message_text = QTextBrowser()
        message_text.setReadOnly(True)
        message_text.setOpenExternalLinks(True)
        html_content = markdown_to_html(content)
        message_text.setHtml(html_content)
        message_text.setFrameStyle(QFrame.Shape.NoFrame)

        message_text.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        from PyQt6.QtGui import QTextOption
        message_text.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        message_text.setStyleSheet("""
            background-color: transparent;
            color: #e5e7eb;
            font-size: 14px;
            padding: 0px;
            margin: 0px;
            border: none;
        """)
        message_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        message_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        doc = message_text.document()
        doc.setDocumentMargin(0)
        message_text.setContentsMargins(0, 0, 0, 0)
        message_text.setViewportMargins(0, 0, 0, 0)

        from PyQt6.QtWidgets import QSizePolicy
        message_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        message_text.document().contentsChanged.connect(lambda: self.adjust_text_height(message_text))
        
        # Initial height adjustment
        return message_text

    def adjust_text_height(self, widget):
        """Adjust height of text widget"""
        doc = widget.document()
        doc.setTextWidth(widget.viewport().width())
        height = int(doc.size().height()) + 5
        widget.setFixedHeight(height)

    def parse_message(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse markdown text into blocks of text and code.
        Handles unclosed code blocks for streaming.
        """
        blocks = []
        lines = text.split('\n')
        current_content = []
        in_code_block = False
        current_lang = ""
        
        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    # Closing block
                    in_code_block = False
                    blocks.append({
                        'type': 'code',
                        'lang': current_lang,
                        'content': '\n'.join(current_content)
                    })
                    current_content = []
                    current_lang = ""
                else:
                    # Opening block
                    if current_content:
                        blocks.append({
                            'type': 'text',
                            'content': '\n'.join(current_content)
                        })
                    
                    current_content = []
                    marker = line.strip()[3:].strip()
                    current_lang = marker
                    in_code_block = True
            else:
                current_content.append(line)
        
        # Handle remaining content
        if in_code_block:
            # We are in a code block that hasn't closed yet (streaming)
            # Even if content is empty (just opened fence), we want to show the block
            blocks.append({
                'type': 'code',
                'lang': current_lang,
                'content': '\n'.join(current_content)
            })
        elif current_content:
            # Remaining text content
            content = '\n'.join(current_content)
            if content.strip():
                blocks.append({
                    'type': 'text',
                    'content': content
                })
        
        return blocks


class ChatWidget(QWidget):
    """
    Widget for displaying and interacting with the chat
    """
    
    message_sent = pyqtSignal(str)
    
    def __init__(self, session_manager: SessionManager, parent: Optional[QWidget] = None):
        """
        Initialize the chat widget
        
        Args:
            session_manager: Session manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.session_manager = session_manager
        self.current_entity_id: Optional[str] = None
        self.current_entity_type: Optional[str] = None
        self.streaming_response: str = ""
        self.current_entity_id: Optional[str] = None
        self.current_entity_type: Optional[str] = None
        self.streaming_response: str = ""
        self.streaming_handled: bool = False  # Flag to track if streaming handled the response
        self._polling_task_id: Optional[str] = None
        self._polling_widget: Optional[TaskPollingWidget] = None

        # Register callbacks with thread-safe wrappers
        self.session_manager.register_message_callback(self._thread_safe_message_callback)
        self.session_manager.register_streaming_callback(self._thread_safe_streaming_callback)
        self.session_manager.register_error_callback(self._thread_safe_error_callback)
        self.session_manager.register_thread_callback(self._thread_safe_thread_callback)
        
        # Create the layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Create delete button header (top right)
        self.delete_header = QHBoxLayout()
        self.delete_header.setContentsMargins(10, 5, 10, 5)
        self.delete_header.setSpacing(10)
        self.delete_header.addStretch()

        # Delete thread button (trash icon in top right corner)
        self.delete_thread_btn = QPushButton("🗑")
        self.delete_thread_btn.setFixedWidth(36)
        self.delete_thread_btn.setFixedHeight(36)
        self.delete_thread_btn.setToolTip("Delete chat")
        self.delete_thread_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_thread_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6b7280;
                border: none;
                border-radius: 18px;
                font-size: 18px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #ef4444;
                color: white;
            }
            QPushButton:pressed {
                background: #dc2626;
                color: white;
            }
            QPushButton:disabled {
                color: #4b5563;
                background: transparent;
            }
        """)
        self.delete_thread_btn.clicked.connect(self.delete_current_thread)
        self.delete_header.addWidget(self.delete_thread_btn)

        self.layout.addLayout(self.delete_header)

        # Create the chat display area
        self.chat_scroll_area = QScrollArea()
        self.chat_scroll_area.setWidgetResizable(True)
        self.chat_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_scroll_area.setStyleSheet("""
            QScrollArea {
                background: #1a1a1a;
                border: none;
            }
            QScrollBar:vertical {
                background: #2a2a2a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #4b5563;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6b7280;
            }
        """)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(4)
        self.chat_layout.setContentsMargins(16, 10, 16, 10)

        self.chat_scroll_area.setWidget(self.chat_container)
        self.layout.addWidget(self.chat_scroll_area, 1)

        # Loading Indicator (replaces status container)
        self.loading_indicator = LoadingIndicator(self)
        self.layout.addWidget(self.loading_indicator)

        # Create the input area
        self.input_layout = QHBoxLayout()
        self.input_layout.setContentsMargins(10, 10, 10, 10)
        self.input_layout.setSpacing(10)

        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setAcceptRichText(False)
        self.message_input.setFixedHeight(50)
        self.message_input.setStyleSheet("""
            QTextEdit {
                background: #2a2a2a;
                color: #e5e7eb;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self.input_layout.addWidget(self.message_input, 1)

        # Reset/Clear button with circular icon design
        self.reset_button = QPushButton("↻")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.setFixedWidth(50)
        self.reset_button.setFixedHeight(50)
        self.reset_button.setToolTip("Clear chat")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background: #3f3f46;
                color: #e5e7eb;
                border: none;
                border-radius: 25px;
                font-size: 24px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: #ef4444;
                color: white;
            }
            QPushButton:pressed {
                background: #dc2626;
            }
        """)
        self.reset_button.clicked.connect(self.reset_thread)
        self.input_layout.addWidget(self.reset_button)

        # Send button with icon
        self.send_button = QPushButton("➤")
        self.send_button.setFixedWidth(50)
        self.send_button.setFixedHeight(50)
        self.send_button.setToolTip("Send message")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
        """)
        self.send_button.clicked.connect(self.send_message)
        self.input_layout.addWidget(self.send_button)

        self.layout.addLayout(self.input_layout)

        # Add developer credit
        credit_label = QLabel("Built by Keshav")
        credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
                font-style: italic;
                padding: 5px;
                background: transparent;
            }
        """)
        self.layout.addWidget(credit_label)

        # Create a timer for updating the UI
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_streaming_message)

        # Setup scroll behavior
        self.stick_to_bottom = True
        self.setup_scroll_behavior()

    def setup_scroll_behavior(self):
        """
        Setup auto-scrolling behavior
        """
        scrollbar = self.chat_scroll_area.verticalScrollBar()
        scrollbar.rangeChanged.connect(self.on_scroll_range_changed)
        scrollbar.valueChanged.connect(self.on_scroll_value_changed)

    def on_scroll_range_changed(self, min_val, max_val):
        """
        Handle scroll range changes (e.g. content added)
        """
        if self.stick_to_bottom:
            self.chat_scroll_area.verticalScrollBar().setValue(max_val)

    def on_scroll_value_changed(self, value):
        """
        Handle manual scroll changes
        """
        scrollbar = self.chat_scroll_area.verticalScrollBar()
        max_val = scrollbar.maximum()
        
        # If user is near the bottom, enable sticky mode
        # If user scrolls up, disable sticky mode
        if value >= max_val - 20:  # 20px tolerance
            self.stick_to_bottom = True
        else:
            # Only disable if the range didn't just change (which might cause a value change)
            # We can't easily distinguish, but this basic logic is usually sufficient
            # If we are programmatically scrolling, we've set stick_to_bottom=True anyway
            if self.chat_scroll_area.verticalScrollBar().isSliderDown(): # User is dragging
                 self.stick_to_bottom = False

        
    def _thread_safe_message_callback(self, sender_id: str, message: str, message_type: str):
        """Thread-safe wrapper for message callback"""
        QMetaObject.invokeMethod(
            self, "on_message_received",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, sender_id),
            Q_ARG(str, message),
            Q_ARG(str, message_type)
        )

    def _thread_safe_streaming_callback(self, sender_id: str, chunk: str, message_type: str):
        """Thread-safe wrapper for streaming callback"""
        QMetaObject.invokeMethod(
            self, "on_streaming_chunk_received",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, sender_id),
            Q_ARG(str, chunk),
            Q_ARG(str, message_type)
        )

    def _thread_safe_error_callback(self, error_message: str):
        """Thread-safe wrapper for error callback"""
        QMetaObject.invokeMethod(
            self, "on_error_received",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, error_message)
        )

    def _thread_safe_thread_callback(self):
        """Thread-safe wrapper for thread change callback"""
        # Emit signal to notify that threads have changed
        # Main window will handle the refresh
        pass

    def set_current_entity(self, entity_id: str, entity_type: str):
        """
        Set the current entity (agent or LLM)

        Args:
            entity_id: ID of the entity
            entity_type: Type of the entity (agent or llm)
        """
        self.current_entity_id = entity_id
        self.current_entity_type = entity_type

        # Thread list will be refreshed by session manager's thread callback
        # which is registered in main_window

        # Clear the chat display
        self.clear_chat()
        # Clear the chat display
        self.clear_chat()
        self.loading_indicator.stop_animation()

        # Load the chat history for the current thread
        self.load_chat_history()
    
    def clear_chat(self):
        """
        Clear the chat display
        """
        # Remove all widgets from the chat layout
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def load_chat_history(self):
        """
        Load the chat history for the current entity
        """
        history = self.session_manager.get_current_chat_history()
        if not history:
            return
        
        # Add messages to the chat display
        for msg in history.messages:
            is_user = msg.role == "user"
            sender = "You" if is_user else self.current_entity_id or "Assistant"
            self.add_message_widget(msg.content, sender, is_user)
    
    def add_message_widget(self, message: str, sender: str, is_user: bool = False):
        """
        Add a message widget to the chat display

        Args:
            message: Message text
            sender: Sender name
            is_user: Whether the message is from the user
        """
        # Create a container widget for alignment
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Determine the icon based on entity type
        sender_icon = "🤖"  # Default to agent icon
        if not is_user and self.current_entity_type == "llm":
            sender_icon = "🧠"  # Use brain icon for LLMs

        # Create the message widget
        message_widget = MessageWidget(message, sender, is_user, sender_icon)

        # User messages: no max width, let them shrink to content
        # AI messages: no max width, use full available width

        if is_user:
            # User messages: add spacer on left, message on right
            container_layout.addStretch()
            container_layout.addWidget(message_widget)
        else:
            # AI messages: full width, no spacer
            container_layout.addWidget(message_widget)

        self.chat_layout.addWidget(container)

        # For AI messages, schedule a height recalculation after the widget is rendered
        # This ensures the QTextBrowser has the correct width for proper height calculation
        if not is_user:
            def recalculate_height():
                # Check if the widget still exists before accessing it
                try:
                    if message_widget is None:
                        return
                    text_edit = message_widget.findChild(QTextBrowser)
                    if text_edit:
                        # Force document to recalculate layout with current width
                        text_edit.document().setTextWidth(text_edit.viewport().width())
                        doc_height = text_edit.document().size().height()
                        height = int(doc_height) + 10  # Add extra padding for wrapped content
                        text_edit.setFixedHeight(height)
                except RuntimeError:
                    # Widget has been deleted, ignore
                    pass

            # Use a single-shot timer to recalculate after the widget is rendered
            QTimer.singleShot(0, recalculate_height)
            # Also recalculate on resize
            QTimer.singleShot(100, recalculate_height)

        # Scroll to the bottom is now handled by rangeChanged signal if stick_to_bottom is True
    
    def send_message(self):
        """
        Send a message
        """
        # Get the message text
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # Clear the input
        self.message_input.clear()
        
        # Add the message to the chat display
        self.stick_to_bottom = True  # Force scroll to bottom for user message
        self.add_message_widget(message, "You", True)
        
        # Emit the message sent signal
        self.message_sent.emit(message)
        
        # Reset the streaming response and flags
        self.streaming_response = ""
        self.streaming_handled = False

        # Start loading animation
        entity_type = "agent" if self.current_entity_type == "agent" else "llm"
        self.loading_indicator.start_animation(entity_type)
        
        # Start the update timer
        self.update_timer.start(100)
        
        # Define a callback to stop the timer when the message is sent
        def on_message_complete():
            self.update_timer.stop()
        
        # Run the async task in a separate thread
        run_async_in_thread(self._send_message_async, message, on_complete=on_message_complete)
    
    async def _send_message_async(self, message: str, on_complete=None):
        """
        Send a message asynchronously

        Args:
            message: Message text
            on_complete: Callback to call when the message is sent
        """
        try:
            # Disable input while processing
            QMetaObject.invokeMethod(self, "set_input_enabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, False))
            
            # Auto-rename thread if it's the first user message and thread has default name
            current_thread = self.session_manager.get_current_thread()
            if current_thread:
                # Check if thread has default "Chat HH:MM:SS" format name
                if current_thread.title.startswith("Chat ") and len(current_thread.title) == 13:
                    # Check if this is the first user message (chat history is empty or has only this message)
                    history = self.session_manager.get_current_chat_history()
                    if history and len(history.messages) == 0:
                        # Auto-rename to first 25 chars of message
                        new_title = message[:25] + ("..." if len(message) > 25 else "")
                        self.session_manager.rename_thread(current_thread.thread_id, new_title)
                        # Thread list will be refreshed by the session manager's thread callback

            # Send the message
            await self.session_manager.send_message(message)

            # Do one final update to ensure all chunks are displayed
            # Use QMetaObject.invokeMethod to call from the correct thread
            import time
            time.sleep(0.1)  # Small delay to ensure all callbacks have processed

            # Schedule UI updates in the main thread
            QMetaObject.invokeMethod(self, "_do_final_update", Qt.ConnectionType.QueuedConnection)

            # Call the completion callback if provided
            if on_complete:
                on_complete()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            QMetaObject.invokeMethod(self, "on_error_received", Qt.ConnectionType.QueuedConnection, Q_ARG(str, str(e)))
            # Stop the update timer using a helper slot
            QMetaObject.invokeMethod(self, "_stop_update_timer", Qt.ConnectionType.QueuedConnection)
            # Re-enable input on failure
            QMetaObject.invokeMethod(self, "set_input_enabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, True))

    @pyqtSlot(bool)
    def set_input_enabled(self, enabled: bool):
        """Enable or disable input fields"""
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)
        
        if enabled:
            self.message_input.setPlaceholderText("Type your message here...")
            # Restore background
            self.message_input.setStyleSheet(self.message_input.styleSheet().replace("background: #1f1f22;", "background: #2a2a2a;"))
            self.message_input.setFocus()
        else:
            self.message_input.setPlaceholderText("Waiting for task to complete...")
            # Darker background to indicate disabled state
            self.message_input.setStyleSheet(self.message_input.styleSheet().replace("background: #2a2a2a;", "background: #1f1f22;"))

    @pyqtSlot()
    def _do_final_update(self):
        """
        Do final update of streaming message (must be called from main thread)
        """
        # Ensure loading animation is stopped
        self.loading_indicator.stop_animation()

        self.update_streaming_message()
        self._finalize_streaming_message()

        # Re-enable input after message is complete
        # This handles both streaming and non-streaming LLM responses
        # For agents with polling/webhooks, input will be re-disabled if needed
        if self.current_entity_type == "llm":
            self.set_input_enabled(True)

    @pyqtSlot()
    def _stop_update_timer(self):
        """
        Stop the update timer (must be called from main thread)
        """
        self.update_timer.stop()

    def _finalize_streaming_message(self):
        """
        Finalize the streaming message by removing the streaming flag.
        Content is already rendered by update_content() - no need to re-render here.
        """
        logger.debug(f"Finalizing streaming message. Total length: {len(self.streaming_response)}")

        for i in range(self.chat_layout.count()):
            container = self.chat_layout.itemAt(i).widget()
            if not container:
                continue

            # Look for MessageWidget inside the container
            for j in range(container.layout().count() if container.layout() else 0):
                item = container.layout().itemAt(j)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, MessageWidget) and hasattr(widget, "is_streaming") and widget.is_streaming:
                        # Mark as no longer streaming (don't delete the attribute)
                        # Content is already properly rendered via update_content()
                        widget.is_streaming = False
                        logger.debug("Streaming widget finalized")
                        return
    
    
    @pyqtSlot(str, str, str)
    def on_message_received(self, sender_id: str, message: str, message_type: str):
        """
        Handle a new message

        Args:
            sender_id: ID of the sender
            message: Message text
            message_type: Type of the message
        """
        # Only handle messages from the current entity
        if message_type == "user":
            # User messages are handled by the send_message method
            return

        if self.current_entity_id == sender_id:
            # If streaming already handled this response, don't add a duplicate
            # The streaming path (update_streaming_message + _finalize_streaming_message)
            # already displayed the content
            if self.streaming_handled:
                logger.debug("Streaming already handled this response, skipping on_message_received")
                self.streaming_handled = False  # Reset for next message
                return

            # No streaming happened (e.g., non-streaming response or error recovery)
            # Add the message normally
            self.add_message_widget(message, sender_id)

            # Re-enable input for LLM responses (tool calling loop case)
            # Agents will keep input disabled if they're still in working/submitted state
            if message_type == "llm":
                self.set_input_enabled(True)
    
    @pyqtSlot(str, str, str)
    def on_streaming_chunk_received(self, sender_id: str, chunk: str, message_type: str):
        """
        Handle a streaming chunk

        Args:
            sender_id: ID of the sender
            chunk: Message chunk
            message_type: Type of the message

        Special signals:
            - "<<<STATUS>>>text": Update loading indicator with agent status message
            - "<<<CLEAR>>>": Clear streaming response (on state transition)
        """
        # Only handle chunks from the current entity
        if self.current_entity_id == sender_id:
            # Check for THINKING signal - route to loading indicator
            if chunk.startswith("<<<THINKING>>>"):
                thinking_text = chunk[14:]
                
                # Make sure loading indicator is visible
                if not self.loading_indicator.isVisible():
                    entity_type = "agent" if self.current_entity_type == "agent" else "llm"
                    QMetaObject.invokeMethod(
                        self.loading_indicator, "start_animation",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, entity_type)
                    )
                
                # Update the loading indicator with the thinking content
                # Use a specialized method if available, otherwise use custom status
                QMetaObject.invokeMethod(
                    self.loading_indicator, "set_thinking_status",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, thinking_text)
                )
                return

            # Check for STATUS signal - update loading indicator with custom status
            if chunk.startswith("<<<STATUS>>>"):
                status_text = chunk[12:]
                logger.info(f"Received STATUS signal (length: {len(status_text)})")

                # Update the loading indicator with the agent's status message
                # This overrides the default rotating phrases
                QMetaObject.invokeMethod(
                    self.loading_indicator, "set_custom_status",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, status_text)
                )

                # Make sure loading indicator is visible
                if not self.loading_indicator.isVisible():
                    entity_type = "agent" if self.current_entity_type == "agent" else "llm"
                    QMetaObject.invokeMethod(
                        self.loading_indicator, "start_animation",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, entity_type)
                    )
                return

            # Check for CLEAR signal to reset the streaming response
            # Note: CLEAR just resets state, don't stop animation - wait for real content
            if chunk == "<<<CLEAR>>>":
                logger.info("Received CLEAR signal")
                self.streaming_response = ""

                # Clear custom status when state transitions
                QMetaObject.invokeMethod(
                    self.loading_indicator, "clear_custom_status",
                    Qt.ConnectionType.QueuedConnection
                )
                # Don't stop animation here - wait for actual content to arrive
                return

            # Check for TASK_ID signal
            if chunk.startswith("<<<TASK_ID>>>"):
                task_id = chunk[13:]
                self._polling_task_id = task_id
                logger.info(f"Captured task ID: {task_id}")
                # Ensure input remains disabled
                QMetaObject.invokeMethod(self, "set_input_enabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, False))
                return

            # Check for POLL_REQUIRED signal
            if chunk.startswith("<<<POLL_REQUIRED>>>"):
                logger.info("Manual polling required signal received")
                if self._polling_task_id:
                    self._show_polling_widget(self._polling_task_id)
                self.loading_indicator.stop_animation()
                # Ensure input remains disabled
                QMetaObject.invokeMethod(self, "set_input_enabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, False))
                return

            # Check for NOTIFICATION_RECEIVED signal
            if chunk.startswith("<<<NOTIFICATION_RECEIVED>>>"):
                logger.info("Notification received signal")
                QMetaObject.invokeMethod(
                    self.loading_indicator, "show_notification_received",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, self.current_entity_id or "Agent")
                )
                return

            # Stop loading animation when receiving real content
            # Use thread-safe method via QMetaObject
            if self.loading_indicator.isVisible():
                QMetaObject.invokeMethod(
                    self.loading_indicator, "stop_animation",
                    Qt.ConnectionType.QueuedConnection
                )
                
            # If we received content, usually means task is done or prompting
            # But let the specific polling/webhook logic handle critical re-enabling
            # unless it's a simple message (LLM or non-task agent)
            # For safe measure, if it's NOT a special signal, we might want to re-enable?
            # Actually, for task agents, AgentComm yields content ONLY when terminal/interrupted
            # So if we get real content, we can enable input.
            if not chunk.startswith("<<<"):
                 QMetaObject.invokeMethod(self, "set_input_enabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, True))
            
            # Hide polling widget if real content arrives (state changed to terminal)
            if self._polling_widget and self._polling_widget.isVisible():
                self._polling_widget.deleteLater()
                self._polling_widget = None

            # Mark that streaming is handling this response (prevents duplicate in on_message_received)
            self.streaming_handled = True

            # Append the chunk to the streaming response
            self.streaming_response += chunk
            logger.debug(f"Streaming chunk received. Total length now: {len(self.streaming_response)}")
            
    def _show_polling_widget(self, task_id: str):
        """Show the manual polling widget"""
        # Remove existing if present
        if self._polling_widget:
            self._polling_widget.deleteLater()
            
        self._polling_widget = TaskPollingWidget(task_id)
        self._polling_widget.refresh_clicked.connect(self.trigger_manual_poll)
        
        # Add to chat layout (AI side)
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self._polling_widget)
        # Add stretch to keep it left-aligned (AI side)
        container_layout.addStretch()
        
        self.chat_layout.addWidget(container)
        
        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.chat_scroll_area.verticalScrollBar().setValue(
            self.chat_scroll_area.verticalScrollBar().maximum()
        ))
        
    def trigger_manual_poll(self, task_id: str):
        """Trigger a manual poll for task status"""
        logger.info(f"Triggering manual poll for task {task_id}")
        
        # Start loading indicator again slightly
        entity_type = "agent" if self.current_entity_type == "agent" else "llm"
        self.loading_indicator.start_animation(entity_type)
        self.loading_indicator.start_animation(entity_type)
        self.loading_indicator.set_custom_status("Agent is active - Input disabled")
        
        run_async_in_thread(self._do_manual_poll_async, task_id)
        
    async def _do_manual_poll_async(self, task_id: str):
        """Perform manual poll asynchronously"""
        try:
            if not self.session_manager.agent_comm:
                logger.error("No agent_comm available for polling")
                return

            # Call get_task_status directly
            result = await self.session_manager.agent_comm.get_task_status(task_id)
            
            # Handle result in main thread
            QMetaObject.invokeMethod(
                self, "_handle_poll_result",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(object, result)
            )
            
        except Exception as e:
            logger.error(f"Error polling task: {e}")
            QMetaObject.invokeMethod(self, "on_error_received", Qt.ConnectionType.QueuedConnection, Q_ARG(str, str(e)))

    @pyqtSlot(object)
    def _handle_poll_result(self, result):
        """Handle the result of a manual poll"""
        # Reset button state
        if self._polling_widget:
            self._polling_widget.reset_button()
            
        state = result.state
        
        if state.is_terminal():
            # Task finished!
            logger.info(f"Poll result: Terminal state {state.value}")
            
            # Remove polling widget
            if self._polling_widget:
                self._polling_widget.deleteLater()
                self._polling_widget = None
                
            # Stop loading indicator
            self.loading_indicator.stop_animation()
            
            # Add final content
            content = result.content
            # Use defaults if empty (handled by AgentComm but safe check)
            if not content:
                from agentcomm.agents.task_state import DEFAULT_STATE_MESSAGES
                content = DEFAULT_STATE_MESSAGES.get(state, "Task completed.")
                
            # Perform saving to history
            self.session_manager.receive_agent_response(content)
            
            self.add_message_widget(content, self.current_entity_id or "Agent")
            # Enable input for terminal states
            self.set_input_enabled(True)
            
        elif state.is_interrupted():
            # User input required
            logger.info(f"Poll result: Interrupted state {state.value}")
            
            # Update status message
            msg = result.status_message or "Action required"
            self.loading_indicator.set_custom_status(msg)
            
            # Maybe show content if any (prompt)
            if result.content:
                # Perform saving to history
                self.session_manager.receive_agent_response(result.content)
                self.add_message_widget(result.content, self.current_entity_id or "Agent")
                
            # Enable input for interrupted states logic (user needs to reply)
            self.set_input_enabled(True)
                
        else:
            # Still working
            logger.info(f"Poll result: Active state {state.value}")
            msg = result.status_message or "Agent is still working..."
            self.loading_indicator.set_custom_status(msg)
            
            # Keep input disabled
            self.set_input_enabled(False)
            
            # Keep polling widget visible
            # Maybe auto-close loading indicator if we want to rely on the button?
            # But the button "Refreshing..." state is good feedback.
            # Let's stop the main indicator after a brief delay so user sees "Checking..." then back to button
            # Use lambda to ensure the call happens in the correct thread
            QTimer.singleShot(1500, lambda: self.loading_indicator.stop_animation())
    
    @pyqtSlot(str)
    def on_error_received(self, error_message: str):
        """Handle error, display and stop loading"""
        self.loading_indicator.stop_animation()
        self.loading_indicator.stop_animation()
        self.add_message_widget(f"Error: {error_message}", "System")
        
        # Always re-enable input on error so user isn't stuck
        self.set_input_enabled(True)
    
    def reset_thread(self):
        """
        Reset the current thread by clearing all messages
        """
        # Confirm with the user before resetting
        from agentcomm.ui.custom_dialogs import StyledMessageBox

        if StyledMessageBox.question(
            self,
            "Clear Chat",
            "Are you sure you want to clear this chat? All messages will be deleted."
        ):
            # Reset the chat history in the session manager
            if self.session_manager.reset_current_thread():
                # Clear the UI
                self.clear_chat()
                logger.info("Thread reset successfully")
            else:
                logger.warning("Failed to reset thread")

    def update_streaming_message(self):
        """
        Update the streaming message in the chat display
        """
        if not self.streaming_response:
            return

        # Check if there's already a streaming message widget
        # We need to search through containers now
        streaming_widget = None
        streaming_container = None
        streaming_count = 0

        for i in range(self.chat_layout.count()):
            container = self.chat_layout.itemAt(i).widget()
            if not container:
                continue

            # Look for MessageWidget inside the container
            for j in range(container.layout().count() if container.layout() else 0):
                item = container.layout().itemAt(j)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, MessageWidget) and hasattr(widget, "is_streaming") and widget.is_streaming:
                        streaming_count += 1
                        if not streaming_widget:
                            streaming_widget = widget
                            streaming_container = container

        # Debug: log if multiple streaming widgets found
        if streaming_count > 1:
            logger.warning(f"Found {streaming_count} streaming widgets! Removing duplicates...")
            # Remove duplicate streaming widgets
            for i in range(self.chat_layout.count() - 1, -1, -1):
                container = self.chat_layout.itemAt(i).widget()
                if not container:
                    continue

                for j in range(container.layout().count() if container.layout() else 0):
                    item = container.layout().itemAt(j)
                    if item and item.widget():
                        widget = item.widget()
                        if isinstance(widget, MessageWidget) and hasattr(widget, "is_streaming") and widget.is_streaming:
                            if widget != streaming_widget:
                                logger.warning(f"Removing duplicate streaming container at position {i}")
                                self.chat_layout.removeWidget(container)
                                container.deleteLater()
                                break

        if streaming_widget:
            # Update the existing widget
            streaming_widget.update_content(self.streaming_response)
        else:
            # Create a new widget with container
            logger.debug(f"Creating new streaming widget for entity: {self.current_entity_id}")

            # Create container for alignment
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)

            # Determine the icon based on entity type
            sender_icon = "🤖"  # Default to agent icon
            if self.current_entity_type == "llm":
                sender_icon = "🧠"  # Use brain icon for LLMs

            # Create message widget
            streaming_widget = MessageWidget(self.streaming_response, self.current_entity_id or "Assistant", is_user=False, sender_icon=sender_icon)
            streaming_widget.is_streaming = True

            # AI message - full width, no spacer
            container_layout.addWidget(streaming_widget)

            self.chat_layout.addWidget(container)

        # Scroll to the bottom is now handled by rangeChanged signal if stick_to_bottom is True

    def delete_current_thread(self):
        """
        Delete the current thread
        """
        current_thread = self.session_manager.get_current_thread()
        if not current_thread:
            logger.warning("No thread selected")
            return

        # Get thread count
        threads = self.session_manager.get_threads_for_entity()
        if len(threads) <= 1:
            from agentcomm.ui.custom_dialogs import StyledMessageBox
            StyledMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the last thread. At least one thread must exist."
            )
            return

        # Confirm deletion
        from agentcomm.ui.custom_dialogs import StyledMessageBox

        if StyledMessageBox.question(
            self,
            "Delete Thread",
            f"Are you sure you want to delete thread '{current_thread.title}'? This action cannot be undone."
        ):
            if self.session_manager.delete_thread(current_thread.thread_id):
                # Thread list will be refreshed by callback
                # Load the new current thread
                self.clear_chat()
                self.load_chat_history()


