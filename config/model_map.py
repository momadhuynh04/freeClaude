import json
import os
from typing import Dict, Tuple

class ModelMapper:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.mappings: Dict[str, str] = {}
        self.load_mappings()
        
    def load_mappings(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.mappings = data.get("model_mappings", {})
                
    def save_mappings(self):
        data = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        data["model_mappings"] = self.mappings
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def set_mapping(self, source_model: str, target: str):
        self.mappings[source_model] = target
        self.save_mappings()

    def get_all(self) -> Dict[str, str]:
        return self.mappings
                
    # Keyword tiers to match against — order matters (most specific first)
    KEYWORD_TIERS = ["opus", "sonnet", "haiku"]

    def resolve(self, requested_model: str) -> Tuple[str, str]:
        """
        Resolves the requested model string to a provider and target model.
        Strategy:
          1. Exact match against mapping keys.
          2. Keyword match: if requested model contains 'opus'/'sonnet'/'haiku',
             scan existing mapping keys for the same keyword and use that value.
          3. Raise ValueError with a helpful message.
        """
        # 1. Exact match
        target = self.mappings.get(requested_model)

        # 2. Keyword fallback — scan existing keys for matching keyword
        if not target:
            model_lower = requested_model.lower()
            for keyword in self.KEYWORD_TIERS:
                if keyword in model_lower:
                    # Find first existing key that also contains this keyword
                    for key, val in self.mappings.items():
                        if keyword in key.lower():
                            target = val
                            print(f"[⚡] No exact match for '{requested_model}', "
                                  f"keyword '{keyword}' matched key '{key}' → '{val}'")
                            break
                if target:
                    break

        if not target:
            raise ValueError(
                f"No mapping found for model '{requested_model}'. "
                f"Please add it via WebUI (http://127.0.0.1:8082) or config.json."
            )

        parts = target.split("/", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid mapping format '{target}' for '{requested_model}'. "
                f"Expected 'provider/model_name'."
            )

        return parts[0], parts[1]

model_mapper = ModelMapper()
