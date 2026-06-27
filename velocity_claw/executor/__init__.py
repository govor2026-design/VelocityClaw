"""Velocity Claw executor package.

The package installs small compatibility extensions around the public Executor
class while keeping the main implementation module stable.
"""

from velocity_claw.executor.executor import Executor


def _install_dry_run_file_diff_preview(executor_cls: type) -> None:
    if getattr(executor_cls, "_dry_run_file_diff_preview_installed", False):
        return

    def _simulate_file_action(self, tool: str, args: dict) -> dict:
        resolved = self.fs.validate_path(args["path"])
        before = self.fs.read_existing(resolved)

        if tool == "fs.write":
            after = str(args.get("content", ""))
        elif tool == "fs.append":
            after = before + str(args.get("content", ""))
        elif tool == "fs.replace":
            old_string = str(args.get("old_string", ""))
            if old_string not in before:
                raise ValueError(f"Old string not found in {args['path']}")
            after = before.replace(old_string, str(args.get("new_string", "")), 1)
        else:
            raise ValueError(f"Unsupported dry-run file action: {tool}")

        encoded_size = len(after.encode("utf-8"))
        if encoded_size > self.settings.max_file_size:
            raise ValueError(f"Content too large: {encoded_size}")

        display_path = self.fs.display_path(resolved)
        would_change = before != after
        return {
            "status": "simulated",
            "dry_run": True,
            "validated": True,
            "action": tool,
            "path": display_path,
            "exists": resolved.exists(),
            "changed": would_change,
            "would_change": would_change,
            "diff": self.fs.make_diff(display_path, before, after),
            "bytes_before": len(before.encode("utf-8")),
            "bytes_after": encoded_size,
        }

    executor_cls._simulate_file_action = _simulate_file_action
    executor_cls._dry_run_file_diff_preview_installed = True


_install_dry_run_file_diff_preview(Executor)

__all__ = ["Executor"]
