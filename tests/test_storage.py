"""Tests for engine/storage.py — Cloudflare R2 upload helpers."""

import sys
from unittest.mock import MagicMock, patch

import pytest


# boto3 may not be installed in test environments — stub it in sys.modules
# so that the lazy import inside upload_to_r2() works.
_mock_boto3 = MagicMock()
_mock_botoconfig = MagicMock()


@pytest.fixture(autouse=True)
def _patch_boto3():
    """Ensure boto3 and botocore.config are available as mocks."""
    with patch.dict(sys.modules, {
        "boto3": _mock_boto3,
        "botocore": MagicMock(),
        "botocore.config": _mock_botoconfig,
    }):
        _mock_boto3.reset_mock()
        _mock_botoconfig.reset_mock()
        yield


from engine.storage import upload_to_r2, upload_episode


class TestUploadToR2:
    def test_upload_returns_public_url(self, tmp_path):
        mp3 = tmp_path / "episode.mp3"
        mp3.write_bytes(b"\x00" * 100)
        mock_s3 = MagicMock()
        _mock_boto3.client.return_value = mock_s3

        url = upload_to_r2(
            mp3, "tesla/episode.mp3",
            bucket="podcast-audio",
            endpoint_url="https://r2.example.com",
            access_key="key",
            secret_key="secret",
            public_base_url="https://audio.nerranetwork.com",
        )

        assert url == "https://audio.nerranetwork.com/tesla/episode.mp3"
        mock_s3.upload_file.assert_called_once_with(
            str(mp3), "podcast-audio", "tesla/episode.mp3",
            ExtraArgs={"ContentType": "audio/mpeg"},
        )

    def test_mp3_content_type(self, tmp_path):
        mp3 = tmp_path / "episode.mp3"
        mp3.write_bytes(b"\x00")
        mock_s3 = MagicMock()
        _mock_boto3.client.return_value = mock_s3

        upload_to_r2(
            mp3, "key.mp3",
            bucket="b", endpoint_url="https://r2.example.com",
            access_key="k", secret_key="s",
        )

        _, kwargs = mock_s3.upload_file.call_args
        assert kwargs["ExtraArgs"]["ContentType"] == "audio/mpeg"

    def test_non_mp3_content_type(self, tmp_path):
        txt = tmp_path / "data.json"
        txt.write_text("{}")
        mock_s3 = MagicMock()
        _mock_boto3.client.return_value = mock_s3

        upload_to_r2(
            txt, "data.json",
            bucket="b", endpoint_url="https://r2.example.com",
            access_key="k", secret_key="s",
        )

        _, kwargs = mock_s3.upload_file.call_args
        assert kwargs["ExtraArgs"]["ContentType"] == "application/octet-stream"

    def test_fallback_url_without_public_base(self, tmp_path):
        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"\x00")
        _mock_boto3.client.return_value = MagicMock()

        url = upload_to_r2(
            mp3, "tesla/ep.mp3",
            bucket="bucket",
            endpoint_url="https://r2.example.com",
            access_key="k", secret_key="s",
            public_base_url="",
        )

        assert url == "https://r2.example.com/bucket/tesla/ep.mp3"

    def test_boto_error_propagates(self, tmp_path):
        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"\x00")
        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = Exception("Connection reset")
        _mock_boto3.client.return_value = mock_s3

        with pytest.raises(Exception):
            upload_to_r2(
                mp3, "key.mp3",
                bucket="b", endpoint_url="https://r2.example.com",
                access_key="k", secret_key="s",
            )
        # Verify retry attempted 3 times
        assert mock_s3.upload_file.call_count == 3


class TestUploadEpisode:
    def test_no_storage_config_returns_none(self, tmp_path):
        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"\x00")
        config = MagicMock()
        config.storage = None

        assert upload_episode(mp3, config) is None

    def test_non_r2_provider_returns_none(self, tmp_path):
        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"\x00")
        config = MagicMock()
        config.storage.provider = "gcs"

        assert upload_episode(mp3, config) is None

    def test_missing_credentials_returns_none(self, tmp_path):
        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"\x00")
        config = MagicMock()
        config.storage.provider = "r2"
        config.storage.endpoint_env = "R2_ENDPOINT_URL"
        config.storage.access_key_env = "R2_ACCESS_KEY_ID"
        config.storage.secret_key_env = "R2_SECRET_ACCESS_KEY"

        with patch.dict("os.environ", {}, clear=True):
            assert upload_episode(mp3, config) is None

    def test_successful_upload(self, tmp_path):
        mp3 = tmp_path / "ep.mp3"
        mp3.write_bytes(b"\x00")
        config = MagicMock()
        config.storage.provider = "r2"
        config.storage.endpoint_env = "R2_ENDPOINT"
        config.storage.access_key_env = "R2_KEY"
        config.storage.secret_key_env = "R2_SECRET"
        config.storage.bucket = "audio"
        config.storage.public_base_url = "https://audio.example.com"
        config.slug = "tesla"
        _mock_boto3.client.return_value = MagicMock()

        env = {
            "R2_ENDPOINT": "https://r2.example.com",
            "R2_KEY": "access",
            "R2_SECRET": "secret",
        }
        with patch.dict("os.environ", env, clear=True):
            url = upload_episode(mp3, config)

        assert url == "https://audio.example.com/tesla/ep.mp3"


# ---------------------------------------------------------------------------
# Hardened error semantics added during P0/P1 cleanup
# ---------------------------------------------------------------------------

def test_upload_episode_returns_none_on_boto_exception(monkeypatch, tmp_path):
    """upload_episode() should swallow boto3 / network exceptions and
    return None, so run_show.py's "if r2_audio_url is None" branch
    fires correctly instead of getting an uncaught exception."""
    from types import SimpleNamespace

    from engine import storage

    f = tmp_path / "episode.mp3"
    f.write_bytes(b"\x00" * 16)

    # Provide a config whose env vars resolve to non-empty strings so
    # we get past the credential-skip path.
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://r2.example.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")

    cfg = SimpleNamespace(
        slug="testshow",
        storage=SimpleNamespace(
            provider="r2",
            bucket="podcast-audio",
            endpoint_env="R2_ENDPOINT_URL",
            access_key_env="R2_ACCESS_KEY_ID",
            secret_key_env="R2_SECRET_ACCESS_KEY",
            public_base_url="https://audio.example.com",
        ),
    )

    def _boom(*args, **kwargs):
        # Mimic a botocore.exceptions.ClientError surface — any
        # non-trivial exception class works.
        raise RuntimeError("boto3: credentials are bad")

    monkeypatch.setattr(storage, "upload_to_r2", _boom)
    result = storage.upload_episode(f, cfg)
    assert result is None
