# Git-Telegram Bot System

A system that monitors Git repositories for changes and interacts via Telegram. Built with state machine architecture.

## Features

- **Telegram Bot Interface**: Simple commands to check repositories
- **Multiple Repository Support**: Monitor multiple Git repositories
- **State Machine Architecture**: Robust error handling and retry logic
- **Configurable Polling**: Optional automatic periodic checks
- **Detailed Diff Analysis**: Shows file changes with content previews

## System Architecture

The system consists of three main modules:

1. **Telegram Bot** (`telegram_bot.py`): Handles user commands and sends responses
2. **Git Watcher** (`git_watcher.py`): Monitors repositories for changes
3. **Diff Analyzer** (`diff_analyzer.py`): Analyzes changes and prepares messages

Additionally, a **State Machine** (`state_machine.py`) manages the workflow for each check operation.

## Installation

1. **Clone or copy** the system files to your server.

2. **Create a virtual environment** and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure the bot**:
   - Copy `config.example.yaml` to `config.yaml`
   - Get a Telegram Bot Token from [@BotFather](https://t.me/botfather)
   - Configure your repository paths in `config.yaml`

4. **Run the bot**:
   ```bash
   python main.py --config config.yaml
   ```

## Configuration

### Telegram Bot
1. Create a new bot via [@BotFather](https://t.me/botfather)
2. Copy the bot token to `config.yaml`
3. Optional: Restrict access by adding user IDs to `allowed_user_ids`

### Repository Setup
Each repository requires:
- `path`: Absolute path to the local Git repository
- `branch`: Branch to monitor (default: `main`)
- `remote`: Remote name (default: `origin`)

Example:
```yaml
repositories:
  my-project:
    path: "/home/user/projects/my-app"
    branch: "main"
    remote: "origin"
```

## Usage

### Telegram Commands
- `/start` - Welcome message and brief introduction
- `/help` - Detailed help with command examples
- `/list` - List all configured repositories
- `/check <repo_name>` - Check a specific repository for changes
- `/ck <n> <repo_name>` - View latest n commits (n optional, default 5)
- `/his [n]` - View your recent n commands (default 10)
- `/file <repo> <fileName>` - Find a file from recent updates and send full content
- `/status` - Show bot status

### Example Conversation
```
User: /list
Bot: 📁 Available repositories:
     • my-project
       Path: /home/user/projects/my-app
       Branch: main
       Commit: a1b2c3d4
       Dirty: false

User: /check my-project
Bot: 🔍 Checking repository 'my-project'...
Bot: 📊 Changes detected in 'my-project' (3 file(s)):
     1. README.md:
     ```
     # Updated title
     New content added...
     ```
     2. src/main.py:
     ```
     def new_function():
         return "Hello"
     ```
     3. config.yaml:
     ```
     new_setting: true
     ```
```

## State Machine Workflow

Each repository check follows this state flow:

1. **IDLE** → **FETCHING** (`check_requested`)
2. **FETCHING** → **DIFFING** (`fetch_completed`)
3. **DIFFING** → **SENDING** (`diff_completed`)
4. **SENDING** → **IDLE** (`send_completed`)

If an error occurs at any stage, the machine transitions to **ERROR** state, where it can be retried.

## Deployment

### Systemd Service (Linux)
Create `/etc/systemd/system/git-telegram-bot.service`:
```ini
[Unit]
Description=Git-Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/git-telegram-bot
ExecStart=/path/to/git-telegram-bot/venv/bin/python main.py --config config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable git-telegram-bot
sudo systemctl start git-telegram-bot
```

### Docker
A Dockerfile is not included but can be easily created. Example:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py", "--config", "config.yaml"]
```

## Error Handling

- **Git errors**: Invalid paths, network issues, authentication problems
- **Telegram errors**: Network issues, rate limits, invalid tokens
- **File system errors**: Missing files, permission issues

All errors are logged and the state machine handles retries up to `max_retries`.

## Extending the System

### Adding New Commands
1. Add command handler method in `telegram_bot.py`
2. Register handler in `GitTelegramBot.run()`
3. Update help text

### Supporting Different Git Services
The `GitWatcher` class uses GitPython, which works with any Git repository. For specific services (GitHub, GitLab), you could extend the class to use their APIs.

### Custom Message Formats
Modify `DiffAnalyzer.format_message_for_telegram()` to change how changes are presented.

## Troubleshooting

### Bot doesn't respond
- Check that the bot token is correct
- Ensure the bot has been started with `/start` command
- Verify user ID is in `allowed_user_ids` if configured

### Repository not found
- Verify the path in config.yaml exists
- Ensure the directory is a valid Git repository
- Check file permissions

### No changes detected
- Make sure the remote branch exists
- Verify `git fetch` has permissions to access the remote
- Check that there are actually changes

## License

This project is provided as-is. Feel free to modify and adapt to your needs.