"""Offline regression checks using this fork's real config implementation."""
import argparse
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load("profile_config_test", ROOT / "bittensor/config.py").config
        cls.stub = types.ModuleType("bittensor")
        cls.stub.config = cls.config
        cls.stub.subtensor = MagicMock()
        cls.stub.wallet = MagicMock()
        cls.stub.__networks__ = ["finney", "test"]
        cls.stub.__finney_entrypoint__ = "wss://entrypoint-finney.opentensor.ai:443"
        cls.stub.__console__ = MagicMock()
        cls.commands = types.ModuleType("bittensor.commands")
        cls.commands.defaults = types.SimpleNamespace(profile=types.SimpleNamespace(name="default", path="~/.bittensor/profiles/"))
        cls.modules = patch.dict(sys.modules, {"bittensor": cls.stub, "bittensor.commands": cls.commands})
        cls.modules.start()
        cls.module = load("bittensor.commands.profile", ROOT / "bittensor/commands/profile.py")

    @classmethod
    def tearDownClass(cls):
        cls.modules.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        cfg = self.config()
        cfg.profile = self.config()
        cfg.profile.name, cfg.profile.path, cfg.profile.overwrite = "alice", self.temp.name, False
        cfg.subtensor = self.config()
        cfg.subtensor.network, cfg.subtensor.chain_endpoint = "finney", "wss://example.invalid"
        cfg.wallet = self.config()
        cfg.wallet.name, cfg.wallet.hotkey, cfg.wallet.path = "default", "hot", "~/.bittensor/wallets"
        cfg.netuid, cfg.no_prompt = 7, True
        cfg.private_key = "must-never-be-serialized"
        self.cli = types.SimpleNamespace(config=cfg)
        self.stub.__console__.reset_mock()
        self.stub.subtensor.reset_mock()

    def create(self):
        self.module.ProfileCommand.run(self.cli)
        return Path(self.temp.name) / "alice"

    def test_offline_round_trip_without_trailing_slash(self):
        path = self.create()
        contents = yaml.safe_load(path.read_text())
        self.assertEqual(contents["netuid"], 7)
        self.assertEqual(contents["profile"]["name"], "alice")
        self.assertNotIn("private_key", contents)
        self.stub.subtensor.assert_not_called()
        self.module.ProfileListCommand.run(self.cli)
        self.module.ProfileShowCommand.run(self.cli)
        self.assertEqual(len(self.stub.__console__.print.call_args_list), 3)

    def test_no_prompt_does_not_silently_overwrite(self):
        path = self.create()
        original = path.read_bytes()
        self.cli.config.netuid = 9
        self.create()
        self.assertEqual(path.read_bytes(), original)
        self.cli.config.profile.overwrite = True
        self.create()
        self.assertEqual(yaml.safe_load(path.read_text())["netuid"], 9)

    def test_atomic_write_failure_preserves_previous_profile(self):
        path = self.create()
        original = path.read_bytes()
        self.cli.config.profile.overwrite = True
        with patch.object(self.module.os, "replace", side_effect=OSError("fixture failure")):
            self.create()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [path])

    def test_traversal_and_symlink_refused(self):
        for name in ("../escape", "/absolute", ".", "bad/name"):
            self.cli.config.profile.name = name
            self.module.ProfileCommand.run(self.cli)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        target = Path(self.temp.name) / "target"
        target.write_text("unchanged")
        (Path(self.temp.name) / "alice").symlink_to(target)
        self.cli.config.profile.name = "alice"
        self.create()
        self.assertEqual(target.read_text(), "unchanged")

    def test_invalid_netuid_refused(self):
        for value in (-1, "abc"):
            self.cli.config.netuid = value
            self.create()
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_malformed_or_missing_show_is_graceful(self):
        path = Path(self.temp.name) / "alice"
        for text in ("- list\n", "[invalid"):
            path.write_text(text)
            self.module.ProfileShowCommand.run(self.cli)
        path.unlink()
        self.module.ProfileShowCommand.run(self.cli)

    def test_create_parser_has_netuid_and_overwrite(self):
        parser = argparse.ArgumentParser()
        self.module.ProfileCommand.add_args(parser.add_subparsers())
        parsed = parser.parse_args(["create", "--netuid", "4", "--profile.overwrite"])
        self.assertEqual(parsed.netuid, 4)
        self.assertTrue(vars(parsed)["profile.overwrite"])

    def test_interactive_endpoint_uses_value_equality(self):
        self.cli.config.no_prompt = False
        self.cli.config.subtensor.chain_endpoint = "".join(["wss://entrypoint-", "finney.opentensor.ai:443"])
        self.stub.subtensor.determine_chain_endpoint_and_network.return_value = ("test", "wss://test.invalid")
        values = ["alice", "test", "wss://test.invalid", "default", "hot", "~/.bittensor/wallets", "3"]
        with patch.object(self.module.Prompt, "ask", side_effect=values):
            self.create()
        self.stub.subtensor.determine_chain_endpoint_and_network.assert_called_once_with("test")
        self.assertEqual(yaml.safe_load((Path(self.temp.name) / "alice").read_text())["netuid"], 3)


if __name__ == "__main__":
    unittest.main()
