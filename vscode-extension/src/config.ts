/**
 * Configuration tree data provider for the sidebar.
 */

import * as vscode from "vscode";

export class ConfigProvider implements vscode.TreeDataProvider<ConfigItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<ConfigItem | undefined | null> =
    new vscode.EventEmitter<ConfigItem | undefined | null>();
  readonly onDidChangeTreeData: vscode.Event<ConfigItem | undefined | null> =
    this._onDidChangeTreeData.event;

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ConfigItem): vscode.TreeItem {
    return element;
  }

  async getChildren(_element?: ConfigItem): Promise<ConfigItem[]> {
    const items: ConfigItem[] = [];

    const config = vscode.workspace.getConfiguration("mcpbr");
    const pythonPath = config.get<string>("pythonPath", "python3");
    const apiHost = config.get<string>("apiHost", "http://localhost:8080");

    items.push(new ConfigItem("Python", pythonPath, vscode.TreeItemCollapsibleState.None));
    items.push(new ConfigItem("API Host", apiHost, vscode.TreeItemCollapsibleState.None));

    // Find config files in workspace
    const files = await vscode.workspace.findFiles("**/mcpbr*.{yaml,yml}", "**/node_modules/**", 5);
    for (const file of files) {
      const relativePath = vscode.workspace.asRelativePath(file);
      const item = new ConfigItem("Config", relativePath, vscode.TreeItemCollapsibleState.None);
      item.command = {
        command: "vscode.open",
        title: "Open Config",
        arguments: [file],
      };
      items.push(item);
    }

    return items;
  }
}

export class ConfigItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly description: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState
  ) {
    super(label, collapsibleState);
  }
}
