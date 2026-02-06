/**
 * mcpbr VS Code Extension
 *
 * Provides integration with the mcpbr (MCP Benchmark Runner) CLI tool,
 * allowing users to run benchmarks, view results, and manage configurations
 * directly from VS Code.
 */

import * as vscode from "vscode";
import { BenchmarkRunner } from "./runner";
import { ResultsProvider } from "./results";
import { ConfigProvider } from "./config";

let benchmarkRunner: BenchmarkRunner | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const outputChannel = vscode.window.createOutputChannel("mcpbr");

  // Initialize providers
  const resultsProvider = new ResultsProvider(context);
  const configProvider = new ConfigProvider();

  // Register tree data providers
  vscode.window.registerTreeDataProvider("mcpbr.runs", resultsProvider);
  vscode.window.registerTreeDataProvider("mcpbr.config", configProvider);

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("mcpbr.runBenchmark", async () => {
      const configPath = await selectConfigFile();
      if (!configPath) {
        return;
      }

      benchmarkRunner = new BenchmarkRunner(outputChannel);
      outputChannel.show(true);

      try {
        await benchmarkRunner.run(configPath);
        vscode.window.showInformationMessage("mcpbr: Benchmark completed!");
        resultsProvider.refresh();
      } catch (error) {
        const message =
          error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`mcpbr: Benchmark failed: ${message}`);
      }
    }),

    vscode.commands.registerCommand("mcpbr.viewResults", async () => {
      const panel = vscode.window.createWebviewPanel(
        "mcpbrResults",
        "mcpbr Results",
        vscode.ViewColumn.One,
        { enableScripts: true }
      );
      panel.webview.html = getResultsWebviewContent();
    }),

    vscode.commands.registerCommand("mcpbr.openConfig", async () => {
      const configPath = await selectConfigFile();
      if (configPath) {
        const doc = await vscode.workspace.openTextDocument(configPath);
        await vscode.window.showTextDocument(doc);
      }
    }),

    vscode.commands.registerCommand("mcpbr.showStatus", () => {
      if (benchmarkRunner?.isRunning) {
        vscode.window.showInformationMessage("mcpbr: Benchmark is running...");
      } else {
        vscode.window.showInformationMessage("mcpbr: No benchmark running.");
      }
    }),

    vscode.commands.registerCommand("mcpbr.stopBenchmark", () => {
      if (benchmarkRunner?.isRunning) {
        benchmarkRunner.stop();
        vscode.window.showInformationMessage("mcpbr: Benchmark stopped.");
      } else {
        vscode.window.showInformationMessage(
          "mcpbr: No benchmark is currently running."
        );
      }
    }),

    outputChannel
  );
}

export function deactivate(): void {
  if (benchmarkRunner?.isRunning) {
    benchmarkRunner.stop();
  }
}

async function selectConfigFile(): Promise<string | undefined> {
  const config = vscode.workspace.getConfiguration("mcpbr");
  const defaultPath = config.get<string>("defaultConfigPath");

  if (defaultPath) {
    return defaultPath;
  }

  // Search for config files in workspace
  const files = await vscode.workspace.findFiles(
    "**/mcpbr*.{yaml,yml}",
    "**/node_modules/**",
    10
  );

  if (files.length === 0) {
    const selected = await vscode.window.showOpenDialog({
      canSelectFiles: true,
      canSelectFolders: false,
      filters: { "YAML files": ["yaml", "yml"] },
      title: "Select mcpbr configuration file",
    });
    return selected?.[0]?.fsPath;
  }

  if (files.length === 1) {
    return files[0].fsPath;
  }

  const items = files.map((f) => ({
    label: vscode.workspace.asRelativePath(f),
    detail: f.fsPath,
  }));

  const selected = await vscode.window.showQuickPick(items, {
    placeHolder: "Select mcpbr configuration file",
  });

  return selected?.detail;
}

function getResultsWebviewContent(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>mcpbr Results</title>
  <style>
    body { font-family: var(--vscode-font-family); padding: 20px; }
    h1 { color: var(--vscode-foreground); }
    .placeholder {
      text-align: center;
      padding: 40px;
      color: var(--vscode-descriptionForeground);
    }
  </style>
</head>
<body>
  <h1>mcpbr Benchmark Results</h1>
  <div class="placeholder">
    <p>Run a benchmark to see results here.</p>
    <p>Use the command palette: <code>mcpbr: Run Benchmark</code></p>
  </div>
</body>
</html>`;
}
