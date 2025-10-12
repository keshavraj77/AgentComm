#!/usr/bin/env python3
"""
Chat Widget for A2A Client
"""

import logging
import asyncio
import threading
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QScrollArea, QLabel, QSplitter, QFrame, QComboBox, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QMetaObject, Q_ARG
from PyQt6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat

from agentcomm.core.session_manager import SessionManager
from agentcomm.llm.chat_history import ChatHistory, ChatMessage

logger = logging.getLogger(__name__)


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

class MessageWidget(QFrame):
    """
    Widget for displaying a single message in the chat
    """

    def __init__(self, message: str, sender: str, is_user: bool = False, parent: Optional[QWidget] = None):
        """
        Initialize the message widget

        Args:
            message: Message text
            sender: Sender name
            is_user: Whether the message is from the user
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
            sender_label = QLabel(sender)
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
            # QTextEdit for AI messages (needed for streaming updates)
            message_text = QTextEdit()
            message_text.setReadOnly(True)
            message_text.setPlainText(message)
            message_text.setFrameStyle(QFrame.Shape.NoFrame)
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

            # Remove ALL margins and padding for tighter fit
            doc = message_text.document()
            doc.setDocumentMargin(0)
            message_text.setContentsMargins(0, 0, 0, 0)
            message_text.setViewportMargins(0, 0, 0, 0)

            # Align text to top
            from PyQt6.QtGui import QTextOption
            message_text.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop))

            # Set width for proper text wrapping calculation
            message_text.setMaximumWidth(700)
            doc.setTextWidth(700)

            # Calculate height based on content - must be done after setting width
            doc_height = doc.size().height()
            # Add small buffer for proper display, no maximum limit
            calculated_height = int(doc_height) + 5
            message_text.setMinimumHeight(calculated_height)
            message_text.setMaximumHeight(calculated_height)

            layout.addWidget(message_text, 0, Qt.AlignmentFlag.AlignTop)


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

        # Register callbacks with thread-safe wrappers
        self.session_manager.register_message_callback(self._thread_safe_message_callback)
        self.session_manager.register_streaming_callback(self._thread_safe_streaming_callback)
        self.session_manager.register_error_callback(self._thread_safe_error_callback)
        self.session_manager.register_thread_callback(self._thread_safe_thread_callback)
        
        # Create the layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Create thread selector header
        self.thread_header = QHBoxLayout()
        self.thread_header.setContentsMargins(10, 5, 10, 5)
        self.thread_header.setSpacing(10)

        # Thread selector label
        thread_label = QLabel("Thread:")
        thread_label.setStyleSheet("""
            color: #9ca3af;
            font-size: 12px;
            font-weight: 600;
        """)
        self.thread_header.addWidget(thread_label)

        # Thread dropdown
        self.thread_selector = QComboBox()
        self.thread_selector.setFixedWidth(200)
        self.thread_selector.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                color: #e5e7eb;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                color: #e5e7eb;
                selection-background-color: #3b82f6;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
        """)
        self.thread_selector.currentIndexChanged.connect(self.on_thread_changed)
        self.thread_header.addWidget(self.thread_selector)

        # New thread button
        self.new_thread_btn = QPushButton("New")
        self.new_thread_btn.setFixedWidth(60)
        self.new_thread_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        self.new_thread_btn.clicked.connect(self.create_new_thread)
        self.thread_header.addWidget(self.new_thread_btn)

        # Rename thread button
        self.rename_thread_btn = QPushButton("Rename")
        self.rename_thread_btn.setFixedWidth(70)
        self.rename_thread_btn.setStyleSheet("""
            QPushButton {
                background: #3f3f46;
                color: #e5e7eb;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background: #52525b;
            }
        """)
        self.rename_thread_btn.clicked.connect(self.rename_current_thread)
        self.thread_header.addWidget(self.rename_thread_btn)

        # Delete thread button
        self.delete_thread_btn = QPushButton("Delete")
        self.delete_thread_btn.setFixedWidth(70)
        self.delete_thread_btn.setStyleSheet("""
            QPushButton {
                background: #3f3f46;
                color: #e5e7eb;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background: #ef4444;
            }
        """)
        self.delete_thread_btn.clicked.connect(self.delete_current_thread)
        self.thread_header.addWidget(self.delete_thread_btn)

        # Clear chat button
        self.clear_chat_btn = QPushButton("Clear")
        self.clear_chat_btn.setFixedWidth(60)
        self.clear_chat_btn.setStyleSheet("""
            QPushButton {
                background: #3f3f46;
                color: #e5e7eb;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background: #ef4444;
            }
        """)
        self.clear_chat_btn.clicked.connect(self.reset_thread)
        self.thread_header.addWidget(self.clear_chat_btn)

        self.thread_header.addStretch()

        self.layout.addLayout(self.thread_header)

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

        self.send_button = QPushButton("Send")
        self.send_button.setFixedWidth(80)
        self.send_button.setFixedHeight(50)
        self.send_button.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 12px;
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
        QMetaObject.invokeMethod(
            self, "refresh_thread_list",
            Qt.ConnectionType.QueuedConnection
        )

    def set_current_entity(self, entity_id: str, entity_type: str):
        """
        Set the current entity (agent or LLM)

        Args:
            entity_id: ID of the entity
            entity_type: Type of the entity (agent or llm)
        """
        self.current_entity_id = entity_id
        self.current_entity_type = entity_type

        # Refresh thread list for the new entity
        self.refresh_thread_list()

        # Clear the chat display
        self.clear_chat()

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

        # Create the message widget
        message_widget = MessageWidget(message, sender, is_user)

        # Set max width for better readability
        # User messages: no max width, let them shrink to content
        # AI messages: limit width for readability
        if not is_user:
            message_widget.setMaximumWidth(700)

        if is_user:
            # User messages: add spacer on left, message on right
            container_layout.addStretch()
            container_layout.addWidget(message_widget)
        else:
            # AI messages: message on left, spacer on right
            container_layout.addWidget(message_widget)
            container_layout.addStretch()

        self.chat_layout.addWidget(container)

        # Scroll to the bottom
        self.chat_scroll_area.verticalScrollBar().setValue(
            self.chat_scroll_area.verticalScrollBar().maximum()
        )
    
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
        self.add_message_widget(message, "You", True)
        
        # Emit the message sent signal
        self.message_sent.emit(message)
        
        # Reset the streaming response
        self.streaming_response = ""
        
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
            # Stop the update timer
            QMetaObject.invokeMethod(self.update_timer, "stop", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _do_final_update(self):
        """
        Do final update of streaming message (must be called from main thread)
        """
        self.update_streaming_message()
        self._finalize_streaming_message()

    def _finalize_streaming_message(self):
        """
        Finalize the streaming message by updating with final content and removing streaming flag
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
                        # Update the widget with the final streaming response
                        message_text = widget.findChild(QTextEdit)
                        if message_text and self.streaming_response:
                            message_text.setPlainText(self.streaming_response)
                            # Update the height - ensure full content is visible
                            doc = message_text.document()
                            doc.setTextWidth(700)
                            doc_height = doc.size().height()
                            calculated_height = int(doc_height) + 5
                            message_text.setMinimumHeight(calculated_height)
                            message_text.setMaximumHeight(calculated_height)
                            logger.debug(f"Updated streaming widget with final text: {self.streaming_response[:50]}...")

                        # Mark as no longer streaming (don't delete the attribute)
                        widget.is_streaming = False
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
            # Check if there's already a streaming widget - if so, finalize it
            # The streaming response is already being displayed via update_streaming_message
            # We don't need to add a duplicate message
            streaming_widget = None

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
                            streaming_widget = widget
                            break

                if streaming_widget:
                    break

            if streaming_widget:
                # Finalize the streaming widget by removing the is_streaming flag
                streaming_widget.is_streaming = False
            else:
                # Only add a new message if there's no streaming widget
                # (This happens for non-streaming responses)
                self.add_message_widget(message, sender_id)
    
    @pyqtSlot(str, str, str)
    def on_streaming_chunk_received(self, sender_id: str, chunk: str, message_type: str):
        """
        Handle a streaming chunk

        Args:
            sender_id: ID of the sender
            chunk: Message chunk
            message_type: Type of the message
        """
        # Only handle chunks from the current entity
        if self.current_entity_id == sender_id:
            # Check for CLEAR signal to reset the streaming response
            if chunk == "<<<CLEAR>>>":
                logger.info("Received CLEAR signal - resetting streaming response")
                self.streaming_response = ""
                return

            # Append the chunk to the streaming response
            self.streaming_response += chunk
            logger.debug(f"Streaming chunk received. Total length now: {len(self.streaming_response)}")
    
    @pyqtSlot(str)
    def on_error_received(self, error_message: str):
        """
        Handle an error
        
        Args:
            error_message: Error message
        """
        # Add the error message to the chat display
        self.add_message_widget(f"Error: {error_message}", "System")
    
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
            message_text = streaming_widget.findChild(QTextEdit)
            if message_text:
                message_text.setPlainText(self.streaming_response)

                # Update the height - ensure full content is visible
                doc = message_text.document()
                doc.setTextWidth(700)
                doc_height = doc.size().height()
                calculated_height = int(doc_height) + 5
                message_text.setMinimumHeight(calculated_height)
                message_text.setMaximumHeight(calculated_height)
        else:
            # Create a new widget with container
            logger.debug(f"Creating new streaming widget for entity: {self.current_entity_id}")

            # Create container for alignment
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)

            # Create message widget
            streaming_widget = MessageWidget(self.streaming_response, self.current_entity_id or "Assistant", is_user=False)
            streaming_widget.is_streaming = True
            streaming_widget.setMaximumWidth(700)

            # AI message - left aligned
            container_layout.addWidget(streaming_widget)
            container_layout.addStretch()

            self.chat_layout.addWidget(container)

        # Scroll to the bottom
        self.chat_scroll_area.verticalScrollBar().setValue(
            self.chat_scroll_area.verticalScrollBar().maximum()
        )

    @pyqtSlot()
    def refresh_thread_list(self):
        """
        Refresh the thread dropdown list
        """
        # Block signals to avoid triggering on_thread_changed
        self.thread_selector.blockSignals(True)

        # Save current selection
        current_thread = self.session_manager.get_current_thread()
        current_thread_id = current_thread.thread_id if current_thread else None

        # Clear and repopulate the dropdown
        self.thread_selector.clear()

        # Get threads for the current entity
        threads = self.session_manager.get_threads_for_entity()

        # Add threads to dropdown
        for thread in threads:
            self.thread_selector.addItem(thread.title, thread.thread_id)

        # Restore selection
        if current_thread_id:
            index = self.thread_selector.findData(current_thread_id)
            if index >= 0:
                self.thread_selector.setCurrentIndex(index)

        # Re-enable signals
        self.thread_selector.blockSignals(False)

        # Update button states
        has_threads = len(threads) > 0
        self.rename_thread_btn.setEnabled(has_threads)
        self.delete_thread_btn.setEnabled(has_threads and len(threads) > 1)
        self.clear_chat_btn.setEnabled(has_threads)

    def on_thread_changed(self, index: int):
        """
        Handle thread selection change

        Args:
            index: Index of the selected thread
        """
        if index < 0:
            return

        thread_id = self.thread_selector.itemData(index)
        if thread_id and self.session_manager.switch_thread(thread_id):
            # Clear and reload chat
            self.clear_chat()
            self.load_chat_history()

    def create_new_thread(self):
        """
        Create a new thread for the current entity
        """
        if not self.current_entity_id:
            logger.warning("No entity selected")
            return

        thread_id = self.session_manager.create_thread(self.current_entity_id, self.current_entity_type)
        if thread_id:
            # Switch to the new thread
            if self.session_manager.switch_thread(thread_id):
                # Refresh the thread list and load history
                self.refresh_thread_list()
                self.clear_chat()
                self.load_chat_history()

    def rename_current_thread(self):
        """
        Rename the current thread
        """
        current_thread = self.session_manager.get_current_thread()
        if not current_thread:
            logger.warning("No thread selected")
            return

        # Prompt for new name
        new_title, ok = QInputDialog.getText(
            self,
            "Rename Thread",
            "Enter new thread name:",
            text=current_thread.title
        )

        if ok and new_title.strip():
            if self.session_manager.rename_thread(current_thread.thread_id, new_title.strip()):
                self.refresh_thread_list()

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


