# Gimmich gym

Where Gimmich's AI models learn to use screens by themselves.

- **Eyes and hands** (`gimmich_gym.py`): the same five commands on every
  screen: screenshot, click, type, key, scroll. Screens so far: `x11` (any
  Linux screen: desktops, browsers, apps and every game emulator) and
  `android` (phones and the emulator, through adb). Windows and Mac are next.
- **Coach** (`agent.py`): takes a screenshot, shows it to an AI with the task,
  does the one action the AI picks, checks whether the task is done, and
  repeats. Click positions are 0-1000 across the screen, so any screen size
  works (UI-TARS, trained on pixels, is converted automatically).
- **Practice room** (`practice-app.py`, `tasks.toml`): small pages with one
  job each (click Install, type a name, use a menu, fill a form) plus an
  Android task (open Settings), each checked automatically.
- **Training data**: every run saves `step-NN.png` screenshots and
  `steps.jsonl` (what the AI saw, said and did, and whether it worked).

```
python3 scripts/gym/agent.py --all --screen x11                    # practice tasks, default AI
python3 scripts/gym/agent.py --task type-name --model ui-tars-7b   # one task, another AI
python3 scripts/gym/agent.py --screen x11 --ask "Open the File menu"
python3 scripts/gym/gimmich_gym.py android screenshot phone.png    # by hand
```

**Safety:** each task has a step limit, and the run stops if the AI tries to
type a command that deletes, formats, shuts down or uses sudo.

On GitHub: **Actions → AI gym → Run workflow** (pick the AI, or give it any job).
