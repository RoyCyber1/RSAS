# Third-party notices

RSAS itself is released under the MIT License (see `LICENSE.md`), and RSAS is
non-commercial academic software. It bundles and depends on third-party tools
that carry their own terms. Those terms govern those components, not RSAS's MIT
license. The components below are included or required for academic use; consult
each upstream project for its full license text and the conditions of use.

## Bundled binaries (in `bin/`)

### RNArobo
- **Version:** 2.1.0 (September 2013)
- **Upstream:** https://github.com/rampasek/RNArobo
- **Use in RSAS:** structural motif search (the RNArobo Search page).
- **Citation:** Rampášek, L., Jimenez, R.M., Lupták, A., Vinař, T., Brejová, B.
  (2016). RNA motif search with data-driven element ordering.
  *BMC Bioinformatics* 17:216.
- **Terms:** redistributed for academic/non-commercial use under the upstream
  project's terms. See the upstream repository for the full license.

### Knotty
- **Upstream:** https://github.com/HosnaJabbari/Knotty
- **Use in RSAS:** pseudoknot prediction (the Pseudoknot Finder page), using the
  DP09 energy model.
- **Citation:** Jabbari, H., Wark, I., Montemagno, C., Will, S. (2018). Knotty:
  efficient and accurate prediction of complex RNA pseudoknot structures.
  *Bioinformatics* 34(22):3849-3856.
- **Terms:** redistributed for academic/non-commercial use under the upstream
  project's terms. See the upstream repository for the full license.

### SimFold energy parameters (in `bin/macos/simfold/params/`)
- Knotty links the SimFold library and its thermodynamic parameter files
  (Turner and Andronescu/Mathews parameter sets).
- **Terms:** the parameter files carry their original academic-use terms from
  the SimFold / Mathews / Andronescu sources. See the Knotty and SimFold
  upstream projects.

## Runtime dependency (not bundled)

### ViennaRNA
- **Version used:** 2.7.2
- RSAS does all of its folding through ViennaRNA's Python bindings. ViennaRNA is
  installed separately by the user (it is not redistributed in this repository).
- **Citation:** Lorenz, R. et al. (2011). ViennaRNA Package 2.0. *Algorithms for
  Molecular Biology* 6:26.
- **Project / license:** https://www.tbi.univie.ac.at/RNA/

---

If you intend to use RSAS or any bundled component outside an academic,
non-commercial context, check each upstream project's license first; some of
the bundled tools are restricted to non-commercial use.
