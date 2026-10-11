# Setting up docs/tasks/

1. Ask once whether to copy the task templates into the project. Without them cairn seeds task docs from its own copies in `tasks/_template/`, so the copy is only for people who want to read or edit the templates. No answer → skip.
2. On yes: create `docs/tasks/` if absent, with an empty `.gitkeep`, and copy `tasks/_template/` to `docs/tasks/_template/`, skipping any file already there.
3. Show these lines as a suggestion for the root `.gitignore`, for the user to add if they want task folders kept out of git. cairn does not edit `.gitignore`.

```
docs/tasks/*
!docs/tasks/.gitkeep
!docs/tasks/_template/
```

4. Report what was created and what already existed. A re-run changes nothing it already made.
