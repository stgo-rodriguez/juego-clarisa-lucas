"""Pruebas del guardarraíl de versiones antes de una futura adaptación v2.2."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simulador.versiones import (
    RulesetNotReady,
    get_version,
    require_implemented,
    run_versioned,
)
from laboratorio.simular_versionado import main


class VersionRegistryTests(unittest.TestCase):
    def test_v21_stays_available_without_relabeling(self):
        info = require_implemented("2.1")
        self.assertEqual(info.version, "2.1")
        self.assertEqual(info.engine_module, "simulador.reglas_v21")

    def test_v22_is_not_implemented_without_approved_rules(self):
        info = get_version("2.2")
        self.assertIsNone(info.specification)
        self.assertIsNone(info.engine_module)
        with self.assertRaisesRegex(RulesetNotReady, "v2.2"):
            require_implemented("2.2")

    def test_no_v21_simulation_runs_for_requested_v22(self):
        invocations = []
        with self.assertRaises(RulesetNotReady):
            run_versioned("2.2", lambda **kw: invocations.append(kw),
                          seeds=100, version_label="v2.2")
        self.assertEqual(invocations, [])

    def test_v21_dispatches_only_to_its_own_engine(self):
        seen = []
        output = run_versioned("2.1", lambda **kw: seen.append(kw) or {"ok": True},
                               seeds=1)
        self.assertEqual(output, {"ok": True})
        self.assertEqual(seen, [{"seeds": 1}])

    def test_cli_exits_before_writing_files_if_v22_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "simlog_v22"
            with self.assertRaises(SystemExit) as exc:
                main(["--version", "2.2", "--out", str(target),
                      "--semillas", "2"])
            self.assertEqual(exc.exception.code, 2)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
