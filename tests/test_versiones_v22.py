"""Pruebas de aislamiento de versiones tras la adaptación funcional v2.2."""
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

    def test_v22_is_distinct_implemented_version(self):
        info = require_implemented("2.2")
        self.assertIn('v2_2', info.specification)
        self.assertEqual(info.engine_module, 'simulador.reglas_v22')

    def test_v22_dispatches_explicitly(self):
        seen = []
        result = run_versioned("2.2", lambda **kw: seen.append(kw) or 'v22',
                               seeds=101)
        self.assertEqual(result, 'v22')
        self.assertEqual(seen, [{'seeds': 101}])

    def test_v21_dispatches_only_to_its_own_engine(self):
        seen = []
        output = run_versioned("2.1", lambda **kw: seen.append(kw) or {"ok": True},
                               seeds=1)
        self.assertEqual(output, {"ok": True})
        self.assertEqual(seen, [{"seeds": 1}])

    def test_cli_rejects_unknown_version_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'desconocida'
            with self.assertRaises(SystemExit) as exc:
                main(['--version', '2.3', '--out', str(target)])
            self.assertEqual(exc.exception.code, 2)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
