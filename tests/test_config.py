from __future__ import annotations

import hashlib

from tests.helpers import make_config


def test_admin_content_password_is_verified_by_hash(tmp_path):
    config = make_config(tmp_path)
    digest = hashlib.sha256("secret".encode("utf-8")).hexdigest()
    config = config.__class__(**{**config.__dict__, "admin_content_password_sha256": digest})

    assert config.verify_admin_content_password("secret") is True
    assert config.verify_admin_content_password("wrong") is False
