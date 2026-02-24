"""
Build script for creating standalone RSAS executables.
Uses PyInstaller to package everything into a single distributable app.
"""

import PyInstaller.__main__
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
        '--collect-all=RnaThermofinder',
        '--collect-all=customtkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=IPython',
        '--exclude-module=pytest',
        '--exclude-module=jupyter',
    ]

    if system == "Darwin":
        print("Building for macOS...")
        options = base_options + [
            '--windowed',
            '--onedir',
            '--osx-bundle-identifier=com.royvaknin.rsas',
        ]
        output_msg = "open dist/RSAS.app"

    elif system == "Windows":
        print("Building for Windows...")
        options = base_options + [
            '--windowed',
            '--onefile',
        ]
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
        if system == "Darwin":
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
