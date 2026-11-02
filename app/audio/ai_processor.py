import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx

PRIMARY_GEMINI_MODEL = "gemini-1.5-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.0-flash"

def sanitize_api_key(raw_key: str) -> str:
    """
    Cleans and isolates valid API keys.
    Strips non-ASCII characters, symbols, quotes, and whitespace.
    Automatically extracts the clean AIzaSy... or sk-... key even if
    the user accidentally pasted surrounding terminal text or Google AI Studio icons.
    """
    if not raw_key:
        return ""
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
    Notion AI Meeting & Google NotebookLM Study Engine:
    1. Notion AI Meeting Notes (TL;DR, Decisions, Action Items Table, Discussion Topics by Speaker)
    2. Speaker Diarization (Detects Client vs You vs Presenter)
    3. Live Audio & Video Watch-and-Summarize
    4. NotebookLM Deep Dive Podcast 'Audio Overview' (2-Host Conversational Dialogue)
    5. Study Guide Suite (Active Recall Flashcards, Quizzes, FAQ)
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
        """Validates a Gemini API key with official gemini-1.5-flash model."""
        clean_key = sanitize_api_key(api_key)
        if not clean_key:
            return False, "API key cannot be empty. Please paste your key from aistudio.google.com"
        if not clean_key.startswith("AIza"):
            return False, "Invalid format: Google Gemini keys start with 'AIzaSy' and are 39 characters long."

        try:
            from google import genai
            client = genai.Client(api_key=clean_key)
            # Lightweight verification ping using official standard model
            try:
                response = client.models.generate_content(
                    model=PRIMARY_GEMINI_MODEL,
                    contents="Hi"
                )
            except Exception:
                # Try fallback model
                response = client.models.generate_content(
                    model=FALLBACK_GEMINI_MODEL,
                    contents="Hi"
                )

            if response and response.text:
                return True, f"Connected successfully to Google Gemini AI ({PRIMARY_GEMINI_MODEL})!"
            return False, "Connected but received empty response."
        except Exception as e:
            err = str(e)
            if "API_KEY_INVALID" in err or "400" in err or "INVALID_ARGUMENT" in err:
                return False, "Invalid API key: Google rejected this key. Please check your key at aistudio.google.com"
            if "PERMISSION_DENIED" in err or "403" in err:
                return False, "Permission denied: Ensure the Gemini API is enabled for this key."
            return False, f"Connection test failed: {err}"

    def get_active_provider_status(self) -> Dict[str, Any]:
        """Returns the status and name of the active AI backend."""
        if self.gemini_api_key and self.gemini_api_key.startswith("AIza"):
            return {"provider": "gemini", "name": f"Google Gemini ({PRIMARY_GEMINI_MODEL})", "connected": True}
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
        """Processes audio with Notion AI Meeting synthesis and speaker detection."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

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
        You are Notion AI Meeting Assistant and Google NotebookLM combined into one premier AI workspace.
        Analyze this recorded session (Google Meet, class lecture, or client call).
        {f'Session topic/title: {topic_hint}' if topic_hint else ''}
        {f'User guidance: {custom_instructions}' if custom_instructions else ''}

        MANDATORY NOTION AI & SPEAKER DETECTION SPECIFICATIONS:
        1. Auto-detect each speaker (Speaker Diarization): Clearly identify distinct voices (e.g. "Client / Speaker 1", "You / Presenter", "Professor", "Attendee").
        2. Format a full 'Notion AI Meeting Notes' document:
           - 🎯 TL;DR Executive Summary (high impact takeaways)
           - 📌 Key Decisions Made
           - ⚡ Action Items & Next Steps Table with columns: Task, Owner, Deadline, Priority (High/Medium/Low)
           - 💬 Discussion by Agenda Topic with speaker statements
           - ❓ Questions Asked & Answers Given (Q&A Log)

        Generate a complete JSON package with these exact keys:
        1. "title": Professional, informative title.
        2. "summary": Executive TL;DR summary (2-3 paragraphs).
        3. "notion_meeting_notes": Full Notion-styled markdown document with callouts (> 💡), checklists (- [ ]), tables, and headers.
        4. "client_minutes": A formal client-ready brief with executive summary, requirements, decisions, and deliverables.
        5. "study_notes": Comprehensive markdown study notes with definitions, formulas, and examples.
        6. "deep_dive_podcast": Two-host conversational podcast script ("Jordan" and "Taylor") in NotebookLM style. Formatted as: [{{"speaker": "Jordan", "text": "..."}}, {{"speaker": "Taylor", "text": "..."}}].
        7. "key_concepts": Array of objects: [{{"term": "Term", "definition": "Clear explanation"}}]
        8. "flashcards": Array of active-recall flashcard objects: [{{"question": "Question", "answer": "Answer"}}] (6-10 cards).
        9. "action_items": Array of objects: [{{"title": "Task description", "due": "Deadline or Next Class", "completed": false}}]
        10. "quiz": Array of objects:
           [{{
             "question": "Question text",
             "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
             "correct_index": 0,
             "explanation": "Why this is correct"
           }}]
        11. "faq": Array of objects: [{{"question": "Question", "answer": "Answer"}}]
        12. "transcript": Diarized transcript with speaker labels and timestamps (e.g. "[00:04] Client: ...\\n[00:18] You: ...").

        Output ONLY valid JSON.
        """

        media_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        # Primary attempt with gemini-1.5-flash, fallback to gemini-2.0-flash
        try:
            response = client.models.generate_content(
                model=PRIMARY_GEMINI_MODEL,
                contents=[media_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        except Exception:
            response = client.models.generate_content(
                model=FALLBACK_GEMINI_MODEL,
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
        Analyze this transcript as Notion AI Meeting Assistant. Return valid JSON with keys:
        title, summary, notion_meeting_notes, client_minutes, study_notes, deep_dive_podcast, key_concepts, flashcards, action_items, quiz, faq, transcript.
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
        """Processes video recordings (slides + spoken audio)."""
        return self.process_audio_file(video_path, topic_hint, custom_instructions="Analyze visual slides and commentary as Notion AI meeting notes.")

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
        """Grounded Q&A with citations."""
        clean_key = sanitize_api_key(self.gemini_api_key)
        if not clean_key:
            return "Please enter your Gemini API Key in Settings to chat with your notebook sources."

        from google import genai
        client = genai.Client(api_key=clean_key)

        prompt = f"""
        You are Notion AI & Google NotebookLM grounded research assistant.
        Sources:
        ---
        {context_sources}
        ---
        User Question: "{user_question}"

        Instructions:
        1. Answer directly based on the sources.
        2. Include citations in brackets, e.g. [Source: Meeting Recording, Speaker 1].
        """

        try:
            response = client.models.generate_content(
                model=PRIMARY_GEMINI_MODEL,
                contents=prompt
            )
        except Exception:
            response = client.models.generate_content(
                model=FALLBACK_GEMINI_MODEL,
                contents=prompt
            )

        return response.text.strip()

    def _generate_offline_sample(self, audio_path: str, topic_hint: str) -> Dict[str, Any]:
        filename = Path(audio_path).name
        return {
            "title": topic_hint if topic_hint else f"Meeting Recording ({filename})",
            "summary": (
                "Live audio was captured and saved locally! To enable full automatic AI transcription, "
                "Notion AI meeting notes, flashcards, and speaker diarization, enter your Gemini API key "
                "in the top banner or Settings dialog."
            ),
            "notion_meeting_notes": (
                f"# 📝 Notion AI Meeting Notes: {topic_hint or filename}\n\n"
                "> 💡 **TL;DR Summary**: Audio recording captured and saved locally.\n\n"
                "## 📌 Key Decisions Made\n"
                "- [x] Integrated real-time dynamic sound wave visualizer.\n"
                "- [x] Automated Notion AI meeting notes formatting with live copy.\n\n"
                "## ⚡ Action Items & Next Steps\n"
                "| Task | Owner | Deadline | Priority |\n"
                "|---|---|---|---|\n"
                "| Configure Gemini API Key | User | Today | 🔴 High |\n"
                "| Start Live Class Session | User | Immediate | 🟡 Medium |\n\n"
                "## 💬 Discussion Topics by Speaker\n"
                "### Topic 1: Live Audio Recording\n"
                "- **You / Presenter**: Testing audio input and loopback capture.\n"
                "- **Client / Attendees**: Feedback on clarity and volume.\n\n"
                "## ❓ Questions & Answers\n"
                "- **Q**: How do I export to Notion?\n"
                "  - **A**: Click the '📋 Copy as Notion Blocks' button and paste directly into Notion!\n"
            ),
            "client_minutes": (
                f"# Client Meeting Minutes: {topic_hint or filename}\n\n"
                "## 1. Meeting Overview\n"
                f"- **Audio File**: `{audio_path}`\n\n"
                "## 2. Deliverables Table\n"
                "| Item | Owner | Deadline |\n"
                "|---|---|---|\n"
                "| Add Gemini API Key | User | Today |\n"
            ),
            "study_notes": (
                f"# Study Notes: {topic_hint or filename}\n\n"
                "## 1. Overview\n"
                f"- Audio recording saved at: `{audio_path}`\n"
            ),
            "deep_dive_podcast": [
                {"speaker": "Jordan", "text": "Welcome to our deep dive! Today we're looking at the session that was just recorded."},
                {"speaker": "Taylor", "text": "Right! Connect your Gemini API key to generate a full conversational podcast breakdown!"}
            ],
            "key_concepts": [
                {"term": "Notion AI Meeting Notes", "definition": "Structured meeting notes with TL;DR summaries, decision logs, and action item tables formatted natively for Notion."},
                {"term": "Speaker Diarization", "definition": "Automatic detection of who spoke when."}
            ],
            "flashcards": [
                {
                    "question": "How do you copy notes directly into Notion?",
                    "answer": "Click 'Copy as Notion Blocks' in the Notion AI Meeting Notes tab and press Ctrl+V inside Notion."
                }
            ],
            "action_items": [
                {"title": "Enter valid Gemini API Key starting with AIzaSy...", "due": "Today", "completed": False}
            ],
            "quiz": [
                {
                    "question": "What is the key benefit of Notion AI meeting notes?",
                    "options": [
                        "A) Instant executive TL;DR, decision tracking, and action items table",
                        "B) Lowers the monitor resolution",
                        "C) Erases your notes",
                        "D) Closes your browser"
                    ],
                    "correct_index": 0,
                    "explanation": "Notion AI structures discussions into clean, actionable blocks that paste natively into Notion."
                }
            ],
            "faq": [
                {"question": "How do I get a free Gemini API key?", "answer": "Visit https://aistudio.google.com and click 'Get API Key'. It is free and takes 30 seconds."}
            ],
            "transcript": f"Audio file: {filename}. Connect Gemini API key for speaker-labeled transcript."
        }
