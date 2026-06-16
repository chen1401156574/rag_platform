import "axios";

declare module "axios" {
  export interface AxiosRequestConfig {
    /**
     * 是否显示全屏 loading。
     */
    loading?: boolean;

    /**
     * 请求异常时是否显示 toast 提示。
     */
    errorToast?: boolean;

    /**
     * 是否取消重复请求，默认开启。
     */
    cancelRepeat?: boolean;
    repeatKey?: string;
  }
}
