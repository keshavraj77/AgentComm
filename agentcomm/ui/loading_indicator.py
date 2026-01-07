"""
Loading Indicator Widget for A2A Client
"""

import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, 
    QAbstractAnimation, QSequentialAnimationGroup, pyqtSlot
)
from PyQt6.QtGui import QColor, QPalette

class LoadingIndicator(QWidget):
    """
    Animated loading widget with fun rotating phrases
    """
    
    # Phrase sets for different entity types
    LLM_PHRASES = [
        ("🧠", "Neural networks firing..."),
        ("💭", "Deep thoughts brewing..."),
        ("✨", "Sprinkling AI magic..."),
        ("🔮", "Consulting the oracle..."),
        ("🚀", "Launching response rockets..."),
        ("⚡", "Syncing with the matrix..."),
        ("🎯", "Targeting the perfect answer..."),
        ("🌟", "Gathering stardust..."),
        ("🔥", "Cooking up something good..."),
        ("💡", "Idea bulb lighting up..."),
        ("📚", "Reading the entire internet..."),
        ("🎨", "Painting with pixels..."),
        ("🎹", "Composing the symphony..."),
        ("🎪", "Juggling the data..."),
        ("🌈", "Chasing rainbows..."),
    ]
    
    A2A_PHRASES = [
        ("🤖", "Agent is on it..."),
        ("🔗", "Connecting the dots..."),
        ("⚙️", "Gears are turning..."),
        ("🎯", "Locking on target..."),
        ("🤝", "High-fiving the agent..."),
        ("🚂", "Full steam ahead..."),
        ("🧩", "Piecing it together..."),
        ("🚀", "Boosters engaged..."),
        ("🔧", "Tinkering away..."),
        ("🎪", "Performing magic tricks..."),
        ("🌊", "Riding the data waves..."),
        ("🏃", "Sprinting to the finish..."),
        ("🎭", "Getting into character..."),
        ("🎬", "Action! Rolling..."),
        ("🍿", "Making this interesting..."),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setFixedHeight(60)
        self.current_phrases = self.LLM_PHRASES
        self.aborted = False
        
        # Main layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 5, 20, 5)
        self.layout.setSpacing(15)
        
        # Icon label
        self.icon_label = QLabel("🧠")
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                background: transparent;
            }
        """)
        self.layout.addWidget(self.icon_label)
        
        # Text container for vertical stacking of message + dots
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Message label
        self.message_label = QLabel("Thinking...")
        self.message_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #e5e7eb;
                font-weight: 500;
                background: transparent;
            }
        """)
        text_layout.addWidget(self.message_label)
        
        # Dots label
        self.dots_label = QLabel("...")
        self.dots_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                color: #3b82f6;
                font-weight: bold;
                background: transparent;
                margin-top: -5px;
            }
        """)
        text_layout.addWidget(self.dots_label)
        
        self.layout.addWidget(text_container)
        self.layout.addStretch()
        
        # Setup opacity effect for fade transitions
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.message_label.setGraphicsEffect(self.opacity_effect)
        
        # Phrase rotation timer
        self.phrase_timer = QTimer(self)
        self.phrase_timer.timeout.connect(self._rotate_phrase)
        self.phrase_timer.setInterval(1500)  # Rotate every 1.5s
        
        # Dots animation timer
        self.dots_timer = QTimer(self)
        self.dots_timer.timeout.connect(self._animate_dots)
        self.dots_timer.setInterval(400)  # Update dots every 400ms
        self.dot_count = 0
        
        # Fade animation
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(500)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Initial hidden state
        self.hide()
        
    @pyqtSlot()
    @pyqtSlot(str)
    def start_animation(self, entity_type: str = "llm"):
        """
        Start the loading animation
        
        Args:
            entity_type: Type of entity ("llm" or "agent")
        """
        self.aborted = False
        self.current_phrases = self.A2A_PHRASES if entity_type == "agent" else self.LLM_PHRASES
        
        # Set initial phrase
        self._set_random_phrase()
        
        # Start timers
        self.phrase_timer.start()
        self.dots_timer.start()
        
        # Show with fade in
        self.setHidden(False)
        self.opacity_effect.setOpacity(1.0)  # Start fully visible for immediate feedback
        self.show()
        
    @pyqtSlot()
    def stop_animation(self):
        """
        Stop the loading animation
        """
        if self.aborted:
            return  # Already stopped
            
        self.aborted = True
        self.phrase_timer.stop()
        self.dots_timer.stop()
        
        # Just hide immediately for cleaner transition
        self.hide()
        
    def _set_random_phrase(self):
        """Set a random phrase from the current list"""
        icon, text = random.choice(self.current_phrases)
        self.icon_label.setText(icon)
        self.message_label.setText(text)
        
    def _rotate_phrase(self):
        """Rotate to a new random phrase with fade transition"""
        if self.aborted:
            return
            
        # Fade out
        fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out.setDuration(300)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        
        def on_fade_out_finished():
            if self.aborted:
                return
            self._set_random_phrase()
            # Fade in
            fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
            fade_in.setDuration(300)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.start()
            # Keep reference to avoid garbage collection
            self._fade_in_anim = fade_in
            
        fade_out.finished.connect(on_fade_out_finished)
        fade_out.start()
        # Keep reference
        self._fade_out_anim = fade_out
        
    def _animate_dots(self):
        """Animate the dots ... -> . -> .. -> ..."""
        self.dot_count = (self.dot_count + 1) % 4
        # Use spaces to keep width constant-ish
        text = "." * (self.dot_count if self.dot_count > 0 else 1)
        self.dots_label.setText(text)
