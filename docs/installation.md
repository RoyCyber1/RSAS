# Installation guide

Getting RSAS v3.2 running. There are two routes: download the pre-built app and skip Python entirely, or run from source. Most people want the first one. If you plan to script the analysis or change the code, you want the second.

One thing up front, because it's the part that trips everyone up: RSAS folds RNA using ViennaRNA, and ViennaRNA does not install through pip. It's a system library you install separately. The pre-built app already includes it. If you run from source, Step 2 below is the one to get right.

---

## Option A: the pre-built app (easiest)

1. Go to the [Releases page](https://github.com/RoyCyber1/RNAThermoFinder/releases).
2. Download the latest `.zip` for your platform.
3. Unzip and run it:
   - **macOS**: double-click `RSAS.app`. The first time, macOS will say it can't verify the developer, that's expected, the app isn't notarized. Right-click it, choose **Open**, then **Open** again. Once is enough; it remembers after that.
   - **Windows**: double-click `RSAS.exe`.
   - **Linux**: run `./RSAS` from a terminal.

Everything is bundled, Python, the ViennaRNA bindings, all the dependencies, so there's nothing else to install.

---

## Option B: run from source

### What you need

| Requirement | Details |
|---|---|
| OS | macOS, Linux, or Windows |
| Python | 3.9 or higher (3.10+ recommended) |
| RAM | 4 GB minimum, 8+ GB for big batches or partition-function runs |
| CPU | 2+ cores recommended; multiprocessing is optional |
| ViennaRNA | Installed through your system package manager (see Step 2) |

### Step 1: Python

Check what you've got:

```bash
python3 --version
```

If you need it:
- **macOS**: `brew install python`, or grab it from [python.org](https://www.python.org/downloads/).
- **Ubuntu/Debian**: `sudo apt-get install python3 python3-pip python3-venv`
- **Fedora**: `sudo dnf install python3 python3-pip`
- **Windows**: download from [python.org](https://www.python.org/downloads/) and tick "Add Python to PATH" during setup. Don't skip that checkbox; it's the cause of half the "python isn't recognized" problems later.

### Step 2: ViennaRNA

This is the folding engine, and it has to come from your system package manager, not pip.

**macOS (Homebrew):**
```bash
brew install viennarna
```

**Ubuntu / Debian:**
```bash
sudo apt-get update
sudo apt-get install viennarna
```
If `viennarna` isn't in your distro's repos, you may also need the dev package:
```bash
sudo apt-get install libviennarna-dev
```

**Fedora / RHEL:**
```bash
sudo dnf install viennarna
# or, if that doesn't pull in the Python bindings:
sudo dnf install viennarna-devel
```

**Windows:** download the prebuilt binaries from the [ViennaRNA website](https://www.tbi.univie.ac.at/RNA/) and follow their Windows instructions. The thing to get right is that the ViennaRNA libraries end up on your PATH, so Python can find the `RNA` module.

Then confirm it actually worked:
```bash
python3 -c "import RNA; print('ViennaRNA version:', RNA.__version__)"
```

If that prints a version number, you're past the hard part. If it throws `ModuleNotFoundError`, jump to Troubleshooting, this is the most common snag and it's usually a quick fix.

### Step 3: clone the repo

```bash
git clone https://github.com/RoyCyber1/RNAThermoFinder.git
cd RNAThermoFinder
```

Working from a fork? Use your fork's URL instead.

### Step 4: a virtual environment (optional but recommended)

A venv keeps RSAS's dependencies off your system Python. If you use one, create it *after* installing ViennaRNA so it can see the system library.

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

On some systems the venv can't see ViennaRNA unless you let it reach system packages:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
```

If `import RNA` works outside a venv but breaks inside one, this flag is almost always why.

### Step 5: the Python dependencies

```bash
pip install -r requirements.txt
```

That pulls in:

| Package | What it's for |
|---|---|
| `openpyxl` | Excel (.xlsx) export |
| `numpy` | Partition-function math |
| `customtkinter` | The GUI |
| `biopython` | Fetching sequences from NCBI in the extractor |
| `setuptools` | Packaging (build only) |
| `pyinstaller` | Standalone app builds (build only) |

### Step 6: run it

```bash
python main.py
```

The window should open. To check it end to end, load `Examples/Test_Thermo_RV.fasta`, click Analyze, and confirm you see results in the log and in `Data/Outputs/`.

### Step 7: editable install (optional)

If you want to import RSAS as a package from anywhere:

```bash
pip install -e .
```

Now `from RnaThermofinder.core import HairpinAnalysis` works regardless of your working directory.

---

## Checking the install

Four quick commands that isolate each layer, so if something's wrong you know which one:

```bash
# ViennaRNA
python3 -c "import RNA; print('ViennaRNA OK')"

# The Python deps
python3 -c "import numpy; import openpyxl; import customtkinter; print('Dependencies OK')"

# The package itself
python3 -c "from RnaThermofinder.core import HairpinAnalysis; print('RSAS package OK')"

# The app
python main.py
```

---

## Building a standalone app

To package RSAS into something you can hand to someone who has none of this installed:

```bash
pip install pyinstaller
python build_app.py
```

Or run PyInstaller on the spec directly:

```bash
pyinstaller RSAS.spec
```

Output:
- **macOS**: `dist/RSAS.app` (zip it for distribution)
- **Windows**: `dist/RSAS.exe`
- **Linux**: `dist/RSAS`

It takes a few minutes, and the result bundles every dependency plus the ViennaRNA bindings.

---

## Troubleshooting

### "No module named 'RNA'"

ViennaRNA isn't installed, or Python can't see it. In order of likelihood:

- You installed it with pip instead of the system package manager. Redo Step 2.
- On Linux, you're missing the `-dev` / `-devel` package.
- You haven't restarted your terminal since installing.
- You're in a venv that can't reach system packages. Recreate it with `--system-site-packages`:
  ```bash
  python3 -m venv --system-site-packages venv
  source venv/bin/activate
  ```

### "No module named 'numpy'" (or another package)

Run `pip install -r requirements.txt` again, and if you're using a venv, make sure it's activated first. An inactive venv is the usual reason this comes back.

### ViennaRNA is installed but the wrong Python finds it

If you have several Python versions, ViennaRNA may only be visible to one of them. Check which:

```bash
python3.10 -c "import RNA"    # or whichever version
```

If the one that works isn't the one running `main.py`, switch to it, or use it to create your venv.

### The analysis is slow

- Open the **Performance** card and raise the CPU cores (it starts at 1).
- Disable columns you don't need in **Output Columns**, especially the partition-function ones, which dominate the runtime.
- Use the **Hairpin Analysis** preset for fast screening passes.

### Excel export missing, or "openpyxl not installed"

```bash
pip install openpyxl
```

### The GUI looks wrong or won't start

- Make sure `customtkinter` is installed: `pip install customtkinter`.
- On Linux you may need Tk itself: `sudo apt-get install python3-tk`.
- The app follows your OS dark/light setting, so if it looks off, check that first.

### PyCharm or VS Code doesn't recognize the imports

- Point the project interpreter at the Python environment where you ran `pip install`.
- In PyCharm, mark the project root as Sources Root (right-click the folder, Mark Directory as, Sources Root).
- In VS Code, set `"python.analysis.extraPaths": ["."]`.

---

## Updating

```bash
cd RNAThermoFinder
git pull
pip install -r requirements.txt
```

Your settings in `csv_output_settings.json` survive updates.

---

## The short version

1. Install **Python 3.9+**.
2. Install **ViennaRNA** through your system package manager.
3. Clone the repo and `pip install -r requirements.txt`.
4. Run `python main.py`.
5. If something breaks, it's almost always ViennaRNA, see Troubleshooting.

For how to actually use the app, head to the [Usage guide](usage.md).
