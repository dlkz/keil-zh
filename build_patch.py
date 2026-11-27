#!/usr/bin/env python3
"""让 Keil µVision 5.x 直接显示简体中文（默认**原地汉化**原版 UV4.exe）。

核心目标：**双击桌面上的 Keil 图标就是中文**，不需要另开别的 exe。

* 默认行为：就地改写官方 `UV4.exe` 的界面资源；首次改写前自动备份
  `UV4.exe.bak`（原版）并记录 `UV4.exe.bak.json`，可用 `--restore` 一键还原；
* 只改资源段 `.rsrc`：除 `.rsrc` 外的所有 PE 段与备份原版逐字节一致，
  写入前会自动校验，校验不过立即放弃；
* 词典按 **资源身份 + 英文原文 SHA-256** 双重匹配（参照 GitHub 项目
  player4086/keil-uv5-zh-cn-patch 的"原文指纹"方案），只有完全对得上的
  条目才会被替换，其余一律保持英文；
* 完整验证过的版本按文件 SHA-256 精确识别，其它 µVision 5.x 走保守的
  "兼容模式"，并要求匹配率达到阈值（默认 70%）才允许写入。

附加选项：`--copy` 只生成旁边的 `UV4_zh-CN.exe`、完全不动原版（非破坏式）。

本项目的词典同时覆盖 **字符串表 / 菜单 / 对话框**。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tools.backup import (  # noqa: E402
    backup_paths,
    choose_source,
    restore,
    rotate_stale_backup,
    write_backup_metadata,
)
from tools.verify import compare_sections  # noqa: E402
from tools.winplatform import (  # noqa: E402
    check_official_signature,
    file_version,
    resolve_target,
    sha256,
)
from tools.winres import (  # noqa: E402
    RT_DIALOG,
    RT_MENU,
    RT_STRING,
    build_string_block,
    iter_menu_items,
    parse_dialog,
    parse_menu,
    parse_string_block,
    read_resources,
    serialize_dialog,
    serialize_menu,
    update_resources,
)

ENGLISH_US = 1033
DEFAULT_CATALOG = ROOT / "translations" / "zh_CN.json"
DEFAULT_MIN_COVERAGE = 0.70
# Patched resources score near zero against the English catalog; keep a small margin.
PATCHED_TARGET_MAX_COVERAGE = 0.05


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-16le")).hexdigest().upper()


def load_catalog(path: Path) -> dict[str, object]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read translation catalog {path}: {error}") from error
    if catalog.get("format_version") != 2:
        raise SystemExit("Unsupported translation catalog format; expected version 2.")
    if int(catalog.get("language", -1)) != ENGLISH_US:
        raise SystemExit("Translation catalog language does not match the target resources.")
    translations = catalog.get("translations")
    if not isinstance(translations, dict):
        raise SystemExit("Translation catalog has no translations object.")
    if not isinstance(translations.get("string_table"), dict) or not isinstance(
        translations.get("menus"), dict
    ):
        raise SystemExit("Translation catalog string_table or menus section is invalid.")
    if not isinstance(translations.get("dialogs", {}), dict):
        raise SystemExit("Translation catalog dialogs section is invalid.")
    return catalog


def translation_pair(entry: object, label: str) -> tuple[str, str]:
    if not isinstance(entry, dict):
        raise SystemExit(f"Invalid catalog entry: {label}")
    source = entry.get("source_sha256")
    translation = entry.get("translation")
    if (
        not isinstance(source, str)
        or len(source) != 64
        or any(character not in "0123456789ABCDEFabcdef" for character in source)
        or not isinstance(translation, str)
        or not translation
    ):
        raise SystemExit(f"Invalid source hash or translation in catalog entry: {label}")
    return source.upper(), translation


def menu_item_at_path(menu: dict[str, object], path: str) -> dict[str, object] | None:
    try:
        indexes = [int(value) for value in path.split("/")]
    except ValueError:
        return None
    items = menu["items"]
    item: dict[str, object] | None = None
    for index in indexes:
        if index < 0 or index >= len(items):
            return None
        item = items[index]
        items = item["children"]
    return item


def dialog_item_slot(dialog: dict[str, object], key: str) -> tuple[str, int] | None:
    """把词典键解析为 (kind, index)；title 用 ("title", 0)，控件用 ("item", 索引)。"""
    if key == "title":
        return ("title", 0)
    if key.startswith("item:"):
        try:
            index = int(key[5:])
        except ValueError:
            return None
        if 0 <= index < len(dialog["items"]):
            return ("item", index)
    return None


def read_dialog_text(dialog: dict[str, object], slot: tuple[str, int]) -> str | None:
    kind, index = slot
    if kind == "title":
        target = dialog["title"]
        return target[1] if target[0] == "string" else None
    item = dialog["items"][index]
    return item["title"][1] if item["title"][0] == "string" else None


def write_dialog_text(dialog: dict[str, object], slot: tuple[str, int], text: str) -> bool:
    kind, index = slot
    if kind == "title":
        dialog["title"] = ("string", text)
        return True
    item = dialog["items"][index]
    if item["title"][0] != "string":
        return False
    item["title"] = ("string", text)
    return True


def plan_updates(
    target: Path, catalog: dict[str, object]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    translations = catalog["translations"]
    string_catalog = translations["string_table"]
    menu_catalog = translations["menus"]
    dialog_catalog = translations.get("dialogs", {})
    try:
        catalog_strings: dict[int, object] = {
            int(key): value for key, value in string_catalog.items()
        }
        catalog_menus: dict[int, dict[str, object]] = {}
        for key, value in menu_catalog.items():
            if not isinstance(value, dict):
                raise ValueError(key)
            catalog_menus[int(key)] = value
        catalog_dialogs: dict[int, dict[str, object]] = {}
        for key, value in dialog_catalog.items():
            if not isinstance(value, dict):
                raise ValueError(key)
            catalog_dialogs[int(key)] = value
    except (TypeError, ValueError) as error:
        raise SystemExit(f"Translation catalog contains an invalid resource ID: {error}")

    matched_strings: set[int] = set()
    matched_menus: set[tuple[int, str]] = set()
    matched_dialogs: set[tuple[int, str]] = set()
    updates: list[dict[str, object]] = []
    report: dict[str, object] = {
        "target": str(target),
        "language": ENGLISH_US,
        "string_table": {"resources": 0, "texts": 0},
        "menus": {"resources": 0, "texts": 0},
        "dialogs": {"resources": 0, "texts": 0},
    }
    target_totals = {"strings": 0, "menus": 0, "dialogs": 0}

    for target_item in read_resources(target):
        if int(target_item["lang"]) != ENGLISH_US:
            continue
        resource_name = target_item["name"]

        if target_item["type"] == RT_STRING and isinstance(resource_name, int):
            target_values = parse_string_block(resource_name, target_item["data"])
            target_totals["strings"] += sum(1 for text in target_values.values() if text)
            changed = 0
            for string_id, current_text in target_values.items():
                entry = catalog_strings.get(string_id)
                if entry is None:
                    continue
                source_hash, translation = translation_pair(entry, f"string {string_id}")
                if text_sha256(current_text) != source_hash:
                    continue
                target_values[string_id] = translation
                matched_strings.add(string_id)
                changed += 1
            if changed:
                updates.append(
                    {
                        "type": RT_STRING,
                        "name": resource_name,
                        "lang": ENGLISH_US,
                        "data": build_string_block(resource_name, target_values),
                    }
                )
                report["string_table"]["resources"] += 1
                report["string_table"]["texts"] += changed

        elif target_item["type"] == RT_MENU and isinstance(resource_name, int):
            target_menu = parse_menu(target_item["data"])
            target_totals["menus"] += sum(
                1
                for _, item in iter_menu_items(target_menu["items"])
                if str(item.get("text") or "")
            )
            entries = catalog_menus.get(resource_name)
            if entries is None:
                continue
            changed = 0
            for path, entry in entries.items():
                source_hash, translation = translation_pair(
                    entry, f"menu {resource_name}:{path}"
                )
                item = menu_item_at_path(target_menu, path)
                if item is None or text_sha256(str(item["text"])) != source_hash:
                    continue
                item["text"] = translation
                matched_menus.add((resource_name, path))
                changed += 1
            if changed:
                updates.append(
                    {
                        "type": RT_MENU,
                        "name": resource_name,
                        "lang": ENGLISH_US,
                        "data": serialize_menu(target_menu),
                    }
                )
                report["menus"]["resources"] += 1
                report["menus"]["texts"] += changed

        elif target_item["type"] == RT_DIALOG and isinstance(resource_name, int):
            target_dialog = parse_dialog(target_item["data"])
            if target_dialog["title"][0] == "string" and str(target_dialog["title"][1]):
                target_totals["dialogs"] += 1
            target_totals["dialogs"] += sum(
                1
                for item in target_dialog["items"]
                if item["title"][0] == "string" and str(item["title"][1])
            )
            entries = catalog_dialogs.get(resource_name)
            if entries is None:
                continue
            changed = 0
            for key, entry in entries.items():
                slot = dialog_item_slot(target_dialog, key)
                if slot is None:
                    continue
                current_text = read_dialog_text(target_dialog, slot)
                if current_text is None:
                    continue
                source_hash, translation = translation_pair(
                    entry, f"dialog {resource_name}:{key}"
                )
                if text_sha256(current_text) != source_hash:
                    continue
                if write_dialog_text(target_dialog, slot, translation):
                    matched_dialogs.add((resource_name, key))
                    changed += 1
            if changed:
                updates.append(
                    {
                        "type": RT_DIALOG,
                        "name": resource_name,
                        "lang": ENGLISH_US,
                        "data": serialize_dialog(target_dialog),
                    }
                )
                report["dialogs"]["resources"] += 1
                report["dialogs"]["texts"] += changed

    menu_keys = {
        (resource_id, path)
        for resource_id, entries in catalog_menus.items()
        for path in entries
    }
    dialog_keys = {
        (resource_id, key)
        for resource_id, entries in catalog_dialogs.items()
        for key in entries
    }
    total = len(catalog_strings) + len(menu_keys) + len(dialog_keys)
    matched = len(matched_strings) + len(matched_menus) + len(matched_dialogs)
    target_total = sum(target_totals.values())
    report["resource_updates"] = len(updates)
    report["coverage"] = {
        "matched": matched,
        "total": total,
        "ratio": round(matched / total, 6) if total else 0.0,
        "target_matched": matched,
        "target_total": target_total,
        "target_ratio": round(matched / target_total, 6) if target_total else 0.0,
        "matched_strings": len(matched_strings),
        "total_strings": len(catalog_strings),
        "unmatched_string_ids": sorted(set(catalog_strings) - matched_strings),
        "matched_menu_items": len(matched_menus),
        "total_menu_items": len(menu_keys),
        "unmatched_menu_items": [
            f"{resource_id}:{path}" for resource_id, path in sorted(menu_keys - matched_menus)
        ],
        "matched_dialog_texts": len(matched_dialogs),
        "total_dialog_texts": len(dialog_keys),
        "unmatched_dialog_texts": [
            f"{resource_id}:{key}"
            for resource_id, key in sorted(dialog_keys - matched_dialogs)
        ],
        "target_strings": target_totals["strings"],
        "target_menus": target_totals["menus"],
        "target_dialogs": target_totals["dialogs"],
    }
    return updates, report


def write_report_file(path: Path, report: dict[str, object]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )
    except OSError as error:
        print(f"警告：操作结果未改变，但无法写入报告 {path}：{error}", file=sys.stderr)
        return False
    return True


def apply_patch(
    target: Path,
    source: Path,
    output: Path,
    updates: list[dict[str, object]],
    backup: Path,
    report: dict[str, object],
    *,
    in_place: bool,
    source_hash: str,
    source_version: tuple[int, int, int, int],
) -> None:
    if in_place and backup.is_file() and sha256(backup) != source_hash:
        rotated = rotate_stale_backup(target)
        report["stale_backup_rotated"] = str(rotated) if rotated is not None else None
    if in_place and not backup.is_file():
        shutil.copy2(target, backup)
        report["backup_created"] = True
        source = backup
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".building")
    if temporary.exists():
        temporary.unlink()
    try:
        shutil.copy2(source, temporary)
        update_resources(temporary, updates)
        verification = compare_sections(source, temporary)
        report["verification"] = verification
        if (
            not verification["code_sections_identical"]
            or not verification["resource_section_changed"]
        ):
            raise SystemExit("安全校验未通过：只能允许 .rsrc 段变化，已放弃写入。")
        os.replace(temporary, output)
    except OSError as error:
        raise SystemExit(
            "无法写入目标文件：\n"
            f"  {output}\n"
            f"原因：{error}\n"
            "请先完全退出正在运行的 Keil / µVision；若仍失败，请以管理员身份运行。"
            + ("" if in_place else "\n原版 UV4.exe 未被修改。")
        ) from error
    finally:
        if temporary.exists():
            temporary.unlink()
    report["output_sha256"] = sha256(output)
    if in_place:
        try:
            metadata_path = write_backup_metadata(
                target,
                source_hash=source_hash,
                source_version=".".join(map(str, source_version)),
                output_hash=str(report["output_sha256"]),
            )
            report["backup_metadata"] = str(metadata_path)
        except OSError as error:
            report["backup_metadata"] = None
            print(f"警告：汉化成功，但无法写入备份元数据：{error}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Make Keil uVision 5.x display Simplified Chinese. By default the "
            "installed UV4.exe is patched in place (an original UV4.exe.bak is "
            "created first), so the normal desktop shortcut starts the Chinese UI."
        )
    )
    parser.add_argument(
        "--target",
        type=Path,
        help="path to an official uVision 5.x UV4.exe (default: auto-detect)",
    )
    parser.add_argument(
        "--catalog",
        default=DEFAULT_CATALOG,
        type=Path,
        help="translation catalog (default: bundled Simplified Chinese catalog)",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="write UV4_zh-CN.exe beside the original instead of patching it in place",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="explicit output path (implies a non-destructive copy)",
    )
    report_group = parser.add_mutually_exclusive_group()
    report_group.add_argument(
        "--report",
        type=Path,
        help="write the JSON report to this path (default: build/patch-report.json)",
    )
    report_group.add_argument(
        "--no-report",
        action="store_true",
        help="do not write a JSON report file",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=DEFAULT_MIN_COVERAGE,
        help="minimum catalog and target coverage for untested uVision 5.x builds",
    )
    parser.add_argument(
        "--exact-only",
        action="store_true",
        help="accept only the fully tested executable hash",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="restore the original English UV4.exe from UV4.exe.bak and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow restore when backup metadata no longer matches the target",
    )
    parser.add_argument(
        "--skip-signature-check",
        action="store_true",
        help="allow a source file without a valid Arm Authenticode signature",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="inspect resources without modifying UV4.exe",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args(argv)

    if args.force and not args.restore:
        raise SystemExit("--force can only be used with --restore.")
    target = resolve_target(args.target)
    if args.restore:
        print(f"Keil 安装目录：{target.parent}")
        return restore(target, force=args.force)
    if not target.is_file():
        raise SystemExit(f"Target file does not exist: {target}")

    backup, _ = backup_paths(target)
    in_place = not args.copy and args.output is None
    output = (
        target
        if in_place
        else (
            args.output.resolve()
            if args.output is not None
            else target.with_name("UV4_zh-CN.exe")
        )
    )
    if not in_place and output == target:
        raise SystemExit("Explicit output path equals the original; drop --output to patch in place.")

    catalog_path = args.catalog.resolve()
    report_path = (
        args.report.resolve()
        if args.report is not None
        else (
            None
            if args.no_report or args.dry_run
            else (ROOT / "build" / "patch-report.json").resolve()
        )
    )
    if not 0.0 <= args.min_coverage <= 1.0:
        raise SystemExit("--min-coverage must be between 0.0 and 1.0.")

    catalog_hash = sha256(catalog_path)
    catalog = load_catalog(catalog_path)
    catalog_target = catalog.get("target")
    if not isinstance(catalog_target, dict) or not isinstance(
        catalog_target.get("sha256"), str
    ):
        raise SystemExit("Translation catalog target metadata is invalid.")
    tested_hash = str(catalog_target["sha256"]).upper()

    target_version = file_version(target)
    if target_version[0] != 5:
        raise SystemExit(
            f"Unsupported file version {'.'.join(map(str, target_version))}; "
            "only uVision 5.x is accepted. No file was changed."
        )
    target_updates, target_report = plan_updates(target, catalog)
    target_probe_ratio = float(target_report["coverage"]["target_ratio"])
    source, source_hash, source_reason = choose_source(
        target,
        backup,
        tested_hash,
        for_copy=not in_place,
        target_looks_patched=target_probe_ratio <= PATCHED_TARGET_MAX_COVERAGE,
    )
    version = file_version(source)
    if version[0] != 5:
        raise SystemExit(
            f"Unsupported file version {'.'.join(map(str, version))}; "
            "only uVision 5.x is accepted. No file was changed."
        )
    if args.skip_signature_check:
        signature_ok, signature_status, signer_subject = True, "Skipped", ""
    else:
        signature_ok, signature_status, signer_subject = check_official_signature(source)
    if not signature_ok:
        raise SystemExit(
            "Source file does not have a trusted Arm Authenticode signature.\n"
            f"File: {source}\nStatus: {signature_status}\nSigner: {signer_subject or '-'}\n"
            "No file was changed. Use --skip-signature-check only for a known local build."
        )
    exact_target = source_hash == tested_hash

    if source == target:
        updates, report = target_updates, target_report
    else:
        updates, report = plan_updates(source, catalog)
    catalog_coverage = float(report["coverage"]["ratio"])
    target_coverage = float(report["coverage"]["target_ratio"])
    accepted = exact_target or (
        not args.exact_only
        and catalog_coverage >= args.min_coverage
        and target_coverage >= args.min_coverage
    )
    compatibility = "exact-tested" if exact_target else "compatible-source-match"
    report["target_version"] = ".".join(map(str, version))
    report["target"] = str(target)
    report["target_sha256"] = sha256(target)
    report["target_probe_coverage"] = target_probe_ratio
    report["source"] = str(source)
    report["source_sha256"] = source_hash
    report["source_reason"] = source_reason
    report["signature"] = {
        "valid": signature_ok,
        "status": signature_status,
        "subject": signer_subject,
        "check_skipped": bool(args.skip_signature_check),
    }
    report["mode"] = "in-place" if in_place else "copy"
    report["backup"] = str(backup) if in_place else None
    report["catalog"] = str(catalog_path)
    report["catalog_sha256"] = catalog_hash
    report["compatibility"] = {
        "mode": compatibility,
        "fully_tested": exact_target,
        "minimum_coverage": args.min_coverage,
        "catalog_coverage": catalog_coverage,
        "target_coverage": target_coverage,
        "exact_only": bool(args.exact_only),
        "accepted": accepted,
    }
    report["output"] = str(output)
    report["dry_run"] = bool(args.dry_run)
    report["report"] = str(report_path) if report_path is not None else None

    if accepted and not args.dry_run:
        apply_patch(
            target,
            source,
            output,
            updates,
            backup,
            report,
            in_place=in_place,
            source_hash=source_hash,
            source_version=version,
        )

    if report_path is not None:
        write_report_file(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not accepted:
        print(
            "Compatibility check failed: catalog or target coverage is below the "
            "required threshold, or --exact-only rejected this build. "
            "No file was changed.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
