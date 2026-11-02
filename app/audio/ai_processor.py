import os
import sys
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

class LearningProcessor:
    """
    Processes recorded audio or transcripts into comprehensive learning materials:
    - Verbatim Transcript
    - Executive Summary
    - Detailed Study Notes (Markdown)
    - Key Concepts & Definitions
    - Active Recall Flashcards (Q&A)
    - Action Items & Homework / To-Dos
    - Knowledge Check Quizzes
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")

    def process_audio_file(
        self,
        audio_path: str,
        topic_hint: str = "",
        custom_instructions: str = ""
    ) -> Dict[str, Any]:
        """
        Sends audio to Gemini for speech recognition and learning material extraction.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        api_key = self.gemini_api_key.strip()
        if not api_key:
            # Fallback to local offline template if no key provided
            return self._generate_offline_sample(audio_path, topic_hint)

        # Use google-genai
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Determine MIME type
        ext = path.suffix.lower()
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mp3",
            ".m4a": "audio/m4a",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".webm": "audio/webm"
        }
        mime_type = mime_map.get(ext, "audio/wav")

        prompt = f"""
        You are an elite educational AI and learning assistant.
        Listen carefully to this entire audio recording (which could be a Google Meet session, lecture, seminar, discussion, or voice note).
        {f'Context / Topic hint: {topic_hint}' if topic_hint else ''}
        {f'User focus instruction: {custom_instructions}' if custom_instructions else ''}

        Produce an exhaustive, structured learning package in valid JSON format with the following keys:
        1. "title": A clear, informative title for the session/lecture.
        2. "summary": A concise high-level executive summary (2-3 paragraphs) capturing the main thesis and takeaways.
        3. "study_notes": Comprehensive markdown notes organized logically with headers, bullet points, key equations or rules, definitions, and examples.
        4. "key_concepts": An array of objects: [{{"term": "Term Name", "definition": "Clear explanation"}}]
        5. "flashcards": An array of active recall flashcards: [{{"question": "Prompt/Question", "answer": "Answer"}}] (At least 4-8 cards).
        6. "action_items": An array of tasks or follow-ups mentioned in the meeting: [{{"title": "Task description", "due": "Deadline or ASAP", "completed": false}}]
        7. "quiz": An array of multiple-choice quiz questions to test understanding:
           [{{
             "question": "Question text",
             "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
             "correct_index": 0,
             "explanation": "Why this is correct"
           }}]
        8. "transcript": The full or key transcript with approximate timestamps or speaker labels.

        Output ONLY valid JSON.
        """

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        # Using gemini-2.5-flash for high speed, audio capability, and structured JSON
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[audio_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        response_text = response.text.strip()
        # Clean any accidental markdown code fences
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        data = json.loads(response_text)
        return data

    def ask_ai_tutor(self, context_notes: str, user_question: str) -> str:
        """
        Interactive Q&A: Allows the learner to ask follow-up questions about the recorded material.
        """
        api_key = self.gemini_api_key.strip()
        if not api_key:
            return "Please configure your Gemini API Key in Settings to ask questions to the AI tutor."

        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""
        You are a supportive, knowledgeable AI tutor.
        The student is studying this meeting / lecture material:
        ---
        {context_notes}
        ---
        The student asks: "{user_question}"
        Provide a clear, engaging, step-by-step educational answer using examples if helpful.
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()

    def _generate_offline_sample(self, audio_path: str, topic_hint: str) -> Dict[str, Any]:
        """Provides a helpful structured template when running offline or without an API key."""
        filename = Path(audio_path).name
        return {
            "title": topic_hint if topic_hint else f"Session Recording ({filename})",
            "summary": (
                "Audio recording captured successfully! To enable full automatic AI transcription, "
                "flashcard generation, and lecture summarization, add your free Gemini API key in the "
                "Settings menu (⚙) or set the GEMINI_API_KEY environment variable."
            ),
            "study_notes": (
                f"# Study Notes: {topic_hint or filename}\n\n"
                "## 1. Overview\n"
                "- Audio file was recorded and saved locally.\n"
                "- File path: `" + audio_path + "`\n\n"
                "## 2. Key Takeaways\n"
                "- Capture Google Meet, Zoom, or microphone audio directly.\n"
                "- Automatic sync with CrossSync lets you review notes on both Windows and Linux.\n\n"
                "## 3. How to Enable AI Transcription\n"
                "1. Click **⚙ Settings**\n"
                "2. Paste your Google Gemini API key\n"
                "3. Click **Reprocess Audio** to get instant transcripts, flashcards, and quizzes!\n"
            ),
            "key_concepts": [
                {"term": "Cross-Platform Audio", "definition": "Capturing microphone and meeting audio across Windows WASAPI and Linux PulseAudio/PipeWire."},
                {"term": "Active Recall", "definition": "A study technique involving testing memory through question-and-answer retrieval rather than passive reading."}
            ],
            "flashcards": [
                {
                    "question": "What is the best way to capture Google Meet audio on Linux and Windows?",
                    "answer": "Select 'System / Meeting Audio' loopback device in the audio source dropdown."
                },
                {
                    "question": "Where are the synchronized notes stored?",
                    "answer": "In your local CrossSync SQLite database, automatically synced across all connected devices."
                }
            ],
            "action_items": [
                {"title": "Review recorded session key points", "due": "Today", "completed": False},
                {"title": "Enter Gemini API Key in Settings for live AI summarization", "due": "ASAP", "completed": False}
            ],
            "quiz": [
                {
                    "question": "Which learning technique is used by the Flashcards tab to boost retention?",
                    "options": ["A) Passive reading", "B) Active Recall & Spaced Repetition", "C) Cramming", "D) Highlighting"],
                    "correct_index": 1,
                    "explanation": "Active recall forces the brain to retrieve information, strengthening neural pathways."
                }
            ],
            "transcript": f"Audio recorded: {filename}. (Connect Gemini API Key in settings to generate verbatim transcript with speaker timestamps)."
        }
