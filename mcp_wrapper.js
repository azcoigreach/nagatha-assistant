#!/usr/bin/env node

// Ensure JSON is available globally
if (typeof global !== 'undefined') {
    global.json = JSON;
}

// Forward all arguments to the original command
const { spawn } = require('child_process');
const args = process.argv.slice(2);

if (args.length === 0) {
    console.error('Usage: node mcp_wrapper.js <command> [args...]');
    process.exit(1);
}

const command = args[0];
const commandArgs = args.slice(1);

const child = spawn(command, commandArgs, {
    stdio: 'inherit',
    env: {
        ...process.env,
        json: JSON.stringify(JSON)
    }
});

child.on('close', (code) => {
    process.exit(code);
});

child.on('error', (err) => {
    console.error('Failed to start subprocess:', err);
    process.exit(1);
}); 