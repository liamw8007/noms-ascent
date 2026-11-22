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

https://liamw8007.github.io/noms-ascent/ (the first load downloads the Python runtime, about 13 MB, so give it a few seconds).

# Installation

This game serves a dynamic webpage through Pyodide. To begin, clone the repository:
```
$ git clone https://github.com/liamw8007/noms-ascent
$ cd noms-ascent
```

The game runs in two modes. Neither needs an internet connection: the Python runtime
(Pyodide 314.0.8) is included in `static/pyodide/`.

## Static mode (no server, scores saved in your browser only)

Serve the prebuilt `docs/` folder, the same files GitHub Pages uses:
```
$ python3 -m http.server 8000 -d docs
```

Open http://127.0.0.1:8000 in a web browser. (Opening `index.html` directly as a file does not work.)

After changing the game, rebuild that folder with `python3 scripts/build_static.py` (needs the dependencies below).

## Server mode (Flask, shared high-score table)

Install the Python dependencies, ideally in a virtual environment. Every package is pinned
to an exact version with a SHA-256 hash, so pip refuses anything that doesn't match:
```
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install --require-hashes -r requirements.txt
```

Create `.env` from the example and give it a random secret key of at least 32 characters.
The server refuses to start without one:
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

The tests and the security scanner need the development dependencies, which include
everything in `requirements.txt`:
```
$ pip install --require-hashes -r requirements-dev.txt
$ pytest
$ bandit -r app.py config.py db.py game scripts
```

To change a dependency, edit `requirements.in` or `requirements-dev.in` and regenerate the
pinned files with the `uv pip compile` command at the top of each `.in` file.

## Deploying server mode

`flask run` is a development server. To put server mode on the internet:

- Run it under a production WSGI server, for example
  `waitress-serve --call app:create_app` (Windows or Linux) or `gunicorn "app:create_app()"`.
- Serve it over HTTPS only, behind a reverse proxy such as nginx or Caddy. The session
  cookie is `Secure`, so browsers only send it over HTTPS (or to `localhost`), and the app
  sends `Strict-Transport-Security` on HTTPS requests. If the proxy changes the host or
  scheme, wrap the app in Werkzeug's `ProxyFix` so the `Origin` check sees the real host.
- Set per-IP rate limits in the proxy. The app itself caps active runs (10,000) and keeps
  only the best 100 scores.
- Keep `FLASK_DEBUG=0`. The debugger allows running code on the server.
- Use a long random `SECRET_KEY` and keep `.env` out of version control (it is in `.gitignore`).

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
