import type { AxiosRequestConfig } from "axios";

import { api, asDataResponse, withApiRoot, type DataResponse } from "@/services/api";

export function list(params?: Record<string, never>, options?: AxiosRequestConfig): Promise<DataResponse<API.Repository[]>> {
  return asDataResponse(
    api.get<API.Repository[], API.Repository[]>("/get_files", {
      ...withApiRoot(options),
      params
    })
  );
}

export function upload(
  params: { files: File },
  options?: AxiosRequestConfig
): Promise<DataResponse<Record<string, unknown>>> {
  const form = new FormData();
  form.append("files", params.files);
  return asDataResponse(
    api.post<Record<string, unknown>, Record<string, unknown>>("/upload_files", form, {
      ...withApiRoot(options),
      headers: {
        "Content-Type": "multipart/form-data",
        ...options?.headers
      }
    })
  );
}

export function remove(
  params: { file_name: string },
  options?: AxiosRequestConfig
): Promise<DataResponse<{ message?: string }>> {
  const { file_name, ...requestParams } = params;
  return asDataResponse(
    api.delete<{ message?: string }, { message?: string }>(`/delete_file/${encodeURIComponent(file_name)}`, {
      ...withApiRoot(options),
      params: requestParams
    })
  );
}
