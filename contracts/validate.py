#!/usr/bin/env python
"""Validação dos contratos do ecossistema (JSON Schema). Usa `jsonschema` se instalado; senão um validador mínimo
(type, required, properties, enum, minimum/maximum, pattern, minItems, minProperties, items, anyOf,
additionalProperties) suficiente para os schemas deste diretório.

  python contracts/validate.py <schema-name> <arquivo.json>      # ex.: model_manifest.v1 manifest.json
  from contracts.validate import validate; errors = validate("scoring_result.v1", obj)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TYPES = {"object": dict, "array": list, "string": str, "number": (int, float), "integer": int, "boolean": bool}


def _check(s: dict, v, path: str) -> list[str]:
    errs: list[str] = []
    if "anyOf" in s:
        branches = [_check(b, v, path) for b in s["anyOf"]]
        return [] if any(not b for b in branches) else [f"{path}: não corresponde a nenhuma opção de anyOf"]
    t = s.get("type")
    if t and not (isinstance(v, TYPES[t]) and not (t in ("number", "integer") and isinstance(v, bool))):
        return [f"{path}: esperado {t}"]
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: valor fora de {s['enum']}")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: < {s['minimum']}")
        if "maximum" in s and v > s["maximum"]:
            errs.append(f"{path}: > {s['maximum']}")
    if isinstance(v, str):
        if "minLength" in s and len(v) < s["minLength"]:
            errs.append(f"{path}: curto demais")
        if "pattern" in s and not re.search(s["pattern"], v):
            errs.append(f"{path}: não casa {s['pattern']}")
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{path}: menos de {s['minItems']} itens")
        for i, item in enumerate(v):
            errs += _check(s.get("items", {}), item, f"{path}[{i}]")
    if isinstance(v, dict):
        if len(v) < s.get("minProperties", 0):
            errs.append(f"{path}: menos de {s['minProperties']} propriedades")
        for req in s.get("required", []):
            if req not in v:
                errs.append(f"{path}.{req}: obrigatório")
        props = s.get("properties", {})
        for k, item in v.items():
            if k in props:
                errs += _check(props[k], item, f"{path}.{k}")
            elif s.get("additionalProperties") is False:
                errs.append(f"{path}.{k}: propriedade não permitida")
            elif isinstance(s.get("additionalProperties"), dict):
                errs += _check(s["additionalProperties"], item, f"{path}.{k}")
    return errs


def validate(name: str, obj) -> list[str]:
    schema = json.loads((HERE / f"{name}.schema.json").read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
        return [f"$.{'/'.join(map(str, e.path))}: {e.message}" for e in jsonschema.Draft202012Validator(schema).iter_errors(obj)]
    except ImportError:
        return _check(schema, obj, "$")


if __name__ == "__main__":
    errors = validate(sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    print("\n".join(errors) or "OK")
    sys.exit(1 if errors else 0)
