from __future__ import annotations
from pathlib import Path
from backend.playbooks.loader import load_playbook
from backend.playbooks.validator import validate_playbook

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data" / "playbooks"
class PlaybookCatalog:
    def __init__(self, root: Path = DEFAULT_ROOT): self.root=root; self._items={}; self.reload()
    def reload(self):
        items={}
        for path in sorted(list(self.root.rglob("*.yaml"))+list(self.root.rglob("*.yml"))+list(self.root.rglob("*.json"))):
            item=load_playbook(path); errors=validate_playbook(item)
            if errors: raise ValueError(f"Invalid playbook {path}: {'; '.join(errors)}")
            if item.playbook_id in items: raise ValueError(f"Duplicate playbook id: {item.playbook_id}")
            items[item.playbook_id]=item
        self._items=items; return self.list()
    def list(self): return [item.to_dict() for item in sorted(self._items.values(), key=lambda v:v.name.lower())]
    def get(self, playbook_id):
        item=self._items.get(playbook_id)
        if item is None: raise ValueError(f"Unknown playbook: {playbook_id}")
        return item
    def validate(self, playbook_id):
        item=self.get(playbook_id); return {"valid": not validate_playbook(item), "errors": validate_playbook(item)}
_catalog=None
def get_playbook_catalog():
    global _catalog
    if _catalog is None: _catalog=PlaybookCatalog()
    return _catalog
