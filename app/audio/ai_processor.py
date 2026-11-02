import os
import sys
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

class LearningProcessor:
    """
    Multimodal AI Learning Engine replicating Google NotebookLM mechanisms:
    1. Grounded Multi-Source Learning (Live Audio, Videos, Documents, URLs)
    2. Deep Dive Podcast 'Audio Overview' (2-Host Conversational Dialogue)
    3. Watch-and-Summarize for Video Files & YouTube Lectures
    4. Full Study Guide Suite (Briefing, Flashcards, Quiz, Tasks, FAQ, Outline)
    5. Grounded Source Chat with Timestamps & Citations
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        ollama_endpoint: str = "http://localhost:11434"
    ):
        self.gemini_api_key = (gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.openai_api_key = (openai_api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        self.ollama_endpoint = ollama_endpoint.rstrip("/")

    def get_active_provider_status(self) -> Dict[str, Any]:
        """Returns the status and name of the active AI backend."""
        if self.gemini_api_key:
            return {"provider": "gemini", "name": "Google Gemini 2.5 Flash", "connected": True}
        elif self.openai_api_key:
            return {"provider": "openai", "name": "OpenAI GPT-4o", "connected": True}
        else:
            return {"provider": "offline", "name": "Offline / Free Template Mode", "connected": False}

    def process_audio_file(
        self,
        audio_path: str,
        topic_hint: str = "",
        custom_instructions: str = ""
    ) -> Dict[str, Any]:
        """Sends audio to Gemini for speech recognition and full NotebookLM study extraction."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not self.gemini_api_key and not self.openai_api_key:
            return self._generate_offline_sample(audio_path, topic_hint)

        if self.gemini_api_key:
            return self._process_audio_with_gemini(audio_path, topic_hint, custom_instructions)
        else:
            return self._process_audio_with_openai(audio_path, topic_hint)

    def _process_audio_with_gemini(
        self,
        audio_path: str,
        topic_hint: str = "",
        custom_instructions: str = ""
    ) -> Dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_api_key)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        ext = Path(audio_path).suffix.lower()
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mp3",
            ".m4a": "audio/m4a",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".webm": "audio/webm",
            ".mp4": "video/mp4"
        }
        mime_type = mime_map.get(ext, "audio/wav")

        prompt = f"""
        You are Google NotebookLM reimagined as an advanced AI educational study partner.
        Listen to and analyze this entire recording (Google Meet, class lecture, or meeting).
        {f'Session topic/title: {topic_hint}' if topic_hint else ''}
        {f'User guidance: {custom_instructions}' if custom_instructions else ''}

        Generate an exhaustive NotebookLM Study Package in valid JSON format with these exact keys:
        1. "title": Concise, informative title for the session.
        2. "summary": Executive Briefing (2-3 paragraphs synthesizing core concepts and takeaways).
        3. "study_notes": Comprehensive markdown study notes with hierarchical headers (##, ###), bullet points, definitions, formulas, and real-world examples.
        4. "deep_dive_podcast": An engaging two-host conversational podcast script ("Host A: Jordan" and "Host B: Taylor") in the iconic Google NotebookLM Audio Overview style. They explore the key points, banter naturally, ask insightful questions, and break down complex ideas with humor and clarity. Formatted as an array of objects: [{{"speaker": "Jordan", "text": "..."}}, {{"speaker": "Taylor", "text": "..."}}].
        5. "key_concepts": Array of objects: [{{"term": "Term", "definition": "Clear explanation"}}]
        6. "flashcards": Array of active-recall flashcard objects: [{{"question": "Prompt/Question", "answer": "Answer"}}] (At least 6-10 cards).
        7. "action_items": Array of follow-up tasks and homework: [{{"title": "Task description", "due": "Deadline or Next Class", "completed": false}}]
        8. "quiz": Array of multiple-choice quiz questions:
           [{{
             "question": "Question text",
             "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
             "correct_index": 0,
             "explanation": "Why this is correct"
           }}]
        9. "faq": Array of FAQ objects: [{{"question": "Common student question", "answer": "Clear explanation"}}]
        10. "transcript": Full or segmented verbatim transcript with timestamps (e.g. "[00:15] Speaker: ...").

        Output ONLY valid JSON.
        """

        media_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[media_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    def _process_audio_with_openai(self, audio_path: str, topic_hint: str) -> Dict[str, Any]:
        """Fallback processing via OpenAI Whisper API + GPT-4o."""
        # Step 1: Transcribe with Whisper API
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}
        with open(audio_path, "rb") as f:
            files = {"file": (Path(audio_path).name, f, "audio/wav")}
            data = {"model": "whisper-1"}
            res = httpx.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data=data, timeout=60.0)
            if res.status_code != 200:
                raise RuntimeError(f"OpenAI Whisper error: {res.text}")
            transcript = res.json().get("text", "")

        # Step 2: Structure with GPT-4o
        prompt = f"""
        Analyze this transcript as Google NotebookLM. Return valid JSON with keys:
        title, summary, study_notes, deep_dive_podcast, key_concepts, flashcards, action_items, quiz, faq, transcript.
        Transcript: {transcript}
        """
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        res2 = httpx.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60.0)
        return json.loads(res2.json()["choices"][0]["message"]["content"])

    def process_video_file(self, video_path: str, topic_hint: str = "") -> Dict[str, Any]:
        """
        'Watch then summarize' — processes video recordings (slides + spoken audio).
        """
        return self.process_audio_file(video_path, topic_hint, custom_instructions="Analyze both the visual slides shown and the spoken commentary.")

    def process_youtube_url(self, url: str, topic_hint: str = "") -> Dict[str, Any]:
        """Downloads audio from a YouTube or meeting URL using yt_dlp and analyzes it."""
        import yt_dlp
        import tempfile

        temp_dir = tempfile.mkdtemp()
        out_template = os.path.join(temp_dir, "yt_audio.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get("title", topic_hint or "YouTube Lecture")

        # Find extracted file
        files = list(Path(temp_dir).glob("yt_audio.*"))
        if not files:
            raise FileNotFoundError("Could not extract audio from video URL.")

        return self.process_audio_file(str(files[0]), topic_hint=video_title)

    def ask_grounded_tutor(self, context_sources: str, user_question: str) -> str:
        """
        Google NotebookLM Grounded Chat:
        Answers the learner's question strictly grounded in the notebook sources,
        citing timestamps or specific sections.
        """
        if not self.gemini_api_key:
            return "Please enter your Gemini API Key in Settings to chat with your notebook sources."

        from google import genai
        client = genai.Client(api_key=self.gemini_api_key)

        prompt = f"""
        You are Google NotebookLM's grounded research assistant.
        The user has loaded these sources (meeting transcripts, lecture notes, study guide):
        ---
        {context_sources}
        ---
        User Question: "{user_question}"

        Instructions:
        1. Answer directly and concisely based ONLY on the provided sources.
        2. Include citations in brackets, e.g. [Source: Meeting Recording] or [Section: Key Concepts].
        3. If the answer is not mentioned in the sources, politely clarify that it was not covered in the session.
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()

    def _generate_offline_sample(self, audio_path: str, topic_hint: str) -> Dict[str, Any]:
        filename = Path(audio_path).name
        return {
            "title": topic_hint if topic_hint else f"Meeting Recording ({filename})",
            "summary": (
                "Live sound was captured and saved locally! To enable full automatic AI transcription, "
                "flashcards, quizzes, and the NotebookLM Two-Host Deep Dive Podcast, paste your free Gemini "
                "API key in the top banner or Settings dialog."
            ),
            "study_notes": (
                f"# Study Notes: {topic_hint or filename}\n\n"
                "## 1. Overview\n"
                f"- Audio recording saved at: `{audio_path}`\n"
                "- Live Waveform confirmed speech capture.\n\n"
                "## 2. NotebookLM Capabilities\n"
                "- **Grounded Chat**: Chat with your lecture sources with citations.\n"
                "- **Two-Host Podcast**: AI hosts discuss your meeting like an engaging radio show.\n"
                "- **Active Recall**: Flip flashcards & interactive quizzes.\n"
            ),
            "deep_dive_podcast": [
                {"speaker": "Jordan", "text": "Welcome to our deep dive! Today we're looking at the session that was just recorded."},
                {"speaker": "Taylor", "text": "Right! And what's exciting is that you captured this live from Google Meet while talking with the team."},
                {"speaker": "Jordan", "text": "Exactly. Once you connect your Gemini API key, we will automatically break down every topic covered in full conversational detail!"}
            ],
            "key_concepts": [
                {"term": "Audio Loopback", "definition": "Capturing internal system audio from Google Meet without external microphones."},
                {"term": "Grounded AI", "definition": "AI responses constrained strictly to provided sources, eliminating hallucinations."}
            ],
            "flashcards": [
                {
                    "question": "How do you capture both your voice and meeting attendees?",
                    "answer": "Check the 'Mix in Mic' option to blend your microphone with the meeting audio loopback."
                },
                {
                    "question": "Where are your audio recordings stored?",
                    "answer": "In your OS data directory (~/.local/share/AVebiNaLearning/recordings on Linux)."
                }
            ],
            "action_items": [
                {"title": "Review recorded session key points", "due": "Today", "completed": False},
                {"title": "Configure Gemini API Key in settings", "due": "ASAP", "completed": False}
            ],
            "quiz": [
                {
                    "question": "Which visual indicator confirms sound is actively being recorded in real-time?",
                    "options": ["A) The animated dynamic sound wave bars", "B) Silent flatline", "C) Window title", "D) Cursor"],
                    "correct_index": 0,
                    "explanation": "The live waveform visualizer bounces in real-time to vocal speech frequencies."
                }
            ],
            "faq": [
                {"question": "Can I watch and summarize videos?", "answer": "Yes! You can import .mp4 video files or paste YouTube URLs."}
            ],
            "transcript": f"Audio file: {filename}. Connect Gemini API key for verbatim transcript."
        }
