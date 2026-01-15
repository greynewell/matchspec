/**
 * LRU Cache for indexed graphs
 * Stores raw API responses + derived indexes for fast query execution
 */

import { SupermodelIR, CodeGraphNode, CodeGraphRelationship } from './graph-types';

// Lightweight node descriptor for query responses
export interface NodeDescriptor {
  id: string;
  labels: string[];
  name?: string;
  filePath?: string;
  startLine?: number;
  endLine?: number;
  kind?: string;
}

// Edge descriptor for query responses
export interface EdgeDescriptor {
  type: string;
  from: string;
  to: string;
  props?: Record<string, unknown>;
}

// Adjacency list for traversal
export interface AdjacencyList {
  out: string[];
  in: string[];
}

// Path index entry - what entities are defined in a file
export interface PathIndexEntry {
  fileId: string;
  classIds: string[];
  functionIds: string[];
  typeIds: string[];
}

// Indexed graph structure
export interface IndexedGraph {
  // Raw data
  raw: SupermodelIR;

  // Indexes
  nodeById: Map<string, CodeGraphNode>;
  labelIndex: Map<string, string[]>;  // label -> node ids
  pathIndex: Map<string, PathIndexEntry>;  // filePath -> entities
  dirIndex: Map<string, string[]>;  // dir path -> child file/dir ids
  nameIndex: Map<string, string[]>;  // lowercase name -> node ids
  callAdj: Map<string, AdjacencyList>;  // function id -> callers/callees
  importAdj: Map<string, AdjacencyList>;  // file/module id -> imports/importers
  domainIndex: Map<string, { memberIds: string[], relationships: CodeGraphRelationship[] }>;

  // Precomputed
  summary: {
    filesProcessed: number;
    classes: number;
    functions: number;
    types: number;
    domains: number;
    primaryLanguage: string;
    nodeCount: number;
    relationshipCount: number;
  };

  // Metadata
  cachedAt: string;
  cacheKey: string;
}

// Cache entry with size tracking
interface CacheEntry {
  graph: IndexedGraph;
  nodeCount: number;
  lastAccessed: number;
}

/**
 * Build indexes from raw SupermodelIR response
 */
export function buildIndexes(raw: SupermodelIR, cacheKey: string): IndexedGraph {
  const nodes = raw.graph?.nodes || [];
  const relationships = raw.graph?.relationships || [];

  // Initialize indexes
  const nodeById = new Map<string, CodeGraphNode>();
  const labelIndex = new Map<string, string[]>();
  const pathIndex = new Map<string, PathIndexEntry>();
  const dirIndex = new Map<string, string[]>();
  const nameIndex = new Map<string, string[]>();
  const callAdj = new Map<string, AdjacencyList>();
  const importAdj = new Map<string, AdjacencyList>();
  const domainIndex = new Map<string, { memberIds: string[], relationships: CodeGraphRelationship[] }>();

  // Build node indexes
  for (const node of nodes) {
    const id = node.id;
    const props = node.properties || {};
    const labels = node.labels || [];

    // nodeById
    nodeById.set(id, node);

    // labelIndex
    for (const label of labels) {
      if (!labelIndex.has(label)) {
        labelIndex.set(label, []);
      }
      labelIndex.get(label)!.push(id);
    }

    // nameIndex (lowercase for case-insensitive search)
    const name = props.name as string | undefined;
    if (name) {
      const lowerName = name.toLowerCase();
      if (!nameIndex.has(lowerName)) {
        nameIndex.set(lowerName, []);
      }
      nameIndex.get(lowerName)!.push(id);
    }

    // pathIndex - track what's defined in each file
    const filePath = props.filePath as string | undefined;
    if (filePath) {
      const normalized = normalizePath(filePath);
      if (!pathIndex.has(normalized)) {
        pathIndex.set(normalized, { fileId: '', classIds: [], functionIds: [], typeIds: [] });
      }
      const entry = pathIndex.get(normalized)!;

      const primaryLabel = labels[0];
      if (primaryLabel === 'File') {
        entry.fileId = id;
      } else if (primaryLabel === 'Class') {
        entry.classIds.push(id);
      } else if (primaryLabel === 'Function') {
        entry.functionIds.push(id);
      } else if (primaryLabel === 'Type') {
        entry.typeIds.push(id);
      }
    }

    // dirIndex - build directory tree
    if (labels[0] === 'Directory') {
      const dirPath = normalizePath(props.path as string || props.name as string || '');
      if (!dirIndex.has(dirPath)) {
        dirIndex.set(dirPath, []);
      }
    }

    // Initialize adjacency lists for functions and files
    if (labels[0] === 'Function') {
      callAdj.set(id, { out: [], in: [] });
    }
    if (labels[0] === 'File' || labels[0] === 'LocalModule' || labels[0] === 'ExternalModule') {
      importAdj.set(id, { out: [], in: [] });
    }

    // domainIndex
    if (labels[0] === 'Domain' || labels[0] === 'Subdomain') {
      domainIndex.set(name || id, { memberIds: [], relationships: [] });
    }
  }

  // Build relationship indexes
  for (const rel of relationships) {
    const { type, startNode, endNode } = rel;

    // Call adjacency
    if (type === 'calls') {
      if (callAdj.has(startNode)) {
        callAdj.get(startNode)!.out.push(endNode);
      }
      if (callAdj.has(endNode)) {
        callAdj.get(endNode)!.in.push(startNode);
      }
    }

    // Import adjacency
    if (type === 'IMPORTS') {
      // Some graphs emit IMPORTS edges from non-File nodes (e.g. Function -> Module).
      // Create adjacency lazily for any node that participates.
      let startAdj = importAdj.get(startNode);
      if (!startAdj) {
        startAdj = { out: [], in: [] };
        importAdj.set(startNode, startAdj);
      }
      startAdj.out.push(endNode);

      let endAdj = importAdj.get(endNode);
      if (!endAdj) {
        endAdj = { out: [], in: [] };
        importAdj.set(endNode, endAdj);
      }
      endAdj.in.push(startNode);
    }

    // Directory contains
    if (type === 'CONTAINS_FILE' || type === 'CHILD_DIRECTORY') {
      const startNode_ = nodeById.get(startNode);
      if (startNode_ && startNode_.labels?.[0] === 'Directory') {
        const dirPath = normalizePath(startNode_.properties?.path as string || startNode_.properties?.name as string || '');
        if (dirIndex.has(dirPath)) {
          dirIndex.get(dirPath)!.push(endNode);
        }
      }
    }

    // Domain membership
    if (type === 'belongsTo') {
      const targetNode = nodeById.get(endNode);
      if (targetNode) {
        const domainName = targetNode.properties?.name as string;
        if (domainIndex.has(domainName)) {
          domainIndex.get(domainName)!.memberIds.push(startNode);
        }
      }
    }

    // Domain relationships
    const startNodeData = nodeById.get(startNode);
    const endNodeData = nodeById.get(endNode);
    if (startNodeData?.labels?.[0] === 'Domain' && endNodeData?.labels?.[0] === 'Domain') {
      const domainName = startNodeData.properties?.name as string;
      if (domainIndex.has(domainName)) {
        domainIndex.get(domainName)!.relationships.push(rel);
      }
    }
  }

  // Compute summary
  const summary = {
    filesProcessed: raw.summary?.filesProcessed || labelIndex.get('File')?.length || 0,
    classes: raw.summary?.classes || labelIndex.get('Class')?.length || 0,
    functions: raw.summary?.functions || labelIndex.get('Function')?.length || 0,
    types: raw.summary?.types || labelIndex.get('Type')?.length || 0,
    domains: raw.summary?.domains || labelIndex.get('Domain')?.length || 0,
    primaryLanguage: raw.summary?.primaryLanguage || 'unknown',
    nodeCount: nodes.length,
    relationshipCount: relationships.length,
  };

  return {
    raw,
    nodeById,
    labelIndex,
    pathIndex,
    dirIndex,
    nameIndex,
    callAdj,
    importAdj,
    domainIndex,
    summary,
    cachedAt: new Date().toISOString(),
    cacheKey,
  };
}

/**
 * Normalize file paths for consistent matching
 */
export function normalizePath(path: string): string {
  return path.replace(/\\/g, '/');
}

/**
 * Convert full node to lightweight descriptor
 */
export function toNodeDescriptor(node: CodeGraphNode): NodeDescriptor {
  const props = node.properties || {};
  return {
    id: node.id,
    labels: node.labels || [],
    name: props.name as string | undefined,
    filePath: props.filePath as string | undefined,
    startLine: props.startLine as number | undefined,
    endLine: props.endLine as number | undefined,
    kind: props.kind as string | undefined,
  };
}

/**
 * LRU Cache for indexed graphs
 */
export class GraphCache {
  private cache = new Map<string, CacheEntry>();
  private maxGraphs: number;
  private maxNodes: number;
  private currentNodes = 0;

  constructor(options?: { maxGraphs?: number; maxNodes?: number }) {
    this.maxGraphs = options?.maxGraphs || 20;
    this.maxNodes = options?.maxNodes || 1000000;
  }

  get(cacheKey: string): IndexedGraph | null {
    const entry = this.cache.get(cacheKey);
    if (entry) {
      // Update access time (LRU)
      entry.lastAccessed = Date.now();
      return entry.graph;
    }
    return null;
  }

  set(cacheKey: string, graph: IndexedGraph): void {
    const nodeCount = graph.summary.nodeCount;

    // Evict if needed
    while (
      (this.cache.size >= this.maxGraphs || this.currentNodes + nodeCount > this.maxNodes) &&
      this.cache.size > 0
    ) {
      this.evictOldest();
    }

    // Store
    this.cache.set(cacheKey, {
      graph,
      nodeCount,
      lastAccessed: Date.now(),
    });
    this.currentNodes += nodeCount;
  }

  has(cacheKey: string): boolean {
    return this.cache.has(cacheKey);
  }

  private evictOldest(): void {
    let oldestKey: string | null = null;
    let oldestTime = Infinity;

    for (const [key, entry] of this.cache) {
      if (entry.lastAccessed < oldestTime) {
        oldestTime = entry.lastAccessed;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      const entry = this.cache.get(oldestKey)!;
      this.currentNodes -= entry.nodeCount;
      this.cache.delete(oldestKey);
    }
  }

  status(): { graphs: number; nodes: number; keys: string[] } {
    return {
      graphs: this.cache.size,
      nodes: this.currentNodes,
      keys: Array.from(this.cache.keys()),
    };
  }
}

// Global cache instance
export const graphCache = new GraphCache();
