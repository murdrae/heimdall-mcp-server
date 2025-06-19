#!/bin/bash
# Setup MCP server for Claude Code integration
# This script automates the setup of the Cognitive Memory MCP Server for Claude Code

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Main setup function
main() {
    echo -e "${BLUE}🧠 Setting up Cognitive Memory MCP Server for Claude Code...${NC}"
    echo ""

    # 1. Verify cognitive memory system is installed
    info "Checking cognitive memory system installation..."
    if ! command -v memory_system &> /dev/null; then
        error "Cognitive memory system not found. Please install first:"
        echo "   pip install -e ."
        exit 1
    fi
    success "Cognitive memory system found"

    # 2. Check if we're in the right directory (should contain setup.py or pyproject.toml)
    if [[ ! -f "setup.py" && ! -f "pyproject.toml" ]]; then
        warning "Not in cognitive memory project directory. Continuing anyway..."
    fi

    # 3. Start required services
    info "Starting Qdrant vector database..."
    if memory_system qdrant start; then
        success "Qdrant started successfully"
    else
        error "Failed to start Qdrant. Please check the logs and try again."
        exit 1
    fi

    # Give Qdrant a moment to fully start
    sleep 2

    # 4. Verify system health
    info "Checking system health..."
    if memory_system doctor --json > /dev/null 2>&1; then
        success "System health check passed"
    else
        warning "System health check had issues. Continuing with setup..."
        echo "   Run 'memory_system doctor' for details"
    fi

    # 5. Check if Claude CLI is available
    info "Checking for Claude CLI..."
    if ! command -v claude &> /dev/null; then
        error "Claude CLI not found. Please install Claude Code first."
        echo "   Visit: https://claude.ai/code for installation instructions"
        exit 1
    fi
    success "Claude CLI found"

    # 6. Get current working directory for absolute paths
    CURRENT_DIR="$(pwd)"

    # 7. Add the cognitive-memory MCP server using Claude CLI
    info "Adding cognitive-memory MCP server to Claude Code..."

    # Use Claude CLI to add MCP server with proper syntax
    # Format: claude mcp add [-e VAR=value] [--scope local|project|user] <name> <command> [args...]
    if claude mcp add -e QDRANT_URL=http://localhost:6333 -e PYTHONPATH="$CURRENT_DIR" --scope user cognitive-memory memory_system serve mcp; then
        success "Successfully added cognitive-memory MCP server to Claude Code"

        # Verify the server was added
        info "Verifying MCP server configuration..."
        if claude mcp get cognitive-memory >/dev/null 2>&1; then
            success "MCP server configuration verified"
        else
            warning "MCP server added but verification failed"
        fi
    else
        error "Failed to add MCP server using Claude CLI"

        # Provide manual instructions as fallback
        echo ""
        echo -e "${YELLOW}Manual Configuration Instructions:${NC}"
        echo "Run this command to add the MCP server:"
        echo "  claude mcp add -e QDRANT_URL=http://localhost:6333 -e PYTHONPATH=\"$CURRENT_DIR\" --scope user cognitive-memory memory_system serve mcp"
        echo ""
        echo "To verify it was added:"
        echo "  claude mcp list"
        echo "  claude mcp get cognitive-memory"
        echo ""

        # Ask user if they want to continue or exit
        read -p "Continue with setup anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            warning "Setup aborted by user"
            exit 1
        fi
    fi

    # 8. Test MCP server functionality
    info "Testing MCP server functionality..."

    # Test if MCP server command exists and shows help
    if memory_system serve mcp --help > /dev/null 2>&1; then
        success "MCP server command is functional"
    else
        warning "MCP server command test failed. Please verify installation."
    fi

    # 9. Show current MCP server configuration
    info "Current MCP server configuration:"
    if command -v claude &> /dev/null && claude mcp list > /dev/null 2>&1; then
        claude mcp list | grep -E "(cognitive-memory|Name)" || echo "   No MCP servers configured yet"
    else
        warning "Unable to list MCP servers"
    fi

    # 12. Display setup completion
    echo ""
    success "Setup complete! Claude Code MCP integration is ready."
    echo ""

    # 13. Display configuration summary
    echo -e "${BLUE}📋 Configuration Summary:${NC}"
    echo "   MCP Server: cognitive-memory"
    echo "   Command: memory_system serve mcp"
    echo "   Qdrant URL: http://localhost:6333"
    echo "   Working directory: $CURRENT_DIR"
    echo ""

    # 14. Display available tools
    echo -e "${BLUE}🔧 Available MCP Tools in Claude Code:${NC}"
    echo "   • store_memory - Store experiences and knowledge"
    echo "   • recall_memories - Retrieve relevant memories"
    echo "   • session_lessons - Record key learnings"
    echo "   • memory_status - Check system health"
    echo ""

    # 15. Display usage examples
    echo -e "${BLUE}💡 Usage Examples:${NC}"
    echo "   'Store this debugging insight...' → Uses store_memory automatically"
    echo "   'What do I know about React performance?' → Uses recall_memories"
    echo "   'Record lesson: Always check network tab first when debugging APIs' → Uses session_lessons"
    echo "   'Show memory system status' → Uses memory_status"
    echo ""

    # 16. Display next steps
    echo -e "${BLUE}🚀 Next Steps:${NC}"
    echo "   1. Test the MCP server: 'claude mcp get cognitive-memory'"
    echo "   2. Start a Claude Code session and test the cognitive memory tools"
    echo "   3. Use 'memory_system doctor' to verify system health anytime"
    echo "   4. Use 'memory_system qdrant status' to check Qdrant service"
    echo ""

    # 17. Display troubleshooting
    echo -e "${BLUE}🔧 Troubleshooting:${NC}"
    echo "   • List MCP servers: 'claude mcp list'"
    echo "   • Get server details: 'claude mcp get cognitive-memory'"
    echo "   • Check Qdrant status: 'memory_system qdrant status'"
    echo "   • System health check: 'memory_system doctor --verbose'"
    echo "   • Restart Qdrant: 'memory_system qdrant stop && memory_system qdrant start'"
    echo "   • Remove MCP server: 'claude mcp remove cognitive-memory'"
    echo "   • Re-add MCP server: 'claude mcp add -e QDRANT_URL=http://localhost:6333 -e PYTHONPATH=\"$(pwd)\" --scope user cognitive-memory memory_system serve mcp'"
    echo ""

    success "🎉 Cognitive Memory MCP Server setup completed successfully!"
}

# Handle interrupts gracefully
trap 'echo ""; warning "Setup interrupted by user"; exit 130' INT

# Run main function
main "$@"
