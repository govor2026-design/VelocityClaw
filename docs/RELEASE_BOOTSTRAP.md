# Release bootstrap and repair

The first merge that installs an automatic push trigger may not start that same workflow. After the workflow exists on the default branch, a later qualifying change can exercise the normal push trigger.

Do not use a later `master` commit to recreate an older release. The release tag must point to the commit that actually contains that version.

## Repair a missing historical release

Use the manual `release` workflow only when the expected tag or GitHub Release was not created.

1. Identify the exact historical commit that contains the intended `VERSION`.
2. Open **Actions** and select the **release** workflow.
3. Choose **Run workflow** on branch `master`.
4. Enter the expected tag, for example `v0.2.4`.
5. Enter the full 40-character historical commit SHA as `target_sha`.
6. Start the workflow.

The workflow will:

- check out the requested commit;
- validate that its `VERSION` matches the requested tag;
- run package validation, tests, and dependency audit;
- build the wheel and source distribution;
- create or repair the GitHub Release against the exact target commit;
- verify that the published tag resolves to the requested SHA.

## Required verification

Before closing a release-repair issue, verify all of the following:

- the workflow completed successfully;
- the tag resolves to the intended historical commit;
- the release is neither a draft nor a prerelease unless explicitly intended;
- the wheel, source archive, release notes, and release summary are attached;
- `VERSION` can be read through the release tag ref.

Never repair an old release by running it against the current default-branch SHA unless that SHA is the actual release commit.
