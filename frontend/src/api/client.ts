import axios, { AxiosError } from 'axios';
import type { Template, FilteredTemplate } from '../types';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
});

export interface GetTemplatesResponse {
  templates: Template[];
  services: string[];
  warnings?: string[];
}

export interface FilterTemplatesResponse {
  filteredTemplates: FilteredTemplate[];
  warnings?: string[];
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.response) {
      return `Server error (${error.response.status})`;
    }
    if (error.request) {
      return 'Unable to reach the server. Please check your connection and try again.';
    }
  }
  return 'An unexpected error occurred.';
}

export async function getTemplates(): Promise<GetTemplatesResponse> {
  try {
    const response = await client.get<GetTemplatesResponse>('/templates');
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

export async function filterTemplates(
  selectedServices: string[]
): Promise<FilterTemplatesResponse> {
  try {
    const response = await client.post<FilterTemplatesResponse>('/filter', {
      selectedServices,
    });
    // Ensure filteredTemplates is always an array
    return {
      filteredTemplates: response.data.filteredTemplates || [],
      warnings: response.data.warnings,
    };
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}
