import { useState, useCallback, useMemo } from 'react';
import yaml from 'js-yaml';
import type { FilteredTemplate } from '../types';

interface TemplateResultsProps {
  filteredTemplates: FilteredTemplate[];
}

export default function TemplateResults({ filteredTemplates }: TemplateResultsProps) {
  if (!filteredTemplates || filteredTemplates.length === 0) {
    return (
      <div style={styles.emptyContainer}>
        <p style={styles.emptyText}>
          No templates to display. Select services and click Generate.
        </p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {filteredTemplates.map((template) => (
        <TemplateCard key={template.name} template={template} />
      ))}
    </div>
  );
}

function TemplateCard({ template }: { template: FilteredTemplate }) {
  const [copyLabel, setCopyLabel] = useState('Copy YAML');
  const [copyJsonLabel, setCopyJsonLabel] = useState('Copy JSON');

  // Strip comment header lines and convert YAML to JSON
  const jsonOutput = useMemo(() => {
    try {
      const yamlBody = template.yaml
        .split('\n')
        .filter((line) => !line.startsWith('#'))
        .join('\n');
      const parsed = yaml.load(yamlBody);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return '{"error": "Failed to convert YAML to JSON"}';
    }
  }, [template.yaml]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(template.yaml);
      setCopyLabel('Copied!');
      setTimeout(() => setCopyLabel('Copy YAML'), 2000);
    } catch {
      setCopyLabel('Copy failed');
      setTimeout(() => setCopyLabel('Copy YAML'), 2000);
    }
  }, [template.yaml]);

  const handleCopyJson = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(jsonOutput);
      setCopyJsonLabel('Copied!');
      setTimeout(() => setCopyJsonLabel('Copy JSON'), 2000);
    } catch {
      setCopyJsonLabel('Copy failed');
      setTimeout(() => setCopyJsonLabel('Copy JSON'), 2000);
    }
  }, [jsonOutput]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([template.yaml], { type: 'application/x-yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = template.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [template.yaml, template.name]);

  const handleDownloadJson = useCallback(() => {
    const blob = new Blob([jsonOutput], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = template.name.replace(/\.yaml$/, '.json');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [jsonOutput, template.name]);

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h3 style={styles.cardTitle}>{template.name}</h3>
        <span style={styles.explanation}>{template.explanation}</span>
      </div>

      <pre style={styles.yamlPreview}>{template.yaml}</pre>

      <div style={styles.actions}>
        <button type="button" onClick={handleCopy} style={styles.primaryButton}>
          {copyLabel}
        </button>
        <button type="button" onClick={handleDownload} style={styles.primaryButton}>
          Download YAML
        </button>
        <span style={styles.separator}>|</span>
        <button type="button" onClick={handleCopyJson} style={styles.secondaryButton}>
          {copyJsonLabel}
        </button>
        <button type="button" onClick={handleDownloadJson} style={styles.secondaryButton}>
          Download JSON
        </button>
      </div>
      <p style={styles.formatNote}>
        Note: AWS Config conformance packs only support YAML format for deployment. JSON is provided for review only.
      </p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
  },
  emptyContainer: {
    border: '1px dashed #ccc',
    borderRadius: 8,
    padding: 32,
    textAlign: 'center',
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
    margin: 0,
  },
  card: {
    border: '1px solid #ddd',
    borderRadius: 8,
    padding: 16,
    background: '#fff',
  },
  cardHeader: {
    marginBottom: 12,
  },
  cardTitle: {
    margin: '0 0 4px 0',
    fontSize: 16,
    fontWeight: 600,
    color: '#24292e',
  },
  explanation: {
    fontSize: 13,
    color: '#666',
  },
  yamlPreview: {
    background: '#f6f8fa',
    color: '#24292e',
    border: '1px solid #e1e4e8',
    borderRadius: 4,
    padding: 12,
    fontSize: 12,
    fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
    overflowX: 'auto',
    overflowY: 'auto',
    maxHeight: 400,
    margin: '0 0 12px 0',
    whiteSpace: 'pre',
    lineHeight: 1.5,
  },
  actions: {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  primaryButton: {
    padding: '6px 14px',
    fontSize: 13,
    cursor: 'pointer',
    border: '1px solid #2a6f3b',
    borderRadius: 4,
    background: '#2ea44f',
    color: '#fff',
    fontWeight: 500,
  },
  secondaryButton: {
    padding: '6px 14px',
    fontSize: 13,
    cursor: 'pointer',
    border: '1px solid #ccc',
    borderRadius: 4,
    background: '#f5f5f5',
    color: '#555',
  },
  separator: {
    color: '#ccc',
    fontSize: 16,
    userSelect: 'none' as const,
  },
  formatNote: {
    fontSize: 12,
    color: '#888',
    margin: '8px 0 0 0',
    fontStyle: 'italic',
  },
};
