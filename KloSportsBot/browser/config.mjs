// Shared config loader. Reads config.json (gitignored) sitting next to this file.
// Copy config.example.json -> config.json and fill in your pool's values.
import fs from 'node:fs';

const CONFIG_PATH = new URL('./config.json', import.meta.url);

export function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  } catch (e) {
    console.error('Could not read config.json next to browser/. Copy config.example.json -> config.json and fill it in.');
    throw e;
  }
}

const cfg = loadConfig();
export const POOL_BASE = cfg.poolBase;
export const ROUTES = cfg.routes;
export const TIMEZONE = cfg.timezone || 'UTC';
export const url = (routeKey) => POOL_BASE + (ROUTES[routeKey] || routeKey);
export default cfg;
