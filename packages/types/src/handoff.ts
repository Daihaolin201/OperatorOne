/**
 * Handoff contract types — mirrors handoffs/*.json schema
 */

export type HandoffDirection =
  | "product_to_marketing"
  | "marketing_to_sales"
  | "sales_to_operations"
  | "operations_to_product"
  | "operations_to_marketing"
  | "operations_to_sales";

export interface HandoffMetadata {
  version: string;
  schema_version: string;
  produced_by: string;
  produced_at: string; // ISO 8601
  direction: HandoffDirection;
}

export interface HandoffContract<T = unknown> {
  metadata: HandoffMetadata;
  payload: T;
}
