"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listConnectors,
  listAvailableConnectors,
  createConnector,
  triggerSync,
  deleteConnector,
} from "@/lib/api/connectors";

export const connectorKeys = {
  all: ["connectors"] as const,
  list: () => ["connectors", "list"] as const,
  available: () => ["connectors", "available"] as const,
};

export function useConnectors() {
  return useQuery({ queryKey: connectorKeys.list(), queryFn: listConnectors });
}

export function useAvailableConnectors() {
  return useQuery({
    queryKey: connectorKeys.available(),
    queryFn: listAvailableConnectors,
  });
}

export function useCreateConnector() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createConnector,
    onSuccess: () => qc.invalidateQueries({ queryKey: connectorKeys.all }),
  });
}

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerSync,
    onSuccess: () => qc.invalidateQueries({ queryKey: connectorKeys.all }),
  });
}

export function useDeleteConnector() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteConnector,
    onSuccess: () => qc.invalidateQueries({ queryKey: connectorKeys.all }),
  });
}
