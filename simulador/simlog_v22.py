"""Registro SIMLOG 2.2 con invariantes sobre fuentes de recursos."""
from __future__ import annotations

import json
from pathlib import Path

from simulador.simlog_v21 import SIMLogV21

FORBIDDEN_SOURCES = frozenset({
    'juventud_universidad', 'juventud_tramite', 'adultez_casillero',
})


class SIMLogV22(SIMLogV21):
    def validate(self):
        super().validate()
        forbidden = [
            event for event in self.eco.events
            if event.get('action') == 'issue'
            and event.get('source') in FORBIDDEN_SOURCES
        ]
        if forbidden:
            raise AssertionError(
                f'SIMLOG v2.2 registró recursos de casilleros eliminados: {forbidden[:3]}'
            )

    def write(self, out, *, status, summary):
        manifest = super().write(out, status=status, summary=summary)
        manifest['schema'] = 'SIMLOG-2.2'
        manifest['ruleset'] = 'especificacion-integral-2026-11-09'
        manifest['source_document_id'] = '1XvdzvRGT5ZGtgljpn5vVJYS4A0KDpqkw'
        manifest['juventud'] = 'sin_premios_de_casilleros;perfil_por_vuelta'
        manifest['adultez'] = 'solo_casa_perfil_casamiento;sin_casilleros_A_P_K_M'
        manifest['resource_sources_removed'] = sorted(FORBIDDEN_SOURCES)
        (Path(out) / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        return manifest
