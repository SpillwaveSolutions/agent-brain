# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This is currently an empty repository with no existing codebase. When code is added, this file should be updated with:

1. **Build and Development Commands** - Once a project is initialized, document the essential commands for building, testing, and running the application
2. **Architecture Overview** - Document the high-level architecture and design patterns once the codebase structure is established

## Available Agents

Claude Code has access to specialized agents that can be invoked for specific tasks:

- **general-purpose**: Handles complex research, code searches, and multi-step tasks autonomously
- **statusline-setup**: Configures Claude Code's status line settings
- **requirements-documenter**: Creates and maintains structured product requirements documentation under docs/requirements/
- **code-quality-reviewer**: Reviews code for quality, security issues, and best practices after implementation
- **mermaid-architect**: Analyzes project architecture and creates comprehensive Mermaid diagrams for technical documentation
- **jupyter-notebook-converter**: Transforms code files and tutorials into well-structured, educational Jupyter notebooks
- **change-explainer**: Analyzes and documents code changes, providing clear explanations of modifications and their impact
- **root-cause-debugger**: Systematically debugs errors and identifies root causes of bugs or test failures
- **grammar-style-editor**: Improves grammar, clarity, and engagement of written text while preserving author voice
- **article-chapter-enhancer**: Enhances technical articles with clarity improvements and visual diagrams while maintaining accuracy
- **code-explainer**: Analyzes source files and explains complex logic for code comprehension and onboarding
- **python-expert-engineer**: Provides expert Python development assistance following best practices and PEP standards
- **qa-enforcer**: Enforces test coverage and quality standards after code modifications
- **docs-sync-editor**: Updates documentation to reflect code changes and maintain technical accuracy

## Quality Assurance Protocol

**IMPORTANT**: After ANY major code changes (including but not limited to):
- Adding new features or functionality
- Refactoring existing code
- Fixing bugs
- Modifying core business logic
- Updating dependencies or configurations

You MUST:
1. Use the `qa-enforcer` agent to enforce test coverage and quality standards
2. Run the appropriate build and test commands for the project type:
   - For Taskfile-based projects: `task clean build test`
   - For Gradle/Java projects: `./gradlew clean build test` or `gradle clean build test`
   - For Maven/Java projects: `mvn clean compile test` or `./mvnw clean compile test`
   - For NPM/Node projects: `npm run build && npm test`
   - For Python projects: `pytest` or appropriate test runner
3. Only consider the task complete after both steps pass successfully

The qa-enforcer agent automatically detects the project type and runs appropriate quality checks for Java, Python, JavaScript, TypeScript, and other languages.

This is a mandatory workflow that should be followed automatically without prompting.

## GitHub Authentication for Evinova Projects

**IMPORTANT**: When working on Evinova projects and using the `gh` CLI for GitHub operations (creating PRs, issues, etc.), ensure you're authenticated with the correct account:

```bash
# Switch to the evinova account
gh auth switch --user Rick-Hightower_evinova

# Verify authentication
gh auth status
```

This is required for GitHub API access in Evinova repositories.

## Notes

This directory appears to be a user's Claude Code working directory. When projects are added, update this file with project-specific information.