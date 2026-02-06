/**
 * Results tree data provider for the sidebar.
 */

import * as vscode from "vscode";

export class ResultsProvider implements vscode.TreeDataProvider<ResultItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<ResultItem | undefined | null> =
    new vscode.EventEmitter<ResultItem | undefined | null>();
  readonly onDidChangeTreeData: vscode.Event<ResultItem | undefined | null> =
    this._onDidChangeTreeData.event;

  private _context: vscode.ExtensionContext;

  constructor(context: vscode.ExtensionContext) {
    this._context = context;
  }

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ResultItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: ResultItem): Promise<ResultItem[]> {
    if (!element) {
      // Root level - show recent runs
      return this._getRecentRuns();
    }
    return [];
  }

  private async _getRecentRuns(): Promise<ResultItem[]> {
    // Placeholder - will connect to mcpbr API or SQLite
    return [
      new ResultItem(
        "No runs yet",
        "Run a benchmark to see results",
        vscode.TreeItemCollapsibleState.None
      ),
    ];
  }
}

export class ResultItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly description: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState
  ) {
    super(label, collapsibleState);
    this.tooltip = `${this.label} - ${this.description}`;
  }
}
