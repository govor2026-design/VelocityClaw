# Queue recovery example

After an unclean restart, inspect `GET /queue/v2/runtime`. A recovered job that was previously `running` appears as `queued` with an incremented recovery count and a history event named `recovered_after_restart_from_running`.

Use `POST /queue/v2/recover` to schedule any queued jobs that are not already active or scheduled.
