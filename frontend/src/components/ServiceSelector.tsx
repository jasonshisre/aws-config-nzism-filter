import { useState, useMemo } from 'react';

interface ServiceSelectorProps {
  services: string[];
  selectedServices: Set<string>;
  onSelectionChange: (selected: Set<string>) => void;
}

export default function ServiceSelector({
  services,
  selectedServices,
  onSelectionChange,
}: ServiceSelectorProps) {
  const [search, setSearch] = useState('');

  const sortedServices = useMemo(
    () => [...services].sort((a, b) => a.localeCompare(b)),
    [services]
  );

  const filteredServices = useMemo(() => {
    if (!search.trim()) return sortedServices;
    const term = search.toLowerCase();
    return sortedServices.filter((s) => s.toLowerCase().includes(term));
  }, [sortedServices, search]);

  const toggleService = (service: string) => {
    const next = new Set(selectedServices);
    if (next.has(service)) {
      next.delete(service);
    } else {
      next.add(service);
    }
    onSelectionChange(next);
  };

  const selectAll = () => {
    onSelectionChange(new Set(services));
  };

  const clearAll = () => {
    onSelectionChange(new Set());
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.count}>
          {selectedServices.size} of {services.length} services selected
        </span>
        <div style={styles.buttons}>
          <button type="button" onClick={selectAll} style={styles.button}>
            Select All
          </button>
          <button type="button" onClick={clearAll} style={styles.button}>
            Clear All
          </button>
        </div>
      </div>

      <input
        type="text"
        placeholder="Search services…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={styles.search}
        aria-label="Search services"
      />

      <div style={styles.list}>
        {filteredServices.length === 0 && (
          <p style={styles.empty}>No services match "{search}"</p>
        )}
        {filteredServices.map((service) => (
          <label key={service} style={styles.label}>
            <input
              type="checkbox"
              checked={selectedServices.has(service)}
              onChange={() => toggleService(service)}
              style={styles.checkbox}
            />
            {service}
          </label>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    border: '1px solid #ddd',
    borderRadius: 8,
    padding: 16,
    maxWidth: 480,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    flexWrap: 'wrap',
    gap: 8,
  },
  count: {
    fontSize: 14,
    color: '#555',
  },
  buttons: {
    display: 'flex',
    gap: 8,
  },
  button: {
    padding: '4px 12px',
    fontSize: 13,
    cursor: 'pointer',
    border: '1px solid #ccc',
    borderRadius: 4,
    background: '#f5f5f5',
    color: '#24292e',
  },
  search: {
    width: '100%',
    padding: '8px 10px',
    fontSize: 14,
    border: '1px solid #ccc',
    borderRadius: 4,
    marginBottom: 12,
    boxSizing: 'border-box',
  },
  list: {
    maxHeight: 320,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  label: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '4px 0',
    fontSize: 14,
    cursor: 'pointer',
    color: '#24292e',
  },
  checkbox: {
    cursor: 'pointer',
  },
  empty: {
    color: '#999',
    fontStyle: 'italic',
    fontSize: 14,
    margin: 0,
  },
};
