# Design rules (each one fixed a real complaint)

1. **Show the current run by default.** A stale run id at the top read as "the viewer is wrong".
   Newest first in the picker; an explicit pick stays until changed.
2. **Label every id with its kind.** "01.04" vs "01.9" confused the user (sub-phase vs task).
3. **Targets are not results.** Show "must reach GREEN" until done, then "GREEN ✓". A bare
   GREEN badge on an unfinished task read as success.
4. **Only the current scope's arrows/steps**, with a legend. Grey arrows for all history were
   unreadable.
5. **Keep scroll positions across refreshes.** A feed that jumped to the top every poll was unusable.
6. **Stale data is labelled stale.** A day-old usage record looked current; show its source and
   age, and "unknown" past 5 hours.
7. **Hide what is finished** (e.g. the path strip once every task is done).
8. **Escape everything**; render text, never adapter-provided HTML.
9. **Verify by rendering real payloads in node** for every state (running, paused, stopped,
   completed, no runs). A const name clash passed `node --check` and blanked the page.
10. **Prefix page helpers** (`lv…`, `u…`) so new code cannot shadow an existing helper.
