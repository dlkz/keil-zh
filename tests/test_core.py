from __future__ import annotations

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build_patch
import tools.backup as backup_tools
import tools.catalog as catalog
import tools.winplatform as winplatform_tools
from tools.verify import compare_sections
from tools.winres import (
    ResourceFormatError,
    build_string_block,
    parse_string_block,
)


def make_pe(sections: dict[str, bytes]) -> bytes:
    pe_offset = 0x80
    table_offset = pe_offset + 24
    data_offset = 0x400
    data = bytearray(data_offset)
    data[:2] = b"MZ"
    struct.pack_into("<L", data, 0x3C, pe_offset)
    data[pe_offset : pe_offset + 4] = b"PE\0\0"
    struct.pack_into("<H", data, pe_offset + 6, len(sections))
    struct.pack_into("<H", data, pe_offset + 20, 0)
    for index, (name, payload) in enumerate(sections.items()):
        while len(data) < data_offset + len(payload):
            data.append(0)
        header = table_offset + index * 40
        data[header : header + 8] = name.encode("ascii")[:8].ljust(8, b"\0")
        struct.pack_into("<LL", data, header + 16, len(payload), data_offset)
        data[data_offset : data_offset + len(payload)] = payload
        data_offset += len(payload)
    return bytes(data)


@contextmanager
def mock_source_files(
    target: Path,
    backup: Path,
    target_hash: str = "B" * 64,
    backup_hash: str = "A" * 64,
):
    hashes = {
        target.resolve(): target_hash,
        backup.resolve(): backup_hash,
    }
    with mock.patch.object(
        backup_tools, "sha256", side_effect=lambda path: hashes[Path(path).resolve()]
    ), mock.patch.object(backup_tools, "file_version", return_value=(5, 40, 0, 0)):
        yield


class WinResTests(unittest.TestCase):
    def test_string_block_round_trip(self) -> None:
        original = build_string_block(3, {32: "Open", 35: "Close"})
        self.assertEqual(build_string_block(3, parse_string_block(3, original)), original)

    def test_string_block_rejects_short_and_trailing_data(self) -> None:
        with self.assertRaises(ResourceFormatError):
            parse_string_block(1, b"\x03\0A\0B\0C\0")
        with self.assertRaises(ResourceFormatError):
            parse_string_block(1, build_string_block(1, {}) + b"x")


class VerifyTests(unittest.TestCase):
    def test_only_resource_section_may_change(self) -> None:
        before = {
            ".text": b"text",
            ".rdata": b"read",
            ".data": b"data",
            ".rsrc": b"before",
            ".reloc": b"reloc",
        }
        after = dict(before)
        after[".rsrc"] = b"after"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before_path = root / "before.exe"
            after_path = root / "after.exe"
            before_path.write_bytes(make_pe(before))
            after_path.write_bytes(make_pe(after))
            result = compare_sections(before_path, after_path)
        self.assertTrue(result["code_sections_identical"])
        self.assertTrue(result["resource_section_changed"])
        self.assertEqual(result["changed_sections"], [".rsrc"])

    def test_other_section_change_is_rejected(self) -> None:
        before = {".text": b"text", ".rsrc": b"resource", ".reloc": b"before"}
        after = {".text": b"text", ".rsrc": b"resource", ".reloc": b"after"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before_path = root / "before.exe"
            after_path = root / "after.exe"
            before_path.write_bytes(make_pe(before))
            after_path.write_bytes(make_pe(after))
            result = compare_sections(before_path, after_path)
        self.assertFalse(result["code_sections_identical"])
        self.assertIn(".reloc", result["changed_sections"])


class BackupTests(unittest.TestCase):
    def test_verified_metadata_uses_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            target.write_bytes(b"patched")
            backup.write_bytes(b"original")
            metadata = {
                "format_version": 1,
                "source_sha256": "A" * 64,
                "output_sha256": "B" * 64,
                "source_version": "5.40.0.0",
            }
            backup.with_name(backup.name + ".json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )
            with mock_source_files(target, backup):
                source, source_hash, reason = build_patch.choose_source(
                    target, backup, "B" * 64, for_copy=False
                )
        self.assertEqual(source, backup)
        self.assertEqual(source_hash, "A" * 64)
        self.assertEqual(reason, "metadata-verified-backup")

    def test_copy_mode_never_uses_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            target.write_bytes(b"patched")
            backup.write_bytes(b"original")
            with mock.patch.object(backup_tools, "sha256", return_value="C" * 64):
                source, source_hash, reason = build_patch.choose_source(
                    target, backup, "C" * 64, for_copy=True
                )
        self.assertEqual(source, target)
        self.assertEqual(source_hash, "C" * 64)
        self.assertEqual(reason, "target")

    def test_official_target_ignores_stale_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            target.write_bytes(b"official")
            backup.write_bytes(b"stale")
            with mock_source_files(target, backup):
                source, source_hash, reason = build_patch.choose_source(
                    target, backup, "B" * 64, for_copy=False
                )
        self.assertEqual(source, target)
        self.assertEqual(source_hash, "B" * 64)
        self.assertEqual(reason, "official-target")

    def test_same_version_original_target_wins_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            target.write_bytes(b"new-build")
            backup.write_bytes(b"old-build")
            with mock_source_files(target, backup):
                source, _, reason = build_patch.choose_source(
                    target,
                    backup,
                    "C" * 64,
                    for_copy=False,
                    target_looks_patched=False,
                )
        self.assertEqual(source, target)
        self.assertEqual(reason, "legacy-target")

    def test_same_version_patched_target_uses_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            target.write_bytes(b"patched")
            backup.write_bytes(b"original")
            with mock_source_files(target, backup):
                source, _, reason = build_patch.choose_source(
                    target,
                    backup,
                    "C" * 64,
                    for_copy=False,
                    target_looks_patched=True,
                )
        self.assertEqual(source, backup)
        self.assertEqual(reason, "legacy-backup")

    def test_ambiguous_legacy_backup_requires_a_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            target.write_bytes(b"target")
            backup.write_bytes(b"backup")
            with mock_source_files(target, backup):
                with self.assertRaises(SystemExit):
                    build_patch.choose_source(target, backup, "C" * 64, for_copy=False)

    def test_restore_replaces_target_and_removes_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "UV4.exe"
            backup = root / "UV4.exe.bak"
            metadata_path = root / "UV4.exe.bak.json"
            original = b"original"
            patched = b"patched"
            target.write_bytes(patched)
            backup.write_bytes(original)
            metadata_path.write_text(
                json.dumps(
                    {
                        "format_version": 1,
                        "source_sha256": build_patch.sha256(backup),
                        "output_sha256": build_patch.sha256(target),
                        "source_version": "5.40.0.0",
                    }
                ),
                encoding="utf-8",
            )
            with ExitStack() as stack:
                stack.enter_context(redirect_stdout(io.StringIO()))
                stack.enter_context(
                    mock.patch.object(
                        backup_tools, "file_version", return_value=(5, 40, 0, 0)
                    )
                )
                result = build_patch.restore(target)
            self.assertEqual(result, 0)
            self.assertEqual(target.read_bytes(), original)
            self.assertFalse(backup.exists())
            self.assertFalse(metadata_path.exists())

    def test_backup_metadata_is_written_next_to_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "UV4.exe"
            target.write_bytes(b"target")
            metadata_path = build_patch.write_backup_metadata(
                target,
                source_hash="A" * 64,
                source_version="5.40.0.0",
                output_hash="B" * 64,
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata_path.name, "UV4.exe.bak.json")
        self.assertEqual(metadata["source_sha256"], "A" * 64)
        self.assertEqual(metadata["output_sha256"], "B" * 64)

    def test_report_write_failure_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "blocker"
            blocker.write_text("file", encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertFalse(build_patch.write_report_file(blocker / "report.json", {}))

    def test_multiple_targets_require_explicit_path(self) -> None:
        with mock.patch.object(
            winplatform_tools,
            "find_targets",
            return_value=[Path("C:/Keil/UV4.exe"), Path("D:/Keil/UV4.exe")],
        ):
            with self.assertRaises(SystemExit):
                build_patch.resolve_target()


class SignatureTests(unittest.TestCase):
    def test_accepts_arm_signature(self) -> None:
        result = mock.Mock(
            returncode=0,
            stdout=b'{"Status":"Valid","Subject":"CN=ARM Ltd, O=ARM Ltd"}',
            stderr=b"",
        )
        with mock.patch.object(winplatform_tools.subprocess, "run", return_value=result):
            trusted, status, subject = winplatform_tools.check_official_signature(
                Path("UV4.exe")
            )
        self.assertTrue(trusted)
        self.assertEqual(status, "Valid")
        self.assertIn("ARM Ltd", subject)

    def test_rejects_other_signer(self) -> None:
        result = mock.Mock(
            returncode=0,
            stdout=b'{"Status":"Valid","Subject":"CN=Contoso"}',
            stderr=b"",
        )
        with mock.patch.object(winplatform_tools.subprocess, "run", return_value=result):
            trusted, status, _ = winplatform_tools.check_official_signature(Path("UV4.exe"))
        self.assertFalse(trusted)
        self.assertEqual(status, "Valid")


class CatalogTests(unittest.TestCase):
    def test_atomic_text_writer_uses_lf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            catalog.write_text_atomic(path, "a\nb\n")
            self.assertEqual(path.read_bytes(), b"a\nb\n")

if __name__ == "__main__":
    unittest.main()
