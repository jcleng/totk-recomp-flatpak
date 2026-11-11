/* totk-cjk-path: let the TotK Recomp menu find a CJK font inside the Flatpak sandbox.
 *
 * Why this exists
 * ---------------
 * The in-game settings menu is Dear ImGui. Its text is a small Latin font (roboto) plus the
 * CJK glyphs merged in from a **system** font, so the menu can name each language in its own
 * script and draw the Simplified-Chinese menu text (runtime/ui/menu.cpp, fonts_up()):
 *
 *     if (!plat_font_path(lang, path, sizeof path) || !(data = plat_file_read(path, &size))) continue;
 *     ...
 *     fa->AddFontFromMemoryTTF(data, (int)size, 26.0f * scale, &mc, ranges);
 *
 * plat_font_path() (runtime/platform/linux.c:1254) has no environment variable and no config:
 * it stats five fixed absolute paths and returns the first that exists:
 *
 *     /usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc
 *     /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
 *     /usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc
 *     /usr/share/fonts/noto/NotoSansCJK-Regular.ttc
 *     /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc
 *
 * That is the layout of a normal distribution (and SteamOS). A Flatpak sandbox has none of
 * them: /usr is the runtime, which ships no CJK font, and the app may only write /app. The
 * host's fonts are mounted at /run/host/fonts, also not in the list. So every path misses,
 * plat_font_path() returns 0, the loop `continue`s, no CJK font is merged, and the Latin-only
 * atlas draws every Chinese character as '?'. The English text is unaffected, which is why
 * the bug looks like "the menu is in English with question marks".
 *
 * What this does
 * --------------
 * Redirect exactly those five paths to the font this Flatpak does ship
 * (/app/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc). The game stats for existence and then
 * opens the same string, so both stat() and open() are covered. Nothing else is touched: a
 * path is rewritten only when it matches one of the five entries byte for byte, so file
 * access anywhere else (game data, logs, shader cache, mods) behaves exactly as before.
 *
 * The shim is cheap on purpose: one strcmp against five literals, no allocation, and the
 * rewrite result is a compile-time constant string.
 *
 * Loaded by totk-play via LD_PRELOAD. Building it needs only a C compiler; the manifest
 * compiles it with the bundled clang at build time (see io.github.jcleng.TotKRecomp.yaml),
 * so the running system needs nothing extra.
 *
 * If this shim ever stops matching (upstream changes the path list), the symptom is the
 * original one: Chinese in the menu becomes '?'. totk-play therefore checks that the font it
 * redirects to is present and warns once when it is not.
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

/* Where this Flatpak keeps the CJK font (installed by the noto-cjk-font module). */
#define TOTK_CJK_FONT "/app/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"

/* The five paths runtime/platform/linux.c:1254 looks for, in its order. */
static const char *const kRedirect[] = {
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
};

/* The font path to use instead, or NULL when `path` is not one of the five. */
static const char *redirect(const char *path) {
    if (!path) return NULL;
    for (size_t i = 0; i < sizeof kRedirect / sizeof *kRedirect; i++)
        if (!strcmp(path, kRedirect[i])) return TOTK_CJK_FONT;
    return NULL;
}

#define REAL(name)                                          \
    static __typeof__(name) *real_##name;                   \
    if (!real_##name) real_##name = dlsym(RTLD_NEXT, #name)

int stat(const char *path, struct stat *buf) {
    REAL(stat);
    const char *p = redirect(path);
    return real_stat(p ? p : path, buf);
}

int stat64(const char *path, struct stat64 *buf) {
    REAL(stat64);
    const char *p = redirect(path);
    return real_stat64(p ? p : path, buf);
}

/* glibc < 2.33 exported stat as __xstat; the runtime is newer, but the game is compiled on
 * the user's machine, so keep both: whichever one the binary calls, the rewrite happens. */
int __xstat(int ver, const char *path, struct stat *buf) {
    REAL(__xstat);
    const char *p = redirect(path);
    return real___xstat(ver, p ? p : path, buf);
}

int __xstat64(int ver, const char *path, struct stat64 *buf) {
    REAL(__xstat64);
    const char *p = redirect(path);
    return real___xstat64(ver, p ? p : path, buf);
}

int open(const char *path, int flags, ...) {
    REAL(open);
    /* open() takes mode only with O_CREAT/O_TMPFILE; reading the vararg unconditionally is
     * undefined, so read it exactly when the call site passed one. */
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap;
        va_start(ap, flags);
        mode_t mode = va_arg(ap, mode_t);
        va_end(ap);
        const char *p = redirect(path);
        return real_open(p ? p : path, flags, mode);
    }
    const char *p = redirect(path);
    return real_open(p ? p : path, flags);
}

int open64(const char *path, int flags, ...) {
    REAL(open64);
    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap;
        va_start(ap, flags);
        mode_t mode = va_arg(ap, mode_t);
        va_end(ap);
        const char *p = redirect(path);
        return real_open64(p ? p : path, flags, mode);
    }
    const char *p = redirect(path);
    return real_open64(p ? p : path, flags);
}

/* fopen() is not used by plat_file_read(), but the check step and logging helpers may use it;
 * keep the mapping consistent so a future upstream switch to fopen() still finds the font. */
#include <stdio.h>
FILE *fopen(const char *path, const char *mode) {
    REAL(fopen);
    const char *p = redirect(path);
    return real_fopen(p ? p : path, mode);
}
