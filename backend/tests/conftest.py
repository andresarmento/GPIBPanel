import pytest


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    """Cada teste usa um banco novo numa pasta temporária, nunca o backend/data real."""
    monkeypatch.setenv("GPIBPANEL_DATA", str(tmp_path))
    return tmp_path
