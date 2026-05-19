from settings_manager import SettingsManager


def test_default_settings_has_rbs_detection_block(tmp_path):
    sm = SettingsManager(str(tmp_path / "settings.json"))
    block = sm.settings.get("rbs_detection")
    assert block == {
        "anchor_pattern": "AUG",
        "anchor_match_side": "last",
        "min_spacing": 5,
        "max_spacing": 13,
    }


def test_old_settings_file_gets_rbs_block_merged(tmp_path):
    import json
    p = tmp_path / "settings.json"
    # an old settings file with no rbs_detection block
    p.write_text(json.dumps({"folding_temperatures": [25, 37, 42]}))
    sm = SettingsManager(str(p))
    assert "rbs_detection" in sm.settings
    assert sm.settings["rbs_detection"]["max_spacing"] == 13
