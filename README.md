# remote

Automate any AI chat interface using pyautogui and selenium. Control it from another device via HTTP.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/gliddd4/remote/main/remote.sh | sh
```

Run it:

```bash
remote
```

## Setup

Record 9 button positions (search bar, text input, pop-ups, etc.) by pressing `r` and following the prompts.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Check server status |
| POST | `/send` | Send a prompt (`{"prompt": "..."}`) |
| GET | `/config` | View button config |
| POST | `/config/ai-url` | Change AI website URL |
| POST | `/config/wait-time` | Set max response wait time |

## Requirements

- macOS
- Chrome (with remote debugging support)
- Python 3
