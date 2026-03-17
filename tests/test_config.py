from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from ima_note_cli.config import ConfigError, load_credentials, parse_dotenv


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

    def test_missing_credentials_raise_config_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ConfigError):
                    load_credentials(Path(tmp_dir))
