    1. What the game is.
    2. How to install the required software.
    3. How to install Python dependencies.
    4. How to start the web application.
    5. What URL to open.
    6. The keyboard controls.
    7. How to play.
    8. How the levels work.
    9. What Python does in the application.
    10. What AI tools were used.

# Nom's Ascent

A vibecoded 2d platformer game.

# Play online

https://liamw8007.github.io/noms-ascent/ (the first load downloads Pyodide, so give it a few seconds).

# Installation

This game serves a dynamic webpage through Pyodide. To begin, clone the repository:
```
$ git clone https://github.com/liamw8007/noms-ascent
$ cd noms-ascent
```

The game runs in two modes. Both need an internet connection the first time,
to download Pyodide.

## Static mode (no server, scores saved in your browser only)

Serve the prebuilt `docs/` folder, the same files GitHub Pages uses:
```
$ python3 -m http.server 8000 -d docs
```

Open http://127.0.0.1:8000 in a web browser. (Opening `index.html` directly as a file does not work.)

After changing the game, rebuild that folder with `python3 scripts/build_static.py` (needs the dependencies below).

## Server mode (Flask, shared high-score table)

Install the Python dependencies, ideally in a virtual environment:
```
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install -r requirements.txt
```

Create `.env` from the example and give it a random secret key. The server refuses to start without one:
```
$ cp .env.example .env
$ python3 -c "import secrets; print(secrets.token_hex(32))"   # paste the output as SECRET_KEY in .env
```

Start the server and open http://127.0.0.1:5000:
```
$ flask --app app run
```

The high-score database is created automatically in `instance/scores.db`.

## Tests

```
$ pytest
```

# Controls

Nom can be controlled through WASD/arrow keys and space.
A help menu can be accessed by pressing `?`.

# What does Python do?

In this project, Python serves as the main engine behind the game. It controls game logic
such as collisions, points, and other math. JavaScript connects this Python backend to the
browser.

In server mode, Python (Flask) also runs on the server: it serves the levels, checks each
finished level against the level file, calculates the score itself and stores the
high-score table in SQLite.

# Use of AI

This project was built in collaboration with Claude Code (Opus 5.5).
