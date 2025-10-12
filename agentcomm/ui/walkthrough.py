"""
Interactive walkthrough/onboarding system for first-time users.
"""
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
import json
import os


class WalkthroughOverlay(QWidget):
    """Overlay widget that highlights UI elements and shows tooltips."""

    next_step = pyqtSignal()
    previous_step = pyqtSignal()
    skip_walkthrough = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.highlight_rect = QRect()
        self.tooltip_text = ""
        self.step_number = 0
        self.total_steps = 0
        self.title = ""

        # Create tooltip widget
        self._setup_tooltip()

        # Hide by default - only show when start() is called
        self.hide()

    def _setup_tooltip(self):
        """Setup the tooltip widget with modern styling."""
        self.tooltip_widget = QWidget(self)
        self.tooltip_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7C3AED, stop:1 #EC4899);
                border-radius: 12px;
                padding: 20px;
            }
            QLabel {
                color: white;
                background: transparent;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.3);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.1);
            }
            QPushButton#skipButton {
                background: rgba(255, 100, 100, 0.3);
            }
            QPushButton#skipButton:hover {
                background: rgba(255, 100, 100, 0.5);
            }
        """)

        layout = QVBoxLayout(self.tooltip_widget)
        layout.setSpacing(12)

        # Title label
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Description label
        self.description_label = QLabel()
        self.description_label.setFont(QFont("Segoe UI", 11))
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        # Step indicator
        self.step_label = QLabel()
        self.step_label.setFont(QFont("Segoe UI", 9))
        self.step_label.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        layout.addWidget(self.step_label)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("skipButton")
        self.skip_button.clicked.connect(self.skip_walkthrough.emit)

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_step.emit)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self._on_next_clicked)

        button_layout.addWidget(self.skip_button)
        button_layout.addStretch()
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)

        layout.addLayout(button_layout)

        self.tooltip_widget.hide()

    def _on_next_clicked(self):
        """Handle next button click."""
        if self.step_number >= self.total_steps - 1:
            self.finished.emit()
        else:
            self.next_step.emit()

    def set_step(self, title, description, highlight_rect, step_num, total_steps):
        """Set the current walkthrough step."""
        self.title = title
        self.tooltip_text = description
        self.highlight_rect = highlight_rect
        self.step_number = step_num
        self.total_steps = total_steps

        # Update labels
        self.title_label.setText(title)
        self.description_label.setText(description)
        self.step_label.setText(f"Step {step_num + 1} of {total_steps}")

        # Update button states
        self.prev_button.setEnabled(step_num > 0)
        self.next_button.setText("Finish" if step_num >= total_steps - 1 else "Next")

        # Position tooltip
        self._position_tooltip()

        self.tooltip_widget.show()
        self.update()

    def _position_tooltip(self):
        """Position the tooltip widget near the highlighted area."""
        if self.highlight_rect.isNull():
            # Center on screen
            self.tooltip_widget.adjustSize()
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.tooltip_widget.width()) // 2
            y = (parent_rect.height() - self.tooltip_widget.height()) // 2
            self.tooltip_widget.move(x, y)
        else:
            # Position below or above the highlight
            self.tooltip_widget.adjustSize()
            tooltip_width = min(400, self.tooltip_widget.width())
            tooltip_height = self.tooltip_widget.height()

            parent_rect = self.parent().rect()

            # Try to position below the highlight
            x = self.highlight_rect.center().x() - tooltip_width // 2
            y = self.highlight_rect.bottom() + 20

            # Check if tooltip goes off-screen at bottom
            if y + tooltip_height > parent_rect.height() - 20:
                # Position above instead
                y = self.highlight_rect.top() - tooltip_height - 20

            # Check if tooltip goes off-screen at top
            if y < 20:
                # If not enough room above or below, position to the side
                if self.highlight_rect.right() + tooltip_width + 40 < parent_rect.width():
                    # Position to the right
                    x = self.highlight_rect.right() + 20
                    y = self.highlight_rect.center().y() - tooltip_height // 2
                elif self.highlight_rect.left() - tooltip_width - 20 > 0:
                    # Position to the left
                    x = self.highlight_rect.left() - tooltip_width - 20
                    y = self.highlight_rect.center().y() - tooltip_height // 2
                else:
                    # Last resort: center on screen
                    y = 20

            # Ensure tooltip doesn't go off-screen horizontally
            if x < 20:
                x = 20
            elif x + tooltip_width > parent_rect.width() - 20:
                x = parent_rect.width() - tooltip_width - 20

            # Final vertical bounds check
            if y < 20:
                y = 20
            if y + tooltip_height > parent_rect.height() - 20:
                y = parent_rect.height() - tooltip_height - 20

            self.tooltip_widget.setFixedWidth(tooltip_width)
            self.tooltip_widget.move(x, y)

    def paintEvent(self, event):
        """Draw the overlay with highlight."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw semi-transparent overlay
        overlay_color = QColor(0, 0, 0, 180)
        painter.fillRect(self.rect(), overlay_color)

        # Clear the highlighted area
        if not self.highlight_rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.highlight_rect, Qt.GlobalColor.transparent)

            # Draw highlight border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(124, 58, 237), 3)  # Purple border
            painter.setPen(pen)
            painter.drawRoundedRect(self.highlight_rect.adjusted(-2, -2, 2, 2), 8, 8)

            # Draw glowing effect
            for i in range(3):
                alpha = 50 - (i * 15)
                pen.setColor(QColor(124, 58, 237, alpha))
                pen.setWidth(3 + i * 2)
                painter.setPen(pen)
                painter.drawRoundedRect(
                    self.highlight_rect.adjusted(-2 - i*2, -2 - i*2, 2 + i*2, 2 + i*2),
                    8 + i*2, 8 + i*2
                )

    def showEvent(self, event):
        """Resize overlay to match parent."""
        if self.parent():
            self.setGeometry(self.parent().rect())
            self.raise_()  # Ensure overlay is on top
        super().showEvent(event)

    def resizeEvent(self, event):
        """Reposition tooltip on resize."""
        super().resizeEvent(event)
        if self.tooltip_widget.isVisible():
            self._position_tooltip()


class WalkthroughStep:
    """Represents a single step in the walkthrough."""

    def __init__(self, title, description, target_widget_name, offset=(0, 0, 0, 0)):
        """
        Args:
            title: Step title
            description: Step description
            target_widget_name: Object name of the widget to highlight
            offset: Tuple of (left, top, right, bottom) offset adjustments
        """
        self.title = title
        self.description = description
        self.target_widget_name = target_widget_name
        self.offset = offset


class WalkthroughManager:
    """Manages the walkthrough flow and steps."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.overlay = WalkthroughOverlay(main_window)
        self.current_step_index = 0
        self.steps = []

        # Ensure overlay is hidden initially
        self.overlay.hide()

        # Connect signals
        self.overlay.next_step.connect(self.next_step)
        self.overlay.previous_step.connect(self.previous_step)
        self.overlay.skip_walkthrough.connect(self.skip)
        self.overlay.finished.connect(self.finish)

        # Define walkthrough steps
        self._define_steps()

    def _define_steps(self):
        """Define all walkthrough steps."""
        self.steps = [
            WalkthroughStep(
                "Welcome to AgentComm! 👋",
                "This quick walkthrough will help you understand all the features of this application. "
                "You can skip this at any time by clicking the Skip button.",
                None  # No highlight for welcome
            ),
            WalkthroughStep(
                "🤖 Agent Selection Panel",
                "Here in the left sidebar you can see all available agents with the robot icon (🤖). "
                "Click on any agent to start chatting with it. Active agents have an orange glow! "
                "Each agent has specialized capabilities for different tasks.",
                "agent_list",
                (-10, -10, 10, 10)
            ),
            WalkthroughStep(
                "🧠 LLM Selection Panel",
                "Below the agents, you'll find LLMs (Large Language Models) with the brain icon (🧠). "
                "You can chat directly with OpenAI, Google Gemini, Anthropic Claude, or Local LLMs. "
                "Active LLMs have a yellow glow!",
                "llms_list",
                (-10, -10, 10, 10)
            ),
            WalkthroughStep(
                "↻ Refresh Button",
                "Click this circular refresh button (↻) to reload the list of available agents. "
                "It features a beautiful purple gradient and appears at the bottom of the Agents section.",
                "refresh_agents_button",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "💬 Chat Threads",
                "At the very top of the left sidebar, you'll find the thread dropdown labeled 'Chats:'. "
                "Threads help you organize multiple conversations. Each thread maintains its own history "
                "for the currently selected agent or LLM.",
                "thread_selector",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "➕ New Thread",
                "Right next to the thread dropdown, click the plus button (➕) to create a new conversation thread. "
                "This allows you to have multiple separate conversations with the same agent or LLM.",
                "new_thread_button",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "✏️ Rename Thread",
                "Click the pencil icon (✏️) next to the plus button to give your threads meaningful names. "
                "This helps you organize and find specific conversations later.",
                "rename_thread_button",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "🗑 Delete Thread",
                "Click the trash icon (🗑) in the top-right corner of the chat area to remove unwanted threads. "
                "Note: The delete button is in the chat area, while thread selection is in the sidebar. "
                "Be careful - this action cannot be undone!",
                "delete_thread_button",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "💬 Chat Display Area",
                "This is where your conversations appear. "
                "Your messages appear on the right with a gray background, "
                "and AI responses appear on the left with the agent/LLM icon and name.",
                "chat_display",
                (-10, -10, 10, 10)
            ),
            WalkthroughStep(
                "⌨️ Message Input",
                "Type your messages in this text box at the bottom. "
                "You can have natural conversations with AI agents and LLMs!",
                "message_input",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "↻ Clear Chat Button",
                "The circular arrow button (↻) next to the input clears the current thread's history. "
                "This gives you a fresh start while keeping the thread itself.",
                "reset_button",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "➤ Send Button",
                "Click the blue arrow button (➤) to send your message. "
                "Your message will be delivered to the selected agent or LLM, and you'll see the response appear in the chat area.",
                "send_button",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "⚙ Settings (Top Right)",
                "Click the gear icon (⚙) in the top-right corner of the menu bar to access settings. "
                "Here you can configure agents, manage LLM API keys, and customize the application. "
                "The icon turns blue when you hover over it!",
                "settings_action",
                (-5, -5, 5, 5)
            ),
            WalkthroughStep(
                "You're All Set! 🎉",
                "That's everything! You now know how to:\n"
                "• Select agents (🤖) and LLMs (🧠) from the left sidebar\n"
                "• Manage chat threads (💬 ➕ ✏️) at the top of the sidebar\n"
                "• Delete threads (🗑) from the chat area's top-right\n"
                "• Send messages (➤) and clear history (↻)\n"
                "• Access settings (⚙) in the menu bar\n\n"
                "You can replay this walkthrough anytime from Help → Show Walkthrough. Happy chatting!",
                None
            )
        ]

    def start(self):
        """Start the walkthrough."""
        print("Starting walkthrough...")
        self.current_step_index = 0
        self.overlay.show()
        self.overlay.raise_()
        print(f"Overlay shown, showing step 1 of {len(self.steps)}")
        self._show_current_step()

    def _show_current_step(self):
        """Display the current step."""
        if self.current_step_index >= len(self.steps):
            self.finish()
            return

        step = self.steps[self.current_step_index]

        # Find the target widget and get its geometry
        highlight_rect = QRect()
        if step.target_widget_name:
            target_widget = self.main_window.findChild(QWidget, step.target_widget_name)
            if target_widget and target_widget.isVisible():
                # Get global position and map to overlay coordinates
                global_pos = target_widget.mapTo(self.main_window, QPoint(0, 0))
                highlight_rect = QRect(
                    global_pos.x() + step.offset[0],
                    global_pos.y() + step.offset[1],
                    target_widget.width() + step.offset[2] - step.offset[0],
                    target_widget.height() + step.offset[3] - step.offset[1]
                )

        self.overlay.set_step(
            step.title,
            step.description,
            highlight_rect,
            self.current_step_index,
            len(self.steps)
        )

    def next_step(self):
        """Move to the next step."""
        self.current_step_index += 1
        self._show_current_step()

    def previous_step(self):
        """Move to the previous step."""
        if self.current_step_index > 0:
            self.current_step_index -= 1
            self._show_current_step()

    def skip(self):
        """Skip the walkthrough."""
        self.overlay.hide()
        self._mark_walkthrough_completed()

    def finish(self):
        """Finish the walkthrough."""
        self.overlay.hide()
        self._mark_walkthrough_completed()

    def _mark_walkthrough_completed(self):
        """Mark walkthrough as completed in settings."""
        config_dir = os.path.join(os.path.expanduser("~"), ".agentcomm")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "user_preferences.json")

        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                config = {}

            config['walkthrough_completed'] = True

            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving walkthrough state: {e}")

    @staticmethod
    def is_first_time_user():
        """Check if this is the user's first time using the app."""
        config_file = os.path.join(os.path.expanduser("~"), ".agentcomm", "user_preferences.json")

        print(f"Checking first time user. Config file: {config_file}")
        print(f"File exists: {os.path.exists(config_file)}")

        if not os.path.exists(config_file):
            print("Config file doesn't exist - first time user")
            return True

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            completed = config.get('walkthrough_completed', False)
            print(f"Walkthrough completed flag: {completed}")
            return not completed
        except Exception as e:
            print(f"Error reading config: {e}")
            return True
