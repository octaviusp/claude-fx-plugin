#!/usr/bin/env node
/**
 * Claude FX Plugin - Main Hook Handler
 *
 * Receives Claude Code hook events via stdin and triggers visual/audio effects.
 * Runs as a subprocess spawned by Claude Code hooks.
 */

import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || join(__dirname, '..');

/**
 * Load configuration from config.json
 */
function loadConfig() {
  const configPath = join(PLUGIN_ROOT, 'config.json');
  if (existsSync(configPath)) {
    return JSON.parse(readFileSync(configPath, 'utf-8'));
  }
  return {
    theme: 'default',
    volume: 0.5,
    overlay: {
      enabled: true,
      position: 'bottom-right',
      size: 200,
      duration: 2000
    },
    audio: {
      enabled: true
    }
  };
}

/**
 * Load theme manifest
 */
function loadTheme(themeName) {
  const themePath = join(PLUGIN_ROOT, 'themes', themeName, 'manifest.json');
  if (existsSync(themePath)) {
    return JSON.parse(readFileSync(themePath, 'utf-8'));
  }
  return null;
}

/**
 * Get effect mapping for an event
 */
function getEffect(theme, eventName, toolName) {
  if (!theme?.effects) return null;

  // Check for tool-specific effect first
  if (toolName && theme.effects[`${eventName}:${toolName}`]) {
    return theme.effects[`${eventName}:${toolName}`];
  }

  // Fall back to general event effect
  return theme.effects[eventName] || null;
}

/**
 * Play audio file using system player
 */
function playAudio(audioPath, volume) {
  if (!existsSync(audioPath)) return;

  // macOS: afplay, Linux: aplay/paplay, Windows: powershell
  const platform = process.platform;
  let cmd, args;

  if (platform === 'darwin') {
    cmd = 'afplay';
    args = ['-v', String(volume), audioPath];
  } else if (platform === 'linux') {
    cmd = 'paplay';
    args = ['--volume', String(Math.floor(volume * 65536)), audioPath];
  } else if (platform === 'win32') {
    cmd = 'powershell';
    args = ['-c', `(New-Object Media.SoundPlayer '${audioPath}').PlaySync()`];
  } else {
    return;
  }

  const child = spawn(cmd, args, {
    detached: true,
    stdio: 'ignore'
  });
  child.unref();
}

/**
 * Display overlay using native notification or terminal
 */
function showOverlay(config, imagePath, message) {
  if (!config.overlay.enabled) return;

  // For now, use native notifications as overlay
  // TODO: Implement proper transparent overlay window
  const platform = process.platform;

  if (platform === 'darwin') {
    const script = `display notification "${message}" with title "Claude FX"`;
    spawn('osascript', ['-e', script], {
      detached: true,
      stdio: 'ignore'
    }).unref();
  } else if (platform === 'linux') {
    spawn('notify-send', ['Claude FX', message], {
      detached: true,
      stdio: 'ignore'
    }).unref();
  }
}

/**
 * Main handler
 */
async function main() {
  // Read hook input from stdin
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk;
  }

  let hookData;
  try {
    hookData = JSON.parse(input);
  } catch {
    // Silent fail - not valid JSON
    process.exit(0);
  }

  const eventName = hookData.hook_event_name || hookData.event || 'Unknown';
  const toolName = hookData.tool_name || hookData.toolName || null;

  const config = loadConfig();
  const theme = loadTheme(config.theme);

  if (!theme) {
    // No theme loaded, exit silently
    process.exit(0);
  }

  const effect = getEffect(theme, eventName, toolName);

  if (!effect) {
    process.exit(0);
  }

  // Trigger effects
  const themePath = join(PLUGIN_ROOT, 'themes', config.theme);

  if (config.audio.enabled && effect.sound) {
    const audioPath = join(themePath, 'sounds', effect.sound);
    playAudio(audioPath, config.volume);
  }

  if (config.overlay.enabled && effect.animation) {
    const imagePath = join(themePath, 'animations', effect.animation);
    const message = effect.message || `${eventName}${toolName ? `: ${toolName}` : ''}`;
    showOverlay(config, imagePath, message);
  }

  // Return success - don't block Claude
  process.exit(0);
}

main().catch(() => process.exit(0));
