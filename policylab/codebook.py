"""Load the YAML codebook and validate codes against it."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from . import paths

NOT_STATED = "not_stated"


@dataclass(frozen=True)
class Variable:
    id: str
    label: str
    type: str  # single | multi | date
    definition: str
    values: dict[str, str]
    decision_rules: list[str]
    cues: dict[str, list[str]]
    retrieval_query: str

    def validate_values(self, values: list[str]) -> list[str]:
        """Return a list of problems (empty when valid)."""
        problems = []
        if self.type == "date":
            if len(values) != 1:
                problems.append(f"{self.id}: expected exactly one date value")
            for v in values:
                if v == NOT_STATED:
                    continue
                try:
                    dt.date.fromisoformat(v)
                except ValueError:
                    problems.append(f"{self.id}: {v!r} is not YYYY-MM-DD or {NOT_STATED!r}")
            return problems
        if not values:
            problems.append(f"{self.id}: at least one value required")
        if self.type == "single" and len(values) > 1:
            problems.append(f"{self.id}: single-select variable got {len(values)} values")
        for v in values:
            if v not in self.values:
                problems.append(f"{self.id}: {v!r} not in allowed values {sorted(self.values)}")
        if self.type == "multi" and "none" in values and len(values) > 1:
            problems.append(f"{self.id}: 'none' cannot be combined with other values")
        return problems


@dataclass(frozen=True)
class Codebook:
    version: str
    name: str
    general_rules: list[str]
    variables: tuple[Variable, ...]

    def get(self, var_id: str) -> Variable:
        for v in self.variables:
            if v.id == var_id:
                return v
        raise KeyError(var_id)

    @property
    def ids(self) -> list[str]:
        return [v.id for v in self.variables]

    def to_prompt(self) -> str:
        """Render the codebook as compact text for the LLM prompt."""
        lines = [f"CODEBOOK {self.name} (version {self.version})", "General rules:"]
        lines += [f"- {r}" for r in self.general_rules]
        for v in self.variables:
            lines.append(f"\n## {v.id} ({v.type}) - {v.label}\n{v.definition}")
            if v.values:
                lines.append("Allowed values:")
                lines += [f"  - {k}: {d}" for k, d in v.values.items()]
            else:
                lines.append(f'Value: one ISO date "YYYY-MM-DD" or "{NOT_STATED}".')
            if v.decision_rules:
                lines.append("Decision rules:")
                lines += [f"  - {r}" for r in v.decision_rules]
        return "\n".join(lines)


def load_codebook(path: Path | None = None) -> Codebook:
    with open(path or paths.CODEBOOK) as f:
        raw = yaml.safe_load(f)
    variables = tuple(
        Variable(
            id=v["id"],
            label=v["label"],
            type=v["type"],
            definition=v["definition"].strip(),
            values={str(k): str(d) for k, d in (v.get("values") or {}).items()},
            decision_rules=list(v.get("decision_rules") or []),
            cues={str(k): list(c) for k, c in (v.get("cues") or {}).items()},
            retrieval_query=v.get("retrieval_query", v["label"]),
        )
        for v in raw["variables"]
    )
    return Codebook(
        version=str(raw["version"]),
        name=raw["name"],
        general_rules=list(raw.get("general_rules") or []),
        variables=variables,
    )


@lru_cache(maxsize=1)
def default_codebook() -> Codebook:
    return load_codebook()
