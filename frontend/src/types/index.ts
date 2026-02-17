export interface Template {
  name: string;
  ruleCount: number;
}

export interface FilteredTemplate {
  name: string;
  yaml: string;
  ruleCount: number;
  originalRuleCount: number;
  explanation: string;
}

export interface AppState {
  services: string[];
  selectedServices: Set<string>;
  templates: Template[];
  filteredTemplates: FilteredTemplate[];
  loading: boolean;
  error: string | null;
}
