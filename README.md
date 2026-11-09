# totk-recomp-flatpak

非官方 **TotK Recomp**（《塞尔达传说：王国之泪》Switch 版静态重编译项目）安装器的 Flatpak 封装。

**构建方式**：直接解包上游官方 Linux AppImage Release 并重新打包为 Flatpak，**不做源码编译**，因此构建快、产物与上游完全一致。

- 上游源码：https://github.com/valentderah/totk-pc-recomp
- 上游制品：`TotK-Setup-x86_64-0.3.13-linux.AppImage`

---

## 和 Savage Wind 那套的关键区别

上游**没有**直接可分发的游戏可执行文件。Release 里给的是 **setup（安装器）**：
它读你自己的游戏 dump，用包内自带的 LLVM 工具链在**本机**把游戏逐函数翻译并编译成 `totk`，
再准备好着色器缓存。所以本 Flatpak 封装的是这个安装器，而不是一装就能玩的游戏。

| | Savage Wind（旷野之息） | TotK Recomp（王国之泪） |
|---|---|---|
| 上游产物 | 直接可运行的 `savagewind` | `totk-setup` 安装器 |
| 首次启动 | 选目录 → 编译（约 6 分钟） | 选 dump 与安装目录 → 翻译 + 编译 + 着色器准备（约 20-40 分钟） |
| 游戏产物 | `/app/bin/savagewind` | 你选的安装目录里的 `totk`（在沙箱外） |
| AppImage 体积 | 86 MB | 230 MB（解包约 830 MB，其中 LLVM 545 MB、Python 187 MB） |

---

## 下载安装

从本仓库的 [Releases](../../releases) 页面下载 `io.github.jcleng.TotKRecomp.flatpak`：

```bash
flatpak install --user io.github.jcleng.TotKRecomp.flatpak
flatpak run io.github.jcleng.TotKRecomp
```

## ⚠️ 重要：需要自备游戏文件

**本包不含任何版权游戏资源、密钥或 DUMP 工具。** 你需要自己合法获得的《王国之泪》：

- 本体：XCI / NSP / NSZ（1.0.0）
- 更新：1.1.0 / 1.2.1 / 1.4.3 的 NSP / NSZ
- `prod.keys`
- 可选：Switch 固件目录（`Contents/registered`），仅在中文/韩文/繁体需要系统共享字体时使用

安装器窗口里逐项选择，然后指定一个**安装目录**（建议放在家目录下，比如 `~/Games/TotK`），
点开始后它会在该目录里完成全部工作。上游采取零容忍政策，不提供、不分发任何游戏文件。

运行要求：x86-64 CPU（有 AVX2 走默认 v3 构建，只有 SSE4.2 会自动退化为 v2 构建）、
**Vulkan 1.3** 显卡驱动、16 GB 内存、约 40 GB 空闲磁盘（RomFS + 编译中间物 + 着色器缓存）。

## 编译完成之后

安装器会在你选的目录里生成普通可执行文件 `totk` 与 `libSDL3.so.0`。**它在沙箱外面，直接运行即可**：

```bash
~/Games/TotK/totk
```

安装器窗口完成页的 *Play* 按钮同样会直接启动它（沙箱对家目录有读写权限，所以能执行到）。
之后再玩不需要打开 Flatpak ——游戏是普通 Linux 程序，`totk.ini` 放在 `totk` 旁边，
所有图形/分辨率/手柄设置见上游的 `totk.ini.example`。

> 想给游戏加 Steam / 桌面快捷方式，直接指向 `totk` 的绝对路径即可。

## 数据与路径

```bash
# 沙箱内可见的上游 release 树
/app/share/totk-recomp

# 安装器记住的「上次用的游戏文件路径」
~/.var/app/io.github.jcleng.TotKRecomp/data/.local/state/totk-recomp/setup.json
```

游戏安装目录完全由你决定，在家目录里、从沙箱内外都能访问。

## 常见问题

**Wayland 桌面下报 `no display name and no $DISPLAY environment variable`？**

0.3.13 的第一版包有这个问题，已在当前版本修复；如果还遇到，先 `flatpak update` 到最新 Release。

原因值得记一下：安装器窗口用的是 **Tk 9，它没有 Wayland 后端**（`libtcl9tk9.0.so` 里搜不到任何
`wayland` 符号，`tk windowingsystem` 只会返回 `x11`）。所以纯 Wayland 会话下必须走 XWayland。

第一版清单里同时写了 `--socket=x11` 和 `--socket=fallback-x11`，而 `fallback-x11` 的语义是
「**只在没有 wayland socket 时**才给 x11」——两者同时存在时 Flatpak 不转发 X11，
沙箱里 `DISPLAY` 就是空的，`tk.Tk()` 直接抛异常。修法是 `x11` 与 `wayland` 都**无条件**给出，
包装脚本再加一层兜底：`DISPLAY` 为空时自己扫描 `/tmp/.X11-unix/X*` 取实际显示号
（XWayland 的显示号不一定是 `:0`）。

自查：

```bash
flatpak run --command=sh io.github.jcleng.TotKRecomp -c 'echo "DISPLAY=${DISPLAY:-EMPTY}"; ls /tmp/.X11-unix'
```

若 `DISPLAY` 仍为空且 `/tmp/.X11-unix` 里没有任何 socket，说明桌面的 XWayland 没开，手动指定显示号：

```bash
flatpak run --env=DISPLAY=:1 io.github.jcleng.TotKRecomp
```

**【注意】** 这个问题**不影响编译出来的游戏**：`totk` 是 SDL3 程序，原生支持 Wayland 与 X11。

**安装器窗口是英文，能改中文吗？**
能。安装器界面支持 `en`、`ru`、`pt-BR`、`zh-Hans` 四种语言，默认跟随系统 locale（Flatpak 里是 `C.UTF-8`，所以会落到英文）。
包装脚本会把参数透传给安装器，直接指定即可：

```bash
flatpak run io.github.jcleng.TotKRecomp --lang zh-Hans
```

（安装完成后，游戏自身的文本语言在安装器的 *Language* 一栏选择，与界面语言无关。）

**编译到一半没空间 / 想换目录？**
直接重新运行安装器，选一个新目录即可。安装器的每一步都有指纹记录（`totk-install.json`），
同一目录重跑会从中断处继续，也能识别「同一版本的新 release」并只重建受影响的部分。

**安装器说 "release incomplete"？**
说明包体不完整，通常装的是旧版。升级到最新 Release；如果仍有问题，把错误里列出的路径附到 issue。

**选中文时提示缺少共享字体？**
中文/韩文/繁体界面文字需要 Switch 固件里的系统字体（BFTTF）。在上游的 `--firmware` 一栏
指定固件目录（`Contents/registered`）和 `prod.keys` 后，安装器会在安装目录的 `shared-fonts/` 里生成。

**Flatpak 里编译，和直接在宿主上跑 AppImage 有区别吗？**
有一点：沙箱内的 glibc 来自 `org.freedesktop.Platform` 25.08，而游戏用包内自带的
`llvm/sysroot`（glibc 2.31，Steam Runtime 的那套）编译与链接，所以**产物不依赖沙箱**，
拿出来的 `totk` 在宿主上直接跑没有任何沙箱残留依赖。

**为什么要 `--filesystem=home`？**
游戏文件（XCI/NSP、keys、固件）和编译产物都在用户目录里。用 `home` 而不是 `host`
是为了不暴露系统分区；上游安装器本来也需要在这些位置读写。

---

## 版本对应

| 项目 | 值 |
|---|---|
| 应用 ID | `io.github.jcleng.TotKRecomp` |
| 上游版本 | TotK Recomp **0.3.13** (`0.3.13+ae30a61`) |
| 运行时 | `org.freedesktop.Platform` 25.08 |
| 构建来源 | 上游官方 `TotK-Setup-x86_64-0.3.13-linux.AppImage` |
| AppImage SHA256 | `b0c992f1e879401c119c796badc43687c3a5ac804d0d8c17f37fb16925f0e3ad` |

升级上游版本需要修改三处：
1. `io.github.jcleng.TotKRecomp.yaml` 里 `sources[].url` 的版本号和 `sha256`
2. `.github/workflows/build.yml` 里的 `TOTK_VERSION`
3. `io.github.jcleng.TotKRecomp.metainfo.xml` 里的 `<release>`

上游每个 release 资产的 `digest` 字段就是 sha256，可直接取用：

```bash
gh release view v0.3.13 -R valentderah/totk-pc-recomp --json assets \
  -q '.assets[] | select(.name|test("linux.AppImage")) | "\(.name)  \(.digest)"'
```

## 构建流程说明

全部构建都在 GitHub Actions（`.github/workflows/build.yml`）完成，本机不需要装 flatpak：

1. **Prefetch upstream AppImage** —— 先用带重试的 `curl` 把上游 AppImage 下载到 workspace 并校验 sha256。
   上游 release 资产所在的 GitHub CDN 会偶发返回 `504`，而 flatpak-builder 的内置下载器遇到这种抖动
   会直接让整个构建失败，所以这一步单独做，最多重试 10 轮（230 MB 文件，超时给到 30 分钟）。
2. **Patch manifest to local source** —— 把清单里的 remote `url`/`sha256` 就地换成 `path: upstream.AppImage`，
   让 flatpak-builder 只吃本地文件。（仓库里的清单始终保持带 url + sha256 的“可复现”形态。）
3. **Build Flatpak** —— `flatpak-builder` 在 `ghcr.io/flathub-infra/flatpak-github-actions:freedesktop-25.08`
   容器里构建并 `build-bundle` 产出 `.flatpak`。
4. **Verify bundle** —— 实际 `flatpak install --bundle` 一遍，确认 bundle 能被识别。
5. **Verify bundled toolchain inside the sandbox** —— 见下。
6. **Verify the setup GUI starts inside the sandbox** —— 见下。
7. **Compute checksum / Generate release notes** → **Upload artifact**（保留 14 天）→ **Release**
   （push 即自动建 Release，产物附 SHA256）。

### 为什么要在 CI 里真的把安装器和 GUI 跑起来

`totk-recomp` 这个包容易「装得上但一运行就报错」，因为安装器一启动就会校对整棵 release 树：
`installer/layout.py` 的 `missing()` 会逐个 `stat` 自带 Python、clang、lld、sysroot、
`bin/totk_xlate`、`bin/ninja`、`bin/hactool`、`runtime/libtotkrt*.a`、`runtime/deps/**`、
`recomp/patches-v*.txt`、`tools/data/expected-v*.json` 等几十个路径，缺一个就报 "release incomplete"。

所以 CI 里做了四层验证（任何一层失败就直接中断发布）：

| 步骤 | 验证什么 |
|---|---|
| 构建期自检 | manifest 里逐项 `test -e`，并 `import numpy, lz4, cryptography, fontTools, cffi` |
| 沙箱内工具链 | 上面那串路径再查一遍，然后调 `layout.find().missing()`，要求返回空 |
| 沙箱内编译 | 用**包内自带** clang + `--sysroot=llvm/sysroot` + `-fuse-ld=lld` 把 `installer/hostcheck.c` 真的编出来，运行并打印 Vulkan 探测结果 |
| 沙箱内 GUI | 装 Xvfb 起 `:99`，跑 `python -m installer.gui --selftest`：它会建出真窗口、把每一种界面语言的每一页都渲染一遍并断言、然后自己退出，退出码 0 才算通过；同时要求输出里不能出现 `SyntaxWarning` |
| Wayland-only | 关键一步：**抽掉** `DISPLAY`、只留 `WAYLAND_DISPLAY`，跑完整的 `totk-recomp-wrapper`，要求窗口能起、输出里没有 `no display name`/`TclError`。上一步显式设了 `DISPLAY=:99`，永远测不到这一场景 |

这几层覆盖了 Flatpak 封装最容易踩的坑：只读 `/app` 导致 Python 写不了 `__pycache__`、
Tcl/Tk 数据目录没设对、`libXft.so.2` 在沙箱里找不到、以及 sysroot 里缺链接期依赖。

## 为什么这样做（可行性依据）

封装前对 AppImage 0.3.13 做了实际拆包分析：

| 检查项 | 结果 | 影响 |
|---|---|---|
| 入口 | `AppRun` → 自带 `python/bin/python3 -m installer.gui` | 包装脚本只需准备环境变量后 `exec` |
| 资源定位 | `installer/layout.py` 相对「`installer/` 的上一级」查找 | release 树必须**原样**放在同一个父目录下 |
| `/app` 硬编码路径 | 无 | 只读 `/app` 不会造成写入失败 |
| 编译工具链 | `llvm/bin/{clang,lld,llvm-ar}`，RUNPATH `$ORIGIN/../lib` | 整棵 `llvm/` 保留即可，无需 patchelf |
| 链接期依赖 | 全部在 `llvm/sysroot` 内：`libc/libm/libdl/libpthread`(2.31)、`libvulkan.so`、`libSDL3.so`、`libopus.a`、`libvpx.a`；`libzstd.a` 在 `runtime/deps/lib` | 编译**不依赖宿主/沙箱的系统库**，产物也不依赖沙箱 |
| VMA / Vulkan 头 | `runtime/deps/include/{vulkan,vma}` 随包 | 不会触发上游「首次运行联网抓 `vk_mem_alloc.h`」的路径 |
| Python | python-build-standalone + numpy/lz4/cryptography/fontTools/cffi | 自足，无需沙箱 Python |
| Tk | `python/lib/libtcl9tk9.0.so` 需要 `libXft.so.2`、`libfontconfig.so.1`、`libfreetype.so.6`、`libX11.so.6`；前者的 `libXft.so.2`/`libXrender.so.1` **随包自带**，靠主程序 RPATH `$ORIGIN/../lib` 命中。**Tk 9 没有 Wayland 后端**，只能走 X11/XWayland | 其余由 freedesktop runtime 提供。清单里 x11 与 wayland 必须都无条件给出（不能只用 `fallback-x11`），否则 Wayland 会话下 `DISPLAY` 为空、Tk 启动失败 |
| glibc 需求 | `clang` 2.34、`totk_xlate` 2.29、`python3.14` 2.17 | Freedesktop 25.08 满足 |
| 配置路径 | 遵循 `XDG_STATE_HOME`（`$XDG_STATE_HOME/totk-recomp/setup.json`） | Flatpak 自动沙箱化到 `~/.var/app/` |
| 游戏文件是否内含 | 否 | 只有工具链、脚本与着色器列表 |
| 网络需求 | 仅 Windows 的 `--dlss`（下载 `nvngx_dlss.dll`） | Linux 构建路径全程离线；`--share=network` 仍开着，便于将来上游加检查更新 |
| 体积 | AppImage 230 MB，解包约 830 MB（`llvm/` 545 MB、`python/` 187 MB、`runtime/` 72 MB） | 全部是编译必需，不能裁 |

## 本仓库结构

```
io.github.jcleng.TotKRecomp.yaml          # Flatpak 清单（核心）
totk-recomp-wrapper                       # 启动包装脚本（环境兜底 + 固定 Tcl/Tk 路径）
io.github.jcleng.TotKRecomp.desktop       # 桌面入口
io.github.jcleng.TotKRecomp.metainfo.xml  # AppStream 元数据
icons/io.github.jcleng.TotKRecomp.png     # 图标（256x256，取自上游 totk-setup.png）
.github/workflows/build.yml               # GitHub Actions 构建 + 验证 + 自动 Release
```

## 本地构建（可选）

本仓库设计为**只在 GitHub Actions 上构建**；若确实需要本地验证，需要 `flatpak-builder` + `org.freedesktop.Sdk//25.08`：

```bash
git clone <this repo>
cd totk-recomp-flatpak
flatpak-builder --user --install --force-clean build-dir \
  io.github.jcleng.TotKRecomp.yaml
flatpak run io.github.jcleng.TotKRecomp
```

## 许可

- Flatpak 清单 / 包装脚本：MIT
- TotK Recomp 本体：MIT，见 [上游](https://github.com/valentderah/totk-pc-recomp)
  （内含 LLVM、Python、SDL3、libvpx、Opus、hactool 等第三方组件，各自遵循其许可证；
  完整清单见包内 `/app/share/totk-recomp/THIRD_PARTY_NOTICES.md`）
- 本项目与 Nintendo / valentderah 均无隶属关系
