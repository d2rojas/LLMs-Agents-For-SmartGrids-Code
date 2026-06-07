// API response types

export interface Network {
  id: string;
  label: string;
}

export interface Scenario {
  id: string;
  label: string;
  category: 'normal' | 'nonconvergence' | 'voltage' | 'thermal' | 'contingency';
}

// Can be array of indices or ["all"] marker
type ComponentIndices = number[] | ['all'];

export interface ParsedAffectedComponents {
  bus?: ComponentIndices;
  line?: ComponentIndices;
  load?: ComponentIndices;
  gen?: ComponentIndices;
  trafo?: ComponentIndices;
  ext_grid?: ComponentIndices;
}

/** Phase classification for agent actions. */
export type ActionPhase = 'diagnostic' | 'fix' | 'verify';

/** One tool invocation during agentic reasoning. */
export interface AgentToolCall {
  iteration: number;
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  reasoning?: string;
  phase?: ActionPhase;
}

/** Unified agent action with reasoning and phase. */
export interface AgentAction {
  iteration: number;
  tool?: string;
  action?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  reasoning?: string;
  rationale?: string;
  phase?: ActionPhase;
  success?: boolean;
}

/** Initial diagnosis extracted from preprocessor before fixes. */
export interface InitialDiagnosis {
  root_causes: string[];
  affected_components: string[];
  failure_category: string;
  converged_initially: boolean;
}

/** Final state after all fixes applied. */
export interface FinalState {
  converged: boolean;
  remaining_violations: string[];
  is_healthy: boolean;
}

export interface PipelineResult {
  rawResult?: string;
  analysisStatus: 'success' | 'error' | 'not_implemented' | 'skipped';
  rootCauses: string[];
  affectedComponents: string[];
  correctiveActions: string[];
  parsedAffectedComponents?: ParsedAffectedComponents;
  /** Present for agentic pipeline: tools the agent called (reasoning trace). */
  toolCalls?: AgentToolCall[];
  /** Full reasoning process text (agentic only): steps and tool results. */
  reasoningTrace?: string;
  /** Heuristic checks: does tool usage support the report? (agentic only). */
  reasoningQuality?: {
    checks: { id: string; passed: boolean; message: string }[];
    summary: string;
    passedCount: number;
    totalCount: number;
  };
  /** Iterative debugger: history of corrective actions applied. */
  fixHistory?: Array<Record<string, unknown>>;
  /** Whether power flow converged after all fixes (iterative only). */
  finalConverged?: boolean;
  /** Number of fix iterations used (iterative only). */
  iterationsUsed?: number;
  /** Initial diagnosis from preprocessor before fixes (agentic only). */
  initialDiagnosis?: InitialDiagnosis;
  /** Unified list of agent actions with reasoning and phase (agentic only). */
  agentActions?: AgentAction[];
  /** Final state after all fixes applied (agentic only). */
  finalState?: FinalState;
  /** Network state before agent fixes (agentic only). */
  beforeState?: RawNetworkState;
  /** Network state after agent fixes (agentic only). */
  afterState?: RawNetworkState;
  /** Concise answer to the user's query, separate from fix narrative (agentic only). */
  querySummary?: string;
}

// Only 2 tabs: Baseline (manual) and Agentic (auto-fix)
export type PipelineId = 'baseline' | 'agentic';

export interface DiagnoseResponse {
  baseline: PipelineResult;
  agentic: PipelineResult;
}

export interface ReDiagnoseResponse {
  baseline: PipelineResult;
  agentic: PipelineResult;
  networkState: RawNetworkState;
}

export interface GeneratedGroundTruth {
  failureType: string;
  rootCauses: string[];
  affectedComponents: Record<string, unknown>;
  knownFix: string;
}

export interface DiagnoseNLResponse {
  generationStatus: 'success' | 'error';
  generationError: string | null;
  generatedCode: string;
  generatedGroundTruth: GeneratedGroundTruth | null;
  baseline: PipelineResult;
  agentic: PipelineResult;
  responseType: 'text_only' | 'plot_only' | 'direct_answer' | 'full_diagnosis';
  textAnswer?: string;
}

// Network Manipulation Types

// Value overrides (numeric properties only)
export interface LoadValues {
  p_mw?: number;
  q_mvar?: number;
}

export interface GenValues {
  p_mw?: number;
  vm_pu?: number;
}

export interface ExtGridValues {
  vm_pu?: number;
}

// Override state with separate in_service maps and value maps
export interface OverrideState {
  globalLoadScale: number;
  // In-service state maps (boolean only)
  lineStates: Record<number, boolean>;
  trafoStates: Record<number, boolean>;
  genStates: Record<number, boolean>;
  loadStates: Record<number, boolean>;
  extGridStates: Record<number, boolean>;
  // Value overrides (numeric properties)
  loadValues: Record<number, LoadValues>;
  genValues: Record<number, GenValues>;
  extGridValues: Record<number, ExtGridValues>;
}

export interface BusData {
  name: string;
  vn_kv: number;
  type: string;
  in_service: boolean;
  zone?: string;
  max_vm_pu?: number;
  min_vm_pu?: number;
}

export interface LineData {
  name: string;
  from_bus: number;
  to_bus: number;
  length_km: number;
  in_service: boolean;
  max_i_ka?: number;
  r_ohm_per_km?: number;
  x_ohm_per_km?: number;
  c_nf_per_km?: number;
  max_loading_percent?: number;
  std_type?: string;
}

export interface LoadData {
  name: string;
  bus: number;
  p_mw: number;
  q_mvar: number;
  in_service: boolean;
  const_z_percent?: number;
  const_i_percent?: number;
  scaling?: number;
  type?: string;
}

export interface GenData {
  name: string;
  bus: number;
  p_mw: number;
  vm_pu: number;
  in_service: boolean;
  min_p_mw?: number;
  max_p_mw?: number;
  min_q_mvar?: number;
  max_q_mvar?: number;
  scaling?: number;
  type?: string;
  controllable?: boolean;
}

export interface TrafoData {
  name: string;
  hv_bus: number;
  lv_bus: number;
  in_service: boolean;
  sn_mva?: number;
  vn_hv_kv?: number;
  vn_lv_kv?: number;
  vk_percent?: number;
  vkr_percent?: number;
  tap_pos?: number;
  shift_degree?: number;
  std_type?: string;
}

export interface ExtGridData {
  name: string;
  bus: number;
  vm_pu: number;
  in_service: boolean;
  va_degree?: number;
  min_p_mw?: number;
  max_p_mw?: number;
  min_q_mvar?: number;
  max_q_mvar?: number;
}

export interface BusCoords {
  [busIdx: string]: { x: number; y: number };
}

export interface AffectedComponents {
  bus?: number[];
  line?: number[];
  trafo?: number[];
  load?: number[];
  gen?: number[];
}

export interface RawNetworkState {
  bus: Record<string, BusData>;
  line: Record<string, LineData>;
  load: Record<string, LoadData>;
  gen: Record<string, GenData>;
  trafo: Record<string, TrafoData>;
  ext_grid: Record<string, ExtGridData>;
  res_bus?: Record<string, { vm_pu: number; va_degree: number; p_mw: number; q_mvar: number }>;
  res_line?: Record<string, { loading_percent: number; p_from_mw: number; p_to_mw: number }>;
  bus_coords: BusCoords;
  affected_components: AffectedComponents;
  converged: boolean;
}
