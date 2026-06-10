# Third-party notices

RSAS is released under the MIT License (see `LICENSE.md`). It bundles and
depends on third-party tools that carry their own licenses. RSAS invokes the
bundled binaries as **separate executables** (via subprocess); they are
aggregated with RSAS, not linked into it, so each remains under its own license
and RSAS itself stays MIT.

Full license texts and per-component notices are in the [`LICENSES/`](LICENSES/)
directory (`GPL-3.0.txt` and `THIRD-PARTY-NOTICE.txt`), and ship inside the
packaged app's DMG.

## Bundled binaries (in `bin/`)

### RNArobo
- **Version:** 2.1.0 (September 2013)
- **License:** GNU General Public License v3.0 (`LICENSES/GPL-3.0.txt`).
  GPL-3.0 permits commercial and non-commercial use, modification, and
  redistribution, provided the license and copyright notices are preserved and
  the corresponding source remains available. RSAS redistributes it unmodified.
- **Source:** https://github.com/rampasek/RNArobo
- **Use in RSAS:** structural motif search (the RNArobo Search page).
- **Citation:** Rampášek, L., Jimenez, R.M., Lupták, A., Vinař, T., Brejová, B.
  (2016). RNA motif search with data-driven element ordering.
  *BMC Bioinformatics* 17:216.

### Knotty
- **License:** GNU General Public License (stated in the upstream README;
  copyright University of Alberta and the MultiRNAFold/SimFold authors).
  Redistributed unmodified.
- **Source:** https://github.com/HosnaJabbari/Knotty
- **Use in RSAS:** pseudoknot prediction (the Pseudoknot Finder page), using the
  DP09 energy model.
- **Citation:** Jabbari, H., Wark, I., Montemagno, C., Will, S. (2018). Knotty:
  efficient and accurate prediction of complex RNA pseudoknot structures.
  *Bioinformatics* 34(22):3849-3856.

### SimFold energy parameters (in `bin/macos/simfold/params/`)
- Knotty reads its thermodynamic parameters from SimFold / MultiRNAFold (Turner
  and Andronescu/Mathews parameter sets), which are part of MultiRNAFold and
  distributed under the same GPL terms as Knotty.
- **Source:** http://www.rnasoft.ca/download.html

## Bundled / runtime dependencies

### ViennaRNA
- RSAS performs all folding through ViennaRNA's Python bindings. The packaged
  macOS application bundles ViennaRNA; when running from source it is installed
  separately by the user.
- **Citation:** Lorenz, R. et al. (2011). ViennaRNA Package 2.0. *Algorithms for
  Molecular Biology* 6:26.
- **Project / license:** https://www.tbi.univie.ac.at/RNA/

### Other libraries
- Biopython, NumPy, openpyxl, CustomTkinter and Pillow are bundled in the
  packaged application, each under its own permissive open-source license.
