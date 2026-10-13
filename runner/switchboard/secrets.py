"""Read a secret from the environment, then (on a Mac) the Keychain. Never from files in the repo.

Store one in Keychain:  security add-generic-password -a "$USER" -s NOTION_TOKEN -w
"""
import os
import shutil
import subprocess


def get_secret(name, required=True):
    val = os.environ.get(name)
    if not val and shutil.which("security"):
        r = subprocess.run(["security", "find-generic-password", "-s", name, "-w"],
                           capture_output=True, text=True)
        val = r.stdout.strip() if r.returncode == 0 else None
    if not val and required:
        raise RuntimeError(f"missing secret {name}: set the env var or a Keychain item named {name}")
    return val
