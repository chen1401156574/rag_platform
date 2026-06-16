import type { AxiosRequestConfig } from "axios";

import { api, asDataResponse, withApiRoot, type DataResponse } from "@/services/api";

export interface LegacyLoginResponse {
  access_token: string;
  token_type?: string;
}

export interface RegisterResponse {
  message: string;
}

export function register(
  params: {
    username: string;
    password: string;
  },
  options?: AxiosRequestConfig
): Promise<DataResponse<RegisterResponse>> {
  return asDataResponse(api.post<RegisterResponse, RegisterResponse>("/register", params, withApiRoot(options)));
}

export function login(
  params: {
    username: string;
    password: string;
  },
  options?: AxiosRequestConfig
): Promise<DataResponse<LegacyLoginResponse>> {
  return asDataResponse(api.post<LegacyLoginResponse, LegacyLoginResponse>("/login", params, withApiRoot(options)));
}
