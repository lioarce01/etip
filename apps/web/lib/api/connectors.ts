import { apiClient } from "./client";
import type { ConnectorConfig, ConnectorSchema } from "@/types/api";

export async function listConnectors(): Promise<ConnectorConfig[]> {
  return apiClient.get("api/v1/connectors").json<ConnectorConfig[]>();
}

export async function listAvailableConnectors(): Promise<string[]> {
  return apiClient.get("api/v1/connectors/available").json<string[]>();
}

export async function getConnectorSchema(name: string): Promise<ConnectorSchema> {
  return apiClient.get(`api/v1/connectors/${name}/schema`).json<ConnectorSchema>();
}

export async function createConnector(payload: {
  connector_name: string;
  config: Record<string, unknown>;
}): Promise<ConnectorConfig> {
  return apiClient
    .post("api/v1/connectors", { json: payload })
    .json<ConnectorConfig>();
}

export async function triggerSync(connectorId: string): Promise<void> {
  await apiClient.post(`api/v1/connectors/${connectorId}/sync`);
}

export async function deleteConnector(connectorId: string): Promise<void> {
  await apiClient.delete(`api/v1/connectors/${connectorId}`);
}
