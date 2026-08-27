"""
Unit tests for app.api.documents._safe_output_path — the fix for a
path-traversal vulnerability found during a security review: `base_name`
path parameters on /api/documents/{base_name}/... endpoints were joined
into a filesystem path with a raw f-string and never validated, so a
base_name like "../../../etc/passwd" (or its Windows equivalent) could
escape OUTPUT_DIR.
"""

import pytest
from fastapi import HTTPException

from app.api.documents import _safe_output_path
from app import config


def test_normal_filename_resolves_inside_output_dir():
    from pathlib import Path
    path = _safe_output_path("some-estimation-id_data.json")
    out_dir = Path(config.OUTPUT_DIR).resolve()
    assert path.parent == out_dir


@pytest.mark.parametrize("malicious", [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\win.ini",
    "../../../../../../etc/shadow",
])
def test_path_traversal_sequences_rejected(malicious):
    with pytest.raises(HTTPException) as exc_info:
        _safe_output_path(f"{malicious}_data.json")
    assert exc_info.value.status_code == 400


def test_url_encoded_traversal_is_decoded_before_reaching_this_function():
    # FastAPI/Starlette URL-decodes path parameters before the route handler
    # (and thus _safe_output_path) ever sees them, so "..%2f" arrives here
    # as the literal 3-character string "..%2f" with no real path separator
    # — it's inert at this layer. This test documents that boundary rather
    # than asserting a specific outcome either way is "the fix": the actual
    # decoding happens upstream in Starlette, not in this function.
    from pathlib import Path
    path = _safe_output_path("..%2f..%2f..%2fetc%2fpasswd_data.json")
    out_dir = Path(config.OUTPUT_DIR).resolve()
    assert path.parent == out_dir


def test_absolute_path_injection_rejected():
    # An absolute path as the "filename" would otherwise make `out_dir / filename`
    # discard out_dir entirely (pathlib's `/` operator honors an absolute RHS).
    with pytest.raises(HTTPException) as exc_info:
        _safe_output_path("/etc/passwd")
    assert exc_info.value.status_code == 400


def test_legitimate_looking_but_escaping_name_rejected():
    with pytest.raises(HTTPException):
        _safe_output_path("normal_name/../../../secrets_data.json")
