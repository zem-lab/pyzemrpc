---
name: release-pyzemrpc
description: Bump, build, validate, and publish the main pyzemrpc pure-Python wheel to public PyPI and the project's local devpi index. Use for pyzemrpc SDK wheel releases; do not use for the optional Rust accelerator wheels or Nuitka executable releases.
---

# Release pyzemrpc

Release only committed sources, following the mandatory [repository release order](../../../AGENTS.md). Inspect git status and diff, preserve unrelated user changes, and commit the release-related changes (including the version) before regenerating build metadata and rebuilding the artifact. Use a clean checkout or committed source snapshot when unrelated changes remain. Never package uncommitted source under HEAD's commit, reuse pre-commit binaries, or fix provenance by merely rewriting metadata. Further source changes require another commit and rebuild. Do not clean or reset unrelated work, or push/upload beyond the user's authorization.

## Workflow

1. Treat a request such as “bump to VERSION, build, and release to PyPI and devpi” as authorization for those two uploads. Merely invoking this skill without an explicit publish request is not upload authorization.
2. Validate the requested version with `packaging.version.Version`. Check that it is absent from both destinations before a new release. If resuming a partial release, reuse the exact existing artifact and require its checksum to match the already-published file.
3. Update only `zemrpc/__version__.py` using `apply_patch`. `setup.py` reads the version from that file. Do not change the Rust package versions for a main-wheel release.
4. Ensure the project virtual environment has the release tools:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade build twine "packaging>=24.2" devpi-client
   ```

   `packaging>=24.2` is needed to validate the wheel's Metadata 2.4 `License-File` field.
5. Before running the bundled script, commit the release changes and record the full source commit. Run from the repository root of that clean committed source tree. The legacy ConfirmedWorktree switch does not waive the commit-before-build rule and must not be used to include uncommitted source. If unrelated work remains, use an isolated clean source tree instead:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File ".agents/skills/release-pyzemrpc/scripts/release_pyzemrpc.ps1" `
     -Version "<version>"
   ```

   The script refreshes ignored `zemrpc/__commit__.py`, regenerates the ignored Qt UI module from the current `.ui`, cleans `build/`, builds one exact wheel, runs `twine check`, installs that wheel, and runs the non-hardware tests. It excludes `tests/test_zem_api.py` by default because that module requires a responding ZEM at the configured address. Add `-RunHardwareTests` only when the hardware or suitable emulator is ready.
6. Inspect the reported wheel path, embedded version/commit, size, and SHA-256. The embedded commit must equal the recorded build-source commit. To publish the already validated artifact, run in the same committed source tree; do not relabel or rebuild an existing release:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File ".agents/skills/release-pyzemrpc/scripts/release_pyzemrpc.ps1" `
     -Version "<version>" -ReuseArtifact -Publish
   ```

   `-Publish` uploads the exact wheel to `http://dc000.local:7104/zeptools/devpi` with `devpi upload`, then to the `pypi` Twine repository. It never uses a wildcard.
7. The devpi client must already report `logged in as ...`. Its session token normally lasts ten hours. If it is expired, ask the user to authenticate locally with `.\.venv\Scripts\devpi.exe login zeptools`, or use a password the user explicitly provided for that release. Never write a password into this skill, the script, repository files, or command output. Do not use Twine with the devpi session token; Twine sends Basic Auth and the server rejects it with HTTP 401.
8. The script verifies both remote records after upload. Success requires the same filename, size, and SHA-256 on PyPI and a direct `/zeptools/devpi/+f/` link on devpi—not merely visibility through an upstream mirror.

If one destination succeeds and the other fails, do not rebuild. Fix authentication or connectivity, then rerun with `-ReuseArtifact -Publish`; the script verifies and skips an existing identical release. PyPI releases are immutable, so stop on any checksum mismatch.

Report the final version, artifact path, SHA-256, PyPI URL, devpi direct-stage verification, test results, and remaining worktree changes.
