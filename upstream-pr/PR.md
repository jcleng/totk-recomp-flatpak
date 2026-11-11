# Ask fontconfig for the menu's CJK font instead of hard-coding five paths

## Problem

`plat_font_path()` (`runtime/platform/linux.c`) returns the first of five hard-coded paths that exists:

```c
static const char *files[] = {
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
};
```

There is no environment variable or config to override it. `fonts_up()` in `runtime/ui/menu.cpp` merges whatever it
finds into the atlas, so when all five miss, `merged` is 0 and every Chinese character in the settings menu renders as
`?` — English (`amiibo`, `Discord Rich Presence`, the version string) stays correct, which makes it read as
"English menu, question marks for Chinese".

This is not a corner case. **Any sandboxed build hits it.** Under Flatpak, `/usr` is the runtime and carries no CJK
font, the app may only write `/app`, and the host's fonts appear at `/run/host/fonts`. The same applies to Snap and,
depending on how the AppImage is run, to an AppImage too.

It is also invisible to the checks one would naturally make. On a NixOS host, `fc-list | grep -ci cjk` counts 105 face
names through `/run/host/fonts` and the Tk setup window is perfectly readable, yet the in-game menu is still all `?`,
because `plat_font_path` never asks fontconfig. The font file existing, `fc-list` finding the codepoint, `fc-match`
resolving to the SC face and `font.measure()` returning a non-zero width all pass with the bug present.

## Fix

Ask fontconfig, which is the same database Tk/Xft and every other Linux toolkit reads. It knows `/app/share/fonts`,
the XDG data dirs, `/run/host/fonts` and the per-user directories, so installing the font where the system looks is
enough and no packaging can leave the menu stranded.

Three points worth reviewing:

1. **`libfontconfig` is `dlopen`'d, not linked.** A host without it (headless, a bare container) still builds and runs
   and simply takes the fallback, so this adds no build dependency. The runtime already links `-ldl` for the NVIDIA
   libraries.
2. **The match is checked against the character before it is used.** fontconfig returns the closest pattern even when
   nothing covers a character, so without this a Latin-only system hands back DejaVu Sans and the menu believes it
   merged glyphs when it did not. One representative character per language (日 한 设 設) is what the charset test
   asks for.
3. **The old paths stay**, after fontconfig, for a system with no fontconfig, and `TOTK_MENU_FONT` overrides both for
   a font in an unusual place.

The pattern names `zh-cn`/`zh-tw` rather than `zh-hans`/`zh-hant`: that is how Noto CJK and fontconfig tag the faces,
and a pattern naming only `zh-hans` does not reach Noto Sans CJK SC.

## Testing

Built the function against the real fontconfig on Arch, and drove it through six cases:

| Case | Expected | Result |
|---|---|---|
| Host with no CJK font | no match, fall through to the five paths | `MISS` x5, no crash |
| fontconfig pointed at a directory holding only `NotoSansCJK-Regular.ttc` (the Flatpak case) | resolved | all four CJK languages resolve to that file |
| Same, `TOTK_MENU_FONT` set | override wins | resolved via the variable |
| `TOTK_MENU_FONT` naming a file that does not exist | ignored, fall through | `MISS`, no crash |
| `libfontconfig` made unloadable | silent fallback | `MISS` x5, exit 0 |
| `en` | no CJK font wanted | `MISS`, as before |

Also compiled with `-Wall -Wextra` — no warnings from the new code. `platform.h`'s contract is unchanged (same
signature, same semantics), so nothing else needs touching.

With this, a Flatpak that ships `NotoSansCJK-Regular.ttc` in `/app/share/fonts` gets `language names from 4 of 4
system fonts` with no shim, no patched binary and no extra configuration, and SteamOS and the distributions keep
working through the same call as before.

## What this does not do

Windows keeps its hard-coded `C:\Windows\Fonts\*` list (`win32.c`), which is fine: the file names there are fixed by
the OS. macOS has no `plat_font_path` yet.
