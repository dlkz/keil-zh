from __future__ import annotations

import os
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "build", "__pycache__", "备份", "tools/python"}
TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".gitattributes",
    ".gitignore",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
SENSITIVE_SUFFIXES = {
    ".bak",
    ".crt",
    ".csv",
    ".db",
    ".der",
    ".docx",
    ".hex",
    ".key",
    ".log",
    ".map",
    ".p12",
    ".pdf",
    ".pem",
    ".pfx",
    ".sqlite",
    ".tmp",
    ".uvopt",
    ".uvproj",
    ".xlsx",
}
SECRET_PATTERNS = (
    ("GitHub token", re.compile(rb"ghp_[A-Za-z0-9]{30,}")),
    ("GitHub token", re.compile(rb"github_pat_[A-Za-z0-9_]{30,}")),
    ("OpenAI-style key", re.compile(rb"sk-[A-Za-z0-9_-]{20,}")),
    ("AWS key", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("Google API key", re.compile(rb"AIza[0-9A-Za-z_-]{20,}")),
    (
        "private key",
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "credential assignment",
        re.compile(
            rb"(?i)\b(?:password|passwd|api[_-]?key|client[_-]?secret|"
            rb"access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*"
            rb"[\"']?[A-Za-z0-9_./+=-]{8,}"
        ),
    ),
)
PRIVATE_IPV4 = re.compile(
    rb"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|"
    rb"192\.168\.(?:\d{1,3}\.)\d{1,3}|"
    rb"172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3}|"
    rb"169\.254\.(?:\d{1,3}\.)\d{1,3})\b"
)


def project_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(relative == skipped or relative.startswith(skipped + "/") for skipped in SKIP_DIRS):
            continue
        yield path, relative


class PrivacyTests(unittest.TestCase):
    def test_local_identity_is_not_embedded(self) -> None:
        terms = {
            value
            for value in (
                os.environ.get("USERPROFILE"),
                os.environ.get("USERNAME"),
                os.environ.get("COMPUTERNAME"),
                Path.home().name,
            )
            if value and len(value) >= 4
        }
        hits: list[str] = []
        for path, relative in project_files():
            data = path.read_bytes()
            relative_lower = relative.lower()
            for term in terms:
                if (
                    term.lower() in relative_lower
                    or term.encode("utf-8") in data
                    or term.encode("utf-16le") in data
                ):
                    hits.append(relative)
                    break
        self.assertEqual(hits, [], "Local identity found in package files")

    def test_no_credentials_or_private_addresses(self) -> None:
        hits: list[str] = []
        for path, relative in project_files():
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_SUFFIXES:
                continue
            data = path.read_bytes()
            if any(pattern.search(data) for _, pattern in SECRET_PATTERNS):
                hits.append(f"{relative}: credential")
            if PRIVATE_IPV4.search(data):
                hits.append(f"{relative}: private IPv4")
        self.assertEqual(hits, [], "Sensitive values found in project text")

    def test_no_sensitive_project_artifacts(self) -> None:
        hits = [
            relative
            for path, relative in project_files()
            if path.suffix.lower() in SENSITIVE_SUFFIXES
            or path.name in {"python-path.txt", "UV4.exe", "UV4.exe.bak", "patch-report.json"}
        ]
        self.assertEqual(hits, [], "Sensitive artifacts found in package")


if __name__ == "__main__":
    unittest.main()
