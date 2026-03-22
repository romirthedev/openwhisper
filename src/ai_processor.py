"""
AI post-processing for transcribed text.

Two modes:
  1. Rule-based (always available) – fixes punctuation, capitalization, and
     common corrections like "I mean, actually..." → the corrected version.
  2. Ollama LLM (optional) – sends text to a local Ollama instance for smart
     reformatting, handling self-corrections, bullet points, etc.
"""
import re
import json
from typing import Optional
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# Filler words optionally stripped
FILLER_WORDS = re.compile(
    r"\b(um+|uh+|er+|hmm+|like,? |you know,? |I mean,? )\b",
    re.IGNORECASE,
)

# Correction pattern: "X, I mean / actually / wait / never mind, Y" → use Y
CORRECTION_PATTERN = re.compile(
    r".+?\s*,?\s*(?:i mean|actually|wait,? no|never mind)[,.]?\s+",
    re.IGNORECASE,
)

OLLAMA_PROMPT = """\
You are a transcription editor. The following is raw voice dictation text. \
Clean it up by:
1. Fixing punctuation and capitalization.
2. If the speaker corrects themselves (says "I mean", "actually", "never mind", \
"wait no", etc.), keep only what they intended to say.
3. Format bullet points if the speaker says "bullet point" or lists items.
4. Remove excessive filler words (um, uh, er) but keep the meaning intact.
5. Return ONLY the cleaned text, no explanation.

Raw text:
{text}
"""


class AIProcessor:
    """
    Post-processes transcription text.

    Args:
        use_ollama: Use Ollama LLM when available.
        ollama_url: Base URL for Ollama API (default: http://localhost:11434).
        ollama_model: Model name to use (default: llama3.1).
        strip_fillers: Remove filler words in rule-based mode.
    """

    def __init__(
        self,
        use_ollama: bool = False,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1",
        strip_fillers: bool = False,
    ):
        self.use_ollama = use_ollama
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.strip_fillers = strip_fillers

    def process(self, text: str) -> str:
        """Process text and return cleaned version."""
        if not text.strip():
            return text

        if self.use_ollama and REQUESTS_AVAILABLE:
            result = self._ollama_process(text)
            if result:
                return result

        return self._rule_based_process(text)

    # ------------------------------------------------------------------ #
    #  Rule-based                                                           #
    # ------------------------------------------------------------------ #

    def _rule_based_process(self, text: str) -> str:
        text = text.strip()

        # Handle self-corrections: keep the corrected part
        text = self._resolve_corrections(text)

        # Strip filler words if enabled
        if self.strip_fillers:
            text = FILLER_WORDS.sub("", text)
            text = re.sub(r"\s{2,}", " ", text).strip()

        # Capitalize first letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        # Ensure sentence ends with punctuation
        if text and text[-1] not in ".!?,;:":
            text += "."

        # Fix spacing around punctuation
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        text = re.sub(r"([.,!?;:])\s*([A-Z])", r"\1 \2", text)

        return text

    def _resolve_corrections(self, text: str) -> str:
        """
        Handle verbal corrections.
        E.g. "Let's meet at 5, I mean actually 6" → "Let's meet at 6"
        E.g. "Never mind that, how about tomorrow" → "How about tomorrow"
        """
        # Patterns like "never mind [that/it/all], [rest]"
        never_mind = re.compile(
            r"^.*?never mind(?:\s+(?:that|it|everything|all))?[,.]?\s+",
            re.IGNORECASE,
        )
        m = never_mind.search(text)
        if m:
            remainder = text[m.end():].strip()
            if remainder:
                text = remainder

        # "I mean X" / "actually X" at end of a clause – keep X
        # Only apply when the correction appears mid-sentence
        correction = re.compile(
            r"([^.!?]*?),?\s+(?:i mean|actually)\s+([^.!?]+)",
            re.IGNORECASE,
        )
        m = correction.search(text)
        if m:
            # Replace matched portion with just the corrected part
            text = text[: m.start()] + m.group(2) + text[m.end():]

        return text.strip()

    # ------------------------------------------------------------------ #
    #  Ollama LLM                                                           #
    # ------------------------------------------------------------------ #

    def _ollama_process(self, text: str) -> Optional[str]:
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": OLLAMA_PROMPT.format(text=text),
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
        except Exception:
            pass
        return None

    def is_ollama_available(self) -> bool:
        """Check whether Ollama is running and the model is available."""
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return any(self.ollama_model in m for m in models)
        except Exception:
            pass
        return False
