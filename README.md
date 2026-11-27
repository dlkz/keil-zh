# Keil µVision 5.x 简体中文补丁（非官方改进版）

> 本项目是基于
> [cddd-yin/keil-zh](https://github.com/cddd-yin/keil-zh) 提交 `69fb191`
> 的非官方独立改进版。

**原地汉化**你的 Keil µVision：运行一次，之后**双击桌面那个 Keil 图标就是中文**，
不需要额外的启动器，也不需要改名。**不用安装 Python**——仓库已内置便携版。

![主界面](截图/01-主界面.png)

## 怎么装？（新手照做即可）

> 全程只需三步，**不用装任何东西**（Python 已内置在仓库里）。装完双击桌面 Keil 图标就是中文。

### 第 1 步：把这个仓库下载到电脑

优先从 **Releases** 下载已测试的 ZIP；没有 Release 时，才从 **`Code` → `Download ZIP`** 下载源码包。
下载后**解压**到任意文件夹（例如桌面）。
解压后应能看到 `一键安装汉化.bat`、`build_patch.py`、`tools` 等文件。

> 提示：如果不会解压，右键压缩包 → 用系统自带的「全部解压缩」即可。

### 第 2 步：双击 `一键安装汉化.bat`

- 脚本先按普通权限运行；只有 Keil 安装目录不允许当前用户写入时，才需要右键选择「以管理员身份运行」。
- 脚本会**自动找到**已安装的 Keil µVision 并打补丁（原版会先备份为 `UV4.exe.bak`）。
- 看到 `[成功]` 即完成。

> **完全退出 Keil：** 双击前请先关闭 Keil µVision。
>
> **存在多套安装：** 脚本会列出全部路径并停止。请使用
> `一键安装汉化.bat --target "<...>\UV4.exe"` 明确指定要汉化的版本。

### 第 3 步：打开 Keil

照常双击桌面/开始菜单里的 Keil 图标——界面就是中文了。

> **还原英文：** 双击 `一键还原英文.bat`，从备份恢复原版。
>
> **升级或重装 Keil：** `UV4.exe` 会被官方文件覆盖；再做一次第 2 步即可。

## 常见问题

| 现象 | 处理 |
|---|---|
| SmartScreen 提示「Windows 已保护你的电脑」 | 先核对下载来源和 SHA-256；确认无误后再选择「仍要运行」 |
| 提示权限不足 | 右键对应脚本，选择「以管理员身份运行」 |
| 发现多套 `UV4.exe` | 使用 `--target "<完整路径>"` 明确指定目标，不要依赖自动选择 |
| 找不到 `UV4.exe` | 使用 `工具\生成中文版.cmd --target "<完整路径>"` 手动指定 |
| 汉化后仍然是英文 | 完全退出 Keil 后重跑，并查看 `build/build.log` 与 `build/patch-report.json` |
| 想彻底还原 | 双击 `一键还原英文.bat` |

### 签名、安全软件与兼容性

**提示 Arm 签名无效**

先用官方安装包修复 Keil。只有在确认文件来源可靠时，才使用
`--skip-signature-check`。

**杀毒软件报警**

先核对下载来源、SHA-256 和报毒名称，不要直接关闭防护。确认文件可信后，
再按安全软件提示处理，或改用 `--copy` 生成中文副本。

**提示 `Compatibility check failed`**

先运行预览并检查匹配报告。不要盲目降低阈值；未验证的版本仍可能缺译。

**「关于 µVision」正文或个别按钮仍是英文**

这些文本位于程序代码中，不属于可替换的资源，详见下文「已知限制」。

## 本改进版与上游的差异

- 强制 Windows 批处理使用 CRLF，并在 Windows CI 中实际启动预览入口。
- 直接调用仓库内置 Python，修正管理员提权、退出码和日志编码问题。
- 增加备份元数据、旧备份轮换、同版本目标识别和事务式英文还原。
- 校验除 `.rsrc` 外的全部 PE 段，并增加字符串表、菜单和对话框往返验证。
- 默认校验 Arm Authenticode 签名；多套 Keil 安装时停止猜测并要求 `--target`。
- 增加单元测试、隐私扫描，以及 Release ZIP 的 CRLF 和敏感文件检查。

## 高级用法（命令行）

先设置内置 Python 路径：

```powershell
$py = ".\tools\python\python.exe"
```

### 原地汉化与还原

```powershell
& $py build_patch.py
& $py build_patch.py --copy
& $py build_patch.py --restore
& $py build_patch.py --restore --force
& $py build_patch.py --target "<...>\UV4.exe"
```

### 预览、报告与校验

```powershell
& $py build_patch.py --dry-run
& $py build_patch.py --report build\report.json
& $py build_patch.py --no-report
& $py tools\verify.py "<原版备份>" "<UV4.exe>"
```

### 兼容性与签名选项

```powershell
& $py build_patch.py --skip-signature-check
& $py build_patch.py --min-coverage 0.85
& $py build_patch.py --exact-only
```

> `tools/python/` 内置便携版 Python 3.12（仅标准库），一键脚本优先使用它；
> 系统 Python 已测试 3.9 和 3.12；其它版本不保证可用。也可以在仓库根目录放
> `python-path.txt` 指定解释器完整路径。

## 工作原理

µVision 的大部分界面文字保存在 `UV4.exe` 的 Win32 资源里（字符串表 `RT_STRING`、
菜单 `RT_MENU`、对话框 `RT_DIALOG`）。本补丁用官方 Windows 资源 API
把 `1033`（英文）资源中的文本**精确替换**为简体中文，并就地写回 `UV4.exe`。

## 安全设计与验证范围

1. **备份与来源识别：** 首次执行先备份 `UV4.exe.bak`，并记录源文件、版本和
   汉化后哈希；只有元数据匹配时才使用备份继续处理。
2. **指纹精确匹配：** 词典按「资源身份（字符串 ID、菜单路径或对话框控件序号）
   + 英文原文 SHA-256」匹配；两项同时命中才会替换，未命中项保持英文。
3. **资源级写入：** 写入在临时文件上进行，完成后逐段比对；除 `.rsrc` 外的
   所有 PE 段必须与原版完全一致，否则放弃写入，`UV4.exe` 保持原样。
4. **安全还原：** 先写 `UV4.exe.restoring` 并校验，再原子替换目标；
   元数据与目标不匹配时默认拒绝还原。
5. **签名校验：** 默认要求源文件的 Authenticode 状态有效，且签发者属于
   Arm Limited（或 ARM Ltd）。

> 设计上只修改资源段，不修改程序代码。MDK 5.40.0.0 已完成实机验证；
> 其它版本仍属实验性，资源改写会使 Arm 数字签名失效。

## 覆盖情况

以 µVision **5.40.0.0** 的实际测试结果为例；运行后可在 `build/patch-report.json`
查看同类报告：

| 资源 | 命中 / 总数 |
| --- | --- |
| 字符串表（RT_STRING） | 828 / 955 |
| 菜单（RT_MENU） | 265 / 318 |
| 对话框（RT_DIALOG） | 2043 / 2294 |
| **合计（按出现次数）** | **3136 条** |

词典在这些条目上的匹配率为 **100%**（`coverage.ratio = 1.0`）。
目标文件共有 3567 条非空可翻译文本，实际覆盖 3136 条（`coverage.target_ratio = 0.87917`）。
未命中的多为数字、寄存器名、器件型号、URL、脚本关键字等**本就不该翻译**的内容。

## 兼容性

| 版本 | 状态与说明 |
| --- | --- |
| MDK µVision 5.40.0.0 | **已验证**：实际启动并验证中文菜单、工具栏和主要命令（`exact-tested`） |
| C51 µVision 5.27.1.0 | **实验性**：资源级补丁和字符串/菜单/对话框校验通过；未完成 UI 逐页检查 |
| 其它 µVision 5.x | **实验性**：词典命中率和目标文本覆盖率都达到阈值才允许写入 |
| µVision 4.x / 非 µVision | **不支持**：只接受主版本号为 5 的文件 |

词典按**原文指纹**（而非版本号）匹配，因此小版本升级后部分词条仍可能有效；
但不能据此保证完整汉化。
**升级 / 重装 Keil 后**：`UV4.exe` 会被官方文件覆盖，重打一次 `一键安装汉化.bat` 即可。
旧备份如果与新版本不一致，会被轮换为带时间戳的 `.bak.previous-*`，不会用来覆盖新版。

## 已知限制

以下内容存在于**程序代码/数据**而非资源中，无法通过资源方式翻译，保持英文：

- 「关于 µVision」对话框中的版权/许可正文（硬编码在 `.data`）；
- 少数属性表框架按钮（如「器件数据库」窗口底部的 *Close / Help*）；
- 由代码在运行时拼接或设置的个别文本，如窗格标题（*Project*、*Build Output*）、
  *Recent Files*、部分窗口标题等。

## 目录结构

```
一键安装汉化.bat           双击：汉化（新手入口）
一键还原英文.bat           双击：还原英文
一键预览匹配.bat           双击：只检查并写 build/preview.log，不修改 UV4.exe
build_patch.py            入口：原地汉化（默认）/ --copy / --restore / --dry-run
CHANGELOG.md              版本变化与已知限制
tests/                    标准库单元测试
.github/workflows/        Windows CI 与标签发布流程
tools/
  python/                 内置便携版 Python 3.12（仅标准库，免安装）
  winplatform.py          Windows 文件定位、版本读取与签名校验
  backup.py               备份元数据、源文件选择与事务式还原
  winres.py               PE 资源读写 + 字符串表 / 菜单 / 对话框格式解析
  catalog.py              由 translations/src.json + 官方 UV4.exe 生成指纹词典
  verify.py               PE 段对比 + 字符串表/菜单/对话框往返解析校验
translations/
  zh_CN.json              编译好的指纹词典（补丁实际使用）
  src.json                词典源文件（英文原文 → 简体中文）
工具/                     生成中文版 / 预览匹配 / 还原英文（一键 bat 调用它们）
截图/                     效果截图
```

## 维护与二次开发

- 修正某个词条：编辑 `translations/src.json` 中对应的“英文原文 → 中文”，
  运行 `& ".\tools\python\python.exe" tools\catalog.py`（会自动定位官方 `UV4.exe`）重新生成词典；
- 补翻新版本新增文案：先运行 `& ".\tools\python\python.exe" tools\catalog.py`，未翻译的界面文本会列到
  `build/missing.txt`，补进 `src.json` 后重新生成即可；
- 同一英文在不同位置共用同一译文；需要区分上下文时，再扩展词典格式。
- 格式符、快捷键、助记符或换行校验失败时，生成器会写 `build/ignored.txt` 并返回失败，不会静默发布。
- 提交前运行 `& ".\tools\python\python.exe" -B -m unittest discover -s tests -v`；
  推送 `zh-v*` 标签会由 GitHub Actions 生成 ZIP 和 SHA256。

## 隐私与数据处理

- Release 包不包含用户的 `UV4.exe`、`UV4.exe.bak`、Keil 商业授权文件、运行日志、
  `python-path.txt` 或本机路径。
- 汉化工具在本机处理目标文件，不主动上传工程、可执行文件或备份。
- Authenticode 验证由 Windows 证书链机制完成，系统可能按自身策略访问网络检查证书状态。
- CI 会自动扫描用户名、主机名、绝对用户路径、凭据和敏感文件；失败报告只显示相对路径和类别。

## 来源与版权

本项目是基于 [cddd-yin/keil-zh](https://github.com/cddd-yin/keil-zh) 提交
`69fb191` 的独立衍生项目，并非上游官方版本。

- 上游原始代码、文档及其贡献者保留各自版权。
- 本仓库新增和修改的部分，其版权由对应作者保留。
- 本仓库中由本项目作者创作的代码和翻译词典采用 MIT 许可证，详见 `LICENSE`。
- 仓库内置的 Python 运行时适用其自身许可证，详见 `tools/python/LICENSE.txt`。
- Arm/Keil 软件界面截图、商标、名称及其他第三方材料不在本项目 MIT 授权范围内，
  相关权利归各自权利人所有。

## 使用风险与免责声明

- **分发范围：** 本项目仅用于界面资源本地化，不附带、下载或分发 Arm/Keil 的软件本体、
  `UV4.exe`、编译器、Pack、商业授权文件、账号或注册机。工具只处理用户本机
  已安装的官方文件，不以修改授权状态或绕过授权机制为目的。
- **商标关系：** Keil、µVision、MDK、ARM 等名称及商标归 Arm Limited 或其关联公司所有。
  本项目仅在说明兼容对象时使用这些名称，与 Arm Limited 及其关联公司不存在
  隶属、授权、赞助或背书关系。
- **修改风险：** 汉化会修改目标可执行文件，可能导致数字签名失效、杀毒软件报警、升级后被覆盖，
  或因版本差异出现兼容问题。使用前请自行备份，并确认软件来源可靠。
- **MIT 免责：** 本项目及补丁按 MIT 许可证“现状”提供，不保证无错误运行、不发生数据丢失，
  也不保证适用于特定用途。
- **Keil 授权：** 使用 Keil 软件仍需获得其官方授权并遵守相应许可协议。本声明不修改 MIT
  许可证；如有冲突，以 `LICENSE` 中的条款为准。
