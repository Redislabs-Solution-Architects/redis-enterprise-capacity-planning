# Visual capacity report

Generate a self-contained HTML dashboard from the same snapshot used by the CLI:

```bash
recap report --snapshot /path/to/snapshot.json --format html --out /path/outside/repository/capacity-report.html --open
```

The file opens directly in a browser. It needs no Grafana, web server, CDN, remote
fonts or JavaScript. Keep real reports outside the checkout because they contain
cluster topology. Generation does not contact or modify a cluster.

For a working offline example with inspectable upscale plans:

```bash
recap report --snapshot tests/fixtures/upscale-steps.json --ladder '6GiB:1' --format html --out /tmp/recap-report.html --open
```

## Read the dashboard

- **Summary:** node and rack groups, known free planning RAM, free shard slots and
  available license headroom. Unknown values stay explicitly unknown.
- **Node resources:** blue bars show free provisional RAM relative to physical node
  memory. The remaining width is not a measurement of database memory used. Green
  bars show free shard slots relative to each node's limit. Exact values and capacity
  constraints are also available in the table.
- **Capacity by rack:** expand a shard-size section to compare individual shard
  capacity by rack. The cluster total additionally observes the known license limit.
- **Can-create:** feasibility and reasons for replicated database targets in the ladder.
- **Can-upscale:** next-rung results for supported replicated databases. Expand
  **Inspect plan** to read verified exported commands; nothing is executed.
- **Unsupported targets and provenance:** inspect snapshot age, source, warnings,
  unknown semantics and unsupported database types before using the results.

The report uses the same calculated results and replay checks as the text/JSON
report. It does not replace uncertainty with a healthy status. A partial snapshot
gets a prominent banner and its visibility reasons; use `--allow-partial` explicitly
when generating it. Colors supplement written verdicts and values.

## Save, share or print

Omit `--open` on a server or in an unattended job:

```bash
recap report --snapshot /path/to/snapshot.json --format html --out /path/outside/repository/report.html
```

Without `--out`, HTML is written to stdout and can be redirected. `--out -` also
means stdout. Browser opening is explicit and requires a real output file.

You can share the single HTML file; its charts and styles travel with it. The
browser's light/dark preference controls its theme. Tables scroll within their
containers on smaller screens and charts retain visible labels.

To make a PDF, expand the sections and plans you want to include, then use the
browser's print dialog and choose **Save as PDF**. A print stylesheet removes
navigation and uses a light background.

Store and share the report with the same care as its source snapshot. Exported
REST commands retain credential placeholders. Review conditional placement notes
and re-collect before acting on an actual cluster.
