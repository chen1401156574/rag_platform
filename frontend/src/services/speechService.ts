import type { AxiosRequestConfig } from "axios";

import { api, asDataResponse, withApiRoot, type DataResponse } from "@/services/api";

export function getVolcToken(
  params: {
    appid: string;
    accessKey: string;
  },
  options?: AxiosRequestConfig
): Promise<DataResponse<{ jwt_token?: string }>> {
  const { appid, accessKey } = params;
  return asDataResponse(
    api.post<{ jwt_token?: string }, { jwt_token?: string }>(
      "/sts-token",
      {
        appid,
        accessKey
      },
      withApiRoot(options)
    )
  );
}
