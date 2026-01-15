import { describe, it } from 'node:test';
import assert from 'node:assert';
import { spawn } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HANDLER_PATH = join(__dirname, '..', 'scripts', 'fx-handler.js');

/**
 * Helper to run the handler with stdin input
 */
function runHandler(input) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', [HANDLER_PATH], {
      env: { ...process.env, CLAUDE_PLUGIN_ROOT: join(__dirname, '..') }
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => { stdout += data; });
    child.stderr.on('data', (data) => { stderr += data; });

    child.on('close', (code) => {
      resolve({ code, stdout, stderr });
    });

    child.on('error', reject);

    child.stdin.write(JSON.stringify(input));
    child.stdin.end();
  });
}

describe('fx-handler', () => {
  it('should exit cleanly with valid PreToolUse event', async () => {
    const result = await runHandler({
      hook_event_name: 'PreToolUse',
      tool_name: 'Write',
      tool_input: { file_path: '/test/file.js' }
    });
    assert.strictEqual(result.code, 0);
  });

  it('should exit cleanly with valid Stop event', async () => {
    const result = await runHandler({
      hook_event_name: 'Stop'
    });
    assert.strictEqual(result.code, 0);
  });

  it('should exit cleanly with invalid JSON', async () => {
    const child = spawn('node', [HANDLER_PATH], {
      env: { ...process.env, CLAUDE_PLUGIN_ROOT: join(__dirname, '..') }
    });

    const result = await new Promise((resolve) => {
      child.on('close', (code) => resolve({ code }));
      child.stdin.write('not valid json');
      child.stdin.end();
    });

    assert.strictEqual(result.code, 0);
  });

  it('should handle empty stdin', async () => {
    const child = spawn('node', [HANDLER_PATH], {
      env: { ...process.env, CLAUDE_PLUGIN_ROOT: join(__dirname, '..') }
    });

    const result = await new Promise((resolve) => {
      child.on('close', (code) => resolve({ code }));
      child.stdin.end();
    });

    assert.strictEqual(result.code, 0);
  });
});
