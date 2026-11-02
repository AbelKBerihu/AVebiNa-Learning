import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.audio.recorder import AudioRecorder
from app.audio.ai_processor import LearningProcessor

class TestLearningFeatures(unittest.TestCase):
    def test_audio_device_enumeration(self):
        devices = AudioRecorder.get_audio_devices()
        self.assertIsInstance(devices, list)
        # Even in headless/virtualized environments, query_devices returns a list
        if devices:
            first = devices[0]
            self.assertIn("name", first)
            self.assertIn("category", first)
            self.assertIn("display_name", first)

    def test_learning_processor_offline_fallback(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"RIFFdummywavdata")
            temp_path = f.name

        try:
            processor = LearningProcessor(gemini_api_key="")
            result = processor.process_audio_file(temp_path, topic_hint="Biology 101")
            self.assertIn("title", result)
            self.assertIn("summary", result)
            self.assertIn("study_notes", result)
            self.assertIn("flashcards", result)
            self.assertIn("quiz", result)
            self.assertIn("action_items", result)
            self.assertIn("transcript", result)

            self.assertGreater(len(result["flashcards"]), 0)
            self.assertGreater(len(result["quiz"]), 0)
            self.assertGreater(len(result["action_items"]), 0)

            # Check flashcard structure
            fc = result["flashcards"][0]
            self.assertIn("question", fc)
            self.assertIn("answer", fc)

            # Check quiz structure
            q = result["quiz"][0]
            self.assertIn("question", q)
            self.assertIn("options", q)
            self.assertIn("correct_index", q)
            self.assertIn("explanation", q)
        finally:
            Path(temp_path).unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
