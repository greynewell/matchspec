/**
 * Benchmark runner - executes mcpbr CLI commands.
 */

import * as vscode from "vscode";
import { ChildProcess, spawn } from "child_process";

export class BenchmarkRunner {
  private _process: ChildProcess | undefined;
  private _outputChannel: vscode.OutputChannel;

  constructor(outputChannel: vscode.OutputChannel) {
    this._outputChannel = outputChannel;
  }

  get isRunning(): boolean {
    return this._process !== undefined && this._process.exitCode === null;
  }

  async run(configPath: string): Promise<void> {
    const config = vscode.workspace.getConfiguration("mcpbr");
    const pythonPath = config.get<string>("pythonPath", "python3");

    return new Promise<void>((resolve, reject) => {
      this._outputChannel.appendLine(`Running: ${pythonPath} -m mcpbr run -c ${configPath}`);
      this._outputChannel.appendLine("---");

      this._process = spawn(pythonPath, ["-m", "mcpbr", "run", "-c", configPath], {
        cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
      });

      this._process.stdout?.on("data", (data: Buffer) => {
        this._outputChannel.append(data.toString());
      });

      this._process.stderr?.on("data", (data: Buffer) => {
        this._outputChannel.append(data.toString());
      });

      this._process.on("close", (code: number | null) => {
        this._outputChannel.appendLine(`\n--- Exited with code ${code}`);
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`mcpbr exited with code ${code}`));
        }
      });

      this._process.on("error", (err: Error) => {
        this._outputChannel.appendLine(`Error: ${err.message}`);
        reject(err);
      });
    });
  }

  stop(): void {
    if (this._process && this._process.exitCode === null) {
      this._process.kill("SIGTERM");
      this._outputChannel.appendLine("\n--- Benchmark stopped by user");
    }
  }
}
