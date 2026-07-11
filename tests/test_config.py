from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.config import ConfigError, inspect_credentials, load_credentials, parse_dotenv, resolve_credentials


class ParseDotenvTests(unittest.TestCase):
    def test_parse_dotenv_ignores_comments_and_export(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            dotenv_path = Path(tmp_dir) / ".env"
            dotenv_path.write_text(
                "# comment\n"
                "export IMA_OPENAPI_CLIENTID=abc123\n"
                "IMA_OPENAPI_APIKEY='secret'\n",
                encoding="utf-8",
            )

            parsed = parse_dotenv(dotenv_path)

        self.assertEqual(parsed["IMA_OPENAPI_CLIENTID"], "abc123")
        self.assertEqual(parsed["IMA_OPENAPI_APIKEY"], "secret")


class LoadCredentialsTests(unittest.TestCase):
    def test_user_config_fallback_and_field_priority(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir); config = root / "user"; config.mkdir()
            (config / "client_id").write_text("user-client\n", encoding="utf-8")
            (config / "api_key").write_text("user-key\n", encoding="utf-8")
            (root / ".env").write_text("IMA_OPENAPI_APIKEY=dotenv-key\n", encoding="utf-8")
            result = resolve_credentials(root, env={}, config_dir=config).status
        self.assertEqual((result.client_id_source, result.api_key_source), ("user_config", "project_dotenv"))
        self.assertEqual((result.client_id, result.api_key), ("user-client", "dotenv-key"))

    def test_invalid_user_config_is_config_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir); config = root / "user"; config.mkdir()
            (config / "client_id").write_bytes(b"\xff")
            with self.assertRaises(ConfigError): resolve_credentials(root, env={}, config_dir=config)

    def test_inspect_credentials_reports_mixed_sources(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".env").write_text(
                "IMA_OPENAPI_CLIENTID=dotenv-client\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "IMA_OPENAPI_APIKEY": "env-key",
                },
                clear=True,
            ):
                status = inspect_credentials(root, config_dir=root / "user")

        self.assertTrue(status.client_id)
        self.assertTrue(status.api_key)
        self.assertEqual(status.client_id_source, "project_dotenv")
        self.assertEqual(status.api_key_source, "environment")

    def test_env_variables_override_dotenv(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".env").write_text(
                "IMA_OPENAPI_CLIENTID=dotenv-client\n"
                "IMA_OPENAPI_APIKEY=dotenv-key\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "IMA_OPENAPI_CLIENTID": "env-client",
                    "IMA_OPENAPI_APIKEY": "env-key",
                },
                clear=False,
            ):
                credentials = load_credentials(root, config_dir=root / "user")

        self.assertEqual(credentials.client_id, "env-client")
        self.assertEqual(credentials.api_key, "env-key")
        self.assertEqual(credentials.client_id_source, "environment")
        self.assertEqual(credentials.api_key_source, "environment")

    def test_loads_from_dotenv_when_environment_is_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".env").write_text(
                "IMA_OPENAPI_CLIENTID=dotenv-client\n"
                "IMA_OPENAPI_APIKEY=dotenv-key\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                credentials = load_credentials(root, config_dir=root / "user")

        self.assertEqual(credentials.client_id, "dotenv-client")
        self.assertEqual(credentials.api_key, "dotenv-key")
        self.assertEqual(credentials.client_id_source, "project_dotenv")
        self.assertEqual(credentials.api_key_source, "project_dotenv")

    def test_missing_credentials_raise_config_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ConfigError):
                    load_credentials(Path(tmp_dir), config_dir=Path(tmp_dir) / "user")
