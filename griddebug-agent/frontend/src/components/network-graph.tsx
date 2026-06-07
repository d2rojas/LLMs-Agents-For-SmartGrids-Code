'use client';

import { useMemo, useEffect, useState, useCallback } from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  NodeProps,
  Handle,
  Position,
  EdgeProps,
  getBezierPath,
  EdgeLabelRenderer,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { RawNetworkState, LoadData, GenData, ExtGridData } from '@/types/diagnostic';
import { Loader2, X } from 'lucide-react';

interface NetworkGraphProps {
  networkState: RawNetworkState | null;
  isLoading: boolean;
}

interface TooltipData {
  type: 'bus' | 'line' | 'trafo';
  x: number;
  y: number;
  data: Record<string, unknown>;
}

interface SelectedElement {
  type: 'bus' | 'line' | 'trafo';
  id: string;
  data: Record<string, unknown>;
}

// Custom node component for buses with hover tooltip
function BusNode({ data, id }: NodeProps) {
  const isAffected = data.isAffected as boolean;
  const isOutOfService = data.isOutOfService as boolean;
  const busType = data.busType as string;
  const onHover = data.onHover as ((data: TooltipData | null) => void) | undefined;
  const onSelect = data.onSelect as ((data: SelectedElement | null) => void) | undefined;

  // Color based on type
  let bgColor = '#3b82f6'; // blue for regular bus
  if (busType === 'ext_grid') bgColor = '#eab308'; // yellow
  else if (busType === 'gen') bgColor = '#f97316'; // orange
  else if (busType === 'load') bgColor = '#6b7280'; // gray

  const handleMouseEnter = (e: React.MouseEvent) => {
    if (onHover) {
      const rect = e.currentTarget.getBoundingClientRect();
      onHover({
        type: 'bus',
        x: rect.right + 10,
        y: rect.top,
        data: data as Record<string, unknown>,
      });
    }
  };

  const handleMouseLeave = () => {
    if (onHover) onHover(null);
  };

  const handleClick = () => {
    if (onSelect) {
      onSelect({
        type: 'bus',
        id,
        data: data as Record<string, unknown>,
      });
    }
  };

  return (
    <div
      className="flex items-center justify-center rounded-full text-white text-xs font-bold cursor-pointer"
      style={{
        width: 40,
        height: 40,
        backgroundColor: bgColor,
        border: isAffected ? '3px solid #ef4444' : isOutOfService ? '3px dashed #64748b' : '2px solid #1e293b',
        boxShadow: isAffected ? '0 0 8px #ef4444' : 'none',
        opacity: isOutOfService ? 0.5 : 1,
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    >
      {data.label as string}
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
}

// Custom edge component with hover support
function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  data,
  label,
  labelStyle,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const onHover = data?.onHover as ((data: TooltipData | null) => void) | undefined;
  const onSelect = data?.onSelect as ((data: SelectedElement | null) => void) | undefined;
  const edgeType = data?.edgeType as 'line' | 'trafo' | undefined;

  const handleMouseEnter = (e: React.MouseEvent) => {
    if (onHover && edgeType) {
      onHover({
        type: edgeType,
        x: e.clientX + 10,
        y: e.clientY,
        data: data as Record<string, unknown>,
      });
    }
  };

  const handleMouseLeave = () => {
    if (onHover) onHover(null);
  };

  const handleClick = () => {
    if (onSelect && edgeType) {
      onSelect({
        type: edgeType,
        id,
        data: data as Record<string, unknown>,
      });
    }
  };

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path cursor-pointer"
        d={edgePath}
        style={{ ...style, strokeWidth: 8, stroke: 'transparent' }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
      />
      <path
        d={edgePath}
        style={style}
        className="react-flow__edge-path pointer-events-none"
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'none',
              ...labelStyle,
            }}
            className="text-[10px] bg-background/80 px-1 rounded"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = {
  bus: BusNode,
};

const edgeTypes = {
  custom: CustomEdge,
};

// Tooltip component
function Tooltip({ tooltip }: { tooltip: TooltipData }) {
  const { type, x, y, data } = tooltip;

  return (
    <div
      className="fixed z-50 bg-popover border rounded-lg shadow-lg p-3 text-xs max-w-[280px] pointer-events-none"
      style={{ left: x, top: y }}
    >
      {type === 'bus' && (
        <div className="space-y-1.5">
          <div className="font-semibold text-sm border-b pb-1 mb-2">
            Bus {String(data.label)} {data.name ? `(${String(data.name)})` : ''}
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            <span className="text-muted-foreground">Type:</span>
            <span className="capitalize">{(data.busType as string)?.replace('_', ' ')}</span>
            <span className="text-muted-foreground">Voltage:</span>
            <span>{data.vm_pu != null ? `${(data.vm_pu as number).toFixed(3)} pu` : 'N/A'}</span>
            <span className="text-muted-foreground">Nominal:</span>
            <span>{String(data.vn_kv)} kV</span>
            <span className="text-muted-foreground">Status:</span>
            <span>{data.in_service ? 'In Service' : 'Out of Service'}</span>
          </div>
          {(data.connectedLoads as LoadData[])?.length > 0 && (
            <div className="mt-2 pt-2 border-t">
              <div className="font-medium mb-1">Loads:</div>
              {(data.connectedLoads as LoadData[]).map((load, i) => (
                <div key={i} className="text-muted-foreground">
                  {load.name || `Load ${i}`}: {load.p_mw?.toFixed(1)} MW, {load.q_mvar?.toFixed(1)} Mvar
                </div>
              ))}
            </div>
          )}
          {(data.connectedGens as GenData[])?.length > 0 && (
            <div className="mt-2 pt-2 border-t">
              <div className="font-medium mb-1">Generators:</div>
              {(data.connectedGens as GenData[]).map((gen, i) => (
                <div key={i} className="text-muted-foreground">
                  {gen.name || `Gen ${i}`}: {gen.p_mw?.toFixed(1)} MW @ {gen.vm_pu?.toFixed(3)} pu
                </div>
              ))}
            </div>
          )}
          {(data.connectedExtGrids as ExtGridData[])?.length > 0 && (
            <div className="mt-2 pt-2 border-t">
              <div className="font-medium mb-1">External Grid:</div>
              {(data.connectedExtGrids as ExtGridData[]).map((ext, i) => (
                <div key={i} className="text-muted-foreground">
                  {ext.name || `Ext Grid ${i}`}: Vm = {ext.vm_pu?.toFixed(3)} pu
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {type === 'line' && (
        <div className="space-y-1.5">
          <div className="font-semibold text-sm border-b pb-1 mb-2">
            Line {String(data.lineIndex)} {data.name ? `(${String(data.name)})` : ''}
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            <span className="text-muted-foreground">From → To:</span>
            <span>Bus {String(data.from_bus)} → {String(data.to_bus)}</span>
            <span className="text-muted-foreground">Loading:</span>
            <span className={data.loading_percent != null && (data.loading_percent as number) > 100 ? 'text-red-500 font-medium' : ''}>
              {data.loading_percent != null ? `${(data.loading_percent as number).toFixed(1)}%` : 'N/A'}
            </span>
            <span className="text-muted-foreground">Length:</span>
            <span>{data.length_km != null ? `${(data.length_km as number).toFixed(2)} km` : 'N/A'}</span>
            <span className="text-muted-foreground">Status:</span>
            <span>{data.in_service ? 'In Service' : 'Out of Service'}</span>
          </div>
        </div>
      )}
      {type === 'trafo' && (
        <div className="space-y-1.5">
          <div className="font-semibold text-sm border-b pb-1 mb-2">
            Transformer {String(data.trafoIndex)} {data.name ? `(${String(data.name)})` : ''}
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            <span className="text-muted-foreground">HV → LV:</span>
            <span>Bus {String(data.hv_bus)} → {String(data.lv_bus)}</span>
            <span className="text-muted-foreground">Rating:</span>
            <span>{data.sn_mva != null ? `${String(data.sn_mva)} MVA` : 'N/A'}</span>
            <span className="text-muted-foreground">Status:</span>
            <span>{data.in_service ? 'In Service' : 'Out of Service'}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// Detail panel component for selected element
function DetailPanel({ selected, onClose, networkState }: { selected: SelectedElement; onClose: () => void; networkState: RawNetworkState }) {
  const { type, data } = selected;

  return (
    <div className="absolute bottom-2 left-2 right-2 bg-popover border rounded-lg shadow-lg p-3 text-xs max-h-[200px] overflow-y-auto z-40">
      <div className="flex justify-between items-center mb-2">
        <span className="font-semibold text-sm">
          {type === 'bus' && `Bus ${String(data.label)}`}
          {type === 'line' && `Line ${String(data.lineIndex)}`}
          {type === 'trafo' && `Transformer ${String(data.trafoIndex)}`}
          {data.name ? ` (${String(data.name)})` : ''}
        </span>
        <button onClick={onClose} className="p-1 hover:bg-muted rounded">
          <X className="h-3 w-3" />
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
        {type === 'bus' && (
          <>
            <div><span className="text-muted-foreground">Type:</span> <span className="capitalize">{(data.busType as string)?.replace('_', ' ')}</span></div>
            <div><span className="text-muted-foreground">Voltage:</span> {data.vm_pu != null ? `${(data.vm_pu as number).toFixed(4)} pu` : 'N/A'}</div>
            <div><span className="text-muted-foreground">Nominal:</span> {String(data.vn_kv)} kV</div>
            <div><span className="text-muted-foreground">Status:</span> {data.in_service ? 'In Service' : 'Out of Service'}</div>
            {(data.connectedLoads as LoadData[])?.map((load, i) => (
              <div key={`load-${i}`} className="col-span-2">
                <span className="text-muted-foreground">Load {i}:</span> P={load.p_mw?.toFixed(2)} MW, Q={load.q_mvar?.toFixed(2)} Mvar
              </div>
            ))}
            {(data.connectedGens as GenData[])?.map((gen, i) => (
              <div key={`gen-${i}`} className="col-span-2">
                <span className="text-muted-foreground">Gen {i}:</span> P={gen.p_mw?.toFixed(2)} MW, Vm={gen.vm_pu?.toFixed(3)} pu
              </div>
            ))}
          </>
        )}
        {type === 'line' && (
          <>
            <div><span className="text-muted-foreground">From:</span> Bus {String(data.from_bus)}</div>
            <div><span className="text-muted-foreground">To:</span> Bus {String(data.to_bus)}</div>
            <div><span className="text-muted-foreground">Loading:</span> <span className={data.loading_percent != null && (data.loading_percent as number) > 100 ? 'text-red-500 font-medium' : ''}>{data.loading_percent != null ? `${(data.loading_percent as number).toFixed(2)}%` : 'N/A'}</span></div>
            <div><span className="text-muted-foreground">Length:</span> {data.length_km != null ? `${(data.length_km as number).toFixed(2)} km` : 'N/A'}</div>
            <div><span className="text-muted-foreground">Status:</span> {data.in_service ? 'In Service' : 'Out of Service'}</div>
            {data.max_i_ka && <div><span className="text-muted-foreground">Max I:</span> {String(data.max_i_ka)} kA</div>}
          </>
        )}
        {type === 'trafo' && (
          <>
            <div><span className="text-muted-foreground">HV Bus:</span> {String(data.hv_bus)}</div>
            <div><span className="text-muted-foreground">LV Bus:</span> {String(data.lv_bus)}</div>
            <div><span className="text-muted-foreground">Rating:</span> {data.sn_mva != null ? `${String(data.sn_mva)} MVA` : 'N/A'}</div>
            <div><span className="text-muted-foreground">Status:</span> {data.in_service ? 'In Service' : 'Out of Service'}</div>
            {data.vn_hv_kv && <div><span className="text-muted-foreground">HV:</span> {String(data.vn_hv_kv)} kV</div>}
            {data.vn_lv_kv && <div><span className="text-muted-foreground">LV:</span> {String(data.vn_lv_kv)} kV</div>}
          </>
        )}
      </div>
    </div>
  );
}

function transformNetworkToGraph(
  state: RawNetworkState,
  onHover: (data: TooltipData | null) => void,
  onSelect: (data: SelectedElement | null) => void
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const affectedBuses = new Set(state.affected_components?.bus || []);
  const affectedLines = new Set(state.affected_components?.line || []);
  const affectedTrafos = new Set(state.affected_components?.trafo || []);
  const affectedLoads = new Set(state.affected_components?.load || []);
  const affectedGens = new Set(state.affected_components?.gen || []);

  // Build lookup for connected components per bus
  const busLoads: Record<number, LoadData[]> = {};
  const busGens: Record<number, GenData[]> = {};
  const busExtGrids: Record<number, ExtGridData[]> = {};

  Object.values(state.load || {}).forEach((load) => {
    if (!busLoads[load.bus]) busLoads[load.bus] = [];
    busLoads[load.bus].push(load);
  });

  Object.values(state.gen || {}).forEach((gen) => {
    if (!busGens[gen.bus]) busGens[gen.bus] = [];
    busGens[gen.bus].push(gen);
  });

  Object.values(state.ext_grid || {}).forEach((ext) => {
    if (!busExtGrids[ext.bus]) busExtGrids[ext.bus] = [];
    busExtGrids[ext.bus].push(ext);
  });

  // Determine bus types and service status (ext_grid > gen > load > bus)
  const busTypes: Record<number, string> = {};
  const busOutOfService: Record<number, boolean> = {};

  // Mark ext_grid buses
  Object.entries(state.ext_grid || {}).forEach(([, ext]) => {
    busTypes[ext.bus] = 'ext_grid';
    if (ext.in_service === false) {
      busOutOfService[ext.bus] = true;
    }
  });

  // Mark gen buses (if not already ext_grid)
  Object.entries(state.gen || {}).forEach(([idx, gen]) => {
    if (!busTypes[gen.bus]) {
      busTypes[gen.bus] = 'gen';
      if (gen.in_service === false) {
        busOutOfService[gen.bus] = true;
      }
    }
    if (affectedGens.has(Number(idx))) {
      affectedBuses.add(gen.bus);
    }
  });

  // Mark load buses (if not already marked)
  Object.entries(state.load || {}).forEach(([idx, load]) => {
    if (!busTypes[load.bus]) {
      busTypes[load.bus] = 'load';
      if (load.in_service === false) {
        busOutOfService[load.bus] = true;
      }
    }
    if (affectedLoads.has(Number(idx))) {
      affectedBuses.add(load.bus);
    }
  });

  // Create bus nodes
  Object.entries(state.bus || {}).forEach(([idxStr, bus]) => {
    const idx = Number(idxStr);
    const coords = state.bus_coords?.[idxStr] || { x: 0, y: 0 };
    const isAffected = affectedBuses.has(idx);
    const busType = busTypes[idx] || 'bus';
    const isOutOfService = busOutOfService[idx] || false;
    const voltage = state.res_bus?.[idxStr]?.vm_pu;

    nodes.push({
      id: `bus-${idx}`,
      type: 'bus',
      position: { x: coords.x, y: coords.y },
      data: {
        label: String(idx),
        name: bus.name,
        vn_kv: bus.vn_kv,
        vm_pu: voltage,
        isAffected,
        isOutOfService,
        busType,
        in_service: bus.in_service,
        connectedLoads: busLoads[idx] || [],
        connectedGens: busGens[idx] || [],
        connectedExtGrids: busExtGrids[idx] || [],
        onHover,
        onSelect,
      },
    });
  });

  // Create edges from lines
  Object.entries(state.line || {}).forEach(([idxStr, line]) => {
    const idx = Number(idxStr);
    const isAffected = affectedLines.has(idx);
    const loading = state.res_line?.[idxStr]?.loading_percent;
    const hasLoading = loading != null && !isNaN(loading);
    const isOutOfService = line.in_service === false;

    edges.push({
      id: `line-${idx}`,
      source: `bus-${line.from_bus}`,
      target: `bus-${line.to_bus}`,
      type: 'custom',
      style: {
        stroke: isAffected ? '#ef4444' : '#64748b',
        strokeWidth: isAffected ? 3 : 2,
        strokeDasharray: isOutOfService ? '5,5' : undefined,
        opacity: isOutOfService ? 0.5 : 1,
      },
      label: hasLoading ? `${loading.toFixed(0)}%` : undefined,
      labelStyle: {
        fill: isAffected ? '#ef4444' : '#64748b',
        fontSize: 10,
      },
      data: {
        edgeType: 'line' as const,
        lineIndex: idx,
        name: line.name,
        loading_percent: loading,
        from_bus: line.from_bus,
        to_bus: line.to_bus,
        length_km: line.length_km,
        max_i_ka: line.max_i_ka,
        isAffected,
        in_service: line.in_service,
        onHover,
        onSelect,
      },
    });
  });

  // Create edges from transformers
  Object.entries(state.trafo || {}).forEach(([idxStr, trafo]) => {
    const idx = Number(idxStr);
    const isAffected = affectedTrafos.has(idx);
    const isOutOfService = trafo.in_service === false;

    edges.push({
      id: `trafo-${idx}`,
      source: `bus-${trafo.hv_bus}`,
      target: `bus-${trafo.lv_bus}`,
      type: 'custom',
      style: {
        stroke: isAffected ? '#ef4444' : '#8b5cf6',
        strokeWidth: isAffected ? 3 : 2,
        strokeDasharray: isOutOfService ? '5,5' : undefined,
        opacity: isOutOfService ? 0.5 : 1,
      },
      label: 'T',
      labelStyle: { fill: '#8b5cf6', fontSize: 10 },
      data: {
        edgeType: 'trafo' as const,
        trafoIndex: idx,
        name: trafo.name,
        hv_bus: trafo.hv_bus,
        lv_bus: trafo.lv_bus,
        sn_mva: trafo.sn_mva,
        vn_hv_kv: trafo.vn_hv_kv,
        vn_lv_kv: trafo.vn_lv_kv,
        isAffected,
        in_service: trafo.in_service,
        onHover,
        onSelect,
      },
    });
  });

  return { nodes, edges };
}

export function NetworkGraph({ networkState, isLoading }: NetworkGraphProps) {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [selected, setSelected] = useState<SelectedElement | null>(null);

  const handleHover = useCallback((data: TooltipData | null) => {
    setTooltip(data);
  }, []);

  const handleSelect = useCallback((data: SelectedElement | null) => {
    setSelected(data);
  }, []);

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    if (!networkState) return { nodes: [], edges: [] };
    return transformNetworkToGraph(networkState, handleHover, handleSelect);
  }, [networkState, handleHover, handleSelect]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes/edges when networkState changes
  useEffect(() => {
    if (networkState) {
      const { nodes: newNodes, edges: newEdges } = transformNetworkToGraph(networkState, handleHover, handleSelect);
      setNodes(newNodes);
      setEdges(newEdges);
    }
  }, [networkState, setNodes, setEdges, handleHover, handleSelect]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-muted/20">
        <Loader2 className="h-8 w-8 text-primary animate-spin mb-4" />
        <p className="text-sm text-muted-foreground">Simulating network overrides...</p>
      </div>
    );
  }

  if (!networkState) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-muted/20">
        <p className="text-sm text-muted-foreground">No network data available</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      </ReactFlow>

      {/* Legend - top right, compact */}
      <div className="absolute top-2 right-2 bg-background/80 hover:bg-background/95 border rounded px-2 py-1.5 text-[10px] space-y-0.5 transition-opacity opacity-70 hover:opacity-100 z-10">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          <span>Ext Grid</span>
          <div className="w-2.5 h-2.5 rounded-full bg-orange-500 ml-2" />
          <span>Gen</span>
          <div className="w-2.5 h-2.5 rounded-full bg-gray-500 ml-2" />
          <span>Load</span>
          <div className="w-2.5 h-2.5 rounded-full bg-blue-500 ml-2" />
          <span>Bus</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-slate-500" />
          <span>Line</span>
          <div className="w-3 h-0.5 bg-purple-500 ml-2" />
          <span>Trafo</span>
          <div className="w-2.5 h-2.5 rounded-full border-2 border-red-500 ml-2" />
          <span>Affected</span>
          <div className="w-2.5 h-2.5 rounded-full bg-gray-400 opacity-50 border border-dashed border-slate-500 ml-2" />
          <span>Out</span>
        </div>
      </div>

      {/* Hover tooltip */}
      {tooltip && <Tooltip tooltip={tooltip} />}

      {/* Selected element detail panel */}
      {selected && (
        <DetailPanel
          selected={selected}
          onClose={() => setSelected(null)}
          networkState={networkState}
        />
      )}
    </div>
  );
}
