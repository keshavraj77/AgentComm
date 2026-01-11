"""
Loading Indicator Widget for A2A Client

Features:
- Glowing star animation that morphs from a dot
- Flowing color animation through the text
- LLM mode: Static message (doesn't rotate)
- A2A mode: Dynamic messages from agent status updates
"""

import math
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSlot, pyqtProperty, QPointF, QRectF
)
from PyQt6.QtGui import (
    QColor, QPainter, QPolygonF, QRadialGradient, QBrush, QPen,
    QLinearGradient, QFont, QFontMetrics
)


class MorphingIcon(QWidget):
    """
    Custom widget that animates: + (cross) → * (star with more lines) → ○ (circle)
    The animation loops continuously.
    """
    def __init__(self, parent=None, size=20):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._morph_phase = 0.0  # 0.0 = +, 0.5 = star, 1.0 = circle
        self._rotation = 0

        # Animation timer for smooth morphing
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_animation)
        self.anim_timer.setInterval(25)  # ~40 FPS

        # Animation state
        self._phase_direction = 1  # 1 = forward, -1 = backward
        self._phase_speed = 0.012

    @pyqtProperty(float)
    def morph_phase(self):
        return self._morph_phase

    @morph_phase.setter
    def morph_phase(self, value):
        self._morph_phase = value
        self.update()

    def _update_animation(self):
        # Update morph phase (oscillate between 0 and 1)
        self._morph_phase += self._phase_speed * self._phase_direction
        if self._morph_phase >= 1.0:
            self._morph_phase = 1.0
            self._phase_direction = -1
        elif self._morph_phase <= 0.0:
            self._morph_phase = 0.0
            self._phase_direction = 1

        # Slow rotation
        self._rotation = (self._rotation + 0.8) % 360

        self.update()

    def start(self):
        self._morph_phase = 0.0
        self._phase_direction = 1
        self._rotation = 0
        self.anim_timer.start()

    def stop(self):
        self.anim_timer.stop()
        self._morph_phase = 0.0

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            cx, cy = self.width() / 2, self.height() / 2
            radius = self.width() * 0.38

            painter.translate(cx, cy)
            painter.rotate(self._rotation)

            # Main color - high contrast orange
            main_color = QColor(251, 146, 60)  # Orange-400
            painter.setPen(QPen(main_color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Phase 0.0-0.5: + morphs to * (4 lines → 8 lines)
            # Phase 0.5-1.0: * morphs to ○ (8 lines → circle)

            if self._morph_phase < 0.5:
                # + to * transition
                # Start with 4 lines (cross), add diagonal lines
                t = self._morph_phase * 2  # 0 to 1 for this phase

                # Draw the main cross (always present)
                line_len = radius * 0.9

                # Vertical line
                painter.drawLine(QPointF(0, -line_len), QPointF(0, line_len))
                # Horizontal line
                painter.drawLine(QPointF(-line_len, 0), QPointF(line_len, 0))

                # Diagonal lines fade in
                if t > 0.1:
                    diag_len = line_len * min(1.0, (t - 0.1) / 0.6)
                    diag_alpha = min(1.0, (t - 0.1) / 0.4)
                    diag_color = QColor(251, 146, 60)
                    diag_color.setAlphaF(diag_alpha)
                    painter.setPen(QPen(diag_color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

                    # Diagonal lines at 45 degrees
                    d = diag_len * 0.707  # cos(45) = sin(45) = 0.707
                    painter.drawLine(QPointF(-d, -d), QPointF(d, d))
                    painter.drawLine(QPointF(-d, d), QPointF(d, -d))

            else:
                # * to ○ transition
                t = (self._morph_phase - 0.5) * 2  # 0 to 1 for this phase

                # Number of lines decreases as we approach circle
                # Line length shrinks, then becomes arc segments
                line_len = radius * 0.9 * (1 - t * 0.3)

                # Draw 8 lines that curve into a circle
                num_points = 8
                for i in range(num_points):
                    angle = i * (360 / num_points)
                    rad = math.radians(angle)

                    # Start point moves outward as we approach circle
                    inner_r = line_len * t * 0.7
                    outer_r = line_len

                    x1 = inner_r * math.cos(rad)
                    y1 = inner_r * math.sin(rad)
                    x2 = outer_r * math.cos(rad)
                    y2 = outer_r * math.sin(rad)

                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

                # Draw circle that fades in
                if t > 0.3:
                    circle_alpha = (t - 0.3) / 0.7
                    circle_color = QColor(251, 146, 60)
                    circle_color.setAlphaF(circle_alpha)
                    painter.setPen(QPen(circle_color, 2.0))
                    painter.drawEllipse(QPointF(0, 0), line_len * 0.85, line_len * 0.85)


class FlowingTextLabel(QWidget):
    """
    Custom label with flowing color animation through the text.
    A highlight sweeps from left to right continuously.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "Loading..."
        self._flow_position = 0.0  # 0.0 to 1.0, position of the highlight
        self._base_color = QColor(156, 163, 175)  # Gray-400
        self._highlight_color = QColor(251, 146, 60)  # Orange-400
        self._font = QFont()
        self._font.setPointSize(12)
        self._font.setWeight(QFont.Weight.Medium)

        # Flow animation timer
        self.flow_timer = QTimer(self)
        self.flow_timer.timeout.connect(self._update_flow)
        self.flow_timer.setInterval(30)  # ~33 FPS

        self.setMinimumHeight(24)
        self.setMinimumWidth(200)

        # Size policy to expand horizontally
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    @pyqtProperty(float)
    def flow_position(self):
        return self._flow_position

    @flow_position.setter
    def flow_position(self, value):
        self._flow_position = value
        self.update()

    def setText(self, text: str):
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def start(self):
        self._flow_position = 0.0
        self.flow_timer.start()

    def stop(self):
        self.flow_timer.stop()
        self._flow_position = 0.0

    def _update_flow(self):
        # Move the flow position
        self._flow_position += 0.02
        if self._flow_position > 1.5:  # Allow some overshoot for smooth loop
            self._flow_position = -0.3  # Start before visible area
        self.update()

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setFont(self._font)

            fm = QFontMetrics(self._font)
            text_width = max(fm.horizontalAdvance(self._text), 1)

            # Calculate vertical position to center text
            y = (self.height() + fm.ascent() - fm.descent()) / 2

            # Create gradient for the flowing effect
            gradient = QLinearGradient(0, 0, text_width, 0)

            # Simplified gradient: base color with a highlight band sweeping through
            highlight_pos = self._flow_position
            highlight_width = 0.2

            # Always set base color at start and end
            gradient.setColorAt(0.0, self._base_color)
            gradient.setColorAt(1.0, self._base_color)

            # Add highlight if it's in visible range
            if 0.0 < highlight_pos < 1.0:
                start = max(0.01, highlight_pos - highlight_width)
                end = min(0.99, highlight_pos + highlight_width)

                if start < end:
                    gradient.setColorAt(start, self._base_color)
                    gradient.setColorAt(highlight_pos, self._highlight_color)
                    gradient.setColorAt(end, self._base_color)

            # Draw text with gradient
            painter.setPen(QPen(QBrush(gradient), 1))
            painter.drawText(0, int(y), self._text)


class LoadingIndicator(QWidget):
    """
    Animated loading widget with:
    - Glowing star animation
    - Flowing color text animation
    - LLM mode: Static message (set once, doesn't rotate)
    - A2A mode: Dynamic messages from agent status updates
    """

    # Phrase sets for different entity types
    LLM_PHRASES = [
        "Neural networks firing...",
        "Deep thoughts brewing...",
        "Sprinkling AI magic...",
        "Consulting the oracle...",
        "Launching response rockets...",
        "Syncing with the matrix...",
        "Targeting the perfect answer...",
        "Gathering stardust...",
        "Cooking up something good...",
        "Idea bulb lighting up...",
        "Reading the entire internet...",
        "Painting with pixels...",
        "Composing the symphony...",
        "Juggling the data...",
        "Chasing rainbows...",
    ]

    A2A_PHRASES = [
        "Agent is on it...",
        "Connecting the dots...",
        "Gears are turning...",
        "Locking on target...",
        "High-fiving the agent...",
        "Full steam ahead...",
        "Piecing it together...",
        "Boosters engaged...",
        "Tinkering away...",
        "Performing magic tricks...",
        "Riding the data waves...",
        "Sprinting to the finish...",
        "Getting into character...",
        "Action! Rolling...",
        "Making this interesting...",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(50)
        self.current_phrases = self.LLM_PHRASES
        self.aborted = False
        self.custom_status_mode = False
        self.custom_status_text = None
        self.entity_type = "llm"

        # Main layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 5, 20, 5)
        self.layout.setSpacing(12)

        # Morphing Icon Animation (+ → * → ○)
        self.star = MorphingIcon(self, size=22)
        self.layout.addWidget(self.star)

        # Flowing text label (replaces static QLabel)
        self.message_label = FlowingTextLabel(self)
        self.layout.addWidget(self.message_label)

        self.layout.addStretch()

        # Initial hidden state
        self.hide()

    @pyqtSlot()
    @pyqtSlot(str)
    def start_animation(self, entity_type: str = "llm"):
        """
        Start the loading animation.

        Args:
            entity_type: Type of entity ("llm" or "agent")
        """
        self.aborted = False
        self.entity_type = entity_type
        self.custom_status_mode = False
        self.current_phrases = self.A2A_PHRASES if entity_type == "agent" else self.LLM_PHRASES

        # Set initial phrase (for LLM, this stays; for A2A, it can be updated)
        self._set_random_phrase()

        # Start animations
        self.star.start()
        self.message_label.start()

        # Show
        self.setHidden(False)
        self.show()

    @pyqtSlot()
    def stop_animation(self):
        """
        Stop the loading animation.
        """
        if self.aborted:
            return

        self.aborted = True
        self.star.stop()
        self.message_label.stop()

        # Clear custom status mode
        self.custom_status_mode = False
        self.custom_status_text = None

        self.hide()

    def _set_random_phrase(self):
        """Set a random phrase from the current list."""
        text = random.choice(self.current_phrases)
        self.message_label.setText(text)

    @pyqtSlot(str)
    def set_thinking_status(self, thinking_text: str):
        """
        Set the status message from thinking content.
        
        Args:
            thinking_text: The thinking content to display
        """
        # Truncate if too long (keeping the end is often more interesting for streaming)
        # But for thinking, the beginning/current thought is vital.
        # Let's show a fixed window or just the latest chunk if it was a stream? 
        # Actually, the thinking_text usually comes in chunks.
        # But typically set_custom_status replaces the whole text.
        # If we are receiving chunks, we should probably append them or show the latest "thought".
        # However, the providers are yielding <<<THINKING>>>chunk.
        # So here we are receiving a CHUNK. 
        # We should accumulate it?
        # NO, the providers yield <<<THINKING>>>content.
        # wait, local.py yields chunks: yield f"<<<THINKING>>>{content[current_pos:close_pos]}"
        # So we get partial text. 
        
        # We need to maintain a buffer if we want to show "full" thought, 
        # but the loading indicator is small. 
        # Better approach: Show the current chunk as a fleeting thought glimpse.
        # OR better: Accumulate locally in a buffer and show the last N chars.
        
        # Since this method is called frequently, let's keep it simple:
        # Just display the incoming chunk if it's substantial, 
        # or append to a small rolling buffer.
        
        # Actually, let's just format it nicely.
        # Users want to see "thinking...".
        # Note: The chunk might be small (tokens).
        
        # Let's clean the text
        clean_text = thinking_text.strip()
        if not clean_text:
            return

        # Format with a brain icon
        display_text = f"🧠 {clean_text}"
        
        # Update the text widget directly
        # We use a slightly different color or style for thinking
        if hasattr(self, 'status_label'):
             # If it's very long, truncate
             if len(display_text) > 80:
                 display_text = display_text[:77] + "..."
             
             self.status_label.setText(display_text)

    @pyqtSlot(str)
    def set_custom_status(self, status_text: str):
        """
        Set a custom status message from the agent.

        For A2A agents, this updates the displayed message with agent-provided status.
        This is the primary way A2A agents communicate their current state.

        Args:
            status_text: The status message to display
        """
        self.custom_status_mode = True
        self.custom_status_text = status_text
        self.message_label.setText(status_text)

        # Make sure we're visible and animating
        if not self.isVisible():
            self.star.start()
            self.message_label.start()
            self.show()

    @pyqtSlot()
    def clear_custom_status(self):
        """
        Clear the custom status and return to default phrase.
        """
        self.custom_status_mode = False
        self.custom_status_text = None

        # For A2A, pick a new random phrase; for LLM, keep current
        if self.entity_type == "agent" and not self.aborted:
            self._set_random_phrase()
