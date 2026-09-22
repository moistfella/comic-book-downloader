#!/bin/bash
echo "Checking prerequisites..."

if ! command -v git >/dev/null 2>&1; then
    echo "Error: Git is not installed or not in PATH."
    echo "Please install Git using your package manager (e.g. sudo apt install git or sudo pacman -S git)"
    exit 1
fi

if [ ! -d ".git" ]; then
    echo "Error: Not a Git repository."
    exit 1
fi

echo "Pulling latest changes from GitHub..."
git pull
if [ $? -eq 0 ]; then
    echo ""
    echo "Update complete!"
    echo "Enjoy using the new version of Comic Book Downloader!"
    echo ""
else
    echo ""
    echo "Update failed. Please check the error message above."
    echo ""
fi
