"""Unit tests for the core scrubber (declaude.scrub_message).

This is declaude's riskiest logic: a wrong regex could either leave a Claude
trace behind or corrupt a legitimate commit message. The same function source
is reused verbatim as the git-filter-repo callback, so testing it here covers
the real rewrite path too.

Run:  python -m pytest          (or)   python tests/test_scrub.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from declaude import DETECT_RE, scrub_message  # noqa: E402


def scrub(text: str) -> str:
    return scrub_message(text.encode("utf-8")).decode("utf-8")


class ScrubMessageTests(unittest.TestCase):
    def test_drops_claude_coauthor_trailer(self):
        msg = (
            "fix: thing\n\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = scrub(msg)
        self.assertNotRegex(out, r"(?i)claude")
        self.assertNotRegex(out, r"(?i)anthropic")
        self.assertIn("fix: thing", out)

    def test_drops_generated_with_claude_code_line(self):
        msg = (
            "feat: add feature\n\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = scrub(msg)
        self.assertNotIn("Generated with", out)
        self.assertNotRegex(out, r"(?i)claude")
        self.assertTrue(out.startswith("feat: add feature"))

    def test_keeps_human_coauthor(self):
        msg = (
            "chore: pairing\n\n"
            "Co-Authored-By: Alice <alice@example.com>\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = scrub(msg)
        self.assertIn("Alice <alice@example.com>", out)
        self.assertNotRegex(out, r"(?i)claude")

    def test_leaves_clean_message_unchanged(self):
        msg = "refactor: rename helper\n\nMakes the API clearer.\n"
        self.assertEqual(scrub(msg), msg)

    def test_collapses_blank_lines_after_removal(self):
        msg = (
            "subject\n\n"
            "body line\n\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        )
        out = scrub(msg)
        self.assertNotIn("\n\n\n", out)
        self.assertIn("body line", out)

    def test_strips_inline_noreply_email(self):
        msg = "hack by claude noreply@anthropic.com here\n"
        out = scrub(msg)
        self.assertNotIn("anthropic.com", out)

    def test_subject_only_message_survives(self):
        self.assertEqual(scrub("just a subject\n"), "just a subject\n")

    def test_detect_re_matches_what_scrub_removes(self):
        # Anything DETECT_RE flags should be gone after scrubbing.
        traced = "x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
        self.assertTrue(DETECT_RE.search(traced))
        self.assertFalse(DETECT_RE.search(scrub(traced)))


if __name__ == "__main__":
    unittest.main()
