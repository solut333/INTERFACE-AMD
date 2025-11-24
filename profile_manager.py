import json
import os

class ProfileManager:
    def __init__(self, profiles_file="profiles.json"):
        self.profiles_file = profiles_file
        self.profiles = self._load_profiles()

    def _load_profiles(self):
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_profile(self, profile_name, settings):
        if not profile_name:
            raise ValueError("O nome do perfil não pode ser vazio.")
        self.profiles[profile_name] = settings
        self._write_profiles()

    def load_profile(self, profile_name):
        return self.profiles.get(profile_name)

    def delete_profile(self, profile_name):
        if profile_name in self.profiles:
            del self.profiles[profile_name]
            self._write_profiles()
            return True
        return False

    def get_profile_names(self):
        return sorted(list(self.profiles.keys()))

    def _write_profiles(self):
        with open(self.profiles_file, 'w') as f:
            json.dump(self.profiles, f, indent=4)
