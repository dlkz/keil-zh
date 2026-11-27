from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


class VSFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", ctypes.c_uint32),
        ("structure_version", ctypes.c_uint32),
        ("file_version_ms", ctypes.c_uint32),
        ("file_version_ls", ctypes.c_uint32),
        ("product_version_ms", ctypes.c_uint32),
        ("product_version_ls", ctypes.c_uint32),
        ("file_flags_mask", ctypes.c_uint32),
        ("file_flags", ctypes.c_uint32),
        ("file_os", ctypes.c_uint32),
        ("file_type", ctypes.c_uint32),
        ("file_subtype", ctypes.c_uint32),
        ("file_date_ms", ctypes.c_uint32),
        ("file_date_ls", ctypes.c_uint32),
    ]


def file_version(path: Path) -> tuple[int, int, int, int]:
    if os.name != "nt":
        raise SystemExit("This patcher requires Windows.")
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    version.GetFileVersionInfoSizeW.restype = ctypes.c_uint32
    version.GetFileVersionInfoW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    version.GetFileVersionInfoW.restype = ctypes.c_int
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    version.VerQueryValueW.restype = ctypes.c_int

    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        raise SystemExit(f"No Windows version information found in: {path}")
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = ctypes.c_void_p()
    length = ctypes.c_uint32()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    fixed = ctypes.cast(pointer, ctypes.POINTER(VSFixedFileInfo)).contents
    if fixed.signature != 0xFEEF04BD:
        raise SystemExit(f"Invalid Windows version resource in: {path}")
    return (
        fixed.file_version_ms >> 16,
        fixed.file_version_ms & 0xFFFF,
        fixed.file_version_ls >> 16,
        fixed.file_version_ls & 0xFFFF,
    )


def check_official_signature(path: Path) -> tuple[bool, str, str]:
    shells = [
        shell
        for shell in (
            shutil.which("pwsh.exe"),
            shutil.which("powershell.exe"),
        )
        if shell
    ]
    if not shells:
        shells = ["powershell.exe"]
    script = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "$s=Get-AuthenticodeSignature -LiteralPath $env:KEIL_ZH_SIGNATURE_PATH; "
        "$subject=''; if($s.SignerCertificate){$subject=$s.SignerCertificate.Subject}; "
        "[pscustomobject]@{Status=$s.Status.ToString();Subject=$subject} | "
        "ConvertTo-Json -Compress"
    )
    environment = os.environ.copy()
    environment["KEIL_ZH_SIGNATURE_PATH"] = str(path)
    last_error = "PowerShell is unavailable"
    for powershell in shells:
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                check=False,
                env=environment,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            last_error = str(error)
            continue
        if result.returncode != 0:
            last_error = (
                result.stderr.decode("utf-8", errors="replace").strip()
                or f"PowerShell exited with {result.returncode}"
            )
            continue
        try:
            data = json.loads(result.stdout.decode("utf-8-sig").strip())
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            last_error = f"Cannot parse signature result: {error}"
            continue
        status = str(data.get("Status", ""))
        subject = str(data.get("Subject", ""))
        subject_lower = subject.lower()
        trusted = status.lower() == "valid" and any(
            marker in subject_lower
            for marker in ("o=arm limited", "o=arm ltd", "cn=arm limited", "cn=arm ltd")
        )
        return trusted, status, subject
    return False, "Error", last_error


def find_targets() -> list[Path]:
    candidates: list[Path] = []
    try:
        import winreg
    except ImportError:
        winreg = None
    if winreg is not None:
        products = ("MDK", "C51", "C251", "C166", "MDK-ARM", "ARM")
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY, 0):
                for product in products:
                    for prefix in (
                        r"SOFTWARE\Keil\Products",
                        r"SOFTWARE\WOW6432Node\Keil\Products",
                    ):
                        try:
                            with winreg.OpenKey(
                                hive, prefix + "\\" + product, 0, winreg.KEY_READ | view
                            ) as key:
                                base, _ = winreg.QueryValueEx(key, "Path")
                        except OSError:
                            continue
                        candidates.append(Path(base).parent / "UV4" / "UV4.exe")
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates.extend(
        (
            local / "Keil_v5" / "UV4" / "UV4.exe",
            Path(r"C:\Keil_v5\UV4\UV4.exe"),
            Path(r"C:\Keil\UV4\UV4.exe"),
            Path(r"C:\Keil\C51\UV4\UV4.exe"),
            Path(r"D:\Keil_v5\UV4\UV4.exe"),
        )
    )
    found: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            key = os.path.normcase(str(resolved))
            if resolved.is_file() and key not in seen:
                seen.add(key)
                found.append(resolved)
        except OSError:
            continue
    return found


def resolve_target(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    targets = find_targets()
    if not targets:
        raise SystemExit(
            "Could not locate UV4.exe automatically; pass --target \"<...>\\UV4\\UV4.exe\"."
        )
    if len(targets) > 1:
        listed = "\n".join(f"  {path}" for path in targets)
        raise SystemExit(
            "Found multiple Keil uVision installations. Pass --target explicitly:\n" + listed
        )
    return targets[0]
