'use client';

import { useState } from 'react';
import { InputPanel } from './input-panel';
import { ResultsPanel } from './results-panel';
import { PipelineResult, DiagnoseNLResponse, DiagnoseResponse } from '@/types/diagnostic';
import { runDiagnosisStream, runNLDiagnosis } from '@/lib/api';

export function DiagnosticLayout() {
  const [fullResponse, setFullResponse] = useState<{ baseline: PipelineResult; agentic: PipelineResult } | null>(null);
  const [nlExtra, setNlExtra] = useState<DiagnoseNLResponse | null>(null);
  const [currentNetwork, setCurrentNetwork] = useState<string | null>(null);
  const [currentScenario, setCurrentScenario] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (network: string, scenario: string, query?: string) => {
    setIsLoading(true);
    setError(null);
    setNlExtra(null);
    setFullResponse(null);
    setCurrentNetwork(network);
    setCurrentScenario(scenario);
    setLoadingStage('Running baseline analysis...');

    try {
      await runDiagnosisStream(network, scenario, query, (event, data) => {
        const typedData = data as PipelineResult;
        switch (event) {
          case 'baseline':
            setFullResponse(prev => ({
              baseline: typedData,
              agentic: prev?.agentic ?? ({} as PipelineResult),
            }));
            setLoadingStage('Running agentic debugger...');
            break;
          case 'agentic':
            setFullResponse(prev => ({
              baseline: prev?.baseline ?? ({} as PipelineResult),
              agentic: typedData
            }));
            setLoadingStage(null);
            break;
          case 'done':
            setLoadingStage(null);
            break;
        }
      });
    } catch {
      setError('Analysis failed. Please try again.');
      setFullResponse(null);
    } finally {
      setIsLoading(false);
      setLoadingStage(null);
    }
  };

  const handleAnalyzeNL = async (network: string, description: string) => {
    setIsLoading(true);
    setError(null);
    setNlExtra(null);
    setFullResponse(null);
    setCurrentNetwork(network);
    setCurrentScenario('nl_generated');
    try {
      const response = await runNLDiagnosis(network, description);
      setNlExtra(response);
      if (response.generationStatus === 'success') {
        setFullResponse({ baseline: response.baseline, agentic: response.agentic });
      } else {
        setError(response.generationError || 'Failed to generate scenario');
        setFullResponse(null);
      }
    } catch {
      setError('NL Analysis failed. Please try again.');
      setFullResponse(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDiagnosisUpdate = (response: DiagnoseResponse) => {
    setFullResponse({ baseline: response.baseline, agentic: response.agentic });
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <div className="w-[360px] min-w-[320px] border-r border-border flex-shrink-0 h-full overflow-y-auto">
        <InputPanel
          onAnalyze={handleAnalyze}
          onAnalyzeNL={handleAnalyzeNL}
          isLoading={isLoading}
        />
      </div>
      <div className="flex-1 h-full overflow-hidden">
        <ResultsPanel
          baselineResult={fullResponse?.baseline ?? null}
          agenticResult={fullResponse?.agentic ?? null}
          nlExtra={nlExtra}
          isLoading={isLoading}
          loadingStage={loadingStage}
          error={error}
          networkName={currentNetwork}
          scenarioName={currentScenario}
          onDiagnosisUpdate={handleDiagnosisUpdate}
        />
      </div>
    </div>
  );
}
