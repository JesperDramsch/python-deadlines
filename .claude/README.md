# Claude Code Configuration

This directory contains Claude Code configuration and enhancements for the Python Deadlines project.

## Directory Structure

```
.claude/
├── settings.json       # Main configuration file with hooks and permissions
├── settings.local.json # Local overrides (not committed)
├── agents/            # Specialized agents for domain tasks
├── commands/          # Custom slash commands  
├── scripts/           # Hook scripts (pre/post actions)
├── context/           # Auto-loaded documentation
├── docs/              # Project documentation
└── README.md          # This file
```

## Features

### 🎣 Hooks (Active)
Automated actions that run before/after Claude uses tools:
- **Pre-Edit Hook** (`pre-edit-check.sh`): Warns when editing protected files
- **Post-Edit Hook** (`format-python.sh`): Auto-formats Python files, validates YAML/JSON
- **Pre-Write Hook** (`pre-write-check.sh`): Validates new file creation
- **Pre-Bash Hook** (`validate-command.sh`): Blocks dangerous commands

### 🤖 Specialized Agents
Domain-specific agents for complex tasks:
- **conference-specialist** - Conference data validation and enrichment
- **qa-guardian** - Quality assurance and testing

### 📝 Custom Commands
Slash commands for common workflows:
- `/add-conference` - Interactive conference addition
- `/validate-data` - Comprehensive data validation
- `/import-conferences` - Import from external sources
- `/newsletter` - Generate newsletter content
- `/quick-fix` - Automatic issue resolution
- `/check-deadlines` - Check upcoming CFP deadlines
- `/test-conference` - Test conference data entry

### 📚 Context Documents
Auto-loaded documentation for Claude:
- **ADHD Support** - Development support for ADHD
- **Critical Operations** - Safety guidelines and checklists
- **Git Workflow** - Branching and deployment procedures
- **Conference Schema** - Complete field reference
- **Data Pipeline** - Processing workflow details
- **Troubleshooting** - Common issues and solutions

## Configuration

### settings.json
Main configuration file that defines:
- **Permissions**: Tool access control (allow/ask/deny patterns)
- **Hooks**: Pre/post actions for tools (Edit, Write, Bash)
- **Environment**: Project-specific environment variables
- **Output Style**: Response formatting preferences
- **MCP Servers**: Integration with Model Context Protocol servers

### Permissions System
- **Allow**: Tools/commands that run without prompting
- **Ask**: Tools that require user confirmation
- **Deny**: Blocked patterns for safety

Example patterns:
```json
"allow": ["Bash(pixi run:*)", "Read", "Edit"],
"ask": ["Bash", "Write", "MultiEdit"],
"deny": ["Bash(rm -rf /)", "Read(*.key)"]
```

### Customization
To add new features:

1. **New Command**: Create `.md` file in `commands/`
2. **New Hook**: Add script in `scripts/`, update `settings.json`
3. **New Agent**: Add `.md` file in `agents/` with frontmatter
4. **New Context**: Add `.md` file in `context/` or `docs/`

## Security

### Blocked Operations
The configuration prevents:
- Destructive git operations (`git push --force`, `git reset --hard HEAD~`)
- System-wide deletions (`rm -rf /`, `rm -rf ~`)
- Insecure file permissions (`chmod 777`)
- Branch deletions (`git push origin :main`)
- Fork bombs and malicious patterns

### Protected Files
Warnings are issued when editing:
- GitHub workflow files (`.github/workflows/`)
- License files (`LICENSE`)
- Environment configuration (`.env`)
- Secret files (`*.key`, `*.pem`)
- Configuration files (`settings.json`, `CLAUDE.md`)
- Archive data (`_data/archive.yml` - auto-managed)

## Usage

Claude Code automatically loads this configuration when working in the project. No manual activation needed.

### Testing Hooks
```bash
# Test pre-command validation (should block)
./.claude/scripts/validate-command.sh "rm -rf /"

# Test pre-edit check
./.claude/scripts/pre-edit-check.sh ".github/workflows/test.yml"

# Test formatting hook
./.claude/scripts/format-python.sh "utils/test.py"

# Test pre-write check
./.claude/scripts/pre-write-check.sh "_data/new-conference.yml"
```

### MCP Servers
The project integrates with MCP servers for enhanced functionality:
- **Time**: Timezone management for conference deadlines
- **Git**: Version control operations
- **Filesystem**: Enhanced file operations
- **Memory**: Knowledge persistence
- **Context7**: Library documentation

## Maintenance

### Updating Hooks
1. Edit script in `scripts/`
2. Make executable: `chmod +x scripts/*.sh`
3. Test manually using commands above
4. Update `settings.json` hooks section

### Adding Commands
1. Create command documentation in `commands/`
2. Follow existing template structure
3. Test with Claude Code
4. Document in this README

### Adding Agents
1. Create agent file in `agents/`
2. Add frontmatter with name, description, tools
3. Define agent personality and workflows
4. Test agent invocation

## Best Practices

1. **Keep hooks fast** - They run on every tool use
2. **Make hooks safe** - Always exit 0 unless blocking critical operations
3. **Document commands** - Include examples and options
4. **Update context** - Keep documentation current
5. **Test changes** - Verify hooks work before committing

## Troubleshooting

### Hooks Not Running
- Check `settings.json` syntax with `json` validator
- Verify script permissions: `chmod +x scripts/*.sh`
- Check hook configuration in settings.json
- Enable hooks: `"disableAllHooks": false`

### Command Not Found
- Ensure `.md` file exists in `commands/`
- Check file naming matches command name
- Restart Claude Code session
- Verify command documentation format

### MCP Server Issues
- Check server connectivity: `claude mcp list`
- Verify `enableAllProjectMcpServers: true`
- Check specific server configuration
- Review server logs for errors

## Project-Specific Features

### Conference Data Validation
- Automatic validation when editing `_data/conferences.yml`
- Timezone verification for conference locations
- HTTPS URL enforcement
- Date logic validation (cfp < start < end)

### Python Development
- Auto-formatting with ruff on save
- Linting and type checking integration
- Test runner integration with pytest
- Pixi environment management

### ADHD Support
- Task breakdown with TodoWrite
- Energy management reminders
- Focus patterns for common tasks
- Break reminders at intervals

## Contributing

To improve Claude Code configuration:
1. Test changes locally
2. Document new features
3. Update this README
4. Submit PR with examples

For issues or suggestions, create an issue in the repository.