'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { OverrideState, RawNetworkState, LoadValues, GenValues, ExtGridValues } from '@/types/diagnostic';
import { RefreshCcw, Play, Loader2, Stethoscope } from 'lucide-react';

interface NetworkControlBoardProps {
    networkState: RawNetworkState | null;
    onApplyOverrides: (overrides: OverrideState) => Promise<void>;
    onReDiagnose: (overrides: OverrideState) => void;
    isLoading: boolean;
    isReDiagnosing: boolean;
    lastSimulationConverged: boolean | null;
}

const DEFAULT_OVERRIDES: OverrideState = {
    globalLoadScale: 1.0,
    lineStates: {},
    trafoStates: {},
    genStates: {},
    loadStates: {},
    extGridStates: {},
    loadValues: {},
    genValues: {},
    extGridValues: {},
};

export function NetworkControlBoard({ networkState, onApplyOverrides, onReDiagnose, isLoading, isReDiagnosing, lastSimulationConverged }: NetworkControlBoardProps) {
    const [overrides, setOverrides] = useState<OverrideState>(DEFAULT_OVERRIDES);

    const handleGlobalScaleChange = (value: number[]) => {
        setOverrides(prev => ({ ...prev, globalLoadScale: value[0] }));
    };

    const setLineState = (index: number, inService: boolean) => {
        setOverrides(prev => {
            const newLineStates = { ...prev.lineStates, [index]: inService };
            return { ...prev, lineStates: newLineStates };
        });
    };

    // Gen state (in_service only)
    const setGenState = (index: number, inService: boolean) => {
        setOverrides(prev => ({
            ...prev,
            genStates: { ...prev.genStates, [index]: inService }
        }));
    };

    // Gen values (p_mw, vm_pu)
    const updateGenValue = (index: number, field: keyof GenValues, value: string) => {
        const numValue = parseFloat(value);
        if (isNaN(numValue)) return;
        setOverrides(prev => {
            const currentValues = { ...prev.genValues };
            if (!currentValues[index]) currentValues[index] = {};
            currentValues[index][field] = numValue;
            return { ...prev, genValues: currentValues };
        });
    };

    // Load state (in_service only)
    const setLoadState = (index: number, inService: boolean) => {
        setOverrides(prev => ({
            ...prev,
            loadStates: { ...prev.loadStates, [index]: inService }
        }));
    };

    // Load values (p_mw, q_mvar)
    const updateLoadValue = (index: number, field: keyof LoadValues, value: string) => {
        const numValue = parseFloat(value);
        if (isNaN(numValue)) return;
        setOverrides(prev => {
            const currentValues = { ...prev.loadValues };
            if (!currentValues[index]) currentValues[index] = {};
            currentValues[index][field] = numValue;
            return { ...prev, loadValues: currentValues };
        });
    };

    // ExtGrid state (in_service only)
    const setExtGridState = (index: number, inService: boolean) => {
        setOverrides(prev => ({
            ...prev,
            extGridStates: { ...prev.extGridStates, [index]: inService }
        }));
    };

    // ExtGrid values (vm_pu)
    const updateExtGridValue = (index: number, field: keyof ExtGridValues, value: string) => {
        const numValue = parseFloat(value);
        if (isNaN(numValue)) return;
        setOverrides(prev => {
            const currentValues = { ...prev.extGridValues };
            if (!currentValues[index]) currentValues[index] = {};
            currentValues[index][field] = numValue;
            return { ...prev, extGridValues: currentValues };
        });
    };

    const setTrafoState = (index: number, inService: boolean) => {
        setOverrides(prev => {
            const newTrafoStates = { ...prev.trafoStates, [index]: inService };
            return { ...prev, trafoStates: newTrafoStates };
        });
    };

    const handleReset = () => {
        setOverrides(DEFAULT_OVERRIDES);
        onApplyOverrides(DEFAULT_OVERRIDES);
    };

    const handleApply = async () => {
        await onApplyOverrides(overrides);
        // Don't reset overrides - keep them so Re-run Diagnosis works
    };

    if (!networkState) {
        return (
            <Card className="h-full">
                <CardContent className="flex items-center justify-center p-6 text-muted-foreground">
                    No network data available for manipulation.
                </CardContent>
            </Card>
        );
    }

    // Convert array-like objects to arrays for easier mapping
    const lines = Object.entries(networkState.line || {});
    const loads = Object.entries(networkState.load || {});
    const gens = Object.entries(networkState.gen || {});
    const trafos = Object.entries(networkState.trafo || {});
    const extGrids = Object.entries(networkState.ext_grid || {});

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-3 border-b">
                <CardTitle className="text-md flex justify-between items-center">
                    Manual Controls
                    <div className="flex gap-2">
                        <Button variant="outline" size="icon" onClick={handleReset} disabled={isLoading} aria-label="Reset">
                            <RefreshCcw className="h-4 w-4" />
                        </Button>
                        <Button size="icon" onClick={handleApply} disabled={isLoading} aria-label="Apply Overrides">
                            <Play className="h-4 w-4" />
                        </Button>
                    </div>
                </CardTitle>
                <CardDescription>Tweak parameters and re-run flow</CardDescription>

                {/* Convergence Status */}
                {lastSimulationConverged !== null && (
                    <div className={`mt-2 px-3 py-2 rounded-md text-sm font-medium ${
                        lastSimulationConverged
                            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                            : 'bg-red-500/10 text-red-600 dark:text-red-400'
                    }`}>
                        {lastSimulationConverged ? '✓ Power flow converged' : '✗ Power flow did not converge'}
                    </div>
                )}

                <Button
                    className="w-full mt-3"
                    variant="secondary"
                    onClick={() => {
                        console.log('Re-diagnose sending overrides:', JSON.stringify(overrides, null, 2));
                        onReDiagnose(overrides);
                    }}
                    disabled={isLoading || isReDiagnosing}
                >
                    {isReDiagnosing ? (
                        <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Re-analyzing...
                        </>
                    ) : (
                        <>
                            <Stethoscope className="h-4 w-4 mr-2" />
                            Re-run Diagnosis
                        </>
                    )}
                </Button>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto p-0">
                <div className="p-4 space-y-6">
                    {/* Global Controls */}
                    <div className="space-y-3">
                        <div className="flex justify-between items-center text-sm font-medium">
                            <span>Global Load Scale</span>
                            <span>{(overrides.globalLoadScale * 100).toFixed(0)}%</span>
                        </div>
                        <Slider
                            value={[overrides.globalLoadScale]}
                            min={0}
                            max={3}
                            step={0.1}
                            onValueChange={handleGlobalScaleChange}
                            disabled={isLoading}
                        />
                    </div>

                    <Accordion type="multiple" className="w-full">
                        {/* Lines & Topology */}
                        <AccordionItem value="lines">
                            <AccordionTrigger className="text-sm font-medium">Lines & Topology ({lines.length})</AccordionTrigger>
                            <AccordionContent>
                                <div className="space-y-2 pt-2">
                                    {lines.map(([idxStr, line]) => {
                                        const idx = parseInt(idxStr);
                                        // Use override if set, otherwise use networkState
                                        const inService = idx in overrides.lineStates
                                            ? overrides.lineStates[idx]
                                            : line.in_service !== false;

                                        return (
                                            <div key={`line-${idxStr}`} className="flex items-center justify-between text-xs p-2 rounded bg-muted/30">
                                                <span>{line.name || `Line ${idxStr}`} (Bus {line.from_bus} ➔ {line.to_bus})</span>
                                                <div className="flex items-center gap-2">
                                                    <span className={!inService ? "text-destructive" : "text-success"}>
                                                        {!inService ? "Tripped" : "In Service"}
                                                    </span>
                                                    <Switch
                                                        checked={inService}
                                                        onCheckedChange={(checked) => setLineState(idx, checked)}
                                                        disabled={isLoading}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </AccordionContent>
                        </AccordionItem>

                        {/* Generators */}
                        <AccordionItem value="gens">
                            <AccordionTrigger className="text-sm font-medium">Generators ({gens.length})</AccordionTrigger>
                            <AccordionContent>
                                <div className="space-y-4 pt-2">
                                    {gens.map(([idxStr, gen]) => {
                                        const idx = parseInt(idxStr);
                                        const currentP = overrides.genValues[idx]?.p_mw ?? gen.p_mw;
                                        const currentV = overrides.genValues[idx]?.vm_pu ?? gen.vm_pu;
                                        // Use explicit state map, fall back to networkState
                                        const inService = idx in overrides.genStates
                                            ? overrides.genStates[idx]
                                            : gen.in_service !== false;
                                        return (
                                            <div key={`gen-${idxStr}`} className="space-y-2 p-2 rounded bg-muted/30 text-xs">
                                                <div className="flex items-center justify-between font-medium">
                                                    <span>{gen.name || `Gen ${idxStr}`} (Bus {gen.bus})</span>
                                                    <div className="flex items-center gap-2">
                                                        <span className={!inService ? "text-destructive" : "text-success"}>
                                                            {!inService ? "Tripped" : "In Service"}
                                                        </span>
                                                        <Switch
                                                            checked={inService}
                                                            onCheckedChange={(val) => setGenState(idx, val)}
                                                            disabled={isLoading}
                                                        />
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <label className="w-16">P (MW)</label>
                                                    <Input
                                                        type="number"
                                                        className="h-7 text-xs"
                                                        value={currentP}
                                                        onChange={(e) => updateGenValue(idx, 'p_mw', e.target.value)}
                                                        disabled={isLoading}
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <label className="w-16">V (p.u.)</label>
                                                    <Input
                                                        type="number"
                                                        className="h-7 text-xs"
                                                        value={currentV}
                                                        step={0.01}
                                                        onChange={(e) => updateGenValue(idx, 'vm_pu', e.target.value)}
                                                        disabled={isLoading}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </AccordionContent>
                        </AccordionItem>

                        {/* Loads */}
                        <AccordionItem value="loads">
                            <AccordionTrigger className="text-sm font-medium">Loads ({loads.length})</AccordionTrigger>
                            <AccordionContent>
                                <div className="space-y-4 pt-2">
                                    {loads.map(([idxStr, load]) => {
                                        const idx = parseInt(idxStr);
                                        const currentP = overrides.loadValues[idx]?.p_mw ?? load.p_mw;
                                        const currentQ = overrides.loadValues[idx]?.q_mvar ?? load.q_mvar;
                                        // Use explicit state map, fall back to networkState
                                        const inService = idx in overrides.loadStates
                                            ? overrides.loadStates[idx]
                                            : load.in_service !== false;
                                        return (
                                            <div key={`load-${idxStr}`} className="space-y-2 p-2 rounded bg-muted/30 text-xs">
                                                <div className="flex items-center justify-between font-medium">
                                                    <span>{load.name || `Load ${idxStr}`} (Bus {load.bus})</span>
                                                    <div className="flex items-center gap-2">
                                                        <span className={!inService ? "text-destructive" : "text-success"}>
                                                            {!inService ? "Tripped" : "In Service"}
                                                        </span>
                                                        <Switch
                                                            checked={inService}
                                                            onCheckedChange={(val) => setLoadState(idx, val)}
                                                            disabled={isLoading}
                                                        />
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <label className="w-16">P (MW)</label>
                                                    <Input
                                                        type="number"
                                                        className="h-7 text-xs"
                                                        value={currentP}
                                                        onChange={(e) => updateLoadValue(idx, 'p_mw', e.target.value)}
                                                        disabled={isLoading}
                                                    />
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <label className="w-16">Q (MVAR)</label>
                                                    <Input
                                                        type="number"
                                                        className="h-7 text-xs"
                                                        value={currentQ}
                                                        onChange={(e) => updateLoadValue(idx, 'q_mvar', e.target.value)}
                                                        disabled={isLoading}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </AccordionContent>
                        </AccordionItem>

                        {/* Transformers */}
                        {trafos.length > 0 && (
                            <AccordionItem value="trafos">
                                <AccordionTrigger className="text-sm font-medium">Transformers ({trafos.length})</AccordionTrigger>
                                <AccordionContent>
                                    <div className="space-y-4 pt-2">
                                        {trafos.map(([idxStr, trafo]) => {
                                            const idx = parseInt(idxStr);
                                            // Use override if set, otherwise use networkState
                                            const inService = idx in overrides.trafoStates
                                                ? overrides.trafoStates[idx]
                                                : trafo.in_service !== false;

                                            return (
                                                <div key={`trafo-${idxStr}`} className="flex items-center justify-between text-xs p-2 rounded bg-muted/30">
                                                    <span>{trafo.name || `Trafo ${idxStr}`} (Bus {trafo.hv_bus} ➔ {trafo.lv_bus})</span>
                                                    <div className="flex items-center gap-2">
                                                        <span className={!inService ? "text-destructive" : "text-success"}>
                                                            {!inService ? "Tripped" : "In Service"}
                                                        </span>
                                                        <Switch
                                                            checked={inService}
                                                            onCheckedChange={(checked) => setTrafoState(idx, checked)}
                                                            disabled={isLoading}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>
                        )}

                        {/* External Grids */}
                        {extGrids.length > 0 && (
                            <AccordionItem value="ext_grids">
                                <AccordionTrigger className="text-sm font-medium">External Grids ({extGrids.length})</AccordionTrigger>
                                <AccordionContent>
                                    <div className="space-y-4 pt-2">
                                        {extGrids.map(([idxStr, ext]) => {
                                            const idx = parseInt(idxStr);
                                            const currentV = overrides.extGridValues[idx]?.vm_pu ?? ext.vm_pu;
                                            // Use explicit state map, fall back to networkState
                                            const inService = idx in overrides.extGridStates
                                                ? overrides.extGridStates[idx]
                                                : ext.in_service !== false;
                                            return (
                                                <div key={`ext-${idxStr}`} className="space-y-2 p-2 rounded bg-muted/30 text-xs">
                                                    <div className="flex items-center justify-between font-medium">
                                                        <span>{ext.name || `Ext Grid ${idxStr}`} (Bus {ext.bus})</span>
                                                        <div className="flex items-center gap-2">
                                                            <span className={!inService ? "text-destructive" : "text-success"}>
                                                                {!inService ? "Tripped" : "In Service"}
                                                            </span>
                                                            <Switch
                                                                checked={inService}
                                                                onCheckedChange={(val) => setExtGridState(idx, val)}
                                                                disabled={isLoading}
                                                            />
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <label className="w-16">V (p.u.)</label>
                                                        <Input
                                                            type="number"
                                                            className="h-7 text-xs"
                                                            value={currentV}
                                                            step={0.01}
                                                            onChange={(e) => updateExtGridValue(idx, 'vm_pu', e.target.value)}
                                                            disabled={isLoading}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>
                        )}

                    </Accordion>
                </div>
            </CardContent>
        </Card>
    );
}
