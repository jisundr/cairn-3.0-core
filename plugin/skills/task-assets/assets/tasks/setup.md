# Setting up docs/tasks/

1. Ask once whether to copy the task templates into the project. Without them cairn seeds task docs from its own copies in `tasks/_template/`, so the copy is only for people who want to read or edit the templates. No answer → skip.
2. On yes: create `docs/tasks/` if absent, with an empty `.gitkeep`, and copy `tasks/_template/` to `docs/tasks/_template/`, skipping any file already there.
3. Show these lines as a suggestion for the root `.gitignore`, for the user to add if they want task folders kept out of git. cairn does not edit `.gitignore`.

```
docs/tasks/*
!docs/tasks/.gitkeep
!docs/tasks/_template/
```

4. Archive folder, per `tasks/archive.md`. `.harness/workflow.md` absent → skip with a note. `## Archive` already has `- Path:` → report it and change nothing. Else run `find docs -maxdepth 2 -type d -iname '*archive*'`: one hit → propose it; several → list them and ask which; none → propose the default. The user accepts or types a path, validated per that file's Setting; no answer → nothing is written and the default applies. Show the section, then append it to `.harness/workflow.md`. The folder itself is not created here.
5. Report what was created and what already existed. A re-run changes nothing it already made.
