# Scripts

This directory contains shell scripts and batch files for various automation tasks.

## Script Files

- `run_video_scorer.sh` - Linux/macOS launcher script
- `run_video_scorer.bat` - Windows batch launcher
- `run_video_scorer.ps1` - PowerShell launcher script
- `docker-entrypoint.sh` - Docker container entry point
- `validate-docker-setup.sh` - Docker setup validation
- `demo.sh` - Demo script for the application
- `demo_mining_workflow.sh` - Mining workflow demonstration
- `mine_archive.sh` - Archive mining script

## Usage

These scripts are designed to be run from the project root directory. They automatically:
- Set up virtual environments
- Install dependencies
- Load configuration files
- Launch the application with proper settings

### Examples

```bash
# From project root
./scripts/run_video_scorer.sh /path/to/media 7862
./scripts/validate-docker-setup.sh
```

### Windows

```cmd
scripts\run_video_scorer.bat "C:\path\to\media" 7862
```

```powershell
.\scripts\run_video_scorer.ps1 -Dir "C:\path\to\media" -Port 7862
```