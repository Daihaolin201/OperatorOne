/**
 * Shared API response envelope — used across all HTTP endpoints
 */

export interface ApiSuccess<T> {
  ok: true;
  data: T;
  meta?: {
    page?: number;
    pageSize?: number;
    total?: number;
  };
}

export interface ApiError {
  ok: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

/** Pagination params */
export interface PaginationParams {
  page?: number;
  pageSize?: number;
}
