import os
import sys
import unittest
from pathlib import Path

# Set offscreen Qt platform for headless test runs
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_PLATFORMTHEME"] = "generic"

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication
from app.audio.ai_processor import LearningProcessor
from app.gui.waveform_widget import WaveformWidget
from app.gui.podcast_widget import PodcastWidget

app = QApplication.instance() or QApplication(["-platform", "offscreen"])

class TestNotebookLMFeatures(unittest.TestCase):
    def test_waveform_widget_states(self):
        import numpy as np
        w = WaveformWidget()
        self.assertFalse(w.is_recording)

        # Toggle recording
        w.set_recording_state(True)
        self.assertTrue(w.is_recording)

        # Update audio data with 2D stereo chunk
        chunk_2d = (np.random.randn(1024, 2) * 5000).astype(np.int16)
        w.update_audio_data(0.75, chunk_2d)
        self.assertEqual(w.level, 0.75)

        # Test paintEvent execution
        w.repaint()

        w.set_recording_state(False)
        self.assertFalse(w.is_recording)

    def test_podcast_widget_loading(self):
        pw = PodcastWidget()
        dialogue = [
            {"speaker": "Jordan", "text": "Welcome to our deep dive on this lecture!"},
            {"speaker": "Taylor", "text": "Thanks! Today we cover the central thesis."}
        ]
        pw.load_podcast(dialogue)
        self.assertEqual(len(pw.dialogue), 2)

    def test_processor_notebooklm_sample(self):
        processor = LearningProcessor(gemini_api_key="")
        sample = processor._generate_offline_sample("lecture.wav", "Quantum Physics")
        self.assertIn("deep_dive_podcast", sample)
        self.assertIn("study_notes", sample)
        self.assertIn("faq", sample)
        self.assertGreater(len(sample["deep_dive_podcast"]), 0)

if __name__ == "__main__":
    unittest.main()
