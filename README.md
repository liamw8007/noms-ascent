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

# Installation

This game serves a dynamic webpage through Pyodide. To begin, clone the repository:
```
$ git clone https://github.com/liamw8007/noms-ascent
$ cd noms-ascent
```

Start an HTTP server:
```
$ python3 -m http.server 8000
```

Access `127.0.0.1:8000` from a web browser.

# Controls

Nom can be controlled through WASD/arrow keys and space.
A help menu can be accessed by pressing `?`.

# What does Python do?

In this project, Python serves as the main engine behind the game. It controls game logic
such as collisions, points, and other math. JavaScript connects this Python backend to the
browser.

# Use of AI

This project was built in collaboration with Claude Code (Opus 5.5).
