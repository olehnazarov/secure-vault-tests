#!/usr/bin/env node
// Rebuilds gh-pages-history/index.html from runs.log.
// Usage: node scripts/generate-report-index.mjs <gh-pages-history-dir>
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const dir = process.argv[2];
if (!dir) {
  console.error('Usage: node generate-report-index.mjs <gh-pages-history-dir>');
  process.exit(1);
}

const logPath = join(dir, 'runs.log');
const lines = readFileSync(logPath, 'utf8').split('\n').filter(Boolean);

const runs = lines.map((line) => {
  const [run, date, sha, status] = line.split('|');
  return { run, date, sha, passed: status === 'success' };
});

const total = runs.length;
const passedCount = runs.filter((r) => r.passed).length;
const passRate = total ? Math.round((passedCount / total) * 100) : 0;
const last = runs[runs.length - 1];
const recent = runs.slice(-40);
const rows = [...runs].reverse();

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const dot = (r) =>
  `<a class="dot ${r.passed ? 'pass' : 'fail'}" href="reports/${r.run}/" title="#${r.run} · ${esc(r.date)} · ${r.passed ? 'passed' : 'failed'}"></a>`;

const row = (r) => `
      <tr>
        <td><a href="reports/${r.run}/">#${r.run}</a></td>
        <td>${esc(r.date)}</td>
        <td><code>${esc((r.sha || '').slice(0, 7))}</code></td>
        <td>${badge(r.passed)}</td>
      </tr>`;

const badge = (passed) =>
  passed
    ? '<span class="badge pass"><span class="badge-icon">✓</span>Passed</span>'
    : '<span class="badge fail"><span class="badge-icon">✕</span>Failed</span>';

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SecureVault Allure Report history</title>
<style>
  :root {
    color-scheme: light;
    --page:       #faf9f5;
    --surface:    #ffffff;
    --ink:        #1f1e1d;
    --ink-2:      #6b6a66;
    --ink-muted:  #928f87;
    --border:     rgba(31,30,29,0.10);
    --accent:     #d97757;
    --accent-ink: #b54e30;
    --good:       #1a7f37;
    --good-bg:    #e9f5ec;
    --bad:        #cf222e;
    --bad-bg:     #fbeaea;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --page:       #171615;
      --surface:    #262624;
      --ink:        #f5f4ef;
      --ink-2:      #b5b3ac;
      --ink-muted:  #83807a;
      --border:     rgba(255,255,255,0.10);
      --accent:     #e08a64;
      --accent-ink: #e08a64;
      --good:       #4ade80;
      --good-bg:    rgba(74,222,128,0.12);
      --bad:        #f85149;
      --bad-bg:     rgba(248,81,73,0.12);
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 48px 20px 80px;
    background: var(--page);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 880px; margin: 0 auto; }
  header { margin-bottom: 32px; }
  h1 {
    font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
    font-weight: 500;
    font-size: 2rem;
    margin: 0 0 6px;
    letter-spacing: -0.01em;
  }
  .sub { color: var(--ink-2); font-size: 0.95rem; margin: 0; }
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin: 28px 0 32px;
  }
  .stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
  }
  .stat-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ink-muted);
    margin: 0 0 6px;
  }
  .stat-value {
    font-size: 1.6rem;
    font-weight: 600;
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
  .stat-value.accent { color: var(--accent-ink); }
  .stat-value.good { color: var(--good); }
  .stat-value.bad { color: var(--bad); }
  .sparkline {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 32px;
  }
  .sparkline-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ink-muted);
    margin: 0 0 12px;
  }
  .dots { display: flex; flex-wrap: wrap; gap: 5px; }
  .dot {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    display: inline-block;
    text-decoration: none;
  }
  .dot.pass { background: var(--good); }
  .dot.fail { background: var(--bad); }
  .dot:hover { outline: 2px solid var(--accent); outline-offset: 1px; }
  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }
  th, td { padding: 11px 16px; text-align: left; font-size: 0.9rem; }
  th {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ink-muted);
    border-bottom: 1px solid var(--border);
    font-weight: 600;
  }
  tbody tr:not(:last-child) td { border-bottom: 1px solid var(--border); }
  td code { font-size: 0.85rem; color: var(--ink-2); }
  a { color: var(--accent-ink); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
  }
  .badge.pass { color: var(--good); background: var(--good-bg); }
  .badge.fail { color: var(--bad); background: var(--bad-bg); }
  .badge-icon { font-size: 0.78rem; }
  footer {
    margin-top: 28px;
    color: var(--ink-muted);
    font-size: 0.82rem;
    text-align: center;
  }
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>SecureVault Allure Report History</h1>
      <p class="sub">SecureVault API test runs on every push to main</p>
    </header>

    <div class="stats">
      <div class="stat">
        <p class="stat-label">Total runs</p>
        <p class="stat-value">${total}</p>
      </div>
      <div class="stat">
        <p class="stat-label">Pass rate</p>
        <p class="stat-value accent">${passRate}%</p>
      </div>
      <div class="stat">
        <p class="stat-label">Last run</p>
        <p class="stat-value ${last?.passed ? 'good' : 'bad'}">${last ? (last.passed ? 'Passed' : 'Failed') : '—'}</p>
      </div>
      <div class="stat">
        <p class="stat-label">Last run date</p>
        <p class="stat-value" style="font-size:1.1rem">${last ? esc(last.date) : '—'}</p>
      </div>
    </div>

    <div class="sparkline">
      <p class="sparkline-label">Last ${recent.length} runs</p>
      <div class="dots">${recent.map(dot).join('')}</div>
    </div>

    <table>
      <thead>
        <tr><th>Run</th><th>Date</th><th>Commit</th><th>Status</th></tr>
      </thead>
      <tbody>${rows.map(row).join('')}
      </tbody>
    </table>

    <footer>Generated by GitHub Actions</footer>
  </div>
</body>
</html>
`;

writeFileSync(join(dir, 'index.html'), html);
