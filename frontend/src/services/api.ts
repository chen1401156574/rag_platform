import axios, { AxiosError, CanceledError, type AxiosRequestConfig } from "axios";
import { toast } from "sonner";

import { storage } from "@/utils/storage";

export const API_ROOT_URL = import.meta.env.VITE_API_BASE || "";
export const API_RAGENT_BASE_URL = `${API_ROOT_URL}/api/ragent`;

export const api = axios.create({
  baseURL: API_RAGENT_BASE_URL,
  timeout: 60000
});

const pendingRequests = new Map<string, AbortController>();

export type DataResponse<T> = { data: T };

export function withApiRoot(options?: AxiosRequestConfig): AxiosRequestConfig {
  return {
    ...options,
    baseURL: API_ROOT_URL
  };
}

export async function asDataResponse<T>(request: Promise<T>): Promise<DataResponse<T>> {
  const data = await request;
  return { data };
}

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = token;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

function requestKey(config: AxiosRequestConfig) {
  const params = config.params ? JSON.stringify(config.params) : "";
  const data = config.data instanceof FormData ? "FormData" : config.data ? JSON.stringify(config.data) : "";
  return [config.method, config.baseURL, config.url, params, data, config.repeatKey].join("|");
}

function removePendingRequest(config?: AxiosRequestConfig) {
  if (!config) return;
  const key = requestKey(config);
  const controller = pendingRequests.get(key);
  if (controller) {
    controller.abort();
    pendingRequests.delete(key);
  }
}

function showLoading(config: AxiosRequestConfig) {
  if (config.loading && window.$showLoading) {
    window.$showLoading({ title: "加载中..." });
  }
}

function hideLoading(config?: AxiosRequestConfig) {
  if (config?.loading && window.$hideLoading) {
    window.$hideLoading();
  }
}

function handleAuthExpired(message = "登录状态已失效，请重新登录") {
  storage.clearAuth();
  if (window.location.pathname !== "/login") {
    toast.error(message);
    window.location.href = "/login";
  }
}

api.interceptors.request.use((config) => {
  const token = storage.getToken();
  if (token) {
    config.headers.Authorization = token;
  }
  if (config.cancelRepeat !== false) {
    removePendingRequest(config);
    if (!config.signal) {
      const controller = new AbortController();
      config.signal = controller.signal;
      pendingRequests.set(requestKey(config), controller);
    }
  }
  showLoading(config);
  return config;
});

api.interceptors.response.use(
  (response) => {
    hideLoading(response.config);
    removePendingRequest(response.config);
    const payload = response.data;
    if (payload && typeof payload === "object" && "code" in payload) {
      if (payload.code !== "0") {
        const message = payload.message || "请求失败";
        const isAuthExpired =
          payload.code === "401" ||
          response.status === 401 ||
          (typeof message === "string" && message.includes("未登录"));
        if (isAuthExpired) {
          handleAuthExpired(message);
        }
        return Promise.reject(new Error(message));
      }
      return payload.data;
    }
    if (payload && typeof payload === "object" && "status" in payload) {
      if (payload.status !== "success") {
        const message = payload.message || payload.detail || "请求失败";
        return Promise.reject(new Error(typeof message === "string" ? message : JSON.stringify(message)));
      }
      return "data" in payload ? payload.data : payload;
    }
    return payload;
  },
  (error) => {
    const config = error?.config as AxiosRequestConfig | undefined;
    hideLoading(config);
    removePendingRequest(config);
    if (error instanceof CanceledError) {
      return Promise.reject(error);
    }
    if (error?.response?.status === 401) {
      handleAuthExpired();
      return Promise.reject(error);
    }
    if (error?.response?.status === 461) {
      toast.error("请先上传文档");
      if (window.location.pathname !== "/repository") {
        window.location.href = "/repository";
      }
      return Promise.reject(error);
    }
    if (config?.errorToast === false) {
      return Promise.reject(error);
    }
    const responseData = error?.response?.data;
    if (responseData && typeof responseData === "object" && "message" in responseData && responseData.message) {
      toast.error(responseData.message);
    } else if (responseData && typeof responseData === "object" && "detail" in responseData && responseData.detail) {
      const detail = responseData.detail;
      toast.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    } else if (error?.code === "ERR_NETWORK") {
      toast.error("网络错误，请检查网络连接");
    } else {
      toast.error((error as AxiosError)?.message || "网络错误");
    }
    return Promise.reject(error);
  }
);
