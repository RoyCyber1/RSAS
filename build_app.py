"""
Build script for creating standalone RSAS executables.
Uses PyInstaller to package everything into a single distributable app.
"""

import PyInstaller.__main__
import subprocess
import sys
import platform
import os
import shutil
import tempfile


def _create_macos_dmg(app_path):
    """
    Package the codesigned .app into a distributable DMG.

    The DMG contains:
      - RSAS.app
      - Install RSAS.sh  (strips macOS quarantine and copies to /Applications)
      - README.txt        (plain-text fallback instructions)
      - Applications/     (symlink so users can drag-install manually)

    When a user downloads the DMG, macOS quarantines it. The install script
    strips that quarantine flag after copying the app to /Applications, which
    is the root cause of the misleading "app is damaged" Gatekeeper error.
    """
    print("\nCreating distributable DMG...")
    staging = tempfile.mkdtemp(prefix="rsas_dmg_")
    try:
        # Copy codesigned app into staging area
        staged_app = os.path.join(staging, "RSAS.app")
        shutil.copytree(app_path, staged_app)

        # Symlink to /Applications for drag-install convenience
        os.symlink("/Applications", os.path.join(staging, "Applications"))

        # Install script — copies app and strips quarantine automatically
        install_script = os.path.join(staging, "Install RSAS.sh")
        with open(install_script, "w") as f:
            f.write(
                '#!/bin/bash\n'
                '# RSAS First-Time Installer\n'
                '# Copies RSAS.app to /Applications and removes the macOS quarantine\n'
                '# flag that causes the misleading "app is damaged" error.\n'
                '\n'
                'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
                'APP_SRC="$SCRIPT_DIR/RSAS.app"\n'
                'APP_DEST="/Applications/RSAS.app"\n'
                '\n'
                'echo "=============================="\n'
                'echo "  RSAS Installer"\n'
                'echo "=============================="\n'
                '\n'
                'if [ ! -d "$APP_SRC" ]; then\n'
                '    echo "Error: RSAS.app not found. Run this script from inside the DMG."\n'
                '    exit 1\n'
                'fi\n'
                '\n'
                'echo "Copying RSAS.app to /Applications..."\n'
                'cp -r "$APP_SRC" "$APP_DEST"\n'
                '\n'
                'echo "Removing macOS quarantine flag..."\n'
                'xattr -cr "$APP_DEST"\n'
                '\n'
                'echo "Done! Launching RSAS..."\n'
                'open "$APP_DEST"\n'
            )
        os.chmod(install_script, 0o755)

        # README with plain-text fallback instructions
        readme = os.path.join(staging, "README.txt")
        with open(readme, "w") as f:
            f.write(
                "RSAS — RNA Structure Analysis Suite v3.2\n"
                "=========================================\n\n"
                "QUICK INSTALL\n"
                "  Double-click 'Install RSAS.sh' to install automatically.\n\n"
                "MANUAL INSTALL\n"
                "  Drag RSAS.app into the Applications folder shown in this window.\n\n"
                "IF MACOS SAYS 'APP IS DAMAGED'\n"
                "  This is a macOS security warning, not actual damage.\n"
                "  Fix it by opening Terminal and running:\n\n"
                "      xattr -cr /Applications/RSAS.app\n\n"
                "  Then double-click RSAS from your Applications folder normally.\n\n"
                "SUPPORT\n"
                "  https://github.com/RoyCyber1/RNAThermoFinder\n"
            )

        # Build DMG
        dmg_out = os.path.join("dist", "RSAS_macOS.dmg")
        result = subprocess.run(
            [
                "hdiutil", "create",
                "-volname", "RSAS",
                "-srcfolder", staging,
                "-ov",
                "-format", "UDZO",
                dmg_out,
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"DMG created: {dmg_out}")
            print("Distribute this DMG — users run 'Install RSAS.sh' inside it.")
        else:
            print(f"Warning: DMG creation failed: {result.stderr.strip()}")
            print("Falling back: compress dist/RSAS.app manually as a .zip")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def build_app():
    system = platform.system()

    # Find entry point
    if os.path.exists('main.py'):
        main_script = 'main.py'
    elif os.path.exists('RnaThermofinder/main.py'):
        main_script = 'RnaThermofinder/main.py'
    else:
        print("Error: Cannot find main.py")
        sys.exit(1)

    print(f"Entry point: {main_script}")

    # Check for app icon
    icon_mac = 'icon.icns' if os.path.exists('icon.icns') else None
    icon_win = 'icon.ico' if os.path.exists('icon.ico') else None

    base_options = [
        main_script,
        '--name=RSAS',
        '--clean',
        '--noconfirm',
        '--hidden-import=RNA',
        '--hidden-import=tkinter',
        '--hidden-import=customtkinter',
        '--hidden-import=numpy',
        '--hidden-import=Bio',
        '--hidden-import=PIL',
        '--hidden-import=openpyxl',
        '--collect-all=RNA',
        '--collect-all=RnaThermofinder',
        '--collect-all=customtkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=IPython',
        '--exclude-module=pytest',
        '--exclude-module=jupyter',
    ]

    # Bundle rnarobo binary if available
    rnarobo_bin = None
    platform_dirs = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
    bin_name = "rnarobo.exe" if system == "Windows" else "rnarobo"
    candidate = os.path.join("bin", platform_dirs.get(system, "linux"), bin_name)
    if os.path.isfile(candidate):
        rnarobo_bin = candidate
        base_options.append(f'--add-binary={candidate}{os.pathsep}bin')
        print(f"Bundling rnarobo binary: {candidate}")
    else:
        print(f"Note: rnarobo binary not found at {candidate} — RNArobo search will be unavailable in the build")

    # Bundle knotty binary if available
    knotty_name = "knotty.exe" if system == "Windows" else "knotty"
    knotty_candidate = os.path.join("bin", platform_dirs.get(system, "linux"), knotty_name)
    if os.path.isfile(knotty_candidate):
        base_options.append(f'--add-binary={knotty_candidate}{os.pathsep}bin')
        print(f"Bundling knotty binary: {knotty_candidate}")
        # Bundle Knotty energy parameter files (simfold/params/)
        knotty_params = os.path.join(os.path.dirname(knotty_candidate), "simfold", "params")
        if os.path.isdir(knotty_params):
            base_options.append(f'--add-data={knotty_params}{os.pathsep}bin/simfold/params')
            print(f"Bundling knotty params: {knotty_params}")
        else:
            print(f"Warning: knotty params not found at {knotty_params} — Knotty will fail at runtime")
    else:
        print(f"Note: knotty binary not found at {knotty_candidate} — Pseudoknot Finder will be unavailable in the build")

    if system == "Darwin":
        print("Building for macOS...")
        options = base_options + [
            '--windowed',
            '--onedir',
            '--osx-bundle-identifier=com.royvaknin.rsas',
        ]
        if icon_mac:
            options.append(f'--icon={icon_mac}')
            print(f"Using icon: {icon_mac}")
        output_msg = "open dist/RSAS.app"

    elif system == "Windows":
        print("Building for Windows...")
        options = base_options + [
            '--windowed',
            '--onefile',
        ]
        if icon_win:
            options.append(f'--icon={icon_win}')
            print(f"Using icon: {icon_win}")
        output_msg = "dist\\RSAS.exe"

    else:
        print("Building for Linux...")
        options = base_options + [
            '--onefile',
        ]
        output_msg = "./dist/RSAS"

    print("This may take several minutes...")

    try:
        PyInstaller.__main__.run(options)
        print(f"\nBuild complete! To run: {output_msg}")

        # macOS: ad-hoc codesign to prevent "damaged app" errors
        if system == "Darwin":
            app_path = os.path.join("dist", "RSAS.app")
            if os.path.isdir(app_path):
                print("Signing app with ad-hoc identity...")
                subprocess.run(["xattr", "-cr", app_path], check=False)
                sign = subprocess.run(
                    ["codesign", "--force", "--sign", "-", app_path],
                    capture_output=True, text=True,
                )
                if sign.returncode == 0:
                    print("Ad-hoc codesign successful.")
                else:
                    print(f"Warning: codesign failed: {sign.stderr.strip()}")

                verify = subprocess.run(
                    ["codesign", "--verify", "--verbose", app_path],
                    capture_output=True, text=True,
                )
                if verify.returncode == 0:
                    print("Signature verified OK.")
                else:
                    print(f"Warning: verification failed: {verify.stderr.strip()}")

            print("Your .app is in: dist/RSAS.app")
            _create_macos_dmg(app_path)
        elif system == "Windows":
            print("Your .exe is in: dist/RSAS.exe")
        else:
            print("Your executable is in: dist/RSAS")
    except Exception as e:
        print(f"\nBuild failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build_app()
