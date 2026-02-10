"""Entity Alias Management System for MegaBook.

Handles mapping of entity aliases to canonical names.
Examples:
- "Ion", "Ion the Brave", "Prince Ion" → "Ion"
- "Waterdeep", "The City of Splendors" → "Waterdeep"

Stores aliases in metadata/entity_aliases.json
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import re

from src.core.filesystem import FilesystemService, KnowledgeLayer


@dataclass
class EntityAlias:
    """An alias entry for an entity."""
    canonical_name: str
    aliases: List[str]
    entity_type: str
    disambiguation_note: Optional[str] = None
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "entity_type": self.entity_type,
            "disambiguation_note": self.disambiguation_note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "EntityAlias":
        return cls(**data)


class AliasManager:
    """Manages entity aliases and canonical name resolution."""
    
    def __init__(self, filesystem: FilesystemService) -> None:
        """Initialize the alias manager.
        
        Args:
            filesystem: Filesystem service for reading/writing alias data
        """
        self.filesystem = filesystem
        self._aliases_path = "metadata/entity_aliases.json"
        self._aliases: Dict[str, EntityAlias] = {}
        self._name_to_canonical: Dict[str, str] = {}  # Quick lookup cache
        self._load_aliases()
    
    def _load_aliases(self) -> None:
        """Load aliases from disk."""
        try:
            content = self.filesystem.read_file(
                self._aliases_path,
                layer=KnowledgeLayer.PROMPTS
            )
            data = json.loads(content)
            
            for canonical, alias_data in data.get("entities", {}).items():
                entity_alias = EntityAlias.from_dict(alias_data)
                self._aliases[canonical] = entity_alias
                
                # Build lookup cache
                self._name_to_canonical[canonical.lower()] = canonical
                for alias in entity_alias.aliases:
                    self._name_to_canonical[alias.lower()] = canonical
        except (FileNotFoundError, json.JSONDecodeError):
            # No aliases file yet, start empty
            self._aliases = {}
            self._name_to_canonical = {}
    
    def _save_aliases(self) -> None:
        """Save aliases to disk."""
        data = {
            "entities": {
                canonical: alias.to_dict()
                for canonical, alias in self._aliases.items()
            },
            "last_updated": datetime.now().isoformat(),
        }
        
        self.filesystem.write_file(
            self._aliases_path,
            json.dumps(data, indent=2),
            layer=KnowledgeLayer.PROMPTS,
        )
    
    def resolve_name(self, name: str) -> Optional[str]:
        """Resolve a name to its canonical form.
        
        Args:
            name: The name to resolve (e.g., "Ion the Brave")
            
        Returns:
            Canonical name (e.g., "Ion") or None if not found
        """
        # Direct lookup
        name_lower = name.lower()
        if name_lower in self._name_to_canonical:
            return self._name_to_canonical[name_lower]
        
        # Try fuzzy matching for common variations
        canonical = self._fuzzy_match(name)
        if canonical:
            return canonical
        
        return None
    
    def _fuzzy_match(self, name: str) -> Optional[str]:
        """Attempt fuzzy matching for entity names.
        
        Handles cases like:
        - "Prince Ion" → "Ion"
        - "Ion of Waterdeep" → "Ion"
        - "The Sword of Light" → "Sword of Light"
        """
        name_lower = name.lower()
        
        # Remove common prefixes/suffixes
        prefixes = ["the ", "a ", "an ", "prince ", "princess ", "king ", "queen ", 
                   "lord ", "lady ", "sir ", "lady ", "master ", "mistress "]
        suffixes = [" of waterdeep", " of faerûn", " the brave", " the wise", 
                   " from", " of", " in", " at"]
        
        # Try without prefixes
        for prefix in prefixes:
            if name_lower.startswith(prefix):
                without_prefix = name_lower[len(prefix):].strip()
                if without_prefix in self._name_to_canonical:
                    return self._name_to_canonical[without_prefix]
        
        # Try without suffixes
        for suffix in suffixes:
            if name_lower.endswith(suffix):
                without_suffix = name_lower[:-len(suffix)].strip()
                if without_suffix in self._name_to_canonical:
                    return self._name_to_canonical[without_suffix]
        
        # Try contains match (for "Ion the Brave" → "Ion")
        for alias_lower, canonical in self._name_to_canonical.items():
            if alias_lower in name_lower or name_lower in alias_lower:
                return canonical
        
        return None
    
    def add_alias(self, canonical_name: str, alias: str, entity_type: str,
                  disambiguation_note: Optional[str] = None) -> None:
        """Add an alias for an entity.
        
        Args:
            canonical_name: The canonical name (e.g., "Ion")
            alias: The alias to add (e.g., "Ion the Brave")
            entity_type: Type of entity (character, location, etc.)
            disambiguation_note: Optional note to disambiguate similar names
        """
        canonical_name = canonical_name.strip()
        alias = alias.strip()
        
        # Check if canonical already exists
        if canonical_name in self._aliases:
            entity_alias = self._aliases[canonical_name]
            if alias not in entity_alias.aliases and alias != canonical_name:
                entity_alias.aliases.append(alias)
                entity_alias.updated_at = datetime.now().isoformat()
        else:
            # Create new entity alias
            self._aliases[canonical_name] = EntityAlias(
                canonical_name=canonical_name,
                aliases=[alias] if alias != canonical_name else [],
                entity_type=entity_type,
                disambiguation_note=disambiguation_note,
            )
        
        # Update lookup cache
        self._name_to_canonical[canonical_name.lower()] = canonical_name
        self._name_to_canonical[alias.lower()] = canonical_name
        
        # Save to disk
        self._save_aliases()
    
    def get_entity(self, canonical_name: str) -> Optional[EntityAlias]:
        """Get entity alias data by canonical name."""
        return self._aliases.get(canonical_name)
    
    def get_all_entities(self) -> Dict[str, EntityAlias]:
        """Get all entity aliases."""
        return self._aliases.copy()
    
    def search_entities(self, query: str, entity_type: Optional[str] = None) -> List[EntityAlias]:
        """Search for entities matching a query.
        
        Args:
            query: Search string
            entity_type: Optional filter by entity type
            
        Returns:
            List of matching EntityAlias objects
        """
        query_lower = query.lower()
        results = []
        
        for canonical, entity in self._aliases.items():
            # Filter by type if specified
            if entity_type and entity.entity_type != entity_type:
                continue
            
            # Check canonical name
            if query_lower in canonical.lower():
                results.append(entity)
                continue
            
            # Check aliases
            for alias in entity.aliases:
                if query_lower in alias.lower():
                    results.append(entity)
                    break
        
        return results
    
    def merge_entities(self, keep_name: str, merge_name: str) -> None:
        """Merge two entities, keeping one as canonical.
        
        Args:
            keep_name: The canonical name to keep
            merge_name: The entity to merge into keep_name
        """
        if keep_name not in self._aliases or merge_name not in self._aliases:
            raise ValueError("Both entities must exist to merge")
        
        keep_entity = self._aliases[keep_name]
        merge_entity = self._aliases[merge_name]
        
        # Add all aliases from merge_entity to keep_entity
        for alias in merge_entity.aliases:
            if alias not in keep_entity.aliases and alias != keep_name:
                keep_entity.aliases.append(alias)
                self._name_to_canonical[alias.lower()] = keep_name
        
        # Add merge_name itself as an alias
        if merge_name not in keep_entity.aliases and merge_name != keep_name:
            keep_entity.aliases.append(merge_name)
            self._name_to_canonical[merge_name.lower()] = keep_name
        
        # Add disambiguation note
        if keep_entity.disambiguation_note:
            keep_entity.disambiguation_note += f"; Also known as: {merge_name}"
        else:
            keep_entity.disambiguation_note = f"Also known as: {merge_name}"
        
        keep_entity.updated_at = datetime.now().isoformat()
        
        # Remove merged entity
        del self._aliases[merge_name]
        
        # Save changes
        self._save_aliases()
    
    def remove_alias(self, canonical_name: str, alias: str) -> None:
        """Remove an alias from an entity."""
        if canonical_name in self._aliases:
            entity = self._aliases[canonical_name]
            if alias in entity.aliases:
                entity.aliases.remove(alias)
                entity.updated_at = datetime.now().isoformat()
                
                # Remove from lookup cache
                if alias.lower() in self._name_to_canonical:
                    del self._name_to_canonical[alias.lower()]
                
                self._save_aliases()
    
    def suggest_aliases(self, name: str, entity_type: str) -> List[str]:
        """Suggest potential aliases for a new entity.
        
        Based on common naming patterns:
        - "Ion" → ["Ion the Brave", "Prince Ion"]
        - "Waterdeep" → ["The City of Splendors", "Waterdeep City"]
        """
        suggestions = []
        
        if entity_type == "character":
            # Common character titles
            suggestions.extend([
                f"{name} the Brave",
                f"{name} the Wise",
                f"{name} the Strong",
                f"Prince {name}",
                f"Princess {name}",
                f"King {name}",
                f"Queen {name}",
                f"Lord {name}",
                f"Lady {name}",
                f"Sir {name}",
                f"Master {name}",
                f"Mistress {name}",
            ])
        elif entity_type == "location":
            # Common location descriptors
            suggestions.extend([
                f"The {name}",
                f"Old {name}",
                f"New {name}",
                f"{name} City",
                f"{name} Town",
                f"{name} Village",
                f"{name} Castle",
                f"{name} Keep",
            ])
        elif entity_type == "item":
            # Common item descriptors
            suggestions.extend([
                f"The {name}",
                f"{name} of Power",
                f"{name} of Light",
                f"{name} of Darkness",
                f"Ancient {name}",
                f"Legendary {name}",
            ])
        
        return suggestions
