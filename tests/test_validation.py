import pytest

from dash_bucket_upload._validation import UploadValidationError, sanitize_filename, validate_upload
from dash_bucket_upload.manager import UploadConfig


def cfg(**kwargs):
    return UploadConfig(upload_id = 'default', bucket = 'b', **kwargs)


def test_sanitize_strips_paths():
    assert sanitize_filename('/etc/passwd') == 'passwd'
    assert sanitize_filename('..\\..\\evil.exe') == 'evil.exe'
    assert sanitize_filename('dir/sub/name.txt') == 'name.txt'


def test_sanitize_strips_control_chars():
    assert sanitize_filename('a\x00b\x1f.txt') == 'ab.txt'


@pytest.mark.parametrize('bad', ['', '.', '..', '///', '\x00', None, 42])
def test_sanitize_rejects_garbage(bad):
    with pytest.raises(UploadValidationError):
        sanitize_filename(bad)


def test_max_file_size_enforced():
    with pytest.raises(UploadValidationError) as exc:
        validate_upload(cfg(max_file_size = 100), 'a.bin', 101, None)
    assert exc.value.status == 413
    assert validate_upload(cfg(max_file_size = 100), 'a.bin', 100, None) == 'a.bin'


def test_size_must_be_non_negative_int():
    for bad in (-1, 'big', None, 1.5):
        with pytest.raises(UploadValidationError):
            validate_upload(cfg(), 'a.bin', bad, None)


def test_extension_allowlist():
    c = cfg(allowed_extensions = ['.csv', 'parquet'])
    assert validate_upload(c, 'x.CSV', 1, None) == 'x.CSV'
    assert validate_upload(c, 'x.parquet', 1, None) == 'x.parquet'
    with pytest.raises(UploadValidationError):
        validate_upload(c, 'x.exe', 1, None)
    with pytest.raises(UploadValidationError):
        validate_upload(c, 'noext', 1, None)


def test_mime_allowlist():
    c = cfg(allowed_mime_types = ['text/csv'])
    assert validate_upload(c, 'x.csv', 1, 'text/CSV') == 'x.csv'
    with pytest.raises(UploadValidationError):
        validate_upload(c, 'x.csv', 1, 'application/octet-stream')
    with pytest.raises(UploadValidationError):
        validate_upload(c, 'x.csv', 1, None)
