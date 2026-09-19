---
name: create-desktop-launch-bat
description: Create or refresh the Windows desktop ZEMrpc.bat launcher for this repository. Use when the user asks to create, install, repair, or update the ZEMrpc desktop BAT shortcut; do not use for packaging the application as an executable.
---

# Create the desktop ZEMrpc launcher

Use the bundled generator so the desktop launcher points at the current checkout even when the repository is cloned to a different path.

1. Resolve the repository root and inspect `ZEMrpc.bat`, which is the maintained launcher source.
2. Inspect an existing desktop `ZEMrpc.bat` before overwriting it. Pass `-Force` when it is an older ZEMrpc launcher or when the user explicitly asked to replace it. Do not overwrite an unrelated file with the same name.
3. Run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File ".agents/skills/create-desktop-launch-bat/scripts/create_desktop_launch_bat.ps1" -RepositoryRoot "<repo-root>" -Force
   ```

   Omit `-RepositoryRoot` when the skill is running from this Git checkout. Use `-DestinationPath` only when the user requests a non-default location.
4. Verify that the generated file contains the resolved absolute repository path and that `.venv\Scripts\pythonw.exe` exists.
5. Test the launcher. Confirm that the BAT returns promptly and a `pythonw.exe` process creates the `ZEMrpc 示例` window. Close only the test instance afterward.

Keep `pythonw.exe` and the asynchronous `start` command in the generated launcher. Together they prevent a console from remaining open while the GUI runs.
