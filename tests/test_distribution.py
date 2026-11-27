from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class DistributionTests(unittest.TestCase):
    def test_windows_scripts_use_crlf(self) -> None:
        scripts = [
            ROOT / "一键安装汉化.bat",
            ROOT / "一键还原英文.bat",
            ROOT / "一键预览匹配.bat",
            ROOT / "工具" / "生成中文版.cmd",
            ROOT / "工具" / "还原英文.cmd",
            ROOT / "工具" / "预览匹配.cmd",
        ]
        for path in scripts:
            data = path.read_bytes()
            crlf = data.count(b"\r\n")
            lone_lf = data.replace(b"\r\n", b"").count(b"\n")
            self.assertGreater(crlf, 0, path)
            self.assertEqual(lone_lf, 0, path)
            data.decode("gbk")

    def test_gitattributes_requires_crlf_for_windows_scripts(self) -> None:
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.bat text eol=crlf", attributes)
        self.assertIn("*.cmd text eol=crlf", attributes)


if __name__ == "__main__":
    unittest.main()
