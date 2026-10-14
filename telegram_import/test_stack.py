from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts import ai_stack


class StackSwitchTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = self.root / ".env"
        self.env.write_text("OPENAI_API_KEY=preserved-test-key\nTELEGRAM_API_ID=1\nTELEGRAM_API_HASH=test\nTELEGRAM_GROUP=@loads\nTELEGRAM_AI_PROVIDER=openai\n")
        self.root_patch = patch.object(ai_stack, "ROOT", self.root)
        self.env_patch = patch.object(ai_stack, "ENV_FILE", self.env)
        self.root_patch.start()
        self.env_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.env_patch.stop)

    @patch("scripts.ai_stack.subprocess.run")
    def test_ollama_switch_stops_old_worker_before_new_worker(self, runner):
        ai_stack.start_stack("build", "ollama")
        commands = [call.args[0][2:] for call in runner.call_args_list]
        stop = commands.index(["stop", "telegram_importer"])
        start = commands.index(["--profile", "telegram", "up", "-d", "--no-deps", "--force-recreate", "telegram_importer"])
        self.assertLess(stop, start)
        self.assertEqual(commands.count(["--profile", "telegram", "up", "-d", "--no-deps", "--force-recreate", "telegram_importer"]), 1)
        self.assertIn("TELEGRAM_AI_PROVIDER=ollama", self.env.read_text())
        self.assertIn("OPENAI_API_KEY=preserved-test-key", self.env.read_text())
        self.assertTrue(all(call.kwargs["env"]["TELEGRAM_AI_PROVIDER"] == "ollama" for call in runner.call_args_list))

    @patch("scripts.ai_stack.subprocess.run")
    def test_openai_switch_stops_ollama_service(self, runner):
        ai_stack.start_stack("build", "openai")
        commands = [call.args[0][2:] for call in runner.call_args_list]
        self.assertIn(["--profile", "ollama", "stop", "ollama"], commands)
        self.assertFalse(any("pull" in command for command in commands))

    @patch("scripts.ai_stack.subprocess.run")
    def test_provider_check_failure_keeps_previous_selection_and_worker(self, runner):
        def fail_check(command, **kwargs):
            if "check_ai_provider" in command:
                raise subprocess.CalledProcessError(1, command)

        runner.side_effect = fail_check
        with self.assertRaises(subprocess.CalledProcessError):
            ai_stack.start_stack("build", "ollama")
        self.assertIn("TELEGRAM_AI_PROVIDER=openai", self.env.read_text())
        self.assertFalse(any(call.args[0][2:] == ["stop", "telegram_importer"] for call in runner.call_args_list))
