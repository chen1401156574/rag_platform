import { api } from "@/services/api";

export interface LLMProvider {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  enabled_models: string[];
  is_active: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface FetchModelsResult {
  models: string[];
}

export async function listProviders(): Promise<LLMProvider[]> {
  return api.get<LLMProvider[], LLMProvider[]>("/llm-providers/list");
}

export async function createProvider(data: {
  name: string;
  base_url: string;
  api_key: string;
}): Promise<LLMProvider> {
  return api.post<LLMProvider, LLMProvider>("/llm-providers/create", data);
}

export async function updateProvider(
  id: string,
  data: {
    name?: string;
    base_url?: string;
    api_key?: string;
    enabled_models?: string[];
    is_active?: number;
  }
): Promise<LLMProvider> {
  return api.put<LLMProvider, LLMProvider>(`/llm-providers/${id}`, data);
}

export async function deleteProvider(id: string): Promise<void> {
  return api.delete<void, void>(`/llm-providers/${id}`);
}

export async function fetchProviderModels(id: string): Promise<FetchModelsResult> {
  return api.post<FetchModelsResult, FetchModelsResult>(
    `/llm-providers/${id}/fetch-models`
  );
}

export async function testProviderConnection(id: string): Promise<void> {
  return api.post<void, void>(`/llm-providers/${id}/test`);
}
