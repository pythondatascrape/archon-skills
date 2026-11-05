---
name: fingerprint-registry
description: Check or update a JSON registry of file fingerprints (path to sha256), e.g. a compatibility or freeze file that must change whenever a listed file changes. Use whenever you edit a file that such a registry lists, or a task says to update hashes.
---

- Check: `python3 ${CLAUDE_SKILL_DIR}/scripts/fingerprints.py check --file <registry JSON> --pointer /path/to/map`. Exit 1 lists stale and missing files.
- Update: `python3 ${CLAUDE_SKILL_DIR}/scripts/fingerprints.py update --file <registry JSON> --pointer /path/to/map [--add <new paths>]`. It keeps everything else in the file, and changes nothing if a listed file is missing.
