# Cline Code Review Agent

A Streamlit-based application that leverages Cline AI to perform automated code reviews on GitHub Pull Requests with a focus on Android application development.

## Overview

This tool automates the code review process by:
- Fetching Pull Request changes from GitHub
- Analyzing code differences with AI-powered insights
- Generating expert-level review comments focusing on Android best practices
- Providing feedback on performance, memory leaks, lifecycle issues, and modern Android practices

## Prerequisites

### Required Software
1. **Node.js v20+** - Required for Cline
2. **Python 3.8+** - For running the Streamlit app
3. **Cline CLI** - Install via npm:
   ```bash
   npm install -g cline
   ```

### Cline Configuration
Configure Cline with your AI provider (Anthropic, OpenAI, etc.):
```bash
cline config set
```

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd mcp-prompt/app
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your project:**
   Edit `config.json` with your GitHub project details:
   ```json
   {
       "github_project_url": "https://github.com/owner/repo",
       "pull_request_id": "123"
   }
   ```

## Usage

### Starting the Application

1. **Ensure Cline instance is running:**
   ```bash
   cline instance new --default
   ```

2. **Verify instance is active:**
   ```bash
   cline instance list
   ```
   You should see output like:
   ```
   ADDRESS (ID)      │ STATUS   │ VERSION │ ...
   127.0.0.1:52727   │ SERVING  │ 3.47.0  │ ...
   ```



3. **Launch the Streamlit app:**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser:**
   The app will automatically open at `http://localhost:8501`

### Using the Interface

1. Enter the Pull Request URL in the input field
2. Click "Start Review" button
3. Monitor the review progress in real-time
4. View generated review comments
5. Export results if needed

## 📁 Project Structure

```
app/
├── app.py              # Main Streamlit application (working version)
├── config.json         # GitHub project configuration
├── requirements.txt    # Python dependencies
└── README.md          # This file

../
└── agent_prompt.md     # AI agent instructions for code review
```

## 🔧 How It Works

### Review Process Flow

1. **Input Gathering**
   - Retrieves GitHub project URL from `config.json`
   - Gets Pull Request ID from config or user input

2. **Branch Identification**
   - Identifies the feature branch from the PR
   - Identifies the target branch (merge destination)

3. **Fetch Changes**
   - Pulls latest changes for both branches
   - Ensures local repository is up-to-date

4. **Diff Extraction**
   - Generates complete diff between branches
   - Captures all code changes

5. **Context Preservation**
   - Saves diff to `pr_changes.diff`
   - Includes full file context for analysis

6. **AI-Powered Review**
   - Analyzes code through Cline AI
   - Focuses on Android development best practices
   - Generates expert-level comments

7. **Output Generation**
   - Saves review to `review_comments.md`
   - Displays results in the UI

### Key Features

- **Automated Instance Management**: Automatically detects or creates Cline instances
- **Real-time Progress**: Live output streaming during review process
- **Rate Limit Handling**: Automatic retry with exponential backoff
- **Error Recovery**: Graceful handling of API quota and timeout issues
- **Interactive UI**: User-friendly Streamlit interface

## 🐛 Troubleshooting

### "No Cline instances found"

**Solution:**
```bash
# Create a new instance
cline instance new --default

# Verify it's running
cline instance list
```

### Instance Creation Fails

**Check Node.js version:**
```bash
node --version  # Should be v20.0.0 or higher
```

**View Cline logs:**
```bash
cline log list
tail -50 ~/.cline/logs/<latest-log-file>
```

### Kill all Cline instances
If you need to restart from a clean state:
```bash
cline instance kill -a
```

### Rate Limit Errors

The app automatically handles rate limits with:
- Automatic retry mechanism
- Exponential backoff
- Clear user feedback

If persistent, check your API quota:
```bash
cline config show
```

### Streamlit Issues

**Port already in use:**
```bash
# Use a different port
streamlit run app.py --server.port 8502
```

**Module not found:**
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

## 🔍 Configuration Details

### config.json

```json
{
    "github_project_url": "https://github.com/owner/repo",
    "pull_request_id": "123"
}
```

- `github_project_url`: Full URL to the GitHub repository
- `pull_request_id`: PR number to review

### agent_prompt.md

Contains the AI agent instructions focusing on:
- Android performance optimization
- Memory leak detection
- Lifecycle management
- Modern Android practices (Jetpack, Kotlin)
- UI/UX consistency
- Library usage and best practices

## 🛠️ Technical Implementation

### Cline Instance Management

The app uses correct Cline CLI commands:
- `cline instance new --default` - Creates new instance
- `cline instance list` - Lists active instances
- `cline instance kill <address>` - Terminates instance

**Note:** The app checks for both `localhost` and `127.0.0.1` addresses for compatibility.

### Process Execution

Uses Python subprocess with:
- Non-blocking I/O for real-time output
- Timeout handling (default: 600s)
- Error detection and retry logic
- YOLO mode (`--yolo`) for autonomous operation

## Output Files

Generated during review process:
- `pr_changes.diff` - Complete diff between branches
- `review_comments.md` - AI-generated review comments

## Contributing

To modify the review focus or add features:

1. Edit `agent_prompt.md` for different review criteria
2. Modify `app.py` for UI/workflow changes
3. Update `config.json` for different projects

## Available Cline Commands

Reference for manual operations:

```bash
# Instance management
cline instance new          # Create new instance
cline instance list         # List instances
cline instance kill <addr>  # Kill specific instance
cline instance default      # Set default instance

# Configuration
cline config show           # Display current config
cline config set            # Interactive config setup

# Logs
cline log list              # List available logs
```

## Performance Tips

1. **Reuse instances**: Don't create new instances for each review
2. **Monitor logs**: Check `~/.cline/logs/` for issues
3. **Rate limits**: Space out reviews if hitting API limits
4. **File size**: Large diffs may require increased timeout values

## Security Notes

- API keys are managed through Cline config
- Never commit API keys to version control
- Review generated comments before posting publicly

## License

[Add your license information here]

## Support

For issues related to:
- **Cline CLI**: https://github.com/cline/cline/issues
- **This application**: [Add your issue tracker]

---

**Version**: 3.0 (Stable)  
**Last Updated**: January 2026  
**Cline Version Tested**: 3.47.0
