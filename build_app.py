"""
Build script for creating standalone RSAS executables.
Uses PyInstaller to package everything into a single distributable app.
"""

import PyInstaller.__main__
import subprocess
import sys
import platform
import os


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
                    ["codesign", "--force", "--deep", "--sign", "-", app_path],
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
            print("To distribute: compress it to a .zip file")
        elif system == "Windows":
            print("Your .exe is in: dist/RSAS.exe")
        else:
            print("Your executable is in: dist/RSAS")
    except Exception as e:
        print(f"\nBuild failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build_app()
