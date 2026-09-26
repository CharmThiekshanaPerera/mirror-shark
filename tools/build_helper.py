"""Build the Android helper app (android-helper/) into assets/MirrorSharkHelper.apk with the SDK command-line tools.

Needs a JDK on PATH (or JAVA_HOME) and the Android SDK (ANDROID_HOME) with build-tools and a platform.
Run with the project's Python:  python tools/build_helper.py
"""
import glob
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "android-helper"
OUT = ROOT / "assets" / "MirrorSharkHelper.apk"
WORK = ROOT / "build" / "helper"
PLATFORM = "android-34"
ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def sdk_root() -> Path:
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(var):
            return Path(os.environ[var])
    return Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk"


def latest_build_tools(sdk: Path) -> Path:
    versions = sorted((p for p in (sdk / "build-tools").iterdir() if p.is_dir() and p.name[0].isdigit()),
                      key=lambda p: [int(x) for x in p.name.split("-")[0].split(".") if x.isdigit()])
    if not versions:
        sys.exit("No Android build-tools found in the SDK.")
    return versions[-1]


def java_tool(name: str) -> str:
    home = os.environ.get("JAVA_HOME")
    if home and (Path(home) / "bin" / f"{name}.exe").exists():
        return str(Path(home) / "bin" / name)
    found = shutil.which(name)
    if not found:
        sys.exit(f"{name} not found: install a JDK or set JAVA_HOME.")
    return found


def run(*cmd: str) -> None:
    print("  >", Path(cmd[0]).name, *[c for c in cmd[1:3]])
    r = subprocess.run(list(cmd), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")


def make_icons() -> None:
    from PySide6.QtGui import QGuiApplication
    sys.path.insert(0, str(ROOT))
    from mirrorshark.theme import make_pixmap
    app = QGuiApplication([])  # noqa: F841 - Qt needs it to paint pixmaps
    for density, px in ICON_SIZES.items():
        d = SRC / "res" / f"mipmap-{density}"
        d.mkdir(parents=True, exist_ok=True)
        make_pixmap(px).save(str(d / "ic_launcher.png"), "PNG")


def debug_keystore() -> Path:
    ks = Path.home() / ".android" / "debug.keystore"
    if not ks.exists():
        ks.parent.mkdir(parents=True, exist_ok=True)
        run(java_tool("keytool"), "-genkeypair", "-keystore", str(ks), "-storepass", "android", "-keypass", "android",
            "-alias", "androiddebugkey", "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
            "-dname", "CN=Android Debug,O=Android,C=US")
    return ks


def main() -> None:
    sdk = sdk_root()
    bt = latest_build_tools(sdk)
    android_jar = sdk / "platforms" / PLATFORM / "android.jar"
    if not android_jar.exists():
        sys.exit(f"Missing {android_jar} (install the {PLATFORM} platform in the SDK Manager).")
    aapt2, d8, zipalign, apksigner = (str(bt / n) for n in ("aapt2.exe", "d8.bat", "zipalign.exe", "apksigner.bat"))

    print(f"Building helper with build-tools {bt.name}")
    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "gen").mkdir(parents=True)
    (WORK / "classes").mkdir()
    (WORK / "dex").mkdir()
    make_icons()

    run(aapt2, "compile", "--dir", str(SRC / "res"), "-o", str(WORK / "res.zip"))
    run(aapt2, "link", "-I", str(android_jar), "--manifest", str(SRC / "AndroidManifest.xml"),
        "--java", str(WORK / "gen"), "--min-sdk-version", "30", "--target-sdk-version", "34",
        "-o", str(WORK / "base.apk"), str(WORK / "res.zip"))

    sources = glob.glob(str(SRC / "src" / "**" / "*.java"), recursive=True) + glob.glob(str(WORK / "gen" / "**" / "*.java"), recursive=True)
    run(java_tool("javac"), "--release", "11", "-Xlint:-options", "-cp", str(android_jar), "-d", str(WORK / "classes"), *sources)
    classes = glob.glob(str(WORK / "classes" / "**" / "*.class"), recursive=True)
    run(d8, "--lib", str(android_jar), "--release", "--min-api", "30", "--output", str(WORK / "dex"), *classes)

    unsigned = WORK / "unsigned.apk"
    shutil.copy(WORK / "base.apk", unsigned)
    with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(WORK / "dex" / "classes.dex", "classes.dex")
    aligned = WORK / "aligned.apk"
    run(zipalign, "-f", "-p", "4", str(unsigned), str(aligned))
    OUT.parent.mkdir(exist_ok=True)
    run(apksigner, "sign", "--ks", str(debug_keystore()), "--ks-pass", "pass:android", "--out", str(OUT), str(aligned))
    print(f"Built {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
