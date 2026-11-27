# Keil µVision 5.x 简体中文补丁（非官方改进版）

> 本仓库是基于 [cddd-yin/keil-zh](https://github.com/cddd-yin/keil-zh)（提交
> `69fb191`）的非官方独立改进版。原始项目及贡献者保留其版权；本项目与
> Arm / Keil 无隶属或官方关系。

## 本改进版与上游的差异

- 强制 Windows 批处理使用 CRLF，并在 Windows CI 中实际启动预览入口。
- 直接调用仓库内置 Python，修正管理员提权、退出码和日志编码问题。
- 增加备份元数据、旧备份轮换、同版本目标识别和事务式英文还原。
- 校验除 `.rsrc` 外的全部 PE 段，并增加字符串表、菜单和对话框往返验证。
- 默认校验 Arm Authenticode 签名；多套 Keil 安装时停止猜测并要求 `--target`。
- 增加单元测试、隐私扫描，以及 Release ZIP 的 CRLF 和敏感文件检查。

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

> 注意：双击前请先**完全退出** Keil µVision。
> 如果安装过多套 Keil，脚本会列出全部路径并停止。请使用
> `一键安装汉化.bat --target "<...>\UV4.exe"` 明确指定要汉化的版本。

### 第 3 步：打开 Keil

照常双击桌面/开始菜单里的 Keil 图标——界面就是中文了。

> **想还原英文**：双击 `一键还原英文.bat`，从备份恢复原版，桌面图标随即恢复英文。
> **升级 / 重装 Keil 后界面变回英文**：`UV4.exe` 被官方文件覆盖了，再做一次第 2 步即可。

## 常见问题

| 现象 | 原因 | 解决方法 |
|---|---|---|
| 双击 bat 弹「Windows 已保护你的电脑」 | SmartScreen 对未签名脚本的常规拦截 | 点「更多信息」→「仍要运行」 |
| 提示权限不足 | Keil 安装在受保护目录 | 右键对应 bat，选择「以管理员身份运行」 |
| 提示发现多套 `UV4.exe` | 同时安装了 MDK、C51 或多个版本 | 按提示增加 `--target "<完整路径>"`，不要依赖自动选择 |
| 提示 Arm 签名无效 | 文件被修改、不是官方 UV4，或证书链不可用 | 先用官方安装包修复 Keil；只在确认文件可靠时使用 `--skip-signature-check` |
| 提示找不到 `UV4.exe` | 安装位置特殊或注册表无记录 | 用 `工具\生成中文版.cmd --target "D:\Keil_v5\UV4\UV4.exe"` 手动指定 |
| 汉化后仍然是英文 | 有 Keil 进程未完全退出，写入被跳过 | 完全退出 Keil 后重跑；查看 `build\build.log` 和 `build\patch-report.json` |
| 杀毒软件报警 | 本项目修改资源后会使 Arm 的数字签名失效 | 放行/信任即可；介意的话可用 `--copy` 模式（见高级用法） |
| 提示 `Compatibility check failed` | 词典命中率或目标文本覆盖率低于安全阈值 | 先运行预览；不要盲目调低阈值，未测试版本仍可能缺译 |
| 「关于 µVision」正文、个别按钮仍是英文 | 这些文本硬编码在程序代码里，不在资源中 | 已知限制，见下文 |
| 想彻底还原 | — | 双击 `一键还原英文.bat` |

### 安全设计与验证范围
- **只改界面资源**：仅替换 `UV4.exe` 中 PE 资源段的字符串表、菜单、对话框文本，除 `.rsrc` 外的所有 PE 段与原版**逐字节一致**（写入前自动校验，不过则放弃）；
- **指纹精确匹配**：词典按「资源身份 + 英文原文 SHA-256」双重匹配，只有二者同时命中才会替换，未命中项保持英文；
- **首次自动备份**：原版保留为 `UV4.exe.bak`，并用 `UV4.exe.bak.json` 记录源文件、版本和汉化后哈希；
- **安全还原**：先写 `UV4.exe.restoring` 并校验，再原子替换目标；元数据与目标不匹配时默认拒绝还原。
- **签名校验**：默认要求源文件的 Authenticode 状态为有效，且签发者属于 Arm Limited / ARM Ltd。

## 高级用法（命令行）

```powershell
$py = ".\tools\python\python.exe"

& $py build_patch.py                       # 原地汉化（默认；自动备份 UV4.exe.bak）
& $py build_patch.py --dry-run             # 只统计；默认不写报告
& $py build_patch.py --restore             # 还原英文（等价于 一键还原英文.bat）
& $py build_patch.py --restore --force     # 确认文件后再强制还原
& $py build_patch.py --copy                # 非破坏式：只生成旁边的 UV4_zh-CN.exe，完全不动原版
& $py build_patch.py --target "<...>\UV4.exe"
& $py build_patch.py --report build\report.json
& $py build_patch.py --no-report
& $py build_patch.py --skip-signature-check  # 仅用于确认可信的本地构建
& $py build_patch.py --min-coverage 0.85   # 其它版本提高兼容模式阈值
& $py build_patch.py --exact-only          # 只接受完整验证过的版本哈希
& $py tools\verify.py "<原版备份>" "<UV4.exe>"   # PE 段 + 字符串表/菜单/对话框校验
```

> `tools\python\` 内置便携版 Python 3.12（仅标准库），一键脚本优先使用它；
> 系统 Python 已测试 3.9 和 3.12；其它版本不保证可用。也可以在仓库根目录放
> `python-path.txt` 指定解释器完整路径。

## 工作原理（一句话）

µVision 的大部分界面文字保存在 `UV4.exe` 的 Win32 资源里（字符串表 `RT_STRING`、
菜单 `RT_MENU`、对话框 `RT_DIALOG`）。本补丁用官方 Windows 资源 API
把 `1033`（英文）资源中的文本**精确替换**为简体中文，并就地写回 `UV4.exe`。

安全设计：

1. 首次执行先备份 `UV4.exe.bak`（原版英文），并记录源哈希、版本和汉化后哈希；只有元数据匹配时才用备份继续匹配；
2. 每条词典的键是“**资源身份**（字符串 ID / 菜单路径 / 对话框控件序号）+
   **英文原文的 SHA-256 指纹**”，只有二者同时命中才会替换；
3. 写入在临时文件上进行，写完后逐段比对：除 `.rsrc` 外的所有 PE 段必须与原版完全一致；
   校验不过就放弃写入，`UV4.exe` 保持原样。

> 设计上只修改资源段，不修改程序代码。MDK 5.40.0.0 已完成实机验证；
> 其它版本仍属实验性，资源改写会使 Arm 数字签名失效。

## 覆盖情况

以 µVision **5.40.0.0** 为例（见 `build/patch-report.json`）：

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

| 版本 | 状态 |
| --- | --- |
| MDK µVision 5.40.0.0 | ✅ 实际启动并验证中文菜单、工具栏和主要命令（`exact-tested`） |
| C51 µVision 5.27.1.0 | ⚠️ 资源级补丁和字符串/菜单/对话框校验通过；未完成 UI 逐页检查 |
| 其它 µVision 5.x | ⚠️ 实验性；词典命中率和目标文本覆盖率都达到阈值才允许写入 |
| µVision 4.x / 非 µVision | ❌ 拒绝（只接受主版本号为 5 的文件） |

词典按**原文指纹**（而非版本号）匹配，因此小版本升级后部分词条仍可能有效，但不能据此保证完整汉化。
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
一键预览匹配.bat           双击：只检查并写 build\preview.log，不修改 UV4.exe
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
  `build\missing.txt`，补进 `src.json` 后重新生成即可；
- 同一英文在不同位置共用同一译文；需要区分上下文时，再扩展词典格式。
- 格式符、快捷键、助记符或换行校验失败时，生成器会写 `build\ignored.txt` 并返回失败，不会静默发布。
- 提交前运行 `& ".\tools\python\python.exe" -m unittest discover -s tests -v`；推送 `zh-v*` 标签会由 GitHub Actions 生成 ZIP 和 SHA256。

## 隐私与数据处理

- Release 包不包含用户的 `UV4.exe`、`UV4.exe.bak`、许可证、运行日志、`python-path.txt` 或本机路径。
- 汉化工具在本机处理目标文件，不主动上传工程、可执行文件或备份。
- Authenticode 验证由 Windows 证书链机制完成，系统可能按自身策略访问网络检查证书状态。
- CI 会自动扫描用户名、主机名、绝对用户路径、凭据和敏感文件；失败报告只显示相对路径和类别。

## 版权与免责声明

- 本仓库**不提供** Arm/Keil 的软件本体、`UV4.exe`、编译器、Pack、许可证或注册机；
  补丁在**使用者自己的机器**上由官方文件现场生成。内置 Python 是公开的开源运行时。
- Keil、µVision、MDK、ARM 是 Arm Limited / Keil 的商标；请通过官方渠道获取并使用正版软件。
- 本项目为第三方非官方汉化，与 Arm / Keil 无任何关联。
- 工具与词典：MIT（见 `LICENSE`）；使用本项目产生的一切后果由使用者自行承担。
