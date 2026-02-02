Implement the following plan:                                                                                                
                                                                                                                               
  # Plan: Release Automation with GitHub Actions and Claude Code Skill                                                         
                                                                                                                               
  ## Objective                                                                                                                 
                                                                                                                               
  Create automated release infrastructure for Agent Brain:                                                                     
  1. **GitHub Action** (`publish-to-pypi.yml`) - Deploys to PyPI on release creation                                           
  2. **Claude Code Skill** (`/agent-brain-release`) - Automates version bump, changelog, and release creation                  
                                                                                                                               
  ## Current State                                                                                                             
                                                                                                                               
  - **Repository**: SpillwaveSolutions/agent-brain (monorepo)                                                                  
  - **Packages**:                                                                                                              
  - `agent-brain-rag` (server) - https://pypi.org/project/agent-brain-rag/                                                     
  - `agent-brain-cli` (CLI) - https://pypi.org/project/agent-brain-cli/                                                        
  - **Current version**: v1.2.0                                                                                                
  - **Existing workflow**: Only `pr-qa-gate.yml` (no release automation)                                                       
  - **Version locations**: 4 files (2 pyproject.toml + 2 __init__.py)                                                          
                                                                                                                               
  ---                                                                                                                          
                                                                                                                               
  ## Deliverables                                                                                                              
                                                                                                                               
  ### 1. GitHub Action: `.github/workflows/publish-to-pypi.yml`                                                                
                                                                                                                               
  **Trigger**: `on: release: types: [published]`                                                                               
                                                                                                                               
  **Jobs**:                                                                                                                    
  1. `quality-gate` - Run lint, typecheck, tests before publishing                                                             
  2. `publish-server` - Build and publish `agent-brain-rag` to PyPI                                                            
  3. `publish-cli` - Build and publish `agent-brain-cli` to PyPI                                                               
                                                                                                                               
  **Key Features**:                                                                                                            
  - Uses PyPI Trusted Publisher (OIDC) - no API tokens needed                                                                  
  - Parallel package publishing after quality gate                                                                             
  - GitHub environment protection (`pypi`)                                                                                     
                                                                                                                               
  ### 2. Claude Code Skill: `.claude/skills/agent-brain-release/`                                                              
                                                                                                                               
  **Command**: `/agent-brain-release <bump> [--dry-run]`                                                                       
  - `bump`: major | minor | patch                                                                                              
  - `--dry-run`: Preview without executing                                                                                     
                                                                                                                               
  **Process**:                                                                                                                 
  1. Validate pre-conditions (clean repo, on main, synced)                                                                     
  2. Calculate new version from bump type                                                                                      
  3. Update 4 version files                                                                                                    
  4. Generate release notes from commits                                                                                       
  5. Commit, tag, push                                                                                                         
  6. Create GitHub release (triggers PyPI publish)                                                                             
                                                                                                                               
  ---                                                                                                                          
                                                                                                                               
  ## Files to Create                                                                                                           
                                                                                                                               
  | File | Purpose |                                                                                                           
  |------|---------|                                                                                                           
  | `.github/workflows/publish-to-pypi.yml` | PyPI deployment on release |                                                     
  | `.claude/skills/agent-brain-release/SKILL.md` | Main skill file |                                                          
  | `.claude/commands/agent-brain-release.md` | Command definition |                                                           
  | `.claude/skills/agent-brain-release/references/version-management.md` | Version file reference |                           
  | `.claude/skills/agent-brain-release/references/pypi-setup.md` | OIDC setup guide |                                         
                                                                                                                               
  ## Files to Update (PyPI Marketing)                                                                                          
                                                                                                                               
  Both README files need enhancement for better PyPI pages:                                                                    
                                                                                                                               
  | File | Updates Needed |                                                                                                    
  |------|----------------|                                                                                                    
  | `agent-brain-server/README.md` | Marketing copy, wiki links, release history link |                                        
  | `agent-brain-cli/README.md` | Marketing copy, wiki links, release history link |                                           
                                                                                                                               
  ### README Enhancement Requirements                                                                                          
                                                                                                                               
  Both README files should include:                                                                                            
                                                                                                                               
  1. **History/Rename Note**:                                                                                                  
  > Agent Brain (formerly doc-serve) is an intelligent document indexing and semantic search system designed to give AI        
  agents long-term memory.                                                                                                     
                                                                                                                               
  2. **Search Capabilities Section**:                                                                                          
  - **Semantic Search (Vector Index)**: Natural language queries using OpenAI embeddings                                       
  - **Keyword Search (BM25)**: Traditional keyword matching with TF-IDF ranking                                                
  - **GraphRAG**: Knowledge graph-based retrieval for relationship-aware queries                                               
  - **Hybrid Search**: Combines vector + BM25 for best of both worlds                                                          
                                                                                                                               
  3. **Why This Matters**:                                                                                                     
  > AI agents need persistent memory to be truly useful. Agent Brain provides the retrieval infrastructure that enables        
  context-aware, knowledge-grounded AI interactions.                                                                           
                                                                                                                               
  4. **Documentation Links**:                                                                                                  
  - User Guide: https://github.com/SpillwaveSolutions/agent-brain/wiki/User-Guide                                              
  - Developer Guide: https://github.com/SpillwaveSolutions/agent-brain/wiki/Developer-Guide                                    
  - API Reference: https://github.com/SpillwaveSolutions/agent-brain/wiki/API-Reference                                        
                                                                                                                               
  5. **Release Information**:                                                                                                  
  - Current Version: vX.Y.Z                                                                                                    
  - Release Notes: https://github.com/SpillwaveSolutions/agent-brain/releases                                                  
  - Changelog: https://github.com/SpillwaveSolutions/agent-brain/releases/latest                                               
                                                                                                                               
  ### Skill Responsibility                                                                                                     
                                                                                                                               
  The `/agent-brain-release` skill should:                                                                                     
  - Prompt to update README version references if significant changes                                                          
  - Include links to the new release in generated release notes                                                                
  - Remind user to sync wiki documentation if API changes                                                                      
                                                                                                                               
  ## Files to Modify (by skill at runtime)                                                                                     
                                                                                                                               
  | File | Change |                                                                                                            
  |------|--------|                                                                                                            
  | `agent-brain-server/pyproject.toml` | Version bumped by skill |                                                            
  | `agent-brain-server/agent_brain_server/__init__.py` | Version bumped by skill |                                            
  | `agent-brain-cli/pyproject.toml` | Version bumped by skill |                                                               
  | `agent-brain-cli/agent_brain_cli/__init__.py` | Version bumped by skill |                                                  
                                                                                                                               
  ---                                                                                                                          
                                                                                                                               
  ## Implementation Details                                                                                                    
                                                                                                                               
  ### GitHub Action Structure                                                                                                  
                                                                                                                               
  ```yaml                                                                                                                      
  name: Publish to PyPI                                                                                                        
                                                                                                                               
  on:                                                                                                                          
  release:                                                                                                                     
  types: [published]                                                                                                           
                                                                                                                               
  permissions:                                                                                                                 
  contents: read                                                                                                               
  id-token: write  # OIDC for PyPI                                                                                             
                                                                                                                               
  jobs:                                                                                                                        
  quality-gate:                                                                                                                
  runs-on: ubuntu-latest                                                                                                       
  steps:                                                                                                                       
  - uses: actions/checkout@v4                                                                                                  
  - uses: actions/setup-python@v5                                                                                              
  with:                                                                                                                        
  python-version: '3.11'                                                                                                       
  - uses: arduino/setup-task@v2                                                                                                
  with:                                                                                                                        
  version: 3.43.3                                                                                                              
  - uses: snok/install-poetry@v1                                                                                               
  with:                                                                                                                        
  version: 1.7.1                                                                                                               
  - run: task install                                                                                                          
  - run: task lint                                                                                                             
  - run: task typecheck                                                                                                        
  - run: task test                                                                                                             
                                                                                                                               
  publish-server:                                                                                                              
  needs: quality-gate                                                                                                          
  runs-on: ubuntu-latest                                                                                                       
  environment: pypi                                                                                                            
  steps:                                                                                                                       
  - uses: actions/checkout@v4                                                                                                  
  - uses: snok/install-poetry@v1                                                                                               
  with:                                                                                                                        
  version: 1.7.1                                                                                                               
  - run: poetry build                                                                                                          
  working-directory: agent-brain-server                                                                                        
  - uses: pypa/gh-action-pypi-publish@release/v1                                                                               
  with:                                                                                                                        
  packages-dir: agent-brain-server/dist/                                                                                       
                                                                                                                               
  publish-cli:                                                                                                                 
  needs: quality-gate                                                                                                          
  runs-on: ubuntu-latest                                                                                                       
  environment: pypi                                                                                                            
  steps:                                                                                                                       
  - uses: actions/checkout@v4                                                                                                  
  - uses: snok/install-poetry@v1                                                                                               
  with:                                                                                                                        
  version: 1.7.1                                                                                                               
  - run: poetry build                                                                                                          
  working-directory: agent-brain-cli                                                                                           
  - uses: pypa/gh-action-pypi-publish@release/v1                                                                               
  with:                                                                                                                        
  packages-dir: agent-brain-cli/dist/                                                                                          
  ```                                                                                                                          
                                                                                                                               
  ### Skill Release Process                                                                                                    
                                                                                                                               
  ```                                                                                                                          
  /agent-brain-release minor                                                                                                   
                                                                                                                               
  [1/8] Validating pre-conditions...                                                                                           
  Working directory: clean ✓                                                                                                   
  Branch: main ✓                                                                                                               
  Remote sync: up to date ✓                                                                                                    
                                                                                                                               
  [2/8] Calculating version...                                                                                                 
  Current: 1.2.0 → New: 1.3.0                                                                                                  
                                                                                                                               
  [3/8] Updating version files...                                                                                              
  4 files updated ✓                                                                                                            
                                                                                                                               
  [4/8] Generating release notes...                                                                                            
  Found 12 commits since v1.2.0                                                                                                
                                                                                                                               
  [5/8] Committing version bump...                                                                                             
  chore(release): bump version to 1.3.0                                                                                        
                                                                                                                               
  [6/8] Creating git tag...                                                                                                    
  Tag: v1.3.0                                                                                                                  
                                                                                                                               
  [7/8] Pushing to remote...                                                                                                   
  Branch and tag pushed ✓                                                                                                      
                                                                                                                               
  [8/8] Creating GitHub release...                                                                                             
  https://github.com/SpillwaveSolutions/agent-brain/releases/tag/v1.3.0                                                        
                                                                                                                               
  ✓ Release complete! PyPI publish triggered automatically.                                                                    
                                                                                                                               
  PyPI packages (available in ~5 minutes):                                                                                     
  https://pypi.org/project/agent-brain-rag/1.3.0/                                                                              
  https://pypi.org/project/agent-brain-cli/1.3.0/                                                                              
                                                                                                                               
  Install:                                                                                                                     
  pip install agent-brain-rag==1.3.0                                                                                           
  pip install agent-brain-cli==1.3.0                                                                                           
  ```                                                                                                                          
                                                                                                                               
  ### Release Notes Template                                                                                                   
                                                                                                                               
  ```markdown                                                                                                                  
  ## What's Changed                                                                                                            
                                                                                                                               
  ### Features                                                                                                                 
  - feat: description (#PR)                                                                                                    
                                                                                                                               
  ### Bug Fixes                                                                                                                
  - fix: description (#PR)                                                                                                     
                                                                                                                               
  ### Documentation                                                                                                            
  - docs: description (#PR)                                                                                                    
                                                                                                                               
  ## About Agent Brain                                                                                                         
                                                                                                                               
  Agent Brain (formerly doc-serve) provides intelligent document indexing and semantic search for AI agents:                   
                                                                                                                               
  - **Semantic Search**: Natural language queries via OpenAI embeddings                                                        
  - **Keyword Search (BM25)**: Traditional keyword matching with TF-IDF                                                        
  - **GraphRAG**: Knowledge graph retrieval for relationship-aware queries                                                     
  - **Hybrid Search**: Best of vector + keyword approaches                                                                     
                                                                                                                               
  ## PyPI Packages                                                                                                             
                                                                                                                               
  - **agent-brain-rag**: https://pypi.org/project/agent-brain-rag/X.Y.Z/                                                       
  - **agent-brain-cli**: https://pypi.org/project/agent-brain-cli/X.Y.Z/                                                       
                                                                                                                               
  ## Installation                                                                                                              
                                                                                                                               
  ```bash                                                                                                                      
  pip install agent-brain-rag==X.Y.Z agent-brain-cli==X.Y.Z                                                                    
  ```                                                                                                                          
                                                                                                                               
  ## Documentation                                                                                                             
                                                                                                                               
  - [User Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/User-Guide)                                            
  - [Developer Guide](https://github.com/SpillwaveSolutions/agent-brain/wiki/Developer-Guide)                                  
  - [All Releases](https://github.com/SpillwaveSolutions/agent-brain/releases)                                                 
                                                                                                                               
  **Full Changelog**: https://github.com/SpillwaveSolutions/agent-brain/compare/vPREV...vNEW                                   
  ```                                                                                                                          
                                                                                                                               
  ---                                                                                                                          
                                                                                                                               
  ## PyPI Trusted Publisher Setup (Manual, One-Time)                                                                           
                                                                                                                               
  After creating the workflow, configure OIDC in PyPI. This must be done for BOTH packages.                                    
                                                                                                                               
  ### Step-by-Step: Configure agent-brain-rag                                                                                  
                                                                                                                               
  1. **Log in to PyPI**: https://pypi.org/account/login/                                                                       
                                                                                                                               
  2. **Navigate to project publishing settings**:                                                                              
  - Go to: https://pypi.org/manage/project/agent-brain-rag/settings/publishing/                                                
  - Or: Your Projects → agent-brain-rag → Settings → Publishing                                                                
                                                                                                                               
  3. **Add a new trusted publisher**:                                                                                          
  - Click "Add a new publisher"                                                                                                
  - Select "GitHub Actions"                                                                                                    
                                                                                                                               
  4. **Fill in the form**:                                                                                                     
  | Field | Value |                                                                                                            
  |-------|-------|                                                                                                            
  | Owner | `SpillwaveSolutions` |                                                                                             
  | Repository name | `agent-brain` |                                                                                          
  | Workflow name | `publish-to-pypi.yml` |                                                                                    
  | Environment name | `pypi` |                                                                                                
                                                                                                                               
  5. **Click "Add"** to save the trusted publisher                                                                             
                                                                                                                               
  ### Step-by-Step: Configure agent-brain-cli                                                                                  
                                                                                                                               
  1. **Navigate to project publishing settings**:                                                                              
  - Go to: https://pypi.org/manage/project/agent-brain-cli/settings/publishing/                                                
                                                                                                                               
  2. **Add a new trusted publisher** with same values:                                                                         
  | Field | Value |                                                                                                            
  |-------|-------|                                                                                                            
  | Owner | `SpillwaveSolutions` |                                                                                             
  | Repository name | `agent-brain` |                                                                                          
  | Workflow name | `publish-to-pypi.yml` |                                                                                    
  | Environment name | `pypi` |                                                                                                
                                                                                                                               
  3. **Click "Add"** to save                                                                                                   
                                                                                                                               
  ### Step-by-Step: Create GitHub Environment                                                                                  
                                                                                                                               
  1. **Go to repository settings**:                                                                                            
  - https://github.com/SpillwaveSolutions/agent-brain/settings/environments                                                    
                                                                                                                               
  2. **Create new environment**:                                                                                               
  - Click "New environment"                                                                                                    
  - Name: `pypi`                                                                                                               
  - Click "Configure environment"                                                                                              
                                                                                                                               
  3. **Optional protections** (recommended for production):                                                                    
  - Enable "Required reviewers" - add yourself                                                                                 
  - Enable "Deployment branches" - select "main" only                                                                          
                                                                                                                               
  4. **Click "Save protection rules"**                                                                                         
                                                                                                                               
  ### Verification                                                                                                             
                                                                                                                               
  After setup, verify by checking:                                                                                             
  - PyPI shows "Trusted Publishers" configured for both packages                                                               
  - GitHub shows `pypi` environment in repository settings                                                                     
  - First release will test the OIDC authentication                                                                            
                                                                                                                               
  ---                                                                                                                          
                                                                                                                               
  ## Verification                                                                                                              
                                                                                                                               
  1. **GitHub Action**: Create test release, verify both packages published to PyPI                                            
  2. **Skill**: Run `/agent-brain-release patch --dry-run` to preview                                                          
  3. **End-to-end**: Full release cycle with actual version bump                                                               
  4. **PyPI**: Verify packages at:                                                                                             
  - https://pypi.org/project/agent-brain-rag/                                                                                  
  - https://pypi.org/project/agent-brain-cli/                                                                                  
                                                                                                                               
  ---                                                                                                                          
                                                                                                                               
  ## Success Criteria                                                                                                          
                                                                                                                               
  - [ ] GitHub Action triggers on release and publishes both packages                                                          
  - [ ] OIDC authentication works (no API tokens)                                                                              
  - [ ] Skill creates proper version bumps across all 4 files                                                                  
  - [ ] Release notes include PyPI package links and wiki documentation links                                                  
  - [ ] GitHub release created with proper changelog                                                                           
  - [ ] README files updated with marketing copy, search capabilities, wiki links                                              
  - [ ] PyPI pages show enhanced descriptions with documentation links                                                         
                                                                                                                               
                                                                                                                               
  If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you         
  generated), read the full transcript at: /Users/richardhightower/.claude/projects/-Users-richardhightower-clients-spillw     
  ave-src-doc-serve/453ae221-504d-400e-8dc9-e9ba896a9581.jsonl                 