# Local AI Assistant

A private, desktop coding/learning assistant powered by **local LLMs** — Ollama by default,
with support for any other server that speaks the OpenAI-compatible API (LM Studio,
llama.cpp `server`, vLLM, ...). Nothing leaves your machine.

## Run it as a regular Windows app (no terminal)

1. **Install Ollama** if you haven't already: https://ollama.com/download — the app will
   tell you if it can't find it, with a button straight to that page.
2. Get the app onto your PC one of two ways:
   - **Portable**: copy `dist\LocalAI Assistant.exe` anywhere and double-click it. That's it —
     no installation, nothing else needed. You can hand this single file to someone else and
     it'll run the same way on their PC (they'll need Ollama installed too).
   - **Installed-feel shortcut**: after building (see below), run `python make_shortcut.py`
     once — it drops a "LocalAI Assistant" icon on your Desktop and Start Menu with the app's
     icon, so you can launch it exactly like any other installed program from then on.
3. Double-click the icon. The app opens, detects your installed Ollama models, and you can
   start chatting immediately.

## Building the standalone .exe

```
pip install -r requirements.txt
python build_exe.py
```

This bundles the app, its dependencies, the icon, and the stylesheet into a single file:
`dist\LocalAI Assistant.exe`. It runs on any Windows PC without Python installed.

Then, optionally:

```
python make_shortcut.py
```

...to place a Desktop + Start Menu shortcut pointing at that exe (with the app's icon),
so it behaves like a normally-installed application.

## Sharing it with someone else

Copy `dist\LocalAI Assistant.exe` to a USB drive, cloud folder, etc., and send it to them.
They just need:
- Windows (the same architecture you built on — 64-bit)
- [Ollama](https://ollama.com/download) installed and running (the app will prompt them if not)

No Python, no terminal, no setup beyond that.

## Running in development mode

```
pip install -r requirements.txt
python -m app.main
```

## Features

- **Chat** — streamed replies from any locally-installed model, markdown rendering with
  syntax-highlighted, individually-copyable code blocks (built for coding help), persona
  presets ("Coding helper", "Explain simply", "Code reviewer", "Plain assistant"), and
  persisted chat history you can revisit from the sidebar.
- **Models** — see what's installed, pull new models with a live progress bar, delete ones
  you don't need, and a clear status banner that tells you if Ollama isn't running/installed
  (with a one-click link to the official download page).
- **Settings** — switch themes, set your default persona, and connect additional
  OpenAI-compatible local servers (LM Studio, llama.cpp server, vLLM, ...) alongside Ollama.

## Project layout

```
app/
├── main.py                 Entry point
├── backends/               LLMBackend abstraction: Ollama + generic OpenAI-compatible
├── core/                   Settings, chat session persistence, background workers
├── ui/                     Main window, Chat/Models/Settings pages, widgets, stylesheet
└── resources/              App icon
build_exe.py                Packages the app into dist\LocalAI Assistant.exe (PyInstaller)
make_shortcut.py            Creates Desktop/Start Menu shortcuts for the packaged app
```
