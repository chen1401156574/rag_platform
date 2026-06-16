import type { AxiosRequestConfig } from "axios";

import { api, asDataResponse, withApiRoot, type DataResponse } from "@/services/api";

const CHAT_STREAM_TIMEOUT_MS = 0;

export function list(params?: Record<string, never>, options?: AxiosRequestConfig): Promise<DataResponse<{ sessions: API.Session[] }>> {
  return asDataResponse(
    api.get<{ sessions: API.Session[] }, { sessions: API.Session[] }>("/get_sessions", {
      ...withApiRoot(options),
      params
    })
  );
}

export function detail(
  params: {
    session_id: string;
  },
  options?: AxiosRequestConfig
): Promise<
  DataResponse<
    {
      created_at: string;
      message_id: string;
      session_id: string;
      user_question: string;
      model_answer: string;
      think?: string;
      documents?: string;
      recommended_questions?: string;
      message_type?: string;
      metadata_json?: string;
      original_question?: string;
      clarifications?: string;
      clarifying_questions?: string[];
      legacy_merged_clarification?: boolean;
    }[]
  >
> {
  return asDataResponse(
    api.get("/get_messages", {
      ...withApiRoot(options),
      params
    })
  );
}

export function create(params?: Record<string, never>, options?: AxiosRequestConfig): Promise<DataResponse<{ session_id: string }>> {
  return asDataResponse(api.post<{ session_id: string }, { session_id: string }>("/create_session", params, withApiRoot(options)));
}

export function chat(
  params: {
    id: string;
    message: string;
    clarifications?: string;
    original_question?: string;
  },
  options?: AxiosRequestConfig
): Promise<DataResponse<ReadableStream<Uint8Array>>> {
  const { id, ...requestParams } = params;
  return asDataResponse(
    api.post<ReadableStream<Uint8Array>, ReadableStream<Uint8Array>>(
      "/chat_on_docs",
      {
        message: requestParams.message,
        clarifications: requestParams.clarifications,
        original_question: requestParams.original_question
      },
      {
        ...withApiRoot(options),
        headers: {
          Accept: "text/event-stream",
          ...options?.headers
        },
        responseType: "stream",
        adapter: "fetch",
        timeout: CHAT_STREAM_TIMEOUT_MS,
        loading: false,
        cancelRepeat: false,
        errorToast: false,
        params: {
          session_id: id
        }
      }
    )
  );
}

export function quickParse(
  params: {
    session_id: string;
    file: File;
  },
  options?: AxiosRequestConfig
): Promise<DataResponse<Record<string, unknown>>> {
  const { file, ...requestParams } = params;
  const formData = new FormData();
  formData.append("file", file);
  return asDataResponse(
    api.post<Record<string, unknown>, Record<string, unknown>>("/quick_parse", formData, {
      ...withApiRoot(options),
      params: requestParams
    })
  );
}

export function documents(
  params: {
    session_id: string;
  },
  options?: AxiosRequestConfig
): Promise<
  DataResponse<{
    documents?: {
      created_at: string;
      document_name: string;
      document_type: string;
      file_size: number;
      id: number;
      session_id: string;
      updated_at: string;
      upload_time: string;
    }[];
    has_documents: boolean;
  }>
> {
  const { session_id, ...requestParams } = params;
  return asDataResponse(
    api.get(`/sessions/${session_id}/documents`, {
      ...withApiRoot(options),
      params: requestParams
    })
  );
}
