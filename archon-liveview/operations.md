# Operations

- **Page changes**: `page.html` is read on every request: reload the browser, no restart.
- **Server changes** (`base.py`, an adapter, `.shared/loop_ratelimit.py`): restart that viewer.
  Find it with `pgrep -fl liveview/base.py` (or `coding-loop/viz/server.py`), check its start
  time with `ps -o lstart= -p <pid>`: a process older than your change is serving old code.
- **Restart reliably**: kill the exact pid, confirm it is gone, start it again from a real
  terminal (a `!` command's shell can take a background viewer down with it), confirm a NEW pid.
- **"Port in use"**: an old viewer still holds the port; a new one exits quietly.
- **Viewers never affect runs**: runs execute their own workflow snapshot; viewers only read files.
- **Usage line**: live from Anthropic when the viewer could read the keychain; otherwise the
  newest Archon log record, labelled with its age.
