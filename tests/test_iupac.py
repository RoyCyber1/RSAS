from RnaThermofinder.utils.motif_finder import iupac_to_regex


def test_literal_passthrough():
    assert iupac_to_regex("AUG") == "AUG"


def test_t_normalized_to_u():
    assert iupac_to_regex("ATG") == "AUG"


def test_degenerate_d_code():
    # D = A or G or U
    assert iupac_to_regex("D") == "[AGU]"


def test_dtg_matches_all_start_codons():
    import re
    rx = re.compile(iupac_to_regex("DTG"))
    assert rx.fullmatch("AUG")
    assert rx.fullmatch("GUG")
    assert rx.fullmatch("UUG")
    assert not rx.fullmatch("CUG")
