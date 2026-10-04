# Update to 2.21.2

Copy the contents of the `bld-letter-memo-web-2.21.2` folder into your existing
project folder, replacing matching files. Include the new `ui/theme_colors.py`
file. Do not nest the versioned folder inside the existing project.

The Flet dependencies, GitHub Pages workflow and saved-data formats are unchanged.
Do not clear browser storage. A data import is not required.

Once the files are copied, run these commands from your existing project's
Terminal window (already inside `letterpairscheme-helper-web`):

```sh
git add -A &&
git commit -m "Fix dark mode text contrast across all controls" &&
git push
```

Wait for GitHub Actions to finish. Reload the site and check that **2.21.2**
appears in the header or browser tab title. If the old build remains, use a
hard reload (Command+Shift+R on macOS); do not clear site data.

## Checks

26 automated tests pass. They cover the original BLD cases, navigation,
theme preferences, color contrast and concrete foreground values sent to UI
controls, including repeated theme switches and newly generated controls.
These do not constitute a browser screenshot or keyboard-focus test.

Verify each page in both themes after deployment, including dropdown options,
forms, memo colors, pair ratings, timer history and confirmation dialogs.
The timer's control instances, session logic, keyboard handlers and persistence
are unchanged by this release. All core/, data/ and ui/state.py files are
byte-identical to 2.21.1.
