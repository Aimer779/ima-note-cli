from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from ima_note_cli.config import ConfigError, inspect_credentials, load_credentials, parse_dotenv


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
                status = inspect_credentials(root)

        self.assertTrue(status.client_id)
        self.assertTrue(status.api_key)
        self.assertEqual(status.client_id_source, ".env")
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
                credentials = load_credentials(root)

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
                credentials = load_credentials(root)

        self.assertEqual(credentials.client_id, "dotenv-client")
        self.assertEqual(credentials.api_key, "dotenv-key")
        self.assertEqual(credentials.client_id_source, ".env")
        self.assertEqual(credentials.api_key_source, ".env")

    def test_missing_credentials_raise_config_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ConfigError):
                    load_credentials(Path(tmp_dir))
