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


class GlowingStar(QWidget):
    """
    Custom widget that draws a glowing, rotating star that morphs from a dot.
    """
    def __init__(self, parent=None, size=18):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._glow_intensity = 0.6
        self._rotation = 0
        self._morph_ratio = 0.0  # 0.0 = dot, 1.0 = star

        # Morph in (Dot -> Star)
        self.morph_in = QPropertyAnimation(self, b"morph_ratio")
        self.morph_in.setDuration(800)
        self.morph_in.setStartValue(0.0)
        self.morph_in.setEndValue(1.0)
        self.morph_in.setEasingCurve(QEasingCurve.Type.OutBack)

        # Pulse/Glow loop
        self.pulse_anim = QPropertyAnimation(self, b"glow_intensity")
        self.pulse_anim.setDuration(1000)
        self.pulse_anim.setStartValue(0.4)
        self.pulse_anim.setEndValue(1.0)
        self.pulse_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.pulse_anim.setLoopCount(-1)

        # Rotation animation
        self.rotate_timer = QTimer(self)
        self.rotate_timer.timeout.connect(self._update_rotation)
        self.rotate_timer.setInterval(20)  # ~50 FPS

    @pyqtProperty(float)
    def glow_intensity(self):
        return self._glow_intensity

    @glow_intensity.setter
    def glow_intensity(self, value):
        self._glow_intensity = value
        self.update()

    @pyqtProperty(float)
    def morph_ratio(self):
        return self._morph_ratio

    @morph_ratio.setter
    def morph_ratio(self, value):
        self._morph_ratio = value
        self.update()

    def _update_rotation(self):
        self._rotation = (self._rotation + 2) % 360
        self.update()

    def start(self):
        self._morph_ratio = 0.0
        self.morph_in.start()
        self.pulse_anim.start()
        self.rotate_timer.start()

    def stop(self):
        self.morph_in.stop()
        self.pulse_anim.stop()
        self.rotate_timer.stop()
        self._morph_ratio = 0.0

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            cx, cy = self.width() / 2, self.height() / 2
            radius = self.width() * 0.4

            # Move to center and rotate
            painter.translate(cx, cy)
            if self._morph_ratio > 0.1:
                painter.rotate(self._rotation * self._morph_ratio)

            # Draw glow
            gradient = QRadialGradient(0, 0, radius * 1.5)
            color = QColor(251, 146, 60)  # Orange-400
            color.setAlphaF(0.4 * self._glow_intensity)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(-radius * 1.5), int(-radius * 1.5), int(radius * 3), int(radius * 3))

            # Draw morphing shape (Dot -> Star)
            star_color = QColor(230, 81, 0)  # Dark Orange
            painter.setBrush(QBrush(star_color))
            painter.setPen(QPen(star_color, 1))

            # Interpolate inner radius
            inner_r_target = radius * 0.4
            current_inner_r = radius - (radius - inner_r_target) * self._morph_ratio

            star_poly = QPolygonF()
            for i in range(10):
                angle = i * 36
                r = radius if i % 2 == 0 else current_inner_r
                rad = math.radians(angle - 90)
                star_poly.append(QPointF(r * math.cos(rad), r * math.sin(rad)))

            painter.drawPolygon(star_poly)


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

        # Glowing Star Animation
        self.star = GlowingStar(self, size=20)
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
