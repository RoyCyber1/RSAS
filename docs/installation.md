# Installation Guide

Step-by-step instructions for getting RSAS v3.2 running on your machine. There are two ways to use RSAS: download the pre-built app (no Python needed), or run from source.

---

## Option A: Pre-built app (recommended for most users)

1. Go to the [Releases page](https://github.com/RoyCyber1/RNAThermoFinder/releases)
2. Download the latest `.zip` for your platform
3. Unzip and run:
   - **macOS**: double-click `RSAS.app`. If macOS says the app is from an unidentified developer, right-click the app, click **Open**, then click **Open** again in the dialog
   - **Windows**: double-click `RSAS.exe`
   - **Linux**: run `./RSAS` from a terminal

The pre-built app bundles everything (Python, ViennaRNA bindings, dependencies), so there's nothing else to install.

---

## Option B: Run from source

### System requirements

| Requirement | Details |
|---|---|
| OS | macOS, Linux, or Windows |
| Python | 3.9 or higher (3.10+ recommended) |
| RAM | 4 GB minimum, 8+ GB for large batches or partition function |
| CPU | 2+ cores recommended (multiprocessing is optional) |
| ViennaRNA | Must be installed via system package manager (see below) |

### Step 1: Install Python

Make sure Python 3.9+ is available. Check with:

```bash
python3 --version
```

If you don't have it:
- **macOS**: `brew install python` or download from [python.org](https://www.python.org/downloads/)
- **Ubuntu/Debian**: `sudo apt-get install python3 python3-pip python3-venv`
- **Fedora**: `sudo dnf install python3 python3-pip`
- **Windows**: download from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH" during installation

### Step 2: Install ViennaRNA

ViennaRNA provides the RNA folding engine. It has to be installed through your system package manager — it's not available via pip.

**macOS (Homebrew):**
```bash
brew install viennarna
```

**Ubuntu / Debian:**
```bash
sudo apt-get update
sudo apt-get install viennarna
```
If `viennarna` isn't in your distro's repos, you may need the development package too:
```bash
sudo apt-get install libviennarna-dev
```

**Fedora / RHEL:**
```bash
sudo dnf install viennarna
```
Or:
```bash
sudo dnf install viennarna-devel
```

**Windows:**
Download prebuilt binaries from the [ViennaRNA website](https://www.tbi.univie.ac.at/RNA/). Follow their Windows installation instructions. Make sure the ViennaRNA libraries end up on your system PATH so Python can find the `RNA` module.

**Verify it works:**
```bash
python3 -c "import RNA; print('ViennaRNA version:', RNA.__version__)"
```

If this prints the version number, you're good. If you get `ModuleNotFoundError`, see Troubleshooting below.

### Step 3: Clone the repository

```bash
git clone https://github.com/RoyCyber1/RNAThermoFinder.git
cd RNAThermoFinder
```

If you're working from a fork, use your fork URL instead.

### Step 4: (Optional) Create a virtual environment

This keeps RSAS dependencies isolated from your system Python. If you use a virtual environment, create it **after** installing ViennaRNA so the environment can see the system library.

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

On some systems you may need to create the venv with access to system packages so it can find ViennaRNA:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
```

### Step 5: Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `openpyxl` | Excel (.xlsx) export |
| `numpy` | Partition function calculations |
| `customtkinter` | Modern GUI framework |
| `biopython` | NCBI sequence fetching in the upstream extractor |
| `setuptools` | Package management (build only) |
| `pyinstaller` | Standalone app builds (build only) |

### Step 6: Run RSAS

```bash
python main.py
```

The RSAS window should appear. Try loading one of the bundled sample files in `Examples/` (e.g. `Examples/Test_Thermo_RV.fasta`), click Analyze, and check that results appear in the log and in `Data/Outputs/`.

### Step 7: (Optional) Editable install

If you want to use RSAS as an importable Python package:

```bash
pip install -e .
```

This lets you do `from RnaThermofinder.core import HairpinAnalysis` from anywhere.

---

## Verifying the installation

Run these checks to make sure everything is wired up:

```bash
# Check ViennaRNA
python3 -c "import RNA; print('ViennaRNA OK')"

# Check all dependencies
python3 -c "import numpy; import openpyxl; import customtkinter; print('Dependencies OK')"

# Check the package itself
python3 -c "from RnaThermofinder.core import HairpinAnalysis; print('RSAS package OK')"

# Run the app
python main.py
```

---

## Building a standalone app

If you want to package RSAS into a distributable application:

```bash
pip install pyinstaller
python build_app.py
```

Or use the spec file directly:

```bash
pyinstaller RSAS.spec
```

Output location:
- **macOS**: `dist/RSAS.app` — compress to `.zip` for distribution
- **Windows**: `dist/RSAS.exe`
- **Linux**: `dist/RSAS`

The build takes a few minutes. The resulting app includes all Python dependencies and ViennaRNA bindings.

---

## Troubleshooting

### "No module named 'RNA'"

ViennaRNA isn't installed, or Python can't find it.

- Make sure you installed it via your system package manager (step 2), not pip
- On Linux, you may also need the `-dev` or `-devel` package
- Restart your terminal after installing
- If using a venv, recreate it with `--system-site-packages`:
  ```bash
  python3 -m venv --system-site-packages venv
  source venv/bin/activate
  ```

### "No module named 'numpy'" or other missing packages

Run `pip install -r requirements.txt` again. If you're using a venv, make sure it's activated first.

### ViennaRNA installed but wrong Python version finds it

If you have multiple Python versions, ViennaRNA may only be visible to one of them. Try:

```bash
python3.10 -c "import RNA"    # or whichever version you're using
```

If the version that works is different from the one you're running main.py with, switch to that Python version or use it to create your venv.

### Analysis is very slow

- Go to the **Performance** card in the Settings page and increase CPU cores (default is 1)
- Disable columns you don't need in **Output Columns** — especially partition function columns, which are the most expensive
- Use the **Hairpin Analysis** preset for faster screening runs

### Excel export missing or "openpyxl not installed"

```bash
pip install openpyxl
```

### GUI looks wrong or won't start

- Make sure `customtkinter` is installed: `pip install customtkinter`
- On Linux, you may need `python3-tk`: `sudo apt-get install python3-tk`
- Try running with a specific appearance mode: the app respects your OS dark/light setting

### PyCharm or VS Code doesn't recognize imports

- Set the project interpreter to the Python environment where you ran `pip install`
- Mark the project root as Sources Root in PyCharm (right-click the folder > Mark Directory as > Sources Root)
- In VS Code, set `"python.analysis.extraPaths": ["."]` in settings

---

## Updating

To update to the latest version:

```bash
cd RNAThermoFinder
git pull
pip install -r requirements.txt
```

Your settings (in `csv_output_settings.json`) are preserved across updates.

---

## Summary

1. Install **Python 3.9+**
2. Install **ViennaRNA** via system package manager
3. Clone the repo and `pip install -r requirements.txt`
4. Run `python main.py`
5. Check **Troubleshooting** if anything goes wrong

For how to use the app, see [Usage Guide](usage.md).
