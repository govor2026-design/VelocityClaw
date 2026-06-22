# Project memory v2

Velocity Claw now separates reusable repository knowledge from temporary run trace.

Reusable knowledge is stored in the `project_knowledge` SQLite table with a stable key, category, JSON value, source, confidence, timestamps, and usage counters.

Recommended categories are `architecture`, `constraint`, `convention`, `dependency`, `path`, and `test_command`.

Operational events such as task text, run summaries, failures, approval pauses, and auto-fix events remain trace data. They are not promoted into reusable planning notes.

Task context may contain `project_knowledge`. A mapping stores each item as a reusable fact. A list may provide explicit `key`, `value`, `category`, `source`, and `confidence` fields.

Planning and resume artifacts include `project_memory_v2`. The agent also projects selected v2 information into the existing Planner fields:

- `project_facts` for structured knowledge;
- `recent_notes` for reusable notes only;
- `recent_run_tasks` for semantically related runs;
- `recent_failed_tasks` for related failures;
- `memory_signals_v2` for reuse and inspection hints.

The Planner consumes `memory_signals_v2` directly. A prior successful related run produces an explicit reuse directive, while a related failure strengthens inspection-first planning before edits.

Related runs are ranked by meaningful term overlap and recency rather than exact full-task substring matching. The current active run is removed before context reaches the Planner.

Existing API responses remain compatible:

- `/memory/context` now contains `project_memory_v2`;
- `/memory/resume?task=...` now contains task-aware `project_memory_v2`.

Structured project knowledge is not deleted by short-term run cleanup. Obsolete entries should be removed explicitly through the agent project-knowledge interface.
