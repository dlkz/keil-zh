from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from tools.winplatform import file_version, sha256


def backup_paths(target: Path) -> tuple[Path, Path]:
    backup = target.with_name(target.name + ".bak")
    return backup, backup.with_name(backup.name + ".json")


def load_backup_metadata(backup: Path) -> dict[str, object] | None:
    metadata_path = backup.with_name(backup.name + ".json")
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read backup metadata {metadata_path}: {error}") from error
    if metadata.get("format_version") != 1:
        raise SystemExit(f"Unsupported backup metadata format: {metadata_path}")
    for key in ("source_sha256", "output_sha256", "source_version"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value:
            raise SystemExit(f"Backup metadata is missing {key}: {metadata_path}")
    return metadata


def write_backup_metadata(
    target: Path,
    source_hash: str,
    source_version: str,
    output_hash: str,
) -> Path:
    _, metadata_path = backup_paths(target)
    metadata = {
        "format_version": 1,
        "source_sha256": source_hash,
        "source_version": source_version,
        "output_sha256": output_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = metadata_path.with_name(metadata_path.name + ".building")
    temporary.write_bytes(
        (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    os.replace(temporary, metadata_path)
    return metadata_path


def rotate_stale_backup(target: Path) -> Path | None:
    backup, metadata_path = backup_paths(target)
    if not backup.is_file():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rotated = backup.with_name(f"{backup.name}.previous-{stamp}")
    os.replace(backup, rotated)
    if metadata_path.is_file():
        os.replace(metadata_path, rotated.with_name(rotated.name + ".json"))
    return rotated


def choose_source(
    target: Path,
    backup: Path,
    official_hash: str,
    for_copy: bool,
    target_looks_patched: bool | None = None,
) -> tuple[Path, str, str]:
    target_hash = sha256(target)
    if for_copy or not backup.is_file():
        return target, target_hash, "target"

    backup_hash = sha256(backup)
    metadata = load_backup_metadata(backup)
    if metadata is not None:
        source_hash = str(metadata["source_sha256"]).upper()
        output_hash = str(metadata["output_sha256"]).upper()
        if backup_hash != source_hash:
            raise SystemExit(
                f"Backup does not match its metadata: {backup}\n"
                "Move the backup and metadata aside, then run the patch again."
            )
        if target_hash == output_hash:
            return backup, backup_hash, "metadata-verified-backup"
        if target_hash == official_hash:
            return target, target_hash, "official-target"
        if file_version(target) != file_version(backup):
            return target, target_hash, "newer-target"
        raise SystemExit(
            "The existing backup metadata does not match the current UV4.exe.\n"
            f"Target: {target}\nBackup: {backup}\n"
            "Move the backup and metadata aside, or use --copy for a non-destructive build."
        )

    if target_hash == backup_hash:
        return target, target_hash, "same-as-backup"
    if target_hash == official_hash:
        return target, target_hash, "official-target"
    if file_version(target) != file_version(backup):
        return target, target_hash, "newer-target"
    if target_looks_patched is None:
        raise SystemExit(
            "Cannot safely choose between UV4.exe and the legacy backup.\n"
            f"Target: {target}\nBackup: {backup}\n"
            "Use metadata from the current version or run --copy from a known original."
        )
    if target_looks_patched:
        return backup, backup_hash, "legacy-backup"
    return target, target_hash, "legacy-target"


def restore(target: Path, force: bool = False) -> int:
    backup, metadata_path = backup_paths(target)
    restored = False
    if backup.is_file():
        backup_hash = sha256(backup)
        backup_version = file_version(backup)
        if backup_version[0] != 5:
            raise SystemExit(
                f"Backup is not a supported uVision 5.x file: {backup}\n"
                "No file was changed."
            )
        metadata = load_backup_metadata(backup)
        target_exists = target.is_file()
        if not force and metadata is not None:
            if backup_hash != str(metadata["source_sha256"]).upper():
                raise SystemExit(
                    "Backup does not match its metadata. No file was changed.\n"
                    f"Backup: {backup}"
                )
            expected_target = str(metadata["output_sha256"]).upper()
            if target_exists and sha256(target) != expected_target:
                raise SystemExit(
                    "UV4.exe has changed since it was patched. No file was changed.\n"
                    f"Target: {target}\nUse --force only after verifying the files."
                )
        elif not force and target_exists and file_version(target) != backup_version:
            raise SystemExit(
                "The backup belongs to a different Keil version. No file was changed.\n"
                f"Target: {target}\nBackup: {backup}"
            )

        temporary = target.with_name(target.name + ".restoring")
        if temporary.exists():
            temporary.unlink()
        try:
            shutil.copy2(backup, temporary)
            if sha256(temporary) != backup_hash:
                raise SystemExit("Restore verification failed; the backup copy does not match.")
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        backup.unlink()
        if metadata_path.is_file():
            metadata_path.unlink()
        restored = True
        print(f"已从 {backup.name} 还原原版 {target.name}（并删除备份）。")
    removed = False
    for name in ("UV4_zh-CN.exe", "UV4_CN.exe"):
        copy = target.with_name(name)
        if copy.is_file():
            try:
                copy.unlink()
                removed = True
                print(f"已删除中文副本 {name}。")
            except OSError as error:
                print(f"警告：无法删除 {copy}（可能仍在运行）：{error}")
    if not restored and not removed:
        print("没有发现汉化痕迹（UV4.exe.bak 不存在，也没有中文副本）。")
    return 0
