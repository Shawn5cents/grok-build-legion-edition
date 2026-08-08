import importlib.util
import os
import stat
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import legion_common as common

AUTO_SPEC = importlib.util.spec_from_file_location(
    "auto_discover", TOOLS_DIR / "auto-discover.py"
)
assert AUTO_SPEC is not None and AUTO_SPEC.loader is not None
auto_discover = importlib.util.module_from_spec(AUTO_SPEC)
AUTO_SPEC.loader.exec_module(auto_discover)

MODE_SPEC = importlib.util.spec_from_file_location(
    "legion_mode", TOOLS_DIR / "legion-mode.py"
)
assert MODE_SPEC is not None and MODE_SPEC.loader is not None
legion_mode = importlib.util.module_from_spec(MODE_SPEC)
MODE_SPEC.loader.exec_module(legion_mode)


class LegionCommonTests(unittest.TestCase):
    def test_deepseek_route_defaults_to_direct(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                auto_discover.deepseek_endpoint(),
                "https://api.deepseek.com/v1",
            )

    def test_deepseek_route_can_use_cheapskate_default(self):
        with mock.patch.dict(os.environ, {"LEGION_USE_CHEAPSKATE": "1"}, clear=True):
            self.assertEqual(
                auto_discover.deepseek_endpoint(),
                "http://127.0.0.1:8787/deepseek/v1",
            )

    def test_deepseek_route_override_preserves_direct_bypass(self):
        with mock.patch.dict(
            os.environ,
            {"LEGION_DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1/"},
            clear=True,
        ):
            self.assertEqual(
                auto_discover.deepseek_endpoint(),
                "https://api.deepseek.com/v1",
            )

    def test_cheapskate_preset_keeps_openai_compatible_route_and_key(self):
        preset = common.bundled_presets_dir() / "legion-cheapskate-dag.toml"
        parsed = common.load_toml(preset)
        for model_id in ("deepseek-v4-pro", "deepseek-v4-flash"):
            entry = parsed["model"][model_id]
            self.assertEqual(
                entry["base_url"], "http://127.0.0.1:8787/deepseek/v1"
            )
            self.assertEqual(entry["env_key"], "DEEPSEEK_API_KEY")

    def test_grok_home_honors_runtime_override(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"GROK_HOME": directory}):
                self.assertEqual(common.grok_home(), Path(directory))

    def test_role_update_preserves_siblings_and_synchronizes_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                "[ui]\ntheme = \"dark\"\n\n"
                "[subagents]\nenabled = false\nmax_parallel = 2\n\n"
                "[subagents.models]\nplan = \"old-plan\"\n"
                "general-purpose = \"old-coder\"\ncustom = \"keep-me\"\n",
                encoding="utf-8",
            )
            common.write_subagent_models(
                {"architect": "new-plan", "implementor": "new-coder"},
                path,
            )
            with path.open("rb") as handle:
                parsed = tomllib.load(handle)
            self.assertEqual(parsed["ui"]["theme"], "dark")
            self.assertEqual(parsed["subagents"]["max_parallel"], 2)
            self.assertTrue(parsed["subagents"]["enabled"])
            models = parsed["subagents"]["models"]
            self.assertEqual(models["architect"], "new-plan")
            self.assertEqual(models["plan"], "new-plan")
            self.assertEqual(models["implementor"], "new-coder")
            self.assertEqual(models["general-purpose"], "new-coder")
            self.assertEqual(models["custom"], "keep-me")

    def test_parent_subagents_table_is_inserted_before_existing_child(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                "[subagents.models]\norchestrator = \"grok-4.5\"\n",
                encoding="utf-8",
            )
            common.write_subagent_models({}, path)
            with path.open("rb") as handle:
                parsed = tomllib.load(handle)
            self.assertTrue(parsed["subagents"]["enabled"])

    def test_apply_preset_merges_runtime_model_with_quoted_catalog_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            preset = root / "preset.toml"
            config.write_text("[ui]\ntheme = \"light\"\n", encoding="utf-8")
            preset.write_text(
                "[subagents.models]\n"
                "orchestrator = \"provider/model.one\"\n"
                "explore = \"provider/model.one\"\n"
                "architect = \"provider/model.one\"\n"
                "implementor = \"provider/model.one\"\n"
                "verifier = \"provider/model.one\"\n\n"
                "[model.\"provider/model.one\"]\n"
                "model = \"model.one\"\n"
                "base_url = \"https://example.test/v1\"\n"
                "env_key = \"EXAMPLE_API_KEY\"\n"
                "context_window = 123456\n\n"
                "[model.\"provider/model.one\".extra_headers]\n"
                "X-Example = \"enabled\"\n",
                encoding="utf-8",
            )
            common.apply_preset(preset, config)
            with config.open("rb") as handle:
                parsed = tomllib.load(handle)
            self.assertEqual(parsed["ui"]["theme"], "light")
            self.assertEqual(
                parsed["model"]["provider/model.one"]["model"],
                "model.one",
            )
            self.assertEqual(
                parsed["model"]["provider/model.one"]["extra_headers"]["X-Example"],
                "enabled",
            )

    def test_model_upsert_matches_equivalent_bare_and_quoted_table_names(self):
        content = (
            "[model.deepseek-v4-pro]\n"
            'model = "deepseek-v4-pro"\n'
            'base_url = "http://127.0.0.1:8787/deepseek/v1"\n'
            'api_key = "keep-private-key"\n'
        )
        updated = common.merge_model_entries(
            content,
            {
                "deepseek-v4-pro": {
                    "model": "deepseek-v4-pro",
                    "base_url": "https://api.deepseek.com/v1",
                }
            },
        )

        parsed = tomllib.loads(updated)
        route = parsed["model"]["deepseek-v4-pro"]
        self.assertEqual(route["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(route["api_key"], "keep-private-key")
        self.assertEqual(updated.count("[model."), 1)

    def test_selected_role_copies_known_runtime_route(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            presets = root / "presets"
            presets.mkdir()
            (presets / "provider.toml").write_text(
                "[subagents.models]\n"
                "orchestrator = \"provider/model\"\n\n"
                "[model.\"provider/model\"]\n"
                "model = \"raw-model\"\n"
                "base_url = \"https://example.test/v1\"\n"
                "env_key = \"EXAMPLE_API_KEY\"\n"
                "context_window = 123456\n",
                encoding="utf-8",
            )
            config = root / "config.toml"
            known = common.known_model_entries(presets)
            common.write_subagent_models({"explore": "provider/model"}, config)
            common.ensure_model_entries(
                ["provider/model"],
                config,
                entries=known,
            )
            with config.open("rb") as handle:
                parsed = tomllib.load(handle)
            self.assertEqual(
                parsed["model"]["provider/model"]["base_url"],
                "https://example.test/v1",
            )

    def test_selected_role_preserves_existing_runtime_override(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text(
                '[model."provider/model"]\n'
                'model = "raw-model"\n'
                'base_url = "https://private-gateway.test/v1"\n'
                'api_key = "private-key"\n'
                "context_window = 64000\n",
                encoding="utf-8",
            )
            common.ensure_model_entries(
                ["provider/model"],
                config,
                entries={
                    "provider/model": {
                        "model": "raw-model",
                        "base_url": "https://public-provider.test/v1",
                        "env_key": "PROVIDER_API_KEY",
                        "context_window": 128000,
                    }
                },
            )
            with config.open("rb") as handle:
                route = tomllib.load(handle)["model"]["provider/model"]
            self.assertEqual(
                route["base_url"],
                "https://private-gateway.test/v1",
            )
            self.assertEqual(route["api_key"], "private-key")

    def test_atomic_write_uses_private_mode_for_new_config(self):
        if os.name == "nt":
            self.skipTest("POSIX permission assertion")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            common.atomic_write(path, "[ui]\ntheme = \"dark\"\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_malformed_config_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            malformed = "this is [not toml\n"
            path.write_text(malformed, encoding="utf-8")
            with self.assertRaises(ValueError):
                common.write_subagent_models({"architect": "model"}, path)
            self.assertEqual(path.read_text(encoding="utf-8"), malformed)

    def test_dag_preset_accepts_natural_short_name(self):
        def resolve(name):
            return Path(f"/presets/{name}.toml") if name == "vendor-dag" else None

        with mock.patch.object(legion_mode.common, "resolve_preset", side_effect=resolve):
            self.assertEqual(legion_mode.resolve_mode("vendor"), "vendor-dag")


if __name__ == "__main__":
    unittest.main()
