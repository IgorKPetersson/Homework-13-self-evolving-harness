"""Version store with atomic promotion and last-known-good recovery.

state/versions/vNNNN/   immutable accepted versions (solver.py, genome.json, eval.json)
state/candidates/<id>/  every candidate ever evaluated, accepted or not
state/CURRENT           name of the active version (replaced atomically)
"""
import hashlib
import json
import os
import shutil
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.candidates = self.root / "candidates"
        self.pointer = self.root / "CURRENT"

    def initialized(self):
        return self.pointer.exists()

    def list_versions(self):
        return sorted(p.name for p in self.versions.glob("v[0-9]*") if p.is_dir())

    def _write_pointer(self, name):
        tmp = self.pointer.with_suffix(".tmp")
        tmp.write_text(name + "\n")
        os.replace(tmp, self.pointer)                 # atomic on POSIX

    def save_candidate(self, cand_id, source, genome, evaluation):
        d = self.candidates / cand_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "solver.py").write_text(source)
        (d / "genome.json").write_text(json.dumps(genome))
        (d / "eval.json").write_text(json.dumps(evaluation, indent=2, sort_keys=True))
        return d

    def promote(self, cand_dir):
        name = f"v{len(self.list_versions()) + 1:04d}"
        staging = self.versions / f".{name}.staging"
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(cand_dir, staging)
        os.replace(staging, self.versions / name)
        self._write_pointer(name)
        return name

    def _load(self, name):
        d = self.versions / name
        source = (d / "solver.py").read_text()
        meta = json.loads((d / "eval.json").read_text())
        if hashlib.sha256(source.encode()).hexdigest() != meta["sha256"]:
            raise ValueError(f"{name}: solver.py does not match its recorded hash")
        return {"version": name, "source": source, "eval": meta,
                "genome": json.loads((d / "genome.json").read_text())}

    def current(self):
        """Load the active version; on corruption fall back to the newest intact
        older version and repoint CURRENT. Returns (version_dict, recovery_note)."""
        name = self.pointer.read_text().strip()
        try:
            return self._load(name), None
        except (OSError, ValueError, KeyError) as exc:
            problem = str(exc)
        for older in reversed(self.list_versions()):
            if older == name:
                continue
            try:
                v = self._load(older)
            except (OSError, ValueError, KeyError):
                continue
            self._write_pointer(older)
            return v, f"{name} corrupt ({problem}); recovered to {older}"
        raise RuntimeError(f"no intact version available: {problem}")

    def rollback(self):
        name = self.pointer.read_text().strip()
        older = [v for v in self.list_versions() if v < name]
        if not older:
            raise RuntimeError("no earlier version to roll back to")
        self._write_pointer(older[-1])
        return name, older[-1]
