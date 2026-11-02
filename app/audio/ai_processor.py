import os
import sys
import re
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx

def sanitize_api_key(raw_key: str) -> str:
    """
    Cleans and extracts valid API keys.
    Strips non-ASCII characters, symbols, quotes, and whitespace.
    If the user accidentally pasted surrounding terminal text or Google AI Studio icons,
    it automatically isolates the exact AIzaSy... or sk-... key.
    """
    if not raw_key:
        return ""
    # Remove all non-ASCII characters (e.g. \u2726, emojis, bullets)
    cleaned = re.sub(r'[^\x20-\x7E]', '', str(raw_key)).strip()
    
    # Try finding Google Gemini key pattern (starts with AIzaSy... 39 chars)
    gemini_match = re.search(r'AIzaSy[A-Za-z0-9_\-]{33}', cleaned)
    if gemini_match:
        return gemini_match.group(0)

    # General AIza pattern
    aiza_match = re.search(r'AIza[A-Za-z0-9_\-]{20,}', cleaned)
    if aiza_match:
        return aiza_match.group(0)

    # OpenAI pattern
    openai_match = re.search(r'sk-[A-Za-z0-9_\-]{20,}', cleaned)
    if openai_match:
        return openai_match.group(0)

    return cleaned.strip().strip('"\'')

class LearningProcessor:
    """
    Multimodal AI Learning & Meeting Engine:
    1. Automatic Speaker Diarization (Detects Client vs You vs Presenter)
    2. Client-Ready Executive Meeting Minutes & Deliverables Table
    3. Grounded Multi-Source Learning (Live Audio, Videos, Documents, URLs)
    4. Deep Dive Podcast 'Audio Overview' (2-Host Conversational Dialogue)
    5. Watch-and-Summarize for Video Files & YouTube Lectures
    6. Full Study Guide Suite (Briefing, Flashcards, Quiz, Tasks, FAQ, Outline)
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        ollama_endpoint: str = "http://localhost:11434"
    ):
        self.gemini_api_key = sanitize_api_key(gemini_api_key or os.environ.get("GEMINI_API_KEY", ""))
        self.openai_api_key = sanitize_api_key(openai_api_key or os.environ.get("OPENAI_API_KEY", ""))
        self.ollama_endpoint = ollama_endpoint.rstrip("/")

    @staticmethod
    def validate_gemini_key(api_key: str) -> Tuple[bool, str]:
        """Validates a Gemini API key by performing a lightweight ping test."""
        clean_key = sanitize_api_key(api_key)
        if not clean_key:
            return False, "API key cannot be empty."
        if not clean_key.startswith("AIza"):
            return False, "Invalid format: Google Gemini API keys start with 'AIzaSy' and are 39 characters."

        try:
            from google import genai
            client = genai.Client(api_key=clean_key)
            # Lightweight verification
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Respond with 'OK'."
            )
            if response and response.text:
                return True, "Connected successfully to Google Gemini 2.5 Flash!"
            return False, "Connected but received empty response."
        except Exception as e:
            err = str(e)
            if "API_KEY_INVALID" in err or "400" in err:
                return False, "Invalid API key: Rejected by Google. Please check your key at aistudio.google.com"
            return False, f"Connection test failed: {err}"

    def get_active_provider_status(self) -> Dict[str, Any]:
        """Returns the status and name of the active AI backend."""
        if self.gemini_api_key and self.gemini_api_key.startswith("AIza"):
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
        """Processes audio with automatic speaker detection and client-ready minutes."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Sanitize keys before making request
        clean_gemini = sanitize_api_key(self.gemini_api_key)
        clean_openai = sanitize_api_key(self.openai_api_key)

        if not clean_gemini and not clean_openai:
            return self._generate_offline_sample(audio_path, topic_hint)

        if clean_gemini:
            return self._process_audio_with_gemini(audio_path, topic_hint, custom_instructions, clean_gemini)
        else:
            return self._process_audio_with_openai(audio_path, topic_hint, clean_openai)

    def _process_audio_with_gemini(
        self,
        audio_path: str,
        topic_hint: str,
        custom_instructions: str,
        api_key: str
    ) -> Dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

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
        You are an elite Executive Meeting Assistant and Learning Specialist (replicating Google NotebookLM).
        Analyze this recorded meeting or lecture with deep precision.
        {f'Session topic/title: {topic_hint}' if topic_hint else ''}
        {f'User focus: {custom_instructions}' if custom_instructions else ''}

        CRITICAL SPEAKER DETECTION & CLIENT-READY INSTRUCTIONS:
        1. Auto-detect each speaker (Speaker Diarization): Identify distinct voices (e.g. "Client / Speaker 1", "You / Consultant", "Professor", "Presenter").
        2. Write a professional, client-ready Executive Meeting Minutes document that could be sent directly to a client or executive.

        Generate an exhaustive JSON package with these exact keys:
        1. "title": Professional title for this session.
        2. "summary": Executive Summary (2-3 paragraphs synthesizing core discussion, objectives, and conclusions).
        3. "client_minutes": A formal client-ready brief formatted in Markdown:
           - ## Meeting Overview & Purpose
           - ## Client Requirements & Discussion Points
           - ## Agreed Decisions & Approvals
           - ## Deliverables & Commitments Table (| Deliverable | Owner | Deadline |)
        4. "study_notes": Comprehensive markdown study notes with headers, bullet points, definitions, formulas, and examples.
        5. "deep_dive_podcast": An engaging two-host conversational podcast script ("Jordan" and "Taylor") in the iconic Google NotebookLM Audio Overview style. Formatted as an array of objects: [{{"speaker": "Jordan", "text": "..."}}, {{"speaker": "Taylor", "text": "..."}}].
        6. "key_concepts": Array of objects: [{{"term": "Term", "definition": "Clear explanation"}}]
        7. "flashcards": Array of active-recall flashcard objects: [{{"question": "Prompt/Question", "answer": "Answer"}}] (At least 6-10 cards).
        8. "action_items": Array of follow-up tasks and homework: [{{"title": "Task description", "due": "Deadline or Next Class", "completed": false}}]
        9. "quiz": Array of multiple-choice quiz questions:
           [{{
             "question": "Question text",
             "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
             "correct_index": 0,
             "explanation": "Why this is correct"
           }}]
        10. "faq": Array of FAQ objects: [{{"question": "Question", "answer": "Explanation"}}]
        11. "transcript": Diarized transcript with speaker labels and timestamps (e.g. "[00:04] Client: ...\\n[00:18] You: ...").

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

    def _process_audio_with_openai(self, audio_path: str, topic_hint: str, api_key: str) -> Dict[str, Any]:
        """Fallback processing via OpenAI Whisper API + GPT-4o."""
        headers = {"Authorization": f"Bearer {api_key}"}
        with open(audio_path, "rb") as f:
            files = {"file": (Path(audio_path).name, f, "audio/wav")}
            data = {"model": "whisper-1"}
            res = httpx.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data=data, timeout=60.0)
            if res.status_code != 200:
                raise RuntimeError(f"OpenAI Whisper error: {res.text}")
            transcript = res.json().get("text", "")

        prompt = f"""
        Analyze this transcript as an Executive Assistant & Google NotebookLM. Return valid JSON with keys:
        title, summary, client_minutes, study_notes, deep_dive_podcast, key_concepts, flashcards, action_items, quiz, faq, transcript.
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
        """'Watch then summarize' — processes video recordings (slides + spoken audio)."""
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

        files = list(Path(temp_dir).glob("yt_audio.*"))
        if not files:
            raise FileNotFoundError("Could not extract audio from video URL.")

        return self.process_audio_file(str(files[0]), topic_hint=video_title)

    def ask_grounded_tutor(self, context_sources: str, user_question: str) -> str:
        """Google NotebookLM Grounded Chat with citations."""
        clean_key = sanitize_api_key(self.gemini_api_key)
        if not clean_key:
            return "Please enter your Gemini API Key in Settings to chat with your notebook sources."

        from google import genai
        client = genai.Client(api_key=clean_key)

        prompt = f"""
        You are Google NotebookLM's grounded research assistant.
        The user has loaded these sources:
        ---
        {context_sources}
        ---
        User Question: "{user_question}"

        Instructions:
        1. Answer directly and concisely based ONLY on the provided sources.
        2. Include citations in brackets, e.g. [Source: Meeting Recording, Speaker 1] or [Section: Key Concepts].
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
                "flashcards, quizzes, speaker detection, and client-ready meeting minutes, paste your free Gemini "
                "API key in the top banner or Settings dialog."
            ),
            "client_minutes": (
                f"# Client Meeting Minutes: {topic_hint or filename}\n\n"
                "## 1. Meeting Overview\n"
                "- **Status**: Audio captured and stored locally.\n"
                f"- **Audio File**: `{audio_path}`\n\n"
                "## 2. Speaker Diarization Notice\n"
                "Connect your free Google Gemini API key to automatically identify multiple speakers (Client vs You) "
                "and generate formatted client-ready meeting minutes.\n\n"
                "## 3. Next Steps\n"
                "| Item | Owner | Deadline |\n"
                "|---|---|---|\n"
                "| Configure Gemini API Key | User | Today |\n"
                "| Reprocess Audio | System | Immediate |\n"
            ),
            "study_notes": (
                f"# Study Notes: {topic_hint or filename}\n\n"
                "## 1. Overview\n"
                f"- Audio recording saved at: `{audio_path}`\n"
                "- Live Waveform confirmed speech capture.\n\n"
                "## 2. NotebookLM Capabilities\n"
                "- **Speaker Diarization**: Detects Client vs You vs Presenter.\n"
                "- **Grounded Chat**: Chat with your lecture sources with citations.\n"
                "- **Two-Host Podcast**: AI hosts discuss your meeting like an engaging radio show.\n"
            ),
            "deep_dive_podcast": [
                {"speaker": "Jordan", "text": "Welcome to our deep dive! Today we're looking at the session that was just recorded."},
                {"speaker": "Taylor", "text": "Right! And what's exciting is that you captured this live from Google Meet while talking with the team."},
                {"speaker": "Jordan", "text": "Exactly. Once you connect your Gemini API key, we will automatically break down every topic covered in full conversational detail!"}
            ],
            "key_concepts": [
                {"term": "Speaker Diarization", "definition": "The process of partitioning an audio stream into homogeneous segments according to each speaker's identity."},
                {"term": "Client-Ready Minutes", "definition": "A formal, structured meeting document summarizing decisions, requirements, and next steps for business stakeholders."}
            ],
            "flashcards": [
                {
                    "question": "What is Speaker Diarization?",
                    "answer": "Automatically detecting and distinguishing different speakers (e.g. Client vs You) in an audio recording."
                },
                {
                    "question": "Where are your audio recordings stored?",
                    "answer": "In your OS data directory (~/.local/share/AVebiNaLearning/recordings on Linux)."
                }
            ],
            "action_items": [
                {"title": "Enter valid Gemini API Key starting with AIzaSy...", "due": "Today", "completed": False},
                {"title": "Review client meeting deliverables", "due": "ASAP", "completed": False}
            ],
            "quiz": [
                {
                    "question": "What does speaker diarization do in client meeting notes?",
                    "options": [
                        "A) Automatically labels who said what (Client, You, Presenter)",
                        "B) Deletes the recording",
                        "C) Translates to binary",
                        "D) Lowers the volume"
                    ],
                    "correct_index": 0,
                    "explanation": "Diarization identifies distinct voices so each statement is attributed to the correct speaker."
                }
            ],
            "faq": [
                {"question": "How do I get a free Gemini API key?", "answer": "Visit https://aistudio.google.com and click 'Get API Key'. It takes 30 seconds and is free."}
            ],
            "transcript": f"Audio file: {filename}. Connect Gemini API key for speaker-labeled transcript."
        }
