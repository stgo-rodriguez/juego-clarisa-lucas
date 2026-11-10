"""SIMLOG 2.3: eventos de Casa con ubicación, comprador y propietario."""
from __future__ import annotations

import json
from pathlib import Path

from simulador.experimento_politicas_v22 import SIMLogAuditV22


class SIMLogV23(SIMLogAuditV22):
    def validate(self):
        super().validate()
        for event in self.events:
            if event["Fuente"] != "economia" or event["Accion"] not in (
                "house_attempt", "house_encounter", "house_bought",
            ):
                continue
            detail = json.loads(event["Detalle_JSON"])
            loc = detail.get("location")
            if not isinstance(loc, list) or len(loc) != 2:
                raise AssertionError("Evento Casa v2.3 sin coordenadas del encuentro")
            if detail.get("mode") == "banca":
                if loc != [3, 3]:
                    raise AssertionError("Compra a la banca fuera de CASA (3,3)")
                # house_bought.owners identifica a los NUEVOS compradores;
                # house_attempt.owners identifica al propietario anterior.
                if event["Accion"] == "house_bought":
                    if detail.get("prior") is not None:
                        raise AssertionError("Venta de propietarios etiquetada como banca")
                elif detail.get("owners") not in (None, []):
                    raise AssertionError("Compra bancaria con dueño anterior")
            elif detail.get("mode") == "propietarios":
                if event["Accion"] == "house_bought":
                    if not detail.get("prior"):
                        raise AssertionError("Disputa adjudicada sin dueños anteriores")
                elif not detail.get("owners"):
                    raise AssertionError("Disputa sin identificación de propietarios")
            else:
                raise AssertionError("Origen de compra/disputa de Casa no identificado")

    def write(self, out, *, status, summary):
        manifest = super().write(out, status=status, summary=summary)
        manifest.update({
            "schema": "SIMLOG-2.3",
            "ruleset": "especificacion-integral-2026-11-10",
            "source_document_id": "16IOCwC72fT__n5b19PQm-LRa7CenB5S_",
            "experimental_variant": "v23-bank-mixed-policy",
            "house_acquisition": "bank_only_at_3_3;dispute_at_current_owner_position",
            "house_encounters_include_positions": True,
        })
        Path(out, "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest
