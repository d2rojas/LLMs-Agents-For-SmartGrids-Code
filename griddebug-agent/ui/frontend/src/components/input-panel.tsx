'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Network, Scenario } from '@/types/diagnostic';
import { fetchNetworks, fetchScenarios } from '@/lib/api';

type InputMode = 'preset' | 'nl';

interface InputPanelProps {
  onAnalyze: (network: string, scenario: string, query?: string) => void;
  onAnalyzeNL: (network: string, description: string) => void;
  isLoading: boolean;
}

const EXAMPLE_PROMPTS = [
  'Scale all loads by 15x to cause non-convergence',
  'Take line 5 out of service and double loads at bus 10',
  'Run AC power flow and show the total active power loss',
  'What are the connected buses for line 11?',
  'Perform N-1 contingency on line 171 and summarize violations',
];

export function InputPanel({ onAnalyze, onAnalyzeNL, isLoading }: InputPanelProps) {
  const [networks, setNetworks] = useState<Network[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedNetwork, setSelectedNetwork] = useState<string>('');
  const [selectedScenario, setSelectedScenario] = useState<string>('');
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [mode, setMode] = useState<InputMode>('nl');
  const [nlDescription, setNlDescription] = useState<string>('');
  const [presetQuery, setPresetQuery] = useState<string>(''); // optional benchmark/user query for preset mode

  useEffect(() => {
    async function loadData() {
      try {
        const [networksData, scenariosData] = await Promise.all([
          fetchNetworks(),
          fetchScenarios(),
        ]);
        setNetworks(networksData);
        setScenarios(scenariosData);
        setFetchError(null);
      } catch {
        setFetchError('Failed to load data. Is the backend running?');
      }
    }
    loadData();
  }, []);

  const handleAnalyze = () => {
    if (mode === 'preset') {
      if (selectedNetwork && selectedScenario) {
        onAnalyze(selectedNetwork, selectedScenario, presetQuery.trim() || undefined);
      }
    } else {
      if (selectedNetwork && nlDescription.trim()) {
        onAnalyzeNL(selectedNetwork, nlDescription.trim());
      }
    }
  };

  const canRun =
    mode === 'preset'
      ? selectedNetwork && selectedScenario
      : selectedNetwork && nlDescription.trim();

  const selectedScenarioData = scenarios.find(s => s.id === selectedScenario);

  return (
    <div className="flex flex-col h-full p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold mb-2">GridDebugAgent</h1>
        <p className="text-muted-foreground">
          Analyze power flow failures and get diagnostic recommendations
        </p>
      </div>

      {fetchError && (
        <div className="mb-4 p-3 bg-destructive/10 text-destructive rounded-md text-sm">
          {fetchError}
        </div>
      )}

      <div className="flex-1 space-y-6">
        {/* Mode Toggle */}
        <div className="flex rounded-lg border border-border overflow-hidden">
          <button
            onClick={() => setMode('nl')}
            className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${mode === 'nl'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted/30 text-muted-foreground hover:bg-muted/50'
              }`}
          >
            Query / Scenario
          </button>
          <button
            onClick={() => setMode('preset')}
            className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${mode === 'preset'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted/30 text-muted-foreground hover:bg-muted/50'
              }`}
          >
            Preset Scenarios
          </button>
        </div>

        {/* Network Selector (shown in both modes) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Network</CardTitle>
            <CardDescription>
              Select an IEEE test network
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedNetwork} onValueChange={setSelectedNetwork}>
              <SelectTrigger>
                <SelectValue placeholder="Select network..." />
              </SelectTrigger>
              <SelectContent>
                {networks.map((network) => (
                  <SelectItem key={network.id} value={network.id}>
                    {network.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Preset Mode: Scenario Dropdown */}
        {mode === 'preset' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Failure Scenario</CardTitle>
              <CardDescription>
                Choose a failure scenario to diagnose
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select value={selectedScenario} onValueChange={setSelectedScenario}>
                <SelectTrigger>
                  <SelectValue placeholder="Select scenario..." />
                </SelectTrigger>
                <SelectContent>
                  {scenarios.map((scenario) => (
                    <SelectItem key={scenario.id} value={scenario.id}>
                      <div className="flex flex-col items-start">
                        <span>{scenario.label}</span>
                        <span className="text-xs text-muted-foreground">
                          {scenario.category}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {selectedScenarioData && (
                <div className="p-3 bg-muted/50 rounded-md text-sm text-muted-foreground">
                  Category: {selectedScenarioData.category}
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-muted-foreground block mb-1">
                  Optional: Benchmark / user query
                </label>
                <textarea
                  className="w-full min-h-[60px] p-2 rounded-md border border-input bg-background text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="e.g. Find top 5 heavily loaded lines; Run contingency analysis..."
                  value={presetQuery}
                  onChange={(e) => setPresetQuery(e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Used for paper benchmark or task-focused evaluation (run power flow, find overloads, etc.)
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* NL Mode: Text Area + Examples */}
        {mode === 'nl' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Query</CardTitle>
              <CardDescription>
                Ask a question about the network or describe a failure to simulate
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <textarea
                className="w-full min-h-[120px] p-3 rounded-md border border-input bg-background text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="e.g. Run AC power flow and show total losses, or: Take line 3 out of service..."
                value={nlDescription}
                onChange={(e) => setNlDescription(e.target.value)}
              />
              <div>
                <p className="text-xs text-muted-foreground mb-2">Try an example:</p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_PROMPTS.map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => setNlDescription(prompt)}
                      className="text-xs px-2.5 py-1.5 rounded-full border border-border bg-muted/30 text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <Button
          onClick={handleAnalyze}
          disabled={!canRun || isLoading}
          className="w-full"
          size="lg"
        >
          {isLoading ? 'Analyzing...' : mode === 'nl' ? 'Generate & Analyze' : 'Run Analysis'}
        </Button>
      </div>
    </div>
  );
}
