from app.licensing.license_manager import LicenseManager


def test_license_validation_is_disabled():
    result = LicenseManager().validate("")
    assert result.valid is True
    assert "removido" in result.message


def test_validate_simple_always_true():
    assert LicenseManager().validate_simple("") is True
    assert LicenseManager().validate_simple("ANY") is True


def test_hwid_is_local():
    assert LicenseManager().hwid == "LOCAL"

