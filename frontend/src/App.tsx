import { useState, useEffect, useCallback } from 'react';
import './App.css';
import ServiceSelector from './components/ServiceSelector';
import TemplateResults from './components/TemplateResults';
import { getTemplates, filterTemplates } from './api/client';
import type { Template, FilteredTemplate } from './types';

function App() {
  const [services, setServices] = useState<string[]>([]);
  const [selectedServices, setSelectedServices] = useState<Set<string>>(new Set());
  const [, setTemplates] = useState<Template[]>([]);
  const [filteredTemplates, setFilteredTemplates] = useState<FilteredTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    setWarnings([]);
    try {
      const data = await getTemplates();
      setServices(data.services);
      setTemplates(data.templates);
      if (data.warnings?.length) {
        setWarnings(data.warnings);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleGenerate = async () => {
    if (selectedServices.size === 0) return;
    setLoading(true);
    setError(null);
    try {
      const data = await filterTemplates(Array.from(selectedServices));
      setFilteredTemplates(data.filteredTemplates);
      if (data.warnings?.length) {
        setWarnings(data.warnings);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate templates.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>NZISM Config Filter</h1>
        <p className="app-subtitle">
          Generate filtered AWS Config conformance pack templates for the services you use.
        </p>
      </header>

      {error && (
        <div className="banner banner-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={loadTemplates} className="retry-button">
            Retry
          </button>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="banner banner-warning" role="status">
          <strong>Warning:</strong> Some templates could not be fully parsed:
          <ul className="warning-list">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {loading && (
        <div className="loading" aria-live="polite">
          <div className="spinner" />
          <span>Loading…</span>
        </div>
      )}

      {!error && !loading && services.length > 0 && (
        <>
          <ServiceSelector
            services={services}
            selectedServices={selectedServices}
            onSelectionChange={setSelectedServices}
          />

          <div className="generate-section">
            <button
              type="button"
              className="generate-button"
              disabled={loading || selectedServices.size === 0}
              onClick={handleGenerate}
            >
              Generate Templates
            </button>
          </div>

          <TemplateResults filteredTemplates={filteredTemplates} />
        </>
      )}
    </div>
  );
}

export default App;
