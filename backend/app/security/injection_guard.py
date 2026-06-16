"""
Prompt injection and jailbreak detection guard.
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: List[Tuple[str, str]] = [
    # Role manipulation
    (r"ignore\s+(previous|prior|all|your)\s+instructions?", "ignore_instructions"),
    (r"forget\s+(your|previous|all)\s+instructions?", "forget_instructions"),
    (r"you\s+are\s+now\s+", "you_are_now"),
    (r"roleplay\s+as\s+", "roleplay_as"),
    (r"pretend\s+(you\s+are|to\s+be)\s+", "pretend_to_be"),
    (r"act\s+as\s+(if\s+you\s+are|a\s+)", "act_as"),
    (r"(you\s+have\s+no\s+restrictions?|no\s+ethical\s+guidelines?)", "no_restrictions"),
    # System prompt leakage
    (r"<\s*system\s*>", "system_tag"),
    (r"system\s*:", "system_colon"),
    (r"\[system\]", "system_bracket"),
    (r"reveal\s+(your|the)\s+system\s+prompt", "reveal_system_prompt"),
    (r"show\s+(me\s+)?(your|the)\s+(instructions?|prompt|system)", "show_instructions"),
    # Jailbreak keywords
    (r"jailbreak", "jailbreak"),
    (r"dan\s+mode", "dan_mode"),
    (r"developer\s+mode", "developer_mode"),
    (r"override\s+(all\s+)?safety", "override_safety"),
    # Harmful content
    (r"(how\s+to\s+make|instructions?\s+for|making)\s+.*?(bomb|weapon|explosive)", "harmful_content"),
]

_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE | re.DOTALL), name)
    for pattern, name in _INJECTION_PATTERNS
]

_MAX_SPECIAL_CHAR_RATIO = 0.30  # 30% non-alphanumeric chars triggers flag


@dataclass
class ScanResult:
    """Result of an injection scan."""
    is_safe: bool
    risk_level: str  # "low" | "medium" | "high" | "critical"
    matched_patterns: List[str] = field(default_factory=list)
    score: float = 0.0  # 0.0 = safe, 1.0 = most dangerous


class InjectionGuard:
    """
    Scans text for prompt injection, jailbreak, and manipulation attempts.
    """

    def scan(self, text: str) -> ScanResult:
        """
        Scan text for injection patterns.

        Args:
            text: Input text to scan (query or document).

        Returns:
            ScanResult with safety verdict and matched patterns.
        """
        matched: List[str] = []

        # 1. Direct pattern matching
        for pattern, name in _COMPILED_PATTERNS:
            if pattern.search(text):
                matched.append(name)

        # 2. Base64 injection detection
        base64_result = self._check_base64(text)
        if base64_result:
            matched.append("base64_injection")
            logger.warning("Base64 injection attempt: decoded='%s'", base64_result[:100])

        # 3. Special character density
        if len(text) > 20:
            non_alnum = sum(1 for c in text if not c.isalnum() and not c.isspace())
            ratio = non_alnum / len(text)
            if ratio > _MAX_SPECIAL_CHAR_RATIO:
                matched.append("excessive_special_chars")

        # Compute risk level
        score = min(1.0, len(matched) / 5.0)
        risk_level = self._compute_risk(matched, score)
        is_safe = risk_level in ("low",) and not matched

        result = ScanResult(
            is_safe=is_safe,
            risk_level=risk_level,
            matched_patterns=matched,
            score=round(score, 3),
        )

        if not is_safe:
            logger.warning(
                "Injection detected: risk=%s, patterns=%s, text_preview='%s'",
                risk_level, matched, text[:100],
            )

        return result

    def _check_base64(self, text: str) -> str:
        """
        Check if text contains Base64-encoded injection attempts.
        Returns decoded string if injection found, empty string otherwise.
        """
        # Look for base64-like substrings (length ≥ 20, valid base64 charset)
        b64_pattern = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
        for match in b64_pattern.finditer(text):
            candidate = match.group()
            try:
                decoded = base64.b64decode(candidate + "==").decode("utf-8", errors="ignore")
                # Check if decoded text contains injection keywords
                for pattern, _ in _COMPILED_PATTERNS[:8]:  # check first 8 critical patterns
                    if pattern.search(decoded):
                        return decoded
            except Exception:
                continue
        return ""

    def _compute_risk(self, matched: List[str], score: float) -> str:
        """Compute risk level from matched patterns."""
        if not matched:
            return "low"

        critical_patterns = {
            "jailbreak", "dan_mode", "developer_mode", "override_safety",
            "harmful_content", "base64_injection",
        }
        high_patterns = {
            "ignore_instructions", "forget_instructions", "you_are_now",
            "roleplay_as", "pretend_to_be", "reveal_system_prompt",
        }

        if any(p in critical_patterns for p in matched):
            return "critical"
        if any(p in high_patterns for p in matched):
            return "high"
        if len(matched) >= 2:
            return "medium"
        return "low"
