# Movie Picker

A desktop app that picks random movies based on your preferences using the TMDB database.

## Setup (one time)

### 1. Install Python
Download and install **Python 3.10+** from https://www.python.org/downloads/

> During install, check **"Add Python to PATH"**

### 2. Install dependencies
Double-click `setup.bat` (or run in terminal):
```
setup.bat
```

### 3. Get a free TMDB API key
1. Create a free account at https://www.themoviedb.org/
2. Go to Settings → API → Request an API key (v3 auth)
3. Copy the key — you'll paste it into the app on first launch

## Running the app

Double-click `run.bat`, or:
```
python main.py
```

## Features

- **Genre filters** — pick one or more genres (or none for anything)
- **Year range** — e.g. 1980–2000 for classics
- **Minimum rating** — slider from 0–10
- **Streaming providers** — filter by Netflix, Disney+, Hulu, etc. (US)
- **Watchlist** — save movies you want to watch
- **Pick Again** — keep rolling until you find something good
- **View on TMDB** — opens the movie's TMDB page in your browser

Preferences are saved automatically between sessions.
