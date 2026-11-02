import tempfile
import wave
import unittest
from pathlib import Path
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.audio.player import AudioPlayer

class TestAudioPlayer(unittest.TestCase):
    def test_audio_player_load_and_seek(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            # Create a 1-second 16kHz sine/dummy wav
            sample_rate = 16000
            data = np.zeros(sample_rate, dtype=np.int16)
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(data.tobytes())

            player = AudioPlayer()
            loaded = player.load_file(temp_path)
            self.assertTrue(loaded)
            self.assertAlmostEqual(player.total_seconds, 1.0, places=1)

            # Test seek
            player.seek(0.5)
            self.assertEqual(player.current_frame, 8000)

            player.stop()
            self.assertEqual(player.current_frame, 0)
        finally:
            Path(temp_path).unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
