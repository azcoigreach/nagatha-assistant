#!/bin/bash

# Voice Dependencies Installation Script for Nagatha Assistant
# This script installs the required dependencies for voice features

set -e

echo "🎤 Installing Voice Dependencies for Nagatha Assistant"
echo "=================================================="

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment. Consider activating one first."
    echo "   You can create one with: python -m venv venv && source venv/bin/activate"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install system dependencies
install_system_deps() {
    echo "📦 Installing system dependencies..."
    
    if command_exists apt-get; then
        # Ubuntu/Debian
        echo "Detected Ubuntu/Debian system"
        sudo apt-get update
        sudo apt-get install -y ffmpeg python3-dev build-essential
    elif command_exists brew; then
        # macOS
        echo "Detected macOS system"
        brew install ffmpeg
    elif command_exists pacman; then
        # Arch Linux
        echo "Detected Arch Linux system"
        sudo pacman -S ffmpeg python-pip
    elif command_exists dnf; then
        # Fedora
        echo "Detected Fedora system"
        sudo dnf install -y ffmpeg python3-devel gcc
    else
        echo "⚠️  Could not detect package manager. Please install FFmpeg manually:"
        echo "   Visit: https://ffmpeg.org/download.html"
        read -p "Continue with Python dependencies? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to install Python dependencies
install_python_deps() {
    echo "🐍 Installing Python dependencies..."
    
    # Upgrade pip first
    python -m pip install --upgrade pip
    
    # Install voice dependencies
    echo "Installing PyNaCl (Discord voice support)..."
    python -m pip install PyNaCl
    
    echo "Installing ffmpeg-python (audio processing)..."
    python -m pip install ffmpeg-python
    
    echo "Installing openai-whisper (speech recognition)..."
    python -m pip install openai-whisper
    
    # Also install the updated requirements.txt
    echo "Installing updated requirements.txt..."
    python -m pip install -r requirements.txt
}

# Function to verify installation
verify_installation() {
    echo "🔍 Verifying installation..."
    
    # Check FFmpeg
    if command_exists ffmpeg; then
        echo "✅ FFmpeg is installed"
        ffmpeg -version | head -n 1
    else
        echo "❌ FFmpeg not found. Please install manually."
        return 1
    fi
    
    # Check Python packages
    echo "Checking Python packages..."
    python -c "import nacl; print('✅ PyNaCl installed')" 2>/dev/null || echo "❌ PyNaCl not found"
    python -c "import ffmpeg; print('✅ ffmpeg-python installed')" 2>/dev/null || echo "❌ ffmpeg-python not found"
    python -c "import whisper; print('✅ openai-whisper installed')" 2>/dev/null || echo "❌ openai-whisper not found"
    
    echo ""
    echo "🎉 Voice dependencies installation complete!"
}

# Function to setup environment variables
setup_env() {
    echo ""
    echo "🔧 Environment Setup"
    echo "==================="
    
    # Check for .env file
    if [[ -f ".env" ]]; then
        echo "Found existing .env file"
    else
        echo "Creating .env file from template..."
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            echo "✅ Created .env file from template"
        else
            echo "⚠️  No .env.example found. Please create .env file manually."
        fi
    fi
    
    echo ""
    echo "📝 Required Environment Variables:"
    echo "   DISCORD_BOT_TOKEN=your_discord_bot_token"
    echo "   OPENAI_API_KEY=your_openai_api_key"
    echo ""
    echo "You can set these in your .env file or export them:"
    echo "   export DISCORD_BOT_TOKEN='your_token'"
    echo "   export OPENAI_API_KEY='your_key'"
}

# Function to show next steps
show_next_steps() {
    echo ""
    echo "🚀 Next Steps"
    echo "============="
    echo "1. Set up your Discord bot token:"
    echo "   export DISCORD_BOT_TOKEN='your_bot_token'"
    echo ""
    echo "2. Set up your OpenAI API key:"
    echo "   export OPENAI_API_KEY='your_openai_key'"
    echo ""
    echo "3. Start Nagatha with voice support:"
    echo "   nagatha discord start"
    echo ""
    echo "4. Use voice commands in Discord:"
    echo "   /join - Join a voice channel"
    echo "   /voice-status - Check voice capabilities"
    echo "   /leave - Leave voice channel"
    echo ""
    echo "📚 For more information, see: docs/VOICE_FEATURES.md"
}

# Main installation flow
main() {
    echo "This script will install the required dependencies for Nagatha's voice features."
    echo ""
    echo "Dependencies to be installed:"
    echo "• FFmpeg (audio processing)"
    echo "• PyNaCl (Discord voice support)"
    echo "• ffmpeg-python (Python audio interface)"
    echo "• openai-whisper (speech recognition)"
    echo ""
    
    read -p "Continue with installation? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    
    # Install system dependencies
    install_system_deps
    
    # Install Python dependencies
    install_python_deps
    
    # Verify installation
    verify_installation
    
    # Setup environment
    setup_env
    
    # Show next steps
    show_next_steps
}

# Run main function
main "$@" 